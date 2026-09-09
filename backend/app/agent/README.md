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

5 adapter skeleton đã được triển khai trong `backend/app/capabilities/`:
- `load_student_context`: StudentContextOutput
- `load_knowledge_context`: KnowledgeContext  
- `build_course_space`: CourseSpace
- `generate_candidates`: GenerationResult
- `validate_candidate`: ValidatedPlan

Mỗi adapter nhận `ToolCallContext` + typed parameters, trả về `ToolResult[OutputSchema]` với `Provenance`. Orchestrator gọi adapter qua `create_call_context()` → adapter function → `apply_result()` / `apply_generation_result()` / `apply_validations()`.

**Hiện tại:** skeleton implementation (mock data, minimal evidence). Tests pass (21/21).  
**Tiếp theo:** wire adapters to real services (`StudentDataService`, `RecommendationEngine`, `StandardValidator`).

Xem [Capability Adapter README](../capabilities/README.md) để biết chi tiết integration, wiring steps, và testing strategy. Các nhánh Feedback/Confirm và real service wiring đang pending. Tham khảo [sơ đồ mapping](../../../docs/MAPPING_CAPABILITY_MODULE_TOOL.md) và [kế hoạch MVP](../../../docs/KE_HOACH_TRIEN_KHAI_AGENT_MVP.md).
