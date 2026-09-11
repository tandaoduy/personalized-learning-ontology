# Agent Orchestrator

`AgentOrchestrator` quản lý State của một planning run. Nó không gọi Flask, `RecommendationEngine`, LLM hoặc rule học vụ; các capability được nối vào sau qua contract ở `schemas/capability.py`.

Luồng đã được khung hóa:

```text
received → loading_context → loading_knowledge → building_course_space
→ generating → validating → assessing_risk → ranking → explaining
→ awaiting_feedback → final_validating → confirmed
```

Nếu toàn bộ candidate không valid, Orchestrator chuyển sang `replanning` khi còn budget, hoặc `no_plan_found` khi hết budget. Tool error dừng run với `failed`; dữ liệu nguồn thiếu dùng `needs_data`. Chỉ `apply_validations` nhận `ValidationResult`; chỉ status `valid` mới được chuyển tới `assessing_risk`.

## Capability Adapters

7 adapter được nối với service thật qua `AgentPipeline` trong `pipeline.py`:
- `load_student_context`: StudentContextOutput
- `load_knowledge_context`: KnowledgeContext  
- `build_course_space`: CourseSpace
- `generate_candidates`: GenerationResult
- `validate_candidate`: ValidatedPlan
- `assess_plan_risk`: RiskBatch
- `rank_valid_plans`: RankingResult

Mỗi adapter nhận `ToolCallContext` + typed parameters, trả về `ToolResult[OutputSchema]` với `Provenance`. Orchestrator gọi adapter qua `create_call_context()` → adapter function → `apply_result()` / `apply_generation_result()` / `apply_validations()`.

**Ngày 10/09/2026:** SV001 chạy qua StudentDataService, ontology, Beam Search và StandardValidator;
hai candidate valid được tính Risk, chấm sáu feature, xếp hạng, chọn đa dạng và tạo giải thích có evidence trước khi Orchestrator tới `awaiting_feedback`. Có ca đối chứng thêm môn sai chuyên ngành.
Bộ kết quả kiểm thử mới nhất nằm trong `artifacts/agent_acceptance/`; đó không phải kết quả
toàn bộ repository.

## Ràng buộc pilot về dữ liệu đầu vào

- Chỉ nhận `target_term_id=next-term`, được định nghĩa là học kỳ hiện tại cộng một. Các kỳ quá khứ
  hay mã kỳ bất kỳ trả `TARGET_TERM_UNSUPPORTED` cho tới khi có academic-calendar mapping có phiên bản.
- Ngành được ánh xạ tường minh: CNTT/Công nghệ thông tin → `CNTT`; KHMT/Khoa học máy tính → `KHMT`.
  Không nhận diện được ngành sẽ trả `MAJOR_MAPPING_UNKNOWN`, không tự mặc định CNTT.
- Trạng thái lần học được phân biệt chính xác: `Chưa đạt` → failed; `Đạt` → passed;
  `Miễn` và `Không tính điểm` → exempt.

Tái chạy và xuất request, snapshots, JSON, trace, source audit và kiểm thử:

```powershell
python scripts/run_m4_acceptance.py --with-tests
```

Xem [mapping capability](../../../docs/MAPPING_CAPABILITY_MODULE_TOOL.md) và
[kế hoạch MVP](../../../docs/KE_HOACH_TRIEN_KHAI_AGENT_MVP.md). Pipeline đã nối Risk, Ranking và Grounded Explanation. Trạng thái học vụ dùng proxy `ProgressRiskAnalyzer` có version và được đánh dấu không phải cảnh báo học vụ chính thức. Các nhánh Feedback/Re-planning/Confirm còn cần triển khai.
