from .common import conclusion

def evaluate(plan, code):
    positions = [i for i,c in enumerate(plan.courses) if c.course_code == code]
    return conclusion(plan, code, "duplicate_course", len(positions)==1,
        "DUPLICATE_COURSE" if len(positions)>1 else "Unique course", {"positions":positions})
