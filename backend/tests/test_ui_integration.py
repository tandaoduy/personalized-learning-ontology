"""Kiểm thử tích hợp luồng giao diện người dùng (UI)."""

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

def test_ui_student_dashboard_loads(client):
    """Đảm bảo trang danh sách sinh viên được load thành công."""
    response = client.get("/students")
    assert response.status_code == 200
    assert b"Advisor Test" in response.data or b"S\xc6\xb0\xc6\xa1ng" in response.data or b"Sinh vi\xc3\xaan" in response.data

def test_ui_student_course_history_loads(client):
    """Đảm bảo trang lịch sử học tập của sinh viên load thành công với dữ liệu mẫu."""
    students = app.student_data_service.get_all_students()
    assert len(students) > 0
    student_id = students[0].student_id

    response = client.get(f"/students/{student_id}/course-history")
    assert response.status_code == 200
    # Phải có chứa mã sinh viên hoặc tên bảng lịch sử
    html_data = response.data.decode('utf-8')
    assert student_id in html_data
    
def test_ui_components_disabled_in_production(client):
    """Đảm bảo trang components không truy cập được nếu không ở debug mode."""
    original_debug = app.config["DEBUG"]
    app.config["DEBUG"] = False
    try:
        response = client.get("/components")
        assert response.status_code == 404
    finally:
        app.config["DEBUG"] = original_debug
