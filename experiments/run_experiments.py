"""Official entry point: ``python experiments/run_experiments.py --limit 0``."""
from collections import Counter

import experimental_evaluation as suite


def validate(truth, student, plan, max_credits):
    """Use exactly the production engine's semester-opening semantics."""
    codes, passed, count = {x.code for x in plan}, set(student.passed_courses), Counter()
    if len(codes) != len(plan):
        count["duplicate"] += len(plan) - len(codes)
    if sum(x.credits for x in plan) > max_credits:
        count["credit"] += 1
    for code in codes:
        info = truth.get(code, {})
        count["prerequisite"] += sum(x not in passed | codes for x in info.get("prereqs", []))
        count["corequisite"] += sum(x not in passed | codes for x in info.get("corequisites", []))
        count["program"] += not suite.relevant(info, student)
        offered = int(info.get("openSemesterType", 3) or 3)
        always_open = info.get("is_general_education_course") or info.get("is_physical_education_course")
        count["semester"] += not (always_open or offered in (3, 12, student.next_semester_type()))
    count["total"] = sum(value for key, value in count.items() if key != "total")
    return count


def scenario(student):
    if student.current_semester >= 7:
        return "near_graduation"
    if student.failed_courses:
        return "failed_course_or_prerequisite"
    normalize = suite.RecommendationEngine._normalize_text
    if normalize(student.specialization or "") == "chua chon chuyen nganh":
        return "no_specialization"
    if student.study_goal == "học vượt":
        return "accelerated"
    return "on_track"


if __name__ == "__main__":
    suite.violations = validate
    suite.scenario = scenario
    suite.main()
