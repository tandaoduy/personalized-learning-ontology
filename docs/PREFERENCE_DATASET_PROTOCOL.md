# Preference Dataset protocol (RQ3 — chưa huấn luyện LTR)

LTR chưa được triển khai và không được suy diễn từ feedback mô phỏng của E2E/batch. Chỉ feedback thật của sinh viên hoặc cố vấn mới tạo một bản ghi preference.

Mỗi bản ghi phải giữ: `anonymous_student_id`, `run_id`, request và source-manifest hash, các plan đã hiển thị cùng thứ tự hiển thị, feature/ranking score, evidence IDs, hành động chọn/chỉnh sửa, AdjustmentRequest và thời điểm. Không lưu tên, mã sinh viên gốc hoặc mapping pseudonym trong dataset nghiên cứu.

Chất lượng dữ liệu trước khi train:

- Loại bản ghi thiếu source/version, evidence hoặc displayed order.
- Tách train/validation/test theo `anonymous_student_id`, không tách ngẫu nhiên theo interaction.
- Giữ feedback sửa đổi là adjustment event; không xem là nhãn preference nếu người dùng chưa chọn một phương án.
- Validator vẫn là cổng hard constraint; LTR chỉ rerank plan đã valid.

Chỉ bắt đầu LTR khi có số lượng phản hồi thật được xác định trước trong protocol, được ẩn danh và kiểm tra chất lượng. Khi đó mới báo cáo NDCG@3/MRR cho RQ3.
