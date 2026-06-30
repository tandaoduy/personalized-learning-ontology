"""
Các route quản lý dữ liệu sinh viên.
"""

from flask import Blueprint, current_app, jsonify, request

bp = Blueprint("students", __name__, url_prefix="/api/students")


@bp.route("", methods=["GET"])
def list_students():
    """Trả về danh sách rút gọn của tất cả sinh viên."""
    try:
        current_app.logger.info("Đã yêu cầu danh sách sinh viên")
        service = current_app.student_data_service
        students = service.get_all_students()

        result = [
            {
                "student_id": s.student_id,
                "name": s.name,
                "major": s.major,
                "specialization": s.specialization,
                "current_semester": s.current_semester,
            }
            for s in students
        ]

        current_app.logger.info("Đã trả về %s sinh viên", len(result))
        return jsonify({
            "success": True,
            "data": result,
            "total": len(result),
        })
    except Exception as exc:
        current_app.logger.exception("Không thể lấy danh sách sinh viên")
        return jsonify({
            "success": False,
            "error": str(exc),
        }), 500


@bp.route("/next-id", methods=["GET"])
def get_next_student_id():
    """Trả về mã sinh viên kế tiếp theo định dạng SV0001."""
    try:
        service = current_app.student_data_service
        next_id = service.get_next_student_id(force_reload=True)
        current_app.logger.info("Đã tạo mã sinh viên kế tiếp: %s", next_id)
        return jsonify({
            "success": True,
            "data": {
                "student_id": next_id,
            }
        })
    except Exception as exc:
        current_app.logger.exception("Không thể tạo mã sinh viên kế tiếp")
        return jsonify({
            "success": False,
            "error": str(exc),
        }), 500


@bp.route("", methods=["POST"])
def create_student():
    """Tạo sinh viên mới và lưu vào nguồn JSON."""
    try:
        payload = request.get_json(silent=True) or {}
        if not payload:
            return jsonify({
                "success": False,
                "error": "Không nhận được dữ liệu sinh viên",
            }), 400

        engine = current_app.recommendation_engine
        if engine is None:
            return jsonify({
                "success": False,
                "error": "Bộ máy gợi ý chưa sẵn sàng để tải dữ liệu",
            }), 500

        current_app.logger.info("Yêu cầu tạo sinh viên: %s", payload.get("student_id"))
        course_catalog = _get_course_catalog(engine)
        specialization_options = _get_specializations(engine)
        student = current_app.student_data_service.create_student(
            payload,
            course_catalog,
            specialization_options,
        )

        current_app.logger.info("Đã tạo sinh viên thành công: %s", student.student_id)
        return jsonify({
            "success": True,
            "message": f"Đã thêm sinh viên {student.student_id}",
            "data": student.to_dict(),
        }), 201
    except ValueError as exc:
        current_app.logger.warning("Xác thực tạo sinh viên thất bại: %s", exc)
        return jsonify({
            "success": False,
            "error": str(exc),
        }), 400
    except Exception as exc:
        current_app.logger.exception("Không thể tạo sinh viên")
        return jsonify({
            "success": False,
            "error": str(exc),
        }), 500


@bp.route("/courses", methods=["GET"])
def list_courses():
    """Trả về danh mục môn học trích xuất từ ontology."""
    try:
        engine = current_app.recommendation_engine
        if engine is None:
            return jsonify({
                "success": False,
                "error": "Bộ máy gợi ý chưa khởi tạo được",
            }), 500

        catalog = sorted(
            _get_course_catalog(engine).values(),
            key=lambda item: (item["code"], item["name"])
        )
        current_app.logger.info("Đã yêu cầu danh mục môn học: %s môn", len(catalog))

        return jsonify({
            "success": True,
            "data": catalog,
            "total": len(catalog),
        })
    except Exception as exc:
        current_app.logger.exception("Không thể lấy danh mục môn học")
        return jsonify({
            "success": False,
            "error": str(exc),
        }), 500


@bp.route("/majors", methods=["GET"])
def list_majors():
    """Trả về danh sách ngành học trích xuất từ ontology."""
    try:
        engine = current_app.recommendation_engine
        if engine is None:
            return jsonify({
                "success": False,
                "error": "Bộ máy gợi ý chưa khởi tạo được",
            }), 500

        options = sorted({
            name.strip()
            for name in engine.majors_map.values()
            if isinstance(name, str) and name.strip()
        })
        current_app.logger.info("Đã yêu cầu danh sách ngành học: %s lựa chọn", len(options))
        return jsonify({
            "success": True,
            "data": options,
            "total": len(options),
        })
    except Exception as exc:
        current_app.logger.exception("Không thể lấy danh sách ngành học")
        return jsonify({
            "success": False,
            "error": str(exc),
        }), 500


@bp.route("/specializations", methods=["GET"])
def list_specializations():
    """Trả về danh sách chuyên ngành trích xuất từ ontology."""
    try:
        engine = current_app.recommendation_engine
        if engine is None:
            return jsonify({
                "success": False,
                "error": "Bộ máy gợi ý chưa khởi tạo được",
            }), 500

        major = request.args.get("major", "").strip()
        if major:
            options = engine.major_specializations_map.get(major, [])
        else:
            options = _get_specializations(engine)

        current_app.logger.info("Đã yêu cầu danh sách chuyên ngành: %s lựa chọn", len(options))
        return jsonify({
            "success": True,
            "data": options,
            "total": len(options),
        })
    except Exception as exc:
        current_app.logger.exception("Không thể lấy danh sách chuyên ngành")
        return jsonify({
            "success": False,
            "error": str(exc),
        }), 500


@bp.route("/<student_id>", methods=["GET"])
def get_student(student_id: str):
    """Trả về hồ sơ của một sinh viên."""
    try:
        current_app.logger.info("Đã yêu cầu chi tiết sinh viên: %s", student_id)
        service = current_app.student_data_service
        student = service.get_student(student_id)

        if not student:
            return jsonify({
                "success": False,
                "error": f"Không tìm thấy sinh viên {student_id}",
            }), 404

        return jsonify({
            "success": True,
            "data": student.to_dict(),
        })
    except Exception as exc:
        current_app.logger.exception("Không thể lấy chi tiết sinh viên: %s", student_id)
        return jsonify({
            "success": False,
            "error": str(exc),
        }), 500


@bp.route("/<student_id>", methods=["DELETE"])
def delete_student(student_id: str):
    """Xóa hồ sơ của một sinh viên."""
    try:
        current_app.logger.info("Yêu cầu xóa sinh viên: %s", student_id)
        service = current_app.student_data_service
        student = service.get_student(student_id)

        if not student:
            return jsonify({
                "success": False,
                "error": f"Không tìm thấy sinh viên {student_id}",
            }), 404

        service.delete_student(student_id)
        return jsonify({
            "success": True,
            "message": f"Đã xóa sinh viên {student_id} thành công",
        })
    except Exception as exc:
        current_app.logger.exception("Không thể xóa sinh viên: %s", student_id)
        return jsonify({
            "success": False,
            "error": str(exc),
        }), 500


def _get_course_catalog(engine) -> dict:
    catalog = {}
    for code, info in engine.course_data.items():
        catalog[code] = {
            "code": code,
            "name": info.get("name", code),
            "credits": info.get("credit", 0),
        }
    return catalog


def _get_specializations(engine) -> list:
    return sorted({
        name.strip()
        for name in engine.specializations_map.values()
        if isinstance(name, str) and name.strip()
    })
