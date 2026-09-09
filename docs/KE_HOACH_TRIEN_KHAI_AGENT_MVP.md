# Kế hoạch triển khai Agent MVP

Ngày lập: 2026-09-08. Kế hoạch dựa trên source hiện tại và [đặc tả MVP đã đối chiếu PDF v3](DAC_TA_TRIEN_KHAI_MVP.md). Các đường dẫn ghi “mới” là đầu ra dự kiến, chưa phải chức năng đã triển khai.

## 1. Mục tiêu và phạm vi

Hoàn thành một luồng có thể chạy lại và kiểm tra bằng evidence:

```text
Student Profile → Agent Orchestrator → Ontology/Eligibility
→ Candidate Generation → Standard Validator → Risk/Ranking
→ tối đa 3 valid plans → Grounded Explanation
→ Feedback → Adjustment → Re-planning → Validation lại
→ Final Validation trước Confirm
```

Mốc đầu tiên là một sinh viên ẩn danh và một CTĐT/học kỳ có đủ nguồn. Sau khi chạy xuyên suốt mới mở rộng bộ hồ sơ và giao diện. Không viết lại ontology/Validator/Beam Search từ đầu. Chưa triển khai LTR, RAG, chuyển database hoặc toàn bộ baseline trong đợt MVP này.

Tái sử dụng: StudentDataService, RDF/OWL và SPARQL, OntologyEvidenceService, các schemas đã có, StandardValidator và thuật toán Beam Search. Phần engine đang dùng mixin cần tách đầu vào snapshot tường minh; bọc nguyên engine mà vẫn lấy học kỳ/live context cũ chưa đáp ứng contract.

## 2. Các mốc và phụ thuộc

| Mốc | Công việc | Phụ thuộc | Bằng chứng hoàn thành |
|---|---|---|---|
| M0 | Chốt quyết định triển khai còn thiếu | Đặc tả PDF v3 | Cấu hình/rule đo lường có phiên bản và ví dụ tính tay |
| M1 | Schema tool, Agent State, trace và khung Orchestrator | Không chờ M0 hoàn tất mọi chi tiết Ranking | Chuyển bước, chặn invalid/error, lưu và đọc lại State |
| M2 | Loader Student/Knowledge và nguồn evidence | M1 | Snapshot thực có cutoff, manifest/hash và policy |
| M3 | Eligibility, Generation, adapter Validator | M1–M2 | Một lần chạy Agent + Ontology + Validator có trace |
| M4 | Risk, Ranking, diversity | M0 và M3 | Plan hợp lệ có sáu feature, score và kết quả chọn tái lập |
| M5 | Grounded explanation | M3–M4 | Claim và quyết định chọn/loại truy được nguồn |
| M6 | Feedback, Re-planning, Final Validation | M1–M5 | Điều chỉnh tạo vòng mới, kiểm định lại và xác nhận đúng phiên bản |
| M7 | API/UI, chạy thử và gói báo cáo | M3 trở đi; nghiệm thu sau M6 | Demo xuyên suốt và năm sản phẩm gửi cô |

Có thể xây schema/khung điều phối trong lúc hoàn thiện dữ liệu nguồn. Mỗi capability hoàn thành được nối ngay vào Orchestrator; không chờ viết xong tất cả module mới tích hợp. API thử nghiệm tối thiểu có thể bắt đầu ở M3, giao diện hoàn thiện ở M7.

## 3. M0 — Chốt các quyết định trước khi code Ranking

Giữ sáu feature, trọng số và min–max/diversity theo PDF v3. Không dùng JSON bảy feature cũ. Tạo cấu hình mới có version riêng trong `knowledge/rules/ranking_pdf3_v1.json` sau khi hoàn tất các mục sau:

| Điểm cần chốt | Công việc cụ thể |
|---|---|
| Goal Fit | Liệt kê tiêu chí `s_j`, nguồn, công thức, alpha và trường hợp không có preference. Phân biệt ưu tiên mềm với must-include/must-exclude |
| Workload/Safety | Xác định reference credits và mapping cảnh báo học vụ từ nguồn; xử lý thiếu nguồn, tổng alpha=0 và U=L một cách tường minh |
| Unlock | Xác định tập môn được đếm và cạnh dependency theo đúng PDF; không diễn đạt “đã đủ điều kiện học kỳ sau” chỉ từ điểm unlock |
| Ba nhãn phương án | Chốt cách chọn ba strategy thành kết quả hiển thị. PDF mới quy định duyệt score và diversity, chưa có thuật toán hợp nhất ba nhãn |
| Tie-break | Đề xuất: score giảm dần, rồi tuple mã môn đã sort, rồi plan ID/version; không dùng random/timestamp |
| Precision và version | Quy định làm tròn dùng để so sánh, hash pool, feature/risk/ranking version và cấu hình |

Đề xuất cho bước hợp nhất ba nhãn, cần ghi rõ là **bổ sung triển khai ngoài PDF**: duyệt slot Safe → Balanced → Accelerated; ở mỗi slot duyệt danh sách theo score của strategy đó, lấy plan đầu tiên đủ diversity với tập đã chọn. Không dùng lại course set; slot không có plan phù hợp để trống. Cách này dễ tái lập nhưng phụ thuộc thứ tự slot và không bảo đảm tìm được bộ ba dù bộ ba có thể tồn tại. Nếu chọn cách khác, chốt trước M4 và lưu selection policy/version; không quay lại assignment cũ một cách ngầm định.

**Nghiệm thu:** một ví dụ pool nhỏ được tính tay gồm feature, score của ba strategy và quyết định diversity; mỗi điểm chưa có trong PDF được đánh dấu bổ sung. Cấu hình mới phải khớp Markdown và không được mô tả là đã hiệu chỉnh thực nghiệm.

## 4. M1 — Schema và Agent Orchestrator tối thiểu

Tái sử dụng `PlanningRequest`, `StudentSnapshot`, `KnowledgeSnapshot`, `KnowledgeVersion`, `CandidatePlan`, `ValidationResult`, `EvidenceRecord`.

Tạo mới theo từng nhu cầu, không nhân đôi schema đang có:

- `schemas/capability.py`: ToolCallContext, ToolResult, ToolError, Provenance.
- `schemas/agent_state.py`: AgentState, run status, budget, iteration và state revision.
- `schemas/feedback.py`: FeedbackRequest, AdjustmentRequest, FeedbackReceipt; hoàn thiện hành vi ở M6.
- `agent/orchestrator.py`: luồng chuyển trạng thái và các cổng kiểm tra.
- `agent/trace.py`: sự kiện tool-call và tham chiếu output/evidence.
- `services/agent_run_store.py`: lưu/đọc run, revision và artifact bằng kho file dành riêng cho Agent.

State tối thiểu chứa request, snapshots, CourseSpace, attempts/candidates, validations, risk, ranking, explanations, feedback/adjustments, trace, errors, selected plan và final result. Artifact lớn có thể lưu riêng bằng reference/hash; State vẫn phải giải được tham chiếu.

Luồng trạng thái đích:

```text
RECEIVED → LOADING_CONTEXT → BUILDING_COURSE_SPACE → GENERATING
→ VALIDATING → ASSESSING_RISK → RANKING → EXPLAINING
→ AWAITING_FEEDBACK → REPLANNING hoặc FINAL_VALIDATING → CONFIRMED

Nhánh dừng: NEEDS_DATA / NO_PLAN_FOUND / FAILED
```

Tool chỉ nhận input cần thiết và trả output, không sửa toàn State. Orchestrator kiểm tra schema, postcondition, hash/version trước khi chuyển bước. Validator là module độc lập bên dưới, không import ngược Agent.

