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

from flask_app.models.student import StudentProfile
from flask_app.models.recommendation import (
    RecommendedCourse, RecommendationResult, BeamSearchState
)

# Định danh RDF
BASE_URI = "http://www.semanticweb.org/henrydao/ontologies/2025/7/TrainingProgramOntology#"

PROP_courseCode = URIRef(BASE_URI + "courseCode")
PROP_courseName = URIRef(BASE_URI + "courseName")
PROP_hasPrerequisiteCourse = URIRef(BASE_URI + "hasPrerequisiteCourse")
PROP_openSemesterType = URIRef(BASE_URI + "openSemesterType")
PROP_recommendedInSemester = URIRef(BASE_URI + "recommendedInSemester")
PROP_specializationName = URIRef(BASE_URI + "specializationName")
PROP_isRequiredForSpecialization = URIRef(BASE_URI + "isRequiredForSpecialization")
PROP_isElectiveForSpecialization = URIRef(BASE_URI + "isElectiveForSpecialization")
PROP_offeredInSpecialization = URIRef(BASE_URI + "offeredInSpecialization")
PROP_isRequiredForMajor = URIRef(BASE_URI + "isRequiredForMajor")
PROP_isElectiveForMajor = URIRef(BASE_URI + "isElectiveForMajor")
PROP_hasCredit = URIRef(BASE_URI + "hasCredit")
PROP_credit = URIRef(BASE_URI + "credit")
PROP_corequisiteWith = URIRef(BASE_URI + "corequisiteWith")

CLASS_Specialization = URIRef(BASE_URI + "Specialization")
CLASS_GeneralEducationCourse = URIRef(BASE_URI + "GeneralEducationCourse")
CLASS_PhysicalEducationCourse = URIRef(BASE_URI + "PhysicalEducationCourse")
CLASS_FoundationCourse = URIRef(BASE_URI + "FoundationCourse")

# Hằng số
REGISTER_MAX_CREDITS = 27
REGISTER_MIN_CREDITS = 10

WEIGHT_DEBT = 1000
WEIGHT_LINK = 20
WEIGHT_DELAY = 50

ELECTIVE_QUOTA_KEYS = ('general', 'physical', 'foundation', 'specialization')


