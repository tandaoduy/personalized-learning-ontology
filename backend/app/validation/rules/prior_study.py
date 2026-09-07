from .common import conclusion


def evaluate(plan, code, student, knowledge):
    policy = next((r for r in knowledge.prior_study_requirements if r.course_code == code), None)
    if policy is None:
        raise ValueError("PRIOR_STUDY_POLICY_MISSING")
    # A finished attempt (including a failed attempt) counts as studied.
    # In-progress and courses merely proposed in this plan do not count.
    studied = set(student.completed_courses) | set(student.failed_courses)
    studied.update(a.course_code for a in student.attempts if a.outcome in {"passed", "failed", "exempt"})
    missing = sorted(policy.required_courses - studied)
    return conclusion(plan, code, "prior_study", not missing,
        "PRIOR_STUDY_MISSING: " + ", ".join(missing) if missing else "Prior study conditions satisfied",
        {"required_courses": sorted(policy.required_courses), "studied_courses": sorted(studied),
         "missing_courses": missing, "rules_ref": knowledge.rules_ref,
         "snapshot_id": knowledge.snapshot_id})
