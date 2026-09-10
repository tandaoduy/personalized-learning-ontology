"""M4 scoring kernel over explicitly sourced features of validated candidates.

Context construction is handled via ranking_context_service and wired to the
live pipeline via capabilities.ranking and AgentPipeline.
"""
from hashlib import sha256
import json

from backend.app.schemas import RankingResult, RiskResult
from backend.app.services.plan_risk_service import check_finite, load_config, require_current_validation


def fit_credits(total, target, lower, upper):
    check_finite(total, target, lower, upper)
    if not 0 <= lower <= target <= upper:
        raise ValueError("CREDIT_TARGET_OUTSIDE_POLICY")
    return max(0.0, 1 - abs(total - target) / max(target - lower, upper - target, 1))


def goal_fit(criteria):
    """Explicit (score, alpha) pairs; no implicit neutral preference."""
    if not criteria:
        raise ValueError("GOAL_CRITERIA_MISSING")
    for value, weight in criteria:
        check_finite(value, weight)
        if not 0 <= value <= 1 or weight < 0:
            raise ValueError("GOAL_CRITERIA_INVALID")
    denominator = sum(weight for _, weight in criteria)
    if denominator == 0:
        raise ValueError("GOAL_WEIGHTS_ZERO")
    return sum(value * weight for value, weight in criteria) / denominator


def dependency_unlock(selected, completed, dependencies):
    """Count each unfinished, unselected course with a newly resolved edge once.

    This does not assert full next-term eligibility. The supplied map must
    explicitly cover the curriculum and combine prerequisite/corequisite edges.
    """
    return sum(bool((set(required) - set(completed)) & set(selected))
               for code, required in dependencies.items() if code not in set(completed) | set(selected))


def diversity(left, right):
    union = left | right
    return 1 - len(left & right) / len(union) if union else 0.0


def build_plan_features(plan, risk, context, request, *, current_semester, completed_courses, course_metadata):
    """Calculate the six PDF-v3 features from one versioned ranking context."""
    selected = {course.course_code for course in plan.candidate.courses}
    known_recommended = []
    for code in selected:
        value = course_metadata.get(code, {}).get("recommended_sem")
        try:
            value = int(value)
        except (TypeError, ValueError):
            continue
        if 1 <= value <= 8:
            known_recommended.append(value)
    if not known_recommended:
        raise ValueError("GOAL_SCHEDULE_EVIDENCE_MISSING")
    target_semester = current_semester + 1
    if request.goal == "on_time":
        objective = sum(value <= target_semester for value in known_recommended) / len(known_recommended)
    else:
        objective = sum(value > current_semester for value in known_recommended) / len(known_recommended)
    config, _ = load_config()
    goal_config = config["goal_fit"]
    criteria = [(objective, float(goal_config["objective_weight"]))]
    if request.preferred_courses:
        criteria.append((len(selected & set(request.preferred_courses)) / len(request.preferred_courses),
                         float(goal_config["preferred_weight"])))
    if request.avoided_courses:
        criteria.append((1 - len(selected & set(request.avoided_courses)) / len(selected),
                         float(goal_config["avoided_weight"])))
    total = plan.candidate.total_credits
    return {
        "goal_fit": goal_fit(tuple(criteria)),
        "mandatory": sum(context.catalog_credits[code] for code in selected & set(context.required_codes)),
        "unlock": float(dependency_unlock(selected, set(completed_courses), context.dependency_map)),
        "credit_fit": fit_credits(total, request.target_credits, context.credit_min, context.credit_max),
        "workload": fit_credits(total, context.reference_credits, context.credit_min, context.credit_max),
        "safety": risk.safety,
    }


