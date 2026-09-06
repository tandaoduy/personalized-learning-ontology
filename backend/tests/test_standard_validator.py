from datetime import datetime, timezone
import pytest
from pydantic import ValidationError
from test_ontology_evidence import service
from backend.app.schemas import CandidatePlan, StudentSnapshot, KnowledgeSnapshot, KnowledgeVersion
from backend.app.schemas.validation import REQUIRED_RULES
from backend.app.validation.validator import StandardValidator
from backend.app.validation.prerequisite_rule import RULE_VERSION


def inputs(service, completed=(), codes=("B", "C"), current_sem=2):
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    versions = KnowledgeVersion(student_version="s1", curriculum_version="c1", ontology_version=service.ontology_version,
        rule_version=RULE_VERSION, offering_version="o1")
    student = StudentSnapshot(student_id="S", student_version="s1", captured_at=now, curriculum_id="c1",
        major_id="m1", current_semester=current_sem, completed_courses=completed)
    knowledge = KnowledgeSnapshot(snapshot_id="k1", versions=versions, captured_at=now, curriculum_id="c1",
        target_term_id="t1", ontology_ref=service.source_ref, rules_ref="prerequisite-v1", offerings_ref="o1")
    plan = CandidatePlan(plan_id="p1", plan_version="1", request_id="r1", student_id="S", target_term_id="t1",
        knowledge_versions=versions, plan_type="safe", courses=[dict(course_code=c, credits=3) for c in codes])
    return plan, student, knowledge


def semantic(value):
    if isinstance(value, dict): return {k: semantic(v) for k,v in value.items() if k not in {"captured_at", "validated_at"}}
    if isinstance(value, list): return [semantic(v) for v in value]
    return value


def test_audit_collects_pass_and_fail(service):
    result = StandardValidator(service).validate(*inputs(service))
    assert result.status == "invalid"
    assert {e.result for e in result.evidence} == {"pass", "fail"}
    assert len(result.ontology_evidence) >= 6
    assert set(result.checked_rules) == set(REQUIRED_RULES)
    assert not result.pending_rules
    assert any(v.constraint_id == "prerequisite" and v.course_codes == ("B",) for v in result.violations)


def test_pass_is_valid_and_repeatable(service):
    validator = StandardValidator(service)
    # student current_sem=1 -> next_sem=2 (even) -> B (open 2) and C (open 3) both valid in semester 2!
    data = inputs(service, completed=("A",), current_sem=1)
    a, b = validator.validate(*data), validator.validate(*data)
    assert a.status == "valid"
    assert not a.pending_rules
    assert not a.violations
    assert semantic(a.model_dump(mode="json")) == semantic(b.model_dump(mode="json"))


def test_same_plan_prerequisite_is_not_completed(service):
    result = StandardValidator(service).validate(*inputs(service, codes=("A", "B")))
    assert result.status == "invalid"


def test_mismatch_is_error_before_queries(service):
    plan, student, knowledge = inputs(service)
    result = StandardValidator(service).validate(plan.model_copy(update={"student_id":"other"}), student, knowledge)
    assert result.status == "error"
    assert not result.violations and not result.evidence
    assert result.errors[0].code == "SNAPSHOT_MISMATCH"


def test_unknown_course_is_invalid_with_dependent_skips(service):
    result = StandardValidator(service).validate(*inputs(service, codes=("B", "UNKNOWN")))
    assert result.status == "invalid"
    assert not result.errors
    assert any(v.message == "COURSE_NOT_FOUND" for v in result.violations)
    skipped = {c.rule_id for c in result.rule_checks if c.course_code == "UNKNOWN" and c.status == "skipped"}
    assert "prerequisite" in skipped
    assert "catalog_credit_match" in skipped
    assert "corequisite" in skipped
    assert "semester_offering" in skipped
    assert result.pending_rules


def test_normalized_duplicates_have_candidate_evidence(service):
    result = StandardValidator(service).validate(*inputs(service, codes=("A", "a")))
    assert result.status == "invalid"
    item = next(e for e in result.evidence if e.rule_id == "duplicate_course")
    assert not item.supporting_evidence_ids and not item.triples
    assert any(i.variable == "positions" and i.value == "[0, 1]" for i in item.rule_inputs)
    assert any(i.variable == "candidate_plan_hash" for i in item.rule_inputs)


