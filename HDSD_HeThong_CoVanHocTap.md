# Sách hướng dẫn sử dụng hệ thống

## 1. Mục đích

Hệ thống có hai vai trò:

- **Sinh viên:** xem hồ sơ, lịch sử, GPA, tiến độ và kế hoạch đã được xác nhận.
- **Cố vấn học tập:** quản lý hồ sơ, phân tích nguy cơ, sinh kế hoạch, chỉnh sửa và chốt kế hoạch.

Khuyến nghị của hệ thống không thay thế việc kiểm tra lịch mở lớp và quy định đăng ký chính thức của trường.

## 2. Đăng nhập

1. Chạy ứng dụng theo [README.md](README.md).
2. Mở `http://localhost:5000`.
3. Đăng nhập bằng tài khoản đã được cấp hoặc đăng ký tại `/register`.
4. Không chia sẻ mật khẩu. Mật khẩu đăng ký phải dài ít nhất 8 ký tự; phiên đăng nhập có thời hạn 60 phút.
5. Sinh viên chỉ truy cập được hồ sơ và kế hoạch của chính mình. Các chức năng quản trị dành cho cố vấn học tập.

## 3. Dành cho sinh viên

### Tổng quan

Vào `/student` để xem GPA tích lũy, tín chỉ đạt, môn nợ và trạng thái tiến độ.

### Hồ sơ và lịch sử

Vào `/student/profile` hoặc `/student/history` để xem ngành, chuyên ngành, mục tiêu học tập, từng lần học, điểm và học kỳ. Nếu dữ liệu sai, liên hệ cố vấn để cập nhật.

### Kế hoạch

Vào `/student/plan` để xem học phần được đề xuất, số tín chỉ, học kỳ, lý do ưu tiên và cảnh báo. Kế hoạch chỉ chính thức sau khi cố vấn chốt.

## 4. Dành cho cố vấn

### Quản lý sinh viên

Vào `/advisor/students` để tìm kiếm/lọc sinh viên. Từ hồ sơ có thể xem lịch sử hoặc mở `/advisor/student-editor` để cập nhật thông tin và học phần.

### Phân tích nguy cơ

Vào `/advisor/at-risk`. Hệ thống xét tín chỉ đã đạt, tín chỉ dự kiến, môn nợ, chuỗi tiên quyết bị chặn và xu hướng hoàn thành. Mức `LOW`, `MEDIUM`, `HIGH` là tín hiệu hỗ trợ tư vấn.

### Sinh kế hoạch

1. Vào `/advisor/scenarios` và chọn sinh viên.
2. Chọn mục tiêu **Đúng hạn** hoặc **Học vượt**.
3. Chạy sinh kế hoạch.
4. Xem học phần được chọn, tổng tín chỉ, học phần bị loại và lý do.

Bộ máy kiểm tra học phần đã đạt, tiên quyết, song hành, ngành/chuyên ngành, học kỳ mở, quota tự chọn và giới hạn tín chỉ. Môn học lại hoặc môn bắt buộc bị trễ thường được ưu tiên.

### Chốt kế hoạch

Tại `/advisor/consultation`, kiểm tra từng môn và tổng tín chỉ, bỏ/thêm môn cần thiết, nhập nhận xét rồi chọn **Chốt và xác nhận kế hoạch**. Chỉ thêm thủ công các môn đã được xác minh điều kiện học vụ.

### Báo cáo

Vào `/advisor/reports` để xem hoặc in kế hoạch đã xác nhận. Kiểm tra đúng sinh viên và học kỳ trước khi in.

## 5. Quy tắc nghiệp vụ

- Không đề xuất môn đã đạt.
- Môn thiếu tiên quyết/song hành bị loại kèm lý do.
- Không vượt `REGISTER_MAX_CREDITS` (mặc định 27).
- Môn miễn có thể được ghi nhận là đạt nhưng không tính GPA nếu không có điểm.
- Học lại không cộng tín chỉ lần hai; điểm tổng hợp lấy từ lần hợp lệ theo quy tắc dữ liệu.
- Mã học phần phải tồn tại trong ontology.

## 6. Xử lý sự cố

### Ứng dụng không khởi động

Kiểm tra chạy từ thư mục gốc và các tệp `knowledge/ontology/ontology_v23.rdf`, `data/DanhSachSinhVien.json`, `data/DanhSachSinhVien.csv`. Xem log terminal và `/api/health`.

### Không có môn được đề xuất

Kiểm tra ngành/chuyên ngành, tiên quyết, song hành, học kỳ mở, quota và phần **Môn bị loại/Lý do**.

### GPA hoặc tín chỉ sai

Kiểm tra `course_attempts`, trạng thái, `grade_specified`, `attempt_number`, `semester_taken` và mã môn trong ontology.

### Chạy test

```powershell
python -m pytest
# hoặc chạy pytest và sinh báo cáo Markdown:
python experiments/run_benchmark.py
```

Notebook trong `backend/tests/test_ontology/` chỉ dùng để minh họa/phân tích ontology, không phải bộ kiểm thử chính.

## 7. API kiểm tra nhanh

- `GET /api/health`
- `GET /api/debug/pipeline/<student_id>` (chỉ development và cố vấn)
- `GET /api/courses/<course_code>/prerequisite-chain`

Trong production, `/components/*` và endpoint debug không được cung cấp. Không chia sẻ log debug hoặc thông tin phiên đăng nhập.
