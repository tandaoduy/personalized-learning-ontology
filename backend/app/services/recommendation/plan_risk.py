"""Extracted existing behavior; operates on RecommendationEngine shared context."""

from typing import Dict, Any, List, Tuple
from backend.app.models.student import StudentProfile
from .constants import (
    EQUIVALENT_COURSES,
)


class PlanRiskMixin:
    """Internal extraction boundary, not an independent Agent capability."""

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
