# Sơ đồ mapping capability → tool → module

Cập nhật theo source ngày 2026-09-14. Sơ đồ phục vụ báo cáo kiến trúc MVP; Orchestrator, State, trace, run store, capability adapters và AgentPipeline đã được triển khai. Module ghi “đã có” là phần tái sử dụng hoặc capability đã nối; giới hạn dữ liệu nguồn vẫn được nêu riêng, không suy diễn thành chính sách chính thức.

Đường dẫn Python tính từ `backend/app/`; đường dẫn `knowledge/` tính từ gốc repository. Mỗi sơ đồ đọc từ trái sang phải: **capability và tên tool → adapter → module nghiệp vụ/nguồn**.

- **Xanh lá — ĐÃ NỐI:** capability/module đang được AgentPipeline dùng.
- **Vàng — TÁI SỬ DỤNG:** source cũ còn được bọc bởi capability.
- **Xanh dương, viền đứt — CÒN THIẾU:** hạng mục chưa có, chủ yếu là source-loader xác minh policy chính thức.
- Mũi tên thể hiện quan hệ gọi/tái sử dụng; thứ tự runtime được kiểm soát bởi AgentOrchestrator.

## 1. Student Context, Ontology, Eligibility và Generation

```mermaid
flowchart LR
    SC["Student Context<br/>load_student_context<br/>ĐÃ NỐI"] --> SCA["capabilities/student_context.py<br/>ĐÃ NỐI"]
    SCA --> SCS["services/student_data_service.py<br/>ĐÃ CÓ"]

    KN["Ontology / Knowledge<br/>load_knowledge_context<br/>ĐÃ NỐI"] --> KNA["capabilities/knowledge.py<br/>ĐÃ NỐI"]
    KNA --> KNS["services/ontology_evidence_service.py<br/>ĐÃ CÓ"]
    KNS --> KQ["knowledge/ontology/ và knowledge/queries/<br/>ĐÃ CÓ"]
    KNA --> KNL["services/knowledge_context_loader.py<br/>Manifest và policy snapshot<br/>DỰ KIẾN"]

    EL["Eligibility<br/>build_course_space<br/>ĐÃ NỐI"] --> ELA["capabilities/eligibility.py<br/>ĐÃ NỐI"]
    ELA --> ELS["services/recommendation/eligibility.py<br/>TÁI SỬ DỤNG"]

    GE["Candidate Generation<br/>generate_candidates<br/>ĐÃ NỐI"] --> GEA["capabilities/generation.py<br/>ĐÃ NỐI"]
    GEA --> GES["services/recommendation/candidate_generation.py<br/>Beam Search — TÁI SỬ DỤNG"]

    classDef existing fill:#ecfdf5,stroke:#15803d,color:#14532d;
    classDef adapt fill:#fffbeb,stroke:#b45309,color:#78350f;
    classDef planned fill:#eff6ff,stroke:#2563eb,color:#1e3a8a,stroke-dasharray:5 3;
    class SC,SCA,SCS,KN,KNA,KNS,KQ,EL,ELA,GE,GEA existing;
    class ELS,GES adapt;
    class KNL planned;
```

Student Context tạo hồ sơ tại học kỳ đích. Knowledge capability tạo snapshot/evidence và giữ manifest/hash; loader xác minh artifact nguồn chính thức còn thiếu. Eligibility trả trạng thái từng môn cùng evidence; Generation trả candidate/attempt trace, chưa kết luận validity. Các capability nhận snapshot tường minh.

## 2. Validator, Risk, Ranking và Grounded Explanation

```mermaid
flowchart LR
    VA["Standard Validation<br/>validate_candidate<br/>ĐÃ NỐI"] --> VAA["capabilities/validation.py<br/>ĐÃ NỐI"]
    VAA --> VAS["validation/validator.py<br/>StandardValidator.validate<br/>ĐÃ CÓ"]
    VAS --> VR["validation/rules/ và prerequisite_rule.py<br/>11 nhóm kiểm tra — ĐÃ CÓ"]
    VAS --> VE["services/ontology_evidence_service.py<br/>ĐÃ CÓ"]

    RI["Risk<br/>assess_plan_risk<br/>ĐÃ NỐI"] --> RIA["capabilities/risk.py<br/>ĐÃ NỐI"]
    RIA --> RIS["services/plan_risk_service.py<br/>Risk theo PDF v3 — ĐÃ NỐI"]

    RA["Ranking / Diversity<br/>rank_valid_plans<br/>ĐÃ NỐI"] --> RAA["capabilities/ranking.py<br/>ĐÃ NỐI"]
    RAA --> RAS["services/plan_ranking_service.py<br/>6 feature và Jaccard — ĐÃ NỐI"]

    EX["Grounded Explanation<br/>explain_plans"] --> EXA["capabilities/explanation.py"]
    EXA --> EXS["services/grounded_explanation_service.py<br/>Claim liên kết evidence"]

    classDef existing fill:#ecfdf5,stroke:#15803d,color:#14532d;
    classDef planned fill:#eff6ff,stroke:#2563eb,color:#1e3a8a,stroke-dasharray:5 3;
    class VA,VAA,VAS,VR,VE,RI,RIA,RIS,RA,RAA,RAS,EX,EXA,EXS existing;
```

