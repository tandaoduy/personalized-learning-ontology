"""Immutable state and trace records for one Agent planning run."""
from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from .capability import ToolError
from .common import Identifier, KnowledgeVersion, SchemaModel
from .feedback import AdjustmentRequest
from .planning import PlanningRequest


RunStatus = Literal[
    "received", "loading_context", "loading_knowledge", "building_course_space",
    "generating", "validating", "assessing_risk", "ranking", "explaining",
    "awaiting_feedback", "replanning", "final_validating", "confirmed",
    "needs_data", "no_plan_found", "failed",
]
ToolAction = Literal[
    "load_student_context", "load_knowledge_context", "build_course_space",
    "generate_candidates", "validate_candidates", "assess_plan_risk",
    "rank_valid_plans", "explain_plans", "normalize_feedback", "confirm",
]


class ValidationSummary(SchemaModel):
    plan_id: Identifier
    plan_version: Identifier
    status: Literal["valid", "invalid", "partially_validated", "error"]
    validation_hash: Identifier


class ArtifactReference(SchemaModel):
    artifact_id: Identifier
    kind: Identifier
    ref: Identifier
    content_hash: Identifier


class ToolTraceEvent(SchemaModel):
    call_id: Identifier
    action: ToolAction
    tool_name: Identifier
    iteration: int = Field(ge=0, strict=True)
    outcome: Literal["ok", "error"]
    input_hash: Identifier
    output_hash: Identifier | None = None
    deadline_at: AwareDatetime
    attempt: int = Field(ge=1, strict=True)
    evidence_ids: tuple[Identifier, ...] = ()
    occurred_at: AwareDatetime
    error: ToolError | None = None

    @model_validator(mode="after")
    def trace_matches_outcome(self):
        if self.outcome == "error" and self.error is None:
            raise ValueError("Error trace requires ToolError")
        if self.outcome == "ok" and self.error is not None:
            raise ValueError("Successful trace cannot carry ToolError")
        return self


class AgentState(SchemaModel):
    run_id: Identifier
    request: PlanningRequest
    status: RunStatus = "received"
    iteration: int = Field(default=0, ge=0, strict=True)
    max_generation_rounds: int = Field(default=3, ge=1, strict=True)
    max_candidate_attempts: int = Field(default=60, ge=1, strict=True)
    max_expanded_states: int = Field(default=5000, ge=1, strict=True)
    max_active_seconds: int = Field(default=120, ge=1, strict=True)
    seed: int = Field(default=42, strict=True)
    candidate_attempts_used: int = Field(default=0, ge=0, strict=True)
    expanded_states_used: int = Field(default=0, ge=0, strict=True)
    state_revision: int = Field(default=0, ge=0, strict=True)
    created_at: AwareDatetime
    updated_at: AwareDatetime
    active_deadline_at: AwareDatetime
    knowledge_versions: KnowledgeVersion | None = None
    student_snapshot_hash: Identifier | None = None
    knowledge_snapshot_hash: Identifier | None = None
    course_space_hash: Identifier | None = None
    candidate_hashes: tuple[Identifier, ...] = ()
    validations: tuple[ValidationSummary, ...] = ()
    risk_hashes: tuple[Identifier, ...] = ()
    ranking_hash: Identifier | None = None
    explanation_hashes: tuple[Identifier, ...] = ()
    feedback_hashes: tuple[Identifier, ...] = ()
    latest_adjustment: AdjustmentRequest | None = None
    artifacts: tuple[ArtifactReference, ...] = ()
    selected_plan_id: Identifier | None = None
    final_validation_hash: Identifier | None = None
    final_result_hash: Identifier | None = None
    trace: tuple[ToolTraceEvent, ...] = ()
    errors: tuple[ToolError, ...] = ()

    @model_validator(mode="after")
    def consistent_state(self):
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not precede created_at")
        if self.active_deadline_at < self.created_at:
            raise ValueError("active_deadline_at must not precede created_at")
        if self.iteration >= self.max_generation_rounds and self.status == "replanning":
            raise ValueError("Cannot replan after the generation-round budget")
        if self.candidate_attempts_used > self.max_candidate_attempts:
            raise ValueError("Candidate attempt budget exceeded")
        if self.expanded_states_used > self.max_expanded_states:
            raise ValueError("Expanded-state budget exceeded")
        valid_ids = {item.plan_id for item in self.validations if item.status == "valid"}
        if self.status in {"assessing_risk", "ranking", "explaining", "awaiting_feedback", "final_validating", "confirmed"} and not valid_ids:
            raise ValueError("Downstream planning states require at least one valid plan")
        if self.selected_plan_id is not None and self.selected_plan_id not in valid_ids:
            raise ValueError("Selected plan must have a valid validation result")
        if self.status == "confirmed" and self.selected_plan_id is None:
            raise ValueError("Confirmed state requires selected_plan_id")
        if self.status == "confirmed" and (self.final_validation_hash is None or self.final_result_hash is None):
            raise ValueError("Confirmed state requires final validation and result references")
        if len({item.artifact_id for item in self.artifacts}) != len(self.artifacts):
            raise ValueError("Artifact IDs must be unique")
        return self
