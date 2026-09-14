"""Agent pipeline coordinating capabilities with structured logging."""
from __future__ import annotations

from hashlib import sha256
import json
import logging
from time import perf_counter
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from backend.app.agent.orchestrator import AgentOrchestrator
from backend.app.capabilities import (
    build_course_space,
    confirm_plan,
    generate_candidates,
    load_knowledge_context,
    load_student_context,
    assess_plan_risks,
    explain_plans,
    normalize_feedback,
    rank_plans,
    validate_candidate,
)
from backend.app.schemas import (
    AdjustmentRequest, AgentState, CandidatePlan, FeedbackRequest, KnowledgeSnapshot,
    PlanningRequest, Provenance, RankingResult, StudentSnapshot,
    ToolCallContext, ToolError, ToolResult, ValidatedPlan,
)
from backend.app.services.ontology_evidence_service import OntologyEvidenceService
from backend.app.services.ranking_context_service import build_ranking_context
from backend.app.services.recommendation_engine import RecommendationEngine
from backend.app.services.student_data_service import StudentDataService

logger = logging.getLogger(__name__)


def digest(value: object) -> str:
    return "sha256:" + sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


class _RunEvidenceCache:
    """Read-through cache: identical RDF facts are queried once per planning run."""
    def __init__(self, service: OntologyEvidenceService):
        self._service = service
        self._cache: dict[tuple, object] = {}

    def __getattr__(self, name):
        attribute = getattr(self._service, name)
        if not callable(attribute) or not name.startswith("get_"):
            return attribute
        def cached(*args, **kwargs):
            key = (name, args, tuple(sorted(kwargs.items())))
            if key not in self._cache:
                self._cache[key] = attribute(*args, **kwargs)
            return self._cache[key]
        return cached


