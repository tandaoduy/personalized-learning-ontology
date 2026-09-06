from .common import conclusion

def evaluate(plan, code, min_credits: float = 0.0, max_credits: float = 27.0):
    total = plan.total_credits
    passed = min_credits <= total <= max_credits
    if total > max_credits:
        message = "CREDIT_LIMIT_EXCEEDED"
    elif total < min_credits:
        message = "CREDIT_BELOW_MINIMUM"
    else:
        message = "Credit limit satisfied"
    return conclusion(
        plan, code, "credit_limit", passed, message,
        {"total_credits": total, "min_credits": min_credits, "max_credits": max_credits}
    )
