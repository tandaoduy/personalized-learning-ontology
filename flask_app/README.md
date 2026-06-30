# Flask App (Web) - Gợi Ý Kế Hoạch Học Tập

Ứng dụng Flask cung cấp giao diện web và API cho hệ thống gợi ý kế hoạch học tập (dựa trên ontology).

## Cài Đặt

```bash
pip install -r requirements.txt
```

## Chạy Ứng Dụng

Khuyến nghị chạy từ root (đã cấu hình UTF-8 trên Windows):

```bash
python run_app.py
```

Mặc định chạy tại: `http://localhost:5000`

## Route Giao Diện

- `/` Trang chủ
- `/students` Danh sách sinh viên (gợi ý kế hoạch học tập)
- `/students/new` Thêm sinh viên
- `/students/<student_id>/course-history` Chi tiết danh sách môn của sinh viên

## API Chính

- `GET /api/students` Danh sách sinh viên
- `GET /api/students/<student_id>` Chi tiết sinh viên
- `POST /api/students` Thêm sinh viên (kèm danh sách môn + điểm)
- `GET /api/students/courses` Danh mục môn học (từ ontology)
- `GET /api/students/specializations` Danh sách chuyên ngành (từ ontology)
- `GET /api/students/next-id` Lấy mã SV kế tiếp (SVxxxx)
- `POST /api/recommendations` Tạo gợi ý kế hoạch học tập
- `POST /api/recommend` Bí danh tương thích cho buổi demo và tài liệu cũ
- `GET /api/health` Kiểm tra trạng thái hệ thống
- `GET /api/debug/pipeline/<student_id>` Kiểm tra luồng đầu-cuối

Ví dụ test nhanh:

```bash
curl http://localhost:5000/api/students
```

## Dữ Liệu / Cấu Hình

Các đường dẫn quan trọng nằm trong [config.py](./config.py):

- `owl/current/ontology_v19.rdf`
- `data/DanhSachSinhVien.json`
