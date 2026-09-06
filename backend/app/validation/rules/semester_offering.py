from .common import conclusion

def evaluate(plan, code, student, fact):
    next_sem = max(1, student.current_semester + 1)
    target_sem_type = 1 if next_sem % 2 != 0 else 2
    open_type = fact.open_semester_type if fact and fact.open_semester_type is not None else 3
    passed = open_type == 3 or open_type == target_sem_type
    return conclusion(
        plan, code, "semester_offering", passed,
        "Offered in target semester" if passed else "SEMESTER_OFFERING_MISMATCH",
        {"target_semester": next_sem, "target_semester_type": target_sem_type, "open_semester_type": open_type},
        fact
    )
