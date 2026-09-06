from .common import conclusion

def evaluate(plan, code, student, fact):
    plan_codes = {c.course_code for c in plan.courses}
    coreqs = set(fact.corequisite_codes) if fact and fact.corequisite_codes else set()
    missing = sorted(coreqs - (student.completed_courses | plan_codes))
    passed = len(missing) == 0
    return conclusion(
        plan, code, "corequisite", passed,
        "All corequisites satisfied" if passed else f"MISSING_COREQUISITE: {', '.join(missing)}",
        {"corequisites": sorted(coreqs), "missing": missing, "plan_codes": sorted(plan_codes)},
        fact
    )
