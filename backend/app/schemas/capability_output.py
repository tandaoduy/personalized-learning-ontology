"""Output schemas for capability adapters following MVP contract specification."""
from typing import Literal
from pydantic import AwareDatetime, Field, model_validator
from .common import CourseCode, Identifier, KnowledgeVersion, NonNegative, SchemaModel
from .snapshot import StudentSnapshot, KnowledgeSnapshot
from .planning import CandidatePlan
from .validation import ValidationResult


class StudentContextOutput(SchemaModel):
    """Output from load_student_context capability."""
    student_snapshot: StudentSnapshot
    source_manifest_ref: Identifier
    target_term_id: Identifier
    history_cutoff: Identifier
    normalization_rule_version: Identifier


class PolicyManifest(SchemaModel):
    """Policy source manifest with completeness flags."""
    manifest_id: Identifier
    version: Identifier
    content_hash: Identifier
    curriculum_id: Identifier
    target_term_id: Identifier
    has_catalog: bool = False
    has_prerequisite: bool = False
    has_corequisite: bool = False
    has_prior_study: bool = False
    has_category: bool = False
    has_offering: bool = False
    has_recommended_semester: bool = False
    credit_min: NonNegative
    credit_max: NonNegative
    credit_rule_id: Identifier
    credit_rule_version: Identifier


class CourseInfo(SchemaModel):
    """Course catalog entry."""
    course_code: CourseCode
    credits: NonNegative
    course_name: Identifier = ""


class KnowledgeContext(SchemaModel):
    """Output from load_knowledge_context capability."""
    knowledge_snapshot: KnowledgeSnapshot
    catalog: tuple[CourseInfo, ...] = ()
    policy_manifest: PolicyManifest
    ranking_metadata: dict[str, float] = {}

    @model_validator(mode="after")
    def unique_catalog_codes(self):
        codes = [item.course_code for item in self.catalog]
        if len(codes) != len(set(codes)):
            raise ValueError("Duplicate course codes in catalog")
        return self


class EligibilityDecision(SchemaModel):
    """Decision for a single course in CourseSpace."""
    course_code: CourseCode
    status: Literal["eligible", "conditional", "ineligible", "unknown"]
    reason_code: Identifier | None = None
    evidence_ids: tuple[Identifier, ...] = ()
    conditional_bundle: frozenset[CourseCode] = frozenset()


class CourseSpace(SchemaModel):
    """Output from build_course_space capability."""
    snapshot_id: Identifier
    decisions: tuple[EligibilityDecision, ...] = ()

    @model_validator(mode="after")
    def unique_course_codes(self):
        codes = [d.course_code for d in self.decisions]
        if len(codes) != len(set(codes)):
            raise ValueError("Duplicate course codes in decisions")
        if any(d.status == "conditional" and not d.conditional_bundle for d in self.decisions):
            raise ValueError("Conditional status requires conditional_bundle")
        return self

    @property
    def eligible_courses(self) -> frozenset[CourseCode]:
        return frozenset(d.course_code for d in self.decisions if d.status == "eligible")

    @property
    def conditional_courses(self) -> frozenset[CourseCode]:
        return frozenset(d.course_code for d in self.decisions if d.status == "conditional")

    @property
    def ineligible_courses(self) -> frozenset[CourseCode]:
        return frozenset(d.course_code for d in self.decisions if d.status == "ineligible")

    @property
    def unknown_courses(self) -> frozenset[CourseCode]:
        return frozenset(d.course_code for d in self.decisions if d.status == "unknown")


class GenerationAttemptRecord(SchemaModel):
    """Record of a single generation attempt."""
    attempt_id: Identifier
    candidate_hash: Identifier | None = None
    state_count: int = Field(ge=0, strict=True)
    reason: Identifier


class GenerationResult(SchemaModel):
    """Output from generate_candidates capability."""
    candidates: tuple[CandidatePlan, ...] = ()
    attempt_records: tuple[GenerationAttemptRecord, ...] = Field(min_length=1)
    seed: int = Field(strict=True)
    generator_config_hash: Identifier
    expanded_states: int = Field(ge=0, strict=True)
    generated_count: int = Field(ge=0, strict=True)
    duplicate_count: int = Field(ge=0, strict=True)
    stop_reason: Literal["budget_reached", "no_candidates", "target_met"]

    @model_validator(mode="after")
    def consistent_counts(self):
        if self.generated_count != len(self.candidates) + self.duplicate_count:
            raise ValueError("generated_count must equal len(candidates) + duplicate_count")
        return self


class ValidatedPlan(SchemaModel):
    """Validated plan with candidate and validation result bound together."""
    candidate: CandidatePlan
    candidate_hash: Identifier
    validation: ValidationResult
    validation_hash: Identifier

    @model_validator(mode="after")
    def matching_plan_and_validation(self):
        if self.candidate.plan_id != self.validation.plan_id:
            raise ValueError("Candidate and validation plan_id mismatch")
        if self.candidate.plan_version != self.validation.plan_version:
            raise ValueError("Candidate and validation plan_version mismatch")
        if self.candidate.knowledge_versions != self.validation.knowledge_versions:
            raise ValueError("Candidate and validation knowledge_versions mismatch")
        if self.validation.status != "valid":
            raise ValueError("ValidatedPlan requires validation status='valid'")
        return self
