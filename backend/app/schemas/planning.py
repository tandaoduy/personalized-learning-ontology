"""Planning input and unvalidated candidate output."""
from typing import Literal
from pydantic import Field, model_validator
from .common import CourseCode, Identifier, KnowledgeVersion, NonNegative, SchemaModel

PlanningGoal = Literal["on_time", "accelerated"]
PlanType = Literal["safe", "balanced", "accelerated"]

class PlanningRequest(SchemaModel):
    request_id: Identifier
    student_id: Identifier
    target_term_id: Identifier
    goal: PlanningGoal
    target_credits: float = Field(gt=0, allow_inf_nan=False)
    preferred_courses: frozenset[CourseCode] = frozenset()
    avoided_courses: frozenset[CourseCode] = frozenset()

    @model_validator(mode="after")
    def consistent_preferences(self):
        if self.preferred_courses & self.avoided_courses:
            raise ValueError("A course cannot be both preferred and avoided")
        return self

class CandidateCourse(SchemaModel):
    course_code: CourseCode
    credits: NonNegative

class CandidatePlan(SchemaModel):
    plan_id: Identifier
    plan_version: Identifier
    request_id: Identifier
    student_id: Identifier
    target_term_id: Identifier
    knowledge_versions: KnowledgeVersion
    plan_type: PlanType
    courses: tuple[CandidateCourse, ...] = Field(min_length=1)
    # Duplicates and incorrect catalog credits are intentionally left to Validator.
    # Parsing a candidate never certifies academic validity.
    @property
    def total_credits(self) -> float:
        return sum(course.credits for course in self.courses)
