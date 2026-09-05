"""Extracted existing behavior; operates on RecommendationEngine shared context."""

from typing import Dict, Any, List, Set, Optional
from rdflib import Graph, URIRef
from rdflib.namespace import RDF
from .constants import (
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
    ENGLISH_COURSE_CREDITS,
    ENGLISH_COURSE_PREREQUISITES,
    ENGLISH_COURSES,
    NON_GPA_ONE_CREDIT_COURSES,
    EQUIVALENT_COURSES,
)


class OntologyMixin:
    """Internal extraction boundary, not an independent Agent capability."""

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
