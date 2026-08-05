def _course(**overrides):
    course = {
        "name": "Mon hoc",
        "credit": 3,
        "prereqs": [],
        "corequisites": [],
        "openSemesterType": 3,
        "recommended_sem": 3,
        "specializations": [],
        "majors": [],
        "is_required_major": True,
        "is_required_specialization": False,
        "is_elective_major": False,
        "is_elective_specialization": False,
    }
    course.update(overrides)
    return course


# UT-ALG-01: Chọn môn khi đủ tiên quyết và đúng học kỳ mở.
def test_valid_courses_includes_course_when_prerequisites_and_open_semester_match(recommendation_engine, student):
    recommendation_engine.course_data = {
        "CS101": _course(recommended_sem=1),
        "CS201": _course(prereqs=["CS101"], recommended_sem=3, openSemesterType=1),
    }
    student.passed_courses = ["CS101"]

    valid, excluded = recommendation_engine._get_valid_courses(
        student, {"CS101"}, set(), current_sem=2, next_sem=3, sem_type=1, study_goal="đúng hạn"
    )

    assert [course.code for course in valid] == ["CS201"]
    assert any(item.code == "CS101" and "already_passed" in item.failed_rules for item in excluded)


# UT-ALG-02: Loại môn thiếu tiên quyết và hiển thị lý do.
def test_valid_courses_excludes_missing_prerequisite_with_reason(recommendation_engine, student):
    recommendation_engine.course_data = {"CS201": _course(prereqs=["CS101"], openSemesterType=1)}

    valid, excluded = recommendation_engine._get_valid_courses(
        student, set(), set(), current_sem=2, next_sem=3, sem_type=1, study_goal="đúng hạn"
    )

    assert valid == []
    item = excluded[0]
    assert item.code == "CS201"
    assert item.failed_rules == ["prerequisite"]


# UT-ALG-03: Loại môn không mở trong học kỳ hiện tại.
def test_valid_courses_excludes_course_not_open_in_current_semester(recommendation_engine, student):
    recommendation_engine.course_data = {"CS201": _course(openSemesterType=2)}

    valid, excluded = recommendation_engine._get_valid_courses(
        student, set(), set(), current_sem=2, next_sem=3, sem_type=1, study_goal="đúng hạn"
    )

    assert valid == []
    assert excluded[0].failed_rules == ["open_semester"]


# UT-ALG-04: Loại môn không thuộc ngành của sinh viên.
def test_valid_courses_excludes_course_from_another_major(recommendation_engine, student):
    recommendation_engine.course_data = {"BUS101": _course(majors=["Quan tri kinh doanh"])}

    valid, excluded = recommendation_engine._get_valid_courses(
        student, set(), set(), current_sem=2, next_sem=3, sem_type=1, study_goal="đúng hạn"
    )

    assert valid == []
    assert excluded[0].failed_rules == ["major"]


# UT-ALG-05: Ưu tiên học lại môn đã trượt.
def test_valid_courses_marks_failed_course_as_retake_and_prioritizes_it(recommendation_engine, student):
    recommendation_engine.course_data = {
        "NORMAL": _course(recommended_sem=3, openSemesterType=1),
        "DEBT": _course(recommended_sem=1, openSemesterType=1),
    }
    recommendation_engine.dependency_count = {"DEBT": 1}

    valid, _ = recommendation_engine._get_valid_courses(
        student, set(), {"DEBT"}, current_sem=2, next_sem=3, sem_type=1, study_goal="đúng hạn"
    )

    assert valid[0].code == "DEBT"
    assert valid[0].is_retake is True


# UT-ALG-06: Môn nợ A được ưu tiên, môn B phụ thuộc A bị loại.
def test_failed_prerequisite_is_prioritized_while_dependent_course_is_excluded(recommendation_engine, student):
    """Ca nghiệp vụ điển hình: nợ A phải trả trước, B bị khóa bởi A."""
    recommendation_engine.course_data = {
        "A": _course(name="A", recommended_sem=1, openSemesterType=1),
        "B": _course(name="B", prereqs=["A"], recommended_sem=3, openSemesterType=1),
    }
    recommendation_engine.dependency_count = {"A": 1}

    valid, excluded = recommendation_engine._get_valid_courses(
        student, set(), {"A"}, current_sem=2, next_sem=3, sem_type=1, study_goal="đúng hạn",
        priority_mode="priority_retake"
    )

    assert [course.code for course in valid] == ["A"]
    dependent = next(item for item in excluded if item.code == "B")
    assert dependent.failed_rules == ["prerequisite"]
    assert "A" in dependent.reasons[0]


# UT-ALG-07: Phát hiện chu trình tiên quyết mà không đệ quy vô hạn.
def test_get_prerequisite_chain_reports_cycle_without_recursing_forever(recommendation_engine):
    recommendation_engine.course_data = {
        "A": _course(name="A", prereqs=["B"]),
        "B": _course(name="B", prereqs=["A"]),
    }

    chain = recommendation_engine.get_prerequisite_chain("A")

    assert chain["prerequisites"][0]["prerequisites"][0]["cycle_detected"] is True
