"""Fast e2e contract test: real Agent pipeline over a tiny versioned RDF fixture."""
import json

from rdflib import Graph, Literal, URIRef

from backend.app.agent.pipeline import AgentPipeline
from backend.app.models.recommendation import RecommendedCourse
from backend.app.models.student import StudentProfile
from backend.app.schemas import PlanningRequest
from backend.app.schemas import StudentSnapshot, KnowledgeSnapshot
from backend.app.schemas.agent_state import AgentState
from backend.app.services.ontology_evidence_service import BASE, CODE, OntologyEvidenceService


class FixtureStudents:
    def __init__(self, path):
        self.json_path = str(path)
        self.profile = StudentProfile(student_id="SV001", name="Fixture Student", year_admitted=2024,
            major="Cong nghe thong tin", current_semester=2, academic_class="64.CNTT-1")

    def get_student(self, student_id):
        return self.profile if student_id == "SV001" else None


class FixtureEngine:
    min_credits = 0
    max_credits = 27
    beam_width = 1
    elective_quotas = {}
    course_data = {"A": {"credit": 3, "name": "Course A", "recommended_sem": 3,
        "is_required_major": True, "prerequisites": [], "corequisites": []}}

    def __init__(self, ontology_path):
        self.ontology_path = str(ontology_path)
        self.eligible = [RecommendedCourse(code="A", name="Course A", credits=3, total_priority_score=1)]

    def get_eligible_courses(self, _profile):
        return self.eligible, set(), {}, "on_time"

    def _random_select_electives(self, courses, *_args):
        # Mirror the legacy engine's in-place noise to catch input contamination.
        for course in courses:
            course.total_priority_score += 100
        return list(courses)

    def _beam_search_optimize(self, _profile, courses, *_args):
        return list(courses[:1]), []


def test_fast_agent_pipeline_e2e(tmp_path):
    source = tmp_path / "students.json"
    source.write_text(json.dumps([{"student_id": "SV001"}]), encoding="utf-8")
    ontology = tmp_path / "agent-e2e.rdf"
    graph = Graph()
    course = URIRef(BASE + "A")
    graph.add((course, CODE, Literal("A")))
    graph.add((course, URIRef(BASE + "hasCredit"), Literal(3)))
    graph.add((course, URIRef(BASE + "isRequiredForMajor"), URIRef(BASE + "CNTT")))
    graph.add((course, URIRef(BASE + "openSemesterType"), Literal(1)))
    graph.serialize(ontology, format="xml")

    pipeline = AgentPipeline(FixtureStudents(source), FixtureEngine(ontology), OntologyEvidenceService(ontology))
    result = pipeline.run_planning_flow(PlanningRequest(request_id="fast-e2e", student_id="SV001",
        target_term_id="next-term", goal="on_time", target_credits=3))

    assert result["success"] is True
    assert result["status"] == "awaiting_feedback"
    assert len(result["candidates"]) == 1
    assert len(result["validations"]) == 1
    assert pipeline.engine.eligible[0].total_priority_score == 1
    assert result["generation"]["seed"] == result["state"]["seed"] == 42
    # Exported artifacts must round-trip without repr(frozenset(...)).
    exported = json.loads(json.dumps(result))
    StudentSnapshot.model_validate(exported["student_snapshot"])
    KnowledgeSnapshot.model_validate(exported["knowledge_snapshot"])
    AgentState.model_validate(exported["state"])
    assert {event["action"] for event in result["trace"]} == {
        "load_student_context", "load_knowledge_context", "build_course_space",
        "generate_candidates", "validate_candidates", "assess_plan_risk", "rank_valid_plans", "explain_plans",
    }
    assert result["ranking"]["selected_plans"] == [{"plan_id": result["candidates"][0]["plan_id"], "strategy": "safe"}]
    assert result["ranking_context"]["academic_status_is_official"] is False
    explanation = result["explanations"]["explanations"][0]
    assert explanation["plan_id"] == result["candidates"][0]["plan_id"]
    assert all(claim["evidence_ids"] and claim["source_refs"] for claim in explanation["claims"])
    assert any(claim["kind"] == "course_classification" for claim in explanation["claims"])
