from datetime import datetime, timezone
import pytest
from rdflib import Graph, URIRef, Literal
from backend.app.services.ontology_evidence_service import OntologyEvidenceService, EvidenceSourceError, BASE, CODE, PREREQ
from backend.app.validation.prerequisite_rule import evaluate_prerequisites, RULE_VERSION
from backend.app.schemas import StudentSnapshot, KnowledgeVersion

@pytest.fixture
def service(tmp_path):
    graph = Graph()
    for code in ["A", "B", "C"]:
        graph.add((URIRef(BASE + code), CODE, Literal(code)))
        graph.add((URIRef(BASE + code), URIRef(BASE + "hasCredit"), Literal(3)))
    graph.add((URIRef(BASE + "B"), PREREQ, URIRef(BASE + "A")))
    graph.add((URIRef(BASE + "C"), URIRef(BASE + "corequisiteWith"), URIRef(BASE + "A")))
    graph.add((URIRef(BASE + "A"), URIRef(BASE + "openSemesterType"), Literal(1)))
    graph.add((URIRef(BASE + "B"), URIRef(BASE + "openSemesterType"), Literal(2)))
    graph.add((URIRef(BASE + "C"), URIRef(BASE + "openSemesterType"), Literal(3)))
    path = tmp_path / "ontology.rdf"
    graph.serialize(path, format="xml")
    return OntologyEvidenceService(path)

def test_facts_keep_query_triples_and_content_version(service):
    fact = service.get_prerequisite_evidence("b", service.ontology_version)
    assert fact.prerequisite_codes == ("A",)
    assert fact.triples[0].predicate == str(PREREQ)
    assert fact.query_id == "Q_PREREQ_01"
    assert fact.query_version.startswith("sha256:")
    assert fact.evidence_id == service.get_prerequisite_evidence("B", service.ontology_version).evidence_id
    assert not hasattr(fact, "result")

def test_corequisite_evidence(service):
    fact = service.get_corequisite_evidence("C", service.ontology_version)
    assert fact.corequisite_codes == ("A",)
    assert fact.query_id == "Q_COREQ_01"
    assert fact.triples

def test_semester_offering_evidence(service):
    fact_a = service.get_semester_offering_evidence("A", service.ontology_version)
    assert fact_a.open_semester_type == 1
    assert fact_a.query_id == "Q_SEMESTER_01"

    fact_c = service.get_semester_offering_evidence("C", service.ontology_version)
    assert fact_c.open_semester_type == 3

def test_unknown_course_and_version_mismatch_are_errors(service):
    with pytest.raises(EvidenceSourceError): service.get_prerequisite_evidence("UNKNOWN", service.ontology_version)
    with pytest.raises(EvidenceSourceError): service.get_prerequisite_evidence("B", "wrong")
    assert service.get_prerequisite_evidence("C", service.ontology_version).prerequisite_codes == ()

@pytest.mark.parametrize("completed,expected", [((), "fail"), (("A",), "pass")])
def test_rule_conclusion_links_to_fact(service, completed, expected):
    fact = service.get_prerequisite_evidence("B", service.ontology_version)
    student = StudentSnapshot(student_id="s1", student_version="s1", captured_at=datetime.now(timezone.utc),
        curriculum_id="c1", major_id="m1", current_semester=2, completed_courses=completed)
    versions = KnowledgeVersion(student_version="s1", curriculum_version="c1", ontology_version=service.ontology_version,
        rule_version=RULE_VERSION, offering_version="o1")
    result = evaluate_prerequisites(fact, student, versions)
    assert result.result == expected
    assert result.supporting_evidence_ids == (fact.evidence_id,)
    assert result.query_id and result.rule_id and result.triples
    assert result.knowledge_versions == versions
    with pytest.raises(ValueError): evaluate_prerequisites(fact, student, versions.model_copy(update={"student_version":"s2"}))
