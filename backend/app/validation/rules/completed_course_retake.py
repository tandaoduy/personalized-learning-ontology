from .common import conclusion

def evaluate(plan, code, student, fact=None):
    is_completed = code in student.completed_courses
    passed = not is_completed
    return conclusion(
        plan, code, "completed_course_retake", passed,
        "Course not previously completed" if passed else "COURSE_ALREADY_COMPLETED",
        {"completed_courses": sorted(student.completed_courses)},
        fact
    )
