# Đối chiếu dự án với nhận xét người hướng dẫn

> Bản cập nhật trạng thái source: 2026-09-14. Tài liệu này thay thế các nhận định tiến độ của bản rà soát ngày 2026-09-08; các đoạn cũ nói Orchestrator, adapters, API Agent hoặc Feedback/Re-planning chưa triển khai không còn phản ánh source hiện tại.

## 1. Kết luận hiện tại

MVP Agent đã có state machine/orchestrator tự xây dựng bằng Python và Pydantic; **không dùng LangGraph**. `AgentPipeline` nối các capability thật với Student data, ontology, Beam Search, Standard Validator, Risk, Ranking và Grounded Explanation. API run nằm tại `/api/agent/runs`.

Vòng human-in-the-loop đã được triển khai theo nguyên tắc thiết kế v3:

```text
awaiting_feedback → normalize_feedback → AdjustmentRequest → replanning
→ generating → validating → assessing_risk → ranking → explaining → awaiting_feedback

awaiting_feedback → normalize_feedback → final_validating → confirmed
```

Feedback chỉ tạo selection intent hoặc `AdjustmentRequest`, không sửa trực tiếp candidate, ontology hay hard constraints. Candidate của vòng mới phải đi lại qua Standard Validator trước Risk/Ranking/Explanation. Confirm tải lại snapshot nguồn; nếu version thay đổi, hệ thống lập một vòng mới và yêu cầu chọn lại, không xác nhận plan stale.

## 2. Bằng chứng theo yêu cầu

| Yêu cầu | Hiện trạng source | Bằng chứng chính |
|---|---|---|
| Điều phối state, budget, trace và validation gate | Đã triển khai | `backend/app/agent/orchestrator.py` |
| Capability adapters dùng dịch vụ thật | Đã triển khai | `backend/app/capabilities/`, `backend/app/agent/pipeline.py` |
| API tạo run, feedback, re-plan, confirm | Đã triển khai | `backend/app/routes/agent_routes.py` |
| Feedback idempotent, có hash/provenance | Đã triển khai | `services/agent_run_store.py`, `services/feedback_service.py` |
| Re-planning và validation lại | Đã triển khai | `AgentPipeline.replan_from_feedback()` |
| Final Validation/Confirm và refresh version | Đã triển khai | `AgentPipeline.confirm_from_feedback()` |
| LTR | Chưa triển khai, đúng chủ đích | Chỉ lưu dữ liệu preference cho giai đoạn sau |

Ca acceptance tái lập hiện có là SV001: `python scripts/run_feedback_acceptance.py`. Nó xuất trace/JSON cho initial plan, feedback modify, re-planning, validation của candidate mới và Final Validation/Confirm vào `artifacts/feedback_acceptance/`. Đây là minh chứng tích hợp có phạm vi một hồ sơ, chưa thay thế E2E đa dạng hoặc thực nghiệm batch.

## 3. Kiểm thử và cách diễn giải đúng

Kết quả **98 tests** chỉ được diễn giải là bộ acceptance/regression được chọn cho Agent, ontology, validator, pipeline, risk và ranking. Nó không có nghĩa toàn bộ source code đã vượt đúng 98 kiểm thử, cũng không chứng minh hiệu quả khoa học hay độ đầy đủ của chính sách học vụ thực tế.

Chạy toàn bộ suite, bao gồm các test được đánh dấu `integration`, và lưu báo cáo riêng:

```powershell
python scripts/run_full_regression.py
```

Lệnh tạo `REPORT.md`, `pytest-output.txt` và `junit.xml` dưới `artifacts/full_regression/<UTC timestamp>/`. Báo cáo phải được dùng làm số liệu full regression theo lần chạy, không thay bằng số test cũ trong `benchmark_results/test_report.md`.

## 4. Giới hạn cần công bố rõ

- Phiên bản CTĐT, lịch mở môn, quota và credit policy phải gắn source manifest/version chính thức trước khi coi là dữ liệu của Trường.
- Quan hệ `học trước` không được dùng baseline rỗng hoặc suy diễn là đã xác minh khi chưa có nguồn chính thức.
- Pilot `target_term_id=next-term` hiện chỉ biểu diễn học kỳ hiện tại + 1; chưa ánh xạ academic calendar thực tế có version.
- `ProgressRiskAnalyzer` là proxy có version, không phải cảnh báo học vụ chính thức.
- Grounded explanation phải giữ chuỗi claim → decision → evidence → query/rule → source/version; evidence coverage cần được đo thay vì chỉ đếm chuỗi lý do.

## 5. Việc tiếp theo trước thí nghiệm chính thức

1. Ổn định E2E đa hồ sơ: đúng tiến độ, môn nợ, thiếu tiên quyết, song hành, chưa chọn chuyên ngành, nhiều chuyên ngành, quota tự chọn gần đầy, tải thấp/cao, học vượt và gần tốt nghiệp.
2. Báo cáo validity, violations theo từng nhóm, diversity, latency và evidence coverage; sau đó mới chạy batch trên hồ sơ ẩn danh.
3. Chạy Rule-based, Greedy, Beam Search, Agent không Ontology và Agent có Ontology trên cùng dữ liệu, seed, search budget và Standard Validator. Đo valid-plan rate trên candidate attempts trước lọc và các vi phạm tiên quyết/song hành/chuyên ngành/kỳ mở/quota.
4. Chỉ xây Preference Dataset và LTR sau khi có đủ phản hồi cố vấn/sinh viên; LTR không thuộc tiêu chí hoàn tất giai đoạn Agent + Ontology + Validator + Grounded Explanation + Feedback/Re-planning.
