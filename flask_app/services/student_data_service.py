"""
Dịch vụ nạp và quản lý dữ liệu sinh viên từ JSON/CSV.
"""

import csv
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Set

from flask_app.models.student import CourseAttempt, StudentProfile

NON_ACCUMULATED_ENGLISH_COURSES = frozenset({'FLS310', 'FLS312', 'FLS313'})
NON_ACCUMULATED_FIXED_COURSES = frozenset({'SOT301'})


class StudentDataService:
    """Nạp, chuẩn hóa và lưu trữ hồ sơ sinh viên."""

    def __init__(self, json_path: str, csv_path: str):
        self.json_path = json_path
        self.csv_path = csv_path
        self._students_cache: Optional[List[StudentProfile]] = None
        self._last_mtime: float = 0.0
        self.logger = logging.getLogger(__name__)

    def get_all_students(self, force_reload: bool = False) -> List[StudentProfile]:
        """Trả về danh sách tất cả sinh viên."""
        if os.path.exists(self.json_path):
            try:
                mtime = os.path.getmtime(self.json_path)
                if mtime > self._last_mtime:
                    force_reload = True
                    self._last_mtime = mtime
            except Exception:
                pass

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
                self.logger.info("Đã tìm thấy sinh viên")
                return student
        self.logger.warning("Không tìm thấy sinh viên")
        return None

    def get_next_student_id(self, force_reload: bool = True) -> str:
        """Trả về mã sinh viên kế tiếp theo định dạng SV0001."""
        students = self.get_all_students(force_reload=force_reload)
        max_num = 0

        for student in students:
            raw = str(getattr(student, "student_id", "") or "").strip()
            match = re.search(r"(\d+)", raw)
            if not match:
                continue
            try:
                num = int(match.group(1))
            except ValueError:
                continue
            if num > max_num:
                max_num = num

        next_id = str(max_num + 1)
        self.logger.info("Đã tính mã sinh viên kế tiếp")
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

        self.logger.info("Đang tạo sinh viên")
        normalized_goal = self._normalize_study_goal(student_data.get("study_goal"))
        current_semester = self._safe_int(student_data.get("current_semester"), 1)
        specialization = str(student_data.get("specialization", "Chưa chọn chuyên ngành")).strip() or "Chưa chọn chuyên ngành"

        if current_semester < 4:
            if specialization != "Chưa chọn chuyên ngành":
                raise ValueError("Sinh viên từ học kỳ 1 đến 3 không được chọn chuyên ngành")
            specialization = "Chưa chọn chuyên ngành"
        else:
            if specialization != "Chưa chọn chuyên ngành":
                import unicodedata
                spec_nfc = unicodedata.normalize("NFC", specialization).strip().lower()
                normalized_options = [unicodedata.normalize("NFC", opt).strip().lower() for opt in specialization_options]
                if spec_nfc not in normalized_options:
                    raise ValueError("Chuyên ngành không hợp lệ")

        course_entries = student_data.get("courses", [])
        (
            passed_courses, failed_courses, course_grades,
            course_statuses, course_grade_specified,
            total_credits_accumulated, course_attempts,
        ) = self._process_course_entries(course_entries, course_catalog, current_semester)

        gpa_accumulated = self._calculate_gpa(course_grades, course_statuses, course_grade_specified, course_catalog)

        student = StudentProfile(
            student_id=student_id,
            name=str(student_data.get("name", "")).strip(),
            year_admitted=self._safe_int(student_data.get("year_admitted"), 2023),
            major=str(student_data.get("major", "Công Nghệ Thông Tin")).strip() or "Công Nghệ Thông Tin",
            specialization=specialization,
            study_goal=normalized_goal,
            current_semester=current_semester,
            total_credits_accumulated=total_credits_accumulated,
            gpa_accumulated=gpa_accumulated,
            academic_class=str(student_data.get("academic_class", "")).strip() or "Chưa xếp lớp",
            passed_courses=passed_courses,
            failed_courses=failed_courses,
            course_grades=course_grades,
            course_statuses=course_statuses,
            course_grade_specified=course_grade_specified,
            course_attempts=course_attempts,
        )

        errors = student.validate()
        if errors:
            raise ValueError("; ".join(errors))

        self._append_student_to_json(student, course_catalog)
        self._students_cache = None
        self.logger.info("Đã lưu sinh viên")
        return self.get_student(student.student_id) or student

    def update_student(
        self,
        student_id: str,
        student_data: Dict[str, Any],
        course_catalog: Dict[str, Dict[str, Any]],
        specialization_options: List[str],
    ) -> StudentProfile:
        """Cập nhật sinh viên đã có và lưu vào nguồn JSON."""
        normalized_id = self._normalize_student_id(student_id)
        existing_student = self.get_student(student_id)
        if not existing_student:
            raise ValueError(f"Không tìm thấy sinh viên {student_id} để cập nhật")

        self.logger.info("Đang cập nhật sinh viên")
        normalized_goal = self._normalize_study_goal(student_data.get("study_goal"))
        current_semester = self._safe_int(student_data.get("current_semester"), 1)
        specialization = str(student_data.get("specialization", "Chưa chọn chuyên ngành")).strip() or "Chưa chọn chuyên ngành"

        if current_semester < 4:
            if specialization != "Chưa chọn chuyên ngành":
                raise ValueError("Sinh viên từ học kỳ 1 đến 3 không được chọn chuyên ngành")
            specialization = "Chưa chọn chuyên ngành"
        else:
            if specialization != "Chưa chọn chuyên ngành":
                import unicodedata
                spec_nfc = unicodedata.normalize("NFC", specialization).strip().lower()
                normalized_options = [unicodedata.normalize("NFC", opt).strip().lower() for opt in specialization_options]
                if spec_nfc not in normalized_options:
                    raise ValueError("Chuyên ngành không hợp lệ")

        course_entries = student_data.get("courses", [])
        (
            passed_courses, failed_courses, course_grades,
            course_statuses, course_grade_specified,
            total_credits_accumulated, course_attempts,
        ) = self._process_course_entries(course_entries, course_catalog, current_semester)

        gpa_accumulated = self._calculate_gpa(course_grades, course_statuses, course_grade_specified, course_catalog)

        student = StudentProfile(
            # Keep original student ID, don't allow changing it
            student_id=existing_student.student_id,
            name=str(student_data.get("name", "")).strip(),
            year_admitted=self._safe_int(student_data.get("year_admitted"), 2023),
            major=str(student_data.get("major", "Công Nghệ Thông Tin")).strip() or "Công Nghệ Thông Tin",
            specialization=specialization,
            study_goal=normalized_goal,
            current_semester=current_semester,
            total_credits_accumulated=total_credits_accumulated,
            gpa_accumulated=gpa_accumulated,
            academic_class=str(student_data.get("academic_class", "")).strip() or "Chưa xếp lớp",
            passed_courses=passed_courses,
            failed_courses=failed_courses,
            course_grades=course_grades,
            course_statuses=course_statuses,
            course_grade_specified=course_grade_specified,
            course_attempts=course_attempts,
        )

        errors = student.validate()
        if errors:
            raise ValueError("; ".join(errors))

        self._update_student_in_json(student, course_catalog)
        self._students_cache = None
        self.logger.info("Đã cập nhật sinh viên")
        return self.get_student(student.student_id) or student

    def _process_course_entries(
        self,
        course_entries: List[Dict[str, Any]],
        course_catalog: Dict[str, Dict[str, Any]],
        default_semester: int = 1,
    ) -> tuple:
        """Xử lý danh sách môn học từ payload, hỗ trợ nhiều lần học (học lại / cải thiện điểm).

        Trả về:
            Tuple (passed_courses, failed_courses, course_grades, course_statuses,
                   course_grade_specified, total_credits_accumulated, course_attempts)
        """
        # Nhóm các entry theo mã môn học — giữ thứ tự xuất hiện
        entries_by_code: Dict[str, List[Dict[str, Any]]] = {}
        for entry in course_entries:
            code = str(entry.get("code", "")).strip().upper()
            if not code:
                continue
            if code not in entries_by_code:
                entries_by_code[code] = []
            entries_by_code[code].append(entry)

        passed_courses: List[str] = []
        failed_courses: List[str] = []
        course_grades: Dict[str, float] = {}
        course_statuses: Dict[str, str] = {}
        course_grade_specified: Dict[str, bool] = {}
        total_credits_accumulated = 0
        course_attempts: List[CourseAttempt] = []

        for code, entries in entries_by_code.items():
            course_info = course_catalog.get(code)
            if not course_info:
                raise ValueError(f"Môn học {code} không tồn tại trong ontology")

            course_credit = self._get_course_credit(course_info)
            course_name = str(course_info.get("name") or code)

            has_passed = False
            best_grade_for_gpa: Optional[float] = None
            best_specified = False
            latest_grade = 0.0
            latest_status = "Chưa đạt"
            latest_specified = True

            for fallback_attempt_num, entry in enumerate(entries, start=1):
                attempt_num = self._safe_int(
                    entry.get("attempt_number", entry.get("attemptNumber")),
                    fallback_attempt_num,
                )
                status = str(entry.get("status", "")).strip()
                specified = bool(entry.get("grade_specified", entry.get("gradeSpecified", True)))
                semester_taken = self._safe_int(
                    entry.get("semester_taken", entry.get("semesterTaken")), default_semester
                )
                actual_term = self._safe_int(
                    entry.get("actual_term", entry.get("actualTerm")),
                    1 if semester_taken % 2 else 2,
                )

                if status in ("Miễn", "Không tính điểm"):
                    grade = 0.0
                    specified = False
                    final_status = status
                    is_pass = True
                else:
                    try:
                        grade = float(entry.get("grade", 0))
                    except (TypeError, ValueError) as exc:
                        raise ValueError(
                            f"Điểm của môn {code} (lần {attempt_num}) không hợp lệ"
                        ) from exc
                    if grade < 0 or grade > 10:
                        raise ValueError(
                            f"Điểm của môn {code} (lần {attempt_num}) phải trong khoảng 0-10"
                        )
                    is_pass = grade >= 5
                    # Trạng thái đạt/chưa đạt luôn nhất quán với điểm số.
                    final_status = "Đạt" if is_pass else "Chưa đạt"

                if is_pass:
                    has_passed = True
                    if specified and (best_grade_for_gpa is None or grade > best_grade_for_gpa):
                        best_grade_for_gpa = grade
                        best_specified = True

                latest_grade = grade
                latest_status = final_status
                latest_specified = specified

                course_attempts.append(CourseAttempt(
                    course_code=code,
                    course_name=course_name,
                    grade=round(grade, 2),
                    status=final_status,
                    semester_taken=semester_taken,
                    attempt_number=attempt_num,
                    grade_specified=specified,
                    actual_term=actual_term,
                    academic_year=str(entry.get("academic_year", entry.get("academicYear", ""))).strip(),
                ))

            # Xác định tình trạng cuối cùng của môn học (dựa trên tất cả các lần học)
            if has_passed:
                passed_courses.append(code)
                gpa_grade = best_grade_for_gpa if best_grade_for_gpa is not None else latest_grade
                course_grades[code] = round(gpa_grade, 2)
                course_statuses[code] = latest_status if latest_status in ("Đạt", "Miễn", "Không tính điểm") else "Đạt"
                course_grade_specified[code] = best_specified
                if not self._is_non_accumulated_course(code, course_catalog):
                    total_credits_accumulated += course_credit
            else:
                failed_courses.append(code)
                course_grades[code] = round(latest_grade, 2)
                course_statuses[code] = latest_status
                course_grade_specified[code] = latest_specified

        return (
            passed_courses, failed_courses, course_grades,
            course_statuses, course_grade_specified,
            total_credits_accumulated, course_attempts,
        )

    def update_student_name(self, student_id: str, new_name: str) -> None:
        """Cập nhật tên sinh viên trực tiếp vào nguồn JSON."""
        normalized_id = self._normalize_student_id(student_id)
        existing_data: List[Dict[str, Any]] = []

        if os.path.exists(self.json_path):
            with open(self.json_path, "r", encoding="utf-8") as file:
                loaded = json.load(file)
                if isinstance(loaded, list):
                    existing_data = loaded

        updated = False
        for item in existing_data:
            item_id = item.get("student_id", item.get("mã sinh viên", item.get("ma sinh vien", item.get("id"))))
            if item_id and self._normalize_student_id(str(item_id)) == normalized_id:
                item["name"] = new_name
                if "tên sinh viên" in item:
                    item["tên sinh viên"] = new_name
                updated = True
                break

        if updated:
            with open(self.json_path, "w", encoding="utf-8") as file:
                json.dump(existing_data, file, ensure_ascii=False, indent=4)
            self._students_cache = None
            self.logger.info("Đã cập nhật tên sinh viên")

    def delete_student(self, student_id: str) -> None:
        """Xóa sinh viên theo mã."""
        normalized_id = self._normalize_student_id(student_id)
        existing_data: List[Dict[str, Any]] = []

        if os.path.exists(self.json_path):
            with open(self.json_path, "r", encoding="utf-8") as file:
                loaded = json.load(file)
                if isinstance(loaded, list):
                    existing_data = loaded

        filtered_data = []
        deleted = False
        for item in existing_data:
            item_id = item.get("student_id", item.get("mã sinh viên", item.get("ma sinh vien", item.get("id"))))
            if item_id and self._normalize_student_id(str(item_id)) == normalized_id:
                deleted = True
                continue
            filtered_data.append(item)

        if not deleted:
            raise ValueError(f"Không tìm thấy sinh viên {student_id} để xóa")

        with open(self.json_path, "w", encoding="utf-8") as file:
            json.dump(filtered_data, file, ensure_ascii=False, indent=4)

        self._students_cache = None
        self.logger.info("Đã xóa sinh viên và làm mới cache")

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

    def _update_student_in_json(
        self,
        student: StudentProfile,
        course_catalog: Dict[str, Dict[str, Any]],
    ) -> None:
        """Cập nhật bản ghi sinh viên trong file JSON nguồn."""
        existing_data: List[Dict[str, Any]] = []

        if os.path.exists(self.json_path):
            with open(self.json_path, "r", encoding="utf-8") as file:
                loaded = json.load(file)
                if isinstance(loaded, list):
                    existing_data = loaded

        normalized_id = self._normalize_student_id(student.student_id)
        updated_data = []
        updated = False
        
        for item in existing_data:
            item_id = item.get("student_id", item.get("mã sinh viên", item.get("ma sinh vien", item.get("id"))))
            if item_id and self._normalize_student_id(str(item_id)) == normalized_id:
                updated_data.append(self._build_student_json_record(student, course_catalog))
                updated = True
            else:
                updated_data.append(item)

        if not updated:
            raise ValueError(f"Không tìm thấy sinh viên {student.student_id} trong cơ sở dữ liệu để cập nhật.")

        with open(self.json_path, "w", encoding="utf-8") as file:
            json.dump(updated_data, file, ensure_ascii=False, indent=4)

    def _build_student_json_record(
        self,
        student: StudentProfile,
        course_catalog: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Chuyển `StudentProfile` về đúng cấu trúc JSON gốc của dự án sử dụng các trường tiếng Anh."""
        passed_entries: Dict[str, str] = {}
        grade_entries: List[Dict[str, Any]] = []
        failed_entries: List[Dict[str, str]] = []

        for code, grade in sorted(student.course_grades.items()):
            course_info = course_catalog.get(code, {})
            course_name = course_info.get("name") or code
            
            status = getattr(student, "course_statuses", {}).get(code)
            if not status:
                status = "Đạt" if grade >= 5 else "Chưa đạt"

            specified = student.course_grade_specified.get(code, True) if hasattr(student, "course_grade_specified") else True
            
            if status in ("Đạt", "Miễn", "Không tính điểm"):
                passed_entries[code] = course_name
            elif status == "Chưa đạt":
                failed_entries.append({
                    "course_code": code,
                    "course_name": course_name,
                })

            grade_entries.append({
                "course_code": code,
                "course_name": course_name,
                "grade": grade,
                "status": status,
                "grade_specified": specified,
            })

        return {
            "student_id": student.student_id,
            "name": student.name,
            "year_admitted": student.year_admitted,
            "major": student.major,
            "specialization": student.specialization,
            "study_goal": student.study_goal,
            "total_credits_accumulated": student.total_credits_accumulated,
            "gpa_accumulated": student.gpa_accumulated,
            "academic_class": student.academic_class,
            "current_semester": student.current_semester,
            "next_semester": student.next_semester(),
            "passed_courses": passed_entries,
            "course_grades": grade_entries,
            "failed_courses": failed_entries,
            "course_attempts": [
                {
                    "course_code": a.course_code,
                    "course_name": a.course_name,
                    "grade": a.grade,
                    "status": a.status,
                    "semester_taken": a.semester_taken,
                    "actual_term": getattr(a, "actual_term", 0) or a.semester_taken,
                    "academic_year": getattr(a, "academic_year", "") or self._academic_year_for_semester(
                        student.year_admitted,
                        a.semester_taken,
                    ),
                    "attempt_number": a.attempt_number,
                    "grade_specified": a.grade_specified,
                }
                for a in (student.course_attempts or [])
            ],
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
        import re
        student_id = re.sub(r'(?i)^sv\s*', '', str(student_id).strip())

        name = str(get_val(["name", "tên sinh viên", "ten sinh vien"]) or "").strip()
        year_admitted = self._safe_int(get_val(["year_admitted", "năm vào học", "nam vao hoc"]), 2023)
        major = str(get_val(["major", "ngành", "nganh"]) or "Công Nghệ Thông Tin").strip()
        specialization = str(get_val(["specialization", "chuyên ngành", "chuyen nganh"]) or "Chưa chọn chuyên ngành").strip()
        study_goal = self._normalize_study_goal(get_val(["study_goal", "mục tiêu học tập", "muc tieu hoc tap"]))
        current_semester = self._safe_int(get_val(["current_semester", "học kỳ hiện tại", "hoc ky hien tai"]), 1)
        total_credits = self._safe_int(get_val(["total_credits_accumulated", "số tín chỉ đã tích lũy", "so tin chi da tich luy"]), 0)
        gpa_accumulated = self._safe_float(get_val(["gpa_accumulated", "điểm trung bình tích lũy", "gpa"]), 0.0)

        academic_class = str(get_val(["academic_class", "lớp", "lop", "lớp hành chính", "lop hanh chinh"]) or "").strip()
        if not academic_class:
            if year_admitted == 2023:
                academic_class = "65.CNTT-1"
            elif year_admitted == 2024:
                academic_class = "66.CNTT-1"
            elif year_admitted == 2025:
                academic_class = "67.CNTT-1"
            else:
                academic_class = "65.CNTT-1"

        # Đọc course_attempts nếu có; nếu không, dựng từ course_grades (tương thích ngược)
        attempts_raw = get_val(["course_attempts"]) or []
        course_attempts: List[CourseAttempt] = []
        grades_raw = get_val(["course_grades", "điểm từng môn", "diem tung mon", []])
        
        if isinstance(attempts_raw, list) and attempts_raw:
            for item in attempts_raw:
                if not isinstance(item, dict):
                    continue
                a_code = str(item.get("course_code", "")).strip().upper()
                if not a_code:
                    continue
                try:
                    course_attempts.append(CourseAttempt(
                        course_code=a_code,
                        course_name=str(item.get("course_name", a_code)),
                        grade=float(item.get("grade", 0)),
                        status=str(item.get("status", "")),
                        semester_taken=int(item.get("semester_taken", 0)),
                        attempt_number=int(item.get("attempt_number", 1)),
                        grade_specified=bool(item.get("grade_specified", True)),
                        actual_term=int(item.get("actual_term", item.get("semester_taken", 0))),
                        academic_year=str(item.get("academic_year", "")),
                    ))
                except Exception:
                    pass
        elif isinstance(grades_raw, list):
            # Tương thích ngược: dựng từ dữ liệu cũ (mỗi entry là lần học đầu tiên)
            for item in grades_raw:
                if not isinstance(item, dict):
                    continue
                a_code = str(item.get("course_code", item.get("mã môn học",
                    item.get(self._legacy_mojibake("mã môn học"), "")))).strip().upper()
                if not a_code:
                    continue
                try:
                    g = float(item.get("grade", item.get("điểm",
                        item.get(self._legacy_mojibake("điểm"), 0))))
                except Exception:
                    g = 0.0
                s = str(item.get("status", item.get("trạng thái",
                    item.get(self._legacy_mojibake("trạng thái"), "")))).strip()
                if not s:
                    s = "Đạt" if g >= 5 else "Chưa đạt"
                sp = bool(item.get("grade_specified", item.get("gradeSpecified", True)))
                course_attempts.append(CourseAttempt(
                    course_code=a_code,
                    course_name=str(item.get("course_name", a_code)),
                    grade=g,
                    status=s,
                    semester_taken=0,  # không rõ từ dữ liệu cũ
                    attempt_number=1,
                    grade_specified=sp,
                    actual_term=0,
                    academic_year="",
                ))

        # Tái tạo passed_courses, failed_courses, grades, statuses từ course_attempts
        passed_courses = set()
        failed_courses = set()
        course_grades = {}
        course_statuses = {}
        course_grade_specified = {}
        
        # Nhóm attempts theo mã
        attempts_by_code = {}
        for a in course_attempts:
            if a.course_code not in attempts_by_code:
                attempts_by_code[a.course_code] = []
            attempts_by_code[a.course_code].append(a)
            
        for code, atts in attempts_by_code.items():
            has_passed = False
            best_grade = None
            best_specified = False
            latest_grade = 0.0
            latest_status = "Chưa đạt"
            latest_specified = True
            
            for a in sorted(atts, key=lambda x: x.attempt_number):
                is_pass = a.status in ("Đạt", "Miễn", "Không tính điểm")
                if is_pass:
                    has_passed = True
                    if a.grade_specified and (best_grade is None or a.grade > best_grade):
                        best_grade = a.grade
                        best_specified = True
                latest_grade = a.grade
                latest_status = a.status
                latest_specified = a.grade_specified
                
            if has_passed:
                passed_courses.add(code)
                course_grades[code] = best_grade if best_grade is not None else latest_grade
                # Trạng thái của môn tính là trạng thái của lần học đạt cuối cùng hoặc "Đạt"
                course_statuses[code] = latest_status if latest_status in ("Đạt", "Miễn", "Không tính điểm") else "Đạt"
                course_grade_specified[code] = best_specified
            else:
                failed_courses.add(code)
                course_grades[code] = latest_grade
                course_statuses[code] = latest_status
                course_grade_specified[code] = latest_specified

        return StudentProfile(
            student_id=student_id,
            name=name,
            year_admitted=year_admitted,
            major=major,
            specialization=specialization,
            study_goal=study_goal,
            current_semester=current_semester,
            total_credits_accumulated=total_credits,
            gpa_accumulated=gpa_accumulated,
            academic_class=academic_class,
            passed_courses=list(passed_courses),
            failed_courses=list(failed_courses),
            course_grades=course_grades,
            course_statuses=course_statuses,
            course_grade_specified=course_grade_specified,
            course_attempts=course_attempts,
        )

    @staticmethod
    def _academic_year_for_semester(year_admitted: int, semester_taken: int) -> str:
        """Tính năm học từ học kỳ thứ tự toàn khóa (mỗi năm có 3 kỳ)."""
        try:
            year_admitted = int(year_admitted)
            semester_taken = int(semester_taken)
        except (TypeError, ValueError):
            return ""
        if year_admitted <= 0 or semester_taken <= 0:
            return ""
        start_year = year_admitted + (semester_taken - 1) // 3
        return f"{start_year}-{start_year + 1}"

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
    def _safe_float(value: Any, default: float) -> float:
        """Chuyển đổi sang số thực an toàn."""
        try:
            if isinstance(value, (int, float)):
                return float(value)
            string_value = str(value).strip()
            if not string_value:
                return default
            return float(string_value)
        except Exception:
            return default

    def _calculate_gpa(
        self,
        course_grades: Dict[str, float],
        course_statuses: Dict[str, str],
        course_grade_specified: Dict[str, bool],
        course_catalog: Dict[str, Dict[str, Any]],
    ) -> float:
        """Tính điểm trung bình tích lũy (GPA) hệ 10."""
        total_grade_points = 0.0
        total_credits = 0
        
        for code, grade in course_grades.items():
            if self._is_non_accumulated_course(code, course_catalog):
                continue

            status = course_statuses.get(code)
            if status != "Đạt" or not course_grade_specified.get(code, True):
                continue
            
            course_info = course_catalog.get(code, {})
            credits = self._get_course_credit(course_info)
            if credits > 0:
                total_grade_points += grade * credits
                total_credits += credits
                
        if total_credits > 0:
            return round(total_grade_points / total_credits, 2)
        return 0.0

    @staticmethod
    def _is_non_accumulated_course(code: str, course_catalog: Optional[Dict[str, Dict[str, Any]]] = None) -> bool:
        """Các học phần đăng ký nhưng không tính vào tín chỉ tích lũy và GPA."""
        normalized_code = str(code or "").strip().upper()
        if normalized_code in NON_ACCUMULATED_ENGLISH_COURSES or normalized_code in NON_ACCUMULATED_FIXED_COURSES:
            return True
        info = (course_catalog or {}).get(normalized_code, {})
        return bool(info.get("is_physical_education_course"))

    @classmethod
    def _get_course_credit(cls, course_info: Dict[str, Any]) -> int:
        """Đọc tín chỉ từ catalog, tương thích cả key `credit` và `credits`."""
        return cls._safe_int(course_info.get("credits", course_info.get("credit")), 0)

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
            "học vượt": "học vượt",
            "hoc vuot": "học vượt"
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
            "học vượt": "Học vượt",
        }
        return mapping.get(value, "Đúng hạn")
