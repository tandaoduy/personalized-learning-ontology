# Hệ thống cố vấn học tập dựa trên Ontology

Hệ thống web Flask hỗ trợ sinh viên và cố vấn học tập theo dõi kết quả, phân tích tiến độ và tạo kế hoạch học phần dựa trên chương trình đào tạo trong ontology RDF.

## Tính năng

- Quản lý hồ sơ, lịch sử học phần và các lần học lại.
- Tính GPA, tín chỉ đạt và trạng thái học phần.
- Kiểm tra tiên quyết, song hành, học kỳ mở, ngành/chuyên ngành.
- Sinh kế hoạch bằng Beam Search, giới hạn tín chỉ và quota môn tự chọn.
- Phân tích nguy cơ `LOW`, `MEDIUM`, `HIGH`.
- Giao diện và API cho sinh viên/cố vấn học tập.

## Công nghệ

- Python 3.10+, Flask 3, RDFLib 7.
- Node.js 18+, npm, Tailwind CSS, DaisyUI, Alpine.js, HTMX, Chart.js.
- Ontology chính thức v23: `knowledge/ontology/ontology_v23.rdf` (RDF/XML); bản OWL nguồn là `knowledge/ontology/TrainingProgramOntology_v23.owl`.
- Dữ liệu demo: `data/`.

## Cài đặt

