"""M4 arithmetic and validity gate; academic status must come from a source.

Context loading is handled via ranking_context_service and wired to the live
pipeline via capabilities.risk and AgentPipeline.
"""
from hashlib import sha256
import json
import math
from pathlib import Path

from backend.app.schemas import RiskResult, ValidatedPlan

CONFIG_PATH = Path(__file__).resolve().parents[3] / "knowledge/rules/ranking_pdf3_v1.json"


def load_config():
    content = CONFIG_PATH.read_bytes()
    config = json.loads(content)
    features = config.get("features", [])
    if len(features) != 6 or len(set(features)) != 6:
        raise ValueError("RANKING_FEATURE_CONFIG_INVALID")
    for strategy in ("safe", "balanced", "accelerated"):
        weights = config.get("weights", {}).get(strategy, [])
        if len(weights) != len(features) or any(not math.isfinite(v) or v < 0 for v in weights) or abs(sum(weights) - 1) > 1e-12:
            raise ValueError("RANKING_WEIGHT_CONFIG_INVALID")
    risk_weights = config.get("risk_weights", {})
    if set(risk_weights) != {"load", "retake", "academic"} or abs(sum(risk_weights.values()) - 1) > 1e-12:
        raise ValueError("RISK_WEIGHT_CONFIG_INVALID")
    threshold = config.get("diversity_threshold")
    if not isinstance(threshold, (int, float)) or not 0 <= threshold <= 1:
        raise ValueError("DIVERSITY_CONFIG_INVALID")
    levels = config.get("risk_levels", {})
    if not 0 <= levels.get("low_max", -1) < levels.get("medium_max", -1) <= 1:
        raise ValueError("RISK_LEVEL_CONFIG_INVALID")
    return config, "sha256:" + sha256(content).hexdigest()


def require_current_validation(plan: ValidatedPlan):
    # Revalidate nested models too: model_copy(update=...) bypasses Pydantic checks.
    checked = ValidatedPlan.model_validate_json(plan.model_dump_json())
    plan_hash = sha256(checked.candidate.model_dump_json().encode()).hexdigest()
    validation_hash = "sha256:" + sha256(checked.validation.model_dump_json().encode()).hexdigest()
    if checked.candidate_hash != "sha256:" + plan_hash or checked.validation_hash != validation_hash:
        raise ValueError("STALE_VALIDATION")
    bound_hashes = {b.value for e in checked.validation.evidence for b in e.rule_inputs
                    if b.variable == "candidate_plan_hash"}
    if bound_hashes != {plan_hash}:
        raise ValueError("STALE_VALIDATION")
    return checked


def check_finite(*values):
    if not all(math.isfinite(v) for v in values):
        raise ValueError("FEATURE_MISSING_OR_NONFINITE")


def assess_plan_risk(plan: ValidatedPlan, *, lower: float, upper: float,
                     retake_codes: frozenset[str], academic_status: str,
                     source_refs: tuple[str, ...], context_hash: str) -> RiskResult:
    plan = require_current_validation(plan)
    config, config_hash = load_config()
    if not source_refs or not all(source_refs) or not context_hash:
        raise ValueError("FEATURE_SOURCE_MISSING")
    if academic_status not in config["academic_risk_mapping"]:
        raise ValueError("ACADEMIC_STATUS_MISSING")
    total = plan.candidate.total_credits
    check_finite(lower, upper, total)
    if not 0 <= lower <= total <= upper:
        raise ValueError("CREDIT_POLICY_MISMATCH")
    # The risk bounds must be those that actually certified the plan.
    for record in plan.validation.evidence:
        if record.rule_id == "credit_limit":
            bindings = {b.variable: b.value for b in record.rule_inputs}
            if float(bindings["min_credits"]) != lower or float(bindings["max_credits"]) != upper:
                raise ValueError("CREDIT_POLICY_MISMATCH")
    courses = {c.course_code for c in plan.candidate.courses}
    components = {
        "load": (total - lower) / (upper - lower) if upper > lower else config["equal_credit_bounds_load"],
        "retake": len(courses & retake_codes) / len(courses) if courses else 0.0,
        "academic": config["academic_risk_mapping"][academic_status],
    }
    risk = sum(config["risk_weights"][key] * value for key, value in components.items())
    levels = config["risk_levels"]
    risk_level = "low" if risk <= levels["low_max"] else "medium" if risk <= levels["medium_max"] else "high"
    return RiskResult(plan_hash=plan.candidate_hash, validation_hash=plan.validation_hash,
        context_hash=context_hash, risk_version="risk-pdf3-v1", config_hash=config_hash,
        risk_score=risk, risk_level=risk_level, safety=1 - risk, components=components,
        inputs={"credits": total, "lower": lower, "upper": upper,
                "retake_codes": sorted(retake_codes), "academic_status": academic_status},
        source_refs=source_refs)
