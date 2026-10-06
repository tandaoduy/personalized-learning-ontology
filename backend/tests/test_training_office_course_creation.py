from rdflib import Graph, Literal, Namespace, RDF

from backend.app.services.training_office_service import TrainingOfficeService


BASE = Namespace("http://www.semanticweb.org/henrydao/ontologies/2025/7/TrainingProgramOntology#")


def _service(tmp_path):
    ontology = tmp_path / "ontology.rdf"
    graph = Graph()
    graph.add((BASE.EXIST101, RDF.type, BASE.Course))
    graph.add((BASE.EXIST101, BASE.courseCode, Literal("EXIST101")))
    graph.add((BASE.EXIST101, BASE.courseName, Literal("Existing course")))
    graph.add((BASE.EXIST101, BASE.credit, Literal(3)))
    graph.add((BASE.CNTT, RDF.type, BASE.Major))
    graph.add((BASE.Semester1, RDF.type, BASE.Semester))
    graph.add((BASE.Semester7, RDF.type, BASE.Semester))
    graph.serialize(ontology, format="xml")
    return TrainingOfficeService(ontology, tmp_path / "data", tmp_path / "artifacts")


def test_create_course_persists_an_independent_course_and_catalog_entry(tmp_path):
    service = _service(tmp_path)

    created = service.create_course("training.office", "int701", "Chuyên đề AI", 3)

    assert created["code"] == "INT701"
    assert created["credits"] == 3.0
    assert created["prerequisites"] == []
    assert any(row["code"] == "INT701" for row in service.list_courses())
    saved = Graph().parse(service.ontology_path, format="xml")
    assert (BASE.INT701, RDF.type, BASE.Course) in saved
    assert (BASE.INT701, BASE.courseCode, Literal("INT701")) in saved


def test_create_course_rejects_duplicate_and_invalid_code(tmp_path):
    service = _service(tmp_path)

    try:
        service.create_course("training.office", "EXIST101", "Duplicate", 3)
    except ValueError as exc:
        assert str(exc) == "COURSE_ALREADY_EXISTS"
    else:
        raise AssertionError("Duplicate course code must be rejected")

    try:
        service.create_course("training.office", "bad code", "Invalid", 3)
    except ValueError as exc:
        assert str(exc) == "INVALID_COURSE_CODE"
    else:
        raise AssertionError("Invalid course code must be rejected")
