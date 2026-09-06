"""Snapshots identify the exact student and domain facts used in a run."""
from typing import Literal
from pydantic import AwareDatetime, Field, model_validator
from .common import CourseCode, Identifier, KnowledgeVersion, NonNegative, PositiveInt, SchemaModel

class CourseAttemptSnapshot(SchemaModel):
    course_code: CourseCode
    term_id: Identifier
    outcome: Literal["passed", "failed", "exempt", "in_progress"]
    grade: NonNegative | None = None

class StudentSnapshot(SchemaModel):
    student_id: Identifier
    student_version: Identifier
    captured_at: AwareDatetime
    curriculum_id: Identifier
    major_id: Identifier
    specialization_id: Identifier | None = None
    current_semester: PositiveInt
    completed_courses: frozenset[CourseCode] = frozenset()
    failed_courses: frozenset[CourseCode] = frozenset()
    attempts: tuple[CourseAttemptSnapshot, ...] = ()
    earned_credits: NonNegative = 0
    gpa: NonNegative | None = None
    gpa_scale: float = Field(default=4, gt=0, allow_inf_nan=False)
    academic_warnings: tuple[Identifier, ...] = ()

    @model_validator(mode="after")
    def consistent_history(self):
        if self.completed_courses & self.failed_courses:
            raise ValueError("Current completed and failed course sets must be disjoint; use attempts for history")
        if self.gpa is not None and self.gpa > self.gpa_scale:
            raise ValueError("GPA exceeds its scale")
        return self

class KnowledgeSnapshot(SchemaModel):
    snapshot_id: Identifier
    versions: KnowledgeVersion
    captured_at: AwareDatetime
    curriculum_id: Identifier
    target_term_id: Identifier
    ontology_ref: Identifier
    rules_ref: Identifier
    offerings_ref: Identifier
    # References must resolve to immutable/versioned artifacts, not mutable live data.
