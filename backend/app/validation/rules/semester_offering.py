from .common import conclusion


def evaluate(plan, code, knowledge, fact):
    if knowledge.target_semester_type is None:
        raise ValueError("TARGET_SEMESTER_TYPE_MISSING")
    if fact.open_semester_type is None:
        raise ValueError("SEMESTER_OFFERING_MISSING")
    passed = fact.open_semester_type in (3, 12, knowledge.target_semester_type)
    return conclusion(plan, code, "semester_offering", passed,
        "Offered in target semester" if passed else "SEMESTER_OFFERING_MISMATCH",
        {"target_term_id": knowledge.target_term_id, "target_semester_type": knowledge.target_semester_type,
         "open_semester_type": fact.open_semester_type, "offerings_ref": knowledge.offerings_ref,
         "snapshot_id": knowledge.snapshot_id}, fact)
