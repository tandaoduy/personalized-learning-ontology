"""Regression checks for Stage-6 emitted-candidate accounting."""
import pytest

from experiments.run_stage6_baselines import request_row, summarize


def test_validator_error_remains_an_emitted_candidate():
    requests = [
        request_row(
            "BL-05-agent-with-ontology", "B0001", 41, 2,
            [("valid", object(), None), ("error", None, "VALIDATOR_ERROR: unavailable")],
        )
    ]
    candidates = [
        {"method": "BL-05-agent-with-ontology", "seed": 41, "status": "valid", "violations": [],
         "evidence_checks": 0, "evidenced_checks": 0, "latency_seconds": 0, "diversity": [], "over_timeout_budget": False},
        {"method": "BL-05-agent-with-ontology", "seed": 41, "status": "error", "violations": [],
         "evidence_checks": 0, "evidenced_checks": 0, "latency_seconds": 0, "diversity": [], "over_timeout_budget": False},
    ]
    summary = summarize(candidates, requests, (41,))["BL-05-agent-with-ontology"]
    seed = summary["per_seed"][0]
    assert seed["internal_attempt_count"] == 2
    assert seed["emitted_candidate_count"] == 2
    assert seed["valid_emitted_candidate_count"] == 1
    assert seed["emitted_candidate_validity"] == 0.5
    assert seed["final_recommendation_coverage"] == 1.0
    assert seed["validator_errors"] == 1
    assert summary["validator_errors"] == 1


def test_impossible_emitted_count_is_rejected():
    requests = [request_row("BL-05-agent-with-ontology", "B0001", 41, 1, [])]
    requests[0]["emitted_candidate_count"] = 2
    with pytest.raises(ValueError, match="INVALID_GENERATION_METRIC_COUNTS"):
        summarize([], requests, (41,))
