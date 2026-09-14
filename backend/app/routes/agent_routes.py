"""HTTP API for persisted ontology-constrained Agent planning runs."""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request, session
from pydantic import ValidationError

from backend.app.agent.pipeline import AgentPipeline
from backend.app.schemas import FeedbackRequest, PlanningRequest, RankingResult
from backend.app.services.agent_run_store import FeedbackIdempotencyConflict
from backend.app.services.feedback_service import NORMALIZATION_VERSION, normalize_feedback

bp = Blueprint("agent", __name__, url_prefix="/api/agent")


def _pipeline() -> AgentPipeline:
    app = current_app
    if not app.recommendation_engine or not app.ontology_evidence_service or not app.agent_run_store:
        raise RuntimeError("AGENT_UNAVAILABLE")
    return AgentPipeline(app.student_data_service, app.recommendation_engine,
                         app.ontology_evidence_service, app.agent_orchestrator)


def _allowed_student(student_id: str) -> bool:
    return session.get("role") != "student" or session.get("username") == student_id


def _load_result(run_id: str) -> dict:
    result = current_app.agent_run_store.load_result(run_id)
    if not _allowed_student(result["request"]["student_id"]):
        raise PermissionError("RUN_ACCESS_DENIED")
    return result


def _feedback_and_receipt(run_id: str, result: dict, payload: dict):
    feedback = FeedbackRequest.model_validate(payload)
    if feedback.run_id != run_id:
        raise ValueError("FEEDBACK_RUN_MISMATCH")
    if not _allowed_student(result["request"]["student_id"]):
        raise PermissionError("RUN_ACCESS_DENIED")
    normalization = normalize_feedback(feedback, RankingResult.model_validate(result["ranking"]))
    receipt = current_app.agent_run_store.save_feedback(run_id, feedback, normalization, {
        "tool_name": "normalize_feedback",
        "tool_version": NORMALIZATION_VERSION,
        "parent_result_hash": normalization.parent_result_hash,
        "feedback_hash": normalization.feedback_hash,
    })
    return feedback, normalization, receipt


@bp.post("/runs")
def create_run():
    try:
        planning_request = PlanningRequest.model_validate(request.get_json(silent=True) or {})
        if not _allowed_student(planning_request.student_id):
            return jsonify(success=False, error="RUN_ACCESS_DENIED"), 403
        result = _pipeline().run_planning_flow(planning_request)
        current_app.agent_run_store.save_result(result)
        return jsonify(success=True, data=result), 201
    except ValidationError as exc:
        return jsonify(success=False, error="INVALID_PLANNING_REQUEST", details=exc.errors()), 400
    except RuntimeError as exc:
        return jsonify(success=False, error=str(exc)), 503


@bp.get("/runs/<run_id>")
def get_run(run_id: str):
    try:
        return jsonify(success=True, data=_load_result(run_id))
    except FileNotFoundError:
        return jsonify(success=False, error="RUN_NOT_FOUND"), 404
    except PermissionError as exc:
        return jsonify(success=False, error=str(exc)), 403


@bp.get("/runs/<run_id>/trace")
def get_trace(run_id: str):
    try:
        result = _load_result(run_id)
        return jsonify(success=True, data={"run_id": run_id, "status": result["status"], "trace": result["trace"]})
    except FileNotFoundError:
        return jsonify(success=False, error="RUN_NOT_FOUND"), 404
    except PermissionError as exc:
        return jsonify(success=False, error=str(exc)), 403


@bp.post("/runs/<run_id>/feedback")
def submit_feedback(run_id: str):
    try:
        result = _load_result(run_id)
        _, normalization, receipt = _feedback_and_receipt(run_id, result, request.get_json(silent=True) or {})
        return jsonify(success=True, data={"receipt": receipt.model_dump(mode="json"),
                                           "normalization": normalization.model_dump(mode="json")})
    except ValidationError as exc:
        return jsonify(success=False, error="INVALID_FEEDBACK", details=exc.errors()), 400
    except FeedbackIdempotencyConflict as exc:
        return jsonify(success=False, error="IDEMPOTENCY_CONFLICT", details=str(exc)), 409
    except (ValueError, PermissionError) as exc:
        return jsonify(success=False, error=str(exc)), 422 if isinstance(exc, ValueError) else 403
    except FileNotFoundError:
        return jsonify(success=False, error="RUN_NOT_FOUND"), 404


@bp.post("/runs/<run_id>/replan")
def replan(run_id: str):
    try:
        result = _load_result(run_id)
        feedback, normalization, receipt = _feedback_and_receipt(run_id, result, request.get_json(silent=True) or {})
        if receipt.duplicate:
            return jsonify(success=True, duplicate=True, data={"receipt": receipt.model_dump(mode="json")})
        replanned = _pipeline().replan_from_feedback(result, feedback)
        current_app.agent_run_store.save_result(replanned)
        return jsonify(success=True, data={"receipt": receipt.model_dump(mode="json"), "result": replanned}), 201
    except ValidationError as exc:
        return jsonify(success=False, error="INVALID_FEEDBACK", details=exc.errors()), 400
    except FeedbackIdempotencyConflict as exc:
        return jsonify(success=False, error="IDEMPOTENCY_CONFLICT", details=str(exc)), 409
    except (ValueError, PermissionError) as exc:
        return jsonify(success=False, error=str(exc)), 422 if isinstance(exc, ValueError) else 403
    except FileNotFoundError:
        return jsonify(success=False, error="RUN_NOT_FOUND"), 404


@bp.post("/runs/<run_id>/confirm")
def confirm(run_id: str):
    try:
        result = _load_result(run_id)
        feedback, normalization, receipt = _feedback_and_receipt(run_id, result, request.get_json(silent=True) or {})
        if receipt.duplicate:
            return jsonify(success=True, duplicate=True, data={"receipt": receipt.model_dump(mode="json")})
        confirmed = _pipeline().confirm_from_feedback(result, feedback)
        current_app.agent_run_store.save_result(confirmed)
        return jsonify(success=True, data={"receipt": receipt.model_dump(mode="json"), "result": confirmed},), 201
    except ValidationError as exc:
        return jsonify(success=False, error="INVALID_FEEDBACK", details=exc.errors()), 400
    except FeedbackIdempotencyConflict as exc:
        return jsonify(success=False, error="IDEMPOTENCY_CONFLICT", details=str(exc)), 409
    except (ValueError, PermissionError) as exc:
        return jsonify(success=False, error=str(exc)), 422 if isinstance(exc, ValueError) else 403
    except FileNotFoundError:
        return jsonify(success=False, error="RUN_NOT_FOUND"), 404
