import argparse
import ast
import csv
import json
import os
import random
import sys
import io
import unicodedata
from datetime import datetime
from typing import Dict, Any, List, Set, Optional, cast
from rdflib import Graph, URIRef  # type: ignore
from rdflib.namespace import RDF  # type: ignore

# Fix UTF-8 output trên Windows terminal
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)

if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)

BASE_URI = "http://www.semanticweb.org/henrydao/ontologies/2025/7/TrainingProgramOntology#"

PROP_courseCode: Any = URIRef(BASE_URI + "courseCode")
PROP_courseName: Any = URIRef(BASE_URI + "courseName")
PROP_hasPrerequisiteCourse: Any = URIRef(BASE_URI + "hasPrerequisiteCourse")
PROP_openSemesterType: Any = URIRef(BASE_URI + "openSemesterType")
PROP_recommendedInSemester: Any = URIRef(BASE_URI + "recommendedInSemester")
PROP_specializationName: Any = URIRef(BASE_URI + "specializationName")
PROP_isRequiredForSpecialization: Any = URIRef(BASE_URI + "isRequiredForSpecialization")
PROP_isElectiveForSpecialization: Any = URIRef(BASE_URI + "isElectiveForSpecialization")
PROP_offeredInSpecialization: Any = URIRef(BASE_URI + "offeredInSpecialization")
PROP_isRequiredForMajor: Any = URIRef(BASE_URI + "isRequiredForMajor")
PROP_isElectiveForMajor: Any = URIRef(BASE_URI + "isElectiveForMajor")
PROP_hasCredit: Any = URIRef(BASE_URI + "hasCredit")
PROP_credit: Any = URIRef(BASE_URI + "credit")
PROP_corequisiteWith: Any = URIRef(BASE_URI + "corequisiteWith")
CLASS_Specialization: Any = URIRef(BASE_URI + "Specialization")
CLASS_GeneralEducationCourse: Any = URIRef(BASE_URI + "GeneralEducationCourse")
CLASS_PhysicalEducationCourse: Any = URIRef(BASE_URI + "PhysicalEducationCourse")
CLASS_FoundationCourse: Any = URIRef(BASE_URI + "FoundationCourse")

# Giới hạn số tín chỉ tối đa/tối thiểu cho một học kỳ
REGISTER_MAX_CREDITS = 27
REGISTER_MIN_CREDITS = 10

# Trọng số thuật toán ưu tiên khóa học
WEIGHT_DEBT = 1000      # W_debt
WEIGHT_LINK = 20        # W_link (môn có nhiều môn phụ thuộc hơn thì ưu tiên)
WEIGHT_DELAY = 50       # W_delay (môn trễ kỳ đề xuất sẽ ưu tiên)

STUDENT_ID_KEYS = ["mã sinh viên", "mã sinh vien", "ma sinh vien", "student_id", "id"]


def normalize_text(value: str) -> str:
    return ''.join(
        ch for ch in unicodedata.normalize('NFKD', value.lower().strip())
        if not unicodedata.combining(ch)
    )


def normalize_course_code(value: str) -> str:
    return value.strip().upper()


def safe_int(value: Any, default: int) -> int:
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


def resolve_default_paths() -> Dict[str, str]:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    workspace_root = os.path.dirname(script_dir)
    return {
        'json': os.path.join(workspace_root, 'data', 'DanhSachSinhVien.json'),
        'csv': os.path.join(workspace_root, 'data', 'DanhSachSinhVien.csv'),
        'rdf': os.path.join(workspace_root, 'owl', 'current', 'ontology_v19.rdf'),
        'output_dir': os.path.join(script_dir, 'outputs'),
    }


def normalize_student_id(value: str) -> str:
    v = value.strip().lower()
    return v.replace('sv', '')


