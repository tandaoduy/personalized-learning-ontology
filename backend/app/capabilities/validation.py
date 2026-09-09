"""Validation adapter backed by the deterministic StandardValidator."""
from hashlib import sha256

from backend.app.schemas import CandidatePlan, KnowledgeSnapshot, StudentSnapshot, ValidatedPlan, ValidationResult, ToolCallContext, ToolError, ToolResult
from backend.app.services.ontology_evidence_service import OntologyEvidenceService
from backend.app.validation.validator import StandardValidator
from ._envelope import fail, now, ok


def validate_candidate(context: ToolCallContext, candidate: CandidatePlan, student_snapshot: StudentSnapshot,
                       knowledge_snapshot: KnowledgeSnapshot, evidence: OntologyEvidenceService,
                       *, min_credits: float, max_credits: float) -> ToolResult[ValidatedPlan | ValidationResult]:
    """Validate one candidate; invalid is a normal validation output, not an LLM judgment."""
    started = now()
    try:
        validation = StandardValidator(evidence, min_credits=min_credits, max_credits=max_credits).validate(
            candidate, student_snapshot, knowledge_snapshot)
        if validation.status != "valid":
            return ok(context, "validate_candidates", validation, started_at=started,
                knowledge_versions=knowledge_snapshot.versions, source_refs=(knowledge_snapshot.ontology_ref,))
        candidate_hash = "sha256:" + sha256(candidate.model_dump_json().encode()).hexdigest()
        validation_hash = "sha256:" + sha256(validation.model_dump_json().encode()).hexdigest()
        return ok(context, "validate_candidates", ValidatedPlan(candidate=candidate, candidate_hash=candidate_hash,
            validation=validation, validation_hash=validation_hash), started_at=started,
            knowledge_versions=knowledge_snapshot.versions, source_refs=(knowledge_snapshot.ontology_ref,))
    except Exception as exc:
        return fail(context, "validate_candidates", ToolError(code="VALIDATOR_ERROR", message=str(exc)), started_at=started)
