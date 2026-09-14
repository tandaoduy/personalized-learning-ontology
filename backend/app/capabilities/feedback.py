"""Normalize feedback without changing plans, ontology or snapshots."""
from backend.app.schemas import (
    FeedbackNormalization, FeedbackRequest, RankingResult, ToolCallContext,
    ToolError, ToolResult,
)
from backend.app.services.feedback_service import normalize_feedback as normalize
from ._envelope import fail, now, ok


def normalize_feedback(context: ToolCallContext, feedback: FeedbackRequest,
                       ranking: RankingResult, knowledge_versions) -> ToolResult[FeedbackNormalization]:
    started = now()
    try:
        output = normalize(feedback, ranking)
        return ok(context, "normalize_feedback", output, started_at=started,
            knowledge_versions=knowledge_versions,
            source_refs=("feedback:" + feedback.feedback_id,), evidence_ids=())
    except Exception as exc:
        return fail(context, "normalize_feedback", ToolError(code="FEEDBACK_NORMALIZATION_ERROR", message=str(exc)), started_at=started)
