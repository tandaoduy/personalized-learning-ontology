"""Typed output for deterministic, evidence-grounded plan explanations."""
from typing import Literal

from pydantic import Field, model_validator

from .common import CourseCode, Identifier, KnowledgeVersion, SchemaModel


ClaimKind = Literal["course_classification", "validation", "risk", "ranking"]


class GroundedClaim(SchemaModel):
    claim_id: Identifier
    kind: ClaimKind
    text: str = Field(min_length=1)
    decision_ids: tuple[Identifier, ...] = Field(min_length=1)
    evidence_ids: tuple[Identifier, ...] = Field(min_length=1)
    source_refs: tuple[Identifier, ...] = Field(min_length=1)
    course_code: CourseCode | None = None


class GroundedExplanation(SchemaModel):
    plan_id: Identifier
    plan_hash: Identifier
    validation_hash: Identifier
    ranking_hash: Identifier
    knowledge_versions: KnowledgeVersion
    template_version: Identifier
    locale: Literal["vi-VN"] = "vi-VN"
    claims: tuple[GroundedClaim, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def claim_ids_are_unique(self):
        ids = [claim.claim_id for claim in self.claims]
        if len(ids) != len(set(ids)):
            raise ValueError("Explanation claim IDs must be unique")
        return self


class GroundedExplanationBatch(SchemaModel):
    ranking_hash: Identifier
    explanations: tuple[GroundedExplanation, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def one_explanation_per_plan(self):
        ids = [item.plan_id for item in self.explanations]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate explanation plan ID")
        if any(item.ranking_hash != self.ranking_hash for item in self.explanations):
            raise ValueError("Explanation ranking hash mismatch")
        return self
