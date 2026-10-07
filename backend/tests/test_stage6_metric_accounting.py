"""Regression tests for the shared Stage 6 request-level metric contract."""
from types import SimpleNamespace

import pytest

from experiments.run_stage6_baselines import request_row, summarize


def test_request_row_records_internal_emitted_valid_and_coverage_units():
    row = request_row(
        "BL-05-agent-with-ontology", "B0001", 41, 3,
        [SimpleNamespace(status="valid"), SimpleNamespace(status="invalid")],
    )
    assert row["internal_attempt_count"] == 3
    assert row["emitted_candidate_count"] == 2
    assert row["valid_emitted_candidate_count"] == 1
    assert row["request_has_valid_final_plan"] is True


def test_request_row_rejects_more_emitted_candidates_than_internal_attempts():
    with pytest.raises(ValueError, match="INVALID_GENERATION_METRIC_COUNTS"):
        request_row("BL-05-agent-with-ontology", "B0001", 41, 1,
                    [SimpleNamespace(status="valid"), SimpleNamespace(status="invalid")])


def test_coverage_is_request_level_not_candidate_level():
    requests = [
        {"method": "BL-05-agent-with-ontology", "seed": 41, "internal_attempt_count": 3,
         "emitted_candidate_count": 2, "valid_emitted_candidate_count": 1,
         "request_has_valid_final_plan": True},
        {"method": "BL-05-agent-with-ontology", "seed": 41, "internal_attempt_count": 2,
         "emitted_candidate_count": 0, "valid_emitted_candidate_count": 0,
         "request_has_valid_final_plan": False},
    ]
    summary = summarize([], requests, (41,))["BL-05-agent-with-ontology"]["per_seed"][0]
    assert summary["internal_generation_yield"] == 2 / 5
    assert summary["emitted_candidate_validity"] == 1 / 2
    assert summary["final_recommendation_coverage"] == 1 / 2
