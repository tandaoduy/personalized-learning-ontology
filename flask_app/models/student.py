"""
Mô hình dữ liệu hồ sơ sinh viên.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional


@dataclass
class CourseAttempt:
    """Lần đăng ký học một môn cụ thể của sinh viên (học lại hoặc cải thiện điểm)."""

    course_code: str
    course_name: str
    grade: float
    status: str  # "Đạt", "Chưa đạt", "Miễn", "Không tính điểm"
    semester_taken: int  # Học kỳ sinh viên học môn này (0 = không rõ)
    attempt_number: int  # Lần học thứ mấy (1, 2, 3, ...)
    grade_specified: bool = True  # False nếu điểm không được nhập cụ thể
    actual_term: int = 0  # Học kỳ thực tế trong năm học: 1, 2 hoặc 3 (học kỳ hè)
    academic_year: str = ""  # Năm học (ví dụ: "2023-2024")


@dataclass
class StudentProfile:
    """Hồ sơ sinh viên."""

    student_id: str
    name: str
    year_admitted: int
    major: str
    specialization: str = "Chưa chọn chuyên ngành"
    study_goal: str = "đúng hạn"  # 'đúng hạn', 'học vượt'
    current_semester: int = 1
    total_credits_accumulated: int = 0
    gpa_accumulated: float = 0.0
    academic_class: str = "Chưa xếp lớp"

    passed_courses: List[str] = field(default_factory=list)
    failed_courses: List[str] = field(default_factory=list)
    course_grades: Dict[str, float] = field(default_factory=dict)
    course_statuses: Dict[str, str] = field(default_factory=dict)
    course_grade_specified: Dict[str, bool] = field(default_factory=dict)
    course_attempts: List[CourseAttempt] = field(default_factory=list)

    def validate(self) -> List[str]:
        """Kiểm tra tính hợp lệ của hồ sơ."""
        errors = []

        if not self.student_id or not self.student_id.strip():
            errors.append("Mã sinh viên không được để trống")

        if not self.name or not self.name.strip():
            errors.append("Tên sinh viên không được để trống")

        if self.year_admitted < 2000 or self.year_admitted > 2030:
            errors.append("Năm vào học không hợp lệ (2000-2030)")

        if self.current_semester < 1 or self.current_semester > 8:
            errors.append("Học kỳ hiện tại phải từ 1-8")

        if self.total_credits_accumulated < 0 or self.total_credits_accumulated > 150:
            errors.append("Tín chỉ tích lũy không hợp lệ (0-150)")

        if not self.academic_class or not self.academic_class.strip():
            errors.append("Lớp hành chính không được để trống")

        if self.study_goal not in ['đúng hạn', 'học vượt']:
            errors.append("Mục tiêu học không hợp lệ")

        return errors

    def to_dict(self):
        """Chuyển thành dict để tuần tự hóa JSON."""
        return asdict(self)

    def next_semester(self) -> int:
        """Học kỳ sắp tới."""
        return self.current_semester + 1

    def next_semester_type(self) -> int:
        """Loại học kỳ sắp tới: 1 = lẻ, 2 = chẵn."""
        next_sem = self.next_semester()
        return 1 if next_sem % 2 != 0 else 2


@dataclass
class CourseRecord:
    """Ghi nhận kết quả học một môn."""

    code: str
    name: str
    credits: int
    grade: float
    status: str  # "Đạt" hoặc "Chưa đạt"
    semester_taken: int

    def is_passed(self) -> bool:
        return self.status == "Đạt"
