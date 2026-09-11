# Đối chiếu dự án với nhận xét người hướng dẫn

Ngày kiểm tra: 2026-09-08. Đối chiếu working tree hiện tại, bao gồm tài liệu chưa commit, với nội dung nhận xét người hướng dẫn do người dùng cung cấp. Đây là báo cáo kiểm tra, không phải xác nhận của người hướng dẫn và không thay đổi đặc tả đang có.

Đã đọc nội dung văn bản PDF v3 (45 trang), sáu Markdown hiện có trong `docs`, cấu hình Ranking đề xuất, hai ảnh kiến trúc/State trong `docs/assets`, README liên quan, mã nguồn các module chính, routes, schemas, validator/evidence và mã thực nghiệm. PDF được trích bằng pypdf; công thức được đối chiếu với văn bản/đặc tả, không coi thứ tự ký tự trích xuất của biểu thức toán là bản trình bày chuẩn.

## 1. Kết luận về tiến độ

Dự án đã có nền tảng triển khai đáng kể: ứng dụng Flask, dữ liệu hồ sơ, ontology, engine Beam Search, schemas thành phần, OntologyEvidenceService và StandardValidator độc lập. Tài liệu đã bổ sung mapping capability, tool contract và Ranking chi tiết.

MVP Agent theo yêu cầu của cô **chưa hoàn thành**. Luồng API hiện vẫn dùng engine cũ; Orchestrator chưa được code, Validator mới chưa được nối vào API, Ranking/diversity mới chưa chạy và chưa có vòng Feedback → Adjustment → Re-planning với trace đầy đủ.

Mốc phù hợp để mô tả hiện tại: **đã có thiết kế triển khai và các module nền; đang chuẩn bị tích hợp MVP Agent**. Không nên gọi màn hình so sánh ba kết quả hiện có là Top-3 valid plans của Agent.

## 2. Đối chiếu từng yêu cầu

