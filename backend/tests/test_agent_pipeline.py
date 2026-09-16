"""End-to-end integration test for AgentPipeline through orchestrator."""
from copy import deepcopy
from datetime import datetime, timezone
import pytest

pytestmark = pytest.mark.integration

from backend.app.agent import AgentOrchestrator
import backend.app.agent.pipeline as pipeline_module
from backend.app.agent.pipeline import AgentPipeline
from backend.app.config import Config
from backend.app.schemas import FeedbackOperation, FeedbackRequest, PlanningRequest, RankingResult
from backend.app.services.grounded_explanation_service import ranking_hash
from backend.app.services.feedback_service import normalize_feedback
from backend.app.services.ontology_evidence_service import OntologyEvidenceService
from backend.app.services.recommendation_engine import RecommendationEngine
from backend.app.services.student_data_service import StudentDataService


@pytest.fixture(scope="module")
def pipeline():
    """Initialize pipeline with real project sources once per module."""
    students = StudentDataService(Config.STUDENT_DATA_JSON, Config.STUDENT_DATA_CSV)
    engine = RecommendationEngine(
        Config.ONTOLOGY_PATH,
        beam_width=Config.BEAM_WIDTH,
        min_credits=Config.REGISTER_MIN_CREDITS,
        max_credits=Config.REGISTER_MAX_CREDITS,
        elective_quotas=Config.ELECTIVE_QUOTAS,
    )
    evidence = OntologyEvidenceService(Config.ONTOLOGY_PATH)
    orchestrator = AgentOrchestrator()
    return AgentPipeline(students, engine, evidence, orchestrator)


def test_pipeline_e2e_generates_and_validates_candidates(pipeline):
    """Full pipeline: student → knowledge → eligibility → beam → validation."""
    request = PlanningRequest(
        request_id="test-e2e",
        student_id="SV001",
        target_term_id="next-term",
        goal="on_time",
        target_credits=15,
    )

    result = pipeline.run_planning_flow(request)

    assert result["success"] is True
    assert result["run_id"].startswith("RUN_")
    assert result["status"] in {"awaiting_feedback", "replanning", "no_plan_found"}
    assert result["iteration"] >= 0

    student = result["student_snapshot"]
    assert student["student_id"]
    assert "completed_courses" in student
    assert student["specialization_id"].endswith("#CNPM")

    knowledge = result["knowledge_snapshot"]
    assert knowledge["versions"]["ontology_version"]
    assert knowledge["curriculum_id"]

    assert len(result["candidates"]) > 0
    for candidate in result["candidates"]:
        assert "plan_id" in candidate
        assert "courses" in candidate
        assert candidate["plan_type"] in {"safe", "balanced", "accelerated"}

    assert len(result["validations"]) == len(result["candidates"])
    for validation in result["validations"]:
        assert validation["status"] in {"valid", "invalid", "partially_validated", "error"}
        assert validation["validator_version"] == "standard-academic-v3"
        assert not any(v["constraint_id"] == "curriculum_membership" for v in validation["violations"])

    budget = result["budget"]
    assert 0 <= budget["candidate_attempts_used"] <= budget["candidate_attempts_max"]
    assert 0 <= budget["expanded_states_used"] <= budget["expanded_states_max"]

    expected_actions = {
        "load_student_context",
        "load_knowledge_context",
        "build_course_space",
        "generate_candidates",
        "validate_candidates",
    }
    if result["status"] == "awaiting_feedback":
        expected_actions.update({"assess_plan_risk", "rank_valid_plans", "explain_plans"})
        assert result["ranking"]["selected_plans"]
        assert result["explanations"]["explanations"]
    trace_actions = {event["action"] for event in result["trace"]}
    assert expected_actions.issubset(trace_actions)


def test_pipeline_handles_missing_student(pipeline):
    """Pipeline returns a structured error when the student is missing."""
    request = PlanningRequest(
        request_id="test-missing",
        student_id="INVALID_STUDENT",
        target_term_id="next-term",
        goal="on_time",
        target_credits=15,
    )

    result = pipeline.run_planning_flow(request)

    assert result["success"] is False
    assert result["error"]["code"] in {"STUDENT_NOT_FOUND", "STUDENT_CONTEXT_ERROR"}
    assert result["status"] in {"loading_context", "failed"}


