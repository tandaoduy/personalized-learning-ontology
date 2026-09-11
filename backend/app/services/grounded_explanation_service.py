"""Build Vietnamese explanations only from Validator, Risk and Ranking evidence."""
from hashlib import sha256

from backend.app.schemas import (
    GroundedClaim, GroundedExplanation, GroundedExplanationBatch,
    RankingResult, RiskBatch, ValidatedPlan,
)

TEMPLATE_VERSION = "grounded-explanation-vi-v1"


def ranking_hash(ranking: RankingResult) -> str:
    return "sha256:" + sha256(ranking.model_dump_json().encode("utf-8")).hexdigest()


def _classification(fact) -> str:
    if fact.is_required_specialization:
        return "Học phần bắt buộc chuyên ngành"
    if fact.is_elective_specialization:
        return "Học phần tự chọn chuyên ngành"
    if fact.is_required_major:
        return "Học phần bắt buộc ngành"
    if fact.is_elective_major:
        return "Học phần tự chọn ngành"
    raise ValueError("COURSE_CLASSIFICATION_EVIDENCE_MISSING")


def build_grounded_explanations(plans: tuple[ValidatedPlan, ...], risks: RiskBatch,
                                ranking: RankingResult) -> GroundedExplanationBatch:
    """Return claims whose factual content is linked to ontology/rule evidence.

    This service never infers a course category from its name, score or
    specialization membership alone.
    """
    if not plans or not ranking.selected_plans:
        raise ValueError("EXPLANATION_INPUT_EMPTY")
    rank_hash = ranking_hash(ranking)
    plan_by_id = {item.candidate.plan_id: item for item in plans}
    risk_by_hash = {item.plan_hash: item for item in risks.results}
    score_by_id = {item.plan_id: item for item in ranking.scored_plans}
    strategy_by_id = {item.plan_id: item.strategy for item in ranking.selected_plans}
    if set(strategy_by_id) - set(plan_by_id) or set(strategy_by_id) - set(score_by_id):
        raise ValueError("EXPLANATION_PLAN_MISMATCH")

    output = []
    for plan_id in sorted(strategy_by_id):
        plan = plan_by_id[plan_id]
        validation = plan.validation
        if validation.status != "valid":
            raise ValueError("EXPLANATION_REQUIRES_VALID_PLAN")
        risk = risk_by_hash.get(plan.candidate_hash)
        if risk is None or risk.validation_hash != plan.validation_hash:
            raise ValueError("EXPLANATION_RISK_MISMATCH")
        scored = score_by_id[plan_id]
        facts = {fact.course_code: fact for fact in validation.ontology_evidence if fact.query_id == "Q_CATEGORY_01"}
        claims = []
        for course in plan.candidate.courses:
            fact = facts.get(course.course_code)
            if fact is None:
                raise ValueError("COURSE_CLASSIFICATION_EVIDENCE_MISSING")
            label = _classification(fact)
            claims.append(GroundedClaim(
                claim_id=f"claim-{plan_id}-{course.course_code}-classification",
                kind="course_classification",
                text=f"{course.course_code} ({course.credits:g} tín chỉ) là {label.lower()}.",
                decision_ids=(f"classification:{course.course_code}",),
                evidence_ids=(fact.evidence_id,), source_refs=(fact.source_ref,), course_code=course.course_code,
            ))
        validation_ids = tuple(record.evidence_id for record in validation.evidence if record.rule_id == "credit_limit")
        if not validation_ids:
            raise ValueError("VALIDATION_EVIDENCE_MISSING")
        claims.append(GroundedClaim(
            claim_id=f"claim-{plan_id}-validation", kind="validation",
            text="Phương án hợp lệ theo toàn bộ các ràng buộc học vụ đã được kiểm tra.",
            decision_ids=(f"validation:{plan_id}:valid",), evidence_ids=validation_ids,
            source_refs=tuple(sorted({record.source_ref for record in validation.evidence if record.rule_id == "credit_limit"})),
        ))
        claims.append(GroundedClaim(
            claim_id=f"claim-{plan_id}-risk", kind="risk",
            text=f"Rủi ro của phương án là {risk.risk_score:.4f} ({risk.risk_level}); độ an toàn là {risk.safety:.2%}.",
            decision_ids=(f"risk:{plan.candidate_hash}",), evidence_ids=validation_ids,
            source_refs=risk.source_refs,
        ))
        strategy = strategy_by_id[plan_id]
        claims.append(GroundedClaim(
            claim_id=f"claim-{plan_id}-ranking", kind="ranking",
            text=f"Phương án được chọn cho chiến lược {strategy} với điểm {scored.scores[strategy]:.4f}.",
            decision_ids=(f"ranking:{plan_id}:{strategy}",), evidence_ids=validation_ids,
            source_refs=tuple(sorted(set(scored.source_refs))),
        ))
        output.append(GroundedExplanation(
            plan_id=plan_id, plan_hash=plan.candidate_hash, validation_hash=plan.validation_hash,
            ranking_hash=rank_hash, knowledge_versions=plan.candidate.knowledge_versions,
            template_version=TEMPLATE_VERSION, claims=tuple(claims),
        ))
    return GroundedExplanationBatch(ranking_hash=rank_hash, explanations=tuple(output))