| Yêu cầu của cô | Bằng chứng hiện có | Kết luận và việc còn thiếu |
|---|---|---|
| Cấu trúc source code mới | `backend/app`, `backend/tests`, `knowledge`, `experiments`, `docs`; engine được tách thành các mixin | Đã thực hiện tổ chức source. Các mixin còn dùng chung context, chưa phải capability độc lập |
| Agent Orchestrator | `backend/app/agent/__init__.py` chỉ chứa docstring “planned MVP implementation” | Chưa có Orchestrator, state transitions, budget và tool-call trace |
| Đóng gói ontology/SPARQL, eligibility, generation, validator, ranking, re-planning, explanation | Bảng mapping tại mục 2 của `DAC_TA_TRIEN_KHAI_MVP.md`; code nghiệp vụ một phần đã có | Mapping đã thiết kế; chưa có package `capabilities` và adapter thực thi contract |
| Input/output schema, pre/postcondition, lỗi và provenance từng tool | Mục 3–4 đặc tả MVP có schema trường, envelope, timeout, retry và provenance | Đã đáp ứng ở mức tài liệu; chưa có đầy đủ schema/code/runtime enforcement của tool |
| Schema Agent State | Mục 4 của thiết kế và mục 3 của đặc tả mô tả State; Pydantic có request, snapshot, candidate, evidence, validation | Có schemas thành phần; chưa có `AgentState`, `AdjustmentRequest`, `ToolResult`, feedback/ranking schemas triển khai |
| Standard Validator độc lập, deterministic, không LLM | `backend/app/validation/validator.py`, 11 REQUIRED_RULES; tests kiểm tra kết luận và evidence lặp lại | Có module thực tế, không gọi Agent/Flask/LLM/Generator. Chưa tích hợp vào các luồng trả/xác nhận kế hoạch; cần loader chính sách nguồn và kiểm chứng tái lập qua process |
| Ontology Evidence | `ontology_evidence_service.py`, sáu `.rq`, schemas evidence, rule conclusions | Có RDF snapshot riêng, hash ontology/query, query text, triple, rule inputs và version. Chưa bao phủ mọi quyết định eligibility/generation/ranking và claim explanation trong luồng người dùng |
| Công thức, feature, normalization, weights, diversity | PDF v3 trang 15–30; đặc tả MVP mục 6; `ranking_v1.proposed.json` | Đã bổ sung nội dung, nhưng PDF và Markdown khác thuật toán. Chưa code Ranking mới; tham số chưa hiệu chỉnh thực nghiệm |
| Top-3 valid plans | API compare gọi engine ba lần, lần sau đổi seed | Có so sánh ba kết quả cũ; chưa có cổng StandardValidator, điểm theo ba profile và kiểm tra Jaccard |
| Grounded explanation | `explanation_generator.py` tạo văn bản từ RecommendationResult | Có lời giải thích/tóm tắt; chưa có claim → decision → evidence → rule/query → version |
| Feedback và Re-planning | Student feedback lưu rating/comment; advisor routes có đánh giá, chỉnh sửa/xác nhận và audit | Có nghiệp vụ phản hồi một phần; chưa thành feedback contract gắn displayed plans/features/version và vòng điều phối Agent |
| Hoãn LTR tới khi đủ dữ liệu preference | Đặc tả ghi rõ chưa huấn luyện LTR; chưa thấy module LTR trong source khảo sát | Đúng thứ tự ưu tiên. Cần chuẩn hóa dữ liệu thu thập, chưa triển khai huấn luyện |
| Sáu baseline và ba đóng góp cần chứng minh | Thiết kế giữ BL-01 đến BL-06 và explanation ablation; experiments có ba phương pháp cũ | Có nền BL-01/02/03. Chưa có kết quả BL-04/05/06 đáp ứng protocol mới; hậu kiểm cũ chưa dùng StandardValidator |
| Trace end-to-end và chạy thử Agent + Ontology + Validator | Có tests module và API engine cũ; ví dụ Ranking chỉ là vector số học | Chưa có trace thật của luồng Agent mà cô yêu cầu |

## 3. Những chỗ cần thống nhất trước khi code tiếp

### 3.1. PDF v3 và đặc tả MVP có hai thiết kế Ranking

| Thành phần | PDF v3 | Markdown/JSON triển khai đề xuất |
|---|---|---|
| Tập feature | 6: goal, mandatory, unlock, credit fit, workload balance, safety | 7: debt, required, unlock, goal, credit fit, preference, safety |
| Mandatory/required | Min–max tín chỉ bắt buộc trong pool valid; trường hợp bằng nhau gán 1 (trang 17–18, 24) | Tỷ lệ tín chỉ nghĩa vụ bắt buộc còn lại được phủ; không phụ thuộc pool (mục 6.2) |
| Unlock | Định nghĩa giải quyết ít nhất một dependency, chuẩn hóa theo pool (trang 18–19) | Chỉ đếm môn mới thỏa toàn bộ tiên quyết nếu hoàn thành plan, chia tập môn đang bị chặn (mục 6.1–6.2) |
| Credit fit | Mẫu số max(target − min, max − target, 1), trang 20 | Mẫu số max(target, U − L), mục 6.2 |
| Risk | 0.4 load + 0.3 retake + 0.3 academic status, trang 22–23 | 0.5 load + 0.3 GPA pressure + 0.2 retake credit share, mục 6.3 |
| Trọng số profile | Bảng sáu feature trang 25 | Bảng bảy feature mục 6.4 và JSON; ba vector đều có tổng 1 |
| Chọn Top-3 | Duyệt giảm dần theo score, nhận plan nếu đủ diversity với tập đã chọn, trang 29 | Xét assignment cho Safe/Balanced/Accelerated; ưu tiên số slot, tổng score, diversity và tie-break, mục 6.5 |
| Ngưỡng diversity | D = 1 − Jaccard, ngưỡng khởi tạo 0.30 | Cùng ngưỡng khởi tạo 0.30 |