class RecommendationEngine:
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
        self.logger = logging.getLogger(__name__)
        
        self._load_ontology()
    
    def _load_ontology(self):
        """Nạp RDF ontology và trích xuất dữ liệu môn học"""
        import os
        from pathlib import Path
        from urllib.request import pathname2url
        
        self.graph = Graph()
        
        # Chuyển đường dẫn Windows sang dạng file:// URI hợp lệ
        ontology_file = Path(self.ontology_path).resolve()
        
        if not ontology_file.exists():
            raise FileNotFoundError(f"Không tìm thấy file ontology: {self.ontology_path}")
        
        # Chuyển đổi file URI phù hợp cho Windows và Unix
        if os.name == 'nt':  # Windows
            # Đổi sang dấu / và thêm tiền tố file:///
            file_path = str(ontology_file).replace('\\', '/')
            ontology_uri = f'file:///{file_path}'
        else:  # Unix/Linux
            ontology_uri = ontology_file.as_uri()
        
        self.logger.info("Đang nạp ontology từ %s", ontology_uri)
        self.graph.parse(ontology_uri, format="xml")
        
        # Trích xuất chuyên ngành
        for spec in self.graph.subjects(RDF.type, CLASS_Specialization):
            if isinstance(spec, URIRef):
                val = self.graph.value(spec, PROP_specializationName)
                if val is not None:
                    self.specializations_map[str(spec)] = str(val)
        
        # Trích xuất thông tin môn học
        for course in self.graph.subjects(PROP_courseCode, None):
            code_val_node = self.graph.value(course, PROP_courseCode)
            if code_val_node is None:
                continue
            
            code = self._normalize_course_code(str(code_val_node))
            if not code:
                continue
            
            # Tên môn
            name_val = self.graph.value(course, PROP_courseName)
            name = str(name_val) if name_val is not None else code
            
            # Tiên quyết
            prereqs = []
            for p in self.graph.objects(course, PROP_hasPrerequisiteCourse):
                p_code = self.graph.value(p, PROP_courseCode)
                if p_code is not None:
                    normalized_pr = self._normalize_course_code(str(p_code))
                    if normalized_pr:
                        prereqs.append(normalized_pr)
            
            # Kỳ mở
            open_sem = self.graph.value(course, PROP_openSemesterType)
            open_sem_val = self._safe_int(open_sem, 3)
            
            # Kỳ khuyến nghị
            recommended_sem_val = 99999
            sem_uri = self.graph.value(course, PROP_recommendedInSemester)
            if sem_uri is not None:
                sem_str = str(sem_uri).split('#')[-1]
                if sem_str.startswith("Semester"):
                    try:
                        recommended_sem_val = int(sem_str.replace("Semester", ""))
                    except ValueError:
                        pass
            
            # Chuyên ngành
            linked_specializations: Set[str] = set()
            is_required_for_specialization = False
            is_elective_for_specialization = False
            
            for spec_uri in self.graph.objects(course, PROP_isRequiredForSpecialization):
                is_required_for_specialization = True
                if isinstance(spec_uri, URIRef):
                    spec_name = self.specializations_map.get(str(spec_uri))
                    if spec_name:
                        linked_specializations.add(spec_name)
            
            for spec_uri in self.graph.objects(course, PROP_isElectiveForSpecialization):
                is_elective_for_specialization = True
                if isinstance(spec_uri, URIRef):
                    spec_name = self.specializations_map.get(str(spec_uri))
                    if spec_name:
                        linked_specializations.add(spec_name)
            
            for spec_uri in self.graph.objects(course, PROP_offeredInSpecialization):
                if isinstance(spec_uri, URIRef):
                    spec_name = self.specializations_map.get(str(spec_uri))
                    if spec_name:
                        linked_specializations.add(spec_name)
            
            # Song hành
            coreqs = []
            for co in self.graph.objects(course, PROP_corequisiteWith):
                if isinstance(co, URIRef):
                    coreq_code = self.graph.value(co, PROP_courseCode)
                    if coreq_code is not None:
                        normalized_coreq = self._normalize_course_code(str(coreq_code))
                        if normalized_coreq:
                            coreqs.append(normalized_coreq)
            
            # Tín chỉ
            credits = 0
            credits_val = self.graph.value(course, PROP_hasCredit)
            if credits_val is None:
                credits_val = self.graph.value(course, PROP_credit)
            
            if credits_val is not None:
                try:
                    if isinstance(credits_val, (int, float)):
                        credits = int(credits_val)
                    else:
                        credit_str = str(credits_val).strip()
                        if '.' in credit_str:
                            credits = int(float(credit_str))
                        else:
                            credits = int(credit_str)
                except Exception:
                    credits = 0
            
            # Loại môn
            is_general_education = any(
                str(t).endswith('#GeneralEducationCourse') 
                for t in self.graph.objects(course, RDF.type)
            )
            is_physical_education = any(
                str(t).endswith('#PhysicalEducationCourse')
                for t in self.graph.objects(course, RDF.type)
            )
            is_foundation_course = any(
                str(t).endswith('#FoundationCourse')
                for t in self.graph.objects(course, RDF.type)
            )
            
            is_required_for_major = any(True for _ in self.graph.objects(course, PROP_isRequiredForMajor))
            is_elective_for_major = any(True for _ in self.graph.objects(course, PROP_isElectiveForMajor))
            
            self.course_data[code] = {
                'name': name,
                'prereqs': prereqs,
                'openSemesterType': open_sem_val,
                'recommended_sem': recommended_sem_val,
                'specializations': list(linked_specializations),
                'is_required_specialization': is_required_for_specialization,
                'is_elective_specialization': is_elective_for_specialization,
                'is_required_major': is_required_for_major,
                'is_elective_major': is_elective_for_major,
                'is_general_education_course': is_general_education,
                'is_physical_education_course': is_physical_education,
                'is_foundation_course': is_foundation_course,
                'corequisites': coreqs,
                'credit': credits,
                'elective_category': None,
            }
        
        # Tính số lượng môn phụ thuộc
        self.dependency_count = {code: 0 for code in self.course_data.keys()}
        for cinfo in self.course_data.values():
            for pr in cinfo.get('prereqs', []):
                if pr in self.dependency_count:
                    self.dependency_count[pr] += 1

        self.logger.info(
            "Đã nạp ontology: %s môn học, %s chuyên ngành",
            len(self.course_data),
            len(self.specializations_map),
        )
    
    def get_recommendation(self, student: StudentProfile) -> RecommendationResult:
        """
        Tạo gợi ý kế hoạch học tập cho sinh viên.

        Tham số:
            student: Hồ sơ sinh viên.

        Kết quả:
            Đối tượng `RecommendationResult`.
        """
        # Tính toán các biến
        started_at = time.perf_counter()
        self.logger.info(
            "Bắt đầu luồng gợi ý cho student_id=%s, học kỳ=%s",
            student.student_id,
            student.current_semester,
        )
        current_sem = max(1, student.current_semester)
        next_sem = current_sem + 1
        sem_type = 1 if next_sem % 2 != 0 else 2
        
        student_spec = student.specialization.strip() if student.specialization else ""
        normalized_student_spec = self._normalize_text(student_spec) if student_spec else ""
        
        study_goal = student.study_goal.strip().lower()
        if study_goal not in ['đúng hạn', 'giảm tải', 'học vượt']:
            study_goal = 'đúng hạn'
        
        # Hạt giống ngẫu nhiên
        rng = random.Random(f"{student.student_id}-{current_sem}-{next_sem}")
        
        # Chuẩn hóa dữ liệu sinh viên
        passed_courses, failed_courses = self._normalize_student_data(student)
        
        # Lấy danh sách môn hợp lệ (giữ lại các điều kiện)
        valid_courses = self._get_valid_courses(
            student, passed_courses, failed_courses, 
            current_sem, next_sem, sem_type, study_goal
        )
        
        # Phân loại tự chọn
        for code, info in self.course_data.items():
            info['elective_category'] = self._categorize_elective(code, info)
        
        # Tính hạn ngạch còn thiếu
        completed_elective_counts = self._count_completed_electives(passed_courses)
        remaining_elective_counts = {
            k: max(0, self.elective_quotas.get(k, 0) - completed_elective_counts.get(k, 0))
            for k in ELECTIVE_QUOTA_KEYS
        }
        
        # Lọc danh sách môn hợp lệ theo hạn ngạch
        eligible_courses = self._filter_by_elective_quota(valid_courses, remaining_elective_counts)
        prerequisite_warnings, specialization_warning = self._build_context_warnings(
            student,
            passed_courses,
            valid_courses,
        )

        # Chọn ngẫu nhiên môn tự chọn (nếu cần)
        beam_candidates = self._random_select_electives(
            eligible_courses, remaining_elective_counts, study_goal, rng
        )
        
        # Tìm kiếm chùm
        recommended_courses = self._beam_search_optimize(
            student, beam_candidates, completed_elective_counts, study_goal, rng
        )
        
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
            total_eligible_count=len(eligible_courses),
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
            f"ứng_viên_chùm={len(beam_candidates)}, đề_xuất={len(recommended_courses)}, "
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

        self.logger.info(
            "Đã hoàn tất luồng gợi ý cho %s: hợp_lệ=%s đề_xuất=%s tín_chỉ=%s",
            student.student_id,
            len(eligible_courses),
            len(recommended_courses),
            total_recommended_credits,
        )
        return result
    
    def _normalize_student_data(self, student: StudentProfile) -> Tuple[Set[str], Set[str]]:
        """Chuẩn hóa dữ liệu sinh viên"""
        passed_courses = set(self._normalize_course_code(c) for c in student.passed_courses)
        failed_courses = set(self._normalize_course_code(c) for c in student.failed_courses)
        
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
                          study_goal: str) -> List[RecommendedCourse]:
        """Lọc môn hợp lệ theo 8 điều kiện"""
        valid_courses = []
        internship_codes = {'INT6900', 'SOT348'}
        
        for code, info in self.course_data.items():
            # 1. Chưa đạt
            if code in passed_courses:
                continue
            
            # 2. Tiên quyết
            prereqs_met = True
            for p in info.get('prereqs', []):
                if p in failed_courses:
                    prereqs_met = False
                    break
                if p not in passed_courses:
                    prereqs_met = False
                    break
            
            if not prereqs_met:
                continue
            
            # 3. Kỳ mở
            open_sem_info = info.get('openSemesterType', 3)
            sem_ok = (open_sem_info in (3, 12) or open_sem_info == sem_type)
            if not sem_ok:
                continue
            
            # 4. Kỳ khuyến nghị
            rec_sem_info = info.get('recommended_sem', 99)
            recommended_ok = True if study_goal == 'học vượt' else (rec_sem_info <= next_sem)
            
            # 5. Chuyên ngành
            student_spec = student.specialization.strip() if student.specialization else ""
            normalized_student_spec = self._normalize_text(student_spec) if student_spec else ""
            spec_ok = True
            specs = info.get('specializations', [])
            
            if student_spec:
                normalized_specs = [self._normalize_text(s) for s in specs if isinstance(s, str)]
                if specs and normalized_student_spec not in normalized_specs:
                    spec_ok = False
            else:
                if specs and not info.get('is_required_specialization', False):
                    spec_ok = False
            
            if not spec_ok:
                continue
            
            # 6. Tín chỉ
            if info.get('credit', 0) > self.max_credits:
                continue
            
            # 7-8. Ràng buộc cứng
            course_name_norm = self._normalize_text(str(info.get('name', '')))
            is_internship = (code in internship_codes) or ('thuc tap nganh' in course_name_norm)
            
            forced_ok = True
            if rec_sem_info == 8:
                forced_ok = (next_sem == 8)
            if is_internship:
                forced_ok = (next_sem == 7)
            
            if not forced_ok:
                continue
            
            # Nếu chưa đạt hay đủ tiên quyết (học lại)
            is_retake = code in failed_courses
            
            if not (prereqs_met and sem_ok and (recommended_ok or is_retake) and spec_ok and forced_ok):
                continue
            
            # Tính điểm
            debt_score = 1 if is_retake else 0
            link_score = self.dependency_count.get(code, 0)
            delay_score = max(0, current_sem - rec_sem_info)
            
            H = (debt_score * self.heuristic_weights['debt'] + 
                 link_score * self.heuristic_weights['link'] + 
                 delay_score * self.heuristic_weights['delay'])
            
            open_now_score = 1 if sem_ok else 0
            rec_gap = abs(next_sem - rec_sem_info) if rec_sem_info < 999 else 999
            rec_proximity_score = max(0, 10 - rec_gap)
            
            if student.study_goal == 'đúng hạn':
                goal_score = 30
            elif student.study_goal == 'giảm tải':
                goal_score = 20
            elif student.study_goal == 'học vượt':
                goal_score = 10
            else:
                goal_score = 0
            
            priority_score = H + (open_now_score * 50) + (rec_proximity_score * 10) + goal_score
            
            # Lý do
            reasons = []
            if is_retake:
                reasons.append('môn học lại')
            if info.get('is_required_major') or info.get('is_required_specialization'):
                reasons.append('môn bắt buộc')
            if open_now_score:
                reasons.append('mở đúng học kỳ hiện tại')
            if rec_gap == 0:
                reasons.append('đúng học kỳ khuyến nghị')
            if student_spec and normalized_student_spec in [self._normalize_text(s) for s in specs if isinstance(s, str)]:
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
        
        return valid_courses
    
    def _categorize_elective(self, code: str, info: Dict[str, Any]) -> Optional[str]:
        """Phân loại môn tự chọn"""
        is_elec = info.get('is_elective_major') or info.get('is_elective_specialization')
        if not is_elec:
            return None
        
        if info.get('is_physical_education_course'):
            return 'physical'
        elif info.get('is_foundation_course'):
            return 'foundation'
        elif info.get('is_general_education_course'):
            return 'general'
        else:
            return 'specialization'
    
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
                                  remaining_quotas: Dict[str, int]) -> List[RecommendedCourse]:
        """Lọc môn theo hạn ngạch còn thiếu"""
        filtered = []
        for course in courses:
            info = self.course_data.get(course.code, {})
            cat = info.get('elective_category')
            if cat is None or remaining_quotas.get(cat, 0) > 0:
                filtered.append(course)
        return filtered
    
    def _random_select_electives(self,
                                courses: List[RecommendedCourse],
                                remaining_quotas: Dict[str, int],
                                study_goal: str,
                                rng: random.Random) -> List[RecommendedCourse]:
        """Random chọn môn tự chọn (nếu cần)"""
        strict_single = study_goal in ('đúng hạn', 'giảm tải')
        
        if strict_single:
            elective_pool = [
                c for c in courses
                if self.course_data.get(c.code, {}).get('elective_category') is not None
            ]
            if len(elective_pool) > 1:
                chosen = rng.choice(elective_pool)
                return [c for c in courses if c.code == chosen.code or 
                        self.course_data.get(c.code, {}).get('elective_category') is None] + [chosen]
        
        return courses
    
    def _beam_search_optimize(self,
                             student: StudentProfile,
                             candidates: List[RecommendedCourse],
                             completed_counts: Dict[str, int],
                             study_goal: str,
                             rng: random.Random) -> List[RecommendedCourse]:
        """Tìm kiếm chùm để tối ưu tổ hợp môn"""
        # Tìm kiếm chùm (phiên bản rút gọn)
        # Khởi tạo trạng thái rỗng
        initial_state = {
            'selected_codes': set(),
            'selected_courses': [],
            'credit': 0,
            'score': 0.0,
            'elective_counts': {k: 0 for k in ELECTIVE_QUOTA_KEYS},
        }
        
        # Cách tham lam: thêm môn có điểm cao nhất
        selected_courses = []
        total_credit = 0
        
        for course in candidates:
            if total_credit + course.credits <= self.max_credits:
                info = self.course_data.get(course.code, {})
                cat = info.get('elective_category')
                
                # Kiểm tra hạn ngạch
                if cat and cat in ELECTIVE_QUOTA_KEYS:
                    if initial_state['elective_counts'][cat] >= completed_counts.get(cat, 0) + 1:
                        continue
                
                selected_courses.append(course)
                total_credit += course.credits
                
                if cat:
                    initial_state['elective_counts'][cat] += 1
        
        return selected_courses

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
        if not student_spec or normalized_spec == "chua chon chuyen nganh":
            specialization_warning = (
                "Sinh viên chưa chọn chuyên ngành; hệ thống chỉ ưu tiên môn bắt buộc và môn chung."
            )

        valid_codes = {course.code for course in valid_courses}
        for code, info in self.course_data.items():
            if code in passed_courses or code in valid_codes:
                continue

            # Lọc theo chuyên ngành để tránh cảnh báo môn không thuộc chuyên ngành của sinh viên
            spec_ok = True
            specs = info.get('specializations', [])
            if student_spec:
                normalized_specs = [self._normalize_text(s) for s in specs if isinstance(s, str)]
                if specs and normalized_spec not in normalized_specs:
                    spec_ok = False
            else:
                if specs and not info.get('is_required_specialization', False):
                    spec_ok = False

            if not spec_ok:
                continue

            prereqs = info.get('prereqs', [])
            if not prereqs:
                continue

            missing_prereqs = [p for p in prereqs if p not in passed_courses]
            if not missing_prereqs:
                continue

            warnings.append(
                f"Môn {code} - {info.get('name', code)} đang thiếu tiên quyết: {', '.join(missing_prereqs)}"
            )
            if len(warnings) >= 5:
                break

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
