from datetime import datetime, timezone
import pytest
from pydantic import ValidationError
from backend.app.schemas.validation import REQUIRED_RULES
from backend.app.schemas import (
    KnowledgeVersion, PlanningRequest, StudentSnapshot, CandidatePlan,
    EvidenceRecord, FeedbackOperation, FeedbackRequest, ValidationResult,
)

VERSIONS = dict(student_version="s1", curriculum_version="c1", ontology_version="o1", rule_version="r1", offering_version="f1")
NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)

def evidence(**changes):
    data = dict(evidence_id="e1", course_code="CS2", decision="constraint_check", result="fail",
        source_type="ontology", source_ref="ontology.rdf", knowledge_versions=VERSIONS, captured_at=NOW,
        triples=[dict(subject="urn:CS2", predicate="urn:prerequisite", object="urn:CS1")])
    return EvidenceRecord(**(data | changes))

def result(**changes):
    return ValidationResult(**(dict(plan_id="p1", plan_version="1", knowledge_versions=VERSIONS,
        validator_version="v1", validated_at=NOW, status="invalid", checked_rules=("prerequisite",),
        pending_rules=tuple(r for r in REQUIRED_RULES if r != "prerequisite"),
        violations=[dict(constraint_id="prerequisite", message="Missing prerequisite", evidence_ids=["e1"])],
        evidence=[evidence()]) | changes))

def test_request_normalizes_and_rejects_conflicting_preferences():
    data = dict(request_id="r1", student_id="s1", target_term_id="2026-1", goal="on_time", target_credits=15)
    request = PlanningRequest(**data, preferred_courses=[" cs1 "])
    assert request.preferred_courses == frozenset({"CS1"})
    with pytest.raises(ValidationError):
        PlanningRequest(**data, preferred_courses=["cs1"], avoided_courses=["CS1"])
    with pytest.raises(ValidationError):
        PlanningRequest(**(data | {"target_credits": float("nan")}))
    with pytest.raises(ValidationError):
        PlanningRequest(**data, invented_rule=True)

def test_snapshot_preserves_history_but_rejects_conflicting_current_state():
    data = dict(student_id="s1", student_version="1", captured_at=NOW, curriculum_id="c1", major_id="m1", current_semester=2)
    with pytest.raises(ValidationError):
        StudentSnapshot(**data, completed_courses=["CS1"], failed_courses=["cs1"])
    with pytest.raises(ValidationError):
        StudentSnapshot(**data, gpa=5, gpa_scale=4)
    with pytest.raises(ValidationError):
        StudentSnapshot(**(data | {"captured_at": datetime(2026, 1, 1)}))
    snapshot = StudentSnapshot(**data, completed_courses=["CS1"], attempts=[dict(course_code="CS1", term_id="old", outcome="failed")])
    with pytest.raises(ValidationError):
        snapshot.student_version = "2"
    assert isinstance(snapshot.attempts, tuple)

def test_candidate_is_not_a_validity_certificate():
    plan = CandidatePlan(plan_id="p1", plan_version="1", request_id="r1", student_id="s1", target_term_id="t1",
        knowledge_versions=VERSIONS, plan_type="safe", courses=[dict(course_code="CS1", credits=3)] * 2)
    assert plan.total_credits == 6
    assert CandidatePlan.model_validate_json(plan.model_dump_json()) == plan
    assert len(plan.courses) == 2  # Independent Validator must detect the duplicate.

@pytest.mark.parametrize("changes", [
    dict(triples=[]),
    dict(source_type="sparql", query_id="Q1"),
    dict(source_type="rule", rule_id="R1"),
])
def test_evidence_requires_actual_source_payload(changes):
    with pytest.raises(ValidationError): evidence(**changes)

def test_empty_sparql_result_is_explicit_evidence():
    item = evidence(source_type="sparql", triples=[], query_id="Q1", query_text="SELECT ?x WHERE { ?x ?p ?o }", query_executed=True)
    assert item.query_rows == ()

def test_validation_roundtrip_and_reference_integrity():
    valid = result()
    assert ValidationResult.model_validate_json(valid.model_dump_json()) == valid
    with pytest.raises(ValidationError): result(status="valid")
    with pytest.raises(ValidationError): result(violations=[])
    with pytest.raises(ValidationError): result(evidence=[evidence(evidence_id="other")])
    with pytest.raises(ValidationError): result(evidence=[evidence(), evidence()])
    with pytest.raises(ValidationError): result(evidence=[evidence(knowledge_versions=VERSIONS | {"ontology_version":"o2"})])

def test_contracts_export_json_schema():
    for schema in [KnowledgeVersion, PlanningRequest, StudentSnapshot, CandidatePlan, EvidenceRecord, FeedbackRequest, ValidationResult]:
        assert schema.model_json_schema()["type"] == "object"


def test_feedback_contract_covers_selection_and_explained_adjustments():
    select = FeedbackRequest(feedback_id="fb-select", run_id="run-1", displayed_result_hash="sha256:shown",
        actor_pseudonym="student-001", actor_role="student", action="select", selected_plan_id="plan-1", created_at=NOW)
    assert select.selected_plan_id == "plan-1"

    modify = FeedbackRequest(feedback_id="fb-modify", run_id="run-1", displayed_result_hash="sha256:shown",
        actor_pseudonym="advisor-001", actor_role="advisor", action="modify", selected_plan_id="plan-1",
        operations=[FeedbackOperation(kind="replace", course_code="INT6209", replacement_course_code="SOT366")],
        reason="Ưu tiên học phần tự chọn thay thế phù hợp với cố vấn.", created_at=NOW)
    assert modify.operations[0].course_code == "INT6209"
    assert modify.operations[0].replacement_course_code == "SOT366"

    common = dict(feedback_id="fb-invalid", run_id="run-1", displayed_result_hash="sha256:shown",
        actor_pseudonym="advisor-001", actor_role="advisor", action="modify",
        operations=[dict(kind="remove", course_code="INT6209")], created_at=NOW)
    with pytest.raises(ValidationError):
        FeedbackRequest(**common, selected_plan_id="plan-1")
    with pytest.raises(ValidationError):
        FeedbackRequest(**common, reason="Cần chỉnh sửa")
    with pytest.raises(ValidationError):
        FeedbackOperation(kind="add", course_code="SOT366", goal="on_time")
