# Nguồn dữ liệu và limitation

Mỗi `KnowledgeSnapshot` mới chứa `source_manifest`: inventory có `source_ref`, version, ngày hiệu lực (nếu biết), bytes hash và trạng thái thẩm quyền cho CTĐT/catalog, tiên quyết/song hành, quota/credit policy, kỳ mở môn và academic calendar. Template khai báo nằm tại `knowledge/source_manifest.json`; hash runtime được tính khi pipeline tải knowledge context.

Hiện các nguồn trong repository mang trạng thái `provisional`, `proxy` hoặc `unavailable`, không phải `official`. Vì vậy kết quả chỉ là đánh giá MVP/research artifact, không phải quyết định học vụ hay quy định chính thức của Trường.

- `next-term` chỉ là `current_semester + 1`; chưa có ánh xạ academic calendar thực tế.
- `openSemesterType` là thuộc tính ontology, chưa phải lịch mở lớp/kỳ thực tế được xác nhận.
- Quota và registration-credit policy là cấu hình MVP. FLS310/FLS312/FLS313 có 4 tín chỉ đăng ký nhưng không tính GPA theo quy ước dữ liệu hiện dùng; cần đính kèm văn bản CTĐT có version trước khi gọi đây là chính sách chính thức.
- `ProgressRiskAnalyzer` là proxy nghiên cứu có version, không phải cảnh báo học vụ chính thức.
- Không còn tạo baseline tiên quyết/học trước rỗng: `prior_study_requirements` được xây từ quan hệ prerequisite trong ontology có version. Nguồn riêng cho policy học trước vẫn được manifest ghi là chưa có.

Khi nhận được nguồn chính thức, cập nhật `knowledge/source_manifest.json` với URL/tài liệu, version, ngày hiệu lực và `authority_status: official`, rồi chạy lại E2E, batch và full regression.