Đây là khác biệt về cách tính và ý nghĩa kết quả, không chỉ khác cách trình bày. Không thể lấy feature từ PDF, weights từ JSON và thuật toán chọn từ nguồn khác rồi coi là cùng một phiên bản.

Đề xuất: dùng `DAC_TA_TRIEN_KHAI_MVP.md` cùng `ranking_v1.proposed.json` làm bản chuẩn triển khai **nếu tiếp tục lựa chọn đã nêu trong Markdown**, ghi rõ nó thay thế những mục nào của PDF. Cập nhật PDF hoặc thêm phụ lục đối chiếu trước lần báo cáo tới. Đây là đề xuất của lần kiểm tra, chưa tự sửa/chọn thay người dùng. Các tham số vẫn là khởi tạo chưa kiểm chứng.

Ảnh `assets/kien-truc-ai-agent.png` đặt Risk sau Ranking/Top-3; đặc tả mới cần Risk trước Ranking vì safety là feature. Cần cập nhật hình để khớp luồng triển khai. PDF mục 4.3 còn câu capability cập nhật phần State của mình, trong khi contract quy định chỉ Orchestrator cập nhật State; nên thống nhất câu chữ. Sơ đồ State có đường từ CONFIRMED quay lại planning cần sửa hoặc chú thích rõ trạng thái kết thúc.

### 3.2. Các đường dẫn và mô tả tiến độ chưa đồng bộ

- Đầu các Markdown vẫn liên kết tới tên PDF không có hậu tố `_v3`, trong khi file hiện có là PDF v3.
- `LO_TRINH_MVP.md` giữ đoạn lịch sử “schemas và validation mới có khung package”, dù phía sau đã cập nhật Validator v3. Khi báo cáo cần dùng trạng thái hiện tại, không trích riêng đoạn lịch sử.
- `knowledge/queries/README.md` còn ghi rule `integrity-prerequisite-v2`; source `prerequisite_rule.py` dùng `academic-constraints-v3`.
- `CLAUDE.md` nói queries chưa được tách, nhưng đã có sáu `.rq`; cũng có mô tả prior-study và prerequisite không khớp rule hiện hành. Ưu tiên source và tests khi xác định hành vi thực tế.
- `benchmark_results/test_report.md` là mốc 59 tests, Python 3.13.10 và đường dẫn `tests/...` cũ; không phải báo cáo kiểm thử mới nhất.

### 3.3. Validator có sẵn nhưng chưa bảo vệ đầu ra API

`recommendation_routes.py::get_recommendation` gọi engine, sinh explanation và trả payload trực tiếp. Chế độ compare lặp ba lần, dùng `priority_mode="standard"`; tên phương án là “Tối ưu chuẩn” và “Thay thế tự chọn”. Không có lời gọi StandardValidator, Ranking mới hoặc kiểm tra diversity.

`advisor_role_routes.py::_validate_advisor_plan` gọi engine để lấy eligible codes rồi kiểm tra danh mục/tín chỉ. Đây chưa phải Final Validation bằng StandardValidator trên snapshot hiện hành.

Engine còn tính học kỳ đích từ current_semester + 1 và parity; contract mới cần target_term_id và lịch học có phiên bản. Adapter không thể chỉ chuyển kiểu output mà giữ nguyên tất cả giả định về nguồn/học kỳ.

### 3.4. Nguồn chính sách là phần còn thiếu trước tích hợp dữ liệu thực

KnowledgeSnapshot chứa tham chiếu và chính sách do caller cung cấp; chưa có loader xác minh artifact và tính đầy đủ. StandardValidator mặc định min/max là 0/27; adapter phải truyền đúng credit policy của sinh viên/học kỳ, gồm tác động của cảnh báo học vụ nếu có quy định nguồn.

