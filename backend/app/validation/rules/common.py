from hashlib import sha256
import json
from datetime import datetime, timezone
from backend.app.schemas.evidence import EvidenceRecord, QueryBinding

def conclusion(plan, code, rule_id, passed, message, inputs, fact=None):
    payload = plan.model_dump_json()
    bindings = tuple(QueryBinding(variable=k, value=json.dumps(v, sort_keys=True)) for k,v in sorted(inputs.items()))
    bindings += (QueryBinding(variable="candidate_plan_id", value=plan.plan_id),
        QueryBinding(variable="candidate_plan_version", value=plan.plan_version),
        QueryBinding(variable="candidate_plan_hash", value=sha256(payload.encode()).hexdigest()))
    identity = sha256((payload + rule_id + code + repr(bindings)).encode()).hexdigest()
    return EvidenceRecord(evidence_id="RULE_"+identity, course_code=code, decision="constraint_check",
        result="pass" if passed else "fail", source_type="rule", source_ref="backend/app/validation/rules/"+rule_id+".py",
        knowledge_versions=plan.knowledge_versions, captured_at=datetime.now(timezone.utc), rule_id=rule_id,
        rule_inputs=bindings, rule_result=message,
        supporting_evidence_ids=(fact.evidence_id,) if fact else (),
        triples=fact.triples if fact else (), query_id=fact.query_id if fact else None,
        query_text=fact.query_text if fact else None, query_executed=fact is not None)