Dùng ngân sách đề xuất trong đặc tả: tối đa 3 generation rounds, 60 candidate attempts, 5.000 expanded states, 120 giây xử lý chủ động; seed=42. Thời gian chờ feedback không tiêu budget xử lý. Ghi cả attempt trùng và lý do dừng; timeout không có nghĩa bài toán vô nghiệm. Kiểm soát output đến muộn và chỉ retry thao tác có thể lặp an toàn.

**Nghiệm thu:** test bằng tool giả có hợp đồng chứng minh đúng thứ tự, invalid/error không tới Ranking, timeout dừng đúng, State lưu/đọc lại được và run khác không dùng chung dữ liệu. Tool giả chỉ phục vụ test, chưa tính là demo MVP.

## 5. M2 — Snapshot thực và nguồn Ontology Evidence

Tạo mới `capabilities/student_context.py`, `capabilities/knowledge.py` và `services/knowledge_context_loader.py`; bọc StudentDataService/OntologyEvidenceService hiện có.

Việc cần làm:

1. Chọn một hồ sơ ẩn danh, CTĐT, chuyên ngành và học kỳ đích làm ca chạy đầu.
2. Chuẩn hóa mã môn, ngành/chuyên ngành sang định danh phù hợp; tính completed/failed tại thời điểm trước học kỳ đích. Không dùng kết quả học tương lai.
3. Lập manifest nguồn CTĐT, lịch học, ontology, offering, prerequisite/corequisite/prior-study, quota và credit policy. Ghi version, hash nội dung, hiệu lực và tính đầy đủ.
4. Kiểm kê ngoại lệ trong `recommendation/constants.py`; xác định mục nào là policy, dữ liệu điều chỉnh hoặc normalization. Không gắn nguồn “ontology” cho ngoại lệ Python.
5. Gắn academic warnings với hạn mức đúng policy; không dùng default 0/27 của Validator thay cho quy định nguồn.
6. Lấy đủ metadata cho sáu feature Ranking: môn bắt buộc còn lại, dependency, mục tiêu, tín chỉ, tải tham chiếu và mapping academic risk.

Kết quả ontology giữ query ID/text/hash, bindings, kết quả/triples, source_ref và ontology version. Quan hệ rỗng chỉ được coi là không có yêu cầu nếu nguồn đã được xác nhận đầy đủ; dữ liệu thiếu trả chẩn đoán, không tự bù.

**Nghiệm thu:** cùng nguồn tạo cùng hash nội dung; đổi nguồn làm đổi version/hash; snapshot loại lịch sử sau cutoff; thiếu/mâu thuẫn policy không được trả context đủ điều kiện để planning. Có ít nhất một query thật và evidence thật trên ontology dự án.

## 6. M3 — Eligibility → Generation → Standard Validator

### Eligibility

Tạo `capabilities/eligibility.py`, tái sử dụng logic có kiểm tra từ `services/recommendation/eligibility.py`. Tách context khỏi live engine và ghi DecisionRecord cho từng môn trong phạm vi curriculum:

- eligible: đủ điều kiện cấp môn;
- conditional: cần bundle song hành khi sinh tổ hợp;
- ineligible: có vi phạm đã được chứng minh;
- unknown: dữ kiện chưa đủ, không chuyển thành eligible.

Quota/tổng tín chỉ của tổ hợp phải được kiểm tra lại trên candidate; không biến một giới hạn tổ hợp thành kết luận sai về mọi môn.

### Candidate Generation

Tạo `capabilities/generation.py`, tái sử dụng thuật toán trong `candidate_generation.py`. Bổ sung đầu vào snapshots, request, adjustment, seed/budget và cách trả pool candidates/attempts thay vì chỉ lấy phương án cuối. Mỗi candidate lưu ID/version, source versions và course set; generator không chứng nhận valid.

