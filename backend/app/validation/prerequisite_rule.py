"""Prerequisite conclusion only, not full-plan validation."""
from hashlib import sha256
import json
from backend.app.schemas.common import KnowledgeVersion
from backend.app.schemas.snapshot import StudentSnapshot
from backend.app.schemas.evidence import EvidenceRecord, OntologyFactEvidence, QueryBinding

RULE_ID = "PREREQ_COMPLETED_01"
RULE_VERSION = "integrity-prerequisite-v2"

def evaluate_prerequisites(fact: OntologyFactEvidence, student: StudentSnapshot,
                           versions: KnowledgeVersion) -> EvidenceRecord:
    if fact.ontology_version != versions.ontology_version or student.student_version != versions.student_version:
        raise ValueError("Evidence/student snapshot version mismatch")
    if versions.rule_version != RULE_VERSION:
        raise ValueError("Unsupported prerequisite rule version")
    missing = sorted(set(fact.prerequisite_codes) - student.completed_courses)
    # Stable identity includes the actual input, not timestamps.
    inputs = (QueryBinding(variable="student_id", value=student.student_id),
              QueryBinding(variable="completed_courses", value=",".join(sorted(student.completed_courses))),
              QueryBinding(variable="prerequisites", value=",".join(sorted(fact.prerequisite_codes))))
    digest = sha256((fact.model_dump_json(exclude={"captured_at"}) + json.dumps({"student_id": student.student_id, "completed_courses": sorted(student.completed_courses)}, sort_keys=True) + versions.model_dump_json()).encode()).hexdigest()
    return EvidenceRecord(evidence_id="RULE_" + digest, course_code=fact.course_code,
        decision="constraint_check", result="fail" if missing else "pass", source_type="rule",
        source_ref="backend/app/validation/prerequisite_rule.py", knowledge_versions=versions,
        captured_at=fact.captured_at, triples=fact.triples, query_id=fact.query_id,
        query_text=fact.query_text, query_executed=True, rule_id=RULE_ID,
        supporting_evidence_ids=(fact.evidence_id,), rule_inputs=inputs,
        rule_result="Missing: " + ", ".join(missing) if missing else "All recorded prerequisites completed")
