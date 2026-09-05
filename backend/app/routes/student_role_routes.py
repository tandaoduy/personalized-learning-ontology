"""
Student-facing page routes.
"""

from flask import Blueprint, redirect, render_template, session, url_for, current_app

bp = Blueprint("student_role", __name__, url_prefix="/student")


@bp.route("")
def index():
    return redirect(url_for("student_role.dashboard"))

@bp.route("/history")
def history():
    """Read-only view of student's learning history."""
    if session.get("role") != "student":
        return redirect(url_for("index"))
        
    student_id = session.get("username", "")
    
    # Get student data
    student_service = current_app.student_data_service
    student = student_service.get_student(student_id)
    student_data = student.to_dict() if student else None

    # Get course catalog
    engine = current_app.recommendation_engine
    course_catalog = []
    if engine:
        from backend.app.routes.student_routes import _get_course_catalog
        catalog_dict = _get_course_catalog(engine)
        course_catalog = sorted(catalog_dict.values(), key=lambda x: (x["code"], x["name"]))

    return render_template(
        "student/history.html",
        username=student_id,
        display_name=session.get("display_name", ""),
        student_data=student_data,
        course_catalog=course_catalog
    )

@bp.route("/dashboard")
def dashboard():
    """Student workspace for profile updates and learning-plan generation."""
    if session.get("role") != "student":
        return redirect(url_for("index"))
    
    student_id = session.get("username", "")
    student = current_app.student_data_service.get_student(student_id)
    student_data = student.to_dict() if student else None

    course_catalog = []
    engine = current_app.recommendation_engine
    if engine:
        from backend.app.routes.student_routes import _get_course_catalog
        catalog_dict = _get_course_catalog(engine)
        course_catalog = sorted(catalog_dict.values(), key=lambda item: (item["code"], item["name"]))

    return render_template(
        "student/dashboard.html",
        username=student_id,
        student_data=student_data,
        course_catalog=course_catalog,
    )


@bp.route("/profile")
def profile():
    """Student profile and course-history entry page."""
    if session.get("role") != "student":
        return redirect(url_for("index"))
    
    from flask import current_app
    engine = current_app.recommendation_engine
    cohorts_data = []
    if engine:
        cohorts_data = [
            cohort for cohort in getattr(engine, "cohorts", [])
            if cohort.get("code") in {"K65", "K66", "K67"}
        ]

    return render_template("student/profile.html", cohorts=cohorts_data)


@bp.route("/plan")
def plan():
    """Student recommendation and roadmap page."""
    if session.get("role") != "student":
        return redirect(url_for("index"))
        
    student_id = session.get("username", "")
    return render_template(
        "student/plan.html",
        username=student_id,
        display_name=session.get("display_name", "")
    )
