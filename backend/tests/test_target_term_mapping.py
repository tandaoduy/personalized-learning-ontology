"""The initial MVP deliberately supports only the next academic term."""
from datetime import datetime, timedelta, timezone

import pytest

from backend.app.capabilities import load_knowledge_context, load_student_context
from backend.app.schemas import PlanningRequest, StudentSnapshot, ToolCallContext


def context(action):
    return ToolCallContext(run_id="RUN_TERM", call_id="CALL_" + action, iteration=0,
        contract_version="agent-orchestrator-v1", attempt=1,
        deadline_at=datetime.now(timezone.utc) + timedelta(seconds=30), input_hash="sha256:" + action)


@pytest.mark.parametrize("term", ["past-term", "2026-1", "arbitrary"])
def test_non_next_term_is_rejected_before_reading_student_source(term):
    request = PlanningRequest(request_id="term-test", student_id="S", target_term_id=term,
        goal="on_time", target_credits=15)
    result = load_student_context(context("student"), request, object())
    assert result.status == "error"
    assert result.error.code == "TARGET_TERM_UNSUPPORTED"


def test_non_next_term_is_rejected_by_knowledge_loader_too():
    request = PlanningRequest(request_id="term-test", student_id="S", target_term_id="past-term",
        goal="on_time", target_credits=15)
    student = StudentSnapshot(student_id="S", student_version="s1", captured_at=datetime.now(timezone.utc),
        curriculum_id="c1", major_id="m1", current_semester=2)
    result = load_knowledge_context(context("knowledge"), request, student, object(), object())
    assert result.status == "error"
    assert result.error.code == "KNOWLEDGE_CONTEXT_ERROR"
    assert result.error.message == "TARGET_TERM_UNSUPPORTED"
