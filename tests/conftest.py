import logging

import pytest

from flask_app.models.student import StudentProfile
from flask_app.services.recommendation_engine import RecommendationEngine
from flask_app.services.student_data_service import StudentDataService


@pytest.fixture
def student_data_service():
    """Service không truy cập file khi kiểm thử các hàm xử lý thuần.

    Các test gọi trực tiếp các hàm xử lý catalog, vì vậy không cần ``tmp_path``.
    Không dùng fixture này giúp suite chạy được trên Windows nơi thư mục Temp
    có thể bị chính sách bảo mật chặn quyền ``scandir``/tạo thư mục.
    """
    return StudentDataService("students-test.json", "students-test.csv")


@pytest.fixture
def student():
    return StudentProfile(
        student_id="SV001",
        name="Nguyen Van A",
        year_admitted=2024,
        major="Cong nghe thong tin",
        current_semester=2,
        academic_class="64.CNTT-1",
    )


@pytest.fixture
def recommendation_engine():
    """Engine tối giản: bỏ qua __init__ để unit test không đọc RDF/ontology."""
    engine = RecommendationEngine.__new__(RecommendationEngine)
    engine.max_credits = 27
    engine.min_credits = 10
    engine.heuristic_weights = {"debt": 1000, "link": 100, "delay": 50}
    engine.elective_quotas = {"general": 1, "physical": 2, "foundation": 1, "specialization": 3}
    engine.dependency_count = {}
    engine.logger = logging.getLogger("tests.recommendation")
    engine.course_data = {}
    return engine
