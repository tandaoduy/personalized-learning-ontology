"""
Các route của luồng gợi ý kế hoạch học tập.
"""

from datetime import datetime
import json
from pathlib import Path
import time

from flask import Blueprint, current_app, jsonify, request, session

bp = Blueprint("recommendations", __name__, url_prefix="/api")

STUDENT_FEEDBACK_PATH = Path(__file__).resolve().parents[3] / "data" / "student_feedback.json"


def _load_student_feedback():
    if not STUDENT_FEEDBACK_PATH.exists():
        return {"feedback": []}
    try:
        with STUDENT_FEEDBACK_PATH.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return {"feedback": []}


def _save_student_feedback(data):
    STUDENT_FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with STUDENT_FEEDBACK_PATH.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


@bp.route("/recommendations", methods=["POST"])
@bp.route("/recommend", methods=["POST"])
def get_recommendation():
    """Sinh gợi ý kế hoạch học tập cho một sinh viên."""
    started_at = time.perf_counter()
    student_id = None

    try:
        role = session.get("role")
        if role not in {"student", "advisor"}:
            return jsonify({"success": False, "error": "Bạn cần đăng nhập trước khi tạo gợi ý."}), 401
        if current_app.recommendation_engine is None:
            return jsonify({
                "success": False,
                "error": "Bộ máy gợi ý chưa sẵn sàng. Vui lòng kiểm tra đường dẫn ontology.",
            }), 500

        data = request.get_json(silent=True) or {}
        student_id = str(data.get("student_id", "")).strip()

        if not student_id:
            return jsonify({
                "success": False,
                "error": "student_id không được để trống",
            }), 400
        if role == "student" and student_id != session.get("username"):
            return jsonify({"success": False, "error": "Bạn chỉ được tạo gợi ý cho hồ sơ của mình."}), 403

        current_app.logger.info(
            "Đã nhận yêu cầu gợi ý: endpoint=%s",
            request.path,
        )

        student_service = current_app.student_data_service
        student = student_service.get_student(student_id)

        if not student:
            return jsonify({
                "success": False,
                "error": f"Không tìm thấy sinh viên {student_id}",
            }), 404

        errors = student.validate()
        if errors:
            return jsonify({
                "success": False,
                "error": "Dữ liệu sinh viên không hợp lệ",
                "details": errors,
            }), 400

        scenario = str(data.get("scenario", "standard")).strip().lower()
        if scenario not in {"standard", "compare"}:
            scenario = "standard"
        is_compare = scenario == "compare" or bool(data.get("compare", False))
        num_plans = 3 if is_compare else 1
        
        import random
        
        plans = []
        engine = current_app.recommendation_engine
        explanation_generator = getattr(current_app, "explanation_generator", None)
        max_credits = current_app.config.get("REGISTER_MAX_CREDITS", 27)

        for i in range(num_plans):
            if i == 0:
                seed_offset = data.get("seed_offset")
                if seed_offset is None:
                    if data.get("randomize"):
                        seed_offset = random.randint(1, 1000000)
                    else:
                        seed_offset = 0
            else:
                seed_offset = random.randint(1, 1000000)

            result = engine.get_recommendation(
                student,
                seed_offset=seed_offset,
                priority_mode="standard",
            )
            result.generated_at = datetime.now().isoformat()
            result.processing_time_ms = round((time.perf_counter() - started_at) * 1000, 2)

            explanation_text = ""
            if explanation_generator is not None:
                explanation_text = explanation_generator.generate_recommendation_summary(
                    result,
                    max_credits=max_credits,
                )

            payload = result.to_dict()
            payload["explanation"] = explanation_text
            
            mandatory_count = sum(1 for c in result.recommended_courses if c.total_priority_score >= 10000)
            elective_count = sum(1 for c in result.recommended_courses if c.total_priority_score < 10000)
            total_priority_score = sum(c.total_priority_score for c in result.recommended_courses)
            
            # Use 1-indexed for names
            if i == 0:
                plan_name = "Tối ưu chuẩn" if not data.get("randomize") else "Ngẫu nhiên hóa"
            else:
                plan_name = f"Thay thế tự chọn {i}"

            payload["summary_metrics"] = {
                "plan_name": plan_name,
                "plan_index": i,
                "total_credits": result.total_recommended_credits,
                "mandatory_count": mandatory_count,
                "elective_count": elective_count,
                "total_priority_score": total_priority_score
            }
            plans.append(payload)

        current_app.logger.info(
            "Đã hoàn tất gợi ý: num_plans=%s duration_ms=%s",
            len(plans),
            round((time.perf_counter() - started_at) * 1000, 2)
        )

        response_data = {"plans": plans} if is_compare else plans[0]

        return jsonify({
            "success": True,
            "data": response_data,
        })

    except Exception as exc:
        current_app.logger.exception("Không thể xử lý gợi ý")
        return jsonify({"success": False, "error": "Không thể tạo gợi ý lúc này."}), 500

