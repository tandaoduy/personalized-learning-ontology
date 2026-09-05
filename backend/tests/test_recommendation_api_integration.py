"""Kiểm thử tích hợp luồng gợi ý công khai qua Flask API."""

import pytest

from backend.app.app import app


@pytest.fixture(scope="module")
def client():
    app.config.update(TESTING=True)
    client = app.test_client()
    with client.session_transaction() as session:
        session["role"] = "advisor"
        session["username"] = "ADVISOR_TEST"
        session["display_name"] = "Advisor Test"
    return client


@pytest.mark.integration
def test_recommendation_api_returns_a_plan_for_a_real_student(client, caplog):
    """Luồng phải đi qua service, RecommendationEngine.get_recommendation và API."""
    engine = app.recommendation_engine
    students = app.student_data_service.get_all_students()

    assert engine is not None
    assert engine.course_data
    assert students

    student_id = students[0].student_id
    with caplog.at_level("INFO"):
        response = client.post(
            "/api/recommendations",
            json={"student_id": student_id, "seed_offset": 0},
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True

    result = payload["data"]
    assert result["student_id"] == student_id
    assert result["total_recommended_count"] == len(result["recommended_courses"])
    assert result["total_recommended_credits"] == sum(
        course["credits"] for course in result["recommended_courses"]
    )
    assert result["total_recommended_credits"] <= app.config["REGISTER_MAX_CREDITS"]
    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert student_id not in messages
    assert "student_id" not in messages


@pytest.mark.integration
def test_recommendation_api_rejects_missing_student_id(client):
    response = client.post("/api/recommendations", json={})

    assert response.status_code == 400
    assert response.get_json()["success"] is False
