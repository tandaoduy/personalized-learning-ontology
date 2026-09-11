"""Capability adapter for deterministic, evidence-grounded explanations."""
from backend.app.schemas import (
    GroundedExplanationBatch, RankingResult, RiskBatch, ToolCallContext,
    ToolError, ToolResult, ValidatedPlan,
)
from backend.app.services.grounded_explanation_service import build_grounded_explanations
from ._envelope import fail, now, ok


def explain_plans(context: ToolCallContext, plans: tuple[ValidatedPlan, ...], risks: RiskBatch,
                  ranking: RankingResult) -> ToolResult[GroundedExplanationBatch]:
    started = now()
    try:
        output = build_grounded_explanations(plans, risks, ranking)
        evidence_ids = tuple(sorted({
            evidence_id for explanation in output.explanations for claim in explanation.claims
            for evidence_id in claim.evidence_ids
        }))
        source_refs = tuple(sorted({
            source_ref for explanation in output.explanations for claim in explanation.claims
            for source_ref in claim.source_refs
        }))
        return ok(context, "explain_plans", output, started_at=started,
            knowledge_versions=plans[0].candidate.knowledge_versions,
            source_refs=source_refs, evidence_ids=evidence_ids)
    except Exception as exc:
        return fail(context, "explain_plans", ToolError(code="EXPLANATION_ERROR", message=str(exc)), started_at=started)
