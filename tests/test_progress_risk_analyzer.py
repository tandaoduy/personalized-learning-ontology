from types import SimpleNamespace

from flask_app.services.progress_risk_analyzer import ProgressRiskAnalyzer


def _engine(course_data, quotas=None):
    return SimpleNamespace(course_data=course_data, elective_quotas=quotas or {})


def _course(credit, semester, prereqs=None, **overrides):
    course = {
        "credit": credit,
        "recommended_sem": semester,
        "prereqs": prereqs or [],
        "is_it_program": True,
        "is_required_major": True,
    }
    course.update(overrides)
    return course


# UT-RISK-01: Không có chương trình đào tạo thì trả về trạng thái UNKNOWN.
def test_assess_student_is_unknown_when_engine_is_not_available(student):
    result = ProgressRiskAnalyzer().assess_student(student)

    assert result["risk_level"] == "UNKNOWN"


# UT-RISK-02: Sinh viên hoàn thành đúng tiến độ được phân loại LOW.
def test_assess_student_is_on_track_when_all_required_courses_are_passed(student):
    student.current_semester = 2
    student.passed_courses = ["A", "B"]
    engine = _engine({"A": _course(3, 1), "B": _course(3, 2)})

    result = ProgressRiskAnalyzer(engine).assess_student(student)

    assert result["progress_status"] == "ON_TRACK"
    assert result["risk_level"] == "LOW"
    assert result["credit_progress"]["earned_required_credits"] == 6


# UT-RISK-03: Chuỗi tiên quyết không thể hoàn tất đúng hạn được phân loại HIGH.
def test_assess_student_marks_high_risk_when_prerequisite_chain_cannot_finish_in_time(student):
    student.current_semester = 3
    engine = _engine({
        "A": _course(3, 1),
        "B": _course(3, 2, ["A"]),
        "C": _course(3, 3, ["B"]),
    })

    result = ProgressRiskAnalyzer(engine).assess_student(student)

    assert result["progress_status"] == "BEHIND_SCHEDULE"
    assert result["risk_level"] == "HIGH"
    assert result["can_complete_on_time"]["value"] is False


# UT-RISK-04: Môn trượt chặn học phần sau được phân loại MEDIUM.
def test_assess_student_marks_medium_risk_when_failed_prerequisite_blocks_course(student):
    # Vẫn còn đủ thời gian và tải tín chỉ để hoàn tất, nhưng môn A đang chặn B.
    student.current_semester = 2
    student.failed_courses = ["A"]
    engine = _engine({
        "A": _course(3, 1),
        "B": _course(3, 3, ["A"]),
        "C": _course(3, 4),
    })

    result = ProgressRiskAnalyzer(engine).assess_student(student)

    assert result["progress_status"] == "AT_RISK"
    assert result["risk_level"] == "MEDIUM"
    assert result["failed_courses_analysis"]["blocked_required_courses"] == ["B"]


# UT-RISK-05: Môn tự chọn trượt đã được thay thế cùng quota không làm tăng nguy cơ.
def test_assess_student_does_not_raise_risk_for_failed_elective_replaced_by_same_group(student):
    student.current_semester = 2
    student.passed_courses = ["E2"]
    student.failed_courses = ["E1"]
    engine = _engine(
        {
            "E1": _course(3, 1, is_required_major=False, elective_category="general"),
            "E2": _course(3, 2, is_required_major=False, elective_category="general"),
            # Các môn bắt buộc giúp chương trình có curriculum hợp lệ; E1/E2 vẫn
            # được dùng để kiểm tra quy tắc thay thế môn tự chọn cùng quota.
            "CORE1": _course(3, 1),
            "CORE2": _course(3, 3),
        },
        quotas={"general": 1},
    )
    student.passed_courses.append("CORE1")

    result = ProgressRiskAnalyzer(engine).assess_student(student)

    assert result["risk_level"] == "LOW"
    assert result["failed_courses_analysis"]["unresolved_elective_failures"] == []
