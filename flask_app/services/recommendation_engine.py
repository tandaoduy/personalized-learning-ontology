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
    RecommendedCourse, RecommendationResult, BeamSearchState, ExcludedCourse
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

ENGLISH_COURSE_CREDITS = 4
ENGLISH_COURSE_PREREQUISITES = {
    'FLS312': ['FLS310'],  # Tiếng Anh A2.1 cần A1
    'FLS313': ['FLS312'],  # Tiếng Anh A2.2 cần A2.1
    'FLS314': ['FLS313'],  # Tiếng Anh B1.1 cần A2.2
    'FLS315': ['FLS314'],  # Tiếng Anh B1.2 cần B1.1
}
ENGLISH_COURSES = frozenset({'FLS310', *ENGLISH_COURSE_PREREQUISITES.keys()})
NATIONAL_DEFENSE_COURSES = frozenset({'QPAD011', 'QPAD02', 'QPAD033', 'QPAD044'})
NON_GPA_ONE_CREDIT_COURSES = frozenset({'SOT301'})

# Môn tương đương: key = mã phụ (sẽ bị loại), value = mã chính (sẽ giữ lại)
# INT6900 và SOT348 thực chất là cùng một môn thực tập ngành
EQUIVALENT_COURSES = {
    'SOT348': 'INT6900',
}

