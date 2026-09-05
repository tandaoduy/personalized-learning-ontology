import rdflib
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

g = rdflib.Graph()
ontology_path = Path(__file__).resolve().parents[1] / "knowledge" / "ontology" / "ontology_v23.rdf"
g.parse(str(ontology_path))

query = """
PREFIX tp: <http://www.semanticweb.org/henrydao/ontologies/2025/7/TrainingProgramOntology#>
SELECT DISTINCT ?code ?name WHERE {
    ?course a tp:Course .
    ?course tp:courseCode ?code .
    ?course tp:courseName ?name .
    {
        ?course tp:isRequiredForMajor tp:KHMT
    } UNION {
        ?course tp:isElectiveForMajor tp:KHMT
    } UNION {
        ?course tp:isRequiredForSpecialization ?spec .
        tp:KHMT tp:hasSpecialization ?spec
    } UNION {
        ?course tp:isElectiveForSpecialization ?spec .
        tp:KHMT tp:hasSpecialization ?spec
    }
} ORDER BY ?code
"""

res = g.query(query)
print("Các môn học thuộc ngành Khoa học máy tính:")
for row in res:
    print(f"- {row.code}: {row.name}")
