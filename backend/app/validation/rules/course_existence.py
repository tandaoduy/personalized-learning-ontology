from .common import conclusion

def evaluate(plan, code, fact):
    return conclusion(plan, code, "course_existence", fact.exists,
        "Course found" if fact.exists else "COURSE_NOT_FOUND", {"exists":fact.exists}, fact)