# Môn gây nhiễu: có isElectiveForMajor=CNTT trong RDF nhưng thực chất là môn
# của ngành Cơ khí / Ô tô / Hàng hải → không bao giờ gợi ý cho sinh viên CNTT.
# (SSH, BUA, MKT, EPM vẫn được giữ vì là tự chọn hợp lệ của CNTT)
NOISE_COURSES: frozenset = frozenset({
    'AUE319',   # Nhập môn ngành Kỹ thuật ô tô
    'MAE3098',  # Nhập môn ngành KT Cơ khí động lực
    'MAE3099',  # Nhập môn ngành Khoa học hàng hải
    'MAE3207',  # Khoa học quản lý (Cơ khí)
    'MAE331',   # Kỹ thuật thủy khí
    'MEM340',   # Cơ học ứng dụng
    'MEM341',   # Đồ họa kỹ thuật (1LT, 1TH)
    'MEM342',   # Vật liệu học
    'MEM347',   # Vẽ kỹ thuật (2LT+1TH)
    'EPM320',   # Con người và môi trường
    'SH1',      # Sinh hoạt Cuối tuần - nhà trường tự thêm, không cần gợi ý
    'SSH380',   # Văn hóa Việt Nam - Môn nhiễu
})


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
        self.cohorts: List[Dict[str, Any]] = []
        self.logger = logging.getLogger(__name__)
        
        self._load_ontology()
    
    def _assign_course_difficulty(self, name: str, is_physical: bool) -> Tuple[str, float]:
        """Gán điểm độ khó và loại môn dựa trên tên môn học."""
        name_lower = name.lower()
        if is_physical or "thể chất" in name_lower:
            return "PHYSICAL", 1.0
        if any(w in name_lower for w in ["toán", "xác suất", "đại số", "giải tích", "rời rạc"]):
            return "MATH", 4.0
        if any(w in name_lower for w in ["lập trình", "cấu trúc dữ liệu", "thuật toán", "hệ điều hành", "kiến trúc máy tính", "mạng", "phần mềm"]):
            return "PROGRAMMING", 3.5
        if any(w in name_lower for w in ["đồ án", "thực tập", "dự án"]):
            return "PROJECT", 4.0
        if any(w in name_lower for w in ["tiếng anh", "ngoại ngữ"]):
            return "GENERAL", 1.5
        if any(w in name_lower for w in ["triết học", "tư tưởng", "chủ nghĩa", "pháp luật", "quốc phòng"]):
            return "THEORY", 2.0
        return "THEORY", 2.5
    
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

        # Trích xuất lớp hành chính
        CLASS_AcademicClass = URIRef(BASE_URI + "AcademicClass")
        PROP_classCode = URIRef(BASE_URI + "classCode")
        from rdflib.namespace import RDFS
        
        classes_set = set()
        for class_uri in self.graph.subjects(RDF.type, CLASS_AcademicClass):
            if isinstance(class_uri, URIRef):
                val = self.graph.value(class_uri, PROP_classCode)
                if val is None:
                    val = self.graph.value(class_uri, RDFS.label)
                if val is None:
                    val = str(class_uri).split('#')[-1]
                if val is not None:
                    classes_set.add(str(val).strip())
        self.academic_classes = sorted(list(classes_set))

        CLASS_Cohort = URIRef(BASE_URI + "Cohort")
        PROP_cohortCode = URIRef(BASE_URI + "cohortCode")
        PROP_academicYearStart = URIRef(BASE_URI + "academicYearStart")
        PROP_hasAcademicClass = URIRef(BASE_URI + "hasAcademicClass")
        cohorts = []
        seen_cohort_codes = set()
        for cohort_uri in self.graph.subjects(RDF.type, CLASS_Cohort):
            if not isinstance(cohort_uri, URIRef):
                continue
            code_node = self.graph.value(cohort_uri, PROP_cohortCode)
            code = str(code_node).strip() if code_node is not None else str(cohort_uri).split("#")[-1].strip()
            if not code or code in seen_cohort_codes:
                continue
            seen_cohort_codes.add(code)

            year_node = self.graph.value(cohort_uri, PROP_academicYearStart)
            year_start = self._safe_int(str(year_node), None) if year_node is not None else None
            if year_start is None:
                digits = "".join(ch for ch in code if ch.isdigit())
                year_start = 1958 + int(digits) if digits else None

            cohort_number = "".join(ch for ch in code if ch.isdigit())
            cohort_classes = []
            for class_uri in self.graph.objects(cohort_uri, PROP_hasAcademicClass):
                class_code_node = self.graph.value(class_uri, PROP_classCode)
                if class_code_node is None:
                    class_code_node = self.graph.value(class_uri, RDFS.label)
                if class_code_node is None and isinstance(class_uri, URIRef):
                    class_code_node = str(class_uri).split("#")[-1]
                if class_code_node is not None:
                    cohort_classes.append(str(class_code_node).strip())
            cohort_classes = sorted({item for item in cohort_classes if item})
            cohorts.append({
                "code": code,
                "label": f"Khóa {cohort_number or code}",
                "year_admitted": year_start,
                "academic_classes": cohort_classes,
            })
        self.cohorts = sorted(
            cohorts,
            key=lambda item: (
                item.get("year_admitted") is None,
                item.get("year_admitted") or 0,
                item.get("code") or "",
            ),
        )

        # Trích xuất ngành học
        self.majors_map = {}
        PROP_majorName = URIRef(BASE_URI + "majorName")
        for s, o in self.graph.subject_objects(PROP_majorName):
            self.majors_map[str(s)] = str(o)

        # Trích xuất bản đồ ngành học - chuyên ngành
        self.major_specializations_map = {}
        PROP_hasSpecialization = URIRef(BASE_URI + "hasSpecialization")
        CLASS_Major = URIRef(BASE_URI + "Major")
        for m in self.graph.subjects(RDF.type, CLASS_Major):
            major_name = self.graph.value(m, PROP_majorName)
            if major_name is not None:
                major_name_str = str(major_name).strip()
                self.major_specializations_map[major_name_str] = []
                for spec in self.graph.objects(m, PROP_hasSpecialization):
                    spec_name = self.graph.value(spec, PROP_specializationName)
                    if spec_name is not None:
                        self.major_specializations_map[major_name_str].append(str(spec_name).strip())
                self.major_specializations_map[major_name_str].sort()
        
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
            
            linked_majors: Set[str] = set()
            is_required_for_major = False
            is_elective_for_major = False
            
            for major_uri in self.graph.objects(course, PROP_isRequiredForMajor):
                is_required_for_major = True
                if isinstance(major_uri, URIRef):
                    major_name = self.majors_map.get(str(major_uri))
                    if major_name:
                        linked_majors.add(major_name)

            for major_uri in self.graph.objects(course, PROP_isElectiveForMajor):
                is_elective_for_major = True
                if isinstance(major_uri, URIRef):
                    major_name = self.majors_map.get(str(major_uri))
                    if major_name:
                        linked_majors.add(major_name)
            
            # Phân loại độ khó
            course_type, difficulty_score = self._assign_course_difficulty(name, is_physical_education)

            self.course_data[code] = {
                'name': name,
                'prereqs': prereqs,
                'openSemesterType': open_sem_val,
                'recommended_sem': recommended_sem_val,
                'specializations': list(linked_specializations),
                'majors': list(linked_majors),
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
                'course_type': course_type,
                'difficulty_score': difficulty_score,
            }
        
        # Gộp môn tương đương: loại bỏ mã phụ, chỉ giữ mã chính
        for alias, canonical in EQUIVALENT_COURSES.items():
            if alias in self.course_data and canonical in self.course_data:
                # Loại bỏ mã phụ khỏi danh sách môn
                del self.course_data[alias]
                self.logger.info(
                    "Đã gộp môn tương đương: %s -> %s", alias, canonical
                )
            elif alias in self.course_data and canonical not in self.course_data:
                # Nếu chỉ có mã phụ, đổi tên thành mã chính
                self.course_data[canonical] = self.course_data.pop(alias)
                self.course_data[canonical]['name'] = f"{self.course_data[canonical]['name']}"
                self.logger.info(
                    "Đã đổi tên môn tương đương: %s -> %s", alias, canonical
                )

        # Cập nhật prereqs: thay mã phụ bằng mã chính
        for cinfo in self.course_data.values():
            cinfo['prereqs'] = [
                EQUIVALENT_COURSES.get(p, p) for p in cinfo.get('prereqs', [])
            ]
            cinfo['corequisites'] = [
                EQUIVALENT_COURSES.get(c, c) for c in cinfo.get('corequisites', [])
            ]

        # Chuẩn hóa học phần tiếng Anh: A1/A2.1/A2.2/B1.1/B1.2 đều có tải đăng ký 4 TC.
        # Riêng việc có tính vào GPA/tín chỉ tích lũy hay không được xử lý ở StudentDataService.
        for code in ENGLISH_COURSES:
            if code in self.course_data:
                self.course_data[code]['credit'] = ENGLISH_COURSE_CREDITS

        # Các học phần này có tải đăng ký 1 tín chỉ nhưng không tính vào GPA/tín chỉ tích lũy.
        for code, cinfo in self.course_data.items():
            if cinfo.get('is_physical_education_course') or code in NON_GPA_ONE_CREDIT_COURSES:
                cinfo['credit'] = 1

        for code, prereqs in ENGLISH_COURSE_PREREQUISITES.items():
            if code not in self.course_data:
                continue
            merged_prereqs = list(self.course_data[code].get('prereqs', []))
            for prereq in prereqs:
                if prereq not in merged_prereqs:
                    merged_prereqs.append(prereq)
            self.course_data[code]['prereqs'] = merged_prereqs

        # --- Cách 2: Gán nhãn is_it_program cho từng môn dựa trên majors từ RDF ---
        # Môn không gắn ngành nào (môn chung, đại cương) → is_it_program = True
        # Môn gắn ngành khác CNTT (ví dụ MAE - Cơ Khí) → is_it_program = False
        # course_data vẫn GIỮ NGUYÊN toàn bộ môn (để validate khi nhập sinh viên),
        # chỉ dùng flag này để lọc trong bước GỢI Ý (_get_valid_courses).
        IT_MAJOR_NORMALIZED = self._normalize_text("Công Nghệ Thông Tin")
        for code, info in self.course_data.items():
            majors = info.get('majors', [])
            if not majors:
                info['is_it_program'] = True   # môn chung/đại cương, không gắn ngành
            else:
                normalized_majors = [self._normalize_text(m) for m in majors]
                info['is_it_program'] = IT_MAJOR_NORMALIZED in normalized_majors

        # Tính toán danh sách môn phụ thuộc
        self.dependents_map = {code: [] for code in self.course_data.keys()}
        for code, cinfo in self.course_data.items():
            for pr in cinfo.get('prereqs', []):
                if pr in self.dependents_map:
                    self.dependents_map[pr].append(code)

        self.logger.info(
            "Đã nạp ontology: %s môn học, %s chuyên ngành",
            len(self.course_data),
            len(self.specializations_map),
        )
    
    def calculate_credit_load_score(self, total_credits: int) -> int:
        if total_credits <= 12:
            return 5
        if total_credits <= 15:
            return 12
        if total_credits <= 18:
            return 18
        if total_credits <= 21:
            return 22
        return 25

    def calculate_course_difficulty_score(self, courses) -> int:
        total_weight = 0
        total_credits = 0

        for course in courses:
            credits = getattr(course, 'credits', 0)
            if credits == 0:
                cinfo = self.course_data.get(course.code, {})
                credits = cinfo.get('credit', 0)
            
            cinfo = self.course_data.get(course.code, {})
            difficulty = cinfo.get('difficulty_score', 2.5)

            total_weight += difficulty * credits
            total_credits += credits

        if total_credits == 0:
            return 0

        average = total_weight / total_credits
        return min(25, round(average / 5 * 25))

    def calculate_retake_risk_score(self, courses, student: StudentProfile) -> int:
        score = 0
        failed_courses = set(self._normalize_course_code(c) for c in student.failed_courses)
        failed_courses = {EQUIVALENT_COURSES.get(c, c) for c in failed_courses}

        for course in courses:
            if course.code in failed_courses:
                score += 8

        return min(score, 20)

    def calculate_prerequisite_pressure_score(self, courses) -> int:
        score = 0
        for course in courses:
            dependents = self.dependents_map.get(course.code, [])
            dependent_count = len(dependents)
            if dependent_count >= 5:
                score += 5
            elif dependent_count >= 3:
                score += 3
            elif dependent_count >= 1:
                score += 1
        return min(score, 15)

    def calculate_student_compatibility_score(
        self,
        cumulative_gpa: float,
        total_credits: int,
        failed_course_count: int
    ) -> int:
        score = 0

        if cumulative_gpa >= 8.0:
            score += 0
        elif cumulative_gpa >= 7.0:
            score += 3
        elif cumulative_gpa >= 6.0:
            score += 7
        elif cumulative_gpa >= 5.0:
            score += 11
        else:
            score += 15

        if total_credits >= 19:
            score += 3

        if failed_course_count >= 2:
            score += 3

        return min(score, 15)

    def classify_difficulty(self, score: int) -> Tuple[str, str]:
        if score <= 25:
            return "EASY", "Dễ"
        if score <= 45:
            return "MODERATE", "Khá nhẹ"
        if score <= 65:
            return "MEDIUM", "Trung bình"
        if score <= 80:
            return "HARD", "Khó"
        return "VERY_HARD", "Rất khó"

    def estimate_weekly_study_hours(self, courses) -> Dict[str, int]:
        total_credits = sum(
            c.credits if hasattr(c, 'credits') else self.course_data.get(c.code, {}).get('credit', 0)
            for c in courses
        )
        return {
            "min": round(total_credits * 1.5),
            "max": round(total_credits * 2.5)
        }

    def generate_difficulty_warnings(
        self,
        courses,
        student: StudentProfile,
        total_credits: int
    ) -> List[str]:
        warnings = []
        if total_credits > 18:
            warnings.append(f"Khối lượng {total_credits} tín chỉ tương đối cao.")

        programming_courses = [
            c for c in courses
            if self.course_data.get(c.code, {}).get("course_type") == "PROGRAMMING"
        ]

        if len(programming_courses) >= 3:
            prog_names = [c.name for c in programming_courses]
            warnings.append(f"Có {len(programming_courses)} môn lập trình trong cùng học kỳ, cần nhiều thời gian thực hành: {', '.join(prog_names)}.")

        failed_courses = set(self._normalize_course_code(c) for c in student.failed_courses)
        failed_courses = {EQUIVALENT_COURSES.get(c, c) for c in failed_courses}

        repeated_courses = [
            c.name for c in courses
            if c.code in failed_courses
        ]

        if repeated_courses:
            warnings.append("Có môn từng học chưa đạt, cần phân bổ thời gian ôn tập: " + ", ".join(repeated_courses) + ".")

        for course in courses:
            dependents = self.dependents_map.get(course.code, [])
            dependent_count = len(dependents)
            if dependent_count >= 4:
                dep_names = [self.course_data.get(dc, {}).get('name', dc) for dc in dependents]
                warnings.append(
                    f"{course.name} là môn nền tảng quan trọng, "
                    f"ảnh hưởng đến {dependent_count} môn phía sau: {', '.join(dep_names)}."
                )

        return warnings

    def generate_plan_strengths(self, courses, student: StudentProfile, total_credits: int) -> List[str]:
        strengths = []
        
        goal = student.study_goal.lower()

        if goal == "học vượt" and total_credits >= 18:
            strengths.append("Số tín chỉ cao, phù hợp mục tiêu học vượt.")
        elif goal == "đúng hạn" and 14 <= total_credits <= 18:
            strengths.append("Khối lượng tín chỉ rất phù hợp với tiến độ đúng hạn.")
            
        theory_courses = [
            c for c in courses
            if self.course_data.get(c.code, {}).get("course_type") in ["THEORY", "GENERAL"]
        ]
        if len(theory_courses) >= 2:
            strengths.append("Có môn lý thuyết/đại cương đan xen, giúp cân bằng khối lượng học.")
            
        return strengths

    def generate_plan_recommendation(self, score: int, warnings: List[str]) -> str:
        if score <= 45:
            return "Phương án nhẹ nhàng, sinh viên có thể dành thời gian cho các hoạt động ngoại khóa."
        if score <= 65:
            if len(warnings) > 0:
                return f"Phương án cân bằng. Chú ý: {warnings[0]}"
            return "Phương án cân bằng, rất phù hợp với tiến độ chuẩn."
        if score <= 80:
            return "Phương án khá nặng, yêu cầu phân bổ thời gian học tập nghiêm túc."
        return "Phương án rất nặng, chỉ nên chọn nếu bạn có quỹ thời gian học tập lớn."

    def analyze_plan_difficulty(
        self,
        plan_courses,
        student: StudentProfile
    ) -> Dict[str, Any]:
        total_credits = sum(
            c.credits if hasattr(c, 'credits') else self.course_data.get(c.code, {}).get('credit', 0)
            for c in plan_courses
        )

        credit_load_score = self.calculate_credit_load_score(total_credits)
        course_difficulty_score = self.calculate_course_difficulty_score(plan_courses)
        retake_risk_score = self.calculate_retake_risk_score(plan_courses, student)
        prerequisite_pressure_score = self.calculate_prerequisite_pressure_score(plan_courses)
        
        failed_count = len(student.failed_courses)
        cumulative_gpa = getattr(student, 'gpa_accumulated', 0.0)

        student_compatibility_score = self.calculate_student_compatibility_score(
            cumulative_gpa=cumulative_gpa,
            total_credits=total_credits,
            failed_course_count=failed_count
        )

        total_score = min(
            100,
            credit_load_score
            + course_difficulty_score
            + retake_risk_score
            + prerequisite_pressure_score
            + student_compatibility_score
        )

        level_code, level_label = self.classify_difficulty(total_score)
        warnings = self.generate_difficulty_warnings(plan_courses, student, total_credits)
        strengths = self.generate_plan_strengths(plan_courses, student, total_credits)
        weekly_hours = self.estimate_weekly_study_hours(plan_courses)

        return {
            "score": total_score,
            "level_code": level_code,
            "level_label": level_label,
            "estimated_weekly_hours": weekly_hours,
            "factors": {
                "credit_load_score": credit_load_score,
                "course_difficulty_score": course_difficulty_score,
                "retake_risk_score": retake_risk_score,
                "prerequisite_pressure_score": prerequisite_pressure_score,
                "student_compatibility_score": student_compatibility_score
            },
            "strengths": strengths,
            "warnings": warnings,
            "recommendation": self.generate_plan_recommendation(total_score, warnings)
        }

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
    
    def _random_select_electives(self,
                                courses: List[RecommendedCourse],
                                remaining_quotas: Dict[str, int],
                                study_goal: str,
                                rng: random.Random,
                                seed_offset: int = 0) -> List[RecommendedCourse]:
        """Giữ toàn bộ ứng viên cho beam search, thêm nhiễu mạnh cho môn tự chọn để tạo đa dạng khi có seed_offset."""
        candidates = list(courses)
        
        if seed_offset != 0:
            for c in candidates:
                if c.total_priority_score < 10000:
                    noise = rng.randint(0, 5000)
                    c.total_priority_score += noise
                    c.heuristic_score += noise

        rng.shuffle(candidates)
        candidates.sort(key=lambda x: (
            -x.total_priority_score,
            not x.is_retake,
            -x.heuristic_score,
        ))
        return candidates
    
    def _beam_search_optimize(self,
                             student: StudentProfile,
                             candidates: List[RecommendedCourse],
                             completed_counts: Dict[str, int],
                             study_goal: str,
                             rng: random.Random,
                             passed_courses: Set[str]) -> Tuple[List[RecommendedCourse], List[ExcludedCourse]]:
        """Tìm kiếm chùm thật sự, có kiểm tra song hành, quota và tín chỉ."""
        effective_max_credits = self.max_credits
            
        excluded: Dict[Tuple[str, str], ExcludedCourse] = {}
        eligible_codes = {c.code for c in candidates}
        course_index = {c.code: c for c in candidates}
        
        def resolve_coreq_bundle(code_: str) -> Optional[Set[str]]:
            bundle = set()
            stack = [code_]
            while stack:
                ccc = stack.pop()
                if ccc in bundle:
                    continue
                bundle.add(ccc)
                coreqs = self.course_data.get(ccc, {}).get('corequisites', [])
                for co in coreqs:
                    if co in passed_courses:
                        continue
                    if co not in eligible_codes:
                        return None
                    if co not in bundle:
                        stack.append(co)
            return bundle

        def remember_excluded(course_: RecommendedCourse, rule: str, reason: str):
            key = (course_.code, rule)
            if key in excluded:
                return
            excluded[key] = ExcludedCourse(
                code=course_.code,
                name=course_.name,
                credits=course_.credits,
                recommended_semester=course_.recommended_semester,
                reasons=[reason],
                failed_rules=[rule],
                stage="beam_search",
                is_specialization_course=bool(self.course_data.get(course_.code, {}).get('specializations')),
            )

        def quota_fill_score(counts: Dict[str, int]) -> int:
            score = 0
            for cat in ELECTIVE_QUOTA_KEYS:
                remaining_quota = max(0, self.elective_quotas.get(cat, 0) - completed_counts.get(cat, 0))
                score += min(counts.get(cat, 0), remaining_quota)
            return score

        def state_key(state: BeamSearchState) -> Tuple[float, int, int, float]:
            return (
                state.priority_score,
                quota_fill_score(state.elective_counts),
                state.credit,
                state.tie_break_random,
            )

        initial_state = BeamSearchState(tie_break_random=rng.random())
        beam = [initial_state]
        best_state = initial_state
        max_iterations = len(candidates)

        for _ in range(max_iterations):
            new_states: List[BeamSearchState] = []

            for state in beam:
                for course in candidates:
                    if course.code in state.selected_codes:
                        continue

                    bundle_codes = resolve_coreq_bundle(course.code)
                    if bundle_codes is None:
                        remember_excluded(
                            course,
                            "corequisite",
                            "thiếu học phần song hành trong tập môn đủ điều kiện",
                        )
                        continue

                    if bundle_codes & state.selected_codes:
                        continue

                    bundle_courses = [course_index[bc] for bc in bundle_codes]
                    bundle_credit = sum(c.credits for c in bundle_courses)
                    if state.credit + bundle_credit > effective_max_credits:
                        remember_excluded(
                            course,
                            "max_credits",
                            f"thêm học phần/bundle sẽ vượt giới hạn {effective_max_credits} tín chỉ (mục tiêu: {study_goal})",
                        )
                        continue

                    next_elective_counts = dict(state.elective_counts)
                    quota_ok = True
                    for bc in bundle_codes:
                        cat = self.course_data.get(bc, {}).get('elective_category')
                        if cat in ELECTIVE_QUOTA_KEYS:
                            next_elective_counts[cat] = next_elective_counts.get(cat, 0) + 1
                            remaining_quota = max(0, self.elective_quotas.get(cat, 0) - completed_counts.get(cat, 0))
                            if next_elective_counts[cat] > remaining_quota:
                                quota_ok = False
                                break

                    if not quota_ok:
                        remember_excluded(
                            course,
                            "elective_quota",
                            "Nhóm học phần tự chọn đã hoàn thành.",
                        )
                        continue

                    next_courses = list(state.selected_courses)
                    for bc in sorted(bundle_codes):
                        if bc not in state.selected_codes:
                            next_courses.append(course_index[bc])

                    new_states.append(BeamSearchState(
                        selected_codes=set(state.selected_codes) | set(bundle_codes),
                        selected_courses=next_courses,
                        credit=state.credit + bundle_credit,
                        priority_score=state.priority_score + sum(c.total_priority_score for c in bundle_courses),
                        elective_counts=next_elective_counts,
                        tie_break_random=rng.random(),
                    ))

            if not new_states:
                break

            beam = sorted(beam + new_states, key=state_key, reverse=True)[:self.beam_width]
            if state_key(beam[0]) > state_key(best_state):
                best_state = beam[0]

        selected = sorted(
            best_state.selected_courses,
            key=lambda c: (-c.total_priority_score, c.code),
        )
        selected_codes = {course.code for course in selected}
        final_excluded = [
            item for item in excluded.values()
            if item.code not in selected_codes
        ]
        return selected, final_excluded

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
    
    def get_prerequisite_chain(
        self,
        course_code: str,
        visited: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        """
        Trả về cây tiên quyết nhiều tầng của một môn học.
        """
        code = self._normalize_course_code(course_code)
        if visited is None:
            visited = set()

        if code in visited:
            return {
                "course_code": code,
                "course_name": self.course_data.get(code, {}).get("name", code),
                "cycle_detected": True,
                "prerequisites": [],
            }

        visited = set(visited)
        visited.add(code)

        course_info = self.course_data.get(code)
        if not course_info:
            return {
                "course_code": code,
                "course_name": code,
                "not_found": True,
                "prerequisites": [],
            }

        prerequisites = []
        for prereq_code in course_info.get("prereqs", []):
            prerequisites.append(
                self.get_prerequisite_chain(
                    prereq_code,
                    visited,
                )
            )

        return {
            "course_code": code,
            "course_name": course_info.get("name", code),
            "recommended_semester": course_info.get("recommended_sem"),
            "credits": course_info.get("credit", 0),
            "prerequisites": prerequisites,
        }

    def get_full_dependency_order(self, course_code: str) -> List[str]:
        """
        Trả về thứ tự học các môn bao gồm CẢ tổ tiên (tiên quyết) và con cháu (bị phụ thuộc),
        sắp xếp theo topological order.
        """
        code = self._normalize_course_code(course_code)
        
        # 1. Thu thập tổ tiên
        ancestors = set()
        def get_ancestors(curr: str):
            for p in self.course_data.get(curr, {}).get("prereqs", []):
                if p not in ancestors:
                    ancestors.add(p)
                    get_ancestors(p)
        get_ancestors(code)

        # 2. Thu thập con cháu
        descendants = set()
        def get_descendants(curr: str):
            for other_code, info in self.course_data.items():
                if curr in info.get("prereqs", []) and other_code not in descendants:
                    descendants.add(other_code)
                    get_descendants(other_code)
        get_descendants(code)

        related = ancestors | {code} | descendants

        # 3. Topological Sort trên tập related
        ordered: List[str] = []
        visited: Set[str] = set()
        processing: Set[str] = set()

        def dfs(curr: str):
            if curr not in related or curr in visited:
                return
            if curr in processing:
                self.logger.warning(f"Phát hiện vòng lặp trong chuỗi tiên quyết tại môn {curr}")
                return

            processing.add(curr)
            for prereq_code in self.course_data.get(curr, {}).get("prereqs", []):
                dfs(prereq_code)
            
            processing.remove(curr)
            visited.add(curr)
            ordered.append(curr)

        # Chạy DFS cho tất cả các môn trong tập related
        for c in related:
            if c not in visited:
                dfs(c)

        return ordered

    def analyze_prerequisite_path(
        self,
        course_code: str,
        student: Any, # StudentProfile
    ) -> Dict[str, Any]:
        """
        Tính toán chuỗi tiên quyết và gán trạng thái (completed/failed/available/locked).
        """
        passed_courses = set(student.passed_courses) if hasattr(student, 'passed_courses') else set()
        failed_courses = set(student.failed_courses) if hasattr(student, 'failed_courses') else set()

        ordered_codes = self.get_full_dependency_order(course_code)
        path = []
        critical_course = None

        for code in ordered_codes:
            info = self.course_data.get(code, {})
            prereqs = info.get("prereqs", [])

            if code in passed_courses:
                status = "completed"
                message = "Đã hoàn thành"
            elif code in failed_courses:
                status = "failed"
                message = "Chưa đạt, cần học lại"
                if critical_course is None:
                    critical_course = code
            elif all(prereq in passed_courses for prereq in prereqs):
                status = "available"
                message = "Đủ điều kiện đăng ký"
                if critical_course is None:
                    critical_course = code
            else:
                status = "locked"
                message = "Chưa đủ điều kiện (Thiếu môn tiên quyết)"

            # Check if this course is a descendant of the target_course
            # To do that simply, if it's after target_course in topological sort and not target, it's likely a descendant.
            # We can mark it as "Hậu quyết" or something, but the UI handles it naturally as it's after the target.
            
            path.append({
                "course_code": code,
                "course_name": info.get("name", code),
                "credits": info.get("credit", 0),
                "recommended_semester": info.get("recommended_sem"),
                "prerequisites": prereqs,
                "status": status,
                "message": message,
            })

        return {
            "target_course": course_code,
            "path": path,
            "critical_course": critical_course
        }

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
