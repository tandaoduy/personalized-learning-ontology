"""Extracted existing behavior; operates on RecommendationEngine shared context."""

from typing import Dict, Any, List, Set, Optional, Tuple
from backend.app.models.student import StudentProfile
from backend.app.models.recommendation import RecommendedCourse, ExcludedCourse
from .constants import (
    ELECTIVE_QUOTA_KEYS,
    NATIONAL_DEFENSE_COURSES,
    EQUIVALENT_COURSES,
    NOISE_COURSES,
)


class EligibilityMixin:
    """Internal extraction boundary, not an independent Agent capability."""

    def get_eligible_courses(
        self,
        student: StudentProfile,
        priority_mode: str = "standard",
    ) -> Tuple[List[RecommendedCourse], Set[str], Dict[str, int], str]:
        """Trả về các ứng viên hợp lệ qua giao diện công khai của engine.

        Benchmark và kiểm thử tích hợp dùng phương thức này thay vì gọi trực
        tiếp các bước lọc nội bộ.
        """
        current_sem = max(1, student.current_semester)
        next_sem = current_sem + 1
        sem_type = 1 if next_sem % 2 != 0 else 2
        study_goal = (student.study_goal or "đúng hạn").strip().lower()
        if study_goal not in {"đúng hạn", "học vượt"}:
            study_goal = "đúng hạn"

        passed_courses, failed_courses = self._normalize_student_data(student)
        for code, info in self.course_data.items():
            info["elective_category"] = self._categorize_elective(code, info)
        completed_elective_counts = self._count_completed_electives(passed_courses)
        remaining_elective_counts = {
            key: max(0, self.elective_quotas.get(key, 0) - completed_elective_counts.get(key, 0))
            for key in ELECTIVE_QUOTA_KEYS
        }
        valid_courses, _ = self._get_valid_courses(
            student,
            passed_courses,
            failed_courses,
            current_sem,
            next_sem,
            sem_type,
            study_goal,
            remaining_elective_counts,
            priority_mode,
        )
        eligible_courses, _ = self._filter_by_elective_quota(
            valid_courses,
            remaining_elective_counts,
        )
        return eligible_courses, passed_courses, completed_elective_counts, study_goal

    def _normalize_student_data(self, student: StudentProfile) -> Tuple[Set[str], Set[str]]:
        """Chuẩn hóa dữ liệu sinh viên"""
        passed_courses = set(self._normalize_course_code(c) for c in student.passed_courses)
        failed_courses = set(self._normalize_course_code(c) for c in student.failed_courses)

        # Chuyển mã phụ sang mã chính (môn tương đương)
        passed_courses = {EQUIVALENT_COURSES.get(c, c) for c in passed_courses}
        failed_courses = {EQUIVALENT_COURSES.get(c, c) for c in failed_courses}

        # Lọc không tồn tại
        passed_courses = {c for c in passed_courses if c in self.course_data}
        failed_courses = {c for c in failed_courses if c in self.course_data}

        # Tránh trùng lặp
        passed_courses -= failed_courses

        return passed_courses, failed_courses

    def _get_valid_courses(self,
                          student: StudentProfile,
                          passed_courses: Set[str],
                          failed_courses: Set[str],
                          current_sem: int,
                          next_sem: int,
                          sem_type: int,
                          study_goal: str,
                          remaining_elective_counts: Optional[Dict[str, int]] = None,
                          priority_mode: str = "standard") -> Tuple[List[RecommendedCourse], List[ExcludedCourse]]:
        """Lọc môn hợp lệ theo 8 điều kiện"""
        valid_courses = []
        excluded_courses = []
        internship_codes = {'INT6900', 'SOT348'}
        semester_8_only_codes = {'INT6901', 'INT6902'}
        student_spec = student.specialization.strip() if student.specialization else ""
        normalized_student_spec = self._normalize_text(student_spec) if student_spec else ""
        has_selected_specialization = bool(student_spec) and normalized_student_spec != "chua chon chuyen nganh"
        student_major = student.major.strip() if getattr(student, 'major', None) else ""
        normalized_student_major = self._normalize_text(student_major) if student_major else ""

        # Khởi tạo lại từ bản cấu hình hiện hành trước khi lọc môn.
        valid_courses = []
        excluded_courses = []
        internship_codes = {'INT6900', 'SOT348'}
        semester_8_only_codes = {'INT6901', 'INT6902'}
        student_spec = student.specialization.strip() if student.specialization else ""
        normalized_student_spec = self._normalize_text(student_spec) if student_spec else ""
        has_selected_specialization = bool(student_spec) and normalized_student_spec != "chua chon chuyen nganh"
        student_major = student.major.strip() if getattr(student, 'major', None) else ""
        normalized_student_major = self._normalize_text(student_major) if student_major else ""

        def exclude_course(code_: str, info_: Dict[str, Any], failed_rules: List[str], reasons: List[str]):
            is_specialization_course = bool(info_.get('specializations'))
            excluded_courses.append(ExcludedCourse(
                code=code_,
                name=info_.get('name', code_),
                credits=info_.get('credit', 0),
                recommended_semester=info_.get('recommended_sem', 0),
                reasons=reasons,
                failed_rules=failed_rules,
                stage="eligibility",
                is_specialization_course=is_specialization_course,
            ))

        for code, info in self.course_data.items():
            # 0. Bỏ qua môn gây nhiễu (cơ khí/ô tô/hàng hải gắn nhầm vào CNTT trong RDF)
            #    Các môn này vẫn hợp lệ khi sinh viên nhập hồ sơ, chỉ không gợi ý.
            if code in NOISE_COURSES:
                exclude_course(
                    code,
                    info,
                    ["noise_course"],
                    ["môn nhiễu/không thuộc phạm vi gợi ý của chương trình CNTT"],
                )
                continue

            # 1. Chưa đạt
            if code in passed_courses:
                exclude_course(
                    code,
                    info,
                    ["already_passed"],
                    ["sinh viên đã hoàn thành học phần này"],
                )
                continue

            if code in NATIONAL_DEFENSE_COURSES:
                exclude_course(
                    code,
                    info,
                    ["national_defense"],
                    ["Đây là học phần giáo dục quốc phòng. Sinh viên liên hệ Trung tâm Giáo dục quốc phòng và an ninh để đăng ký."],
                )
                continue

            # 2. Chuyên ngành: nếu chưa chọn chuyên ngành thì gom toàn bộ học phần chuyên ngành,
            # không để các môn này rơi sang nhóm sai kỳ mở/chưa đến kỳ khuyến nghị.
            spec_ok = True
            specs = info.get('specializations', [])

            if has_selected_specialization:
                normalized_specs = [self._normalize_text(s) for s in specs if isinstance(s, str)]
                if specs and normalized_student_spec not in normalized_specs:
                    spec_ok = False
            else:
                if specs:
                    spec_ok = False

            if not spec_ok:
                if has_selected_specialization:
                    reason = f"không khớp chuyên ngành đã chọn: {student_spec}"
                else:
                    reason = "Sinh viên chưa chọn chuyên ngành."
                exclude_course(code, info, ["specialization"], [reason])
                continue

            # Ưu tiên hạn ngạch tự chọn hơn lý do tiên quyết: khi nhóm đã đủ,
            # học phần không còn là lựa chọn của sinh viên ở bất kỳ trường hợp nào.
            cat = info.get('elective_category')
            if cat in ELECTIVE_QUOTA_KEYS and (remaining_elective_counts or {}).get(cat, 0) <= 0:
                exclude_course(
                    code,
                    info,
                    ["elective_quota"],
                    ["Nhóm học phần tự chọn đã hoàn thành."],
                )
                continue

            # 2. Chuyên ngành: nếu chưa chọn chuyên ngành thì gom toàn bộ học phần chuyên ngành,
            # không để các môn này rơi sang nhóm sai kỳ mở/chưa đến kỳ khuyến nghị.
            spec_ok = True
            specs = info.get('specializations', [])

            if has_selected_specialization:
                normalized_specs = [self._normalize_text(s) for s in specs if isinstance(s, str)]
                if specs and normalized_student_spec not in normalized_specs:
                    spec_ok = False
            else:
                if specs:
                    spec_ok = False

            if not spec_ok:
                if has_selected_specialization:
                    reason = f"không khớp chuyên ngành đã chọn: {student_spec}"
                else:
                    reason = "Sinh viên chưa chọn chuyên ngành."
                exclude_course(code, info, ["specialization"], [reason])
                continue

            # 3. Ngành học: loại môn không thuộc chương trình đào tạo của ngành trước khi xét các luật học kỳ.
            major_ok = True
            majors = info.get('majors', [])

            if student_major:
                normalized_majors = [self._normalize_text(m) for m in majors if isinstance(m, str)]
                if majors and normalized_student_major not in normalized_majors:
                    major_ok = False
            else:
                if majors and not info.get('is_required_major', False):
                    major_ok = False

            if not major_ok:
                exclude_course(
                    code,
                    info,
                    ["major"],
                    [f"không khớp ngành học của sinh viên: {student_major or 'chưa xác định'}"],
                )
                continue

            # Nếu môn bị chặn bởi một học phần tự chọn thuộc nhóm đã hoàn thành,
            # hiển thị theo lý do hạn ngạch tự chọn thay vì "thiếu tiên quyết".
            # Nhờ vậy CVHT/SV không hiểu nhầm rằng cần học lại một nhóm tự chọn đã đủ.
            completed_elective_prereqs = []
            for prereq_code in info.get('prereqs', []):
                prereq_info = self.course_data.get(prereq_code, {})
                prereq_category = prereq_info.get('elective_category')
                if (
                    prereq_category in ELECTIVE_QUOTA_KEYS
                    and (remaining_elective_counts or {}).get(prereq_category, 0) <= 0
                ):
                    completed_elective_prereqs.append(prereq_code)

            if completed_elective_prereqs:
                names = ', '.join(
                    f"{self.course_data.get(prereq_code, {}).get('name', prereq_code)} ({prereq_code})"
                    for prereq_code in completed_elective_prereqs
                )
                exclude_course(
                    code,
                    info,
                    ["elective_quota"],
                    [f"Nhóm học phần tự chọn đã hoàn thành (liên quan tiên quyết: {names})."],
                )
                continue

            # 4. Tiên quyết
            missing_prereqs = []
            failed_prereqs = []
            for p in info.get('prereqs', []):
                if p in failed_courses:
                    failed_prereqs.append(p)
                elif p not in passed_courses:
                    missing_prereqs.append(p)
            prereqs_met = not missing_prereqs and not failed_prereqs

            if not prereqs_met:
                reasons = []
                if missing_prereqs:
                    missing_str = ', '.join([f"{self.course_data.get(p, {}).get('name', p)} ({p})" for p in missing_prereqs])
                    reasons.append(f"thiếu học phần tiên quyết: {missing_str}")
                if failed_prereqs:
                    failed_str = ', '.join([f"{self.course_data.get(p, {}).get('name', p)} ({p})" for p in failed_prereqs])
                    reasons.append(f"tiên quyết chưa đạt: {failed_str}")
                exclude_course(code, info, ["prerequisite"], reasons)
                continue

            # 5. Ràng buộc học kỳ bắt buộc (Thực tập ngành kỳ 7, Đồ án/Chuyên đề kỳ 8)
            rec_sem_info = info.get('recommended_sem', 99)
            course_name_norm = self._normalize_text(str(info.get('name', '')))
            is_internship = (code in internship_codes) or ('thuc tap nganh' in course_name_norm)

            forced_ok = True
            if rec_sem_info == 8:
                forced_ok = (next_sem == 8)
            if code in semester_8_only_codes:
                forced_ok = (next_sem == 8)
            if is_internship:
                forced_ok = (next_sem == 7)

            if not forced_ok:
                reason = "ràng buộc học kỳ bắt buộc không thỏa"
                if rec_sem_info == 8:
                    reason = "học phần khuyến nghị kỳ 8 chỉ được xét khi đăng ký kỳ 8"
                if code in semester_8_only_codes:
                    reason = "Học phần chỉ được gợi ý trong học kì 8."
                if is_internship:
                    reason = "học phần thực tập ngành chỉ được xét khi đăng ký kỳ 7"
                exclude_course(code, info, ["forced_semester"], [reason])
                continue

            # 6. Kỳ mở
            open_sem_info = info.get('openSemesterType', 3)
            is_general_or_foundation = info.get('is_foundation_course') or info.get('is_general_education_course')

            # Chỉ môn giáo dục đại cương/thể chất được xem là mở mọi kỳ.
            # Môn cơ sở (Foundation) vẫn phải tuân thủ học kỳ mở trong CTĐT,
            # kể cả ở kịch bản "Trả nợ & Mở chuỗi".
            is_open_every_semester = (
                info.get('is_general_education_course')
                or info.get('is_physical_education_course')
            )
            if is_open_every_semester:
                sem_ok = True
            else:
                sem_ok = (open_sem_info in (3, 12) or open_sem_info == sem_type)

            if not sem_ok:
                exclude_course(
                    code,
                    info,
                    ["open_semester"],
                    ["Học phần chưa mở trong học kì hiện tại."],
                )
                continue

            # 7. Kỳ khuyến nghị
            recommended_ok = True if study_goal == 'học vượt' else (rec_sem_info <= next_sem)
            is_retake = code in failed_courses
            if priority_mode == "standard" and is_retake and self.dependency_count.get(code, 0) == 0:
                exclude_course(
                    code,
                    info,
                    ["debt_deferred_standard"],
                    ["m\u00f4n n\u1ee3 \u0111\u1ed9c l\u1eadp \u0111\u01b0\u1ee3c \u0111\u1ec3 l\u1ea1i cho k\u1ecbch b\u1ea3n Tr\u1ea3 n\u1ee3 & M\u1edf chu\u1ed7i"],
                )
                continue
            if not recommended_ok and not is_retake:
                exclude_course(
                    code,
                    info,
                    ["recommended_semester"],
                    ["Chưa đến học kỳ khuyến nghị, Sinh viên có thể học vượt."],
                )
                continue

            # 8. Tín chỉ
            if info.get('credit', 0) > self.max_credits:
                exclude_course(
                    code,
                    info,
                    ["course_credit_limit"],
                    [f"số tín chỉ của học phần ({info.get('credit', 0)}) vượt giới hạn đăng ký {self.max_credits}"],
                )
                continue

            # Tính điểm
            debt_score = 1 if is_retake else 0
            link_score = self.dependency_count.get(code, 0)

            is_mandatory = info.get('is_required_major') or info.get('is_required_specialization')
            is_elective = bool(info.get('elective_category')) or info.get('is_elective_major') or info.get('is_elective_specialization')
            delay_score = max(0, current_sem - rec_sem_info) if is_mandatory else 0

            debt_weight = self.heuristic_weights['debt']
            link_weight = self.heuristic_weights['link']
            delay_weight = self.heuristic_weights['delay']
            if priority_mode == "priority_retake":
                # Kịch bản 2: ưu tiên môn nợ và môn mở khóa chuỗi phía sau.
                debt_weight *= 3
                link_weight *= 2
                delay_weight *= 2
            H = (debt_score * debt_weight +
                 link_score * link_weight +
                 delay_score * delay_weight)

            open_sem_info = info.get('openSemesterType', 3)
            is_strict_sem = (open_sem_info == sem_type)
            is_any_sem = (open_sem_info in (3, 12))

            # XÁC ĐỊNH TIER ĐIỂM (Tuân thủ ưu tiên: Rớt -> Trễ bắt buộc -> Bắt buộc đúng kỳ -> Tự chọn)
            tier_score = 0
            if is_retake:
                # Kịch bản chuẩn cân bằng môn nợ với môn đúng tiến độ; kịch bản
                # trả nợ vẫn đặt học lại ở mức ưu tiên tuyệt đối.
                tier_score = 60000 if priority_mode == "priority_retake" else 22000
            elif priority_mode == "priority_retake" and is_mandatory and link_score > 0:
                tier_score = 35000
            elif is_mandatory and rec_sem_info < next_sem:
                tier_score = 30000
            elif is_mandatory and rec_sem_info == next_sem:
                tier_score = 20000
            elif is_mandatory and rec_sem_info > next_sem:
                tier_score = 10000
            else:
                tier_score = 0

            sem_score = 500 if is_strict_sem else (100 if is_any_sem else 0)

            priority_score = tier_score + H + sem_score

            # Lý do
            reasons = []
            rec_gap = abs(next_sem - rec_sem_info) if rec_sem_info < 999 else 999
            if is_retake:
                reasons.append('môn học lại')
            if is_mandatory:
                reasons.append('môn bắt buộc')
            elif is_elective:
                reasons.append('môn tự chọn')
            if is_strict_sem:
                reasons.append('mở đúng học kỳ hiện tại')
            if rec_gap == 0:
                reasons.append('đúng học kỳ khuyến nghị')
            if has_selected_specialization and normalized_student_spec in [self._normalize_text(s) for s in specs if isinstance(s, str)]:
                reasons.append('phù hợp chuyên ngành')

            valid_courses.append(RecommendedCourse(
                code=code,
                name=info.get('name', ''),
                credits=info.get('credit', 0),
                is_retake=is_retake,
                recommended_semester=rec_sem_info,
                heuristic_score=H,
                total_priority_score=priority_score,
                reasons=reasons,
                corequisites=info.get('corequisites', []),
            ))

        # Sắp xếp theo mức ưu tiên
        valid_courses.sort(key=lambda x: (
            -x.total_priority_score,
            not x.is_retake,
            -x.heuristic_score,
        ))

        return valid_courses, excluded_courses

    def _count_completed_electives(self, passed_courses: Set[str]) -> Dict[str, int]:
        """Đếm môn tự chọn đã hoàn thành"""
        counts = {k: 0 for k in ELECTIVE_QUOTA_KEYS}
        for code in passed_courses:
            info = self.course_data.get(code, {})
            cat = info.get('elective_category')
            if cat in ELECTIVE_QUOTA_KEYS:
                counts[cat] += 1
        return counts

    def _filter_by_elective_quota(self,
                                  courses: List[RecommendedCourse],
                                  remaining_quotas: Dict[str, int]) -> Tuple[List[RecommendedCourse], List[ExcludedCourse]]:
        """Lọc môn theo hạn ngạch còn thiếu"""
        filtered = []
        excluded = []
        for course in courses:
            info = self.course_data.get(course.code, {})
            cat = info.get('elective_category')
            if cat is None or remaining_quotas.get(cat, 0) > 0:
                filtered.append(course)
            else:
                excluded.append(ExcludedCourse(
                    code=course.code,
                    name=course.name,
                    credits=course.credits,
                    recommended_semester=course.recommended_semester,
                    reasons=["Nhóm học phần tự chọn đã hoàn thành."],
                    failed_rules=["elective_quota"],
                    stage="quota",
                    is_specialization_course=bool(info.get('specializations')),
                ))
        return filtered, excluded
