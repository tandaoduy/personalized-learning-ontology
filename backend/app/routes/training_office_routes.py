"""Restricted Training Office API."""
from flask import Blueprint, current_app, jsonify, request, session

bp = Blueprint("training_office", __name__, url_prefix="/api/training-office")

def _service(): return current_app.training_office_service
def _deny(): return jsonify(success=False, error="TRAINING_OFFICE_ROLE_REQUIRED"), 403
def _reload(): current_app.reload_ontology_services()

@bp.get("/relations")
def relations(): return jsonify(success=True, data=_service().list_relations()) if session.get("role") == "training_office" else _deny()

@bp.put("/relations/<relation>")
def relation(relation):
    if session.get("role") != "training_office": return _deny()
    try:
        body = request.get_json(silent=True) or {}
        record = _service().set_relation(session["username"], relation, body.get("course_code"), body.get("related_course_code"), bool(body.get("enabled")))
        _reload(); return jsonify(success=True, data=record)
    except ValueError as exc: return jsonify(success=False, error=str(exc)), 400

@bp.get("/programs")
def programs(): return jsonify(success=True, data=_service().list_programs()) if session.get("role") == "training_office" else _deny()

@bp.post("/programs")
def create_program():
    if session.get("role") != "training_office": return _deny()
    try:
        body = request.get_json(silent=True) or {}; record = _service().create_program(session["username"], body.get("program_id"), body.get("name")); _reload()
        return jsonify(success=True, data=record), 201
    except ValueError as exc: return jsonify(success=False, error=str(exc)), 400

@bp.put("/programs/<program_id>")
def update_program(program_id):
    if session.get("role") != "training_office": return _deny()
    try:
        body = request.get_json(silent=True) or {}
        record = _service().update_program(session["username"], program_id, body.get("name")); _reload()
        return jsonify(success=True, data=record)
    except ValueError as exc: return jsonify(success=False, error=str(exc)), 400

@bp.delete("/programs/<program_id>")
def archive_program(program_id):
    if session.get("role") != "training_office": return _deny()
    try:
        record = _service().archive_program(session["username"], program_id); _reload(); return jsonify(success=True, data=record)
    except ValueError as exc: return jsonify(success=False, error=str(exc)), 404

@bp.get("/advisor-assignments")
def assignments(): return jsonify(success=True, data=_service().assignments()) if session.get("role") == "training_office" else _deny()

@bp.post("/advisor-assignments")
def assign():
    if session.get("role") != "training_office": return _deny()
    try:
        body = request.get_json(silent=True) or {}; return jsonify(success=True, data=_service().assign_advisor(session["username"], body.get("advisor_username"), body.get("academic_class"))), 201
    except ValueError as exc: return jsonify(success=False, error=str(exc)), 400

@bp.delete("/advisor-assignments")
def revoke():
    if session.get("role") != "training_office": return _deny()
    try:
        body = request.get_json(silent=True) or {}; _service().revoke_advisor(session["username"], body.get("advisor_username"), body.get("academic_class")); return jsonify(success=True)
    except ValueError as exc: return jsonify(success=False, error=str(exc)), 404
