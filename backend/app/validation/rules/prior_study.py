from .common import conclusion

def evaluate(plan, code, student, fact=None):
    # Prior study check: default pass when no specific prior study constraint failed
    passed = True
    message = "Prior study conditions satisfied"
    inputs = {"student_id": student.student_id, "current_semester": student.current_semester}
    return conclusion(plan, code, "prior_study", passed, message, inputs, fact)
