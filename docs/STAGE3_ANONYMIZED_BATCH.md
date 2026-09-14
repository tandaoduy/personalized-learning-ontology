# Giai đoạn 3 — Batch hồ sơ ẩn danh

Mục đích của giai đoạn này là đo hành vi của Agent pipeline trên toàn bộ hồ sơ hiện có sau khi bộ E2E có kiểm soát đã ổn định. Đây không phải là đánh giá kết quả học tập, độ chính xác so với cố vấn, hay xác nhận chính sách chính thức.

Chạy toàn bộ batch từ thư mục gốc:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_anonymized_batch.py
```

Smoke test hai hồ sơ:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_anonymized_batch.py --limit 2
```

Mỗi lượt chạy tạo `artifacts/anonymized_batch/<timestamp>/` gồm `manifest.json`, `summary.json`, `REPORT.md` và một thư mục artifact cho từng profile. Mã nguồn và tên sinh viên không được ghi vào artifact; runner thay bằng `B0001`, `B0002`, … trước khi pipeline chạy.

Điều kiện tái lập: seed 42, beam width và giới hạn tìm kiếm từ `Config`, cùng `StandardValidator`, target term `next-term`, target credits 18. Các chỉ số được tổng hợp gồm validity, histogram vi phạm, pairwise diversity, latency, evidence coverage và mức đầy đủ artifact.

Giới hạn phải nêu khi sử dụng kết quả: `next-term` là proxy chứ chưa ánh xạ lịch đào tạo thực tế; Academic Risk là proxy; phiên bản CTĐT/rule phải được diễn giải theo `source_manifest` trong KnowledgeSnapshot của từng result. Batch không thay thế xác nhận chính thức của Trường và không trả lời RQ3/LTR. Xem thêm [Nguồn dữ liệu và limitation](DATA_LIMITATIONS_AND_SOURCES.md).

Quy ước dữ liệu đã xác nhận cho FLS310, FLS312 và FLS313: mỗi học phần có **4 tín chỉ đăng ký** nhưng không tính GPA. Generator và evidence/Standard Validator phải cùng dùng giá trị registration credit này. Đây vẫn cần được đối chiếu với nguồn CTĐT có version trước khi diễn giải như chính sách chính thức của Trường.
