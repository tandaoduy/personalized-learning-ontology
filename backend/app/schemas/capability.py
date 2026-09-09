"""Common contracts for capability calls controlled by the Agent Orchestrator."""
from typing import Generic, Literal, TypeVar

from pydantic import AwareDatetime, Field, model_validator

from .common import Identifier, KnowledgeVersion, PositiveInt, SchemaModel


T = TypeVar("T")


class ToolCallContext(SchemaModel):
    run_id: Identifier
    call_id: Identifier
    iteration: int = Field(ge=0, strict=True)
    contract_version: Identifier
    deadline_at: AwareDatetime
    attempt: PositiveInt
    input_hash: Identifier
    idempotency_key: Identifier | None = None


class ToolError(SchemaModel):
    code: Identifier
    message: Identifier
    retryable: bool = False
    field_paths: tuple[Identifier, ...] = ()
    course_codes: tuple[Identifier, ...] = ()
    evidence_ids: tuple[Identifier, ...] = ()


class Provenance(SchemaModel):
    call_id: Identifier
    tool_name: Identifier
    tool_version: Identifier
    input_hash: Identifier
    output_hash: Identifier | None = None
    knowledge_versions: KnowledgeVersion | None = None
    source_refs: tuple[Identifier, ...] = ()
    evidence_ids: tuple[Identifier, ...] = ()
    started_at: AwareDatetime
    finished_at: AwareDatetime

    @model_validator(mode="after")
    def finish_after_start(self):
        if self.finished_at < self.started_at:
            raise ValueError("Provenance finished_at must not precede started_at")
        return self


class ToolResult(SchemaModel, Generic[T]):
    status: Literal["ok", "error"]
    output: T | None = None
    error: ToolError | None = None
    provenance: Provenance

    @model_validator(mode="after")
    def exactly_one_outcome(self):
        if (self.output is None) == (self.error is None):
            raise ValueError("ToolResult requires exactly one of output or error")
        if self.status == "ok" and self.output is None:
            raise ValueError("Successful ToolResult requires output")
        if self.status == "ok" and self.provenance.output_hash is None:
            raise ValueError("Successful ToolResult requires provenance output_hash")
        if self.status == "error" and self.error is None:
            raise ValueError("Failed ToolResult requires error")
        return self
