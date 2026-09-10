"""M4 ranking and diversity capability."""
from backend.app.models.student import StudentProfile
from backend.app.schemas import PlanningRequest, RankingContext, RankingResult, RiskBatch, ToolCallContext, ToolError, ToolResult, ValidatedPlan
from backend.app.services.plan_ranking_service import build_plan_features, rank_valid_plans
from ._envelope import fail, now, ok


def rank_plans(context: ToolCallContext, plans: tuple[ValidatedPlan, ...], risks: RiskBatch,
               ranking_context: RankingContext, request: PlanningRequest,
               profile: StudentProfile, engine) -> ToolResult[RankingResult]:
    started = now()
    try:
        if risks.context_hash != ranking_context.content_hash:
            raise ValueError("STALE_RISK_CONTEXT")
        by_hash = {item.plan_hash: item for item in risks.results}
        if set(by_hash) != {item.candidate_hash for item in plans}:
            raise ValueError("RISK_POOL_MISMATCH")
        rows = []
        for plan in plans:
            risk = by_hash[plan.candidate_hash]
            raw = build_plan_features(plan, risk, ranking_context, request,
                current_semester=profile.current_semester, completed_courses=profile.passed_courses,
                course_metadata=engine.course_data)
            rows.append((plan, raw, ranking_context.source_refs, risk))
        output = rank_valid_plans(rows, request_id=request.request_id,
            knowledge_versions=ranking_context.knowledge_versions,
            context_hash=ranking_context.content_hash)
        return ok(context, "rank_valid_plans", output, started_at=started,
            knowledge_versions=ranking_context.knowledge_versions,
            source_refs=ranking_context.source_refs)
    except Exception as exc:
        return fail(context, "rank_valid_plans", ToolError(code="RANKING_ERROR", message=str(exc)),
            started_at=started)
