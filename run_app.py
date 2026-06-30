"""
Tập lệnh khởi động ứng dụng Flask.
"""

import logging
import os
import sys
from pathlib import Path


import io

# Fix UTF-8 output trên Windows terminal
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)

if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)


def setup_environment():
    """Chuẩn bị môi trường chạy trên Windows và UTF-8."""
    project_root = Path(__file__).parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


def main():
    """Khởi động ứng dụng Flask."""
    setup_environment()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    print("\n" + "=" * 70)
    print("Hệ thống gợi ý kế hoạch học tập")
    print("=" * 70)
    print("\nDựa trên Ontology và thuật toán Beam Search")
    print("Mục tiêu: hỗ trợ sinh viên lập kế hoạch học tập cá nhân hóa\n")

    print("Đang kiểm tra cấu hình...")
    try:
        from flask_app.config import Config
        print("  Đã nạp cấu hình")
        print(f"    - Ontology: {Config.ONTOLOGY_PATH}")
        print(f"    - Dữ liệu sinh viên: {Config.STUDENT_DATA_JSON}")

        from flask_app.services.student_data_service import StudentDataService
        service = StudentDataService(Config.STUDENT_DATA_JSON, Config.STUDENT_DATA_CSV)
        students = service.get_all_students()
        print(f"  Đã nạp dữ liệu sinh viên: {len(students)} sinh viên")
        print("  Kiểm tra trạng thái: http://localhost:5000/api/health")
        print("  Gỡ lỗi luồng: http://localhost:5000/api/debug/pipeline/SV0001\n")
    except Exception as exc:
        print(f"  Kiểm tra cấu hình thất bại: {exc}\n")
        print("Vui lòng chạy chẩn đoán trước khi khởi động máy chủ.")
        sys.exit(1)

    print("Đang khởi động ứng dụng Flask...")
    print("=" * 70)
    print("Địa chỉ ứng dụng: http://localhost:5000")
    print("Đầu mối API: http://localhost:5000/api")
    print("\nCác API chính:")
    print("  - GET /api/students")
    print("  - GET /api/students/<id>")
    print("  - POST /api/students")
    print("  - GET /api/students/courses")
    print("  - GET /api/students/specializations")
    print("  - GET /api/students/next-id")
    print("  - POST /api/recommendations")
    print("  - POST /api/recommend")
    print("  - GET /api/health")
    print("  - GET /api/debug/pipeline/<student_id>")
    print("\nNhấn Ctrl+C để dừng máy chủ")
    print("=" * 70 + "\n")

    try:
        from flask_app.app import app
        app.run(debug=True, port=5000, use_reloader=True)
    except KeyboardInterrupt:
        print("\nMáy chủ đã dừng")
    except Exception as exc:
        print(f"\nLỗi khi khởi động máy chủ: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
