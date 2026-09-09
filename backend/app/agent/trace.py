"""Trace construction kept separate from state transitions."""
from backend.app.schemas.agent_state import ToolAction, ToolTraceEvent
from backend.app.schemas.capability import ToolResult


class TraceRecorder:
    @staticmethod
    def from_result(action: ToolAction, result: ToolResult[object], iteration: int, deadline_at, attempt: int):
        return ToolTraceEvent(
            call_id=result.provenance.call_id, action=action, tool_name=result.provenance.tool_name,
            iteration=iteration, outcome=result.status, input_hash=result.provenance.input_hash,
            output_hash=result.provenance.output_hash, deadline_at=deadline_at,
            attempt=attempt, evidence_ids=result.provenance.evidence_ids,
            occurred_at=result.provenance.finished_at, error=result.error,
        )
