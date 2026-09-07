from .common import conclusion


def evaluate(plan, code, fact, student, knowledge, category_facts):
    category = fact.elective_category
    inputs = {"category": category, "snapshot_id": knowledge.snapshot_id, "rules_ref": knowledge.rules_ref}
    passed = True
    if category is not None:
        quota = next((q for q in knowledge.elective_quotas if q.category == category), None)
        if quota is None:
            raise ValueError("ELECTIVE_QUOTA_POLICY_MISSING")
        completed = sorted(c for c in student.completed_courses if category_facts[c].elective_category == category)
        selected = sorted({c.course_code for c in plan.courses if category_facts[c.course_code].elective_category == category})
        remaining = max(0, quota.max_courses - len(completed))
        passed = len(selected) <= remaining
        inputs.update(max_courses=quota.max_courses, completed_courses=completed,
                      selected_courses=selected, remaining_quota=remaining,
                      category_evidence_ids=sorted(f.evidence_id for f in category_facts.values()))
    return conclusion(plan, code, "elective_quota", passed,
        "Elective quota satisfied" if passed else "ELECTIVE_QUOTA_EXCEEDED: " + category,
        inputs, fact)
