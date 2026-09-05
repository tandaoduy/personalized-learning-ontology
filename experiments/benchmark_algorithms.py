"""So sánh ba phương pháp lập kế hoạch trên cùng hồ sơ sinh viên.

Chạy từ thư mục gốc:
    python experiments/benchmark_algorithms.py --limit 20 --output benchmark_results.csv
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
import time
from statistics import mean
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Set, Tuple

# Cho phép chạy trực tiếp ``python experiments/benchmark_algorithms.py`` từ thư mục gốc.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from backend.app.config import Config
from backend.app.models.recommendation import RecommendedCourse
from backend.app.models.student import StudentProfile
from backend.app.services.recommendation_engine import ELECTIVE_QUOTA_KEYS, RecommendationEngine
from backend.app.services.student_data_service import StudentDataService


# Lấy danh sách học phần hợp lệ qua giao diện công khai của RecommendationEngine.
def _prepare_candidates(engine: RecommendationEngine, student: StudentProfile):
    """Dùng chung bước chuẩn bị công khai cho các phương pháp benchmark."""
    return engine.get_eligible_courses(student)


# Tìm toàn bộ bundle môn song hành của một học phần; trả về None nếu thiếu môn.
def _bundle(engine, code: str, candidates: Dict[str, RecommendedCourse], passed: Set[str]):
    result: Set[str] = set()
    stack = [code]
    while stack:
        current = stack.pop()
        if current in result or current in passed:
            continue
        if current not in candidates:
            return None
        result.add(current)
        stack.extend(engine.course_data.get(current, {}).get("corequisites", []))
    return result


# Chọn học phần tuần tự theo một tiêu chí sắp xếp và kiểm tra các ràng buộc.
def _select_in_order(engine, candidates, passed, completed, order_key):
    selected: List[RecommendedCourse] = []
    selected_codes: Set[str] = set()
    credits = 0
    quota_counts = {key: 0 for key in ELECTIVE_QUOTA_KEYS}
    index = {course.code: course for course in candidates}

    for course in sorted(candidates, key=order_key):
        bundle = _bundle(engine, course.code, index, passed | selected_codes)
        if not bundle or bundle & selected_codes:
            continue
        bundle_courses = [index[code] for code in bundle]
        bundle_credits = sum(item.credits for item in bundle_courses)
        if credits + bundle_credits > engine.max_credits:
            continue
        if any(
            prereq not in passed | selected_codes | bundle
            for code in bundle
            for prereq in engine.course_data.get(code, {}).get("prereqs", [])
        ):
            continue
        next_quota = dict(quota_counts)
        quota_ok = True
        for code in bundle:
            category = engine.course_data.get(code, {}).get("elective_category")
            if category in ELECTIVE_QUOTA_KEYS:
                next_quota[category] += 1
                if next_quota[category] > max(0, engine.elective_quotas.get(category, 0) - completed.get(category, 0)):
                    quota_ok = False
        if not quota_ok:
            continue
        selected.extend(bundle_courses)
        selected_codes.update(bundle)
        quota_counts = next_quota
        credits += bundle_credits
    return selected


# Baseline 1: chọn theo thứ tự học kỳ khuyến nghị, không dùng Beam Search.
def rule_based_plan(engine, student):
    candidates, passed, completed, _ = _prepare_candidates(engine, student)
    return _select_in_order(
        engine, candidates, passed, completed,
        lambda course: (course.recommended_semester, course.code),
    )


# Baseline 2: chọn tham lam từ học phần có điểm ưu tiên cao nhất.
def greedy_plan(engine, student):
    candidates, passed, completed, _ = _prepare_candidates(engine, student)
    return _select_in_order(
        engine, candidates, passed, completed,
        lambda course: (-course.total_priority_score, course.code),
    )


# Phương pháp đề tài: gọi luồng heuristic kết hợp Beam Search hiện hành.
def beam_search_plan(engine, student):
    # Gọi đúng luồng sản phẩm hiện tại; kết quả này là phương pháp đề tài.
    return engine.get_recommendation(student, seed_offset=0).recommended_courses


# Tính các chỉ số so sánh: ràng buộc, bắt buộc, điểm, quota, tín chỉ và giải thích.
def evaluate(engine, student, plan, elapsed_ms):
    _, passed, _, _ = engine.get_eligible_courses(student)
    codes = {course.code for course in plan}
    total_credits = sum(course.credits for course in plan)
    constraints_ok = total_credits <= engine.max_credits and len(codes) == len(plan)
    constraints_ok = constraints_ok and all(code not in passed for code in codes)
    constraints_ok = constraints_ok and all(
        prereq in passed | codes
        for code in codes
        for prereq in engine.course_data.get(code, {}).get("prereqs", [])
    )
    constraints_ok = constraints_ok and all(
        coreq in passed | codes
        for code in codes
        for coreq in engine.course_data.get(code, {}).get("corequisites", [])
    )
    required = [code for code, info in engine.course_data.items() if info.get("is_required_major") or info.get("is_required_specialization")]
    required_eligible = [code for code in required if code not in passed]
    required_covered = sum(code in codes for code in required_eligible) / max(1, len(required_eligible)) * 100
    quota_total = sum(engine.elective_quotas.values())
    quota_selected = sum(
        1 for course in plan
        if engine.course_data.get(course.code, {}).get("elective_category") in ELECTIVE_QUOTA_KEYS
    )
    return {
        "constraints_ok": constraints_ok,
        "required_coverage_pct": round(required_covered, 2),
        "priority_score": round(sum(course.total_priority_score for course in plan), 2),
        "quota_fill_pct": round(min(100, quota_selected / max(1, quota_total) * 100), 2),
        "total_credits": total_credits,
        "processing_time_ms": round(elapsed_ms, 3),
        "explanation_rate_pct": round(sum(bool(course.reasons) for course in plan) / max(1, len(plan)) * 100, 2),
    }


# Đọc tham số, chạy ba phương pháp trên các sinh viên và xuất CSV chi tiết/tổng hợp.
def main():
    parser = argparse.ArgumentParser(description="Benchmark ba phương pháp lập kế hoạch")
    parser.add_argument("--limit", type=int, default=20, help="Số sinh viên đầu tiên (0 = toàn bộ)")
    parser.add_argument("--output", default="benchmark_results/benchmark_results.csv")
    args = parser.parse_args()

    service = StudentDataService(Config.STUDENT_DATA_JSON, Config.STUDENT_DATA_CSV)
    students = service.get_all_students(force_reload=True)
    if args.limit > 0:
        students = students[:args.limit]
    engine = RecommendationEngine(
        Config.ONTOLOGY_PATH, Config.BEAM_WIDTH, Config.REGISTER_MAX_CREDITS,
        Config.REGISTER_MIN_CREDITS,
        {"debt": Config.WEIGHT_DEBT, "link": Config.WEIGHT_LINK, "delay": Config.WEIGHT_DELAY},
        Config.ELECTIVE_QUOTAS,
    )
    methods: List[Tuple[str, Callable]] = [
        ("Rule + Semester Order", rule_based_plan),
        ("Greedy Heuristic", greedy_plan),
        ("Heuristic + Beam Search", beam_search_plan),
    ]
    rows = []
    for student in students:
        for name, method in methods:
            started = time.perf_counter()
            try:
                plan = method(engine, student)
                row = evaluate(engine, student, plan, (time.perf_counter() - started) * 1000)
                row.update({"student_id": student.student_id, "method": name, "status": "OK"})
            except Exception as exc:
                row = {"student_id": student.student_id, "method": name, "status": f"ERROR: {exc}"}
            rows.append(row)
    fields = ["student_id", "method", "status", "constraints_ok", "required_coverage_pct", "priority_score", "quota_fill_pct", "total_credits", "processing_time_ms", "explanation_rate_pct"]
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    summary_fields = ["method", "plans", "constraint_rate_pct", "required_coverage_mean_pct", "priority_score_mean", "quota_fill_mean_pct", "credits_mean", "time_mean_ms", "explanation_rate_mean_pct"]
    summary_rows = []
    for name, _ in methods:
        successful = [row for row in rows if row.get("method") == name and row.get("status") == "OK"]
        summary_rows.append({
            "method": name,
            "plans": len(successful),
            "constraint_rate_pct": round(sum(row["constraints_ok"] is True for row in successful) / max(1, len(successful)) * 100, 2),
            "required_coverage_mean_pct": round(mean(float(row["required_coverage_pct"]) for row in successful), 2) if successful else 0,
            "priority_score_mean": round(mean(float(row["priority_score"]) for row in successful), 2) if successful else 0,
            "quota_fill_mean_pct": round(mean(float(row["quota_fill_pct"]) for row in successful), 2) if successful else 0,
            "credits_mean": round(mean(float(row["total_credits"]) for row in successful), 2) if successful else 0,
            "time_mean_ms": round(mean(float(row["processing_time_ms"]) for row in successful), 3) if successful else 0,
            "explanation_rate_mean_pct": round(mean(float(row["explanation_rate_pct"]) for row in successful), 2) if successful else 0,
        })
    summary_path = output_path.with_name(output_path.stem + "_summary.csv")
    with summary_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=summary_fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(summary_rows)
    print(f"Đã benchmark {len(students)} sinh viên x {len(methods)} phương pháp")
    print(f"Kết quả: {Path(args.output).resolve()}")
    print(f"Tổng hợp: {summary_path.resolve()}")


if __name__ == "__main__":
    main()
