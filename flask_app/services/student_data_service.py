"""
Dịch vụ nạp và quản lý dữ liệu sinh viên từ JSON/CSV.
"""

import csv
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Set

from flask_app.models.student import StudentProfile


class StudentDataService:
    """Nạp, chuẩn hóa và lưu trữ hồ sơ sinh viên."""

    def __init__(self, json_path: str, csv_path: str):
        self.json_path = json_path
        self.csv_path = csv_path
        self._students_cache: Optional[List[StudentProfile]] = None
        self.logger = logging.getLogger(__name__)

    def get_all_students(self, force_reload: bool = False) -> List[StudentProfile]:
        """Trả về danh sách tất cả sinh viên."""
        if self._students_cache and not force_reload:
            return self._students_cache

        self.logger.info("Đang nạp dữ liệu sinh viên (force_reload=%s)", force_reload)
        students: List[StudentProfile] = []

        if os.path.exists(self.json_path):
            try:
                students = self._load_from_json()
                self.logger.info("Đã nạp %s sinh viên từ JSON", len(students))
            except Exception:
                self.logger.exception("Lỗi khi nạp dữ liệu sinh viên từ JSON")

        if not students and os.path.exists(self.csv_path):
            try:
                students = self._load_from_csv()
                self.logger.info("Đã nạp %s sinh viên từ CSV dự phòng", len(students))
            except Exception:
                self.logger.exception("Lỗi khi nạp dữ liệu sinh viên từ CSV")

        self._students_cache = students
        self.logger.info("Đã làm mới bộ nhớ đệm sinh viên với %s bản ghi", len(students))
        return students

    def get_student(self, student_id: str) -> Optional[StudentProfile]:
        """Trả về hồ sơ của một sinh viên theo mã."""
        normalized_id = self._normalize_student_id(student_id)
        for student in self.get_all_students():
            if self._normalize_student_id(student.student_id) == normalized_id:
                self.logger.info("Đã tìm thấy sinh viên: %s", student_id)
                return student
        self.logger.warning("Không tìm thấy sinh viên: %s", student_id)
        return None

    def get_next_student_id(self, force_reload: bool = True) -> str:
        """Trả về mã sinh viên kế tiếp theo định dạng SV0001."""
        students = self.get_all_students(force_reload=force_reload)
        max_num = 0

        for student in students:
            raw = str(getattr(student, "student_id", "") or "").strip()
            match = re.match(r"^\s*SV\s*(\d+)\s*$", raw, flags=re.IGNORECASE)
            if not match:
                continue
            try:
                num = int(match.group(1))
            except ValueError:
                continue
            if num > max_num:
                max_num = num

        next_id = f"SV{max_num + 1:04d}"
        self.logger.info("Đã tính mã sinh viên kế tiếp: %s", next_id)
        return next_id

    def create_student(
        self,
        student_data: Dict[str, Any],
        course_catalog: Dict[str, Dict[str, Any]],
        specialization_options: List[str],
    ) -> StudentProfile:
        """Tạo sinh viên mới và lưu vào nguồn JSON."""
        student_id = str(student_data.get("student_id", "")).strip().upper()
        if not student_id:
            raise ValueError("Mã sinh viên không được để trống")

        if self.get_student(student_id):
            raise ValueError(f"Sinh viên {student_id} đã tồn tại")

        self.logger.info("Đang tạo sinh viên: %s", student_id)
        normalized_goal = self._normalize_study_goal(student_data.get("study_goal"))
        current_semester = self._safe_int(student_data.get("current_semester"), 1)
        specialization = str(student_data.get("specialization", "Chưa chọn chuyên ngành")).strip() or "Chưa chọn chuyên ngành"

        if current_semester < 4:
            if specialization != "Chưa chọn chuyên ngành":
                raise ValueError("Sinh viên từ học kỳ 1 đến 3 không được chọn chuyên ngành")
            specialization = "Chưa chọn chuyên ngành"
        else:
            if specialization != "Chưa chọn chuyên ngành" and specialization not in specialization_options:
                raise ValueError("Chuyên ngành không hợp lệ")

        course_entries = student_data.get("courses", [])
        passed_courses: List[str] = []
        failed_courses: List[str] = []
        course_grades: Dict[str, float] = {}
        total_credits_accumulated = 0

        for entry in course_entries:
            code = str(entry.get("code", "")).strip().upper()
            if not code:
                continue

            if code in course_grades:
                raise ValueError(f"Môn học {code} đang bị trùng")

            course_info = course_catalog.get(code)
            if not course_info:
                raise ValueError(f"Môn học {code} không tồn tại trong ontology")

            try:
                grade = float(entry.get("grade", 0))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Điểm của môn {code} không hợp lệ") from exc

            if grade < 0 or grade > 10:
                raise ValueError(f"Điểm của môn {code} phải trong khoảng 0-10")

            course_grades[code] = round(grade, 2)
            course_credit = self._safe_int(course_info.get("credits"), 0)

            if grade >= 5:
                passed_courses.append(code)
                total_credits_accumulated += course_credit
            else:
                failed_courses.append(code)

        student = StudentProfile(
            student_id=student_id,
            name=str(student_data.get("name", "")).strip(),
            year_admitted=self._safe_int(student_data.get("year_admitted"), 2023),
            major=str(student_data.get("major", "Công Nghệ Thông Tin")).strip() or "Công Nghệ Thông Tin",
            specialization=specialization,
            study_goal=normalized_goal,
            current_semester=current_semester,
            total_credits_accumulated=total_credits_accumulated,
            max_credits_to_register=27,
            passed_courses=passed_courses,
            failed_courses=failed_courses,
            course_grades=course_grades,
        )

        errors = student.validate()
        if errors:
            raise ValueError("; ".join(errors))

        self._append_student_to_json(student, course_catalog)
        self._students_cache = None
        self.logger.info("Đã lưu sinh viên: %s", student.student_id)
        return self.get_student(student.student_id) or student

    def _load_from_json(self) -> List[StudentProfile]:
        """Nạp dữ liệu sinh viên từ JSON."""
        with open(self.json_path, "r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, list):
            raise ValueError("JSON phải là một danh sách")

        students: List[StudentProfile] = []
        for item in data:
            try:
                student = self._parse_student_dict(item)
                if student:
                    students.append(student)
            except Exception as exc:
                self.logger.warning(
                    "Không thể phân tích sinh viên %s: %s",
                    item.get("mã sinh viên", item.get("ma sinh vien", "?")) if isinstance(item, dict) else "?",
                    exc,
                )
        return students

    def _load_from_csv(self) -> List[StudentProfile]:
        """Nạp dữ liệu sinh viên từ CSV."""
        students: List[StudentProfile] = []
        with open(self.csv_path, "r", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                try:
                    student = self._parse_student_dict(row)
                    if student:
                        students.append(student)
                except Exception as exc:
                    self.logger.warning("Không thể phân tích một dòng CSV: %s", exc)
        return students

    def _append_student_to_json(
        self,
        student: StudentProfile,
        course_catalog: Dict[str, Dict[str, Any]],
    ) -> None:
        """Thêm bản ghi sinh viên vào file JSON nguồn."""
        existing_data: List[Dict[str, Any]] = []

        if os.path.exists(self.json_path):
            with open(self.json_path, "r", encoding="utf-8") as file:
                loaded = json.load(file)
                if isinstance(loaded, list):
                    existing_data = loaded

        existing_data.append(self._build_student_json_record(student, course_catalog))

        with open(self.json_path, "w", encoding="utf-8") as file:
            json.dump(existing_data, file, ensure_ascii=False, indent=4)

    def _build_student_json_record(
        self,
        student: StudentProfile,
        course_catalog: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Chuyển `StudentProfile` về đúng cấu trúc JSON gốc của dự án sử dụng các trường tiếng Anh."""
        studied_courses: Dict[str, str] = {}
        grade_entries: List[Dict[str, Any]] = []
        failed_entries: List[Dict[str, str]] = []

        for code, grade in sorted(student.course_grades.items()):
            course_info = course_catalog.get(code, {})
            course_name = course_info.get("name") or code
            is_passed = grade >= 5

            studied_courses[code] = course_name
            grade_entries.append({
                "course_code": code,
                "course_name": course_name,
                "grade": grade,
                "status": "Đạt" if is_passed else "Chưa đạt",
            })

            if not is_passed:
                failed_entries.append({
                    "course_code": code,
                    "course_name": course_name,
                })

        return {
            "student_id": student.student_id,
            "name": student.name,
            "year_admitted": student.year_admitted,
            "major": student.major,
            "specialization": student.specialization,
            "study_goal": student.study_goal,
            "total_credits_accumulated": student.total_credits_accumulated,
            "max_credits_to_register": 27,
            "current_semester": student.current_semester,
            "next_semester": student.next_semester(),
            "passed_courses": studied_courses,
            "course_grades": grade_entries,
            "failed_courses": failed_entries,
        }

    def _parse_student_dict(self, data: Dict[str, Any]) -> Optional[StudentProfile]:
        """Phân tích một từ điển thô thành `StudentProfile`."""
        def get_val(keys):
            for k in keys:
                if k in data:
                    return data[k]
                try:
                    mojibake_k = k.encode("utf-8").decode("latin1")
                    if mojibake_k in data:
                        return data[mojibake_k]
                except Exception:
                    pass
            return None

        student_id = get_val(["student_id", "mã sinh viên", "mã sinh vien", "ma sinh vien", "id"])
        if not student_id:
            return None
        student_id = str(student_id).strip()

        name = str(get_val(["name", "tên sinh viên", "ten sinh vien"]) or "").strip()
        year_admitted = self._safe_int(get_val(["year_admitted", "năm vào học", "nam vao hoc"]), 2023)
        major = str(get_val(["major", "ngành", "nganh"]) or "Công Nghệ Thông Tin").strip()
        specialization = str(get_val(["specialization", "chuyên ngành", "chuyen nganh"]) or "Chưa chọn chuyên ngành").strip()
        study_goal = self._normalize_study_goal(get_val(["study_goal", "mục tiêu học tập", "muc tieu hoc tap"]))
        current_semester = self._safe_int(get_val(["current_semester", "học kỳ hiện tại", "hoc ky hien tai"]), 1)
        total_credits = self._safe_int(get_val(["total_credits_accumulated", "số tín chỉ đã tích lũy", "so tin chi da tich luy"]), 0)
        max_credits = self._safe_int(get_val(["max_credits_to_register", "số tín chỉ đăng ký tối đa", "so tin chi dang ky toi da"]), 27)

        passed_courses_raw = get_val(["passed_courses", "danh sách môn đã học", "danh sach mon da hoc", []])
        passed_courses = self._parse_course_list(passed_courses_raw)

        failed_courses_raw = get_val(["failed_courses", "danh sách môn chưa đạt", "danh sach mon chua dat", []])
        failed_courses = self._parse_course_list(failed_courses_raw)

        grades_raw = get_val(["course_grades", "điểm từng môn", "diem tung mon", []])
        grades = self._parse_grades(grades_raw)
        
        passed_courses -= failed_courses

        return StudentProfile(
            student_id=student_id,
            name=name,
            year_admitted=year_admitted,
            major=major,
            specialization=specialization,
            study_goal=study_goal,
            current_semester=current_semester,
            total_credits_accumulated=total_credits,
            max_credits_to_register=max_credits,
            passed_courses=list(passed_courses),
            failed_courses=list(failed_courses),
            course_grades=grades,
        )

    def _parse_course_list(self, data: Any) -> Set[str]:
        """Phân tích danh sách mã môn học từ dạng từ điển hoặc danh sách."""
        courses: Set[str] = set()

        if isinstance(data, dict):
            for code in data.keys():
                if code and str(code).strip():
                    courses.add(str(code).strip().upper())
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    code = item.get("course_code", item.get("mã môn học", item.get(self._legacy_mojibake("mã môn học"), "")))
                elif isinstance(item, str):
                    code = item
                else:
                    continue

                if code and str(code).strip():
                    courses.add(str(code).strip().upper())

        return courses

    def _parse_grades(self, data: Any) -> Dict[str, float]:
        """Phân tích danh sách điểm."""
        grades: Dict[str, float] = {}
        if not isinstance(data, list):
            return grades

        for item in data:
            if not isinstance(item, dict):
                continue

            code = item.get("course_code", item.get("mã môn học", item.get(self._legacy_mojibake("mã môn học"), "")))
            grade = item.get("grade", item.get("điểm", item.get(self._legacy_mojibake("điểm"), 0)))
            if code and str(code).strip():
                try:
                    grades[str(code).strip().upper()] = float(grade)
                except (ValueError, TypeError):
                    pass

        return grades

    @staticmethod
    def _safe_int(value: Any, default: int) -> int:
        """Chuyển đổi sang số nguyên an toàn."""
        try:
            if isinstance(value, int):
                return value
            if isinstance(value, float):
                return int(value)

            string_value = str(value).strip()
            if not string_value:
                return default
            if "." in string_value:
                return int(float(string_value))
            return int(string_value)
        except Exception:
            return default

    @staticmethod
    def _normalize_student_id(student_id: str) -> str:
        """Chuẩn hóa mã sinh viên để so sánh."""
        return str(student_id or "").strip().lower().replace("sv", "")

    @staticmethod
    def _normalize_study_goal(value: Any) -> str:
        """Chuẩn hóa mục tiêu học tập."""
        goal = str(value or "").strip().lower()
        normalized = {
            "đúng hạn": "đúng hạn",
            "dung han": "đúng hạn",
            "giảm tải": "giảm tải",
            "giam tai": "giảm tải",
            "học vượt": "học vượt",
            "hoc vuot": "học vượt",
        }
        normalized.update({StudentDataService._legacy_mojibake(k): v for k, v in normalized.items()})
        return normalized.get(goal, "đúng hạn")

    @staticmethod
    def _legacy_mojibake(text: str) -> str:
        """Sinh khóa tương thích với dữ liệu cũ bị lệch mã hóa."""
        try:
            return text.encode("utf-8").decode("latin1")
        except Exception:
            return text

    @staticmethod
    def _display_study_goal(value: str) -> str:
        """Trả về chuỗi hiển thị đẹp cho mục tiêu học tập."""
        mapping = {
            "đúng hạn": "Đúng hạn",
            "giảm tải": "Giảm tải",
            "học vượt": "Học vượt",
        }
        return mapping.get(value, "Đúng hạn")
