import pytest


# UT-GPA-01: Tính GPA có trọng số cho nhiều học phần hợp lệ.
def test_calculate_gpa_returns_weighted_average_for_valid_courses(student_data_service):
    # Arrange
    grades = {"CS101": 8.0, "CS102": 7.0}
    statuses = {"CS101": "Đạt", "CS102": "Đạt"}
    specified = {"CS101": True, "CS102": True}
    catalog = {"CS101": {"credit": 3}, "CS102": {"credit": 2}}

    # Act
    result = student_data_service._calculate_gpa(grades, statuses, specified, catalog)

    # Assert: (8 * 3 + 7 * 2) / (3 + 2) = 7.6
    assert result == 7.6


# UT-GPA-02: Danh sách học phần rỗng trả về GPA bằng 0.
def test_calculate_gpa_returns_zero_for_empty_course_list(student_data_service):
    assert student_data_service._calculate_gpa({}, {}, {}, {}) == 0.0


# UT-GPA-03: Bỏ qua môn miễn/không tính GPA và môn 0 tín chỉ.
def test_calculate_gpa_ignores_exempt_non_gpa_and_zero_credit_courses(student_data_service):
    grades = {"CS101": 8.0, "FLS310": 10.0, "PE101": 10.0, "ZERO": 10.0}
    statuses = {code: "Đạt" for code in grades}
    specified = {code: True for code in grades}
    catalog = {
        "CS101": {"credit": 3},
        "FLS310": {"credit": 4},
        "PE101": {"credit": 1, "is_physical_education_course": True},
        "ZERO": {"credit": 0},
    }

    assert student_data_service._calculate_gpa(grades, statuses, specified, catalog) == 8.0


# UT-GPA-04: Không đưa môn trượt hoặc thiếu điểm vào GPA.
def test_calculate_gpa_ignores_failed_and_unspecified_grade(student_data_service):
    grades = {"PASS": 8.0, "FAILED": 1.0, "EXEMPT": 0.0}
    statuses = {"PASS": "Đạt", "FAILED": "Chưa đạt", "EXEMPT": "Đạt"}
    specified = {"PASS": True, "FAILED": True, "EXEMPT": False}
    catalog = {code: {"credit": 3} for code in grades}

    assert student_data_service._calculate_gpa(grades, statuses, specified, catalog) == 8.0


# UT-RET-01: Học lại đạt, lấy điểm đạt tốt nhất và cộng tín chỉ một lần.
def test_process_course_entries_keeps_best_passing_grade_and_counts_credit_once(student_data_service):
    catalog = {"CS101": {"name": "Nhap mon", "credit": 3}}
    entries = [
        {"code": "cs101", "grade": 3.0, "semester_taken": 1},
        {"code": "CS101", "grade": 7.0, "semester_taken": 2},
        {"code": "CS101", "grade": 8.0, "semester_taken": 3},
    ]

    passed, failed, grades, statuses, specified, credits, attempts = student_data_service._process_course_entries(entries, catalog)

    assert passed == ["CS101"]
    assert failed == []
    assert grades == {"CS101": 8.0}
    assert statuses == {"CS101": "Đạt"}
    assert specified == {"CS101": True}
    assert credits == 3
    assert len(attempts) == 3


@pytest.mark.parametrize("grade", [-0.1, 10.1, "khong phai diem"])
# UT-DATA-01: Từ chối điểm âm, vượt 10 hoặc sai kiểu dữ liệu.
def test_process_course_entries_rejects_invalid_grade(student_data_service, grade):
    with pytest.raises(ValueError):
        student_data_service._process_course_entries(
            [{"code": "CS101", "grade": grade}], {"CS101": {"credit": 3}}
        )


# UT-DATA-02: Từ chối mã học phần không tồn tại trong catalog.
def test_process_course_entries_rejects_course_missing_from_catalog(student_data_service):
    with pytest.raises(ValueError):
        student_data_service._process_course_entries([{"code": "UNKNOWN", "grade": 8}], {})