Sort đầu vào và dùng RNG riêng từng run. Giữ bundle song hành, must-include/must-exclude; ghi expanded states, attempts, duplicate/stop reasons. Giữ đường gọi engine cũ để chạy baseline/hồi quy, không sửa ngầm thuật toán baseline.

### Validator

Tạo `capabilities/validation.py`, bọc `StandardValidator.validate`; truyền đúng plan, snapshots và credit policy. Chỉ output `valid` trên đúng hash/config đi tiếp. Giữ toàn bộ invalid/error/pending và evidence để giải thích, điều chỉnh search và thống kê.

**Nghiệm thu M3:** chạy từ request của một sinh viên qua Orchestrator, loader, eligibility, generation và Validator thật. Trace có ít nhất một plan valid khi nguồn/bài toán cho phép; có ca đối chứng vi phạm được Validator phát hiện. Không dùng fixture giả để thay hồ sơ/nguồn thực trong minh chứng này.

Tạo `scripts/run_agent_demo.py` ở mốc này để xuất request, snapshots, trace, candidates và validations ra thư mục run riêng. Đây là **lần chạy thử đầu Agent + Ontology + Validator** để báo cô, chưa phải hoàn tất Top-3/feedback.

## 7. M4 — Risk, Ranking và diversity

Tạo mới `schemas/ranking.py`, `services/plan_risk_service.py`, `services/plan_ranking_service.py`, `capabilities/risk.py`, `capabilities/ranking.py`.

1. Tính Risk theo PDF: load, tỷ lệ số môn học lại/cải thiện và academic status; `Safety=1-Risk`. Risk cũ theo heuristic độ khó không tự được coi tương đương công thức mới.
2. Tính sáu feature; lưu raw, normalized, source/evidence, công thức/version và contribution.
3. Mandatory/Unlock dùng min–max trên pool valid của request; max=min thì gán 1. Pool đổi phải tính lại; không lấy feature cũ của pool khác.
4. Chấm theo ba weight vectors đã chốt; áp dụng selection policy M0 và Jaccard >=0.30 giữa mọi cặp được chọn.
5. Trả selected plans, strategy labels, recommended plan theo quy ước M0, selection trace và shortfall reason.

**Nghiệm thu:** khớp ví dụ tính tay; không nhận stale/invalid/partial/error; 0/1/2/3 plan xử lý đúng; không trùng course set; mọi cặp hiển thị đạt diversity; thay thứ tự input không đổi kết quả theo tie-break đã chốt. Không khẳng định greedy chọn được bộ ba tối ưu.

## 8. M5 — Grounded Explanation

Tạo `services/grounded_explanation_service.py`, `capabilities/explanation.py` và schema claims/decisions. Dùng template tiếng Việt từ dữ liệu đã tính cho MVP; chưa cần LLM để tạo lời giải thích.

Phải phân biệt lý do: không đủ điều kiện, cần song hành, chưa biết vì thiếu dữ liệu, nằm trong plan invalid, không được search tới, điểm thấp hoặc xung đột diversity. Một môn hợp lệ không được chọn không đồng nghĩa vi phạm học vụ.

Mỗi claim có `claim_id`, text, decision IDs và evidence IDs; chuỗi truy vết là:

```text
Claim → Decision → Validation rule hoặc Ranking contribution
→ Query/Rule inputs và kết quả → Source + Version
```

Evidence bao phủ quyết định đạt và không đạt. Không bịa triple để biểu diễn kết quả query rỗng, không gán quyết định ranking thành luật ontology. Nếu thiếu căn cứ cho giải thích bắt buộc, trả lỗi/thiếu dữ kiện; không trình bày lời giải thích không truy vết được.

**Nghiệm thu:** mọi tham chiếu giải được trên cùng phiên bản; câu giải thích đúng ý nghĩa evidence, không chỉ có ID hợp lệ. Có kiểm tra thủ công một plan được chọn, một môn bị loại vì học vụ và một plan không được chọn vì ranking/diversity.

## 9. M6 — Feedback, Re-planning và Confirm

