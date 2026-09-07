from .common import conclusion


def evaluate(plan, code, student, fact, knowledge):
    if knowledge.curriculum_courses is None:
        raise ValueError("CURRICULUM_POLICY_MISSING")
    passed = (code in knowledge.curriculum_courses and fact.exists
              and (not fact.majors or student.major_id in fact.majors)
              and (not fact.specializations or student.specialization_id in fact.specializations))
    return conclusion(plan, code, "curriculum_membership", bool(passed),
        "Curriculum membership confirmed" if passed else "NOT_IN_CURRICULUM",
        {"curriculum_id": student.curriculum_id, "curriculum_courses": sorted(knowledge.curriculum_courses),
         "major_id": student.major_id, "specialization_id": student.specialization_id,
         "majors": list(fact.majors), "specializations": list(fact.specializations),
         "snapshot_id": knowledge.snapshot_id}, fact)
