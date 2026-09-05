import random

import pytest

from backend.app.models.recommendation import RecommendedCourse
from backend.app.models.student import StudentProfile


@pytest.mark.parametrize(
    "credits, expected",
    [(12, 5), (13, 12), (15, 12), (16, 18), (18, 18), (19, 22), (21, 22), (22, 25)],
)
# UT-BOUND-01: Kiểm tra các ngưỡng điểm tải tín chỉ.
def test_credit_load_score_is_stable_at_every_boundary(recommendation_engine, credits, expected):
    assert recommendation_engine.calculate_credit_load_score(credits) == expected


@pytest.mark.parametrize(
    "semester, valid",
    [(0, False), (1, True), (8, True), (9, False)],
)
# UT-BOUND-02: Kiểm tra biên học kỳ hợp lệ từ 1 đến 8.
def test_student_semester_boundary(semester, valid):
    student = StudentProfile("SV1", "Test", 2024, "CNTT", current_semester=semester)
    assert (student.validate() == []) is valid


# UT-META-01: Đảo thứ tự đầu vào không làm thay đổi GPA.
def test_gpa_is_invariant_under_input_order(student_data_service):
    catalog = {"A": {"credit": 3}, "B": {"credit": 2}, "C": {"credit": 1}}
    grades = {"A": 8, "B": 6, "C": 10}
    statuses = {code: "Đạt" for code in grades}
    specified = {code: True for code in grades}

    original = student_data_service._calculate_gpa(grades, statuses, specified, catalog)
    reversed_result = student_data_service._calculate_gpa(
        dict(reversed(list(grades.items()))),
        dict(reversed(list(statuses.items()))),
        dict(reversed(list(specified.items()))),
        dict(reversed(list(catalog.items()))),
    )
    assert original == reversed_result == 7.67


# UT-INV-01: Bản ghi học trùng không làm tăng tín chỉ tích lũy.
def test_duplicate_attempt_does_not_increase_accumulated_credits(student_data_service):
    entries = [
        {"code": "CS101", "attempt_number": 1, "grade": 8},
        {"code": "CS101", "attempt_number": 1, "grade": 8},
    ]
    result = student_data_service._process_course_entries(entries, {"CS101": {"credit": 3}})
    assert result[5] == 3
    assert len(result[6]) == 2  # lịch sử vẫn được giữ, tín chỉ không bị cộng đôi


# UT-RET-02: Môn miễn được tính đạt/tín chỉ nhưng không tính GPA.
def test_exempt_course_is_passed_but_excluded_from_gpa(student_data_service):
    result = student_data_service._process_course_entries(
        [{"code": "CS101", "status": "Miễn"}], {"CS101": {"credit": 3}}
    )
    passed, failed, grades, statuses, specified, credits, _ = result
    assert passed == ["CS101"] and failed == []
    assert statuses["CS101"] == "Miễn" and specified["CS101"] is False
    assert credits == 3
    assert student_data_service._calculate_gpa(grades, statuses, specified, {"CS101": {"credit": 3}}) == 0.0


# UT-COREQ-01: Giữ nguyên bundle song hành và không vượt giới hạn tín chỉ.
def test_beam_search_keeps_corequisite_bundle_and_credit_invariant(recommendation_engine, student):
    recommendation_engine.max_credits = 5
    recommendation_engine.beam_width = 4
    recommendation_engine.course_data = {
        "A": {"corequisites": ["B"], "elective_category": None},
        "B": {"corequisites": [], "elective_category": None},
    }
    candidates = [
        RecommendedCourse("A", "A", 3, total_priority_score=10),
        RecommendedCourse("B", "B", 2, total_priority_score=1),
    ]

    selected, excluded = recommendation_engine._beam_search_optimize(
        student, candidates, {}, "đúng hạn", random.Random(7), set()
    )
    selected_codes = {course.code for course in selected}
    assert selected_codes == {"A", "B"}
    assert sum(course.credits for course in selected) <= recommendation_engine.max_credits
    assert len(selected_codes) == len(selected)


