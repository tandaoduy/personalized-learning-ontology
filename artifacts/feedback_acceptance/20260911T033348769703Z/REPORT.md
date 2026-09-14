# Ca chấp nhận phản hồi — SV001

- Sinh viên/cố vấn chọn phương án hiển thị và yêu cầu thay `INT6209` bằng `SOT366`.
- `normalize_feedback` kiểm tra schema, hash kết quả đã hiển thị và tạo `AdjustmentRequest`.
- Hệ thống chạy lại Generation → Validator → Risk → Ranking → Explanation ở iteration 1.
- Candidate mới có `SOT366`, không có `INT6209`; tất cả candidate xuất ra đều `valid`.
- Phản hồi `confirm` kích hoạt StandardValidator lần cuối trước trạng thái `confirmed`.

Chi tiết JSON, trace và explanation ở `initial.json`, `feedback.json`, `replanned.json`, `confirmed.json` và `summary.json`.