Tạo `capabilities/feedback.py`, `services/feedback_service.py`; hoàn thiện store và Orchestrator của M1.

Các thao tác: select, rank A/B/C, Add/Remove/Replace, đổi tín chỉ mục tiêu, đổi goal và confirm. Modify tạo AdjustmentRequest; include/exclude phải nhất quán. Select/rank không tự kích hoạt generation nếu người dùng chưa yêu cầu sửa.

Phản hồi gắn run_id, displayed result hash, actor role, plan IDs, features, strategy/config/knowledge versions và thứ tự hiển thị. Lưu bằng idempotency key; cùng khóa/cùng payload không ghi trùng, cùng khóa/khác payload trả conflict. Phân biệt preference cố vấn và sinh viên để dùng cho nghiên cứu sau này.

Re-planning tăng revision/iteration, giữ parent trace, áp adjustment rồi chạy lại generation → validation → risk → ranking → explanation. Kiểm tra adjustment đã được đáp ứng ngoài việc plan đạt hard constraints. Snapshot thay đổi thì tải lại context và vô hiệu hóa kết quả phụ thuộc. Giới hạn số lần modify theo đặc tả; không lặp vô hạn.

Confirm phải làm mới nguồn, Final Validation rồi mới ghi. Nếu nguồn thay đổi, tính lại và yêu cầu chọn lại trên kết quả mới. Cần revision/lock cùng cơ chế ghi của các nguồn liên quan; không chỉ check hash một lần rồi ghi không kiểm soát. Trên MVP JSON, mọi writer liên quan phải tuân thủ khóa chung.

**Nghiệm thu:** Remove có hiệu lực ở vòng sau; yêu cầu thêm môn không đủ điều kiện trả chẩn đoán đúng; stale feedback không sửa run; gửi lại không tạo duplicate; restart vẫn đọc và tiếp tục được run đang chờ feedback; race giữa đổi nguồn và confirm không xác nhận plan cũ.

## 10. M7 — Tích hợp API/UI và chuẩn bị báo cáo

Tạo `routes/agent_routes.py`, đăng ký tại app; endpoint đề xuất:

| Endpoint | Vai trò |
|---|---|
| `POST /api/agent/runs` | Nhận PlanningRequest, tạo run và chạy tới kết quả hoặc trạng thái dừng |
| `GET /api/agent/runs/<run_id>` | Lấy state tóm tắt, plans và explanations theo quyền |
| `POST /api/agent/runs/<run_id>/feedback` | Nhận feedback, có thể kích hoạt re-planning |
| `POST /api/agent/runs/<run_id>/confirm` | Final Validation và xác nhận revision được chọn |

Đây là đề xuất API, cần đồng bộ contract trước triển khai. Kiểm tra quyền sinh viên/cố vấn trên từng run/artifact; ID khó đoán không thay thế phân quyền. Chọn cách thực thi đồng bộ hay worker theo latency đo ở M3; không thêm hạ tầng queue trước khi có nhu cầu đã đo.

Tái sử dụng trang plan và màn hình cố vấn. UI hiển thị môn/tín chỉ, nhãn strategy, giải thích có căn cứ, lý do thiếu phương án và thao tác chỉnh sửa. Chi tiết query/hash ở phần xem căn cứ dành cho kiểm tra, không lấn át luồng chính. Mọi đường tạo/xác nhận plan trong luồng Agent phải qua cùng Validator, gồm cả thao tác chỉnh sửa của cố vấn; không rơi về `_validate_advisor_plan` cũ khi lỗi.

Chạy lại tests hồi quy phù hợp và kiểm thử tích hợp mới. Không lấy con số 127 tests của lần kiểm tra trước thay cho kết quả sau thay đổi.

**Nghiệm thu:** một người dùng được phân quyền chạy từ profile tới feedback/re-planning trên giao diện/API; plan đề xuất nào cũng có validation cùng nội dung/phiên bản. API và CLI dùng cùng Orchestrator, không duy trì hai bộ luật.