def test_pipeline_trace_records_capability_outcomes(pipeline):
    """Trace events cover each capability and carry required provenance fields."""
    request = PlanningRequest(
        request_id="test-transitions",
        student_id="SV001",
        target_term_id="next-term",
        goal="on_time",
        target_credits=15,
    )

    result = pipeline.run_planning_flow(request)

    assert result["success"] is True
    trace = result["trace"]
    assert len(trace) >= 5

    for event in trace:
        assert event["action"]
        assert event["call_id"]
        assert event["iteration"] >= 0
        assert event["attempt"] >= 1
        assert event["outcome"] in {"ok", "error"}
        assert event["input_hash"]

    # A valid pool is assessed, ranked and explained before awaiting feedback,
    # or replanning / no_plan_found when all candidates fail validation.
    assert result["status"] in {"awaiting_feedback", "replanning", "no_plan_found"}


def test_sv001_replans_then_confirms_after_advisor_replacement(pipeline):
    """SV001 replaces INT6209 with SOT366; each new plan is validated and explained."""
    initial = pipeline.run_planning_flow(PlanningRequest(
        request_id="test-feedback-sv001", student_id="SV001", target_term_id="next-term",
        goal="on_time", target_credits=15,
    ))
    assert initial["status"] == "awaiting_feedback"
    selected = initial["ranking"]["recommended_plan_id"]
    feedback = FeedbackRequest(
        feedback_id="fb-sv001-replace", run_id=initial["run_id"],
        displayed_result_hash=ranking_hash(RankingResult.model_validate(initial["ranking"])),
        actor_pseudonym="advisor-001", actor_role="advisor", action="modify",
        selected_plan_id=selected,
        operations=(FeedbackOperation(kind="replace", course_code="INT6209", replacement_course_code="SOT366"),),
        reason="Thay học phần tự chọn theo ý kiến cố vấn.",
        created_at=datetime.now(timezone.utc),
    )
    replanned = pipeline.replan_from_feedback(initial, feedback)

    assert replanned["status"] == "awaiting_feedback"
    assert replanned["iteration"] == initial["iteration"] + 1
    assert replanned["parent_run_id"] == initial["run_id"]
    assert replanned["feedback_normalization"]["adjustment"]["must_include"] == ["SOT366"]
    assert replanned["feedback_normalization"]["adjustment"]["must_exclude"] == ["INT6209"]
    assert all(item["status"] == "valid" for item in replanned["validations"])
    assert replanned["explanations"]["explanations"]
    for candidate in replanned["candidates"]:
        course_codes = {course["course_code"] for course in candidate["courses"]}
        assert "SOT366" in course_codes
        assert "INT6209" not in course_codes

    actions = [event["action"] for event in replanned["trace"]]
    feedback_index = actions.index("normalize_feedback")
    assert {"generate_candidates", "validate_candidates", "assess_plan_risk", "rank_valid_plans", "explain_plans"}.issubset(actions[feedback_index + 1:])

    confirm_feedback = FeedbackRequest(
        feedback_id="fb-sv001-confirm", run_id=replanned["run_id"],
        displayed_result_hash=ranking_hash(RankingResult.model_validate(replanned["ranking"])),
        actor_pseudonym="advisor-001", actor_role="advisor", action="confirm",
        selected_plan_id=replanned["ranking"]["recommended_plan_id"],
        created_at=datetime.now(timezone.utc),
    )
    confirmed = pipeline.confirm_from_feedback(replanned, confirm_feedback)
    assert confirmed["status"] == "confirmed"
    assert confirmed["confirmation"]["validation"]["status"] == "valid"
    assert confirmed["state"]["final_validation_hash"]
    assert confirmed["trace"][-1]["action"] == "confirm"