Cần chuẩn bị manifest cho curriculum, prior-study, elective quotas, offering, credit policy, lịch học và metadata Ranking. Gắn hash/phiên bản/nguồn cho các dữ kiện; không điền chính sách rỗng hoặc completeness=true chỉ để tests/validator đi qua.

Ngoại lệ tiếng Anh, tương đương môn và các nhóm môn đặc thù còn ở `recommendation/constants.py`. Cần kiểm kê, phân biệt rule/normalization từ nguồn với ontology fact. Validator và engine cũ có thể khác kết quả nếu dùng catalog thuần và catalog đã được điều chỉnh khác nhau.

### 3.5. Hậu kiểm thực nghiệm cũ không tương đương StandardValidator

`experiments/experimental_evaluation.py::violations` kiểm tra prerequisite bằng `passed | codes`: môn tiên quyết nằm trong cùng plan có thể được tính là thỏa. StandardValidator yêu cầu tiên quyết đã hoàn thành trong lịch sử; test `test_same_plan_prerequisite_is_not_completed` kiểm tra chính khác biệt này.

Hàm hậu kiểm cũ cũng không thực hiện đầy đủ 11 rule. `explanation_rate_pct` chỉ đo môn có trường reasons, không chứng minh claim có evidence hợp lệ hoặc cố vấn tin tưởng/chấp nhận hơn.

Cần chuyển evaluator sang StandardValidator và đóng băng cùng snapshots/config trước so sánh chính thức. Tỷ lệ valid của các output đã lọc không tự chứng minh ontology giúp generator tốt hơn; phải lưu candidate attempts trước lọc. Ablation bỏ riêng một nhóm quan hệ trong engine cũ chưa phải BL-04 Agent không Ontology.

## 4. Kết quả kiểm chứng trong lần đọc này

- Python thực thi tests: `C:\Users\tandd\AppData\Local\Python\pythoncore-3.14-64\python.exe`; pytest 8.3.5.
- Lần đầu: 77 passed, 50 setup errors do không truy cập được thư mục tạm `pytest-of-tandd` của Windows.
- Sau khi đặt basetemp mới trong workspace: **127 passed in 27.52s**, exit code 0. Không sửa code để làm tests đạt.
- `.venv` đọc PDF được nhưng chưa có pytest; alias `python` mặc định trỏ WindowsApps và không chạy được trong phiên này. Vì vậy lệnh dưới dùng đường dẫn interpreter đã kiểm chứng.

Lệnh tái chạy, dùng thư mục mới mỗi lần:

```powershell
$reviewTemp = Join-Path (Get-Location).Path ('.test-tmp\review-' + [guid]::NewGuid().ToString('N'))
& 'C:\Users\tandd\AppData\Local\Python\pythoncore-3.14-64\python.exe' -m pytest -o addopts='' -q --tb=short --basetemp $reviewTemp
```

Tests evidence/validator dùng ontology và snapshot fixture. API integration kiểm tra engine và dữ liệu hiện có; chưa kiểm tra Agent + Ontology + StandardValidator tích hợp. Kết quả 127 tests không chứng minh hiệu quả khoa học, không chứng minh mọi chính sách thực tế đã được mô hình hóa đầy đủ và không thay thế trace end-to-end.

## 5. Thứ tự công việc để hoàn thành yêu cầu cô

### Mốc A — Thống nhất đặc tả và khởi tạo điều phối

Chọn một phiên bản Ranking; đồng bộ PDF/Markdown/JSON, sơ đồ Risk và quyền cập nhật State. Giữ nguyên nguyên tắc chỉ valid được hiển thị và không nới luật để đủ ba phương án.

Triển khai `AgentState`, `ToolCallContext`, `ToolResult`, `ToolError`, provenance/trace và `AdjustmentRequest`; tạo Orchestrator quản lý chuyển bước, budget, error và invalidation. Có thể khởi đầu bằng Python có kiểu dữ liệu và nhánh điều phối rõ; contract hiện không bắt buộc mọi tool là HTTP/MCP hay gọi LLM.

