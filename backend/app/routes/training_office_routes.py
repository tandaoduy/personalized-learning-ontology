"""Restricted Training Office API."""
from flask import Blueprint, current_app, jsonify, request, session
from backend.app.routes.auth_routes import ACCOUNTS_PATH
import json

bp = Blueprint("training_office", __name__, url_prefix="/api/training-office")

def _service(): return current_app.training_office_service
def _deny(): return jsonify(success=False, error="TRAINING_OFFICE_ROLE_REQUIRED"), 403
def _reload(): current_app.reload_ontology_services()

@bp.get("/relations")
def relations(): return jsonify(success=True, data=_service().list_relations()) if session.get("role") == "training_office" else _deny()

@bp.get("/courses")
def courses(): return jsonify(success=True, data=_service().list_courses()) if session.get("role") == "training_office" else _deny()

@bp.get("/courses/<course_code>")
def course_detail(course_code):
    if session.get("role") != "training_office": return _deny()
    try: return jsonify(success=True, data=_service().course_detail(course_code))
    except ValueError as exc: return jsonify(success=False, error=str(exc)), 404

@bp.put("/courses/<course_code>")
def update_course(course_code):
    if session.get("role") != "training_office": return _deny()
    try:
        body = request.get_json(silent=True) or {}
        record = _service().update_course(session["username"], course_code, body.get("name"), body.get("credits"),
                                          body.get("prerequisites"), body.get("corequisites"))
        _reload(); return jsonify(success=True, data=record)
    except ValueError as exc: return jsonify(success=False, error=str(exc)), 400

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

@bp.get("/academic-classes")
def academic_classes():
    if session.get("role") != "training_office": return _deny()
    students = current_app.student_data_service.get_all_students()
    all_assignments = _service().assignments()
    assigned = {row["academic_class"]: row for row in all_assignments}
    accounts = json.loads(ACCOUNTS_PATH.read_text(encoding="utf-8")).get("accounts", [])
    advisor_names = {acc["username"]: acc.get("display_name") or acc["username"] for acc in accounts}
    grouped = {}
    for student in students:
        code = str(student.academic_class or "Chưa xếp lớp").strip()
        if code == "Chưa xếp lớp": continue
        grouped.setdefault(code, []).append({"student_id": student.student_id, "name": student.name,
                                             "major": student.major, "semester": student.current_semester})
    rows = []
    for code, items in sorted(grouped.items()):
        asg = assigned.get(code)
        if asg:
            asg = dict(asg)
            asg["advisor_name"] = advisor_names.get(asg.get("advisor_username"), asg.get("advisor_username"))
        rows.append({"academic_class": code, "student_count": len(items), "students": items,
                     "assignment": asg})
    return jsonify(success=True, data=rows)

@bp.get("/advisors")
def advisors():
    if session.get("role") != "training_office": return _deny()
    accounts = json.loads(ACCOUNTS_PATH.read_text(encoding="utf-8")).get("accounts", [])
    assignments = _service().assignments()
    workload = {}
    for row in assignments:
        u = row.get("advisor_username")
        if u:
            workload[u] = workload.get(u, 0) + 1
    rows = [{"username": account["username"],
             "name": account.get("display_name") or account["username"],
             "assigned_classes_count": workload.get(account["username"], 0)}
            for account in accounts if account.get("role") == "advisor" and account.get("status") == "approved"]
    return jsonify(success=True, data=rows)

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