Validator độc lập, không gọi LLM/Agent/Generator; chỉ `valid` trên đúng candidate/snapshot được chuyển tiếp. Risk chạy trước Ranking vì Safety là feature. `services/recommendation/plan_risk.py` và `services/explanation_generator.py` hiện có là phiên bản cũ để tham khảo; chưa đáp ứng công thức Risk PDF v3 hoặc chuỗi claim → evidence mới.

## 3. Feedback, Re-planning và Confirm

```mermaid
flowchart LR
    FB["Feedback<br/>normalize_feedback / persist_feedback<br/>ĐÃ NỐI"] --> FBA["capabilities/feedback.py<br/>ĐÃ NỐI"]
    FBA --> FBS["services/feedback_service.py<br/>Chuẩn hóa và lưu phản hồi<br/>ĐÃ NỐI"]

    RP["Re-planning / Confirm<br/>Nhánh replan / confirm<br/>ĐÃ NỐI"] --> OR["agent/orchestrator.py<br/>State, budget, revision<br/>ĐÃ TRIỂN KHAI"]
    OR --> CT["Gọi lại các capability<br/>Generation → Validation → Risk<br/>→ Ranking → Explanation<br/>ĐÃ NỐI"]
    OR --> FV["Refresh snapshots<br/>→ validate_candidate → Confirm<br/>ĐÃ NỐI"]
    OR --> ST["services/agent_run_store.py<br/>Run, State và artifact<br/>ĐÃ NỐI"]
    OR --> TR["agent/trace.py<br/>Tool calls và evidence refs<br/>ĐÃ NỐI"]

    classDef existing fill:#ecfdf5,stroke:#15803d,color:#14532d;
    classDef planned fill:#eff6ff,stroke:#2563eb,color:#1e3a8a,stroke-dasharray:5 3;
    class FB,FBA,FBS,RP,OR,CT,FV,ST,TR existing;
```

Re-planning là nhánh điều phối của Orchestrator, không phải generator hoặc bộ luật thứ hai. Feedback tạo adjustment/selection intent; không sửa trực tiếp candidate hoặc ontology. Orchestrator gọi toàn bộ capability ở các sơ đồ trên theo State và là thành phần duy nhất cập nhật State. Khi confirm, chỉ ghi xác nhận sau Final Validation hợp lệ và kiểm tra revision nguồn.

## 4. Schema và contract dùng chung

| Phạm vi | Module/schema | Trạng thái |
|---|---|---|
| Request và candidate | `schemas/planning.py`: PlanningRequest, CandidatePlan | Đã có |
| Student/knowledge snapshots | `schemas/snapshot.py`, `schemas/common.py` | Đã có; loader nguồn còn cần triển khai |
| Ontology và rule evidence | `schemas/evidence.py`: EvidenceRecord, OntologyFactEvidence | Đã có |
| Kết luận Validator | `schemas/validation.py`: ValidationResult | Đã có |
| Envelope, lỗi, provenance | `schemas/capability.py` | Đã có |
| Agent State | `schemas/agent_state.py` | Đã có |
| Features và Ranking Result | `schemas/ranking.py` | Đã có và được AgentPipeline dùng |
| Feedback và adjustment | `schemas/feedback.py`, `capabilities/feedback.py`, `services/feedback_service.py` | Đã nối qua AgentPipeline |

Mỗi tool phải có input/output schema, precondition, postcondition, xử lý lỗi và provenance. Quyết định học vụ lưu nguồn/version và evidence từ triple, query hoặc rule; explanation tham chiếu lại evidence. Bảng contract chi tiết nằm tại [đặc tả MVP, mục 3–5](DAC_TA_TRIEN_KHAI_MVP.md).

## 5. Phạm vi hoàn thành của tài liệu

**Source hiện có ontology, engine, schemas, StandardValidator, AgentState, feedback schema, trace, run store, adapters và AgentPipeline tích hợp.** API Agent tại `/api/agent/runs` dùng AgentPipeline; endpoint recommendation cũ vẫn giữ RecommendationEngine cho tương thích và không phải bằng chứng thay thế pipeline Agent.

Trạng thái trên được đối chiếu với source và test pipeline/API. Các hạng mục nguồn chính thức còn thiếu phải tiếp tục được ghi rõ, không suy diễn từ việc capability đã tích hợp.

Tham chiếu: [bảng mapping](DAC_TA_TRIEN_KHAI_MVP.md#2-mapping-capability--tool--module), [kế hoạch M0–M7](KE_HOACH_TRIEN_KHAI_AGENT_MVP.md), [cấu trúc engine hiện có](../backend/app/services/recommendation/README.md).
