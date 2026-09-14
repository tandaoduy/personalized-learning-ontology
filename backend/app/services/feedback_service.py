"""Pure normalization of validated feedback into a re-planning adjustment."""
from hashlib import sha256
import json

from backend.app.schemas import FeedbackNormalization, FeedbackRequest, RankingResult
from backend.app.services.grounded_explanation_service import ranking_hash

NORMALIZATION_VERSION = "feedback-normalization-v1"


def normalize_feedback(feedback: FeedbackRequest, ranking: RankingResult) -> FeedbackNormalization:
    parent_hash = ranking_hash(ranking)
    if feedback.displayed_result_hash != parent_hash:
        raise ValueError("STALE_FEEDBACK")
    displayed = {item.plan_id for item in ranking.selected_plans}
    if feedback.selected_plan_id is not None and feedback.selected_plan_id not in displayed:
        raise ValueError("SELECTED_PLAN_NOT_DISPLAYED")
    if set(feedback.ordered_plan_ids) - displayed:
        raise ValueError("RANKED_PLAN_NOT_DISPLAYED")

    payload = feedback.model_dump(mode="json")
    feedback_hash = "sha256:" + sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    adjustment = None
    if feedback.action == "modify":
        include, exclude = set(), set()
        target_credits = goal = None
        for operation in feedback.operations:
            if operation.kind == "add":
                include.add(operation.course_code)
            elif operation.kind == "remove":
                exclude.add(operation.course_code)
            elif operation.kind == "replace":
                exclude.add(operation.course_code)
                include.add(operation.replacement_course_code)
            elif operation.kind == "change_target_credits":
                target_credits = operation.target_credits
            elif operation.kind == "change_goal":
                goal = operation.goal
        if include & exclude:
            raise ValueError("ADJUSTMENT_CONFLICT")
        adjustment = {
            "adjustment_id": "adjustment-" + feedback_hash.removeprefix("sha256:")[:16],
            "parent_result_hash": parent_hash,
            "request_version": NORMALIZATION_VERSION,
            "must_include": sorted(include), "must_exclude": sorted(exclude),
            "new_target_credits": target_credits, "new_goal": goal,
            "source_feedback_id": feedback.feedback_id,
        }
    return FeedbackNormalization(feedback_id=feedback.feedback_id, feedback_hash=feedback_hash,
        parent_result_hash=parent_hash, action=feedback.action,
        selected_plan_id=feedback.selected_plan_id, adjustment=adjustment)
