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
        major_id="http://www.semanticweb.org/henrydao/ontologies/2025/7/TrainingProgramOntology#m1", current_semester=current_sem, completed_courses=completed)
    knowledge = KnowledgeSnapshot(snapshot_id="k1", versions=versions, captured_at=now, curriculum_id="c1",
        target_term_id="t1", target_semester_type=1 if (current_sem + 1) % 2 else 2,
        curriculum_courses=frozenset({"A", "B", "C"}),
        prior_study_requirements=[{"course_code": c, "required_courses": []} for c in sorted(set(x.strip().upper() for x in codes))],
        ontology_ref=service.source_ref, rules_ref="prerequisite-v1", offerings_ref="o1")
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
    result = StandardValidator(svc).validate(*inputs(svc,codes=("A",), current_sem=2))
    assert "catalog_credit_match" in result.checked_rules
    assert not any(v.constraint_id == "catalog_credit_match" for v in result.violations)
    assert result.status == "error"  # Missing offering/category must not certify a plan.


def changed_catalog(service, tmp_path, edits):
    from pathlib import Path
    from urllib.parse import urlparse
    from rdflib import Graph, URIRef, Literal
    from backend.app.services.ontology_evidence_service import OntologyEvidenceService, BASE
    from urllib.request import url2pathname
    path = Path(url2pathname(urlparse(service.source_ref).path))
    graph = Graph().parse(path, format="xml")
    for code, predicate, values in edits:
        subject, prop = URIRef(BASE + code), URIRef(BASE + predicate)
        graph.remove((subject, prop, None))
        for value in values:
            graph.add((subject, prop, URIRef(BASE + value) if isinstance(value, str) and value.startswith(("m", "spec")) else Literal(value)))
    target = tmp_path / "changed.rdf"
    graph.serialize(target, format="xml")
    return OntologyEvidenceService(target)


def replace_knowledge(data, **updates):
    plan, student, knowledge = data
    # Validate nested policy objects as real schema instances.
    return plan, student, KnowledgeSnapshot.model_validate({**knowledge.model_dump(), **updates})


@pytest.mark.parametrize("history,expected", [("missing", "invalid"), ("failed", "valid"), ("in_progress", "invalid"), ("same_plan", "invalid")])
def test_prior_study_uses_finished_history(service, history, expected):
    from backend.app.schemas.snapshot import CourseAttemptSnapshot
    data = inputs(service, codes=("A", "C") if history == "same_plan" else ("A",))
    plan, student, knowledge = replace_knowledge(data, prior_study_requirements=[
        {"course_code": c.course_code, "required_courses": ["C"] if c.course_code == "A" else []} for c in data[0].courses])
    if history in {"failed", "in_progress"}:
        student = student.model_copy(update={"attempts": (CourseAttemptSnapshot(course_code="C", term_id="previous", outcome=history),)})
    result = StandardValidator(service).validate(plan, student, knowledge)
    assert result.status == expected
    assert any(v.constraint_id == "prior_study" for v in result.violations) == (expected == "invalid")


@pytest.mark.parametrize("field,value,rule", [
    ("prior_study_requirements", [], "prior_study"),
    ("curriculum_courses", None, "curriculum_membership"),
    ("target_semester_type", None, "semester_offering"),
])
def test_missing_policy_never_certifies_valid(service, field, value, rule):
    result = StandardValidator(service).validate(*replace_knowledge(inputs(service, codes=("A",)), **{field: value}))
    assert result.status == "error"
    assert rule in result.pending_rules
    assert any(c.rule_id == rule and c.status == "error" for c in result.rule_checks)


@pytest.mark.parametrize("major,specialization,curriculum,expected", [
    ("m1", "spec1", ["A"], "valid"),
    ("m2", "spec1", ["A"], "invalid"),
    ("m1", "spec2", ["A"], "invalid"),
    ("m1", None, ["A"], "invalid"),
    ("m1", "spec1", [], "invalid"),
])
def test_curriculum_matches_exact_iris_and_program(service, tmp_path, major, specialization, curriculum, expected):
    from backend.app.services.ontology_evidence_service import BASE
    svc = changed_catalog(service, tmp_path, [("A", "isRequiredForSpecialization", ["spec1"])])
    plan, student, knowledge = replace_knowledge(inputs(svc, codes=("A",)), curriculum_courses=curriculum)
    student = student.model_copy(update={"major_id": BASE + major, "specialization_id": BASE + specialization if specialization else None})
    result = StandardValidator(svc).validate(plan, student, knowledge)
    assert result.status == expected
    assert any(v.constraint_id == "curriculum_membership" for v in result.violations) == (expected == "invalid")


