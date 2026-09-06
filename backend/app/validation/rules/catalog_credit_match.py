from .common import conclusion

def evaluate(plan, code, fact):
    credits = [c.credits for c in plan.courses if c.course_code == code]
    passed = all(value == fact.catalog_credit for value in credits)
    return conclusion(plan, code, "catalog_credit_match", passed,
        "Catalog credits match" if passed else "CATALOG_CREDIT_MISMATCH",
        {"candidate_credits":credits, "catalog_credit":fact.catalog_credit}, fact)
