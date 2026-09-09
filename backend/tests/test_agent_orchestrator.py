"""Contract, budget, timeout and retry tests for the Agent state machine."""
from datetime import datetime, timedelta, timezone

import pytest

from backend.app.agent import AgentOrchestrator, AgentTransitionError
from backend.app.schemas import KnowledgeVersion, PlanningRequest, Provenance, ToolError, ToolResult
from backend.app.schemas.validation import ValidationResult


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
VERSIONS = KnowledgeVersion(
    student_version="student-v1", curriculum_version="curriculum-v1",
    ontology_version="ontology-v1", rule_version="rules-v1", offering_version="offering-v1",
)


def request() -> PlanningRequest:
    return PlanningRequest(
        request_id="R1", student_id="S1", target_term_id="T1",
        goal="on_time", target_credits=15,
    )


def result(action, context, *, error: ToolError | None = None,
           knowledge_versions=None, finished_at=None) -> ToolResult[object]:
    provenance = Provenance(
        call_id=context.call_id, tool_name=action, tool_version="test-v1",
        input_hash=context.input_hash,
        output_hash=None if error else f"sha256:output-{action}",
        knowledge_versions=knowledge_versions,
        started_at=NOW, finished_at=finished_at or NOW,
    )
    if error:
        return ToolResult(status="error", error=error, provenance=provenance)
    return ToolResult(status="ok", output={"result": action}, provenance=provenance)


def call(orchestrator, state, action, *, knowledge_versions=None):
    context = orchestrator.create_call_context(state, action, f"sha256:input-{action}")
    return context, result(action, context, knowledge_versions=knowledge_versions)


def validation(status: str) -> ValidationResult:
    return ValidationResult.model_construct(
        plan_id="P1", plan_version="1", status=status,
        validator_version="standard-academic-v3", knowledge_versions=VERSIONS,
        validated_at=NOW,
    )


def state_at_generation(orchestrator: AgentOrchestrator, run_id="RUN1"):
    state = orchestrator.start(orchestrator.create_run(request(), run_id=run_id))
    for action, versions in (
        ("load_student_context", None),
        ("load_knowledge_context", VERSIONS),
        ("build_course_space", VERSIONS),
    ):
        context, tool_result = call(orchestrator, state, action, knowledge_versions=versions)
        state = orchestrator.apply_result(state, action, context, tool_result)
    return state


def test_orchestrator_enforces_order_and_validation_gate():
    orchestrator = AgentOrchestrator()
    state = state_at_generation(orchestrator)
    context, tool_result = call(orchestrator, state, "generate_candidates", knowledge_versions=VERSIONS)
    state = orchestrator.apply_generation_result(state, context, tool_result, ("sha256:plan-1",), 1, 5)
    assert state.status == "validating"
    assert state.candidate_attempts_used == 1

    with pytest.raises(AgentTransitionError):
        orchestrator.create_call_context(state, "rank_valid_plans", "sha256:input-ranking")

    context, tool_result = call(orchestrator, state, "validate_candidates", knowledge_versions=VERSIONS)
    state = orchestrator.apply_validations(state, (validation("valid"),), context, tool_result)
    assert state.status == "assessing_risk"
    assert [event.action for event in state.trace] == [
        "load_student_context", "load_knowledge_context", "build_course_space",
        "generate_candidates", "validate_candidates",
    ]


def test_invalid_plans_replan_then_stop_after_generation_budget():
    orchestrator = AgentOrchestrator(max_generation_rounds=2)
    state = state_at_generation(orchestrator, "RUN2")
    for expected in ("replanning", "no_plan_found"):
        context, tool_result = call(orchestrator, state, "generate_candidates", knowledge_versions=VERSIONS)
        state = orchestrator.apply_generation_result(state, context, tool_result, ("sha256:plan-1",), 1, 1)
        context, tool_result = call(orchestrator, state, "validate_candidates", knowledge_versions=VERSIONS)
        state = orchestrator.apply_validations(state, (validation("invalid"),), context, tool_result)
        assert state.status == expected
        if expected == "replanning":
            state = orchestrator.begin_replanning(state)


def test_late_result_stops_run_with_timeout():
    orchestrator = AgentOrchestrator()
    state = orchestrator.start(orchestrator.create_run(request(), run_id="RUN_TIMEOUT"))
    context = orchestrator.create_call_context(state, "load_student_context", "sha256:input")
    late = result("load_student_context", context, finished_at=context.deadline_at + timedelta(seconds=1))
    state = orchestrator.apply_result(state, "load_student_context", context, late)
    assert state.status == "failed"
    assert state.errors[-1].code == "TIMEOUT"


def test_retry_only_allows_safe_retryable_action_before_deadline():
    orchestrator = AgentOrchestrator()
    state = orchestrator.start(orchestrator.create_run(request(), run_id="RUN_RETRY"))
    context = orchestrator.create_call_context(state, "load_student_context", "sha256:input", attempt=1)
    transient = result(
        "load_student_context", context,
        error=ToolError(code="TEMPORARY", message="Source unavailable", retryable=True),
    )
    retried = orchestrator.apply_result(state, "load_student_context", context, transient)
    assert retried.status == "loading_context"
    assert retried.errors == ()
    assert retried.trace[-1].error.code == "TEMPORARY"

    retry_context = orchestrator.create_call_context(retried, "load_student_context", "sha256:input", attempt=2)
    recovered = orchestrator.apply_result(retried, "load_student_context", retry_context, result("load_student_context", retry_context))
    assert recovered.status == "loading_knowledge"


def test_generation_budget_stops_without_claiming_no_solution():
    orchestrator = AgentOrchestrator(max_candidate_attempts=1)
    state = state_at_generation(orchestrator, "RUN_BUDGET")
    context, tool_result = call(orchestrator, state, "generate_candidates", knowledge_versions=VERSIONS)
    stopped = orchestrator.apply_generation_result(state, context, tool_result, (), 2, 0)
    assert stopped.status == "needs_data"
    assert stopped.errors[-1].code == "CANDIDATE_BUDGET_EXCEEDED"


def test_mismatched_knowledge_version_cannot_pass_to_validator():
    orchestrator = AgentOrchestrator()
    state = state_at_generation(orchestrator, "RUN_VERSION")
    context, tool_result = call(orchestrator, state, "generate_candidates", knowledge_versions=VERSIONS)
    state = orchestrator.apply_generation_result(state, context, tool_result, ("sha256:plan-1",), 1, 1)
    other = KnowledgeVersion(
        student_version="student-v1", curriculum_version="curriculum-v1",
        ontology_version="ontology-v2", rule_version="rules-v1", offering_version="offering-v1",
    )
    context, tool_result = call(orchestrator, state, "validate_candidates", knowledge_versions=other)
    stopped = orchestrator.apply_validations(state, (validation("valid"),), context, tool_result)
    assert stopped.status == "failed"
    assert stopped.errors[-1].code == "VERSION_MISMATCH"
