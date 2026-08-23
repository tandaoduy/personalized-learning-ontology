"""
Các route quản lý dữ liệu sinh viên.
"""

from flask import Blueprint, current_app, jsonify, request, session

import os
from threading import Lock

bp = Blueprint("students", __name__, url_prefix="/api/students")

_student_list_cache = {"source": None, "data": None}
_student_list_cache_lock = Lock()


def _student_data_signature(service) -> tuple[str, float]:
    try:
        path = os.path.abspath(service.json_path)
        return path, os.path.getmtime(path)
    except (AttributeError, OSError, TypeError):
        return "", 0.0


@bp.route("", methods=["GET"])
def list_students():
    """Trả về danh sách rút gọn của tất cả sinh viên."""
    try:
        current_app.logger.info("Đã yêu cầu danh sách sinh viên")
        service = current_app.student_data_service
        data_signature = _student_data_signature(service)
        with _student_list_cache_lock:
            if (_student_list_cache["data"] is not None
                    and _student_list_cache["source"] == data_signature):
                cached_result = _student_list_cache["data"]
                return jsonify({
                    "success": True,
                    "data": cached_result,
                    "total": len(cached_result),
                    "cached": True,
                })

        students = service.get_all_students()

        result = [
            {
                "student_id": s.student_id,
                "name": s.name,
                "major": s.major,
                "specialization": s.specialization,
                "current_semester": s.current_semester,
                "academic_class": s.academic_class,
                "gpa_accumulated": getattr(s, "gpa_accumulated", 0.0),
                "total_credits_accumulated": getattr(s, "total_credits_accumulated", 0),
                "year_admitted": getattr(s, "year_admitted", 2023),
                "passed_courses_count": len(getattr(s, "passed_courses", []) or []),
                "failed_courses_count": len(getattr(s, "failed_courses", []) or []),
                "study_goal": getattr(s, "study_goal", "Đúng tiến độ"),
            }
            for s in students
        ]

        current_app.logger.info("Đã trả về %s sinh viên", len(result))
        analyzer = getattr(current_app, "progress_risk_analyzer", None)
        if analyzer:
            for student, item in zip(students, result):
                try:
                    analysis = analyzer.assess_student(student, current_app.recommendation_engine)
                    item.update({
                        "progress_status": analysis.get("progress_status", "UNKNOWN"),
                        "risk_level": analysis.get("risk_level", "UNKNOWN"),
                        "progress_message": analysis.get("message", ""),
                    })
                except Exception as exc:
                    current_app.logger.warning("Progress analysis failed")

        with _student_list_cache_lock:
            _student_list_cache["source"] = data_signature
            _student_list_cache["data"] = result

        return jsonify({
            "success": True,
            "data": result,
            "total": len(result),
            "cached": False,
        })
    except Exception as exc:
        current_app.logger.exception("Không thể lấy danh sách sinh viên")
        return jsonify({
            "success": False,
            "error": "Không thể xử lý yêu cầu lúc này.",
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
            "error": "Không thể xử lý yêu cầu lúc này.",
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

        current_app.logger.info("Yêu cầu tạo sinh viên")
        course_catalog = _get_course_catalog(engine)
        specialization_options = _get_specializations(engine)
        student = current_app.student_data_service.create_student(
            payload,
            course_catalog,
            specialization_options,
        )

        current_app.logger.info("Đã tạo sinh viên thành công")
        return jsonify({
            "success": True,
            "message": f"Đã thêm sinh viên {student.student_id}",
            "data": student.to_dict(),
        }), 201
    except ValueError as exc:
        current_app.logger.warning("Xác thực tạo sinh viên thất bại: %s", exc)
        return jsonify({
            "success": False,
            "error": "Không thể xử lý yêu cầu lúc này.",
        }), 400
    except Exception as exc:
        current_app.logger.exception("Không thể tạo sinh viên")
        return jsonify({
            "success": False,
            "error": "Không thể xử lý yêu cầu lúc này.",
        }), 500


@bp.route("/<student_id>", methods=["PUT"])
def update_student(student_id: str):
    """Cập nhật thông tin sinh viên và lưu vào nguồn JSON."""
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

        current_app.logger.info("Yêu cầu cập nhật sinh viên")
        course_catalog = _get_course_catalog(engine)
        specialization_options = _get_specializations(engine)
        student = current_app.student_data_service.update_student(
            student_id,
            payload,
            course_catalog,
            specialization_options,
        )

        current_app.logger.info("Đã cập nhật sinh viên thành công")
        return jsonify({
            "success": True,
            "message": f"Đã cập nhật sinh viên {student.student_id}",
            "data": student.to_dict(),
        }), 200
    except ValueError as exc:
        current_app.logger.warning("Xác thực cập nhật sinh viên thất bại: %s", exc)
        return jsonify({
            "success": False,
            "error": "Không thể xử lý yêu cầu lúc này.",
        }), 400
    except Exception as exc:
        current_app.logger.exception("Không thể cập nhật sinh viên")
        return jsonify({
            "success": False,
            "error": "Không thể xử lý yêu cầu lúc này.",
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
            "error": "Không thể xử lý yêu cầu lúc này.",
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
            "error": "Không thể xử lý yêu cầu lúc này.",
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
            try:
                # Try latin-1 first as the WSGI server decodes 0x87 to U+0087
                major = major.encode('latin-1').decode('utf-8')
            except (UnicodeEncodeError, UnicodeDecodeError):
                try:
                    major = major.encode('cp1252').decode('utf-8')
                except (UnicodeEncodeError, UnicodeDecodeError):
                    pass
            
            import unicodedata
            major_nfc = unicodedata.normalize("NFC", major).strip().lower()
            options = []
            for m_name, specs in engine.major_specializations_map.items():
                m_name_nfc = unicodedata.normalize("NFC", m_name).strip().lower()
                if m_name_nfc == major_nfc:
                    options = specs
                    break
        else:
            options = _get_specializations(engine)

        current_app.logger.info("Đã yêu cầu danh sách chuyên ngành: %s lựa chọn", len(options))
        resp = jsonify({
            "success": True,
            "data": options,
            "total": len(options),
        })
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp
    except Exception as exc:
        current_app.logger.exception("Không thể lấy danh sách chuyên ngành")
        return jsonify({
            "success": False,
            "error": "Không thể xử lý yêu cầu lúc này.",
        }), 500


@bp.route("/academic-classes", methods=["GET"])
def list_academic_classes():
    """Trả về danh sách lớp hành chính đang có trong dữ liệu sinh viên."""
    try:
        service = getattr(current_app, "student_data_service", None)
        if service is None:
            raise RuntimeError("Dữ liệu sinh viên chưa sẵn sàng")

        # Chỉ lấy các lớp đã tồn tại trong nguồn dữ liệu sinh viên, không thêm lớp
        # mẫu từ ontology.
        options_set = {
            s.academic_class.strip()
            for s in service.get_all_students()
            if s.academic_class
            and s.academic_class.strip()
            and s.academic_class.strip() != "Chưa xếp lớp"
        }

        options = sorted(list(options_set))
        current_app.logger.info("Đã yêu cầu danh sách lớp hành chính: %s lựa chọn", len(options))
        return jsonify({
            "success": True,
            "data": options,
            "total": len(options),
        })
    except Exception as exc:
        current_app.logger.exception("Không thể lấy danh sách lớp hành chính")
        return jsonify({
            "success": False,
            "error": "Không thể xử lý yêu cầu lúc này.",
        }), 500


@bp.route("/cohorts", methods=["GET"])
def list_cohorts():
    """Tra ve danh sach khoa trich xuat tu ontology va lop hanh chinh thuc te."""
    try:
        engine = current_app.recommendation_engine
        if engine is None:
            return jsonify({
                "success": False,
                "error": "Bộ máy gợi ý chưa khởi tạo được",
            }), 500

        options = []
        for cohort in getattr(engine, "cohorts", []):
            if cohort.get("code") in {"K65", "K66", "K67"}:
                c_copy = dict(cohort)
                c_classes = set(c_copy.get("academic_classes") or [])
                service = getattr(current_app, "student_data_service", None)
                if service:
                    try:
                        for s in service.get_all_students():
                            if getattr(s, "year_admitted", None) == c_copy.get("year_admitted"):
                                if s.academic_class and s.academic_class.strip() and s.academic_class != "Chưa xếp lớp":
                                    c_classes.add(s.academic_class.strip())
                    except Exception:
                        pass
                c_copy["academic_classes"] = sorted(list(c_classes))
                options.append(c_copy)
        return jsonify({
            "success": True,
            "data": options,
            "total": len(options),
        })
    except Exception as exc:
        current_app.logger.exception("KhÃ´ng thá»ƒ láº¥y danh sÃ¡ch khÃ³a")
        return jsonify({
            "success": False,
            "error": "Không thể xử lý yêu cầu lúc này.",
        }), 500


@bp.route("/<student_id>", methods=["GET"])
def get_student(student_id: str):
    """Trả về hồ sơ của một sinh viên."""
    try:
        current_app.logger.info("Đã yêu cầu chi tiết sinh viên")
        service = current_app.student_data_service
        student = service.get_student(student_id)

        if not student:
            return jsonify({
                "success": False,
                "error": f"Không tìm thấy sinh viên {student_id}",
            }), 404

        data_dict = student.to_dict()
        # actual_term is only the term number inside an academic year (1--3).
        # Preserve a recorded academic year; derive a value only for legacy data.
        for attempt in data_dict.get("course_attempts", []):
            if str(attempt.get("academic_year") or "").strip():
                continue
            semester_taken = attempt.get("semester_taken")
            try:
                semester_taken = int(semester_taken)
            except (TypeError, ValueError):
                continue
            if semester_taken > 0:
                start_year = student.year_admitted + (semester_taken - 1) // 3
                attempt["academic_year"] = f"{start_year}-{start_year + 1}"
        analyzer = getattr(current_app, "progress_risk_analyzer", None)
        if not analyzer:
            from flask_app.services.progress_risk_analyzer import ProgressRiskAnalyzer
            analyzer = ProgressRiskAnalyzer(current_app.recommendation_engine)
        if analyzer:
            try:
                data_dict["progress_analysis"] = analyzer.assess_student(student.__dict__, current_app.recommendation_engine)
            except Exception as e:
                current_app.logger.warning("Không thể phân tích rủi ro tiến độ")

        return jsonify({
            "success": True,
            "data": data_dict,
        })
    except Exception as exc:
        current_app.logger.exception("Không thể lấy chi tiết sinh viên")
        return jsonify({
            "success": False,
            "error": "Không thể xử lý yêu cầu lúc này.",
        }), 500


@bp.route("/<student_id>", methods=["DELETE"])
def delete_student(student_id: str):
    """Delete a student profile; this action is restricted to advisors."""
    if session.get("role") != "advisor":
        return jsonify({
            "success": False,
            "error": "Only advisors may delete student profiles.",
        }), 403

    """Xóa hồ sơ của một sinh viên."""
    try:
        current_app.logger.info("Yêu cầu xóa sinh viên")
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
        current_app.logger.exception("Không thể xóa sinh viên")
        return jsonify({
            "success": False,
            "error": "Không thể xử lý yêu cầu lúc này.",
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
