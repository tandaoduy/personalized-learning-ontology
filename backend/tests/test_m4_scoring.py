"""M4 hand calculations and gates over plans certified by the real Validator."""
from datetime import datetime, timezone
from hashlib import sha256

import pytest
from rdflib import Graph, Literal, URIRef

from backend.app.schemas import CandidatePlan, KnowledgeSnapshot, KnowledgeVersion, StudentSnapshot, ValidatedPlan
from backend.app.services.ontology_evidence_service import BASE, CODE, OntologyEvidenceService
from backend.app.services.plan_ranking_service import dependency_unlock, diversity, fit_credits, goal_fit, rank_valid_plans
from backend.app.services.plan_risk_service import assess_plan_risk
from backend.app.validation.prerequisite_rule import RULE_VERSION
from backend.app.validation.validator import StandardValidator


def digest(model):
    return "sha256:" + sha256(model.model_dump_json().encode()).hexdigest()


@pytest.fixture
def valid_plan(tmp_path):
    graph = Graph()
    codes = tuple("ABCDEFGH")
    for code in codes:
        subject = URIRef(BASE + code)
        for predicate, value in [(CODE, Literal(code)), (URIRef(BASE + "hasCredit"), Literal(3)),
                (URIRef(BASE + "isRequiredForMajor"), URIRef(BASE + "CNTT")),
                (URIRef(BASE + "openSemesterType"), Literal(3))]:
            graph.add((subject, predicate, value))
    path = tmp_path / "m4.rdf"
    graph.serialize(path, format="xml")
    evidence = OntologyEvidenceService(path)
    now = datetime.now(timezone.utc)
    versions = KnowledgeVersion(student_version="s1", curriculum_version="c1",
        ontology_version=evidence.ontology_version, rule_version=RULE_VERSION, offering_version="o1")
    student = StudentSnapshot(student_id="S", student_version="s1", curriculum_id="c1",
        major_id=BASE + "CNTT", current_semester=2, captured_at=now)
    knowledge = KnowledgeSnapshot(snapshot_id="k1", versions=versions, captured_at=now,
        curriculum_id="c1", target_term_id="t1", ontology_ref=evidence.source_ref, rules_ref=RULE_VERSION,
        offerings_ref="o1", target_semester_type=1, curriculum_courses=frozenset(codes),
        prior_study_requirements=tuple({"course_code": c, "required_courses": []} for c in codes))
    def create(selected, lower=0, upper=12):
        candidate = CandidatePlan(plan_id="p-" + selected, plan_version="v1", request_id="r1", student_id="S",
            target_term_id="t1", knowledge_versions=versions, plan_type="safe",
            courses=tuple({"course_code": c, "credits": 3} for c in selected))
        validation = StandardValidator(evidence, min_credits=lower, max_credits=upper).validate(candidate, student, knowledge)
        assert validation.status == "valid"
        return ValidatedPlan(candidate=candidate, candidate_hash=digest(candidate),
            validation=validation, validation_hash=digest(validation))
    return create


def risk(plan, **kwargs):
    return assess_plan_risk(plan, lower=kwargs.pop("lower", 0), upper=kwargs.pop("upper", 12),
        retake_codes=kwargs.pop("retake_codes", frozenset()), academic_status=kwargs.pop("academic_status", "normal"),
        source_refs=("fixture:explicit-policy",), context_hash="context-v1", **kwargs)


def row(plan, mandatory=3, unlock=0):
    assessment = risk(plan)
    fit = fit_credits(plan.candidate.total_credits, 6, 0, 12)
    return (plan, {"goal_fit": 1.0, "mandatory": mandatory, "unlock": unlock,
        "credit_fit": fit, "workload": fit, "safety": assessment.safety}, ("fixture:features",), assessment)


def rank(rows, versions):
    return rank_valid_plans(rows, request_id="r1", knowledge_versions=versions, context_hash="context-v1")


def test_risk_matches_hand_calculation(valid_plan):
    assessment = risk(valid_plan("AB"), retake_codes=frozenset({"A"}), academic_status="mild_warning")
    assert assessment.components.model_dump() == {"load": .5, "retake": .5, "academic": .5}
    assert assessment.risk_score == pytest.approx(.5)


def test_scores_match_hand_calculation_and_are_order_independent(valid_plan):
    a, bc = valid_plan("A"), valid_plan("BC")
    rows = [row(a, 3, 0), row(bc, 6, 2)]
    result = rank(rows, a.candidate.knowledge_versions)
    assert result == rank(list(reversed(rows)), a.candidate.knowledge_versions)
    scores = {p.plan_id: p.scores["safe"] for p in result.scored_plans}
    assert scores == pytest.approx({"p-A": .525, "p-BC": .95})
    assert [p.model_dump() for p in result.selected_plans] == [{"plan_id": "p-BC", "strategy": "safe"}, {"plan_id": "p-A", "strategy": "balanced"}]
    assert result.recommended_plan_id == "p-BC"
    assert result.pairwise_diversity[0].distance == 1


