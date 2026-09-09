"""Integration tests for adapters backed by the project's actual data sources."""
from datetime import datetime, timedelta, timezone

import pytest

from backend.app.capabilities import build_course_space, generate_candidates, load_knowledge_context, load_student_context, validate_candidate
from backend.app.config import Config
from backend.app.schemas import PlanningRequest, ToolCallContext
from backend.app.services.ontology_evidence_service import OntologyEvidenceService
from backend.app.services.recommendation_engine import RecommendationEngine
from backend.app.services.student_data_service import StudentDataService


@pytest.fixture(scope="module")
def sources():
    engine = RecommendationEngine(Config.ONTOLOGY_PATH, beam_width=Config.BEAM_WIDTH,
        min_credits=Config.REGISTER_MIN_CREDITS, max_credits=Config.REGISTER_MAX_CREDITS,
        elective_quotas=Config.ELECTIVE_QUOTAS)
    return (StudentDataService(Config.STUDENT_DATA_JSON, Config.STUDENT_DATA_CSV), engine,
            OntologyEvidenceService(Config.ONTOLOGY_PATH))


@pytest.fixture
def planning_request():
    return PlanningRequest(request_id="capability-integration", student_id="SV001",
        target_term_id="next-term", goal="on_time", target_credits=15)


def context(action: str) -> ToolCallContext:
    return ToolCallContext(run_id="RUN_CAPABILITY", call_id="CALL_" + action, iteration=0,
        contract_version="agent-orchestrator-v1", deadline_at=datetime.now(timezone.utc) + timedelta(seconds=120),
        attempt=1, input_hash="sha256:" + action)


def test_adapters_read_project_sources_and_validate_generated_candidates(sources, planning_request):
    students, engine, evidence = sources
    student_result = load_student_context(context("load_student_context"), planning_request, students)
    assert student_result.status == "ok"
    student = student_result.output.student_snapshot
    assert student.student_id
    assert student_result.provenance.source_refs

    knowledge_result = load_knowledge_context(context("load_knowledge_context"), planning_request, student, engine, evidence)
    assert knowledge_result.status == "ok"
    knowledge = knowledge_result.output.knowledge_snapshot
    assert knowledge.versions.ontology_version == evidence.ontology_version
    assert knowledge_result.output.catalog

    profile = students.get_student(planning_request.student_id)
    eligibility = build_course_space(context("build_course_space"), student, knowledge, profile, engine)
    assert eligibility.status == "ok"
    assert eligibility.output.decisions

    generation = generate_candidates(context("generate_candidates"), planning_request, student, knowledge, profile, engine)
    assert generation.status == "ok"
    assert generation.output.attempt_records
    for candidate in generation.output.candidates:
        validation = validate_candidate(context("validate_candidates"), candidate, student, knowledge, evidence,
            min_credits=engine.min_credits, max_credits=engine.max_credits)
        assert validation.provenance.knowledge_versions == knowledge.versions
        assert validation.status in {"ok", "error"}
