"""End-to-end integration test for AgentPipeline through orchestrator."""
import pytest

pytestmark = pytest.mark.integration

from backend.app.agent import AgentOrchestrator
from backend.app.agent.pipeline import AgentPipeline
from backend.app.config import Config
from backend.app.schemas import PlanningRequest
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
