from .common import conclusion

def evaluate(plan, code, fact, plan_category_count: int = 0, remaining_quota: int = 999):
    category = fact.elective_category if fact else None
    if category is not None:
        passed = plan_category_count <= remaining_quota
        message = "Elective quota satisfied" if passed else f"ELECTIVE_QUOTA_EXCEEDED: {category}"
        inputs = {"category": category, "plan_category_count": plan_category_count, "remaining_quota": remaining_quota}
    else:
        passed = True
        message = "Non-elective or unconstrained course"
        inputs = {"category": None}
    return conclusion(plan, code, "elective_quota", passed, message, inputs, fact)
