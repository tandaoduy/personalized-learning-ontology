"""
Ứng dụng Flask cho hệ thống gợi ý kế hoạch học tập.
"""

from datetime import datetime
import logging
import os
import sys
import time

from flask import Flask, abort, current_app, jsonify, redirect, render_template, request, session, url_for

# Thêm thư mục gốc vào `sys.path` để nhập các mô-đun nội bộ.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.config import Config
from backend.app.services.explanation_generator import ExplanationGenerator
from backend.app.services.progress_risk_analyzer import ProgressRiskAnalyzer
from backend.app.services.recommendation_engine import RecommendationEngine
from backend.app.services.student_data_service import StudentDataService


def create_app():
    """Nhà máy khởi tạo ứng dụng Flask."""
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )

    app.config.from_object(Config)
    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY phải được đặt khi chạy ngoài môi trường phát triển.")

    # Giữ phản hồi JSON dễ đọc trên demo và không tự sắp xếp khóa.
    try:
        app.json.ensure_ascii = False
        app.json.sort_keys = False
    except Exception:
        pass

    app.logger.setLevel(logging.INFO)

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        if request.path.startswith("/api/") and request.path != "/api/health":
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    # Khởi tạo các dịch vụ nền.
    app.student_data_service = StudentDataService(
        json_path=Config.STUDENT_DATA_JSON,
        csv_path=Config.STUDENT_DATA_CSV,
    )

    # Khởi tạo bộ máy gợi ý, nạp ontology theo kiểu lười nếu cần.
    try:
        app.recommendation_engine = RecommendationEngine(
            ontology_path=Config.ONTOLOGY_PATH,
            beam_width=Config.BEAM_WIDTH,
            max_credits=Config.REGISTER_MAX_CREDITS,
            min_credits=Config.REGISTER_MIN_CREDITS,
            heuristic_weights={
                "debt": Config.WEIGHT_DEBT,
                "link": Config.WEIGHT_LINK,
                "delay": Config.WEIGHT_DELAY,
            },
            elective_quotas=Config.ELECTIVE_QUOTAS,
        )
    except Exception as exc:
        print(f"Cảnh báo: lỗi khi khởi tạo RecommendationEngine: {exc}")
        print("Bộ máy sẽ được khởi tạo ở lần yêu cầu đầu tiên.")
        app.recommendation_engine = None

    app.explanation_generator = ExplanationGenerator()
    app.progress_risk_analyzer = ProgressRiskAnalyzer(app.recommendation_engine)

    # Đăng ký các blueprint cho API.
    from backend.app.routes import (
        advisor_role_routes,
        auth_routes,
        recommendation_routes,
        student_role_routes,
        student_routes,
    )

    app.register_blueprint(auth_routes.bp)
    app.register_blueprint(student_routes.bp)
    app.register_blueprint(recommendation_routes.bp)
    app.register_blueprint(student_role_routes.bp)
    app.register_blueprint(advisor_role_routes.bp)
    app.register_blueprint(advisor_role_routes.api_bp)

    @app.before_request
    def enforce_role_access():
        """Chặn truy cập trực tiếp vào khu vực theo vai trò."""
        path = request.path.rstrip("/") or "/"
        role = session.get("role")

        if path == "/students" or path.startswith("/students/"):
            if role not in {"student", "advisor"}:
                return redirect(url_for("index"))

        if (path == "/student" or path.startswith("/student/")) and role != "student":
            return redirect(url_for("index"))

        if (path == "/advisor" or path.startswith("/advisor/")) and role != "advisor":
            return redirect(url_for("index"))

        if not path.startswith("/api/"):
            return None
        if path.startswith("/api/auth/") or path == "/api/health":
            return None
        if role not in {"student", "advisor"}:
            return jsonify({"success": False, "error": "Bạn cần đăng nhập để truy cập tài nguyên này."}), 401
        if path.startswith("/api/advisor/") and role != "advisor":
            return jsonify({"success": False, "error": "Chỉ cố vấn học tập được phép truy cập."}), 403
        if path.startswith("/api/students") and role == "student":
            own_student_path = f"/api/students/{session.get('username', '')}"
            catalog_paths = {
                "/api/students/courses",
                "/api/students/majors",
                "/api/students/specializations",
                "/api/students/cohorts",
            }
            if not (
                (path == own_student_path and request.method in {"GET", "PUT"})
                or (path in catalog_paths and request.method == "GET")
            ):
                return jsonify({"success": False, "error": "Bạn không có quyền truy cập dữ liệu sinh viên này."}), 403
        return None

    # Đăng ký các route giao diện sau khi đã đăng ký blueprint.
    @app.route("/")
    def index():
        """Trang chủ."""
        if session.get("role") == "student":
            return redirect(url_for("student_role.dashboard"))
        if session.get("role") == "advisor":
            return redirect(url_for("advisor_role.dashboard"))
        return render_template("index.html")

    @app.route("/register")
    def register_page():
        """Trang đăng ký tài khoản."""
        return render_template("register.html")

    @app.route("/account")
    def account_page():
        """Trang ho so tai khoan va doi mat khau."""
        if not session.get("role"):
            return redirect(url_for("index"))
        return render_template("account.html")

    @app.route("/components")
    def components_page():
        """Trang kiểm thử các UI components dùng chung."""
        if not app.debug:
            abort(404)
        return render_template("components.html")

    @app.route("/components/<component_name>")
    def component_detail_page(component_name):
        """Trang kiểm thử từng UI component."""
        if not app.debug:
            abort(404)
        allowed_components = {
            "alert",
            "avatar",
            "badge",
            "button",
            "card",
            "dropdown",
            "form-layout",
            "modal-dialog",
            "navbar",
            "radio-group",
            "sidebar",
            "table",
            "tabs",
            "toggle",
            "sign-in-registration",
        }
        if component_name not in allowed_components:
            return render_template("components.html", missing_component=component_name), 404
        return render_template("components/detail.html", component_name=component_name)

    @app.route("/students")
    def students_page():
        """Trang sinh viên với giao diện gợi ý."""
        current_app.logger.info("Đã truy cập route /students")
        return render_template("students.html")

    @app.route("/students/new")
    def create_student_page():
        """Trang thêm sinh viên mới."""
        return render_template("add_student.html")

    @app.route("/students/<student_id>/edit")
    def edit_student_page(student_id):
        """Trang chỉnh sửa sinh viên."""
        return render_template("add_student.html", edit_student_id=student_id)

    @app.route("/students/<student_id>/course-history")
    def student_course_history_page(student_id):
        """Trang chi tiết lịch sử môn học của sinh viên."""
        student = app.student_data_service.get_student(student_id)
        if not student:
            return render_template(
                "student_course_history.html",
                student=None,
                error=f"Không tìm thấy sinh viên {student_id}",
                passed_rows=[],
                failed_rows=[],
            ), 404

        engine = getattr(app, "recommendation_engine", None)
        course_data = getattr(engine, "course_data", {}) if engine is not None else {}

        # Ưu tiên dùng course_attempts để hiển thị đầy đủ lịch sử (học lại, cải thiện điểm)
        if student.course_attempts:
            all_rows = []
            for attempt in student.course_attempts:
                info = course_data.get(attempt.course_code, {}) if isinstance(course_data, dict) else {}
                all_rows.append({
                    "code": attempt.course_code,
                    "name": info.get("name") or attempt.course_name or attempt.course_code,
                    "credits": info.get("credit") if info else None,
                    "grade": attempt.grade,
                    "status": attempt.status,
                    "grade_specified": attempt.grade_specified,
                    "semester_taken": attempt.semester_taken if attempt.semester_taken else None,
                    "attempt_number": attempt.attempt_number,
                })
            all_rows.sort(key=lambda x: (x["code"], x["attempt_number"]))
            passed_rows = [r for r in all_rows if r["status"] in ("Đạt", "Miễn", "Không tính điểm")]
            failed_rows = [r for r in all_rows if r["status"] not in ("Đạt", "Miễn", "Không tính điểm")]
        else:
            # Tương thích ngược với dữ liệu cũ chưa có course_attempts
            def build_rows(codes, default_status_label):
                rows = []
                for code in codes:
                    info = course_data.get(code, {}) if isinstance(course_data, dict) else {}
                    status_label = getattr(student, "course_statuses", {}).get(code) or default_status_label
                    specified = getattr(student, "course_grade_specified", {}).get(code, True)
                    rows.append({
                        "code": code,
                        "name": info.get("name") or code,
                        "credits": info.get("credit") if info else None,
                        "grade": student.course_grades.get(code) if student.course_grades else None,
                        "status": status_label,
                        "grade_specified": specified,
                        "semester_taken": None,
                        "attempt_number": 1,
                    })
                return rows
            passed_rows = build_rows(student.passed_courses or [], "Đạt")
            failed_rows = build_rows(student.failed_courses or [], "Chưa đạt")
            all_rows = (passed_rows or []) + (failed_rows or [])

        # Sắp xếp theo mã môn, rồi theo lần học
        all_rows.sort(key=lambda x: (x["code"], x.get("attempt_number", 1)))
        total_rows = len(all_rows)

        allowed_page_sizes = (10, 20, 50, 100)
        per_page_value = str(request.args.get("per_page", "10")).strip().lower()
        if per_page_value == "all":
            page_size = max(total_rows, 1)
        else:
            try:
                page_size = int(per_page_value)
            except (TypeError, ValueError):
                page_size = 10
            if page_size not in allowed_page_sizes:
                page_size = 10

        page = request.args.get("page", 1, type=int) or 1
        if page < 1:
            page = 1

        total_pages = max(1, (total_rows + page_size - 1) // page_size)
        if page > total_pages:
            page = total_pages

        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        paged_rows = all_rows[start_index:end_index]

        display_from = 0 if total_rows == 0 else (start_index + 1)
        display_to = min(start_index + len(paged_rows), total_rows)

        # Tạo danh sách số trang gọn, chèn dấu ba chấm bằng `None`.
        page_numbers = []
        if total_pages <= 7:
            page_numbers = list(range(1, total_pages + 1))
        else:
            candidates = {1, total_pages, page, page - 1, page + 1}
            candidates = sorted([p for p in candidates if 1 <= p <= total_pages])
            last = None
            for p in candidates:
                if last is not None and p - last > 1:
                    page_numbers.append(None)  # dấu ba chấm
                page_numbers.append(p)
                last = p

        return render_template(
            "student_course_history.html",
            student=student,
            error=None,
            passed_rows=passed_rows,
            failed_rows=failed_rows,
            paged_rows=paged_rows,
            page=page,
            page_size=page_size,
            per_page_value=per_page_value,
            total_rows=total_rows,
            total_pages=total_pages,
            start_index=start_index,
            display_from=display_from,
            display_to=display_to,
            page_numbers=page_numbers,
            base_url=f"/students/{student.student_id}/course-history",
        )

    @app.route("/api/health")
    def health_check():
        """Endpoint kiểm tra nhanh trạng thái hệ thống."""
        engine = getattr(app, "recommendation_engine", None)
        student_service = getattr(app, "student_data_service", None)
        student_count = 0
        if student_service is not None:
            try:
                student_count = len(student_service.get_all_students())
            except Exception as exc:
                app.logger.warning("Không thể nạp danh sách sinh viên khi kiểm tra trạng thái: %s", exc)

        return jsonify({
            "success": True,
            "data": {
                "status": "ok",
                "student_service_ready": student_service is not None,
                "recommendation_engine_ready": engine is not None,
                "ontology_loaded": bool(engine and getattr(engine, "course_data", None)),
                "course_count": len(getattr(engine, "course_data", {}) or {}),
                "specialization_count": len(getattr(engine, "specializations_map", {}) or {}),
                "student_count": student_count,
            }
        })

    @app.route("/api/debug/pipeline/<student_id>")
    def debug_pipeline(student_id):
        """Endpoint gỡ lỗi đầu-cuối để chứng minh luồng chạy thật."""
        if not app.debug:
            abort(404)
        if session.get("role") != "advisor":
            return jsonify({"success": False, "error": "Chỉ cố vấn học tập được phép truy cập."}), 403
        started_at = time.perf_counter()
        engine = getattr(app, "recommendation_engine", None)
        student = app.student_data_service.get_student(student_id)

        if student is None:
            return jsonify({
                "success": False,
                "error": f"Không tìm thấy sinh viên {student_id}",
            }), 404

        if engine is None:
            return jsonify({
                "success": False,
                "error": "Bộ máy gợi ý chưa sẵn sàng",
            }), 500

        result = engine.get_recommendation(student)
        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
        result.processing_time_ms = elapsed_ms

        return jsonify({
            "success": True,
            "data": {
                "student": student.to_dict(),
                "course_count": len(getattr(engine, "course_data", {}) or {}),
                "eligible_count": result.total_eligible_count,
                "recommended_count": result.total_recommended_count,
                "total_recommended_credits": result.total_recommended_credits,
                "processing_time_ms": elapsed_ms,
                "result": result.to_dict(),
            }
        })

    return app


# Tạo ứng dụng Flask.
app = create_app()


@app.errorhandler(404)
def not_found_error(error):
    return jsonify({"success": False, "error": "Không tìm thấy tài nguyên"}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({"success": False, "error": "Lỗi máy chủ nội bộ"}), 500


if __name__ == "__main__":
    app.run(
        debug=app.config["DEBUG"],
        port=5000,
        use_reloader=app.config["DEBUG"],
    )
