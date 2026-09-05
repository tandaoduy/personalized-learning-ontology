"""Phân tích nguy cơ chậm tiến độ dựa trên CTĐT đang nạp từ ontology."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Mapping, Set
import unicodedata


class ProgressRiskAnalyzer:
    """Đánh giá tiến độ mà không dùng mốc tín chỉ hay số kỳ học cố định."""

    def __init__(self, recommendation_engine=None):
        self.recommendation_engine = recommendation_engine

    @staticmethod
    def _value(item: Any, key: str, default=None):
        if isinstance(item, Mapping):
            return item.get(key, default)
        return getattr(item, key, default)

    @staticmethod
    def _text(value: Any) -> str:
        return unicodedata.normalize("NFD", str(value or "")).encode("ascii", "ignore").decode("ascii").lower()

    def _is_passed(self, attempt: Any) -> bool:
        status = self._text(self._value(attempt, "status", ""))
        grade = self._value(attempt, "grade", None)
        if "chua dat" in status or "rot" in status or "fail" in status:
            return False
        if "dat" in status or "mien" in status or "pass" in status:
            return True
        try:
            return float(grade) >= 4.0
        except (TypeError, ValueError):
            return False

    def _is_failed(self, attempt: Any) -> bool:
        status = self._text(self._value(attempt, "status", ""))
        if "chua dat" in status or "rot" in status or "fail" in status:
            return True
        # "Không tính điểm"/"Miễn" có thể mang điểm mặc định 0 nhưng không phải rớt.
        if "khong tinh diem" in status or "mien" in status or "dat" in status or "pass" in status:
            return False
        grade = self._value(attempt, "grade", None)
        try:
            return not status and float(grade) < 4.0 and bool(self._value(attempt, "grade_specified", True))
        except (TypeError, ValueError):
            return False

    def _course_applies(self, info: Mapping[str, Any], specialization: str) -> bool:
        """Môn thuộc CTĐT nếu là môn chung/nền tảng/bắt buộc ngành hoặc đúng CN."""
        if info.get("is_physical_education_course"):
            return False
        if not info.get("is_it_program", True):
            return False
        if info.get("is_required_major") or info.get("is_general_education_course") or info.get("is_foundation_course"):
            return True
        if not info.get("is_required_specialization"):
            return False
        selected = self._text(specialization)
        course_specs = {self._text(x) for x in (info.get("specializations") or [])}
        return bool(selected and selected not in {"", "chua chon chuyen nganh"} and selected in course_specs)

    def _elective_group(self, info: Mapping[str, Any], specialization: str) -> str:
        """Trả về nhóm tự chọn phù hợp với sinh viên, rỗng nếu không phải tự chọn."""
        category = str(info.get("elective_category") or "").strip()
        if category:
            return category
        if info.get("is_elective_specialization"):
            selected = self._text(specialization)
            course_specs = {self._text(x) for x in (info.get("specializations") or [])}
            if selected and selected in course_specs:
                return "specialization"
        if info.get("is_elective_major"):
            return "major"
        return ""

    def _resolved_elective_failures(self, failed_codes: Set[str], passed_codes: Set[str], engine, specialization: str) -> Set[str]:
        """Bỏ qua môn tự chọn đã được thay thế bằng môn đạt trong cùng nhóm quota."""
        course_data = getattr(engine, "course_data", {}) or {}
        quotas = getattr(engine, "elective_quotas", {}) or {}
        passed_by_group: Dict[str, Set[str]] = defaultdict(set)
        for code in passed_codes:
            info = course_data.get(code, {})
            group = self._elective_group(info, specialization) if isinstance(info, Mapping) else ""
            if group:
                passed_by_group[group].add(code)

        unresolved = set()
        for code in failed_codes:
            info = course_data.get(code, {})
            group = self._elective_group(info, specialization) if isinstance(info, Mapping) else ""
            if not group:
                continue
            required_count = int(quotas.get(group, 1) or 1)
            # Học lại đạt đã nằm trong passed_codes; hoặc một môn khác đủ quota
            # trong cùng nhóm đều làm môn rớt này không còn ảnh hưởng tiến độ.
            if len(passed_by_group.get(group, set())) < required_count:
                unresolved.add(code)
        return unresolved

    def _curriculum(self, engine, student: Any) -> Dict[str, Any]:
        course_data = getattr(engine, "course_data", {}) or {}
        specialization = self._value(student, "specialization", "")
        courses = {
            str(code).strip().upper(): info
            for code, info in course_data.items()
            if isinstance(info, Mapping) and self._course_applies(info, specialization)
        }
        by_semester: Dict[int, int] = defaultdict(int)
        unknown_semester_credits = 0
        for info in courses.values():
            credits = int(info.get("credit") or 0)
            sem = info.get("recommended_sem")
            try:
                sem = int(sem)
            except (TypeError, ValueError):
                sem = 0
            if sem > 0 and sem < 99999:
                by_semester[sem] += credits
            else:
                unknown_semester_credits += credits

        planned_terms = sorted(by_semester)
        max_semester = max(planned_terms, default=0)
        per_term_capacity = max(by_semester.values(), default=0)
        return {
            "courses": courses,
            "required_credits": sum(int(info.get("credit") or 0) for info in courses.values()),
            "credits_by_semester": dict(by_semester),
            "max_planned_semester": max_semester,
            "typical_term_load": per_term_capacity,
            "unknown_semester_credits": unknown_semester_credits,
        }

    def _attempts(self, student: Any) -> List[Any]:
        return list(self._value(student, "course_attempts", []) or [])

    def _passed_codes(self, student: Any, attempts: Iterable[Any]) -> Set[str]:
        passed = {str(code).strip().upper() for code in (self._value(student, "passed_courses", []) or [])}
        for attempt in attempts:
            if self._is_passed(attempt):
                code = str(self._value(attempt, "course_code", "")).strip().upper()
                if code:
                    passed.add(code)
        return passed

    def _term_records(self, attempts: Iterable[Any], courses: Mapping[str, Mapping[str, Any]]) -> List[Dict[str, Any]]:
        # Chỉ dùng dữ liệu lần học thật; không dựng lịch sử từ điểm trung bình.
        term_credits: Dict[int, Set[str]] = defaultdict(set)
        for attempt in attempts:
            if not self._is_passed(attempt):
                continue
            code = str(self._value(attempt, "course_code", "")).strip().upper()
            if code not in courses:
                continue
            term = self._value(attempt, "semester_taken", 0) or 0
            try:
                term = int(term)
            except (TypeError, ValueError):
                term = 0
            if term > 0:
                term_credits[term].add(code)
        return [
            {"semester": term, "earned_credits": sum(int(courses[c].get("credit") or 0) for c in codes)}
            for term, codes in sorted(term_credits.items())
        ]

    def _prerequisite_depth(self, code: str, courses: Mapping[str, Mapping[str, Any]], passed: Set[str], visiting=None) -> int:
        if code in passed or code not in courses:
            return 0
        visiting = visiting or set()
        if code in visiting:
            return 0
        visiting.add(code)
        unmet = [p for p in courses[code].get("prereqs", []) if p in courses and p not in passed]
        depth = 1 + max((self._prerequisite_depth(p, courses, passed, visiting.copy()) for p in unmet), default=0)
        return depth

    def assess_student(self, student: Any, recommendation_engine=None) -> Dict[str, Any]:
        engine = recommendation_engine or self.recommendation_engine
        if engine is None:
            return {"progress_status": "UNKNOWN", "risk_level": "UNKNOWN", "message": "Chưa nạp được chương trình đào tạo để phân tích."}

        curriculum = self._curriculum(engine, student)
        courses = curriculum["courses"]
        if not courses:
            return {"progress_status": "UNKNOWN", "risk_level": "UNKNOWN", "message": "Chưa xác định được các học phần bắt buộc của chương trình này."}

        attempts = self._attempts(student)
        passed = self._passed_codes(student, attempts)
        completed = passed & set(courses)
        all_failed = {
            str(self._value(a, "course_code", "")).strip().upper()
            for a in attempts if self._is_failed(a)
        } | {str(c).strip().upper() for c in (self._value(student, "failed_courses", []) or [])}
        # Nếu đã có lần học đạt sau đó thì môn không còn là học phần nợ.
        all_failed -= passed
        failed = all_failed & set(courses)
        unresolved_electives = self._resolved_elective_failures(
            all_failed, passed, engine, self._value(student, "specialization", "")
        )
        risk_failures = failed | unresolved_electives
        earned_credits = sum(int(courses[c].get("credit") or 0) for c in completed)
        required_credits = curriculum["required_credits"]
        remaining_codes = set(courses) - completed
        remaining_credits = max(0, required_credits - earned_credits)

        current_semester = int(self._value(student, "current_semester", 1) or 1)
        expected_by_term = curriculum["credits_by_semester"]
        expected_to_date = sum(v for sem, v in expected_by_term.items() if sem <= current_semester)
        credit_gap = max(0, expected_to_date - earned_credits)
        records = self._term_records(attempts, courses)
        recent = records[-2:]
        if recent:
            completion_rates = [r["earned_credits"] / max(1, expected_by_term.get(r["semester"], curriculum["typical_term_load"] or 1)) for r in recent]
            trend_score = round(sum(completion_rates) / len(completion_rates), 2)
        else:
            trend_score = None

        max_plan_sem = curriculum["max_planned_semester"]
        terms_left = max(0, max_plan_sem - current_semester + 1)
        normal_term_load = curriculum["typical_term_load"]
        max_chain = max((self._prerequisite_depth(code, courses, completed) for code in remaining_codes), default=0)
        blocked = sorted(code for code in remaining_codes if any(p in failed for p in courses[code].get("prereqs", [])))
        capacity_ok = normal_term_load > 0 and remaining_credits <= terms_left * normal_term_load
        prerequisites_ok = max_chain <= terms_left
        can_complete = bool(terms_left and capacity_ok and prerequisites_ok)
        early_stage = current_semester <= 2

        if not can_complete:
            status, level = "BEHIND_SCHEDULE", "HIGH"
            message = "Khối lượng học phần còn lại hoặc chuỗi môn tiên quyết không còn phù hợp với tiến độ CTĐT."
        # Chênh tín chỉ chỉ là tín hiệu phụ: không gắn cờ sinh viên chưa rớt môn
        # nếu họ vẫn còn khả năng hoàn thành đúng hạn.
        # Giai đoạn HK1-HK2 còn đủ thời gian học lại/thay thế tự chọn. Chỉ
        # cảnh báo sớm khi môn nợ đã chặn môn bắt buộc phía sau.
        elif blocked or (not early_stage and len(risk_failures) >= 2):
            status, level = "AT_RISK", "MEDIUM"
            message = "Có dấu hiệu thiếu tiến độ; cần ưu tiên học phần bắt buộc và gỡ các môn tiên quyết bị vướng."
        elif len(risk_failures) > 0:
            status, level = "ON_TRACK", "LOW"
            message = "Có học phần cần học lại nhưng hiện chưa ảnh hưởng đến tiến độ tốt nghiệp."
        else:
            status, level = "ON_TRACK", "LOW"
            message = "Tiến độ hiện tại vẫn phù hợp với kế hoạch chương trình đào tạo."

        return {
            "progress_status": status,
            "risk_level": level,
            "message": message,
            "curriculum_reference": {
                "required_credits": required_credits,
                "planned_semesters": max_plan_sem,
                "unknown_semester_credits": curriculum["unknown_semester_credits"],
            },
            "credit_progress": {
                "earned_required_credits": earned_credits,
                "remaining_required_credits": remaining_credits,
                "expected_credits_to_current_semester": expected_to_date,
                "credit_gap": credit_gap,
                "expected_credits_by_semester": expected_by_term,
            },
            "trend_analysis": {"term_records": records, "recent_completion_rate": trend_score},
            "failed_courses_analysis": {
                "failed_required_courses": sorted(failed),
                "unresolved_elective_failures": sorted(unresolved_electives),
                "blocked_required_courses": blocked,
            },
            "can_complete_on_time": {
                "value": can_complete,
                "remaining_terms": terms_left,
                "normal_term_load": normal_term_load,
                "longest_remaining_prerequisite_chain": max_chain,
            },
        }