@bp.route("/student-feedback", methods=["POST"])
def save_student_feedback():
    """Persist a student's rating and optional comment for a generated plan."""
    if session.get("role") != "student":
        return jsonify({"success": False, "error": "Student role required."}), 403

    payload = request.get_json(silent=True) or {}
    try:
        rating = int(payload.get("rating", 0))
    except (TypeError, ValueError):
        rating = 0

    if not 1 <= rating <= 5:
        return jsonify({"success": False, "error": "Rating must be between 1 and 5."}), 400

    comment = str(payload.get("comment") or "").strip()
    if len(comment) > 2000:
        return jsonify({"success": False, "error": "Comment must not exceed 2,000 characters."}), 400

    data = _load_student_feedback()
    record = {
        "id": f"STUDENT_FB_{int(datetime.now().timestamp() * 1000)}",
        "student_id": session.get("username", ""),
        "student_name": session.get("display_name", ""),
        "rating": rating,
        "comment": comment,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    data.setdefault("feedback", []).append(record)
    _save_student_feedback(data)

    return jsonify({
        "success": True,
        "message": "Feedback saved.",
        "data": record,
    }), 201


@bp.route("/courses/<course_code>/prerequisite-chain", methods=["GET"])
def get_course_prerequisite_chain(course_code):
    """Lấy chuỗi tiên quyết và phân tích trạng thái môn học."""
    student_id = request.args.get("student_id", "").strip()

    try:
        engine = current_app.recommendation_engine
        if not engine:
            return jsonify({
                "success": False,
                "error": "Bộ máy gợi ý chưa sẵn sàng."
            }), 500

        if not student_id:
            return jsonify({
                "success": False,
                "error": "student_id là bắt buộc."
            }), 400
        if session.get("role") == "student" and student_id != session.get("username"):
            return jsonify({
                "success": False,
                "error": "Bạn chỉ được xem dữ liệu hồ sơ của mình."
            }), 403

        student_service = current_app.student_data_service
        student = student_service.get_student(student_id)
        if not student:
            return jsonify({
                "success": False,
                "error": f"Không tìm thấy sinh viên {student_id}"
            }), 404

        analysis_result = engine.analyze_prerequisite_path(course_code, student)
        
        # Build API response
        target_info = engine.course_data.get(course_code, {})
        
        # Generate some simple guidance based on critical course
        guidance = "Chuỗi môn tiên quyết đã hoàn thành hoặc không có."
        critical = analysis_result.get("critical_course")
        path = analysis_result.get("path", [])
        if critical:
            crit_name = engine.course_data.get(critical, {}).get("name", critical)
            
            critical_index = next((i for i, c in enumerate(path) if c["course_code"] == critical), -1)
            
            if critical_index != -1 and critical_index < len(path) - 1:
                guidance = f"Cần hoàn thành {critical} - {crit_name} trước để có thể mở khóa các môn học tiếp theo trong chuỗi."
            else:
                guidance = f"Cần hoàn thành {critical} - {crit_name}."

        response_data = {
            "target_course": {
                "course_code": course_code,
                "course_name": target_info.get("name", course_code)
            },
            "prerequisite_chain": analysis_result["path"],
            "critical_course": critical,
            "guidance": guidance
        }

        return jsonify({
            "success": True,
            "data": response_data
        })

    except Exception as exc:
        current_app.logger.exception("Lỗi khi lấy chuỗi tiên quyết")
        return jsonify({"success": False, "error": "Không thể phân tích chuỗi tiên quyết lúc này."}), 500
