"""Regression checks for clock rollback and ablation accounting."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from backend.app.capabilities import _envelope
from backend.app.capabilities.validation import validate_candidate
from backend.app.schemas import ToolError
from experiments.run_ontology_ablation import context, summarize, validation_outcome, require_output


@pytest.mark.parametrize("delta", [-60, 0, 60])
@pytest.mark.parametrize("success", [False, True])
def test_envelopes_handle_clock_changes(delta, success):
    started = datetime(2026, 10, 2, tzinfo=timezone.utc)
    finished = started + timedelta(seconds=delta)
    ctx = context("run", "call", {})
    payload = ToolError(code="TEST", message="original error")
    with patch.object(_envelope, "now", return_value=finished):
        result = (_envelope.ok if success else _envelope.fail)(
            ctx, "test", payload, started_at=started)
    assert result.provenance.finished_at == max(started, finished)
    assert result.status == ("ok" if success else "error")
    assert (result.output if success else result.error) == payload


def test_validator_exception_survives_clock_rollback():
    started = datetime(2026, 10, 2, tzinfo=timezone.utc)
    with patch("backend.app.capabilities.validation.now", return_value=started), \
         patch.object(_envelope, "now", return_value=started - timedelta(seconds=30)), \
         patch("backend.app.capabilities.validation.StandardValidator") as validator:
        validator.return_value.validate.side_effect = RuntimeError("original failure")
        result = validate_candidate(context("run", "call", {}), None, None, None, None,
                                    min_credits=10, max_credits=18)
    assert validation_outcome(result) == ("error", [], "VALIDATOR_ERROR: original failure")
    with pytest.raises(RuntimeError, match="original failure"):
        require_output(result)


def test_structured_validator_error_preserved():
    result = SimpleNamespace(status="ok", output=SimpleNamespace(status="error", violations=[],
        errors=[ToolError(code="RULE_ERROR", message="rule failed")]))
    assert validation_outcome(result) == ("error", [], "RULE_ERROR: rule failed")


def test_empty_generation_is_in_coverage_but_not_candidate_denominator():
    rows = [dict(configuration="full_ontology", seed=41, attempt=attempt,
                 validation_status=status, released=status == "valid",
                 request_marker=True, violations=[])
            for attempt, status in [(1, "valid"), (0, "no_candidates"), (1, "error")]]
    summary = summarize(rows, (41,))["full_ontology"]
    seed = summary["per_seed"][0]
    assert seed["profiles"] == 3
    assert seed["candidate_attempts_before_filter"] == 2
    assert seed["candidate_attempt_validity"] == 0.5
    assert seed["final_recommendation_coverage"] == 1 / 3
    assert summary["validator_errors"] == 1
    assert not any(summary["violations_by_rule"].values())
