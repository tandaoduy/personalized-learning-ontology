"""Ẩn danh dữ liệu demo trước khi đưa dự án lên kho công khai.

Chỉ thay thế các định danh cá nhân; toàn bộ dữ liệu học tập được giữ nguyên.
Chạy từ thư mục gốc dự án: python scripts/anonymize_demo_data.py
"""

from __future__ import annotations

import json
from pathlib import Path

from werkzeug.security import generate_password_hash


DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def load_json(filename: str):
    with (DATA_DIR / filename).open(encoding="utf-8") as stream:
        return json.load(stream)


def save_json(filename: str, data: object) -> None:
    with (DATA_DIR / filename).open("w", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main() -> None:
    students = load_json("DanhSachSinhVien.json")
    if not isinstance(students, list):
        raise ValueError("DanhSachSinhVien.json phải là một mảng JSON.")

    # References elsewhere use the original identifier, so keep the first mapping
    # for an ID that happened to occur more than once in the source dataset.
    id_map: dict[str, str] = {}
    for number, student in enumerate(students, start=1):
        original_id = str(student.get("student_id", ""))
        anonymized_id = f"SV{number:03d}"
        id_map.setdefault(original_id, anonymized_id)
        student["student_id"] = anonymized_id
        student["name"] = f"Sinh viên {number:02d}"
        for key in (
            "date_of_birth", "birth_date", "place_of_birth", "phone", "phone_number",
            "email", "address", "citizen_id", "identity_number",
        ):
            student.pop(key, None)

    accounts_data = load_json("accounts.json")
    accounts = accounts_data.get("accounts", [])
    student_account_number = 0
    for account in accounts:
        if account.get("role") == "student":
            student_account_number += 1
            original_username = str(account.get("username", ""))
            username = id_map.get(original_username, f"SV{student_account_number:03d}")
            label = username.removeprefix("SV").lstrip("0") or "0"
            account["username"] = username
            account["display_name"] = f"Sinh viên {int(label):02d}"
            account["full_name"] = account["display_name"]
        else:
            account["username"] = "CV001"
            account["display_name"] = "Cố vấn 01"
            account["full_name"] = account["display_name"]
        account["password_hash"] = generate_password_hash("123456789")
        for key in ("email", "phone", "phone_number", "address"):
            account.pop(key, None)
        account.pop("created_at", None)

    advisor_username = next(
        (account["username"] for account in accounts if account.get("role") != "student"),
        "CV001",
    )
    consultations_data = load_json("consultations.json")
    for number, consultation in enumerate(consultations_data.get("consultations", []), start=1):
        consultation["id"] = f"CONS_DEMO_{number:03d}"
        anonymized_id = id_map.get(str(consultation.get("student_id", "")), "SV001")
        consultation["student_id"] = anonymized_id
        consultation["student_name"] = f"Sinh viên {int(anonymized_id[2:]):02d}"
        consultation["advisor_username"] = advisor_username
        consultation["advisor_name"] = "Cố vấn 01"
        consultation["notes"] = "Ghi chú tư vấn mẫu."
        consultation.pop("created_at", None)

    evaluations_data = load_json("evaluations.json")
    for number, evaluation in enumerate(evaluations_data.get("evaluations", []), start=1):
        evaluation["id"] = f"EVAL_DEMO_{number:03d}"
        evaluation["advisor_username"] = advisor_username
        evaluation["advisor_name"] = "Cố vấn 01"
        evaluation.pop("created_at", None)

    save_json("DanhSachSinhVien.json", students)
    save_json("accounts.json", accounts_data)
    save_json("consultations.json", consultations_data)
    save_json("evaluations.json", evaluations_data)
    print(f"Anonymized {len(students)} student records.")


if __name__ == "__main__":
    main()
