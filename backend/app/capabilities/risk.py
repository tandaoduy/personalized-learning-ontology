"""M4 risk capability over a batch of current, valid plans."""
from backend.app.schemas import RankingContext, RiskBatch, StudentSnapshot, ToolCallContext, ToolError, ToolResult, ValidatedPlan
from backend.app.services.plan_risk_service import assess_plan_risk
from ._envelope import fail, now, ok


def assess_plan_risks(context: ToolCallContext, plans: tuple[ValidatedPlan, ...],
                      student: StudentSnapshot, ranking_context: RankingContext) -> ToolResult[RiskBatch]:
    started = now()
    try:
        if not plans:
            raise ValueError("VALID_PLAN_POOL_EMPTY")
        if ranking_context.knowledge_versions != plans[0].candidate.knowledge_versions:
            raise ValueError("RANKING_CONTEXT_STALE")
        results = tuple(assess_plan_risk(
            plan, lower=ranking_context.credit_min, upper=ranking_context.credit_max,
            retake_codes=student.failed_courses,
            academic_status=ranking_context.academic_status,
            source_refs=ranking_context.source_refs,
            context_hash=ranking_context.content_hash,
        ) for plan in plans)
        output = RiskBatch(context_hash=ranking_context.content_hash, results=results)
        return ok(context, "assess_plan_risk", output, started_at=started,
            knowledge_versions=ranking_context.knowledge_versions,
            source_refs=ranking_context.source_refs)
    except Exception as exc:
        return fail(context, "assess_plan_risk", ToolError(code="RISK_ASSESSMENT_ERROR", message=str(exc)),
            started_at=started)