Repository đã kèm `README.md`, `requirements.txt`, `package.json` và `package-lock.json`; dùng lockfile để tái lập dependencies frontend.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
npm install
npm run build:ui
```

`npm run build:ui` biên dịch CSS và sao chép vendor vào `backend/app/static/vendor/`.

Lệnh trên cũng cài `rdflib` (cho các truy vấn SPARQL) và `pypdf` (cho script migration). Các script không tự cài thư viện khi chạy.

## Chạy ứng dụng

```powershell
python run_app.py
```

Mở <http://localhost:5000>. Kiểm tra nhanh bằng `GET /api/health` hoặc chẩn đoán pipeline bằng `GET /api/debug/pipeline/<student_id>`.

Mặc định ứng dụng chạy ở môi trường phát triển. Khi demo/chạy chính thức, đặt `APP_ENV=production` và một `SECRET_KEY` ngẫu nhiên; các trang `/components/*` và endpoint debug sẽ trả về 404. Ví dụ PowerShell:

```powershell
$env:APP_ENV = "production"
$env:SECRET_KEY = "thay-bang-chuoi-ngau-nhien-dai-va-bao-mat"
python run_app.py
```

## Kiểm thử

```powershell
python -m pip install -r requirements-dev.txt
python experiments/run_benchmark.py
```

Lệnh trên sẽ chạy toàn bộ các bài kiểm thử tự động thông qua `pytest` (bao gồm unit test và integration test giao diện/API) và tự động sinh ra một file báo cáo Markdown tại `benchmark_results/test_report.md` thể hiện rõ môi trường chạy, phiên bản Python, số ca đạt/không đạt và các ánh xạ tới yêu cầu nghiệp vụ.

Lệnh `experiments/run_benchmark.py` chạy toàn bộ pytest (unit, API integration và UI integration), đồng thời tạo `benchmark_results/test_report.md`. Có thể chạy pytest trực tiếp bằng `python -m pytest` hoặc tạo báo cáo coverage bằng `python -m pytest --cov=backend.app.services --cov-report=term-missing`.

## Bảo mật và dữ liệu mẫu

- Mật khẩu được băm bằng `werkzeug.security.generate_password_hash`; repository không lưu mật khẩu rõ.
- Cookie phiên có `HttpOnly`, `SameSite=Lax`, thời hạn 60 phút và chỉ bật `Secure` khi không chạy development.
- API yêu cầu đăng nhập; sinh viên chỉ truy cập/cập nhật hồ sơ và gợi ý của chính mình, còn thao tác quản trị dành cho cố vấn.
- Lỗi nội bộ được ghi log phía máy chủ nhưng API không trả chi tiết exception cho các luồng gợi ý.

Các trang `/components/*` và endpoint `/api/debug/pipeline/<student_id>` chỉ dành cho development; production trả về 404.

## Benchmark có thể tái lập

Kết quả mẫu nằm trong `benchmark_results/`. Tái tạo bằng dữ liệu mẫu, ontology v23 và seed cố định:

```powershell
python experiments/benchmark_algorithms.py --limit 0 --output benchmark_results/benchmark_results_all.csv
```

Lệnh trên tạo file chi tiết và file `_summary.csv` tương ứng.

## Migration dữ liệu sinh viên

Script migration dùng đường dẫn tương đối theo thư mục dự án mặc định, nên có thể chạy trên máy khác:

```powershell
python scripts/migrate_student_data.py
```

Có thể chỉ định rõ các file nếu dữ liệu nằm ở vị trí khác:

```powershell
python scripts/migrate_student_data.py --input-json path/to/students.json --output-json path/to/students-v2.json --pdf path/to/transcript-1.pdf --pdf path/to/transcript-2.pdf
```

Để chạy script truy vấn SPARQL, hãy cài dependencies trước rồi chạy `python backend/tests/test_sparql.py`.

## Cấu hình

Xem [`backend/app/config.py`](backend/app/config.py):

- `ONTOLOGY_PATH`, `STUDENT_DATA_JSON`, `STUDENT_DATA_CSV`.
- `REGISTER_MIN_CREDITS`, `REGISTER_MAX_CREDITS`.
- `ELECTIVE_QUOTAS`.
- `SECRET_KEY` (production phải đặt qua biến môi trường).

Không commit mật khẩu hoặc dữ liệu sinh viên thật. Dữ liệu trong `data/` chỉ dành cho demo/phát triển.

## Đường dẫn chính

- Sinh viên: `/student`, `/student/history`, `/student/profile`, `/student/plan`.
- Cố vấn: `/advisor/students`, `/advisor/at-risk`, `/advisor/student-editor`, `/advisor/scenarios`, `/advisor/consultation`, `/advisor/reports`.
- API: `/api/auth/*`, `/api/students/*`, `/api/recommendations`, `/api/courses/<course_code>/prerequisite-chain`.

## Cấu trúc

```text
backend/
  app/
    routes/          API, xác thực và giao diện Flask
    agent/           vị trí triển khai Orchestrator và State
    schemas/         vị trí triển khai hợp đồng capability
    validation/      vị trí triển khai Standard Validator
    services/        ontology, eligibility, Beam Search, risk, explanation
    models/
    templates/
    static/
  tests/
knowledge/
  ontology/          RDF/OWL và cấu hình ontology hiện có
  queries/           vị trí tách SPARQL có định danh
  rules/             vị trí đóng gói rule có phiên bản
experiments/         benchmark, đánh giá và biểu đồ
benchmark_results/  kết quả thực nghiệm hiện có
data/                dữ liệu ứng dụng
frontend/            mã nguồn CSS và công cụ build tài nguyên Flask
scripts/             tiện ích xử lý dữ liệu
legacy/              mã tham khảo cũ
docs/
run_app.py           điểm khởi động từ thư mục gốc
```

`agent/`, `schemas/`, `validation/`, `knowledge/queries/` và `knowledge/rules/` mới là khung thư mục; chức năng MVP tương ứng chưa được triển khai. `frontend/` hiện chỉ chứa công cụ build, không phải ứng dụng frontend độc lập.

Chạy từ thư mục gốc: `python run_app.py`, `python -m pytest`, `npm run build:ui`. Khi dùng Flask CLI: `python -m flask --app backend.app.app:app run`. Điểm WSGI là `backend.app.app:app`.


Xem thêm [Sách hướng dẫn sử dụng](HDSD_HeThong_CoVanHocTap.md).