def test_modify_goal_and_target_credits_start_a_new_versioned_planning_round(pipeline):
    """Non-course feedback is converted to an adjustment, never patched into a displayed plan."""
    initial = pipeline.run_planning_flow(PlanningRequest(
        request_id="test-feedback-goal-credits", student_id="SV001", target_term_id="next-term",
        goal="on_time", target_credits=15,
    ))
    feedback = FeedbackRequest(
        feedback_id="fb-sv001-goal-credits", run_id=initial["run_id"],
        displayed_result_hash=ranking_hash(RankingResult.model_validate(initial["ranking"])),
        actor_pseudonym="advisor-001", actor_role="advisor", action="modify",
        selected_plan_id=initial["ranking"]["recommended_plan_id"],
        operations=(
            FeedbackOperation(kind="change_target_credits", target_credits=18),
            FeedbackOperation(kind="change_goal", goal="accelerated"),
        ),
        reason="Tăng tải để hỗ trợ mục tiêu học vượt.", created_at=datetime.now(timezone.utc),
    )
    replanned = pipeline.replan_from_feedback(initial, feedback)

    assert replanned["status"] == "awaiting_feedback"
    assert replanned["request"]["target_credits"] == 18
    assert replanned["request"]["goal"] == "accelerated"
    adjustment = replanned["feedback_normalization"]["adjustment"]
    assert adjustment["new_target_credits"] == 18
    assert adjustment["new_goal"] == "accelerated"
    assert all(item["status"] == "valid" for item in replanned["validations"])


def test_add_and_remove_feedback_normalize_to_hard_adjustment_without_mutating_plan(pipeline):
    """Add/remove are represented as a request for the next round, not a plan edit."""
    initial = pipeline.run_planning_flow(PlanningRequest(
        request_id="test-feedback-add-remove", student_id="SV001", target_term_id="next-term",
        goal="on_time", target_credits=15,
    ))
    feedback = FeedbackRequest(
        feedback_id="fb-sv001-add-remove", run_id=initial["run_id"],
        displayed_result_hash=ranking_hash(RankingResult.model_validate(initial["ranking"])),
        actor_pseudonym="advisor-001", actor_role="advisor", action="modify",
        selected_plan_id=initial["ranking"]["recommended_plan_id"],
        operations=(
            FeedbackOperation(kind="add", course_code="SOT366"),
            FeedbackOperation(kind="remove", course_code="INT6209"),
        ),
        reason="Điều chỉnh theo mục tiêu cố vấn.", created_at=datetime.now(timezone.utc),
    )

    candidates_before = deepcopy(initial["candidates"])
    normalized = normalize_feedback(feedback, RankingResult.model_validate(initial["ranking"]))
    assert normalized.adjustment.must_include == {"SOT366"}
    assert normalized.adjustment.must_exclude == {"INT6209"}
    assert initial["candidates"] == candidates_before  # Normalization is pure; it cannot patch candidates.


def test_unsatisfied_adjustment_returns_structured_diagnostic(pipeline, monkeypatch):
    """An adjustment that yields no candidate is surfaced, rather than silently ignored."""
    initial = pipeline.run_planning_flow(PlanningRequest(
        request_id="test-feedback-unsatisfied", student_id="SV001", target_term_id="next-term",
        goal="on_time", target_credits=15,
    ))
    original_generate = pipeline_module.generate_candidates

    def reject_adjusted_generation(*args, **kwargs):
        result = original_generate(*args, **kwargs)
        if kwargs.get("adjustment") is None:
            return result
        output = result.output.model_copy(update={"candidates": ()})
        return result.model_copy(update={"output": output})

    monkeypatch.setattr(pipeline_module, "generate_candidates", reject_adjusted_generation)
    feedback = FeedbackRequest(
        feedback_id="fb-sv001-unsatisfied", run_id=initial["run_id"],
        displayed_result_hash=ranking_hash(RankingResult.model_validate(initial["ranking"])),
        actor_pseudonym="advisor-001", actor_role="advisor", action="modify",
        selected_plan_id=initial["ranking"]["recommended_plan_id"],
        operations=(FeedbackOperation(kind="add", course_code="SOT366"),),
        reason="Yêu cầu thêm học phần.", created_at=datetime.now(timezone.utc),
    )
    result = pipeline.replan_from_feedback(initial, feedback)

    assert result["success"] is False
    assert result["error"]["code"] == "ADJUSTMENT_UNSATISFIED"
    assert result["adjustment"]["must_include"] == ["SOT366"]
    assert result["generation"]["candidates"] == []