def main(
    target_student_id: Optional[str] = None,
    json_path: Optional[str] = None,
    rdf_path: Optional[str] = None,
    csv_path: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> None:
    defaults = resolve_default_paths()
    json_path = json_path or defaults['json']
    rdf_path = rdf_path or defaults['rdf']
    csv_path = csv_path or defaults['csv']
    output_dir = output_dir or defaults['output_dir']

    # Yêu cầu người dùng nhập mã sinh viên nếu chưa có
    if target_student_id:
        target_student_id = target_student_id.strip()
    else:
        target_student_id = input("Nhập mã sinh viên cần tra cứu: ").strip()

    if not target_student_id:
        print("Vui lòng nhập mã sinh viên hợp lệ!")
        return

    if not os.path.exists(rdf_path):
        print(f"Không tìm thấy file ontology RDF: {rdf_path}")
        return

    os.makedirs(output_dir, exist_ok=True)

    run_ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = os.path.join(output_dir, f"recommend_courses_report_{target_student_id}_{run_ts}.txt")

    print(f"\nĐang đọc dữ liệu hồ sơ sinh viên từ {json_path}...")
    if not os.path.exists(json_path):
        print("Không tìm thấy file JSON danh sách sinh viên!")
        return
        
    with open(json_path, 'r', encoding='utf-8') as f:
        students = json.load(f)
    if not isinstance(students, list):
        print("Dữ liệu JSON không đúng định dạng danh sách sinh viên.")
        return
        
    # Tìm sinh viên
    target_student_raw = None
    normalized_target_id = normalize_student_id(target_student_id)

    for s in students:
        if not isinstance(s, dict):
            continue
        student_code = None
        for key in STUDENT_ID_KEYS:
            if key in s and s.get(key) is not None:
                student_code = str(s.get(key)).strip()
                break
        if not student_code:
            continue
        if normalize_student_id(student_code) == normalized_target_id:
            target_student_raw = s
            break

    if target_student_raw is None:
        # Fallback: đọc từ CSV nếu JSON không có
        if os.path.exists(csv_path):
            with open(csv_path, newline='', encoding='utf-8') as fcsv:
                reader = csv.DictReader(fcsv)
                for row in reader:
                    row_code = None
                    for key in STUDENT_ID_KEYS:
                        if row.get(key):
                            row_code = str(row.get(key)).strip()
                            break
                    if not row_code:
                        continue
                    if normalize_student_id(row_code) == normalized_target_id:
                        target_student_raw = dict(row)
                        break
            if target_student_raw is not None:
                print(f"Đã tìm thấy SV {target_student_id} trong CSV (fallback), sẽ tự động thêm vào JSON để lần sau lấy nhanh.")
                # chuyển kiểu dữ liệu trường danh sách từ string sang structure
                for key in ['danh sách môn đã học', 'điểm từng môn', 'danh sách môn chưa đạt']:
                    if key in target_student_raw and isinstance(target_student_raw[key], str) and target_student_raw[key].strip():
                        try:
                            target_student_raw[key] = ast.literal_eval(target_student_raw[key])
                        except Exception:
                            pass
                # thêm vào JSON để đỡ phải nhập lại
                if isinstance(students, list):
                    students.append(target_student_raw)
                    try:
                        with open(json_path, 'w', encoding='utf-8') as fw:
                            json.dump(students, fw, ensure_ascii=False, indent=4)
                        print(f"Đã ghi thêm SV {target_student_id} vào {json_path}")
                    except Exception as e:
                        print("Không thể ghi vào JSON:", e)

        if target_student_raw is None:
            print(f"Không tìm thấy sinh viên với mã '{target_student_id}'. Vui lòng kiểm tra lại mã và dữ liệu JSON/CSV.")
            print("Các mã sinh viên khả dụng (một số):")
            cnt = 0
            for s in students:
                if not isinstance(s, dict):
                    continue
                candidate = None
                for key in STUDENT_ID_KEYS:
                    if s.get(key):
                        candidate = s.get(key)
                        break
                if candidate:
                    print(" -", candidate)
                    cnt += 1
                    if cnt >= 20:
                        break
            return
        
    target_student = cast(Dict[str, Any], target_student_raw)
    g: Any = Graph()
    g.parse(rdf_path, format="xml")
    
    # 1. Trích xuất thông tin môn học và chuyên ngành
    # Tìm tên các chuyên ngành
    specializations_map: Dict[str, str] = {}
    for spec in g.subjects(RDF.type, CLASS_Specialization):
        if isinstance(spec, URIRef):
            val = g.value(spec, PROP_specializationName)
            if val is not None:
                specializations_map[str(spec)] = str(val)
        
    course_data: Dict[str, Dict[str, Any]] = {}
    for course in g.subjects(PROP_courseCode, None):
        code_val_node = g.value(course, PROP_courseCode)
        if code_val_node is None:
            continue
        code = normalize_course_code(str(code_val_node))
        if not code:
            continue
        
        name_val = g.value(course, PROP_courseName)
        name = str(name_val) if name_val is not None else code
        
        prereqs: List[str] = []
        for p in g.objects(course, PROP_hasPrerequisiteCourse):
            p_code = g.value(p, PROP_courseCode)
            if p_code is not None:
                normalized_pr = normalize_course_code(str(p_code))
                if normalized_pr:
                    prereqs.append(normalized_pr)
                
        open_sem = g.value(course, PROP_openSemesterType)
        open_sem_val = safe_int(open_sem, 3)
        
        # Học kỳ khuyến nghị
        recommended_sem_val = 99999
        sem_uri = g.value(course, PROP_recommendedInSemester)
        if sem_uri is not None:
            sem_str = str(sem_uri).split('#')[-1] 
            if sem_str.startswith("Semester"):
                try:
                    recommended_sem_val = int(sem_str.replace("Semester", ""))
                except ValueError:
                    pass
                    
        # Lấy thông tin môn học thuộc chuyên ngành nào
        linked_specializations: Set[str] = set()
        is_required_for_specialization = False
        is_elective_for_specialization = False
        is_offered_specialization = False
        for spec_uri in g.objects(course, PROP_isRequiredForSpecialization):
            is_required_for_specialization = True
            if isinstance(spec_uri, URIRef):
                spec_name = specializations_map.get(str(spec_uri))
                if spec_name:
                    linked_specializations.add(spec_name)
        for spec_uri in g.objects(course, PROP_isElectiveForSpecialization):
            is_elective_for_specialization = True
            if isinstance(spec_uri, URIRef):
                spec_name = specializations_map.get(str(spec_uri))
                if spec_name:
                    linked_specializations.add(spec_name)
        for spec_uri in g.objects(course, PROP_offeredInSpecialization):
            is_offered_specialization = True
            if isinstance(spec_uri, URIRef):
                spec_name = specializations_map.get(str(spec_uri))
                if spec_name:
                    linked_specializations.add(spec_name)

        # Xét môn song hành nếu ontology đã có corequisiteWith
        coreqs: List[str] = []
        for co in g.objects(course, PROP_corequisiteWith):
            if isinstance(co, URIRef):
                coreq_code = g.value(co, PROP_courseCode)
                if coreq_code is not None:
                    normalized_coreq = normalize_course_code(str(coreq_code))
                    if normalized_coreq:
                        coreqs.append(normalized_coreq)

        # Lấy tín chỉ
        credits_val = g.value(course, PROP_hasCredit)
        if credits_val is None:
            credits_val = g.value(course, PROP_credit)
        credits = 0
        if credits_val is not None:
            try:
                # Có thể là Literal('3.0'), Literal('3') ...
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

        # Xác định loại môn
        is_general_education = any(str(t).endswith('#GeneralEducationCourse') for t in g.objects(course, RDF.type))
        is_physical_education = any(str(t).endswith('#PhysicalEducationCourse') for t in g.objects(course, RDF.type))
        is_foundation_course = any(str(t).endswith('#FoundationCourse') for t in g.objects(course, RDF.type))

        is_required_for_major = any(True for _ in g.objects(course, PROP_isRequiredForMajor))
        is_elective_for_major = any(True for _ in g.objects(course, PROP_isElectiveForMajor))

        # Phân loại độ ưu tiên / đại cương
        course_data[code] = {
            'name': name,
            'prereqs': prereqs,
            'openSemesterType': open_sem_val,
            'recommended_sem': recommended_sem_val,
            'specializations': list(linked_specializations),
            'is_required_specialization': is_required_for_specialization,
            'is_elective_specialization': is_elective_for_specialization,
            'is_offered_specialization': is_offered_specialization,
            'is_required_major': is_required_for_major,
            'is_elective_major': is_elective_for_major,
            'is_general_education_course': is_general_education,
            'is_physical_education_course': is_physical_education,
            'is_foundation_course': is_foundation_course,
            'corequisites': coreqs,
            'credit': credits,
            'elective_category': None  # Sẽ được gán sau
        }
        
    print(f"Đã tải {len(course_data)} môn học.")

    # Tính số môn phụ thuộc (DoPhu), dựa vào danh sách prerequisite của các môn khác
    dependency_count: Dict[str, int] = {code: 0 for code in course_data.keys()}
    for cinfo in course_data.values():
        for pr in cinfo.get('prereqs', []):
            if pr in dependency_count:
                dependency_count[pr] += 1

    # 2. Xử lý cho sinh viên được chọn
    current_sem = safe_int(target_student.get("học kỳ hiện tại", 1), 1)
    current_sem = max(1, current_sem)
        
    next_sem = current_sem + 1
    sem_type = 1 if next_sem % 2 != 0 else 2
    
    student_spec = target_student.get("chuyên ngành chọn") or target_student.get("chuyên ngành", "")
    if not isinstance(student_spec, str):
        student_spec = ""
    student_spec = student_spec.strip()
    normalized_student_spec = normalize_text(student_spec) if student_spec else ""
    raw_study_goal = str(target_student.get('mục tiêu học tập', '')).strip()
    normalized_study_goal = normalize_text(raw_study_goal)
    study_goal_mapping = {
        'dung han': 'đúng hạn',
        'giam tai': 'giảm tải',
        'hoc vuot': 'học vượt',
    }
    study_goal_value = study_goal_mapping.get(normalized_study_goal, 'đúng hạn')

    rng = random.Random(f"{target_student_id}-{current_sem}-{next_sem}")

    print(f"\nSinh viên {target_student.get('tên sinh viên', '')} đang ở học kỳ {current_sem}, chuẩn bị đăng ký cho học kỳ {next_sem} (Loại học kỳ: {'Lẻ' if sem_type == 1 else 'Chẵn'})")
    print(f"Chuyên ngành đã đăng ký: {student_spec if student_spec else 'Chưa chọn'}")
    
    passed_courses: Set[str] = set()
    failed_courses: Set[str] = set()

    diem_tung_mon = target_student.get("điểm từng môn", [])
    if isinstance(diem_tung_mon, list):
        for c in diem_tung_mon:
            if isinstance(c, dict):
                m = c.get("mã môn học")
                if not m or not isinstance(m, str):
                    continue
                if c.get("Trạng thái") == "Đạt":
                    passed_courses.add(normalize_course_code(m))

    # Dữ liệu thực tế có thể lệch mã ở "điểm từng môn"; bổ sung nguồn từ "danh sách môn đã học"
    ds_da_hoc = target_student.get("danh sách môn đã học", {})
    if isinstance(ds_da_hoc, dict):
        for code in ds_da_hoc.keys():
            if isinstance(code, str) and code.strip():
                passed_courses.add(normalize_course_code(code))
    elif isinstance(ds_da_hoc, list):
        for item in ds_da_hoc:
            if not isinstance(item, dict):
                continue
            code = item.get("mã môn học")
            if isinstance(code, str) and code.strip():
                passed_courses.add(code.strip())

    ds_chua_dat = target_student.get("danh sách môn chưa đạt", [])
    if isinstance(ds_chua_dat, list):
        for c in ds_chua_dat:
            if isinstance(c, dict):
                m = c.get("mã môn học")
                if m and isinstance(m, str):
                    failed_courses.add(normalize_course_code(m))

    # Tránh trường hợp một mã vừa nằm trong đã học vừa nằm trong chưa đạt
    passed_courses -= failed_courses

    internship_course_codes = {'INT6900', 'SOT348'}

    unknown_passed = sorted([code for code in passed_courses if code not in course_data])
    unknown_failed = sorted([code for code in failed_courses if code not in course_data])
    if unknown_passed or unknown_failed:
        print("Cảnh báo: có mã môn trong hồ sơ sinh viên không tồn tại trong ontology.")
        if unknown_passed:
            print(" - Không khớp (đã học):", ', '.join(unknown_passed[:10]))
        if unknown_failed:
            print(" - Không khớp (chưa đạt):", ', '.join(unknown_failed[:10]))

    passed_courses = {code for code in passed_courses if code in course_data}
    failed_courses = {code for code in failed_courses if code in course_data}
            
    valid_courses: List[Dict[str, Any]] = []
    
    for code, info in course_data.items():
        # Bỏ qua nếu đã đạt
        if code in passed_courses:
            continue

        # Kiểm tra môn tiên quyết
        prereqs_met = True
        for p in info.get('prereqs', []):
            if p in passed_courses:
                continue
            # Nếu tiên quyết bị rớt thì chưa đủ điều kiện đăng ký môn phụ thuộc
            if p in failed_courses:
                prereqs_met = False
                break
            prereqs_met = False
            break

        # Kiểm tra học kỳ mở môn (1: Lẻ, 2: Chẵn, 3: Cả hai, 12: Cả hai)
        open_sem_info = info.get('openSemesterType', 3)
        sem_ok = (open_sem_info in (3, 12) or open_sem_info == sem_type)

        # Kiểm tra học kỳ khuyến nghị:
        # - Học vượt: cho phép cả môn kỳ khuyến nghị tương lai nếu đủ tiên quyết và mở đúng kỳ
        # - Mục tiêu khác: giữ điều kiện môn khuyến nghị từ kỳ hiện tại trở về trước
        rec_sem_info = info.get('recommended_sem', 99)
        recommended_ok = True if study_goal_value == 'học vượt' else (rec_sem_info <= next_sem)

        # Ràng buộc cứng theo yêu cầu nghiệp vụ
        # 1) Môn có kỳ khuyến nghị 8: chỉ gợi ý khi đăng ký kỳ 8
        # 2) Môn thực tập ngành: chỉ gợi ý khi đăng ký kỳ 7
        course_name_norm = normalize_text(str(info.get('name', '')))
        is_internship_course = (code in internship_course_codes) or ('thuc tap nganh' in course_name_norm)
        forced_semester_ok = True
        if rec_sem_info == 8:
            forced_semester_ok = (next_sem == 8)
        if is_internship_course:
            forced_semester_ok = (next_sem == 7)

        # Môn trượt có thể đăng ký học lại nếu được mở
        is_retake = (code in failed_courses)

        # Xử lý trường hợp sinh viên chưa chọn chuyên ngành
        spec_ok = True
        specs: List[str] = info.get('specializations', [])
        if student_spec:
            normalized_specs = [normalize_text(s) for s in specs if isinstance(s, str)]

            if specs and normalized_student_spec not in normalized_specs:
                spec_ok = False
        else:
            # sinh viên chưa chọn chuyên ngành: cho phép đại cương (không chuyên ngành) và cơ sở ngành (bắt buộc chuyên ngành)
            if specs and not info.get('is_required_specialization', False):
                spec_ok = False

        # Lọc môn quá tải tín chỉ cá nhân (nếu có môn > 27 tín chỉ bị lỗi dữ liệu, bỏ luôn)
        if info.get('credit', 0) > REGISTER_MAX_CREDITS:
            continue

        if prereqs_met and sem_ok and (recommended_ok or is_retake) and spec_ok and forced_semester_ok:
            debt_score = 1 if is_retake else 0
            link_score = dependency_count.get(code, 0)
            delay_score = max(0, current_sem - rec_sem_info)
            heuristic_H = (debt_score * WEIGHT_DEBT) + (link_score * WEIGHT_LINK) + (delay_score * WEIGHT_DELAY)

            open_now_score = 1 if sem_ok else 0
            rec_gap = abs(next_sem - rec_sem_info) if rec_sem_info < 999 else 999
            rec_proximity_score = max(0, 10 - rec_gap)

            if study_goal_value == 'đúng hạn':
                goal_score = 30
            elif study_goal_value == 'giảm tải':
                goal_score = 20
            elif study_goal_value == 'học vượt':
                goal_score = 10
            else:
                goal_score = 0

            priority_score = heuristic_H + (open_now_score * 50) + (rec_proximity_score * 10) + goal_score

            reasons = []
            if is_retake:
                reasons.append('môn học lại')
            if info.get('is_required_major', False) or info.get('is_required_specialization', False):
                reasons.append('môn bắt buộc')
            elif info.get('is_elective_major', False) or info.get('is_elective_specialization', False):
                reasons.append('môn tự chọn')
            elif info.get('is_foundation_course', False):
                # foundation là dạng cơ sở ngành; nếu chưa gắn loại thì coi là tự chọn
                reasons.append('môn tự chọn cơ sở ngành')
            if open_now_score:
                reasons.append('mở đúng học kỳ hiện tại')
            if rec_gap == 0:
                reasons.append('đúng học kỳ khuyến nghị')
            if student_spec and normalized_student_spec in [normalize_text(s) for s in specs if isinstance(s, str)]:
                reasons.append('phù hợp chuyên ngành')

            valid_courses.append({
                "mã môn học": code,
                "tên môn học": info.get('name', ''),
                "là môn học lại": is_retake,
                "học kỳ đề xuất": rec_sem_info,
                "thuộc chuyên ngành": specs,
                "tín chỉ": info.get('credit', 0),
                "corequisites": info.get('corequisites', []),
                "điểm nợ môn": debt_score,
                "điểm kết nối": link_score,
                "điểm trễ": delay_score,
                "điểm ưu tiên": heuristic_H,
                "mở đúng kỳ": open_now_score,
                "độ gần kỳ đề xuất": rec_proximity_score,
                "điểm mục tiêu": goal_score,
                "điểm tổng ưu tiên": priority_score,
                "lý do": reasons
            })

    # Ưu tiên theo điểm tổng (H + mở kỳ + gần kỳ đề xuất + mục tiêu học tập)
    valid_courses.sort(key=lambda x: (
        -x.get("điểm tổng ưu tiên", 0),
        not x.get("là môn học lại", False),
        -x.get("mở đúng kỳ", 0),
        -x.get("độ gần kỳ đề xuất", 0),
        x.get("học kỳ đề xuất", 99)
    ))

    # Phân loại danh mục tự chọn cho mỗi môn
    def categorize_elective(course_code: str, course_info: Dict[str, Any]) -> Optional[str]:
        """Phân loại môn vào danh mục tự chọn: general, physical, foundation, specialization"""
        is_gen = course_info.get('is_general_education_course', False)
        is_phy = course_info.get('is_physical_education_course', False)
        is_fnd = course_info.get('is_foundation_course', False)
        is_elec = course_info.get('is_elective_major', False) or course_info.get('is_elective_specialization', False)
        
        if not is_elec:
            return None  # Không phải tự chọn
        
        if is_phy:
            return 'physical'
        elif is_fnd:
            return 'foundation'
        elif is_gen:
            return 'general'
        else:
            return 'specialization'
    
    # Ghi nhớ các danh mục trong course_data
    for code, info in course_data.items():
        info['elective_category'] = categorize_elective(code, info)
    
    # Chia nhóm: bắt buộc / core cơ sở ngành (tự chọn) / đại cương tự chọn / thể chất tự chọn / còn lại
    required_courses = []
    required_foundation_courses = []
    elective_foundation_courses = []
    general_electives = []
    physical_electives = []
    specialization_electives = []
    other_courses = []

    for c in valid_courses:
        code_ = c['mã môn học']
        info = course_data.get(code_, {})

        # Kiểm tra xem có phải môn bắt buộc không
        is_required = (
            c.get('là môn học lại', False)
            or info.get('is_required_specialization', False)
            or info.get('is_required_major', False)
        )

        # Nếu là một phần của nền tảng bắt buộc
        if info.get('is_foundation_course', False) and is_required:
            required_foundation_courses.append(c)
            continue

        # Nếu là môn bắt buộc, thêm vào required_courses
        if is_required:
            required_courses.append(c)
            continue

        # Xử lý các môn tự chọn
        elec_cat = info.get('elective_category')
        
        if elec_cat == 'foundation':
            elective_foundation_courses.append(c)
        elif elec_cat == 'general':
            general_electives.append(c)
        elif elec_cat == 'physical':
            physical_electives.append(c)
        elif elec_cat == 'specialization':
            specialization_electives.append(c)
        else:
            # Trường hợp cùng không phải tự chọn và không bắt buộc
            other_courses.append(c)

    ELECTIVE_QUOTA_KEYS = ('general', 'physical', 'foundation', 'specialization')

    elective_target_counts: Dict[str, int] = {
        'general': 1,
        'physical': 2,
        'foundation': 1,
        'specialization': 3,
    }

    if study_goal_value == 'học vượt':
        # Với mục tiêu học vượt: có thể gợi ý 2-3 môn tự chọn chuyên ngành
        elective_target_counts['specialization'] = 3

    # Với mục tiêu đúng hạn/giảm tải: tổ hợp cuối cùng chỉ lấy tối đa 1 môn tự chọn
    strict_single_elective_in_final = study_goal_value in ('đúng hạn', 'giảm tải')

    # Đếm số môn tự chọn đã hoàn thành theo nhóm để tính quota còn thiếu
    completed_elective_counts: Dict[str, int] = {k: 0 for k in ELECTIVE_QUOTA_KEYS}
    for code_ in passed_courses:
        info_done = course_data.get(code_, {})
        done_cat = info_done.get('elective_category')
        if done_cat in ELECTIVE_QUOTA_KEYS:
            completed_elective_counts[str(done_cat)] += 1

    remaining_elective_counts: Dict[str, int] = {
        k: max(0, elective_target_counts.get(k, 0) - completed_elective_counts.get(k, 0))
        for k in ELECTIVE_QUOTA_KEYS
    }

    def elective_category_of_code(code_: str) -> Optional[str]:
        info = course_data.get(code_, {})
        cat = info.get('elective_category')
        if cat in ELECTIVE_QUOTA_KEYS:
            return str(cat)
        return None

    # Tập môn hợp lệ đưa vào beam: chỉ giữ môn tự chọn ở các nhóm còn thiếu quota
    selected_candidates_raw = (
        list(required_courses)
        + list(required_foundation_courses)
        + list(elective_foundation_courses)
        + list(general_electives)
        + list(physical_electives)
        + list(specialization_electives)
        + list(other_courses)
    )

    selected_candidates: List[Dict[str, Any]] = []
    for item in selected_candidates_raw:
        code_ = item.get('mã môn học', '')
        cat = elective_category_of_code(code_)
        if cat is not None and remaining_elective_counts.get(cat, 0) <= 0:
            continue
        selected_candidates.append(item)

    # Khử trùng lặp theo mã môn cho tập hợp lệ (dùng để in báo cáo đầu vào)
    unique_candidates: Dict[str, Dict[str, Any]] = {}
    for item in selected_candidates:
        unique_candidates[item['mã môn học']] = item
    selected_candidates = list(unique_candidates.values())

    # Yêu cầu nghiệp vụ: tập môn hợp lệ phải in ra đầy đủ (không random ở bước này)
    eligible_courses = list(selected_candidates)

    # Random chỉ áp dụng cho tổ hợp cuối cùng (beam search)
    beam_candidates = list(selected_candidates)

    # Random hóa chọn môn tự chọn khi chỉ còn thiếu 1 môn nhưng có nhiều môn hợp lệ
    # để tránh luôn ra cùng một môn ở tổ hợp cuối.
    if strict_single_elective_in_final:
        elective_pool = [
            c for c in beam_candidates
            if elective_category_of_code(c.get('mã môn học', '')) is not None
        ]
        specialization_pool = [
            c for c in elective_pool
            if elective_category_of_code(c.get('mã môn học', '')) == 'specialization'
        ]
        if len(elective_pool) > 1:
            # Ưu tiên tự chọn chuyên ngành nếu có
            pool_to_choose = specialization_pool if len(specialization_pool) > 0 else elective_pool
            chosen_elective = rng.choice(pool_to_choose)
            beam_candidates = [
                c for c in beam_candidates
                if elective_category_of_code(c.get('mã môn học', '')) is None
            ] + [chosen_elective]
    else:
        for cat_key in ELECTIVE_QUOTA_KEYS:
            remain = remaining_elective_counts.get(cat_key, 0)
            if remain <= 0:
                continue
            cat_pool = [
                c for c in beam_candidates
                if elective_category_of_code(c.get('mã môn học', '')) == cat_key
            ]
            if len(cat_pool) > remain:
                chosen_cat_courses = rng.sample(cat_pool, remain)
                beam_candidates = [
                    c for c in beam_candidates
                    if elective_category_of_code(c.get('mã môn học', '')) != cat_key
                ] + chosen_cat_courses

    rng.shuffle(beam_candidates)

    eligible_codes = {c['mã môn học'] for c in beam_candidates}
    course_index = {c['mã môn học']: c for c in beam_candidates}

    student_max_credit = REGISTER_MAX_CREDITS
    student_request_max = safe_int(target_student.get('số tín chỉ đăng ký tối đa', REGISTER_MAX_CREDITS), REGISTER_MAX_CREDITS)
    student_max_credit = min(REGISTER_MAX_CREDITS, max(REGISTER_MIN_CREDITS, student_request_max))

    def resolve_coreq_bundle(code_: str) -> Optional[Set[str]]:
        bundle = set()
        stack = [code_]
        while stack:
            ccc = stack.pop()
            if ccc in bundle:
                continue
            bundle.add(ccc)
            coreqs = course_data.get(ccc, {}).get('corequisites', [])
            for co in coreqs:
                if co in passed_courses:
                    continue
                if co not in eligible_codes:
                    return None
                if co not in bundle:
                    stack.append(co)
        return bundle

    def add_elective_counts(base_counts: Dict[str, int], codes: Set[str]) -> Dict[str, int]:
        new_counts = dict(base_counts)
        for code_ in codes:
            cat = elective_category_of_code(code_)
            if cat is None:
                continue
            new_counts[cat] = new_counts.get(cat, 0) + 1
        return new_counts

    def within_elective_quota(counts: Dict[str, int]) -> bool:
        for key in ELECTIVE_QUOTA_KEYS:
            if counts.get(key, 0) > remaining_elective_counts.get(key, 0):
                return False
        if strict_single_elective_in_final and sum(counts.get(k, 0) for k in ELECTIVE_QUOTA_KEYS) > 1:
            return False
        return True

    def quota_fill_score(counts: Dict[str, int]) -> int:
        if strict_single_elective_in_final:
            return min(sum(counts.get(k, 0) for k in ELECTIVE_QUOTA_KEYS), 1)
        score = 0
        for key in ELECTIVE_QUOTA_KEYS:
            score += min(counts.get(key, 0), remaining_elective_counts.get(key, 0))
        return score

    # Beam Search để chọn tổ hợp khóa học tốt nhất
    beam_width = 8

    initial_state = {
        'selected_codes': set(),
        'selected_courses': [],
        'credit': 0,
        'score': 0.0,
        'elective_counts': {k: 0 for k in ELECTIVE_QUOTA_KEYS},
        'tie_break': rng.random(),
    }

    beam = [initial_state]
    best_state = initial_state

    while True:
        new_beam = []
        improved = False

        for state in beam:
            remaining = [c for c in beam_candidates if c['mã môn học'] not in state['selected_codes']]
            rng.shuffle(remaining)
            for c in remaining:
                bundle_codes = resolve_coreq_bundle(c['mã môn học'])
                if bundle_codes is None:
                    continue
                bundle_codes = {x for x in bundle_codes if x not in state['selected_codes']}
                bundle_credit = sum(course_data.get(x, {}).get('credit', 0) for x in bundle_codes)
                next_elective_counts = add_elective_counts(state.get('elective_counts', {}), bundle_codes)

                if state['credit'] + bundle_credit > student_max_credit:
                    continue
                if not within_elective_quota(next_elective_counts):
                    continue

                next_credit = state['credit'] + bundle_credit
                next_selected_codes = state['selected_codes'] | bundle_codes
                next_selected_courses = list(state['selected_courses'])
                next_score = state['score']

                for code_ in bundle_codes:
                    course_item = course_index.get(code_)
                    if course_item is not None:
                        next_selected_courses.append(course_item)
                        next_score += course_item.get('điểm tổng ưu tiên', 0)

                next_state = {
                    'selected_codes': next_selected_codes,
                    'selected_courses': next_selected_courses,
                    'credit': next_credit,
                    'score': next_score,
                    'elective_counts': next_elective_counts,
                    'tie_break': rng.random(),
                }

                new_beam.append(next_state)
                improved = True

        if not improved:
            break

        # Thêm cả các state cũ để Beam không bị mất tùy chọn không thêm
        new_beam.extend(beam)

        # Giữ beam_width phương án tốt nhất theo mức độ đáp ứng quota tự chọn + điểm + credit
        beam = sorted(
            new_beam,
            key=lambda x: (quota_fill_score(x.get('elective_counts', {})), x['score'], x['credit'], x.get('tie_break', 0.0)),
            reverse=True
        )[:beam_width]

        # Cập nhật best_state: ưu tiên đáp ứng quota tự chọn, sau đó mới đến điểm và tín chỉ
        top_state = max(beam, key=lambda x: (quota_fill_score(x.get('elective_counts', {})), x['score'], x['credit'], x.get('tie_break', 0.0)))
        if (
            quota_fill_score(top_state.get('elective_counts', {})) > quota_fill_score(best_state.get('elective_counts', {}))
            or (
                quota_fill_score(top_state.get('elective_counts', {})) == quota_fill_score(best_state.get('elective_counts', {}))
                and (
                    top_state['score'] > best_state['score']
                    or (top_state['score'] == best_state['score'] and top_state['credit'] > best_state['credit'])
                )
            )
        ):
            best_state = top_state

    # Chọn kết quả ban đầu từ beam
    selected_courses = list(best_state['selected_courses'])
    total_credit = best_state['credit']

    # Chống trùng trong kết quả cuối nếu có do quá trình mở rộng state
    unique_selected: Dict[str, Dict[str, Any]] = {}
    for c in selected_courses:
        unique_selected[c['mã môn học']] = c
    selected_courses = list(unique_selected.values())
    total_credit = sum(c.get('tín chỉ', 0) for c in selected_courses)

    # Cứng chắc: bắt buộc tổng tín chỉ tổ hợp không vượt 27
    if total_credit > student_max_credit:
        selected_courses = [c for c in selected_courses if c.get('tín chỉ', 0) <= student_max_credit]
        total_credit = sum(c.get('tín chỉ', 0) for c in selected_courses)

    # Nếu dưới ngưỡng tối thiểu, bổ sung greedily từ ứng viên còn lại (vẫn giữ mọi ràng buộc)
    selected_codes = {c['mã môn học'] for c in selected_courses}
    selected_elective_counts = {k: 0 for k in ELECTIVE_QUOTA_KEYS}
    for code_ in selected_codes:
        cat = elective_category_of_code(code_)
        if cat is not None:
            selected_elective_counts[cat] += 1

    if total_credit < REGISTER_MIN_CREDITS:
        remaining_sorted = sorted(
            [c for c in beam_candidates if c['mã môn học'] not in selected_codes],
            key=lambda x: x.get('điểm tổng ưu tiên', 0),
            reverse=True,
        )
        for c in remaining_sorted:
            if total_credit >= REGISTER_MIN_CREDITS:
                break
            bundle_codes = resolve_coreq_bundle(c['mã môn học'])
            if bundle_codes is None:
                continue
            bundle_codes = {x for x in bundle_codes if x not in selected_codes}
            if not bundle_codes:
                continue
            bundle_credit = sum(course_data.get(x, {}).get('credit', 0) for x in bundle_codes)
            next_elective_counts = add_elective_counts(selected_elective_counts, bundle_codes)
            if total_credit + bundle_credit > student_max_credit:
                continue
            if not within_elective_quota(next_elective_counts):
                continue
            for code_ in bundle_codes:
                course_item = course_index.get(code_)
                if course_item is not None:
                    selected_courses.append(course_item)
                    selected_codes.add(code_)
            selected_elective_counts = next_elective_counts
            total_credit += bundle_credit

    # Kết quả cuối lấy trực tiếp từ beam search (đã ràng buộc quota tự chọn còn thiếu)
    valid_courses = sorted(selected_courses, key=lambda c: c.get('điểm tổng ưu tiên', 0), reverse=True)
    total_credit = sum(c.get('tín chỉ', 0) for c in valid_courses)

    # Chuẩn bị giá trị in báo cáo
    student_major = target_student.get("ngành", "Công Nghệ Thông Tin")
    spec_display = student_spec if student_spec else 'Chưa chọn chuyên ngành'
    total_selected_credits = sum(c.get('tín chỉ', 0) for c in valid_courses)

    # Xuất báo cáo chi tiết ra file text
    with open(report_path, 'w', encoding='utf-8') as report:
        report.write('=== BÁO CÁO GỢI Ý KẾ HOẠCH HỌC TẬP ===\n')
        report.write(f"Mã sinh viên: {target_student_id}\n")
        report.write(f"Tên: {target_student.get('tên sinh viên', '')}\n")
        report.write(f"Ngành: {student_major}\n")
        report.write(f"Chuyên ngành: {spec_display}\n")
        report.write(f"Học kỳ hiện tại: {current_sem}, học kỳ đăng ký: {next_sem}\n")
        report.write(f"Mục tiêu học: {study_goal_value}\n")
        report.write('---\n')

        report.write('1. Tập môn hợp lệ (đầu vào)\n')
        report.write('Mỗi môn: [H = debt*1000 + doPhu*20 + doTre*50] + [H_total thêm open/rec/goal] \n')
        for c in eligible_courses:
            h = c.get('điểm ưu tiên', 0)
            total = c.get('điểm tổng ưu tiên', 0)
            reasons = c.get('lý do', [])
            report.write(f"- {c['mã môn học']} {c['tên môn học']} ({c.get('tín chỉ', 0)} TIC) H={h}, H_total={total}, Lý do: {', '.join(reasons)}\n")
        report.write('---\n')

        report.write('2. Tổ hợp môn cuối cùng (beam search chọn)\n')
        report.write(f"Tổng số môn hợp lệ có thể đăng ký: {len(valid_courses)}\n")
        report.write(f"Tổng số tín chỉ của các môn đã liệt kê: {total_selected_credits}\n")
        report.write(f"Tổng tín chỉ: {total_credit}\n")
        for c in valid_courses:
            h = c.get('điểm ưu tiên', 0)
            total = c.get('điểm tổng ưu tiên', 0)
            reasons = c.get('lý do', [])
            report.write(f"* {c['mã môn học']} {c['tên môn học']} ({c.get('tín chỉ', 0)} TIC) H_total={total}, Lý do: {', '.join(reasons)}\n")
        report.write('---\n')

        report.write('3. Giải thích quy trình beam search đã dùng\n')
        report.write('- Beam width = 8\n')
        report.write('- Mỗi state lưu selected_codes, credit, score, elective_counts\n')
        report.write('- Mỗi lần mở rộng thêm 1 môn hoặc bundle corequisite nếu không vượt max credit\n')
        report.write('- Ràng buộc cứng: môn kỳ khuyến nghị 8 chỉ gợi ý ở kỳ 8; môn thực tập ngành chỉ gợi ý ở kỳ 7\n')
        report.write(f"- Quota tự chọn theo nhóm (mục tiêu): đại cương={elective_target_counts['general']}, thể chất={elective_target_counts['physical']}, cơ sở ngành={elective_target_counts['foundation']}, chuyên ngành={elective_target_counts['specialization']}\n")
        report.write(f"- Đã hoàn thành: đại cương={completed_elective_counts['general']}, thể chất={completed_elective_counts['physical']}, cơ sở ngành={completed_elective_counts['foundation']}, chuyên ngành={completed_elective_counts['specialization']}\n")
        report.write(f"- Quota còn thiếu để gợi ý: đại cương={remaining_elective_counts['general']}, thể chất={remaining_elective_counts['physical']}, cơ sở ngành={remaining_elective_counts['foundation']}, chuyên ngành={remaining_elective_counts['specialization']}\n")
        if strict_single_elective_in_final:
            report.write('- Ràng buộc theo mục tiêu học: tổ hợp cuối cùng tối đa 1 môn tự chọn\n')
        report.write('- Giữ lại top 8 state theo (đáp ứng quota tự chọn, score, credit)\n')
        report.write('- Kết thúc khi không thể mở rộng thêm\n')
        report.write('- Chọn best_state (đáp ứng quota cao nhất, ưu score và credit nếu hòa)\n')

    print(f"\nĐã lưu báo cáo chi tiết vào: {report_path}\n")

    # In ra màn hình kết quả (gọn, in một lần để tránh lỗi hiển thị terminal)
    student_major = target_student.get("ngành", "Công Nghệ Thông Tin")
    spec_display = student_spec if student_spec else 'Chưa chọn chuyên ngành'
    total_selected_credits = sum(c.get('tín chỉ', 0) for c in valid_courses)

    output_lines: List[str] = [
        "KẾT QUẢ GỢI Ý MÔN HỌC",
        f"Mã SV: {target_student_id}",
        f"Họ tên: {target_student.get('tên sinh viên', '')}",
        f"Năm vào học: {target_student.get('năm vào học', '')}",
        f"Ngành: {student_major}",
        f"Chuyên ngành: {spec_display}",
        f"Mục tiêu học tập: {study_goal_value}",
        f"Số tín chỉ đã tích lũy: {target_student.get('số tín chỉ đã tích lũy', 0)}",
        f"Số tín chỉ đăng ký tối đa: {target_student.get('số tín chỉ đăng ký tối đa', 27)}",
        f"Học kỳ hiện tại: {current_sem}",
        f"Học kỳ dự kiến đăng ký tiếp theo: {next_sem}",
        f"Tổng số môn hợp lệ có thể đăng ký: {len(valid_courses)}",
        f"Tổng số tín chỉ của các môn đã liệt kê: {total_selected_credits}",
    ]

    for idx, course in enumerate(valid_courses, 1):
        rec_sem_str = course.get('học kỳ đề xuất', 99)
        status_str = "Học lại" if course.get('là môn học lại', False) else f"Kỳ {rec_sem_str}"
        coda = course.get('mã môn học', '')
        name = course.get('tên môn học', '')
        tinchi = course.get('tín chỉ', 0)
        total_score = course.get('điểm tổng ưu tiên', 0)
        output_lines.append(f"{idx}. {coda} | {name} | {tinchi} tín chỉ | {status_str} | H_total={total_score}")
        reason_str = ', '.join(course.get('lý do', [])) if course.get('lý do', []) else 'Không rõ'
        output_lines.append(f"   Lý do: {reason_str}")

    print("\n" + "\n".join(output_lines))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gợi ý môn học đăng ký theo ontology và hồ sơ sinh viên")
    parser.add_argument("--student-id", dest="student_id", default=None, help="Mã sinh viên cần tra cứu")
    parser.add_argument("--json", dest="json_path", default=None, help="Đường dẫn file JSON danh sách sinh viên")
    parser.add_argument("--csv", dest="csv_path", default=None, help="Đường dẫn file CSV danh sách sinh viên (fallback)")
    parser.add_argument("--rdf", dest="rdf_path", default=None, help="Đường dẫn file ontology RDF")
    parser.add_argument("--output-dir", dest="output_dir", default=None, help="Thư mục xuất báo cáo")

    args = parser.parse_args()
    main(
        target_student_id=args.student_id,
        json_path=args.json_path,
        rdf_path=args.rdf_path,
        csv_path=args.csv_path,
        output_dir=args.output_dir,
    )