# UT-COREQ-02: Loại môn khi thiếu học phần song hành.
def test_beam_search_excludes_missing_corequisite(recommendation_engine, student):
    recommendation_engine.max_credits = 18
    recommendation_engine.beam_width = 2
    recommendation_engine.course_data = {"A": {"corequisites": ["MISSING"]}}
    selected, excluded = recommendation_engine._beam_search_optimize(
        student,
        [RecommendedCourse("A", "A", 3, total_priority_score=10)],
        {},
        "đúng hạn",
        random.Random(1),
        set(),
    )
    assert selected == []
    assert excluded[0].code == "A"
    assert excluded[0].failed_rules == ["corequisite"]


@pytest.mark.parametrize("specialization", ["Công nghệ phần mềm", "Hệ thống Thông tin"])
# UT-SPEC-01: Chỉ chọn môn thuộc chuyên ngành đã chọn.
def test_selected_specialization_accepts_matching_course_and_rejects_other_specialization(
    recommendation_engine, student, specialization
):
    student.specialization = specialization
    recommendation_engine.course_data = {
        "MATCH": {
            "name": "Môn đúng chuyên ngành", "credit": 3, "prereqs": [],
            "openSemesterType": 3, "recommended_sem": 1,
            "specializations": [specialization], "majors": [],
            "is_required_major": False, "is_required_specialization": True,
            "is_elective_major": False, "is_elective_specialization": False,
        },
        "OTHER": {
            "name": "Môn chuyên ngành khác", "credit": 3, "prereqs": [],
            "openSemesterType": 3, "recommended_sem": 1,
            "specializations": ["Trí tuệ nhân tạo"], "majors": [],
            "is_required_major": False, "is_required_specialization": True,
            "is_elective_major": False, "is_elective_specialization": False,
        },
    }

    valid, excluded = recommendation_engine._get_valid_courses(
        student, set(), set(), current_sem=1, next_sem=2, sem_type=2, study_goal="đúng hạn"
    )

    assert [course.code for course in valid] == ["MATCH"]
    assert any(item.code == "OTHER" and item.failed_rules == ["specialization"] for item in excluded)


# UT-SPEC-02: Chưa chọn chuyên ngành thì không đề xuất môn riêng của chuyên ngành.
def test_unselected_specialization_excludes_specialization_course(recommendation_engine, student):
    student.specialization = "Chưa chọn chuyên ngành"
    recommendation_engine.course_data = {
        "SPEC": {
            "name": "Môn chuyên ngành", "credit": 3, "prereqs": [],
            "openSemesterType": 3, "recommended_sem": 1,
            "specializations": ["Công nghệ phần mềm"], "majors": [],
            "is_required_major": False, "is_required_specialization": True,
            "is_elective_major": False, "is_elective_specialization": False,
        }
    }

    valid, excluded = recommendation_engine._get_valid_courses(
        student, set(), set(), current_sem=1, next_sem=2, sem_type=2, study_goal="đúng hạn"
    )

    assert valid == []
    assert excluded[0].failed_rules == ["specialization"]


# UT-GOAL-01: Mục tiêu học vượt cho phép học trước kỳ khuyến nghị.
def test_study_ahead_allows_course_before_recommended_semester(recommendation_engine, student):
    recommendation_engine.course_data = {
        "ADV": {
            "name": "Môn học vượt", "credit": 3, "prereqs": [],
            "openSemesterType": 3, "recommended_sem": 5,
            "specializations": [], "majors": [],
            "is_required_major": True, "is_required_specialization": False,
            "is_elective_major": False, "is_elective_specialization": False,
        }
    }

    valid, _ = recommendation_engine._get_valid_courses(
        student, set(), set(), current_sem=2, next_sem=3, sem_type=1, study_goal="học vượt"
    )

    assert [course.code for course in valid] == ["ADV"]


