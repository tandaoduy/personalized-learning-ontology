"""Revalidate a selected plan deterministically before confirmation."""
from hashlib import sha256

from backend.app.schemas import (
    CandidatePlan, ConfirmationResult, KnowledgeSnapshot, StudentSnapshot,
    ToolCallContext, ToolError, ToolResult,
)
from backend.app.services.ontology_evidence_service import OntologyEvidenceService
from backend.app.validation.validator import StandardValidator
from ._envelope import fail, now, ok


def confirm_plan(context: ToolCallContext, candidate: CandidatePlan,
                 student: StudentSnapshot, knowledge: KnowledgeSnapshot,
                 evidence: OntologyEvidenceService, *, min_credits: float,
                 max_credits: float) -> ToolResult[ConfirmationResult]:
    """Run StandardValidator again; no LLM or stale validation may confirm a plan."""
    started = now()
    try:
        validation = StandardValidator(evidence, min_credits=min_credits,
                                       max_credits=max_credits).validate(candidate, student, knowledge)
        if validation.status != "valid":
            return fail(context, "confirm", ToolError(
                code="FINAL_VALIDATION_FAILED",
                message="Selected plan is no longer valid during final validation",
            ), started_at=started)
        output = ConfirmationResult(
            selected_plan_id=candidate.plan_id,
            validation=validation,
            validation_hash="sha256:" + sha256(validation.model_dump_json().encode()).hexdigest(),
        )
        return ok(context, "confirm", output, started_at=started,
                  knowledge_versions=knowledge.versions,
                  source_refs=(knowledge.ontology_ref,),
                  evidence_ids=tuple(item.evidence_id for item in validation.evidence))
    except Exception as exc:
        return fail(context, "confirm", ToolError(code="FINAL_VALIDATION_ERROR", message=str(exc)), started_at=started)
