"""Typed, immutable contracts for M4 risk, ranking and diversity."""
from typing import Literal

from pydantic import Field, model_validator

from .common import CourseCode, Identifier, KnowledgeVersion, NonNegative, SchemaModel


AcademicStatus = Literal["normal", "mild_warning", "academic_warning"]
Strategy = Literal["safe", "balanced", "accelerated"]


class RankingContext(SchemaModel):
    context_id: Identifier
    content_hash: Identifier
    context_version: Identifier
    knowledge_versions: KnowledgeVersion
    credit_min: NonNegative
    credit_max: NonNegative
    reference_credits: NonNegative
    reference_credits_source: Identifier
    academic_status: AcademicStatus
    academic_status_source: Identifier
    academic_status_is_official: bool
    progress_status: Identifier
    progress_risk_level: Identifier
    required_codes: frozenset[CourseCode]
    catalog_credits: dict[CourseCode, NonNegative]
    dependency_map: dict[CourseCode, tuple[CourseCode, ...]]
    source_refs: tuple[Identifier, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def policy_is_consistent(self):
        if self.credit_max < self.credit_min:
            raise ValueError("credit_max must be at least credit_min")
        if not self.credit_min <= self.reference_credits <= self.credit_max:
            raise ValueError("reference_credits must be inside credit policy")
        if not self.required_codes.issubset(self.catalog_credits):
            raise ValueError("required_codes must exist in catalog_credits")
        if not set(self.dependency_map).issubset(self.catalog_credits):
            raise ValueError("dependency_map courses must exist in catalog_credits")
        return self


class RiskComponents(SchemaModel):
    load: float = Field(ge=0, le=1, allow_inf_nan=False)
    retake: float = Field(ge=0, le=1, allow_inf_nan=False)
    academic: float = Field(ge=0, le=1, allow_inf_nan=False)


class RiskInputs(SchemaModel):
    credits: NonNegative
    lower: NonNegative
    upper: NonNegative
    retake_codes: tuple[CourseCode, ...] = ()
    academic_status: AcademicStatus


class RiskResult(SchemaModel):
    plan_hash: Identifier
    validation_hash: Identifier
    context_hash: Identifier
    risk_version: Identifier
    config_hash: Identifier
    risk_score: float = Field(ge=0, le=1, allow_inf_nan=False)
    risk_level: Literal["low", "medium", "high"]
    safety: float = Field(ge=0, le=1, allow_inf_nan=False)
    components: RiskComponents
    inputs: RiskInputs
    source_refs: tuple[Identifier, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def safety_complements_risk(self):
        if abs(self.safety - (1 - self.risk_score)) > 1e-12:
            raise ValueError("Safety must equal 1 - risk_score")
        return self


class RiskBatch(SchemaModel):
    context_hash: Identifier
    results: tuple[RiskResult, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def one_current_result_per_plan(self):
        hashes = [item.plan_hash for item in self.results]
        if len(hashes) != len(set(hashes)):
            raise ValueError("Duplicate risk plan hash")
        if any(item.context_hash != self.context_hash for item in self.results):
            raise ValueError("Risk result context mismatch")
        return self


class NormalizationRange(SchemaModel):
    min: NonNegative
    max: NonNegative


class ScoredPlan(SchemaModel):
    plan_id: Identifier
    plan_version: Identifier
    plan_hash: Identifier
    validation_hash: Identifier
    courses: tuple[CourseCode, ...]
    raw: dict[Identifier, NonNegative]
    normalized: dict[Identifier, float]
    source_refs: tuple[Identifier, ...] = Field(min_length=1)
    contributions: dict[Strategy, dict[Identifier, float]]
    scores: dict[Strategy, float]


class SelectedPlan(SchemaModel):
    plan_id: Identifier
    strategy: Strategy


class PairwiseDiversity(SchemaModel):
    left: Identifier
    right: Identifier
    distance: float = Field(ge=0, le=1, allow_inf_nan=False)


class SelectionDecision(SchemaModel):
    strategy: Strategy
    plan_id: Identifier
    accepted: bool
    distances_to_selected: tuple[float, ...] = ()
    reason: Identifier


class RankingResult(SchemaModel):
    ranking_version: Identifier
    config_hash: Identifier
    context_hash: Identifier
    pool_hash: Identifier
    normalization_ranges: dict[Identifier, NormalizationRange]
    scored_plans: tuple[ScoredPlan, ...]
    selected_plans: tuple[SelectedPlan, ...]
    pairwise_diversity: tuple[PairwiseDiversity, ...]
    selection_trace: tuple[SelectionDecision, ...]
    shortfall_reason: Identifier | None = None
    recommended_plan_id: Identifier | None = None

    @model_validator(mode="after")
    def selection_is_consistent(self):
        ids = {item.plan_id for item in self.scored_plans}
        selected = [item.plan_id for item in self.selected_plans]
        if len(selected) > 3 or len(selected) != len(set(selected)):
            raise ValueError("Selected plans must be distinct and limited to three")
        if not set(selected).issubset(ids):
            raise ValueError("Selected plan is absent from scored pool")
        if self.recommended_plan_id is not None and self.recommended_plan_id not in selected:
            raise ValueError("Recommended plan must be selected")
        if (len(selected) < 3) != (self.shortfall_reason is not None):
            raise ValueError("Shortfall reason must match selected plan count")
        return self
