"""
Dịch vụ bộ máy gợi ý
Tách từ legacy/recommend_source.py để dùng lại trong Flask app
"""

import random
import unicodedata
import logging
import time
from typing import Dict, Any, List, Set, Optional, Tuple
from rdflib import Graph, URIRef, Namespace
from rdflib.namespace import RDF

from backend.app.models.student import StudentProfile
from backend.app.models.recommendation import (
    RecommendedCourse, RecommendationResult, BeamSearchState, ExcludedCourse
)

from .recommendation.constants import (
    BASE_URI,
    PROP_courseCode,
    PROP_courseName,
    PROP_hasPrerequisiteCourse,
    PROP_openSemesterType,
    PROP_recommendedInSemester,
    PROP_specializationName,
    PROP_isRequiredForSpecialization,
    PROP_isElectiveForSpecialization,
    PROP_offeredInSpecialization,
    PROP_isRequiredForMajor,
    PROP_isElectiveForMajor,
    PROP_hasCredit,
    PROP_credit,
    PROP_corequisiteWith,
    CLASS_Specialization,
    CLASS_GeneralEducationCourse,
    CLASS_PhysicalEducationCourse,
    CLASS_FoundationCourse,
    REGISTER_MAX_CREDITS,
    REGISTER_MIN_CREDITS,
    WEIGHT_DEBT,
    WEIGHT_LINK,
    WEIGHT_DELAY,
    ELECTIVE_QUOTA_KEYS,
    ENGLISH_COURSE_CREDITS,
    ENGLISH_COURSE_PREREQUISITES,
    ENGLISH_COURSES,
    NATIONAL_DEFENSE_COURSES,
    NON_GPA_ONE_CREDIT_COURSES,
    EQUIVALENT_COURSES,
    NOISE_COURSES,
)
from .recommendation.ontology import OntologyMixin
from .recommendation.eligibility import EligibilityMixin
from .recommendation.candidate_generation import CandidateGenerationMixin
from .recommendation.plan_risk import PlanRiskMixin