def rank_valid_plans(rows, *, request_id, knowledge_versions, context_hash):
    """Rows: (ValidatedPlan, six raw features, source refs, RiskResult).

    Mandatory/unlock are nonnegative counts; all other features are in [0,1].
    Only this function normalizes counts against the current distinct pool.
    """
    config, config_hash = load_config()
    features = config["features"]
    if not context_hash or len(rows) > 60:
        raise ValueError("RANKING_CONTEXT_OR_POOL_INVALID")
    scored, seen = [], set()
    for plan, raw, sources, risk in rows:
        plan = require_current_validation(plan)
        risk = RiskResult.model_validate(risk)
        candidate = plan.candidate
        if candidate.request_id != request_id or candidate.knowledge_versions != knowledge_versions:
            raise ValueError("STALE_VALIDATION")
        if (risk.plan_hash != plan.candidate_hash or risk.validation_hash != plan.validation_hash
                or risk.context_hash != context_hash or risk.config_hash != config_hash):
            raise ValueError("STALE_RISK")
        codes = tuple(sorted(c.course_code for c in candidate.courses))
        if codes in seen:
            raise ValueError("DUPLICATE_COURSE_SET")
        seen.add(codes)
        if set(raw) != set(features) or not sources or not all(sources):
            raise ValueError("FEATURE_MISSING")
        check_finite(*raw.values())
        if any(value < 0 or (key not in {"mandatory", "unlock"} and value > 1) for key, value in raw.items()):
            raise ValueError("FEATURE_OUT_OF_RANGE")
        if abs(raw["safety"] - risk.safety) > 1e-12:
            raise ValueError("SAFETY_MISMATCH")
        scored.append({"plan_id": candidate.plan_id, "plan_version": candidate.plan_version,
            "plan_hash": plan.candidate_hash, "validation_hash": plan.validation_hash,
            "courses": codes, "raw": dict(raw), "normalized": dict(raw), "source_refs": list(sources)})
    scored.sort(key=lambda row: (row["courses"], row["plan_id"], row["plan_version"]))
    ranges = {}
    for feature in ("mandatory", "unlock"):
        values = [row["raw"][feature] for row in scored]
        if not values:
            continue
        low, high = min(values), max(values)
        ranges[feature] = {"min": low, "max": high}
        for row in scored:
            row["normalized"][feature] = (row["raw"][feature] - low) / (high - low) if high > low else 1.0
    for row in scored:
        row["contributions"] = {strategy: {key: row["normalized"][key] * weight
            for key, weight in zip(features, weights)} for strategy, weights in config["weights"].items()}
        row["scores"] = {strategy: sum(parts.values()) for strategy, parts in row["contributions"].items()}
    def order(row, strategy):
        return (-round(row["scores"][strategy], config["comparison_decimals"]),
                row["courses"], row["plan_id"], row["plan_version"])
    selected, trace = [], []
    for strategy in config["slot_order"]:
        for row in sorted(scored, key=lambda item: order(item, strategy)):
            distances = [diversity(set(row["courses"]), set(other["courses"])) for other in selected]
            accepted = all(value >= config["diversity_threshold"] for value in distances)
            trace.append({"strategy": strategy, "plan_id": row["plan_id"], "accepted": accepted,
                "distances_to_selected": distances, "reason": "selected" if accepted else "diversity_or_duplicate"})
            if accepted:
                selected.append(dict(row, strategy=strategy))
                break
    pairwise = [{"left": left["plan_id"], "right": right["plan_id"],
        "distance": diversity(set(left["courses"]), set(right["courses"]))}
        for i, left in enumerate(selected) for right in selected[i + 1:]]
    recommended = min(selected, key=lambda row: order(row, "balanced"))["plan_id"] if selected else None
    pool_hash = "sha256:" + sha256(json.dumps(scored, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    return RankingResult.model_validate({"ranking_version": config["version"], "config_hash": config_hash, "context_hash": context_hash,
        "pool_hash": pool_hash, "normalization_ranges": ranges, "scored_plans": scored,
        "selected_plans": [{"plan_id": row["plan_id"], "strategy": row["strategy"]} for row in selected],
        "pairwise_diversity": pairwise, "selection_trace": trace,
        "shortfall_reason": ("empty_valid_pool" if not scored else "pool_or_diversity_exhausted") if len(selected) < 3 else None,
        "recommended_plan_id": recommended})