def test_offering_uses_target_term_not_current_semester(service):
    data = replace_knowledge(inputs(service, codes=("A",), current_sem=1), target_semester_type=1)
    assert StandardValidator(service).validate(*data).status == "valid"
    data = replace_knowledge(inputs(service, codes=("A",), current_sem=2), target_semester_type=2)
    result = StandardValidator(service).validate(*data)
    assert result.status == "invalid"
    assert any(v.constraint_id == "semester_offering" for v in result.violations)


@pytest.mark.parametrize("values", [[], [1, 2], ["bad"], [7]])
def test_missing_invalid_or_conflicting_offering_is_error(service, tmp_path, values):
    svc = changed_catalog(service, tmp_path, [("A", "openSemesterType", values)])
    result = StandardValidator(svc).validate(*inputs(svc, codes=("A",)))
    assert result.status == "error"
    assert "semester_offering" in result.pending_rules


@pytest.mark.parametrize("completed,limit,expected", [((), 1, "valid"), (("B",), 1, "invalid"), (("B",), 2, "valid"), ((), 0, "invalid")])
def test_quota_counts_completed_and_selected_courses(service, tmp_path, completed, limit, expected):
    edits = [(c, p, values) for c in ("A", "B") for p, values in
             [("isRequiredForMajor", []), ("isElectiveForMajor", ["m1"])]]
    svc = changed_catalog(service, tmp_path, edits)
    data = replace_knowledge(inputs(svc, codes=("A",), completed=completed), elective_quotas=[{"category": "general", "max_courses": limit}])
    result = StandardValidator(svc).validate(*data)
    assert result.status == expected
    item = next(e for e in result.evidence if e.rule_id == "elective_quota")
    import json
    values = {b.variable: json.loads(b.value) for b in item.rule_inputs if b.variable in {"remaining_quota", "completed_courses", "selected_courses"}}
    assert values["remaining_quota"] == max(0, limit - len(completed))
    assert values["selected_courses"] == ["A"]
    assert values["completed_courses"] == list(completed)
    assert any(f.course_code == "B" for f in result.ontology_evidence) == bool(completed)


def test_quota_counts_entire_candidate_and_requires_policy(service, tmp_path):
    edits = [(c, p, values) for c in ("A", "C") for p, values in
             [("isRequiredForMajor", []), ("isElectiveForMajor", ["m1"])]]
    svc = changed_catalog(service, tmp_path, edits)
    data = inputs(svc, codes=("A", "C"))
    missing = StandardValidator(svc).validate(*data)
    assert missing.status == "error" and "elective_quota" in missing.pending_rules
    result = StandardValidator(svc).validate(*replace_knowledge(data, elective_quotas=[{"category": "general", "max_courses": 1}]))
    assert result.status == "invalid"
    assert any(v.constraint_id == "elective_quota" for v in result.violations)


def test_quota_unknown_completed_category_does_not_pass(service, tmp_path):
    svc = changed_catalog(service, tmp_path, [("A", "isRequiredForMajor", []), ("A", "isElectiveForMajor", ["m1"])])
    data = replace_knowledge(inputs(svc, codes=("A",), completed=("UNKNOWN",)), elective_quotas=[{"category": "general", "max_courses": 1}])
    result = StandardValidator(svc).validate(*data)
    assert result.status == "error" and "elective_quota" in result.pending_rules


@pytest.mark.parametrize("edits", [
    [("A", "isRequiredForMajor", [])],
    [("A", "isRequiredForMajor", [17])],
    [("A", "isElectiveForMajor", ["m1"])],
])
def test_missing_malformed_or_ambiguous_category_is_error(service, tmp_path, edits):
    svc = changed_catalog(service, tmp_path, edits)
    result = StandardValidator(svc).validate(*inputs(svc, codes=("A",)))
    assert result.status == "error"
    assert {"curriculum_membership", "elective_quota"} <= set(result.pending_rules)


def test_error_preserves_other_academic_violations(service):
    data = replace_knowledge(inputs(service, codes=("B",)), prior_study_requirements=[])
    result = StandardValidator(service).validate(*data)
    assert result.status == "error"
    assert any(v.constraint_id == "prerequisite" for v in result.violations)
    assert "prior_study" in result.pending_rules


def test_duplicate_snapshot_policy_keys_are_rejected(service):
    data = inputs(service, codes=("A",))
    for updates in (
        {"prior_study_requirements": [{"course_code": "A"}, {"course_code": "a"}]},
        {"elective_quotas": [{"category": "general", "max_courses": 1}] * 2},
    ):
        with pytest.raises(ValidationError, match="Duplicate policy keys"):
            replace_knowledge(data, **updates)
