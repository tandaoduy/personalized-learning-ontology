"""State machine and capability contract gate for the planning Agent."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from uuid import uuid4

from backend.app.agent.trace import TraceRecorder
from backend.app.schemas.agent_state import AgentState, ArtifactReference, ToolAction, ValidationSummary
from backend.app.schemas.capability import ToolCallContext, ToolError, ToolResult
from backend.app.schemas.planning import PlanningRequest
from backend.app.schemas.validation import ValidationResult


class AgentTransitionError(ValueError):
    """Raised when a capability result cannot be applied to the current State."""


class AgentOrchestrator:
    CONTRACT_VERSION = "agent-orchestrator-v1"
    MAX_RETRY_ATTEMPTS = 2
    _EXPECTED_STATUS = {
        "load_student_context": {"loading_context"},
        "load_knowledge_context": {"loading_knowledge"},
        "build_course_space": {"building_course_space"},
        "generate_candidates": {"generating"},
        "assess_plan_risk": {"assessing_risk"},
        "rank_valid_plans": {"ranking"},
        "explain_plans": {"explaining"},
        "normalize_feedback": {"awaiting_feedback"},
        "confirm": {"final_validating"},
    }
    _NEXT_STATUS = {
        "load_student_context": "loading_knowledge",
        "load_knowledge_context": "building_course_space",
        "build_course_space": "generating",
        "assess_plan_risk": "ranking",
        "rank_valid_plans": "explaining",
        "explain_plans": "awaiting_feedback",
        "normalize_feedback": "replanning",
        "confirm": "confirmed",
    }
    _RETRYABLE_ACTIONS = {
        "load_student_context", "load_knowledge_context", "build_course_space",
        "generate_candidates", "assess_plan_risk", "rank_valid_plans", "explain_plans",
        "validate_candidates",
    }

    def __init__(self, max_generation_rounds: int = 3, max_candidate_attempts: int = 60,
                 max_expanded_states: int = 5000, max_active_seconds: int = 120, seed: int = 42):
        if min(max_generation_rounds, max_candidate_attempts, max_expanded_states, max_active_seconds) < 1:
            raise ValueError("Agent budgets must be positive")
        self.max_generation_rounds = max_generation_rounds
        self.max_candidate_attempts = max_candidate_attempts
        self.max_expanded_states = max_expanded_states
        self.max_active_seconds = max_active_seconds
        self.seed = seed

    def create_run(self, request: PlanningRequest, run_id: str | None = None) -> AgentState:
        now = self._now()
        return AgentState(
            run_id=run_id or f"RUN_{uuid4().hex}", request=request,
            max_generation_rounds=self.max_generation_rounds,
            max_candidate_attempts=self.max_candidate_attempts,
            max_expanded_states=self.max_expanded_states,
            max_active_seconds=self.max_active_seconds, seed=self.seed,
            created_at=now, updated_at=now,
            active_deadline_at=now + timedelta(seconds=self.max_active_seconds),
        )

    def start(self, state: AgentState) -> AgentState:
        self._require_status(state, {"received"}, "start")
        return self._replace(state, status="loading_context")

    def create_call_context(self, state: AgentState, action: ToolAction, input_hash: str,
                            attempt: int = 1, timeout_seconds: int = 10) -> ToolCallContext:
        self._require_status(state, self._expected(action), action)
        if attempt < 1 or attempt > self.MAX_RETRY_ATTEMPTS:
            raise AgentTransitionError("Invalid capability attempt")
        deadline = min(state.active_deadline_at, self._now() + timedelta(seconds=max(1, timeout_seconds)))
        return ToolCallContext(
            run_id=state.run_id, call_id=f"CALL_{uuid4().hex}", iteration=state.iteration,
            contract_version=self.CONTRACT_VERSION, deadline_at=deadline,
            attempt=attempt, input_hash=input_hash,
        )

    def apply_result(self, state: AgentState, action: ToolAction, context: ToolCallContext,
                     result: ToolResult[object]) -> AgentState:
        if action in {"validate_candidates", "generate_candidates"}:
            raise AgentTransitionError(f"Use the dedicated handler for {action}")
        self._require_status(state, self._expected(action), action)
        contract_error = self._contract_error(state, action, context, result)
        if contract_error:
            return self._stop_with_error(state, action, context, result, contract_error)
        if result.status == "error":
            return self._handle_tool_error(state, action, context, result)
        changes = {"status": self._NEXT_STATUS[action]}
        output_hash = result.provenance.output_hash
        if action == "load_student_context":
            changes["student_snapshot_hash"] = output_hash
        elif action == "load_knowledge_context":
            changes["knowledge_snapshot_hash"] = output_hash
            changes["knowledge_versions"] = result.provenance.knowledge_versions
        elif action == "build_course_space":
            changes["course_space_hash"] = output_hash
        elif action == "assess_plan_risk":
            changes["risk_hashes"] = state.risk_hashes + (output_hash,)
        elif action == "rank_valid_plans":
            changes["ranking_hash"] = output_hash
        elif action == "explain_plans":
            changes["explanation_hashes"] = state.explanation_hashes + (output_hash,)
        elif action == "normalize_feedback":
            changes["feedback_hashes"] = state.feedback_hashes + (output_hash,)
        elif action == "confirm":
            changes["final_result_hash"] = output_hash
            changes["final_validation_hash"] = output_hash
        return self._replace_with_trace(state, action, context, result, **changes)

    def apply_generation_result(self, state: AgentState, context: ToolCallContext, result: ToolResult[object],
                                candidate_hashes: tuple[str, ...], candidate_attempts: int,
                                expanded_states: int) -> AgentState:
        action = "generate_candidates"
        self._require_status(state, self._expected(action), action)
        contract_error = self._contract_error(state, action, context, result)
        if contract_error:
            return self._stop_with_error(state, action, context, result, contract_error)
        if result.status == "error":
            return self._handle_tool_error(state, action, context, result)
        if candidate_attempts < 0 or expanded_states < 0:
            raise AgentTransitionError("Generation usage cannot be negative")
        if state.candidate_attempts_used + candidate_attempts > state.max_candidate_attempts:
            return self.fail_for_missing_data(state, ToolError(code="CANDIDATE_BUDGET_EXCEEDED", message="Candidate attempt budget exceeded"))
        if state.expanded_states_used + expanded_states > state.max_expanded_states:
            return self.fail_for_missing_data(state, ToolError(code="STATE_BUDGET_EXCEEDED", message="Expanded-state budget exceeded"))
        return self._replace_with_trace(
            state, action, context, result, status="validating",
            candidate_hashes=tuple(candidate_hashes),
            candidate_attempts_used=state.candidate_attempts_used + candidate_attempts,
            expanded_states_used=state.expanded_states_used + expanded_states,
        )

    def apply_validations(self, state: AgentState, results: tuple[ValidationResult, ...],
                          context: ToolCallContext, result: ToolResult[object]) -> AgentState:
        action = "validate_candidates"
        self._require_status(state, {"validating"}, action)
        contract_error = self._contract_error(state, action, context, result)
        if contract_error:
            return self._stop_with_error(state, action, context, result, contract_error)
        if result.status == "error":
            return self._handle_tool_error(state, action, context, result)
        if not results:
            raise AgentTransitionError("Validator batch must contain at least one result")
        if state.knowledge_versions is None:
            raise AgentTransitionError("Validation requires knowledge version")
        if any(item.knowledge_versions != state.knowledge_versions for item in results):
            raise AgentTransitionError("Validation snapshot version mismatch")
        summaries = tuple(
            ValidationSummary(plan_id=item.plan_id, plan_version=item.plan_version,
                              status=item.status, validation_hash=self._validation_hash(item))
            for item in results
        )
        valid = tuple(item for item in summaries if item.status == "valid")
        if valid:
            return self._replace_with_trace(state, action, context, result,
                                            status="assessing_risk", validations=summaries)
        if state.iteration + 1 >= state.max_generation_rounds:
            return self._replace_with_trace(state, action, context, result,
                                            status="no_plan_found", validations=summaries)
        return self._replace_with_trace(state, action, context, result,
                                        status="replanning", iteration=state.iteration + 1,
                                        validations=summaries)

    def begin_replanning(self, state: AgentState) -> AgentState:
        self._require_status(state, {"replanning"}, "begin_replanning")
        return self._replace(state, status="generating")

    def begin_final_validation(self, state: AgentState, selected_plan_id: str) -> AgentState:
        self._require_status(state, {"awaiting_feedback"}, "begin_final_validation")
        valid_ids = {item.plan_id for item in state.validations if item.status == "valid"}
        if selected_plan_id not in valid_ids:
            raise AgentTransitionError("Only a valid displayed plan may be selected")
        return self._replace(state, status="final_validating", selected_plan_id=selected_plan_id)

    def attach_artifact(self, state: AgentState, artifact: ArtifactReference) -> AgentState:
        return self._replace(state, artifacts=state.artifacts + (artifact,))

    def fail_for_missing_data(self, state: AgentState, error: ToolError) -> AgentState:
        return self._replace(state, status="needs_data", errors=state.errors + (error,))

    def should_retry(self, state: AgentState, action: ToolAction, context: ToolCallContext,
                     result: ToolResult[object]) -> bool:
        return (
            result.status == "error" and result.error is not None and result.error.retryable
            and action in self._RETRYABLE_ACTIONS and context.attempt < self.MAX_RETRY_ATTEMPTS
            and self._now() <= context.deadline_at and self._now() <= state.active_deadline_at
        )

    def _handle_tool_error(self, state, action, context, result):
        trace = TraceRecorder.from_result(action, result, state.iteration, context.deadline_at, context.attempt)
        if self.should_retry(state, action, context, result):
            return self._replace(state, trace=state.trace + (trace,))
        return self._replace(state, status="failed", trace=state.trace + (trace,), errors=state.errors + (result.error,))

    def _stop_with_error(self, state, action, context, result, error):
        forced = ToolResult(status="error", error=error, provenance=result.provenance)
        trace = TraceRecorder.from_result(action, forced, state.iteration, context.deadline_at, context.attempt)
        return self._replace(state, status="failed", trace=state.trace + (trace,), errors=state.errors + (error,))

    def _contract_error(self, state, action, context, result):
        if context.run_id != state.run_id or context.iteration != state.iteration:
            return ToolError(code="STALE_CONTEXT", message="Tool context belongs to another run or iteration")
        if context.contract_version != self.CONTRACT_VERSION:
            return ToolError(code="CONTRACT_VERSION_MISMATCH", message="Tool context contract version differs")
        if result.provenance.call_id != context.call_id or result.provenance.input_hash != context.input_hash:
            return ToolError(code="PROVENANCE_MISMATCH", message="Tool provenance does not match call context")
        if result.provenance.tool_name != action:
            return ToolError(code="TOOL_NAME_MISMATCH", message="Tool provenance name differs from requested action")
        if result.provenance.finished_at > context.deadline_at or result.provenance.finished_at > state.active_deadline_at:
            return ToolError(code="TIMEOUT", message="Tool result arrived after its deadline")
        if action == "load_knowledge_context" and result.status == "ok" and result.provenance.knowledge_versions is None:
            return ToolError(code="VERSION_MISSING", message="Knowledge context must provide knowledge versions")
        if state.knowledge_versions is not None and action not in {"load_student_context", "load_knowledge_context"}:
            if result.provenance.knowledge_versions != state.knowledge_versions:
                return ToolError(code="VERSION_MISMATCH", message="Tool result uses a different knowledge version")
        return None

    @staticmethod
    def _validation_hash(result: ValidationResult) -> str:
        payload = result.model_dump_json(exclude={"validated_at"})
        return "sha256:" + sha256(payload.encode("utf-8")).hexdigest()

    def _replace_with_trace(self, state, action, context, result, **changes):
        trace = TraceRecorder.from_result(action, result, state.iteration, context.deadline_at, context.attempt)
        changes["trace"] = state.trace + (trace,)
        return self._replace(state, **changes)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _replace(self, state: AgentState, **changes: object) -> AgentState:
        changes.setdefault("updated_at", self._now())
        changes.setdefault("state_revision", state.state_revision + 1)
        return AgentState.model_validate(
            {**state.model_dump(mode="python"), **changes}
        )

    def _expected(self, action: ToolAction) -> set[str]:
        if action == "validate_candidates":
            return {"validating"}
        if action == "generate_candidates":
            return {"generating"}
        return self._EXPECTED_STATUS[action]

    @staticmethod
    def _require_status(state: AgentState, expected: set[str], action: str) -> None:
        if state.status not in expected:
            raise AgentTransitionError(f"Action {action} requires state: {', '.join(sorted(expected))}; got {state.status}")
