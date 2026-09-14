"""Typed feedback and adjustment contracts; persistence is implemented separately."""
from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from .common import CourseCode, Identifier, SchemaModel
from .planning import PlanningGoal
from .validation import ValidationResult


FeedbackAction = Literal["select", "rank", "modify", "confirm"]
FeedbackOperationKind = Literal["add", "remove", "replace", "change_target_credits", "change_goal"]


class FeedbackOperation(SchemaModel):
    kind: FeedbackOperationKind
    course_code: CourseCode | None = None
    replacement_course_code: CourseCode | None = None
    target_credits: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    goal: PlanningGoal | None = None

    @model_validator(mode="after")
    def consistent_operation(self):
        if self.kind in {"add", "remove"} and self.course_code is None:
            raise ValueError("Add/remove requires course_code")
        if self.kind == "replace" and (self.course_code is None or self.replacement_course_code is None):
            raise ValueError("Replace requires source and replacement course codes")
        if self.kind == "replace" and self.course_code == self.replacement_course_code:
            raise ValueError("Replacement course must differ from source course")
        if self.kind == "change_target_credits" and self.target_credits is None:
            raise ValueError("Change target credits requires target_credits")
        if self.kind == "change_goal" and self.goal is None:
            raise ValueError("Change goal requires goal")
        course_operations = {"add", "remove", "replace"}
        if self.kind not in course_operations and (self.course_code is not None or self.replacement_course_code is not None):
            raise ValueError("Goal/credit operations cannot carry course codes")
        if self.kind != "replace" and self.replacement_course_code is not None:
            raise ValueError("Only replace may carry replacement_course_code")
        if self.kind != "change_target_credits" and self.target_credits is not None:
            raise ValueError("Only change_target_credits may carry target_credits")
        if self.kind != "change_goal" and self.goal is not None:
            raise ValueError("Only change_goal may carry goal")
        return self


class FeedbackRequest(SchemaModel):
    feedback_id: Identifier
    run_id: Identifier
    displayed_result_hash: Identifier
    actor_pseudonym: Identifier
    actor_role: Literal["student", "advisor"]
    action: FeedbackAction
    selected_plan_id: Identifier | None = None
    ordered_plan_ids: tuple[Identifier, ...] = ()
    operations: tuple[FeedbackOperation, ...] = ()
    reason: str | None = Field(default=None, max_length=2000)
    created_at: AwareDatetime

    @model_validator(mode="after")
    def consistent_action(self):
        if self.action in {"select", "confirm"} and self.selected_plan_id is None:
            raise ValueError("Select/confirm requires selected_plan_id")
        if self.action == "rank" and len(self.ordered_plan_ids) < 2:
            raise ValueError("Rank requires at least two plan IDs")
        if self.action == "modify" and not self.operations:
            raise ValueError("Modify requires at least one operation")
        if self.action == "modify" and self.selected_plan_id is None:
            raise ValueError("Modify requires selected_plan_id as the adjustment base")
        if self.action == "modify" and not (self.reason and self.reason.strip()):
            raise ValueError("Modify requires a non-empty reason")
        if self.action != "modify" and self.operations:
            raise ValueError("Only modify may carry operations")
        if self.action != "rank" and self.ordered_plan_ids:
            raise ValueError("Only rank may carry ordered_plan_ids")
        if len(self.ordered_plan_ids) != len(set(self.ordered_plan_ids)):
            raise ValueError("Ranked plan IDs must be unique")
        return self


class AdjustmentRequest(SchemaModel):
    adjustment_id: Identifier
    parent_result_hash: Identifier
    request_version: Identifier
    must_include: frozenset[CourseCode] = frozenset()
    must_exclude: frozenset[CourseCode] = frozenset()
    new_target_credits: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    new_goal: PlanningGoal | None = None
    source_feedback_id: Identifier

    @model_validator(mode="after")
    def consistent_adjustment(self):
        if self.must_include & self.must_exclude:
            raise ValueError("A course cannot be both required and excluded")
        return self


class FeedbackReceipt(SchemaModel):
    feedback_id: Identifier
    record_hash: Identifier
    stored_at: AwareDatetime
    duplicate: bool = False


class FeedbackNormalization(SchemaModel):
    """Deterministic interpretation of one feedback record for the Agent."""
    feedback_id: Identifier
    feedback_hash: Identifier
    parent_result_hash: Identifier
    action: FeedbackAction
    selected_plan_id: Identifier | None = None
    adjustment: AdjustmentRequest | None = None

    @model_validator(mode="after")
    def normalization_matches_action(self):
        if self.action == "modify" and self.adjustment is None:
            raise ValueError("Modify feedback requires an adjustment")
        if self.action != "modify" and self.adjustment is not None:
            raise ValueError("Only modify feedback may create an adjustment")
        return self


class ConfirmationResult(SchemaModel):
    """Result of deterministic final validation immediately before confirmation."""
    selected_plan_id: Identifier
    validation: ValidationResult
    validation_hash: Identifier

    @model_validator(mode="after")
    def final_validation_is_valid(self):
        if self.validation.plan_id != self.selected_plan_id:
            raise ValueError("Confirmation plan does not match validation")
        if self.validation.status != "valid":
            raise ValueError("Only a valid plan can be confirmed")
        return self
