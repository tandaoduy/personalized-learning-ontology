"""
Simple authentication routes for the demo role split.
"""

import json
import re
from datetime import datetime
from pathlib import Path

from flask import Blueprint, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

bp = Blueprint("auth", __name__, url_prefix="/api/auth")

ACCOUNTS_PATH = Path(__file__).resolve().parents[3] / "data" / "accounts.json"
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]{3,64}$")
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 256
MAX_DISPLAY_NAME_LENGTH = 120


def _load_accounts():
    if not ACCOUNTS_PATH.exists():
        return {"accounts": []}
    with ACCOUNTS_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def _save_accounts(data):
    ACCOUNTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with ACCOUNTS_PATH.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def _find_account(username):
    normalized_username = str(username or "").strip().lower()
    data = _load_accounts()
    for account in data.get("accounts", []):
        if str(account.get("username") or "").strip().lower() == normalized_username:
            return account, data
    return None, data


def _password_matches(account, password):
    password_hash = account.get("password_hash")
    if not password_hash:
        return False
    return check_password_hash(password_hash, password)


def _json_payload():
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else None


def _validate_credentials(username: str, password: str):
    if not USERNAME_PATTERN.fullmatch(username):
        return "Mã đăng nhập chỉ gồm chữ, số, dấu gạch dưới hoặc gạch ngang (3-64 ký tự)."
    if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        return f"Mật khẩu phải có từ {MIN_PASSWORD_LENGTH} đến {MAX_PASSWORD_LENGTH} ký tự."
    return None


@bp.route("/login", methods=["POST"])
def login():
    """Authenticate by checking the local JSON account store."""
    payload = _json_payload()
    if payload is None:
        return jsonify({"success": False, "error": "Dữ liệu JSON không hợp lệ."}), 400
    username = str(payload.get("username") or "").strip()
    password = str(payload.get("password") or "")

    if not USERNAME_PATTERN.fullmatch(username) or not password:
        return jsonify({"success": False, "error": "Mã đăng nhập hoặc mật khẩu không đúng."}), 401

    account, _ = _find_account(username)
    if not account or not _password_matches(account, password):
        return jsonify({
            "success": False,
            "error": "Mã đăng nhập hoặc mật khẩu không đúng.",
        }), 401

    if account.get("status") != "approved":
        return jsonify({
            "success": False,
            "error": "Tài khoản đang chờ xác nhận, chưa thể đăng nhập.",
        }), 403

    role = account.get("role")
    if role not in {"student", "advisor"}:
        return jsonify({
            "success": False,
            "error": "Tài khoản chưa được gán vai trò hợp lệ.",
        }), 403

    session.clear()
    session.permanent = True
    session["role"] = role
    session["username"] = username
    session["display_name"] = account.get("display_name") or username

    return jsonify({
        "success": True,
        "data": {
            "role": role,
            "username": username,
            "display_name": session["display_name"],
            "redirect_url": "/student?login=success" if role == "student" else "/advisor?login=success",
        },
    })


@bp.route("/register", methods=["POST"])
def register():
    """Create an approved demo account in the local JSON account store."""
    payload = _json_payload()
    if payload is None:
        return jsonify({"success": False, "error": "Dữ liệu JSON không hợp lệ."}), 400
    role = str(payload.get("role") or "").strip()
    username = str(payload.get("username") or "").strip()
    full_name = str(payload.get("full_name") or "").strip()
    password = str(payload.get("password") or "")

    credential_error = _validate_credentials(username, password)
    if role not in {"student", "advisor"} or credential_error:
        return jsonify({
            "success": False,
            "error": credential_error or "Vui lòng chọn vai trò và nhập đầy đủ thông tin đăng ký.",
        }), 400
    if len(full_name) > MAX_DISPLAY_NAME_LENGTH:
        return jsonify({"success": False, "error": "Họ và tên không được vượt quá 120 ký tự."}), 400

    existing_account, data = _find_account(username)
    if existing_account:
        return jsonify({
            "success": False,
            "error": "Mã đăng nhập này đã tồn tại. Vui lòng dùng mã khác hoặc đăng nhập.",
        }), 409

    role_label = "Sinh viên" if role == "student" else "Cố vấn học tập"
    display_name = full_name or f"{role_label} {username}"
    data.setdefault("accounts", []).append({
        "username": username,
        "password_hash": generate_password_hash(password),
        "role": role,
        "display_name": display_name,
        "full_name": full_name,
        "status": "approved",
        "created_at": datetime.now().isoformat(timespec="seconds"),
    })
    _save_accounts(data)

    session.clear()
    session.permanent = True
    session["role"] = role
    session["username"] = username
    session["display_name"] = display_name

    return jsonify({
        "success": True,
        "message": "Đăng ký tài khoản thành công.",
        "data": {
            "role": role,
            "username": username,
            "display_name": display_name,
            "redirect_url": "/student?login=success" if role == "student" else "/advisor?login=success",
        },
    })


