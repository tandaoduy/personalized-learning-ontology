"""Deployment readiness must reject a successful HTTP response with no ontology."""

import pytest

from scripts.container_healthcheck import validate_health


def ready_payload():
    return {
        "success": True,
        "data": {
            "status": "ok",
            "student_service_ready": True,
            "recommendation_engine_ready": True,
            "ontology_loaded": True,
            "course_count": 1,
        },
    }


def test_accepts_ready_application():
    validate_health(ready_payload())


@pytest.mark.parametrize("field,value", [
    ("status", "error"),
    ("student_service_ready", False),
    ("recommendation_engine_ready", False),
    ("ontology_loaded", False),
    ("course_count", 0),
])
def test_rejects_unready_service(field, value):
    payload = ready_payload()
    payload["data"][field] = value
    with pytest.raises(RuntimeError):
        validate_health(payload)


def test_rejects_missing_health_data():
    with pytest.raises(RuntimeError):
        validate_health({"success": True})
