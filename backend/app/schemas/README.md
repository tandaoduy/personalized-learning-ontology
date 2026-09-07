# Hợp đồng dữ liệu MVP

Các model Pydantic v2 được export từ `backend.app.schemas`. Dùng `Model.model_validate(payload)` hoặc `Model.model_validate_json(text)` để nhận dữ liệu; `model_dump(mode="json")`/`model_dump_json()` để xuất JSON; `model_json_schema()` để xuất hợp đồng JSON Schema.

| Schema | Nội dung |
|---|---|
| PlanningRequest | Request ID, sinh viên, học kỳ đích, goal, tín chỉ và preference |
| StudentSnapshot | Hồ sơ bất biến, lịch sử lần học, kết quả hiện tại, GPA và cảnh báo |
| KnowledgeVersion | Phiên bản student, curriculum, ontology, rule, offering |
| KnowledgeSnapshot | Snapshot ID, phiên bản và tham chiếu tài nguyên tri thức |
| EvidenceRecord | Quyết định, kết quả, triple/query/rule, nguồn và phiên bản |
| CandidatePlan | Plan ID/version, request/student/term, snapshot versions và môn ứng viên |
| ValidationResult | Kết luận, vi phạm, cảnh báo và evidence theo đúng plan/version |

Model cấm trường lạ, bất biến; danh sách dùng tuple/frozenset để tránh sửa lồng nhau. Mã môn được trim và viết hoa; timestamp bắt buộc có múi giờ. Không áp giới hạn tín chỉ học vụ cố định trong schema.

`goal` dùng `on_time` hoặc `accelerated`; `plan_type` dùng `safe`, `balanced`, `accelerated`. Lớp tích hợp sau này cần ánh xạ nhãn tiếng Việt đang có trong StudentProfile. Chưa thay thế model hoặc API Flask hiện tại.

KnowledgeSnapshot lưu tham chiếu tới artifact bất biến, chưa tải hoặc xác minh artifact. Bên tạo snapshot chịu trách nhiệm gắn đúng phiên bản. Các ID/version không được tự sinh mặc định để tránh tạo provenance giả.

Evidence ontology phải có triple; SPARQL có query ID, nội dung và xác nhận đã chạy (kết quả SELECT rỗng vẫn hợp lệ); rule có ID, inputs và kết quả. Schema kiểm tra hình dạng, không chứng minh query thực sự đã chạy hoặc rule đúng. Dịch vụ Evidence/Validator sẽ chịu trách nhiệm xác minh nguồn.

Candidate không phải chứng nhận hợp lệ: duplicate và tín chỉ không khớp catalog vẫn có thể đi vào để Standard Validator phát hiện. `total_credits` là property tính từ courses, không phải trường nhận từ client hoặc trường JSON. Candidate rỗng không hợp lệ về cấu trúc; khi không sinh được phương án, Generator trả tập candidate rỗng.

ValidationResult có bốn trạng thái: valid, invalid, partially_validated, error. checked_rules và pending_rules phải phân hoạch đầy đủ REQUIRED_RULES do hệ thống quản lý. valid chỉ được chấp nhận khi không còn pending và không có violations; error bắt buộc có errors cấu trúc. Có lỗi thực thi thì status error được ưu tiên, nhưng vẫn giữ violations đã thu thập.

ontology_evidence giữ fact gốc, evidence giữ kết luận; supporting_evidence_ids phải trỏ tới fact cùng môn, cùng phiên bản ontology. Lỗi xảy ra trước truy vấn có thể trả evidence rỗng. Các schema không tự thực hiện hay chứng minh rule đã chạy; phạm vi thực tế được StandardValidator quyết định.

Validator v3 kiểm tra toàn bộ REQUIRED_RULES khi đủ dữ liệu; thiếu/lỗi dữ liệu giữ rule pending và trả error. KnowledgeSnapshot bổ sung target_semester_type, curriculum_courses, prior_study_requirements và elective_quotas. Chi tiết nguồn chính sách và giới hạn xem [Validator](../validation/README.md). AgentState/AdjustmentRequest và tích hợp API chưa triển khai.