## 11. Bộ ca nghiệm thu tối thiểu

| Ca | Kỳ vọng |
|---|---|
| Hồ sơ đủ dữ liệu, có nhiều lựa chọn | Tới Ranking/Explanation; mọi plan hợp lệ, có trace và diversity |
| Không đủ ba plan | Trả số có thể chọn theo policy, kèm lý do; không sao chép plan |
| Thiếu prerequisite/quota/offering policy | NEEDS_DATA/error có nguồn chẩn đoán; không công bố plan chưa kiểm định |
| Candidate sai tiên quyết, song hành, tín chỉ hoặc quota | Validator phát hiện theo rule/evidence; giữ attempt để thống kê |
| Môn tiên quyết chỉ nằm trong cùng plan | Không được coi là đã hoàn thành tiên quyết |
| Đổi thứ tự input hoặc chạy process mới với cùng snapshot/seed/config | Kết luận, score, selection và định danh ngữ nghĩa tái lập theo quy ước hash |
| Sửa pool hoặc snapshot | Invalidate và tính lại các kết quả phụ thuộc |
| Remove/Add/Replace hoặc đổi goal | Adjustment có hiệu lực hoặc trả conflict/không tìm được phương án rõ ràng |
| Feedback lặp/cũ, confirm khi dữ liệu vừa thay | Không ghi trùng, không áp revision cũ, không xác nhận plan stale |
| Tool timeout/lỗi, hết search budget | Dừng có cấu trúc; không giả thành valid/vô nghiệm |

Dùng fixture nhỏ cho rule/contract tests và hồ sơ ẩn danh có nguồn thật cho demo end-to-end. Những ca không có đủ căn cứ nguồn được báo thiếu dữ liệu, không sửa fixture chính sách chỉ để tạo kết quả đẹp.

## 12. Gói đầu ra gửi người hướng dẫn

Mỗi demo run lưu request, manifest/snapshot hashes, generation attempts, validation results, ranking features/contributions, selected plans/diversity, claim/evidence, feedback và parent-child trace. Tạo command tái chạy bằng run config; dữ liệu nghiên cứu được ẩn danh.

Năm sản phẩm gửi cô:

1. Cây source hiện tại, phân biệt phần tái sử dụng và module mới.
2. Mapping capability → tool/module thật, contract và tests tương ứng.
3. Agent State JSON Schema cùng một state instance.
4. Một trace thật của sinh viên qua lần lập kế hoạch đầu và ít nhất một lần re-planning.
5. Báo cáo chạy thử: số requests/attempts/valid/invalid/error, nguyên nhân vi phạm, số plan hiển thị, diversity, evidence coverage và thời gian từng bước.

Valid-plan rate tính trên candidate attempts trước lọc, nêu rõ mẫu số. Tỷ lệ plan đã hiển thị hợp lệ được báo riêng. Không khẳng định mức trust/acceptance tăng hoặc LTR hiệu quả chỉ từ demo/tests; các kết luận này cần khảo sát/thực nghiệm sau khi MVP ổn định.

## 13. Thứ tự bắt đầu trong đợt code đầu tiên

1. Chốt phạm vi một sinh viên/CTĐT/học kỳ và kiểm kê nguồn; xác định rõ dữ kiện còn thiếu.
2. Viết schema envelope/trace/State và khung Orchestrator.
3. Nối Student/Knowledge loader cùng Evidence service.
4. Bọc Eligibility/Generation và StandardValidator.
5. Chạy `run_agent_demo.py`, xuất lần trace đầu tiên tới Validator.

Hoàn thành năm việc này tạo ra mốc M3 có thể báo cáo sớm. Tiếp tục M4–M7 để hoàn thành toàn bộ luồng MVP, đồng thời giữ LTR và thực nghiệm so sánh đầy đủ cho giai đoạn sau.