def test_confirm_refreshes_changed_sources_and_requires_new_selection(pipeline, monkeypatch):
    """A changed current student source invalidates the displayed selection before confirm."""
    initial = pipeline.run_planning_flow(PlanningRequest(
        request_id="test-confirm-refresh", student_id="SV001", target_term_id="next-term",
        goal="on_time", target_credits=15,
    ))
    feedback = FeedbackRequest(
        feedback_id="fb-confirm-refresh", run_id=initial["run_id"],
        displayed_result_hash=ranking_hash(RankingResult.model_validate(initial["ranking"])),
        actor_pseudonym="advisor-001", actor_role="advisor", action="confirm",
        selected_plan_id=initial["ranking"]["recommended_plan_id"],
        created_at=datetime.now(timezone.utc),
    )
    original_load_student = pipeline_module.load_student_context

    def changed_only_when_refresh(context, *args, **kwargs):
        result = original_load_student(context, *args, **kwargs)
        if context.call_id.startswith("CALL_REFRESH_STUDENT_"):
            snapshot = result.output.student_snapshot.model_copy(update={"student_version": "sha256:changed-source"})
            return result.model_copy(update={"output": result.output.model_copy(update={"student_snapshot": snapshot})})
        return result

    monkeypatch.setattr(pipeline_module, "load_student_context", changed_only_when_refresh)
    refreshed = pipeline.confirm_from_feedback(initial, feedback)
    assert refreshed["confirmation_refresh_required"] is True
    assert refreshed["status"] == "awaiting_feedback"
    assert refreshed["parent_run_id"] == initial["run_id"]
    assert refreshed["source_versions_before"]["student_version"] != refreshed["source_versions_after"]["student_version"]
    assert refreshed["state"]["selected_plan_id"] is None


def test_confirm_rechecks_sources_after_final_validation(pipeline, monkeypatch):
    """A source change during Final Validation must not be committed as confirmed."""
    initial = pipeline.run_planning_flow(PlanningRequest(
        request_id="test-confirm-post-validation-refresh", student_id="SV001", target_term_id="next-term",
        goal="on_time", target_credits=15,
    ))
    feedback = FeedbackRequest(
        feedback_id="fb-confirm-post-validation-refresh", run_id=initial["run_id"],
        displayed_result_hash=ranking_hash(RankingResult.model_validate(initial["ranking"])),
        actor_pseudonym="advisor-001", actor_role="advisor", action="confirm",
        selected_plan_id=initial["ranking"]["recommended_plan_id"],
        created_at=datetime.now(timezone.utc),
    )
    original_load_student = pipeline_module.load_student_context
    refresh_count = 0

    def change_on_second_refresh(context, *args, **kwargs):
        nonlocal refresh_count
        result = original_load_student(context, *args, **kwargs)
        if context.call_id.startswith("CALL_REFRESH_STUDENT_"):
            refresh_count += 1
            if refresh_count == 2:
                snapshot = result.output.student_snapshot.model_copy(
                    update={"student_version": "sha256:changed-during-final-validation"})
                return result.model_copy(update={
                    "output": result.output.model_copy(update={"student_snapshot": snapshot})
                })
        return result

    monkeypatch.setattr(pipeline_module, "load_student_context", change_on_second_refresh)
    refreshed = pipeline.confirm_from_feedback(initial, feedback)

    assert refresh_count == 2
    assert refreshed["confirmation_refresh_required"] is True
    assert refreshed["status"] == "awaiting_feedback"
    assert refreshed["state"]["selected_plan_id"] is None


def test_confirm_rejects_plan_that_fails_final_validation(pipeline):
    """A valid displayed result cannot bypass the deterministic final validator."""
    initial = pipeline.run_planning_flow(PlanningRequest(
        request_id="test-confirm-invalid", student_id="SV001", target_term_id="next-term",
        goal="on_time", target_credits=15,
    ))
    tampered = deepcopy(initial)
    selected = tampered["ranking"]["recommended_plan_id"]
    candidate = next(item for item in tampered["candidates"] if item["plan_id"] == selected)
    candidate["courses"][0]["credits"] = 99
    feedback = FeedbackRequest(
        feedback_id="fb-confirm-invalid", run_id=tampered["run_id"],
        displayed_result_hash=ranking_hash(RankingResult.model_validate(tampered["ranking"])),
        actor_pseudonym="advisor-001", actor_role="advisor", action="confirm",
        selected_plan_id=selected, created_at=datetime.now(timezone.utc),
    )
    with pytest.raises(ValueError, match="no longer valid"):
        pipeline.confirm_from_feedback(tampered, feedback)
