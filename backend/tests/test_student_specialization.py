"""Student context must preserve specialization before curriculum validation."""
from datetime import datetime, timezone

import pytest

from backend.app.capabilities.student_context import _major_id, snapshot_from_profile
from backend.app.models.student import CourseAttempt, StudentProfile
from backend.app.services.ontology_evidence_service import BASE


@pytest.mark.parametrize("label, expected", [
    ("Công nghệ phần mềm", "CNPM"),
    ("Công nghệ phần mềm".encode("utf-8").decode("latin1"), "CNPM"),
    ("Hệ thống thông tin", "HTTT"),
    ("Truyền thông và mạng máy tính", "TTMMT"),
    ("Trí tuệ nhân tạo", "TTNT"),
    ("Khoa học dữ liệu", "KHDL"),
    ("Chưa chọn chuyên ngành", None),
    ("", None),
])
def test_snapshot_preserves_specialization(label, expected):
    profile = StudentProfile(student_id="SV001", name="Test", year_admitted=2023,
        major="Công nghệ thông tin", specialization=label, current_semester=6,
        academic_class="65.CNTT-1")
    snapshot = snapshot_from_profile(profile, "test-version", datetime.now(timezone.utc))
    assert snapshot.specialization_id == (BASE + expected if expected else None)


@pytest.mark.parametrize("label, expected", [
    ("Công nghệ thông tin", "CNTT"),
    ("CNTT", "CNTT"),
    ("Khoa học máy tính", "KHMT"),
    ("KHMT", "KHMT"),
    ("Khoa học máy tính".encode("utf-8").decode("latin1"), "KHMT"),
])
def test_major_mapping_is_explicit_and_diacritic_insensitive(label, expected):
    assert _major_id(label) == BASE + expected


def test_unknown_major_does_not_default_to_cntt():
    with pytest.raises(ValueError, match="MAJOR_MAPPING_UNKNOWN"):
        _major_id("Ngành chưa được ánh xạ")


@pytest.mark.parametrize("status, outcome", [
    ("Đạt", "passed"),
    ("Miễn", "exempt"),
    ("Không tính điểm", "exempt"),
    ("Chưa đạt", "failed"),
])
def test_snapshot_preserves_attempt_outcomes(status, outcome):
    profile = StudentProfile(student_id="SV001", name="Test", year_admitted=2023,
        major="Công nghệ thông tin", current_semester=6, academic_class="65.CNTT-1",
        course_attempts=[CourseAttempt("A", "A", 4, status, 2, 1)])
    snapshot = snapshot_from_profile(profile, "test-version", datetime.now(timezone.utc))
    assert snapshot.attempts[0].outcome == outcome


def test_unknown_attempt_status_is_not_silently_treated_as_passed():
    profile = StudentProfile(student_id="SV001", name="Test", year_admitted=2023,
        major="Công nghệ thông tin", current_semester=6, academic_class="65.CNTT-1",
        course_attempts=[CourseAttempt("A", "A", 4, "Không rõ", 2, 1)])
    with pytest.raises(ValueError, match="COURSE_ATTEMPT_STATUS_UNKNOWN"):
        snapshot_from_profile(profile, "test-version", datetime.now(timezone.utc))
