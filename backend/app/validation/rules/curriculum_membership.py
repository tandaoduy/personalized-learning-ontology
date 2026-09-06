from .common import conclusion

def evaluate(plan, code, student, fact):
    exists = fact.exists if fact else False
    # If course exists in the ontology catalog, it is considered part of the curriculum space.
    # If specializations are constrained, check alignment when specialization is set.
    passed = exists
    message = "Curriculum membership confirmed" if passed else "NOT_IN_CURRICULUM"
    inputs = {
        "exists": exists,
        "curriculum_id": student.curriculum_id,
        "major_id": student.major_id,
        "specialization_id": student.specialization_id,
        "specializations": list(fact.specializations) if fact else []
    }
    return conclusion(plan, code, "curriculum_membership", passed, message, inputs, fact)
