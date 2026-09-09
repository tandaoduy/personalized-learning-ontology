"""Shared helpers for capability adapters."""
from datetime import datetime, timezone
from hashlib import sha256

from backend.app.schemas import Provenance, ToolCallContext, ToolError, ToolResult
from backend.app.schemas.common import SchemaModel

TOOL_VERSION = "capability-v1"


def now() -> datetime:
    return datetime.now(timezone.utc)


def output_hash(output: SchemaModel) -> str:
    return "sha256:" + sha256(output.model_dump_json().encode("utf-8")).hexdigest()


def ok(context: ToolCallContext, tool_name: str, output: SchemaModel, *,
       started_at: datetime, finished_at: datetime | None = None,
       knowledge_versions=None, source_refs: tuple[str, ...] = ()) -> ToolResult:
    finished = finished_at or now()
    return ToolResult(
        status="ok",
        output=output,
        provenance=Provenance(
            call_id=context.call_id,
            tool_name=tool_name,
            tool_version=TOOL_VERSION,
            input_hash=context.input_hash,
            output_hash=output_hash(output),
            knowledge_versions=knowledge_versions,
            source_refs=source_refs,
            started_at=started_at,
            finished_at=finished,
        ),
    )


def fail(context: ToolCallContext, tool_name: str, error: ToolError, *,
         started_at: datetime, finished_at: datetime | None = None) -> ToolResult:
    return ToolResult(
        status="error",
        error=error,
        provenance=Provenance(
            call_id=context.call_id,
            tool_name=tool_name,
            tool_version=TOOL_VERSION,
            input_hash=context.input_hash,
            started_at=started_at,
            finished_at=finished_at or now(),
        ),
    )
