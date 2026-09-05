"""
Advisor-facing page routes and API endpoints for consultations and evaluations.
"""

import json
from datetime import datetime
from pathlib import Path

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, session, url_for

bp = Blueprint("advisor_role", __name__, url_prefix="/advisor")
api_bp = Blueprint("advisor_api", __name__, url_prefix="/api/advisor")

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
CONSULTATIONS_PATH = DATA_DIR / "consultations.json"
EVALUATIONS_PATH = DATA_DIR / "evaluations.json"
ADVISOR_AUDIT_PATH = DATA_DIR / "advisor_activity_log.json"


def _load_json_file(path: Path, default_data):
    if not path.exists():
        return default_data
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default_data


def _save_json_file(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _append_advisor_audit(event_type: str, record: dict):
    """Lưu nhật ký chung phục vụ kiểm tra và làm tài liệu nghiệp vụ."""
    audit = _load_json_file(ADVISOR_AUDIT_PATH, {
        "schema_version": 1,
        "records": [],
    })
    audit.setdefault("schema_version", 1)
    audit.setdefault("records", []).append({
        "event_id": f"AUDIT_{int(datetime.now().timestamp() * 1000)}",
        "event_type": event_type,
        "created_at": record.get("created_at") or datetime.now().isoformat(timespec="seconds"),
        "advisor_username": record.get("advisor_username", "system"),
        "advisor_name": record.get("advisor_name", "Cố vấn học tập"),
        "student_id": record.get("student_id"),
        "student_name": record.get("student_name"),
        "record": record,
    })
    _save_json_file(ADVISOR_AUDIT_PATH, audit)


def _validate_advisor_plan(student_id: str, courses: list[dict]) -> tuple[list[dict], list[str], int]:
    """Validate advisor-selected courses against the same rules as recommendation."""
    service = current_app.student_data_service
    student = service.get_student(student_id)
    if not student:
        return [], ["Không tìm thấy sinh viên."], 0

    engine = current_app.recommendation_engine
    if engine is None:
        return [], ["Bộ máy kiểm tra điều kiện học vụ chưa sẵn sàng."], 0

    result = engine.get_recommendation(student, priority_mode="standard")
    eligible_codes = {str(course.code).upper() for course in result.eligible_courses}
    excluded_by_code = {
        str(course.code).upper(): list(getattr(course, "failed_rules", []) or [])
        for course in result.excluded_courses
    }
    rule_labels = {
        "prerequisite": "chưa thỏa điều kiện tiên quyết",
        "open_semester": "không mở trong học kỳ kế tiếp",
        "recommended_semester": "chưa đến học kỳ khuyến nghị",
        "forced_semester": "không đúng ràng buộc học kỳ",
        "specialization": "không thuộc chuyên ngành của sinh viên",
        "already_completed": "đã hoàn thành",
        "elective_quota": "đã đủ hạn ngạch học phần tự chọn",
    }

    validated_courses = []
    errors = []
    seen_codes = set()
    for raw_course in courses:
        code = str(raw_course.get("course_code") or raw_course.get("code") or "").strip().upper()
        if not code or code in seen_codes:
            continue
        seen_codes.add(code)
        course_info = engine.course_data.get(code)
        if not course_info:
            errors.append(f"Không tìm thấy học phần {code} trong danh mục.")
            continue
        if code not in eligible_codes:
            reasons = [rule_labels.get(rule, rule) for rule in excluded_by_code.get(code, [])]
            detail = ", ".join(reasons) if reasons else "không đủ điều kiện học vụ ở thời điểm hiện tại"
            errors.append(f"{code} - {course_info.get('name', code)}: {detail}.")
            continue

        normalized = dict(raw_course)
        normalized["course_code"] = code
        normalized["course_name"] = course_info.get("name", code)
        normalized["credits"] = float(course_info.get("credits", 0) or 0)
        validated_courses.append(normalized)

    total_credits = sum(course["credits"] for course in validated_courses)
    max_credits = int(current_app.config.get("REGISTER_MAX_CREDITS", 27))
    if total_credits > max_credits:
        errors.append(f"Tổng số tín chỉ {total_credits:g} vượt quá mức tối đa {max_credits} tín chỉ.")

    return validated_courses, errors, total_credits


# --- UI Page Routes (Các trang chức năng riêng biệt, không dùng chung) ---

@bp.route("")
@bp.route("/dashboard")
def dashboard():
    """Trang chủ CVHT hiển thị lưới thẻ SVG chuyển đến từng chức năng riêng biệt."""
    if session.get("role") != "advisor":
        return redirect(url_for("index"))
    return render_template("advisor/dashboard.html")


@bp.route("/students")
def students():
    """Trang riêng: Tìm kiếm và lọc sinh viên đa chiều."""
    if session.get("role") != "advisor":
        return redirect(url_for("index"))
    return render_template("advisor/students.html")


@bp.route("/at-risk")
def at_risk():
    """Trang riêng: Nhận diện sinh viên nguy cơ chậm tiến độ."""
    if session.get("role") != "advisor":
        return redirect(url_for("index"))
    return render_template("advisor/at-risk.html")


@bp.route("/profile")
def profile():
    """Trang riêng: Xem hồ sơ và lịch sử học phần sinh viên."""
    if session.get("role") != "advisor":
        return redirect(url_for("index"))
    return render_template("advisor/profile.html")


@bp.route("/student-editor")
def student_editor():
    """Trang riêng: Thêm mới hoặc Cập nhật hồ sơ học tập sinh viên (giao diện như sinh viên tự cập nhật)."""
    if session.get("role") != "advisor":
        return redirect(url_for("index"))
    from flask import current_app
    engine = current_app.recommendation_engine
    cohorts_data = []
    if engine:
        cohorts_data = getattr(engine, "cohorts", [])
    return render_template("advisor/student_editor.html", cohorts=cohorts_data)


@bp.route("/scenarios")
def scenarios():
    """Trang riêng: Chạy thuật toán gợi ý theo các kịch bản & xem chuỗi tiên quyết."""
    if session.get("role") != "advisor":
        return redirect(url_for("index"))
    return render_template("advisor/scenarios.html")


@bp.route("/consultation")
def consultation():
    """Trang riêng: Chốt xác nhận kế hoạch và ghi nhận xét tư vấn."""
    if session.get("role") != "advisor":
        return redirect(url_for("index"))
    return render_template("advisor/consultation.html")


@bp.route("/reports")
def reports():
    """Trang riêng: Xuất báo cáo tư vấn và ghi nhận đánh giá 5 sao về hệ thống."""
    if session.get("role") != "advisor":
        return redirect(url_for("index"))
    return render_template("advisor/reports.html")


# --- REST API Routes ---

@api_bp.route("/stats", methods=["GET"])
def get_stats():
    """Trả về số liệu thống kê tổng quan cho màn hình Dashboard CVHT."""
    try:
        service = current_app.student_data_service
        students_list = service.get_all_students()
        total_students = len(students_list)
        
        analyzer = getattr(current_app, "progress_risk_analyzer", None)
        at_risk_count = 0
        for s in students_list:
            is_risk = False
            if analyzer:
                try:
                    res = analyzer.assess_student(s.__dict__, current_app.recommendation_engine)
                    if res.get("progress_status") == "BEHIND_SCHEDULE":
                        is_risk = True
                except Exception:
                    pass
            if not is_risk and not analyzer:
                gpa = getattr(s, "gpa_accumulated", 0.0)
                failed = getattr(s, "failed_courses", []) or []
                if gpa < 2.0 or len(failed) > 0:
                    is_risk = True
            if is_risk:
                at_risk_count += 1
                
        consultations_data = _load_json_file(CONSULTATIONS_PATH, {"consultations": []})
        total_consultations = len(consultations_data.get("consultations", []))
        
        evaluations_data = _load_json_file(EVALUATIONS_PATH, {"evaluations": []})
        evals = evaluations_data.get("evaluations", [])
        avg_rating = 5.0
        if evals:
            total_score = sum(
                (float(e.get("accuracy_rating", 5)) + float(e.get("usefulness_rating", 5))) / 2.0
                for e in evals
            )
            avg_rating = round(total_score / len(evals), 1)
            
        return jsonify({
            "success": True,
            "data": {
                "total_students": total_students,
                "at_risk_students": at_risk_count,
                "total_consultations": total_consultations,
                "average_rating": avg_rating,
            }
        })
    except Exception as exc:
        current_app.logger.exception("Lỗi lấy thống kê CVHT: %s", exc)
        return jsonify({"success": False, "error": "Không thể xử lý yêu cầu lúc này."}), 500
@api_bp.route("/validate-plan", methods=["POST"])
def validate_plan():
    """Check an advisor-edited plan before it is added or confirmed."""
    if session.get("role") != "advisor":
        return jsonify({"success": False, "error": "Advisor role required."}), 403

    payload = request.get_json(silent=True) or {}
    student_id = str(payload.get("student_id") or "").strip()
    courses = payload.get("recommended_courses")
    if not student_id or not isinstance(courses, list):
        return jsonify({"success": False, "error": "student_id and recommended_courses are required."}), 400

    validated_courses, errors, total_credits = _validate_advisor_plan(student_id, courses)
    return jsonify({
        "success": not errors,
        "data": {
            "courses": validated_courses,
            "total_credits": total_credits,
            "errors": errors,
        },
        "error": " ".join(errors) if errors else None,
    }), 200 if not errors else 422


@api_bp.route("/consultations", methods=["POST"])
def save_consultation():
    if session.get("role") != "advisor":
        return jsonify({"success": False, "error": "Advisor role required."}), 403

    """Lưu nhận xét tư vấn và kế hoạch học tập đã xác nhận cho sinh viên."""
    try:
        payload = request.get_json(silent=True) or {}
        student_id = str(payload.get("student_id") or "").strip()
        if not student_id:
            return jsonify({"success": False, "error": "student_id là bắt buộc"}), 400
            
        raw_courses = payload.get("recommended_courses")
        if not isinstance(raw_courses, list):
            return jsonify({"success": False, "error": "recommended_courses must be a list."}), 400
        validated_courses, validation_errors, total_credits = _validate_advisor_plan(student_id, raw_courses)
        if validation_errors:
            return jsonify({"success": False, "error": " ".join(validation_errors)}), 422

        data = _load_json_file(CONSULTATIONS_PATH, {"consultations": []})
        
        record = {
            "id": f"CONS_{int(datetime.now().timestamp() * 1000)}",
            "student_id": student_id,
            "student_name": str(payload.get("student_name") or "").strip(),
            "advisor_username": session.get("username", "system"),
            "advisor_name": session.get("display_name", "Cố vấn học tập"),
            "notes": str(payload.get("notes") or "").strip(),
            "recommended_courses": validated_courses,
            "scenario_used": str(payload.get("scenario_used") or "Tối ưu chuẩn").strip(),
            "total_credits": total_credits,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        
        data.setdefault("consultations", []).append(record)
        _save_json_file(CONSULTATIONS_PATH, data)
        _append_advisor_audit("plan_confirmation", record)
        
        current_app.logger.info("Đã lưu tư vấn cho sinh viên")
        return jsonify({
            "success": True,
            "message": "Đã ghi nhận nhận xét và xác nhận kế hoạch thành công.",
            "data": record,
        })
    except Exception as exc:
        current_app.logger.exception("Lỗi lưu nhận xét tư vấn: %s", exc)
        return jsonify({"success": False, "error": "Không thể xử lý yêu cầu lúc này."}), 500


@api_bp.route("/consultations/<student_id>", methods=["GET"])
def get_student_consultations(student_id: str):
    """Lấy lịch sử tư vấn của một sinh viên cụ thể."""
    try:
        data = _load_json_file(CONSULTATIONS_PATH, {"consultations": []})
        records = [
            r for r in data.get("consultations", [])
            if str(r.get("student_id") or "").strip().lower() == str(student_id).strip().lower()
        ]
        records.sort(key=lambda x: str(x.get("created_at", "")), reverse=True)
        return jsonify({
            "success": True,
            "data": records,
            "total": len(records),
        })
    except Exception as exc:
        current_app.logger.exception("Lỗi lấy lịch sử tư vấn cho sinh viên")
        return jsonify({"success": False, "error": "Không thể xử lý yêu cầu lúc này."}), 500


@api_bp.route("/evaluations", methods=["POST"])
def save_evaluation():
    if session.get("role") != "advisor":
        return jsonify({"success": False, "error": "Advisor role required."}), 403

    """Ghi nhận đánh giá của CVHT về độ chính xác và hữu ích của hệ thống."""
    try:
        payload = request.get_json(silent=True) or {}
        data = _load_json_file(EVALUATIONS_PATH, {"evaluations": []})
        
        try:
            acc_rating = int(payload.get("accuracy_rating", 5))
            use_rating = int(payload.get("usefulness_rating", 5))
        except (ValueError, TypeError):
            acc_rating, use_rating = 5, 5
            
        record = {
            "id": f"EVAL_{int(datetime.now().timestamp() * 1000)}",
            "advisor_username": session.get("username", "system"),
            "advisor_name": session.get("display_name", "Cố vấn học tập"),
            "accuracy_rating": max(1, min(5, acc_rating)),
            "usefulness_rating": max(1, min(5, use_rating)),
            "comments": str(payload.get("comments") or "").strip(),
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        
        data.setdefault("evaluations", []).append(record)
        _save_json_file(EVALUATIONS_PATH, data)
        _append_advisor_audit("system_evaluation", record)
        
        current_app.logger.info("Đã lưu đánh giá từ CVHT")
        return jsonify({
            "success": True,
            "message": "Cảm ơn ý kiến phản hồi và đánh giá của bạn!",
            "data": record,
        })
    except Exception as exc:
        current_app.logger.exception("Lỗi lưu đánh giá hệ thống: %s", exc)
        return jsonify({"success": False, "error": "Không thể xử lý yêu cầu lúc này."}), 500


@api_bp.route("/evaluations", methods=["GET"])
def get_evaluations():
    if session.get("role") != "advisor":
        return jsonify({"success": False, "error": "Advisor role required."}), 403

    """Lấy danh sách các đánh giá từ CVHT."""
    try:
        data = _load_json_file(EVALUATIONS_PATH, {"evaluations": []})
        records = data.get("evaluations", [])
        records.sort(key=lambda x: str(x.get("created_at", "")), reverse=True)
        return jsonify({
            "success": True,
            "data": records,
            "total": len(records),
        })
    except Exception as exc:
        current_app.logger.exception("Lỗi lấy danh sách đánh giá: %s", exc)
        return jsonify({"success": False, "error": "Không thể xử lý yêu cầu lúc này."}), 500


@api_bp.route("/risk-analysis/<student_id>", methods=["GET"])
def get_student_risk_analysis(student_id):
    """Trả về báo cáo phân tích rủi ro tiến độ đa chiều theo ontology CurriculumProgram."""
    try:
        service = current_app.student_data_service
        student = service.get_student(student_id)
        if not student:
            return jsonify({"success": False, "error": "Không tìm thấy sinh viên"}), 404

        analyzer = getattr(current_app, "progress_risk_analyzer", None)
        if not analyzer:
            from backend.app.services.progress_risk_analyzer import ProgressRiskAnalyzer
            analyzer = ProgressRiskAnalyzer(current_app.recommendation_engine)

        analysis = analyzer.assess_student(student.__dict__, current_app.recommendation_engine)
        return jsonify({"success": True, "data": analysis})
    except Exception as exc:
        current_app.logger.exception("Lỗi khi phân tích rủi ro tiến độ: %s", exc)
        return jsonify({"success": False, "error": "Không thể xử lý yêu cầu lúc này."}), 500
