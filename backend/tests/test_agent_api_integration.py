"""Integration coverage for persisted Agent feedback, re-planning and confirmation APIs."""
from datetime import datetime, timezone

import pytest

from backend.app.app import app
from backend.app.services.agent_run_store import AgentRunStore
from backend.app.services.grounded_explanation_service import ranking_hash
from backend.app.schemas import RankingResult

pytestmark = pytest.mark.integration


@pytest.fixture
def client(tmp_path):
    app.config.update(TESTING=True)
    app.agent_run_store = AgentRunStore(tmp_path / "agent-runs")
    client = app.test_client()
    with client.session_transaction() as auth:
        auth["role"] = "advisor"
        auth["username"] = "advisor-001"
    return client


def create_sv001_run(client, request_id: str) -> dict:
    response = client.post("/api/agent/runs", json={
        "request_id": request_id, "student_id": "SV001", "target_term_id": "next-term",
        "goal": "on_time", "target_credits": 15,
    })
    assert response.status_code == 201
    return response.get_json()["data"]


def feedback_for(result: dict, action: str, feedback_id: str, **extra) -> dict:
    payload = {
        "feedback_id": feedback_id,
        "run_id": result["run_id"],
        "displayed_result_hash": ranking_hash(RankingResult.model_validate(result["ranking"])),
        "actor_pseudonym": "advisor-001", "actor_role": "advisor", "action": action,
        "selected_plan_id": result["ranking"]["recommended_plan_id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    payload.update(extra)
    return payload


def test_agent_api_stores_feedback_idempotently_and_exposes_trace(client):
    result = create_sv001_run(client, "api-feedback")
    run_id = result["run_id"]
    assert client.get(f"/api/agent/runs/{run_id}").get_json()["data"]["run_id"] == run_id
    trace = client.get(f"/api/agent/runs/{run_id}/trace").get_json()["data"]["trace"]
    assert trace[-1]["action"] == "explain_plans"

    feedback = feedback_for(result, "select", "feedback-api-select")
    first = client.post(f"/api/agent/runs/{run_id}/feedback", json=feedback)
    assert first.status_code == 200
    assert first.get_json()["data"]["receipt"]["duplicate"] is False
    retry = client.post(f"/api/agent/runs/{run_id}/feedback", json=feedback)
    assert retry.status_code == 200
    assert retry.get_json()["data"]["receipt"]["duplicate"] is True

    stale = feedback_for(result, "select", "feedback-api-stale", displayed_result_hash="sha256:stale")
    stale_response = client.post(f"/api/agent/runs/{run_id}/feedback", json=stale)
    assert stale_response.status_code == 422
    assert stale_response.get_json()["error"] == "STALE_FEEDBACK"

    wrong_run = dict(feedback)
    wrong_run["run_id"] = "RUN_OTHER"
    wrong_response = client.post(f"/api/agent/runs/{run_id}/feedback", json=wrong_run)
    assert wrong_response.status_code == 422
    assert wrong_response.get_json()["error"] == "FEEDBACK_RUN_MISMATCH"


def test_agent_api_replans_and_confirms(client):
    initial = create_sv001_run(client, "api-replan")
    replace = feedback_for(initial, "modify", "feedback-api-replace",
        operations=[{"kind": "replace", "course_code": "INT6209", "replacement_course_code": "SOT366"}],
        reason="Thay hoc phan theo y kien co van.")
    replanned_response = client.post(f"/api/agent/runs/{initial['run_id']}/replan", json=replace)
    assert replanned_response.status_code == 201
    replanned = replanned_response.get_json()["data"]["result"]
    assert replanned["status"] == "awaiting_feedback"
    assert all(item["status"] == "valid" for item in replanned["validations"])

    confirm = feedback_for(replanned, "confirm", "feedback-api-confirm")
    confirmed_response = client.post(f"/api/agent/runs/{replanned['run_id']}/confirm", json=confirm)
    assert confirmed_response.status_code == 201
    confirmed = confirmed_response.get_json()["data"]["result"]
    assert confirmed["status"] == "confirmed"
    assert confirmed["confirmation"]["validation"]["status"] == "valid"
