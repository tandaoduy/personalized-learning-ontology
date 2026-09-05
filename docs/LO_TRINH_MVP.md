# Lộ trình tổ chức source và triển khai MVP

Tài liệu triển khai bổ sung cho [thiết kế](THIET_KE_AI_AGENT.md), theo góp ý ưu tiên Ontology Evidence, Standard Validator và Agent Orchestrator. Các bước dưới đây phân biệt việc đã làm với chức năng cần phát triển tiếp.

## 1. Tổ chức source đã thực hiện

Source đã được chuyển sang cấu trúc MVP:

- `backend/app/`: Flask, routes, services, models, templates/static; khung agent, schemas và validation.
- `backend/tests/`: bộ kiểm thử hiện có.
- `knowledge/ontology/`: ontology và các file cấu hình đi kèm; queries/rules là vị trí triển khai tiếp theo.
- `experiments/`: các script benchmark, đánh giá và sinh biểu đồ.
- `data/`, `docs/`: giữ tại gốc dự án.
- `frontend/`: giữ nguồn CSS và công cụ build tài nguyên Flask; chưa là frontend độc lập.
- `scripts/`: các tiện ích di chuyển/ẩn danh dữ liệu; `benchmark_results/` giữ kết quả hiện có.

Điểm gọi Python mới là `backend.app.services.recommendation_engine.RecommendationEngine`. Bốn nhóm Ontology, Eligibility, Candidate Generation và Plan Risk được giữ trong services/recommendation; xem [README module](../backend/app/services/recommendation/README.md).

Các nhóm này vẫn dùng context chung qua mixin, chưa phải capability độc lập. Agent, schemas và validation mới có khung package. Lệnh chạy tại gốc vẫn là `python run_app.py`; kiểm thử bằng `python -m pytest`; build tài nguyên bằng `npm run build:ui`.

## 2. Mốc đối chiếu trước thay đổi

- Commit mã nguồn trước refactor: `fd9a7db1e365e716afcd7e249013ea5d932840d9`.
- Lệnh kiểm tra: `python -m pytest -q`.
- Trước refactor: 59 tests passed.
- Sau tách module: 59 tests passed. Sau chuyển cấu trúc: 61 tests passed, gồm hai kiểm thử mới bảo vệ đường dẫn dữ liệu/ontology và tài nguyên Flask. Build UI cũng đã được kiểm tra.
- Khi tách module: đối chiếu AST xác nhận thân hàm và chữ ký của mọi phương thức engine được giữ nguyên.

Commit này là mốc truy xuất thuật toán Beam Search hiện tại cho BL-03, chưa phải một gói thực nghiệm đã đóng băng. Khi chạy thực nghiệm cần lưu thêm snapshot dữ liệu/ontology, cấu hình, phiên bản phụ thuộc và seed. Beam Search hiện tại có ngẫu nhiên và thao tác trên tập hợp; cần đánh giá khả năng tái lập giữa các tiến trình trước khi đóng băng protocol.

## 3. Thứ tự phát triển tiếp theo

| Bước | Đầu ra cần hoàn thành |
|---|---|
| 1. Schemas | PlanningRequest, StudentSnapshot, KnowledgeVersion, EvidenceRecord, CandidatePlan, ValidationResult, AdjustmentRequest và AgentState |
| 2. Ontology Evidence | Truy xuất trả dữ kiện cùng triple/query/rule, kết quả và phiên bản nguồn; kiểm kê ngoại lệ đang viết trong Python |
| 3. Standard Validator | Module độc lập, deterministic trên cùng plan/snapshot; kiểm thử từng nhóm hard constraint; không phụ thuộc LLM |
| 4. Capability contracts | Input/output schema, precondition, postcondition, timeout, error handling và provenance cho từng capability |
| 5. Ranking và Diversity | Feature cấp kế hoạch, chuẩn hóa, trọng số Safe/Balanced/Accelerated, tie-break và ngưỡng Jaccard; hiệu chỉnh trên validation |
| 6. Orchestrator | Điều phối State, gọi capability, xử lý lỗi, giới hạn vòng, ghi trace và vô hiệu hóa kết quả phụ thuộc |
| 7. Explanation và Feedback | Giải thích từ evidence, chuẩn hóa điều chỉnh, Re-planning, Final Validation và lưu phản hồi |

Khung Orchestrator có thể được xây song song từ bước schema; chỉ kết nối capability thật khi hợp đồng và các kiểm tra tương ứng đã sẵn sàng.

Phân biệt môn không đủ điều kiện và môn đủ điều kiện nhưng không được chọn. Quyết định do Ranking phải truy vết được tới đặc trưng/điểm và dữ kiện hỗ trợ, không diễn đạt thành vi phạm học vụ.

## 4. Tiêu chí hoàn thành MVP

- Một hồ sơ chạy hết luồng Student Profile → Agent → Ontology → tối đa ba valid plans → Explanation → Feedback → Re-planning.
- Mọi phương án hiển thị qua Validator; không nới hard constraints để đủ ba phương án.
- Mỗi quyết định chọn/loại có căn cứ truy vết; nguồn ontology và rule có phiên bản.
- Thay candidate hoặc snapshot làm mất hiệu lực kết quả phụ thuộc.
- Chấp nhận phương án phải qua Final Validation trên dữ liệu hiện hành.
- Dừng đúng khi thiếu dữ liệu, lỗi công cụ, hết không gian tìm kiếm hoặc đạt giới hạn vòng.
- Lưu lựa chọn và chỉnh sửa cố vấn cùng plan features và phiên bản dữ liệu; chưa huấn luyện LTR.

## 5. Thực nghiệm sau khi luồng ổn định

Giữ các baseline trong bản thiết kế. BL-04 chỉ chạy offline và không nhận Ontology Validator feedback trong generation; mọi baseline được hậu kiểm bằng cùng Standard Validator. Đo valid plan rate trên toàn bộ candidate đã sinh trước khi lọc.

So sánh explanation có/không grounded trên cùng candidate, Validation và Ranking. LTR thực hiện sau khi thu được dữ liệu preference cố vấn phù hợp; chưa là điều kiện hoàn thành MVP đầu tiên.
