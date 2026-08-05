import argparse
import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"


def parse_pdfs(pdf_files: list[Path]):
    from pypdf import PdfReader
    student_terms = {}
    
    for pdf in pdf_files:
        if not pdf.is_file():
            print(f"Skipping missing PDF: {pdf}")
            continue
        reader = PdfReader(pdf)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"

        current_student_id = None
        current_term_id = None

        for line in text.split('\n'):
            line = line.strip()
            if not line: continue
            
            match_student = re.search(r'Họ tên:.* - (\d+)$', line)
            if match_student:
                sid = match_student.group(1)
                if sid != current_student_id:
                    current_student_id = sid
                    current_term_id = None
                    if sid not in student_terms:
                        student_terms[sid] = {}
                continue
                
            if not current_student_id: continue
            
            match_term = re.search(r'Học kỳ (\d) năm học (\d{4})-(\d{4})', line)
            if match_term:
                hk = int(match_term.group(1))
                y_start = int(match_term.group(2))
                y_end = int(match_term.group(3))
                term_type = 'REGULAR' if hk in [1, 2] else 'SUMMER'
                current_term_id = f"Term_{y_start}_{y_end}_HK{hk}"
                if current_term_id not in student_terms[current_student_id]:
                    student_terms[current_student_id][current_term_id] = {
                        'term_id': current_term_id,
                        'academic_year_start': y_start,
                        'academic_year_end': y_end,
                        'semester_number': hk,
                        'semester_type': term_type,
                        'term_label': f"Học kỳ {hk} năm học {y_start}-{y_end}",
                        'courses': set()
                    }
                continue
                
            match_summer = re.search(r'Học kỳ hè năm học (\d{4})-(\d{4})', line)
            if match_summer:
                y_start = int(match_summer.group(1))
                y_end = int(match_summer.group(2))
                hk = 3
                term_type = 'SUMMER'
                current_term_id = f"Term_{y_start}_{y_end}_HK{hk}"
                if current_term_id not in student_terms[current_student_id]:
                    student_terms[current_student_id][current_term_id] = {
                        'term_id': current_term_id,
                        'academic_year_start': y_start,
                        'academic_year_end': y_end,
                        'semester_number': hk,
                        'semester_type': term_type,
                        'term_label': f"Học kỳ hè năm học {y_start}-{y_end}",
                        'courses': set()
                    }
                continue
                
            if current_term_id:
                match_course = re.match(r'^([A-Z0-9]+)\s', line)
                if match_course:
                    code = match_course.group(1)
                    if code not in ['TC', 'ĐVHT', 'Họ', 'Ngày', 'Ngành', 'Điểm', 'Xếp', 'Cán', 'Mã']:
                        student_terms[current_student_id][current_term_id]['courses'].add(code)
    return student_terms

def get_study_goal(goal_str):
    goal_str = (goal_str or "").strip().lower()
    if "sớm" in goal_str or "vượt" in goal_str:
        return "ACCELERATE"
    elif "giảm" in goal_str:
        return "REDUCE_LOAD"
    return "ON_TIME"

def get_status_code(status_str):
    status_str = str(status_str or "").strip().lower()
    if status_str == "đạt":
        return "PASSED"
    elif status_str == "chưa đạt":
        return "FAILED"
    elif status_str == "miễn":
        return "EXEMPTED"
    return "PASSED"

