# Sơ đồ mapping capability → tool → module

Cập nhật theo source ngày 2026-09-08. Sơ đồ phục vụ báo cáo kiến trúc MVP; khung Orchestrator, State, trace và run store đã được triển khai. Các tool/adapter nghiệp vụ bên dưới vẫn chưa được nối; module ghi “đã có” là phần tái sử dụng, chưa đồng nghĩa đã đáp ứng capability contract.

Đường dẫn Python tính từ `backend/app/`; đường dẫn `knowledge/` tính từ gốc repository. Mỗi sơ đồ đọc từ trái sang phải: **capability và tên tool → adapter → module nghiệp vụ/nguồn**.

- **Xanh lá — ĐÃ CÓ:** source hoặc tài nguyên đang tồn tại.
- **Vàng — CẦN TÁCH:** source đã có nhưng còn dùng chung context của engine.
- **Xanh dương, viền đứt — DỰ KIẾN:** tool, adapter hoặc module cần triển khai.
- Mũi tên thể hiện quan hệ gọi/tái sử dụng dự kiến, không phải thứ tự thực thi hay bằng chứng đã tích hợp.

## 1. Student Context, Ontology, Eligibility và Generation

```mermaid
flowchart LR
    SC["Student Context<br/>load_student_context<br/>DỰ KIẾN"] --> SCA["capabilities/student_context.py<br/>DỰ KIẾN"]
    SCA --> SCS["services/student_data_service.py<br/>ĐÃ CÓ"]

    KN["Ontology / Knowledge<br/>load_knowledge_context<br/>DỰ KIẾN"] --> KNA["capabilities/knowledge.py<br/>DỰ KIẾN"]
    KNA --> KNS["services/ontology_evidence_service.py<br/>ĐÃ CÓ"]
    KNS --> KQ["knowledge/ontology/ và knowledge/queries/<br/>ĐÃ CÓ"]
    KNA --> KNL["services/knowledge_context_loader.py<br/>Manifest và policy snapshot<br/>DỰ KIẾN"]

    EL["Eligibility<br/>build_course_space<br/>DỰ KIẾN"] --> ELA["capabilities/eligibility.py<br/>DỰ KIẾN"]
    ELA --> ELS["services/recommendation/eligibility.py<br/>CẦN TÁCH CONTEXT"]

    GE["Candidate Generation<br/>generate_candidates<br/>DỰ KIẾN"] --> GEA["capabilities/generation.py<br/>DỰ KIẾN"]
    GEA --> GES["services/recommendation/candidate_generation.py<br/>Beam Search — CẦN TÁCH CONTEXT"]

    classDef existing fill:#ecfdf5,stroke:#15803d,color:#14532d;
    classDef adapt fill:#fffbeb,stroke:#b45309,color:#78350f;
    classDef planned fill:#eff6ff,stroke:#2563eb,color:#1e3a8a,stroke-dasharray:5 3;
    class SCS,KNS,KQ existing;
    class ELS,GES adapt;
    class SC,SCA,KN,KNA,KNL,EL,ELA,GE,GEA planned;
```

Student Context tạo hồ sơ tại học kỳ đích. Knowledge loader xác minh manifest/hash và chính sách nguồn. Eligibility trả trạng thái từng môn cùng evidence; Generation trả candidate/attempt trace, chưa kết luận validity. Eligibility và Generation phải nhận snapshot tường minh thay cho live context của engine.

## 2. Validator, Risk, Ranking và Grounded Explanation

