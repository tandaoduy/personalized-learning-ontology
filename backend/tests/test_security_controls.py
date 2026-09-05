"""Kiểm thử các rào chắn bảo mật ở mức ứng dụng."""

from datetime import timedelta

from backend.app.app import app
from backend.app.routes.auth_routes import _password_matches
from werkzeug.security import generate_password_hash


def test_recommendation_logs_do_not_contain_student_identifier(caplog):
    """Recommendation logs must not contain a student ID or identifier field."""
    from backend.app.config import Config
    from backend.app.models.student import StudentProfile
    from backend.app.services.recommendation_engine import RecommendationEngine

    engine = RecommendationEngine(
        Config.ONTOLOGY_PATH,
        Config.BEAM_WIDTH,
        Config.REGISTER_MAX_CREDITS,
        Config.REGISTER_MIN_CREDITS,
        {"debt": Config.WEIGHT_DEBT, "link": Config.WEIGHT_LINK, "delay": Config.WEIGHT_DELAY},
        Config.ELECTIVE_QUOTAS,
    )
    student = StudentProfile(
        student_id="SVLOG001",
        name="Demo Student",
        year_admitted=2023,
        major="Công Nghệ Thông Tin",
        specialization="Công nghệ phần mềm",
        study_goal="đúng hạn",
        total_credits_accumulated=0,
        gpa_accumulated=0.0,
        academic_class="65.CNTT-1",
        current_semester=1,
        passed_courses={},
        course_grades=[],
        failed_courses=[],
        course_attempts=[],
    )

    with caplog.at_level("INFO"):
        engine.get_recommendation(student, seed_offset=0)

    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "SVLOG001" not in messages
    assert "student_id" not in messages


def test_passwords_are_verified_against_one_way_hashes():
    hashed = generate_password_hash("correct horse battery staple")

    assert hashed != "correct horse battery staple"
    assert _password_matches({"password_hash": hashed}, "correct horse battery staple")
    assert not _password_matches({"password_hash": hashed}, "wrong password")


def test_session_cookie_and_expiration_configuration_are_secure():
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert app.config["PERMANENT_SESSION_LIFETIME"] == timedelta(minutes=60)


def test_components_are_not_exposed_when_debug_is_disabled():
    original_debug = app.config["DEBUG"]
    app.config["DEBUG"] = False
    try:
        response = app.test_client().get("/components")
        assert response.status_code == 404
    finally:
        app.config["DEBUG"] = original_debug


def test_recommendation_api_requires_authentication():
    response = app.test_client().post("/api/recommendations", json={"student_id": "SVDEMO0001"})

    assert response.status_code == 401
    assert response.get_json()["success"] is False


def test_registration_rejects_weak_or_malformed_credentials():
    response = app.test_client().post(
        "/api/auth/register",
        json={"role": "student", "username": "bad user", "password": "short"},
    )

    assert response.status_code == 400
    assert response.get_json()["success"] is False
