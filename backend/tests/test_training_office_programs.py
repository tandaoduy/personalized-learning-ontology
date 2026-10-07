from rdflib import Graph, Literal, Namespace, RDF
from backend.app.services.training_office_service import TrainingOfficeService

BASE = Namespace("http://www.semanticweb.org/henrydao/ontologies/2025/7/TrainingProgramOntology#")

def _service_with_program(tmp_path):
    ontology = tmp_path / "ontology.rdf"
    graph = Graph()
    
    # Program
    prog = BASE["IT_TrainingProgram"]
    graph.add((prog, RDF.type, BASE.TrainingProgram))
    graph.add((prog, BASE.programCode, Literal("IT_TrainingProgram")))
    graph.add((prog, BASE.programName, Literal("Chương trình đào tạo CNTT")))
    graph.add((prog, BASE.isArchived, Literal(False)))
    
    # Semesters & Courses
    sem1 = BASE["Semester1"]
    graph.add((sem1, RDF.type, BASE.Semester))
    
    c1 = BASE["INT101"]
    graph.add((c1, RDF.type, BASE.Course))
    graph.add((c1, RDF.type, BASE.CoreCourse))
    graph.add((c1, BASE.courseCode, Literal("INT101")))
    graph.add((c1, BASE.courseName, Literal("Lập trình cơ sở")))
    graph.add((c1, BASE.credit, Literal(3.0)))
    graph.add((c1, BASE.recommendedInSemester, sem1))
    
    # Enrolled class
    cls = BASE["Class_65_CNTT_1"]
    graph.add((cls, BASE.followsTrainingProgram, prog))

    graph.serialize(ontology, format="xml")
    return TrainingOfficeService(ontology, tmp_path / "data", tmp_path / "artifacts")

def test_list_and_detail_programs(tmp_path):
    srv = _service_with_program(tmp_path)
    progs = srv.list_programs()
    assert len(progs) == 1
    p = progs[0]
    assert p["program_id"] == "IT_TrainingProgram"
    assert p["classes_count"] == 1
    assert p["archived"] is False
    
    detail = srv.program_detail("IT_TrainingProgram")
    assert detail["program_id"] == "IT_TrainingProgram"
    assert detail["total_courses"] >= 1
    assert len(detail["semesters"]) == 8
    assert len(detail["classes"]) == 1

def test_program_archive_and_restore(tmp_path):
    srv = _service_with_program(tmp_path)
    # Archive
    srv.archive_program("test.admin", "IT_TrainingProgram")
    progs = srv.list_programs()
    assert progs[0]["archived"] is True
    
    # Restore
    srv.restore_program("test.admin", "IT_TrainingProgram")
    progs = srv.list_programs()
    assert progs[0]["archived"] is False

if __name__ == "__main__":
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as td:
        test_list_and_detail_programs(Path(td))
        test_program_archive_and_restore(Path(td))
    print("All program tests passed successfully!")