Đầu ra: State schema xuất được JSON Schema, mapping trỏ được tới tool/module thật, một test điều phối chứng minh invalid/error không đi vào Ranking.

### Mốc B — Nối Student → Ontology → Candidate → Validator

Triển khai loader StudentSnapshot tại học kỳ đích và KnowledgeContext với source manifest. Chọn một hồ sơ ẩn danh và một phạm vi CTĐT đủ nguồn làm ca đầu tiên; không cần hoàn thiện toàn bộ dữ liệu ngay, nhưng dữ kiện được sử dụng phải đầy đủ và có căn cứ.

Bọc Evidence, Eligibility và Generation thành capability, tách context khỏi live engine; tạo DecisionRecord cho eligible/conditional/ineligible/unknown. Generator trả candidate và attempt trace, không gắn nhãn valid. Gọi StandardValidator trên từng candidate với đúng policy, lưu cả kết quả bị loại/lỗi.

Đầu ra: lần chạy đầu Agent + Ontology + Validator có input, snapshot hashes, tool calls, checked/pending rules, evidence và output tái kiểm tra được. Nếu nguồn chưa đủ thì báo thiếu dữ kiện, chưa gọi đó là luồng thành công.

### Mốc C — Risk, Ranking và Top-3

Code feature/risk service theo phiên bản đã chọn. Lưu raw/normalized feature, contribution, weights/config/hash; chỉ nhận kết quả Validation còn hiệu lực trên đúng nội dung candidate/snapshot.

Chọn tối đa ba plan khác nhau, ngưỡng Jaccard theo cấu hình; xử lý rõ 0/1/2 plan và diversity conflict. Nếu dùng assignment theo Markdown, A/B/C là slot profile, cần recommended_plan_id riêng để đo Top-1 agreement.

Đầu ra: bảng score có thể tính lại, mọi plan hiển thị valid, mọi cặp đạt diversity, không tạo bản sao khác nhãn để đủ ba.

### Mốc D — Grounded explanation và vòng phản hồi

Dùng template từ evidence có cấu trúc cho MVP. Mỗi claim học vụ trỏ tới evidence; lý do không chọn do ranking/diversity/budget phải phân biệt với vi phạm học vụ. Evidence cần có cả quyết định đạt và không đạt.

Chuẩn hóa select/rank/modify/confirm; Add/Remove/Replace tạo adjustment tường minh. Lưu feedback cùng plan/features/version/thứ tự hiển thị, idempotency và actor role. Re-planning gọi lại generator/validator/risk/ranking/explanation; kiểm tra adjustment đã được đáp ứng. Khi confirm, làm mới nguồn và Final Validation, kiểm soát revision khi ghi.

Đầu ra: cùng một sinh viên chạy trọn Student Profile → Agent → Ontology → tối đa ba valid plans → Explanation → Feedback → Re-planning, có lineage giữa các vòng.

### Mốc E — Gói báo cáo và thực nghiệm theo giai đoạn

Gửi cô đúng năm nhóm đầu ra ở mục 6. Sau khi luồng ổn định, chuyển baseline cũ sang evaluator chung; thêm BL-04/BL-05 cùng ngân sách và input theo phạm vi tri thức quy định. Không trả Ontology Validator feedback cho BL-04 trong generation/ranking.

Đánh giá explanation trên cùng candidates/validation/ranking, thu trust/acceptance từ cố vấn. Giữ BL-06 trong kế hoạch; chỉ huấn luyện LTR sau khi có preference dataset đủ chất lượng và chia train/validation/test theo sinh viên. Chưa ưu tiên PostgreSQL, RAG hoặc huấn luyện LTR trước luồng MVP.

## 6. Năm sản phẩm cho lần báo cáo tiếp theo