class AgentPipeline:
    """Coordinates capability execution with orchestrator state management and detailed logging."""

    def __init__(
        self,
        student_service: StudentDataService,
        engine: RecommendationEngine,
        evidence: OntologyEvidenceService,
        orchestrator: AgentOrchestrator | None = None,
    ):
        self.student_service = student_service
        self.engine = engine
        self.evidence = evidence
        self.orchestrator = orchestrator or AgentOrchestrator()

    def run_planning_flow(self, request: PlanningRequest, *, adjustment: AdjustmentRequest | None = None,
                          parent_state: AgentState | None = None) -> dict:
        """Execute full planning flow: context → eligibility → generation → validation."""
        if adjustment is not None:
            request = request.model_copy(update={
                "request_id": request.request_id + f"-replan-{parent_state.iteration + 1 if parent_state else 1}",
                "target_credits": adjustment.new_target_credits or request.target_credits,
                "goal": adjustment.new_goal or request.goal,
            })
        run_id = f"RUN_{request.request_id}"
        run_started = perf_counter()
        tool_provenance = []
        evidence = _RunEvidenceCache(self.evidence)
        logger.info("=== AGENT PIPELINE START ===")
        logger.info("Run ID: %s", run_id)
        logger.info("Student ID: %s, Target: %s, Goal: %s", request.student_id, request.target_term_id, request.goal)

        state = self.orchestrator.create_run(request, run_id=run_id)
        if parent_state is not None:
            state = AgentState.model_validate({
                **state.model_dump(mode="python"),
                "iteration": parent_state.iteration + 1,
                "state_revision": parent_state.state_revision + 1,
                "trace": parent_state.trace,
                "feedback_hashes": parent_state.feedback_hashes,
                "latest_adjustment": adjustment,
                "candidate_attempts_used": parent_state.candidate_attempts_used,
                "expanded_states_used": parent_state.expanded_states_used,
            })
        state = self.orchestrator.start(state)
        logger.info("Initial state: %s (revision=%d)", state.status, state.state_revision)

        # Step 1: Load Student Context
        logger.info("\n--- [1/5] LOADING STUDENT CONTEXT ---")
        context = self.orchestrator.create_call_context(state, "load_student_context", digest(request.model_dump()))
        logger.info("Call ID: %s, Deadline: %s", context.call_id, context.deadline_at.isoformat())

        student_result = load_student_context(context, request, self.student_service)
        logger.info("Status: %s", student_result.status)
        if student_result.status == "error":
            logger.error("Error code: %s, message: %s", student_result.error.code, student_result.error.message)
            return self._error_response(state, student_result.error)

        state = self.orchestrator.apply_result(state, "load_student_context", context, student_result)
        tool_provenance.append(student_result.provenance)
        if state.status == "failed":
            return self._error_response(state, state.errors[-1])
        student = student_result.output.student_snapshot
        logger.info("Student loaded: %s, completed=%d courses, GPA=%.2f", student.student_id, len(student.completed_courses), student.gpa or 0)
        logger.info("State transition: loading_context → %s (revision=%d)", state.status, state.state_revision)

        # Step 2: Load Knowledge Context
        logger.info("\n--- [2/5] LOADING KNOWLEDGE CONTEXT ---")
        context = self.orchestrator.create_call_context(
            state, "load_knowledge_context", digest({"request": request.model_dump(), "student": student.model_dump()})
        )
        logger.info("Call ID: %s", context.call_id)

        knowledge_result = load_knowledge_context(context, request, student, self.engine, evidence)
        logger.info("Status: %s", knowledge_result.status)
        if knowledge_result.status == "error":
            logger.error("Error: %s", knowledge_result.error.message)
            return self._error_response(state, knowledge_result.error)

        state = self.orchestrator.apply_result(state, "load_knowledge_context", context, knowledge_result)
        tool_provenance.append(knowledge_result.provenance)
        if state.status == "failed":
            return self._error_response(state, state.errors[-1])
        knowledge = knowledge_result.output.knowledge_snapshot
        catalog = knowledge_result.output.catalog
        logger.info("Ontology loaded: version=%s, catalog=%d courses", knowledge.versions.ontology_version, len(catalog))
        logger.info("Policy: credits=%d-%d, quotas=%s", self.engine.min_credits, self.engine.max_credits, self.engine.elective_quotas)
        logger.info("State transition: loading_knowledge → %s (revision=%d)", state.status, state.state_revision)

        # Step 3: Build Course Space (Eligibility)
        logger.info("\n--- [3/5] BUILD COURSE SPACE (ELIGIBILITY) ---")
        profile = self.student_service.get_student(request.student_id)
        context = self.orchestrator.create_call_context(
            state, "build_course_space", digest({"student": student.model_dump(), "knowledge": knowledge.model_dump()})
        )
        logger.info("Call ID: %s", context.call_id)

        eligibility_result = build_course_space(context, student, knowledge, profile, self.engine)
        logger.info("Status: %s", eligibility_result.status)
        if eligibility_result.status == "error":
            logger.error("Error: %s", eligibility_result.error.message)
            return self._error_response(state, eligibility_result.error)

        state = self.orchestrator.apply_result(state, "build_course_space", context, eligibility_result)
        tool_provenance.append(eligibility_result.provenance)
        if state.status == "failed":
            return self._error_response(state, state.errors[-1])
        decisions = eligibility_result.output.decisions
        eligible_count = sum(1 for d in decisions if d.status == "eligible")
        ineligible_count = sum(1 for d in decisions if d.status == "ineligible")
        logger.info("Course space built: eligible=%d, ineligible=%d (total=%d)", eligible_count, ineligible_count, len(decisions))
        logger.info("State transition: building_course_space → %s (revision=%d)", state.status, state.state_revision)

        # Step 4: Generate Candidates
        logger.info("\n--- [4/5] GENERATE CANDIDATES (BEAM SEARCH) ---")
        context = self.orchestrator.create_call_context(
            state, "generate_candidates", digest({"space": eligibility_result.output.model_dump(), "seed": state.seed}),
            timeout_seconds=60,
        )
        logger.info("Call ID: %s, Seed: %d, Beam width: %d", context.call_id, state.seed, self.engine.beam_width)

        generation = generate_candidates(context, request, student, knowledge, profile, self.engine,
            candidate_limit=3, seed=state.seed, course_space=eligibility_result.output, adjustment=adjustment)
        logger.info("Status: %s", generation.status)
        if generation.status == "error" or not generation.output or not generation.output.candidates:
            if generation.status == "error" or generation.output is None:
                error = generation.error or ToolError(code="NO_CANDIDATES", message="Beam Search returned no candidates")
            elif adjustment is not None:
                reasons = sorted({item.reason for item in generation.output.attempt_records if item.reason})
                error = ToolError(
                    code="ADJUSTMENT_UNSATISFIED",
                    message="No generated candidate satisfies the requested adjustment"
                            + (f" (generation outcomes: {', '.join(reasons)})" if reasons else ""),
                )
            else:
                error = ToolError(code="NO_CANDIDATES", message="Beam Search returned no candidates")
            logger.error("Generation failed: %s", error.message)
            response = self._error_response(state, error)
            if adjustment is not None and generation.output is not None:
                response["adjustment"] = adjustment.model_dump(mode="json")
                response["generation"] = generation.output.model_dump(mode="json")
            return response

        hashes = tuple("sha256:" + sha256(plan.model_dump_json().encode()).hexdigest() for plan in generation.output.candidates)
        state = self.orchestrator.apply_generation_result(
            state,
            context,
            generation,
            hashes,
            len(generation.output.attempt_records),
            generation.output.expanded_states,
        )
        tool_provenance.append(generation.provenance)
        if state.status != "validating":
            return self._error_response(state, state.errors[-1])
        logger.info("Candidates generated: %d plans, attempts=%d, expanded_states=%d, duplicates=%d",
                    len(generation.output.candidates), len(generation.output.attempt_records),
                    generation.output.expanded_states, generation.output.duplicate_count)
        for i, candidate in enumerate(generation.output.candidates):
            logger.info("  Plan %d: type=%s, courses=%d, credits=%.1f",
                        i + 1, candidate.plan_type, len(candidate.courses), sum(c.credits for c in candidate.courses))
        logger.info("State transition: generating → %s (revision=%d)", state.status, state.state_revision)

        # Step 5: Validate Candidates
        # One shared call context so provenance.call_id / input_hash match apply_validations.
        logger.info("\n--- [5/5] VALIDATE CANDIDATES ---")
        batch_hash = digest([c.model_dump() for c in generation.output.candidates])
        context = self.orchestrator.create_call_context(
            state, "validate_candidates", batch_hash, timeout_seconds=180
        )
        logger.info("Call ID: %s (batch of %d)", context.call_id, len(generation.output.candidates))

        validation_results = []
        validated_plans = []
        batch_tool_result = None
        validation_started = None
        for i, candidate in enumerate(generation.output.candidates):
            logger.info("Validating plan %d/%d: %s", i + 1, len(generation.output.candidates), candidate.plan_id)
            validated = validate_candidate(
                context,
                candidate,
                student,
                knowledge,
                evidence,
                min_credits=self.engine.min_credits,
                max_credits=self.engine.max_credits,
            )
            tool_provenance.append(validated.provenance)
            if validation_started is None:
                validation_started = validated.provenance.started_at
            logger.info("  Status: %s", validated.status)
            if validated.status == "error":
                logger.error("  Validator error: %s", validated.error.message if validated.error else "unknown")
                return self._error_response(state, validated.error)
            item = validated.output.validation if hasattr(validated.output, "validation") else validated.output
            if isinstance(validated.output, ValidatedPlan):
                validated_plans.append(validated.output)
            logger.info("  Validation result: status=%s, checked=%d/%d, violations=%d, evidence=%d, ontology_facts=%d",
                        item.status, len(item.checked_rules), len(item.checked_rules) + len(item.pending_rules),
                        len(item.violations), len(item.evidence), len(item.ontology_evidence))
            logger.info("  Versions: ontology=%s rule=%s validator=%s",
                        item.knowledge_versions.ontology_version, item.knowledge_versions.rule_version,
                        item.validator_version)
            if item.violations:
                for v in item.violations[:3]:
                    courses_str = ",".join(v.course_codes) if v.course_codes else "N/A"
                    logger.info("    Violation: constraint=%s, courses=%s, evidence=%s",
                                v.constraint_id, courses_str, ",".join(v.evidence_ids))
            validation_results.append(item)
            batch_tool_result = validated

        if not validation_results or batch_tool_result is None:
            error = ToolError(code="VALIDATION_ERROR", message="No validation results produced")
            logger.error("Validation failed: %s", error.message)
            return self._error_response(state, error)

        # Bind the trace to the entire batch, not just the last candidate.
        batch_tool_result = ToolResult(status="ok", output=tuple(validation_results),
            provenance=Provenance(
                call_id=context.call_id, tool_name="validate_candidates",
                tool_version=batch_tool_result.provenance.tool_version,
                input_hash=context.input_hash,
                output_hash=digest([v.model_dump(mode="json") for v in validation_results]),
                knowledge_versions=knowledge.versions, source_refs=(knowledge.ontology_ref,),
                evidence_ids=tuple(e.evidence_id for v in validation_results for e in v.evidence),
                started_at=validation_started, finished_at=batch_tool_result.provenance.finished_at))
        state = self.orchestrator.apply_validations(
            state, tuple(validation_results), context, batch_tool_result
        )
        valid_count = sum(1 for v in validation_results if v.status == "valid")
        invalid_count = sum(1 for v in validation_results if v.status != "valid")
        logger.info("Validation complete: valid=%d, invalid=%d", valid_count, invalid_count)
        logger.info("State transition: validating → %s (revision=%d)", state.status, state.state_revision)

        ranking_context = None
        risk_batch = None
        ranking_result = None
        explanations = None
        if state.status == "assessing_risk":
            logger.info("\n--- [6/7] ASSESS PLAN RISK ---")
            try:
                ranking_context = build_ranking_context(profile, student, knowledge, request, self.engine)
            except Exception as exc:
                error = ToolError(code="RANKING_CONTEXT_ERROR", message=str(exc))
                state = self.orchestrator.fail_for_missing_data(state, error)
                return self._result(state, request, student, knowledge_result, eligibility_result,
                    generation, validation_results, tool_provenance, run_started,
                    ranking_context=None, risk_batch=None, ranking_result=None, explanations=None)
            context = self.orchestrator.create_call_context(state, "assess_plan_risk",
                digest({"plans": [p.candidate_hash for p in validated_plans],
                        "ranking_context": ranking_context.model_dump(mode="json")}), timeout_seconds=10)
            risk_result = assess_plan_risks(context, tuple(validated_plans), student, ranking_context)
            state = self.orchestrator.apply_result(state, "assess_plan_risk", context, risk_result)
            tool_provenance.append(risk_result.provenance)
            if risk_result.status == "error" or state.status == "failed":
                return self._error_response(state, risk_result.error or state.errors[-1])
            risk_batch = risk_result.output
            logger.info("Risk complete: plans=%d, status=%s", len(risk_batch.results), state.status)

            logger.info("\n--- [7/7] RANK VALID PLANS + DIVERSITY ---")
            context = self.orchestrator.create_call_context(state, "rank_valid_plans",
                digest({"risk": risk_batch.model_dump(mode="json"),
                        "ranking_context": ranking_context.model_dump(mode="json")}), timeout_seconds=10)
            ranked = rank_plans(context, tuple(validated_plans), risk_batch, ranking_context,
                request, profile, self.engine)
            state = self.orchestrator.apply_result(state, "rank_valid_plans", context, ranked)
            tool_provenance.append(ranked.provenance)
            if ranked.status == "error" or state.status == "failed":
                return self._error_response(state, ranked.error or state.errors[-1])
            ranking_result = ranked.output
            logger.info("Ranking complete: scored=%d, selected=%d, recommended=%s, status=%s",
                len(ranking_result.scored_plans), len(ranking_result.selected_plans),
                ranking_result.recommended_plan_id, state.status)

            logger.info("\n--- [8/8] BUILD GROUNDED EXPLANATIONS ---")
            context = self.orchestrator.create_call_context(state, "explain_plans",
                digest({"ranking": ranking_result.model_dump(mode="json"),
                        "plans": [plan.candidate_hash for plan in validated_plans]}), timeout_seconds=10)
            explained = explain_plans(context, tuple(validated_plans), risk_batch, ranking_result)
            state = self.orchestrator.apply_result(state, "explain_plans", context, explained)
            tool_provenance.append(explained.provenance)
            if explained.status == "error" or state.status == "failed":
                return self._error_response(state, explained.error or state.errors[-1])
            explanations = explained.output
            logger.info("Explanation complete: plans=%d, claims=%d, status=%s",
                len(explanations.explanations), sum(len(item.claims) for item in explanations.explanations), state.status)

        logger.info("\n=== AGENT PIPELINE COMPLETE ===")
        logger.info("Final state: %s", state.status)
        logger.info("Budget used: candidates=%d/%d, expanded_states=%d/%d",
                    state.candidate_attempts_used, state.max_candidate_attempts,
                    state.expanded_states_used, state.max_expanded_states)

        return self._result(state, request, student, knowledge_result, eligibility_result,
            generation, validation_results, tool_provenance, run_started,
            ranking_context=ranking_context, risk_batch=risk_batch, ranking_result=ranking_result,
            explanations=explanations)

    def replan_from_feedback(self, previous_result: dict, feedback: FeedbackRequest) -> dict:
        """Normalize a displayed modification and run a new versioned planning round."""
        state = AgentState.model_validate(previous_result["state"])
        ranking = RankingResult.model_validate(previous_result["ranking"])
        if state.status != "awaiting_feedback":
            raise ValueError("REPLAN_REQUIRES_AWAITING_FEEDBACK")
        if feedback.run_id != state.run_id:
            raise ValueError("FEEDBACK_RUN_MISMATCH")
        context = self.orchestrator.create_call_context(state, "normalize_feedback",
            digest({"feedback": feedback.model_dump(mode="json"), "ranking": ranking.model_dump(mode="json")}))
        normalized = normalize_feedback(context, feedback, ranking, state.knowledge_versions)
        state = self.orchestrator.apply_result(state, "normalize_feedback", context, normalized)
        if normalized.status == "error" or state.status != "replanning":
            raise ValueError(normalized.error.message if normalized.error else "FEEDBACK_DOES_NOT_REQUEST_REPLAN")
        result = self.run_planning_flow(PlanningRequest.model_validate(previous_result["request"]),
            adjustment=normalized.output.adjustment, parent_state=state)
        result["feedback_normalization"] = normalized.output.model_dump(mode="json")
        result["parent_run_id"] = previous_result["run_id"]
        return result

    def confirm_from_feedback(self, previous_result: dict, feedback: FeedbackRequest) -> dict:
        """Refresh sources, normalize confirmation and re-run StandardValidator."""
        state = AgentState.model_validate(previous_result["state"])
        ranking = RankingResult.model_validate(previous_result["ranking"])
        if state.status != "awaiting_feedback":
            raise ValueError("CONFIRM_REQUIRES_AWAITING_FEEDBACK")
        if feedback.action != "confirm":
            raise ValueError("CONFIRM_REQUIRES_CONFIRM_FEEDBACK")
        if feedback.run_id != state.run_id:
            raise ValueError("FEEDBACK_RUN_MISMATCH")
        feedback_context = self.orchestrator.create_call_context(
            state, "normalize_feedback",
            digest({"feedback": feedback.model_dump(mode="json"), "ranking": ranking.model_dump(mode="json")}),
        )
        normalized = normalize_feedback(feedback_context, feedback, ranking, state.knowledge_versions)
        state = self.orchestrator.apply_result(state, "normalize_feedback", feedback_context, normalized)
        if normalized.status == "error" or state.status != "final_validating":
            raise ValueError(normalized.error.message if normalized.error else "FEEDBACK_DOES_NOT_CONFIRM")

        candidates = {item.plan_id: item for item in
                      (CandidatePlan.model_validate(value) for value in previous_result["candidates"])}
        candidate = candidates.get(feedback.selected_plan_id)
        if candidate is None:
            raise ValueError("SELECTED_PLAN_NOT_AVAILABLE")
        previous_student = StudentSnapshot.model_validate(previous_result["student_snapshot"])
        previous_knowledge = KnowledgeSnapshot.model_validate(previous_result["knowledge_snapshot"])
        current_student, current_knowledge = self._refresh_confirmation_context(
            state, PlanningRequest.model_validate(previous_result["request"]))
        if (current_student.student_version != previous_student.student_version
                or current_knowledge.versions != previous_knowledge.versions):
            refreshed_request = PlanningRequest.model_validate(previous_result["request"]).model_copy(update={
                "request_id": PlanningRequest.model_validate(previous_result["request"]).request_id
                + f"-refresh-{state.iteration + 1}",
            })
            refreshed = self.run_planning_flow(refreshed_request, parent_state=state)
            refreshed.update({
                "confirmation_refresh_required": True,
                "parent_run_id": previous_result["run_id"],
                "source_versions_before": {
                    "student_version": previous_student.student_version,
                    "knowledge_versions": previous_knowledge.versions.model_dump(mode="json"),
                },
                "source_versions_after": {
                    "student_version": current_student.student_version,
                    "knowledge_versions": current_knowledge.versions.model_dump(mode="json"),
                },
            })
            return refreshed
        confirmation_context = self.orchestrator.create_call_context(
            state, "confirm", digest({"candidate": candidate.model_dump(mode="json"),
                                       "student": current_student.model_dump(mode="json"),
                                       "knowledge": current_knowledge.model_dump(mode="json")}))
        confirmation = confirm_plan(confirmation_context, candidate, current_student, current_knowledge, self.evidence,
                                    min_credits=self.engine.min_credits, max_credits=self.engine.max_credits)
        state = self.orchestrator.apply_result(state, "confirm", confirmation_context, confirmation)
        if confirmation.status == "error" or state.status != "confirmed":
            raise ValueError(confirmation.error.message if confirmation.error else "CONFIRMATION_FAILED")

        result = dict(previous_result)
        result.update({
            "success": True,
            "status": state.status,
            "state": state.model_dump(mode="json"),
            "trace": [event.model_dump(mode="json") for event in state.trace],
            "errors": [error.model_dump(mode="json") for error in state.errors],
            "confirmation": confirmation.output.model_dump(mode="json"),
            "feedback_normalization": normalized.output.model_dump(mode="json"),
        })
        return result

    def _refresh_confirmation_context(self, state: AgentState,
                                      request: PlanningRequest) -> tuple[StudentSnapshot, KnowledgeSnapshot]:
        """Reload source snapshots outside the old plan before the final validator runs."""
        deadline = datetime.now(timezone.utc) + timedelta(seconds=20)
        student_context = ToolCallContext(
            run_id=state.run_id, call_id=f"CALL_REFRESH_STUDENT_{uuid4().hex}", iteration=state.iteration,
            contract_version=self.orchestrator.CONTRACT_VERSION, deadline_at=deadline,
            attempt=1, input_hash=digest({"refresh": "student", "request": request.model_dump(mode="json")}))
        student_result = load_student_context(student_context, request, self.student_service)
        if student_result.status == "error" or student_result.output is None:
            raise ValueError(student_result.error.message if student_result.error else "CURRENT_STUDENT_CONTEXT_ERROR")
        student = student_result.output.student_snapshot
        knowledge_context = ToolCallContext(
            run_id=state.run_id, call_id=f"CALL_REFRESH_KNOWLEDGE_{uuid4().hex}", iteration=state.iteration,
            contract_version=self.orchestrator.CONTRACT_VERSION, deadline_at=deadline,
            attempt=1, input_hash=digest({"refresh": "knowledge", "student": student.model_dump(mode="json")}))
        knowledge_result = load_knowledge_context(knowledge_context, request, student, self.engine, self.evidence)
        if knowledge_result.status == "error" or knowledge_result.output is None:
            raise ValueError(knowledge_result.error.message if knowledge_result.error else "CURRENT_KNOWLEDGE_CONTEXT_ERROR")
        return student, knowledge_result.output.knowledge_snapshot

    def _result(self, state, request, student, knowledge_result, eligibility_result,
                generation, validation_results, tool_provenance, run_started, *,
                ranking_context, risk_batch, ranking_result, explanations=None):
        knowledge = knowledge_result.output.knowledge_snapshot
        return {
            "success": state.status != "failed",
            "run_id": state.run_id,
            "status": state.status,
            "iteration": state.iteration,
            "request": request.model_dump(mode="json"),
            "state": state.model_dump(mode="json"),
            "student_snapshot": student.model_dump(mode="json"),
            "knowledge_snapshot": knowledge.model_dump(mode="json"),
            "knowledge_context": knowledge_result.output.model_dump(mode="json"),
            "course_space": eligibility_result.output.model_dump(mode="json"),
            "generation": generation.output.model_dump(mode="json"),
            "candidates": [c.model_dump(mode="json") for c in generation.output.candidates],
            "validations": [v.model_dump(mode="json") for v in validation_results],
            "ranking_context": ranking_context.model_dump(mode="json") if ranking_context else None,
            "risk": risk_batch.model_dump(mode="json") if risk_batch else None,
            "ranking": ranking_result.model_dump(mode="json") if ranking_result else None,
            "explanations": explanations.model_dump(mode="json") if explanations else None,
            "tool_provenance": [p.model_dump(mode="json") for p in tool_provenance],
            "elapsed_seconds": perf_counter() - run_started,
            "errors": [e.model_dump(mode="json") for e in state.errors],
            "budget": {
                "candidate_attempts_used": state.candidate_attempts_used,
                "candidate_attempts_max": state.max_candidate_attempts,
                "expanded_states_used": state.expanded_states_used,
                "expanded_states_max": state.max_expanded_states,
            },
            "trace": [event.model_dump(mode="json") for event in state.trace],
        }

    def _error_response(self, state, error: ToolError) -> dict:
        """Build error response with state snapshot."""
        return {
            "success": False,
            "error": error.model_dump(),
            "run_id": state.run_id,
            "status": state.status,
            "iteration": state.iteration,
            "trace": [event.model_dump() for event in state.trace],
        }


def run_agent_pipeline(
    request: PlanningRequest,
    student_service: StudentDataService,
    engine: RecommendationEngine,
    evidence: OntologyEvidenceService,
    orchestrator: AgentOrchestrator | None = None,
) -> dict:
    """Convenience entrypoint for Flask routes and demo scripts."""
    return AgentPipeline(student_service, engine, evidence, orchestrator).run_planning_flow(request)