@pytest.mark.parametrize("size", [0, 1, 2, 3])
def test_small_pools_and_constant_normalization(valid_plan, size):
    plans = [valid_plan(code) for code in "ABC"]
    result = rank([row(p) for p in plans[:size]], plans[0].candidate.knowledge_versions)
    assert len(result.selected_plans) == size
    assert bool(result.shortfall_reason) == (size < 3)
    for p in result.scored_plans:
        assert p.normalized["mandatory"] == p.normalized["unlock"] == 1


def test_pool_changes_recompute_normalization(valid_plan):
    a, b, c = [valid_plan(code) for code in "ABC"]
    first = rank([row(a, 3), row(b, 6)], a.candidate.knowledge_versions)
    second = rank([row(a, 3), row(b, 6), row(c, 9)], a.candidate.knowledge_versions)
    assert first.pool_hash != second.pool_hash
    assert next(p for p in second.scored_plans if p.plan_id == "p-B").normalized["mandatory"] == .5


def test_stale_candidate_is_rejected_even_with_recomputed_wrapper_hash(valid_plan):
    original = valid_plan("A")
    changed = original.candidate.model_copy(update={"courses": valid_plan("B").candidate.courses})
    forged = original.model_copy(update={"candidate": changed, "candidate_hash": digest(changed)})
    with pytest.raises(ValueError, match="STALE_VALIDATION"):
        risk(forged)


def test_missing_academic_status_and_changed_credit_policy_are_rejected(valid_plan):
    plan = valid_plan("A")
    with pytest.raises(ValueError, match="ACADEMIC_STATUS_MISSING"):
        risk(plan, academic_status="unknown")
    with pytest.raises(ValueError, match="CREDIT_POLICY_MISMATCH"):
        risk(plan, upper=27)


def test_duplicate_pool_and_stale_risk_are_rejected(valid_plan):
    plan = valid_plan("A")
    with pytest.raises(ValueError, match="DUPLICATE_COURSE_SET"):
        rank([row(plan), row(plan)], plan.candidate.knowledge_versions)
    inputs = row(plan)
    inputs = (*inputs[:3], inputs[3].model_copy(update={"context_hash": "other"}))
    with pytest.raises(ValueError, match="STALE_RISK"):
        rank([inputs], plan.candidate.knowledge_versions)


def test_equal_bounds_and_goal_edge_cases(valid_plan):
    assert risk(valid_plan("A", 3, 3), lower=3, upper=3).components.load == 0
    assert fit_credits(3, 3, 3, 3) == 1
    assert goal_fit(((1, 1), (.5, 1))) == .75
    with pytest.raises(ValueError, match="GOAL_WEIGHTS_ZERO"):
        goal_fit(((1, 0),))
    with pytest.raises(ValueError, match="GOAL_CRITERIA_MISSING"):
        goal_fit(())


def test_unlock_counts_new_edges_once_and_diversity_is_distance():
    assert dependency_unlock({"A"}, {"B"}, {"C": {"A", "B"}, "D": {"B"}, "A": {"B"}}) == 1
    assert diversity(set("ABCDEF"), set("ABCDEG")) == pytest.approx(2 / 7)


def test_near_duplicates_do_not_fill_three_slots(valid_plan):
    a, b = valid_plan("ABCDEF", upper=24), valid_plan("ABCDEG", upper=24)
    rows = []
    for plan in (a, b):
        assessment = risk(plan, upper=24)
        rows.append((plan, {"goal_fit": 1, "mandatory": 18, "unlock": 0,
            "credit_fit": 1, "workload": 1, "safety": assessment.safety}, ("fixture:features",), assessment))
    result = rank(rows, a.candidate.knowledge_versions)
    assert len(result.selected_plans) == 1
    assert result.shortfall_reason == "pool_or_diversity_exhausted"
    assert any(not attempt.accepted for attempt in result.selection_trace)


@pytest.mark.parametrize("status", ["invalid", "partially_validated", "error"])
def test_uncertified_plans_cannot_enter_risk(valid_plan, status):
    plan = valid_plan("A")
    changed = plan.model_copy(update={"validation": plan.validation.model_copy(update={"status": status})})
    with pytest.raises(ValueError):
        risk(changed)