def migrate(json_file: Path, out_file: Path, pdf_files: list[Path]) -> None:
    print("Parsing PDFs...")
    pdf_terms = parse_pdfs(pdf_files)
    print(f"Parsed PDFs for {len(pdf_terms)} students.")

    print("Loading existing JSON...")
    with json_file.open('r', encoding='utf-8') as f:
        students = json.load(f)

    new_students = []
    
    for s in students:
        sid = s.get('student_id', '')
        # Basic fields
        new_s = {
            "student_id": sid,
            "name": s.get('name', ''),
            "year_admitted": s.get('year_admitted', 2023),
            "major_code": "CNTT",
            "major_name": s.get('major', 'Công Nghệ Thông Tin'),
            "specialization_code": None,
            "specialization_name": s.get('specialization', 'Chưa chọn chuyên ngành'),
            "academic_class": s.get('academic_class', ''),
            "study_goal": get_study_goal(s.get('study_goal', '')),
            "current_term_id": f"Term_2025_2026_HK1", # Assuming generic current term
            "academic_summary": {
                "total_credits_accumulated": s.get('total_credits_accumulated', 0),
                "gpa_accumulated": s.get('gpa_accumulated', 0.0),
                "passed_course_codes": [],
                "failed_course_codes": []
            },
            "term_records": []
        }

        # Calculate passed/failed lists
        # We can extract from passed_courses dictionary and failed_courses list from original
        passed_codes = list(s.get('passed_courses', {}).keys())
        failed_codes = [c.get('course_code', '') for c in s.get('failed_courses', [])]
        new_s["academic_summary"]["passed_course_codes"] = passed_codes
        new_s["academic_summary"]["failed_course_codes"] = failed_codes

        # Get PDF term data for this student
        student_pdf_data = pdf_terms.get(sid, {})
        
        # We process course_grades from original JSON and assign them to terms
        course_grades = s.get('course_grades', [])
        
        # Build terms
        # If student_pdf_data is empty, put all in Term_Legacy
        terms_dict = {}
        
        if not student_pdf_data:
            legacy_term = "Term_Legacy_HK0"
            terms_dict[legacy_term] = {
                "term_id": legacy_term,
                "academic_year_start": 2000,
                "academic_year_end": 2023,
                "semester_number": 0,
                "semester_type": "REGULAR",
                "term_label": "Kết quả học tập trước",
                "term_summary": {
                    "registered_credits": 0,
                    "gpa_credits": 0,
                    "earned_credits": 0,
                    "term_gpa": 0.0,
                    "cumulative_credits": new_s["academic_summary"]["total_credits_accumulated"],
                    "cumulative_gpa": new_s["academic_summary"]["gpa_accumulated"]
                },
                "course_attempts": []
            }
        else:
            for tid, tinfo in student_pdf_data.items():
                terms_dict[tid] = {
                    "term_id": tinfo['term_id'],
                    "academic_year_start": tinfo['academic_year_start'],
                    "academic_year_end": tinfo['academic_year_end'],
                    "semester_number": tinfo['semester_number'],
                    "semester_type": tinfo['semester_type'],
                    "term_label": tinfo['term_label'],
                    "term_summary": {
                        "registered_credits": 0,
                        "gpa_credits": 0,
                        "earned_credits": 0,
                        "term_gpa": 0.0,
                        "cumulative_credits": 0,
                        "cumulative_gpa": 0.0
                    },
                    "course_attempts": []
                }
        
        # Distribute courses
        for cg in course_grades:
            code = cg.get('course_code', '')
            if not code: continue
            
            attempt = {
                "course_code": code,
                "course_name": cg.get('course_name', ''),
                "credits": 3, # Mock or leave empty if ontology is not parsed
                "attempt_number": cg.get('attempt_number', 1),
                "grade": cg.get('grade', 0.0),
                "status_code": get_status_code(cg.get('status', '')),
                "status_label": cg.get('status', 'Đạt'),
                "grade_specified": cg.get('grade_specified', True)
            }
            
            # Find the term
            assigned_term = None
            if student_pdf_data:
                for tid, tinfo in student_pdf_data.items():
                    if code in tinfo['courses']:
                        assigned_term = tid
                        break
            
            if not assigned_term:
                assigned_term = list(terms_dict.keys())[0]
                
            terms_dict[assigned_term]["course_attempts"].append(attempt)
            
        # Convert terms_dict to list and sort
        term_records = list(terms_dict.values())
        term_records.sort(key=lambda x: (x['academic_year_start'], x['semester_number']))
        
        new_s["term_records"] = term_records
        new_students.append(new_s)

    out_file.parent.mkdir(parents=True, exist_ok=True)
    with out_file.open('w', encoding='utf-8') as f:
        json.dump(new_students, f, ensure_ascii=False, indent=4)
        
    print(f"Migrated {len(new_students)} students to {out_file}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Migrate student data to the version 2 JSON schema."
    )
    parser.add_argument(
        "--input-json",
        type=Path,
        default=DEFAULT_DATA_DIR / "DanhSachSinhVien.json",
        help="Source student JSON file (default: data/DanhSachSinhVien.json).",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=DEFAULT_DATA_DIR / "DanhSachSinhVien_v2.json",
        help="Destination JSON file (default: data/DanhSachSinhVien_v2.json).",
    )
    parser.add_argument(
        "--pdf",
        type=Path,
        action="append",
        dest="pdf_files",
        help="Transcript PDF to parse. Repeat this option for each PDF.",
    )
    return parser.parse_args()

if __name__ == '__main__':
    args = parse_args()
    default_pdfs = [DEFAULT_DATA_DIR / f"65.CNTT-{index}.pdf" for index in range(1, 5)]
    migrate(args.input_json, args.output_json, args.pdf_files or default_pdfs)
