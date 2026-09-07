"""Fail the container health check if the ontology engine is unavailable."""

import json
from urllib.request import urlopen


def validate_health(payload):
    data = payload.get("data", {})
    if not (
        payload.get("success") is True
        and data.get("status") == "ok"
        and data.get("student_service_ready") is True
        and data.get("recommendation_engine_ready") is True
        and data.get("ontology_loaded") is True
        and data.get("course_count", 0) > 0
    ):
        raise RuntimeError("Application or ontology engine is not ready")


if __name__ == "__main__":
    with urlopen("http://127.0.0.1:8000/api/health", timeout=4) as response:
        validate_health(json.load(response))