class RecommendationEngine(OntologyMixin, EligibilityMixin, CandidateGenerationMixin, PlanRiskMixin):
    """Hệ thống gợi ý kế hoạch học tập dựa trên Ontology và tìm kiếm chùm"""

    def __init__(self,
                 ontology_path: str,
                 beam_width: int = 8,
                 max_credits: int = REGISTER_MAX_CREDITS,
                 min_credits: int = REGISTER_MIN_CREDITS,
                 heuristic_weights: Optional[Dict[str, int]] = None,
                 elective_quotas: Optional[Dict[str, int]] = None):
        """
        Khởi tạo bộ máy gợi ý.

        Tham số:
            ontology_path: Đường dẫn đến tệp RDF ontology.
            beam_width: Độ rộng tìm kiếm chùm, tức số trạng thái giữ lại mỗi vòng.
            max_credits: Số tín chỉ tối đa mỗi học kỳ.
            min_credits: Số tín chỉ tối thiểu mỗi học kỳ.
            heuristic_weights: Trọng số cho công thức tính điểm.
            elective_quotas: Hạn ngạch mục tiêu cho từng nhóm môn tự chọn.
        """
        self.ontology_path = ontology_path
        self.beam_width = beam_width
        self.max_credits = max_credits
        self.min_credits = min_credits

        self.heuristic_weights = heuristic_weights or {
            'debt': WEIGHT_DEBT,
            'link': WEIGHT_LINK,
            'delay': WEIGHT_DELAY,
        }

        self.elective_quotas = elective_quotas or {
            'general': 1,
            'physical': 2,
            'foundation': 1,
            'specialization': 3,
        }

        self.graph: Optional[Graph] = None
        self.course_data: Dict[str, Dict[str, Any]] = {}
        self.dependency_count: Dict[str, int] = {}
        self.specializations_map: Dict[str, str] = {}
        self.cohorts: List[Dict[str, Any]] = []
        self.logger = logging.getLogger(__name__)

        self._load_ontology()


    def get_recommendation(
        self,
        student: StudentProfile,
        seed_offset: int = 0,
        priority_mode: str = "standard",
    ) -> RecommendationResult:
        """
        Tạo gợi ý kế hoạch học tập cho sinh viên.

        Tham số:
            student: Hồ sơ sinh viên.
            seed_offset: Hạt giống ngẫu nhiên để thay đổi kết quả gợi ý.

        Kết quả:
            Đối tượng `RecommendationResult`.
        """
        # Tính toán các biến
        started_at = time.perf_counter()
        self.logger.info(
            "Bắt đầu luồng gợi ý học kỳ=%s",
            student.current_semester,
        )
        current_sem = max(1, student.current_semester)
        next_sem = current_sem + 1
        sem_type = 1 if next_sem % 2 != 0 else 2

        student_spec = student.specialization.strip() if student.specialization else ""
        normalized_student_spec = self._normalize_text(student_spec) if student_spec else ""

        study_goal = student.study_goal.strip().lower()
        if study_goal not in ['đúng hạn', 'học vượt']:
            study_goal = 'đúng hạn'

        # Hạt giống ngẫu nhiên
        rng = random.Random(f"{student.student_id}-{current_sem}-{next_sem}-{seed_offset}")

        # Chuẩn hóa dữ liệu sinh viên
        passed_courses, failed_courses = self._normalize_student_data(student)

        # Phân loại tự chọn trước khi lọc để môn thuộc nhóm tự chọn đã đủ quota
        # không bị rơi sang các lý do phụ như sai kỳ mở hoặc chưa đến kỳ khuyến nghị.
        for code, info in self.course_data.items():
            info['elective_category'] = self._categorize_elective(code, info)

        completed_elective_counts = self._count_completed_electives(passed_courses)
        remaining_elective_counts = {
            k: max(0, self.elective_quotas.get(k, 0) - completed_elective_counts.get(k, 0))
            for k in ELECTIVE_QUOTA_KEYS
        }

        # Lấy danh sách môn hợp lệ (giữ lại các điều kiện)
        valid_courses, excluded_courses = self._get_valid_courses(
            student, passed_courses, failed_courses,
            current_sem, next_sem, sem_type, study_goal, remaining_elective_counts, priority_mode
        )

        # Lọc danh sách môn hợp lệ theo hạn ngạch
        eligible_courses, quota_excluded_courses = self._filter_by_elective_quota(valid_courses, remaining_elective_counts)
        excluded_courses.extend(quota_excluded_courses)
        prerequisite_warnings, specialization_warning = self._build_context_warnings(
            student,
            passed_courses,
            valid_courses,
        )

        # Chọn ngẫu nhiên môn tự chọn (nếu cần)
        beam_candidates = self._random_select_electives(
            eligible_courses, remaining_elective_counts, study_goal, rng, seed_offset
        )

        # Tìm kiếm chùm
        recommended_courses, _beam_excluded_courses = self._beam_search_optimize(
            student, beam_candidates, completed_elective_counts, study_goal, rng, passed_courses
        )
        selected_or_eligible_codes = {c.code for c in recommended_courses} | {c.code for c in eligible_courses}
        existing_excluded_keys = {
            (course.code, (course.failed_rules or ["other"])[0])
            for course in excluded_courses
        }
        for course in _beam_excluded_courses:
            rule = (course.failed_rules or ["other"])[0]
            key = (course.code, rule)
            if course.code not in selected_or_eligible_codes and key not in existing_excluded_keys:
                excluded_courses.append(course)
                existing_excluded_keys.add(key)

        # Tính toán kết quả
        total_recommended_credits = sum(c.credits for c in recommended_courses)

        # Số lượng môn tự chọn đã chốt
        finalized_elective_counts = {k: 0 for k in ELECTIVE_QUOTA_KEYS}
        for course in recommended_courses:
            code = course.code
            info = self.course_data.get(code, {})
            cat = info.get('elective_category')
            if cat in ELECTIVE_QUOTA_KEYS:
                finalized_elective_counts[cat] += 1

        result = RecommendationResult(
            student_id=student.student_id,
            student_name=student.name,
            current_semester=current_sem,
            next_semester=next_sem,
            study_goal=study_goal,
            eligible_courses=eligible_courses,
            recommended_courses=recommended_courses,
            excluded_courses=excluded_courses,
            total_eligible_count=len(eligible_courses),
            total_excluded_count=len(excluded_courses),
            total_recommended_count=len(recommended_courses),
            total_recommended_credits=total_recommended_credits,
            elective_target_quotas=dict(self.elective_quotas),
            elective_completed_counts=completed_elective_counts,
            elective_quota_remaining=remaining_elective_counts,
            finalized_elective_counts=finalized_elective_counts,
        )

        if specialization_warning:
            result.specialization_warning = specialization_warning
            result.warnings.append(specialization_warning)

        if prerequisite_warnings:
            result.prerequisite_warnings = prerequisite_warnings
            result.warnings.extend(prerequisite_warnings)

        result.beam_search_details = (
            f"số_môn_ontology={len(self.course_data)}, hợp_lệ={len(eligible_courses)}, "
            f"bị_loại={len(excluded_courses)}, ứng_viên_chùm={len(beam_candidates)}, đề_xuất={len(recommended_courses)}, "
            f"thời_gian_xử_lý_ms={round((time.perf_counter() - started_at) * 1000, 2)}"
        )
        result.heuristic_formula = (
            "H = nợ*1000 + độ_phủ*20 + độ_trễ*50; "
            "H_tổng = H + đang_mở*50 + gần_khuyến_nghị*10 + điểm_mục_tiêu"
        )

        if total_recommended_credits < self.min_credits:
            result.warnings.append(
                f"Tổng tín chỉ đề xuất {total_recommended_credits} thấp hơn mức tối thiểu {self.min_credits}"
            )

        # Đánh giá độ khó của phương án
        result.difficulty_analysis = self.analyze_plan_difficulty(recommended_courses, student)

        self.logger.info(
            "Đã hoàn tất luồng gợi ý hợp_lệ=%s đề_xuất=%s tín_chỉ=%s",
            len(eligible_courses),
            len(recommended_courses),
            total_recommended_credits,
        )
        return result


    def _build_context_warnings(
        self,
        student: StudentProfile,
        passed_courses: Set[str],
        valid_courses: List[RecommendedCourse],
    ) -> Tuple[List[str], str]:
        """Tạo cảnh báo ngữ cảnh cho tiên quyết và chuyên ngành."""
        warnings: List[str] = []

        specialization_warning = ""
        student_spec = student.specialization.strip() if student.specialization else ""
        normalized_spec = self._normalize_text(student_spec) if student_spec else ""
        has_selected_specialization = bool(student_spec) and normalized_spec != "chua chon chuyen nganh"
        if not has_selected_specialization:
            specialization_warning = (
                "Sinh viên chưa lựa chọn chuyên ngành; các học phần chuyên ngành chưa được xét. "
                "Hệ thống chỉ gợi ý các học phần chung và học phần bắt buộc của ngành."
            )

        valid_codes = {course.code for course in valid_courses}
        for code, info in self.course_data.items():
            if code in passed_courses or code in valid_codes:
                continue

            # Lọc theo chuyên ngành để tránh cảnh báo môn không thuộc chuyên ngành của sinh viên
            spec_ok = True
            specs = info.get('specializations', [])
            if has_selected_specialization:
                normalized_specs = [self._normalize_text(s) for s in specs if isinstance(s, str)]
                if specs and normalized_spec not in normalized_specs:
                    spec_ok = False
            else:
                # Nếu chưa chọn chuyên ngành thì không xét bất kỳ môn chuyên ngành nào
                if specs:
                    spec_ok = False

            if not spec_ok:
                continue


        return warnings, specialization_warning


    # Các hàm hỗ trợ
    @staticmethod
    def _normalize_text(value: str) -> str:
        """Chuẩn hóa text"""
        return ''.join(
            ch for ch in unicodedata.normalize('NFKD', value.lower().strip())
            if not unicodedata.combining(ch)
        )

    @staticmethod
    def _normalize_course_code(value: str) -> str:
        """Chuẩn hóa mã môn"""
        return value.strip().upper()

    @staticmethod
    def _safe_int(value: Any, default: int) -> int:
        """Chuyển sang int an toàn"""
        try:
            if isinstance(value, int):
                return value
            if isinstance(value, float):
                return int(value)
            s = str(value).strip()
            if not s:
                return default
            if '.' in s:
                return int(float(s))
            return int(s)
        except Exception:
            return default
