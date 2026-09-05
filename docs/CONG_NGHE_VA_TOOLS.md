# CÔNG NGHỆ VÀ CÔNG CỤ CHO AI AGENT

> Nguồn: [TÀI LIỆU THIẾT KẾ AI AGENT LẬP KẾ HOẠCH HỌC TẬP.pdf](<TÀI LIỆU THIẾT KẾ AI AGENT LẬP KẾ HOẠCH HỌC TẬP.pdf>). Nội dung và trạng thái công nghệ được đồng bộ theo bản PDF.

## 1. Technology Stack

| Lớp | Công nghệ | Trạng thái |
|---|---|---|
| Agent | LangGraph, Pydantic | Dự kiến MVP |
| Knowledge | RDF/OWL, Protégé, RDFLib, SPARQL | Đang dùng một phần |
| Planning | Python, Beam Search, heuristic | Đang dùng |
| Validation | Python Rule Engine + Ontology | Cần đóng gói capability |
| Data | PostgreSQL, SQLAlchemy | Kiến trúc đích; hiện dùng JSON/CSV |
| Backend | Flask | Đang dùng |
| Testing | Pytest | Đang dùng |
| Future | LTR, pgvector/RAG, LLM | Mở rộng |

## 2. Agent Capabilities

| Capability | Trách nhiệm | State output |
|---|---|---|
| Student Context | Hồ sơ, lịch sử, GPA, tín chỉ, cảnh báo | Student Context |
| Ontology | CTĐT và quan hệ học phần | Knowledge Context, Evidence |
| Eligibility | Môn đủ điều kiện và bị loại | Course Space |
| Candidate Generator | Sinh Safe/Balanced/Accelerated | Candidate Plans |
| Validator | Kiểm tra hard constraints | Validation Results |
| Ranking | Chấm điểm và chọn Top-3 hợp lệ | Ranked Plans |
| Risk | Phân tích tiến độ và tải học | Risk Results |
| Explanation | Giải thích từ evidence | Explanations |
| Feedback/Re-planning | Chuẩn hóa phản hồi và lập lại | Feedback, Adjustment Request |

Danh sách trên mô tả capability logic, chưa ấn định tên hàm, API hoặc schema triển khai.

## 3. Hợp đồng tool và cập nhật State

Sₜ là Agent State ở bước t; aₜ là hành động điều phối. Tập hành động gồm LoadContext, QueryKnowledge, BuildCourseSpace, Generate, Validate, Rank, Explain, CollectFeedback, Replan, FinalValidate và Stop. Cấu trúc State và snapshot được mô tả tại mục 4 của bản thiết kế.

Mỗi tool hoặc capability Tⱼ được biểu diễn bởi:

> **Công thức 4:** Tⱼ: Iⱼ → Oⱼ ∪ Errorⱼ

Trong đó Iⱼ là dữ liệu đầu vào, Oⱼ là dữ liệu đầu ra hợp lệ và Errorⱼ là tập lỗi có thể xảy ra. Mỗi tool phải công bố input schema, output schema, precondition, postcondition, timeout và provenance.

Hàm chuyển trạng thái của Agent được biểu diễn như sau:

> **Công thức 5:** Sₜ₊₁ = δ(Sₜ, aₜ, Oⱼ)

Trong đó aₜ là hành động tại bước t và Oⱼ là kết quả do tool trả về. Chỉ Agent Orchestrator được phép áp dụng hàm chuyển trạng thái δ; các tool riêng lẻ không được tự ý sửa toàn bộ Agent State.

## 4. Ranh giới trách nhiệm

- Ontology và Rule Engine quyết định tính hợp lệ; Candidate Generator chỉ sinh ứng viên.
- Validator kiểm tra độc lập trước Ranking, sau Re-planning và trước xác nhận.
- Ranking dùng tổng có trọng số các đặc trưng; Safe, Balanced và Accelerated dùng cùng tập đặc trưng với trọng số khác nhau. Trọng số được xác định trên validation và cố định trước test.
- Độ khác biệt Top-3 dùng Jaccard trên tập học phần và ngưỡng được xác định trong giai đoạn validation.
- LLM chỉ hỗ trợ diễn giải mục tiêu, phản hồi và evidence; không tự tạo học phần, tín chỉ, quan hệ tiên quyết hoặc quy định học vụ.
- LTR chỉ thay đổi thứ tự phương án hợp lệ. Preference cố vấn là tín hiệu giám sát chính trong thực nghiệm; dữ liệu preference phải được ẩn danh.
- PostgreSQL/SQLAlchemy là kiến trúc đích; trạng thái hiện tại theo PDF là JSON/CSV. LTR, pgvector/RAG và LLM thuộc phần mở rộng.

Chi tiết State, Memory, công thức Ranking, evidence, Preference Dataset và protocol thực nghiệm xem [THIET_KE_AI_AGENT.md](THIET_KE_AI_AGENT.md). PDF chưa ấn định tên hàm, API, schema triển khai hoặc mô hình LTR cụ thể.