```mermaid
flowchart LR
    VA["Standard Validation<br/>validate_candidate<br/>DỰ KIẾN"] --> VAA["capabilities/validation.py<br/>DỰ KIẾN"]
    VAA --> VAS["validation/validator.py<br/>StandardValidator.validate<br/>ĐÃ CÓ"]
    VAS --> VR["validation/rules/ và prerequisite_rule.py<br/>11 nhóm kiểm tra — ĐÃ CÓ"]
    VAS --> VE["services/ontology_evidence_service.py<br/>ĐÃ CÓ"]

    RI["Risk<br/>assess_plan_risk<br/>DỰ KIẾN"] --> RIA["capabilities/risk.py<br/>DỰ KIẾN"]
    RIA --> RIS["services/plan_risk_service.py<br/>Risk theo PDF v3 — DỰ KIẾN"]

    RA["Ranking / Diversity<br/>rank_valid_plans<br/>DỰ KIẾN"] --> RAA["capabilities/ranking.py<br/>DỰ KIẾN"]
    RAA --> RAS["services/plan_ranking_service.py<br/>6 feature và Jaccard — DỰ KIẾN"]

    EX["Grounded Explanation<br/>explain_plans"] --> EXA["capabilities/explanation.py"]
    EXA --> EXS["services/grounded_explanation_service.py<br/>Claim liên kết evidence"]

    classDef existing fill:#ecfdf5,stroke:#15803d,color:#14532d;
    classDef planned fill:#eff6ff,stroke:#2563eb,color:#1e3a8a,stroke-dasharray:5 3;
    class VAS,VR,VE existing;
    class VA,VAA,RI,RIA,RIS,RA,RAA,RAS,EX,EXA,EXS planned;
```

Validator độc lập, không gọi LLM/Agent/Generator; chỉ `valid` trên đúng candidate/snapshot được chuyển tiếp. Risk chạy trước Ranking vì Safety là feature. `services/recommendation/plan_risk.py` và `services/explanation_generator.py` hiện có là phiên bản cũ để tham khảo; chưa đáp ứng công thức Risk PDF v3 hoặc chuỗi claim → evidence mới.

## 3. Feedback, Re-planning và Confirm

```mermaid
flowchart LR
    FB["Feedback<br/>normalize_feedback / persist_feedback<br/>DỰ KIẾN"] --> FBA["capabilities/feedback.py<br/>DỰ KIẾN"]
    FBA --> FBS["services/feedback_service.py<br/>Chuẩn hóa và lưu phản hồi<br/>DỰ KIẾN"]

    RP["Re-planning / Confirm<br/>Nhánh replan / confirm<br/>DỰ KIẾN"] --> OR["agent/orchestrator.py<br/>State, budget, revision<br/>ĐÃ CÓ — KHUNG"]
    OR --> CT["Gọi lại các capability<br/>Generation → Validation → Risk<br/>→ Ranking → Explanation<br/>DỰ KIẾN"]
    OR --> FV["Refresh snapshots<br/>→ validate_candidate → Confirm<br/>DỰ KIẾN"]
    OR --> ST["services/agent_run_store.py<br/>Run, State và artifact<br/>DỰ KIẾN"]
    OR --> TR["agent/trace.py<br/>Tool calls và evidence refs<br/>DỰ KIẾN"]

    classDef existing fill:#ecfdf5,stroke:#15803d,color:#14532d;
    classDef planned fill:#eff6ff,stroke:#2563eb,color:#1e3a8a,stroke-dasharray:5 3;
    class OR existing;
    class FB,FBA,FBS,RP,CT,FV,ST,TR planned;
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
| Features và Ranking Result | `schemas/ranking.py` | Dự kiến |
| Feedback và adjustment | `schemas/feedback.py` | Dự kiến |

Mỗi tool phải có input/output schema, precondition, postcondition, xử lý lỗi và provenance. Quyết định học vụ lưu nguồn/version và evidence từ triple, query hoặc rule; explanation tham chiếu lại evidence. Bảng contract chi tiết nằm tại [đặc tả MVP, mục 3–5](DAC_TA_TRIEN_KHAI_MVP.md).

## 5. Phạm vi hoàn thành của tài liệu

**Đã hoàn thành sơ đồ mapping thiết kế để đưa vào báo cáo.** Source hiện có ontology, engine, schemas thành phần, StandardValidator, AgentState, feedback schema, trace, run store và khung Orchestrator; chưa có các adapter capability và luồng Agent tích hợp. API hiện tại vẫn gọi RecommendationEngine cũ.

Khi một capability được code: đối chiếu đường dẫn thực tế, cập nhật trạng thái node, bổ sung tên test và run/trace chứng minh đã tích hợp. Không đổi nhãn sang “đã có” chỉ vì tạo file rỗng.

Tham chiếu: [bảng mapping](DAC_TA_TRIEN_KHAI_MVP.md#2-mapping-capability--tool--module), [kế hoạch M0–M7](KE_HOACH_TRIEN_KHAI_AGENT_MVP.md), [cấu trúc engine hiện có](../backend/app/services/recommendation/README.md).