def test_wrong_candidate_credit_is_invalid(service):
    from backend.app.schemas import CandidateCourse
    plan, student, knowledge = inputs(service, codes=("A",))
    plan = plan.model_copy(update={"courses":(CandidateCourse(course_code="A", credits=4),)})
    result = StandardValidator(service).validate(plan, student, knowledge)
    assert result.status == "invalid"
    assert any(v.message == "CATALOG_CREDIT_MISMATCH" for v in result.violations)


def test_corequisite_violation_is_invalid(service):
    # C requires A as corequisite; if A is not completed and not in plan -> invalid
    result = StandardValidator(service).validate(*inputs(service, completed=(), codes=("C",)))
    assert result.status == "invalid"
    assert any(v.constraint_id == "corequisite" for v in result.violations)


def test_corequisite_satisfied_in_same_plan(service):
    # C requires A as corequisite; if A is in same plan -> corequisite passes!
    # current_sem=2 -> next_sem=3 (odd) -> A (open 1) and C (open 3) both open in semester 3!
    result = StandardValidator(service).validate(*inputs(service, completed=(), codes=("A", "C"), current_sem=2))
    assert not any(v.constraint_id == "corequisite" for v in result.violations)


def test_semester_offering_violation_is_invalid(service):
    # A is openSemesterType=1 (odd); student at current_sem=1 -> next_sem=2 (even) -> A in semester 2 is mismatch!
    result = StandardValidator(service).validate(*inputs(service, codes=("A",), current_sem=1))
    assert result.status == "invalid"
    assert any(v.constraint_id == "semester_offering" for v in result.violations)


def test_completed_course_retake_is_invalid(service):
    # A is already in completed_courses -> candidate plan containing A is invalid
    result = StandardValidator(service).validate(*inputs(service, completed=("A",), codes=("A",)))
    assert result.status == "invalid"
    assert any(v.constraint_id == "completed_course_retake" for v in result.violations)


def test_credit_limit_exceeded_is_invalid(service):
    from backend.app.schemas import CandidateCourse
    # 10 courses of 3 credits each = 30 credits > 27 max
    courses = [CandidateCourse(course_code="A", credits=3) for _ in range(10)]
    plan, student, knowledge = inputs(service, codes=("A",))
    plan = plan.model_copy(update={"courses": tuple(courses)})
    result = StandardValidator(service).validate(plan, student, knowledge)
    assert result.status == "invalid"
    assert any(v.constraint_id == "credit_limit" for v in result.violations)


@pytest.mark.parametrize("values", [[], [3,4], ["bad"]])
def test_missing_or_conflicting_catalog_credit_is_error(tmp_path, values):
    from rdflib import Graph, URIRef, Literal
    from backend.app.services.ontology_evidence_service import OntologyEvidenceService, BASE, CODE
    g=Graph()
    g.add((URIRef(BASE+"A"), CODE, Literal("A")))
    for value in values: g.add((URIRef(BASE+"A"), URIRef(BASE+"hasCredit"), Literal(value)))
    path=tmp_path/"catalog.rdf"
    g.serialize(path,format="xml")
    svc=OntologyEvidenceService(path)
    result=StandardValidator(svc).validate(*inputs(svc,codes=("A",)))
    assert result.status == "error"
    assert result.errors[0].code == "CATALOG_CREDIT_AMBIGUOUS"
    assert "catalog_credit_match" in result.pending_rules
    assert "duplicate_course" in result.checked_rules


def test_numeric_equivalent_literals_are_not_conflicting(tmp_path):
    from rdflib import Graph, URIRef, Literal
    from backend.app.services.ontology_evidence_service import OntologyEvidenceService, BASE, CODE
    g=Graph(); course=URIRef(BASE+"A")
    g.add((course,CODE,Literal("A")))
    g.add((course,URIRef(BASE+"hasCredit"),Literal(3)))
    g.add((course,URIRef(BASE+"credit"),Literal("3.0")))
    path=tmp_path/"catalog.rdf"; g.serialize(path,format="xml")
    svc=OntologyEvidenceService(path)
    # student current_sem=2 -> next_sem=3 (odd), A openType default 3 (both) -> valid!
    assert StandardValidator(svc).validate(*inputs(svc,codes=("A",), current_sem=2)).status == "valid"
