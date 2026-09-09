"""Create a knowledge snapshot from the loaded RDF and engine configuration."""
from hashlib import sha256
import json
from pathlib import Path

from backend.app.schemas import (CourseInfo, ElectiveQuota, KnowledgeContext, KnowledgeSnapshot,
    KnowledgeVersion, PlanningRequest, PolicyManifest, StudentSnapshot, ToolCallContext, ToolError, ToolResult)
from backend.app.services.ontology_evidence_service import OntologyEvidenceService
from backend.app.services.recommendation_engine import RecommendationEngine
from backend.app.validation.prerequisite_rule import RULE_VERSION
from ._envelope import fail, now, ok


def load_knowledge_context(context: ToolCallContext, request: PlanningRequest, student: StudentSnapshot,
                           engine: RecommendationEngine, evidence: OntologyEvidenceService) -> ToolResult[KnowledgeContext]:
    """Load catalog facts from the engine and bind them to the RDF content version."""
    started = now()
    try:
        if Path(engine.ontology_path).resolve().as_uri() != evidence.source_ref:
            raise ValueError("ONTOLOGY_SOURCE_MISMATCH")
        policy = {"min": engine.min_credits, "max": engine.max_credits, "quotas": engine.elective_quotas}
        policy_hash = "sha256:" + sha256(json.dumps(policy, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        versions = KnowledgeVersion(student_version=student.student_version,
            curriculum_version=student.curriculum_id, ontology_version=evidence.ontology_version,
            rule_version=RULE_VERSION, offering_version=policy_hash)
        codes = frozenset(engine.course_data)
        knowledge = KnowledgeSnapshot(snapshot_id="knowledge-" + policy_hash.removeprefix("sha256:")[:16],
            versions=versions, captured_at=started, curriculum_id=student.curriculum_id,
            target_term_id=request.target_term_id, ontology_ref=evidence.source_ref,
            rules_ref="standard-academic-v3", offerings_ref=policy_hash,
            target_semester_type=1 if (student.current_semester + 1) % 2 else 2,
            curriculum_courses=codes,
            # The legacy data has no separate prior-study policy. Empty requirements
            # are explicit for this baseline and are recorded in the manifest below.
            prior_study_requirements=tuple({"course_code": code, "required_courses": ()} for code in sorted(codes)),
            elective_quotas=tuple(ElectiveQuota(category=k, max_courses=v) for k, v in sorted(engine.elective_quotas.items())))
        catalog = tuple(CourseInfo(course_code=code, credits=float(info.get("credit", 0)),
                                   course_name=str(info.get("name") or code))
                        for code, info in sorted(engine.course_data.items()))
        manifest = PolicyManifest(manifest_id="policy-" + policy_hash.removeprefix("sha256:")[:16], version="engine-policy-v1",
            content_hash=policy_hash, curriculum_id=student.curriculum_id, target_term_id=request.target_term_id,
            has_catalog=True, has_prerequisite=True, has_corequisite=True, has_prior_study=False,
            has_category=True, has_offering=True, has_recommended_semester=True,
            credit_min=engine.min_credits, credit_max=engine.max_credits,
            credit_rule_id="recommendation-engine-credit-bounds", credit_rule_version="v1")
        return ok(context, "load_knowledge_context", KnowledgeContext(knowledge_snapshot=knowledge, catalog=catalog,
            policy_manifest=manifest), started_at=started, knowledge_versions=versions,
            source_refs=(evidence.source_ref, policy_hash))
    except Exception as exc:
        return fail(context, "load_knowledge_context", ToolError(code="KNOWLEDGE_CONTEXT_ERROR", message=str(exc)), started_at=started)