# UT-QUOTA-01: Đủ quota tự chọn thì loại ứng viên cùng nhóm.
def test_full_elective_quota_excludes_candidate(recommendation_engine, student):
    recommendation_engine.elective_quotas = {"general": 1, "physical": 0, "foundation": 0, "specialization": 0}
    recommendation_engine.course_data = {"E1": {"corequisites": [], "elective_category": "general"}}
    candidate = RecommendedCourse("E1", "E1", 3, total_priority_score=10)

    selected, excluded = recommendation_engine._beam_search_optimize(
        student, [candidate], {"general": 1}, "đúng hạn", random.Random(4), set()
    )

    assert selected == []
    assert excluded[0].failed_rules == ["elective_quota"]


# UT-QUOTA-02: Quota tự chọn còn thiếu thì cho phép ứng viên.
def test_remaining_elective_quota_allows_candidate(recommendation_engine, student):
    recommendation_engine.elective_quotas = {"general": 1, "physical": 0, "foundation": 0, "specialization": 0}
    recommendation_engine.beam_width = 2
    recommendation_engine.course_data = {"E1": {"corequisites": [], "elective_category": "general"}}
    candidate = RecommendedCourse("E1", "E1", 3, total_priority_score=10)

    selected, _ = recommendation_engine._beam_search_optimize(
        student, [candidate], {"general": 0}, "đúng hạn", random.Random(4), set()
    )

    assert [course.code for course in selected] == ["E1"]


# UT-BOUND-03: Đúng 27 tín chỉ được chọn, 28 tín chỉ bị loại.
def test_beam_search_accepts_exact_max_credits_and_rejects_excess(recommendation_engine, student):
    recommendation_engine.max_credits = 27
    recommendation_engine.beam_width = 2
    recommendation_engine.course_data = {"MAX": {"corequisites": []}, "OVER": {"corequisites": []}}
    candidates = [
        RecommendedCourse("MAX", "Đúng giới hạn", 27, total_priority_score=10),
        RecommendedCourse("OVER", "Vượt giới hạn", 28, total_priority_score=20),
    ]

    selected, excluded = recommendation_engine._beam_search_optimize(
        student, candidates, {}, "đúng hạn", random.Random(5), set()
    )

    assert [course.code for course in selected] == ["MAX"]
    assert any(item.code == "OVER" and item.failed_rules == ["max_credits"] for item in excluded)


# UT-PROGRESS-01: Sinh viên gần tốt nghiệp còn một môn vẫn có thể hoàn thành đúng hạn.
def test_near_graduation_student_with_one_remaining_course_can_finish_on_time(student):
    from backend.app.services.progress_risk_analyzer import ProgressRiskAnalyzer
    from types import SimpleNamespace

    student.current_semester = 8
    student.passed_courses = ["A"]
    engine = SimpleNamespace(
        course_data={
            "A": {"credit": 3, "recommended_sem": 1, "prereqs": [], "is_required_major": True},
            "B": {"credit": 3, "recommended_sem": 8, "prereqs": [], "is_required_major": True},
        },
        elective_quotas={},
    )

    result = ProgressRiskAnalyzer(engine).assess_student(student)

    assert result["can_complete_on_time"]["value"] is True
    assert result["risk_level"] == "LOW"


# UT-DATA-03: Chuỗi tiên quyết báo đúng mã môn không tồn tại.
def test_prerequisite_chain_reports_unknown_reference(recommendation_engine):
    recommendation_engine.course_data = {"A": {"name": "A", "prereqs": ["NOT_FOUND"]}}
    result = recommendation_engine.get_prerequisite_chain("A")
    assert result["prerequisites"][0]["not_found"] is True


# UT-RISK-06: Mức nguy cơ trả về thuộc tập giá trị được quy định.
def test_risk_result_exposes_only_documented_levels(student, recommendation_engine):
    recommendation_engine.course_data = {"A": {"credit": 3, "recommended_sem": 1, "prereqs": [], "is_required_major": True}}
    result = __import__("backend.app.services.progress_risk_analyzer", fromlist=["ProgressRiskAnalyzer"]).ProgressRiskAnalyzer(recommendation_engine).assess_student(student)
    assert result["risk_level"] in {"LOW", "MEDIUM", "HIGH", "UNKNOWN"}