| Sản phẩm cô yêu cầu | Có thể dùng ngay | Phải bổ sung |
|---|---|---|
| Cấu trúc source code mới | Cây thư mục hiện tại và README module | Cập nhật module Agent/capability sau triển khai, phân biệt hiện có/dự kiến |
| Mapping capability → module/tool | Mục 2 đặc tả MVP | Đường dẫn/tool thật, trạng thái implementation và test tương ứng |
| Schema Agent State | Mô hình State trong thiết kế | Pydantic/JSON Schema chạy được và một state instance hợp lệ |
| Trace end-to-end một sinh viên | Chưa có trace Agent hoàn chỉnh | Hồ sơ ẩn danh, request, snapshots, calls, candidates, Validation, Ranking/diversity, claim/evidence, feedback và vòng mới |
| Kết quả chạy thử Agent + Ontology + Validator | Có 127 tests của source hiện tại | Lần chạy tích hợp thật, số attempts/valid/invalid/error, rule violations, latency và artifact tái chạy |

Không trình bày ví dụ số học trong JSON hay kết quả engine cũ thành trace Agent đã chạy. Lần báo cáo nên tách rõ: phần thiết kế đã chốt; module đã kiểm thử; luồng đã nối; kết quả thực nghiệm còn chờ.

## 7. Cách diễn đạt tiến độ trung thực với cô ở thời điểm này

> Em đã tổ chức lại source theo hướng MVP, tách các nhóm chức năng của recommendation engine, triển khai schemas thành phần, OntologyEvidenceService và StandardValidator độc lập với 11 nhóm kiểm tra. Bộ kiểm thử hiện tại đạt 127 ca. Em đã bổ sung mapping capability/tool, contract và đề xuất Ranking/diversity. Hiện Orchestrator, các adapter và luồng end-to-end chưa hoàn thành; API vẫn chạy engine cũ. Bước tiếp theo em thống nhất Ranking giữa PDF và đặc tả, triển khai Agent State và loader snapshot có nguồn, rồi nối capability qua Validator, Ranking, grounded explanation và feedback/re-planning. LTR được giữ cho giai đoạn có dữ liệu preference của cố vấn.

## 8. Nguồn kiểm tra chính

- [PDF v3](<TÀI LIỆU THIẾT KẾ AI AGENT LẬP KẾ HOẠCH HỌC TẬP_v3.pdf>): 45 trang, đặc biệt trang 13–30, 31–37, 39–45.
- [Thiết kế tổng thể](THIET_KE_AI_AGENT.md), [nghiệp vụ](BA_AI_AGENT.md), [công nghệ](CONG_NGHE_VA_TOOLS.md), [lộ trình](LO_TRINH_MVP.md), [đặc tả triển khai](DAC_TA_TRIEN_KHAI_MVP.md), [hướng dẫn triển khai](DEPLOYMENT.md).
- [Ranking JSON đề xuất](ranking_v1.proposed.json).
- [Agent placeholder](../backend/app/agent/__init__.py), [schemas](../backend/app/schemas/__init__.py).
- [Validator](../backend/app/validation/validator.py), [hợp đồng snapshot/giới hạn](../backend/app/validation/README.md), [Evidence service](../backend/app/services/ontology_evidence_service.py).
- [API recommendations](../backend/app/routes/recommendation_routes.py), [advisor routes](../backend/app/routes/advisor_role_routes.py), [engine](../backend/app/services/recommendation_engine.py), [explanation cũ](../backend/app/services/explanation_generator.py).
- [Validator tests](../backend/tests/test_standard_validator.py), [evidence tests](../backend/tests/test_ontology_evidence.py), [API integration tests](../backend/tests/test_recommendation_api_integration.py).
- [Ba baseline cũ](../experiments/benchmark_algorithms.py), [evaluator cũ](../experiments/experimental_evaluation.py), [test report lịch sử](../benchmark_results/test_report.md).