@bp.route("/logout", methods=["POST"])
def logout():
    """Clear the current session."""
    session.clear()
    return jsonify({"success": True})


@bp.route("/refresh", methods=["POST"])
def refresh_session():
    """Extend the current session by touching it."""
    if "username" in session:
        session.modified = True
        return jsonify({"success": True, "message": "Session extended."})
    return jsonify({"success": False, "error": "No active session."}), 401


@bp.route("/profile", methods=["PUT"])
def update_profile():
    """Update the current account profile and optionally change password."""
    if "username" not in session:
        return jsonify({
            "success": False,
            "error": "Bạn cần đăng nhập trước khi cập nhật tài khoản.",
        }), 401

    payload = _json_payload()
    if payload is None:
        return jsonify({"success": False, "error": "Dữ liệu JSON không hợp lệ."}), 400
    display_name = str(payload.get("display_name") or "").strip()
    current_password = str(payload.get("current_password") or "")
    new_password = str(payload.get("new_password") or "")

    account, data = _find_account(session["username"])
    if not account:
        return jsonify({
            "success": False,
            "error": "Không tìm thấy tài khoản hiện tại.",
        }), 404

    if not display_name:
        return jsonify({
            "success": False,
            "error": "Họ và tên không được để trống.",
        }), 400
    if len(display_name) > MAX_DISPLAY_NAME_LENGTH:
        return jsonify({"success": False, "error": "Họ và tên không được vượt quá 120 ký tự."}), 400

    if new_password:
        if not current_password:
            return jsonify({
                "success": False,
                "error": "Vui lòng nhập mật khẩu hiện tại để đổi mật khẩu.",
            }), 400
        if not _password_matches(account, current_password):
            return jsonify({
                "success": False,
                "error": "Mật khẩu hiện tại không đúng.",
            }), 401
        if not MIN_PASSWORD_LENGTH <= len(new_password) <= MAX_PASSWORD_LENGTH:
            return jsonify({
                "success": False,
                "error": f"Mật khẩu mới phải có từ {MIN_PASSWORD_LENGTH} đến {MAX_PASSWORD_LENGTH} ký tự.",
            }), 400
        account["password_hash"] = generate_password_hash(new_password)

    account["display_name"] = display_name
    account["full_name"] = display_name
    account["updated_at"] = datetime.now().isoformat(timespec="seconds")
    _save_accounts(data)

    session["display_name"] = display_name

    if account.get("role") == "student":
        from flask import current_app
        student_service = getattr(current_app, "student_data_service", None)
        if student_service:
            try:
                student_service.update_student_name(account["username"], display_name)
            except Exception as e:
                current_app.logger.error("Lỗi đồng bộ tên sinh viên: %s", e)

    return jsonify({
        "success": True,
        "message": "Đã cập nhật hồ sơ cá nhân.",
        "data": {
            "username": account.get("username"),
            "display_name": display_name,
            "role": account.get("role"),
        },
    })


@bp.route("/me", methods=["GET"])
def me():
    """Return the current authenticated demo user."""
    if "role" not in session:
        return jsonify({"success": False, "authenticated": False}), 401

    return jsonify({
        "success": True,
        "authenticated": True,
        "data": {
            "role": session.get("role"),
            "username": session.get("username"),
            "display_name": session.get("display_name"),
        },
    })
