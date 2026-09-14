"""Persistence isolation and integrity tests for AgentRunStore."""
from datetime import datetime, timezone
import pytest

from backend.app.agent import AgentOrchestrator
from backend.app.schemas import FeedbackNormalization, FeedbackRequest, PlanningRequest
from backend.app.services.agent_run_store import AgentRunStore, FeedbackIdempotencyConflict, RunRevisionConflict


def request(request_id: str) -> PlanningRequest:
    return PlanningRequest(
        request_id=request_id, student_id=f"S-{request_id}", target_term_id="T1",
        goal="on_time", target_credits=15,
    )


def test_store_round_trip_and_revision_conflict(tmp_path):
    store = AgentRunStore(tmp_path / "agent-runs")
    orchestrator = AgentOrchestrator()
    initial = orchestrator.create_run(request("R1"), run_id="RUN_A")
    store.save_state(initial)

    started = orchestrator.start(initial)
    store.save_state(started, expected_revision=0)
    loaded = store.load_state("RUN_A")
    assert loaded == started

    with pytest.raises(RunRevisionConflict):
        store.save_state(started, expected_revision=1)


def test_runs_and_artifacts_are_isolated_and_hash_checked(tmp_path):
    store = AgentRunStore(tmp_path / "agent-runs")
    orchestrator = AgentOrchestrator()
    run_a = orchestrator.create_run(request("RA"), run_id="RUN_A")
    run_b = orchestrator.create_run(request("RB"), run_id="RUN_B")
    store.save_state(run_a)
    store.save_state(run_b)

    assert store.load_state("RUN_A").request.request_id == "RA"
    assert store.load_state("RUN_B").request.request_id == "RB"
    reference = store.save_artifact("RUN_A", "json", b'{"plan":"A"}')
    assert store.read_artifact(reference) == b'{"plan":"A"}'

    artifact_path = tmp_path / "agent-runs" / reference.ref
    artifact_path.write_bytes(b"changed")
    with pytest.raises(ValueError, match="hash mismatch"):
        store.read_artifact(reference)


def test_feedback_is_idempotent_and_conflicting_reuse_is_rejected(tmp_path):
    store = AgentRunStore(tmp_path / "agent-runs")
    feedback = FeedbackRequest(
        feedback_id="feedback-1", run_id="RUN_A", displayed_result_hash="sha256:ranking",
        actor_pseudonym="advisor-1", actor_role="advisor", action="select",
        selected_plan_id="plan-1", created_at=datetime.now(timezone.utc),
    )
    normalization = FeedbackNormalization(
        feedback_id=feedback.feedback_id, feedback_hash="sha256:feedback",
        parent_result_hash="sha256:ranking", action="select", selected_plan_id="plan-1",
    )
    first = store.save_feedback("RUN_A", feedback, normalization, {"tool_name": "normalize_feedback"})
    duplicate = store.save_feedback("RUN_A", feedback, normalization, {"tool_name": "normalize_feedback"})
    assert first.duplicate is False
    assert duplicate.duplicate is True
    assert store.load_feedback("RUN_A", "feedback-1")["normalization"]["feedback_hash"] == "sha256:feedback"

    changed = feedback.model_copy(update={"selected_plan_id": "plan-2"})
    changed_normalization = normalization.model_copy(update={"selected_plan_id": "plan-2"})
    with pytest.raises(FeedbackIdempotencyConflict):
        store.save_feedback("RUN_A", changed, changed_normalization, {"tool_name": "normalize_feedback"})
