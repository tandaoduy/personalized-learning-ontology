# Chạy E2E đa hồ sơ trên terminal

Hướng dẫn đầy đủ từng bước và bảng kết quả có thể chèn vào báo cáo: [E2E_RUNBOOK_AND_REPORT.md](E2E_RUNBOOK_AND_REPORT.md).

Từ thư mục gốc dự án, chạy toàn bộ ma trận E2E:

```bash
.venv/bin/python scripts/run_e2e_scenarios.py
```

Trên Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_e2e_scenarios.py
```

Runner in log tiến độ từng case, trạng thái planning/re-planning/confirm, candidate attempts, negative probe, evidence coverage, vi phạm và đường dẫn artifact. Dùng log capability chi tiết (Ontology, Generator, Validator, Ranking) khi cần chẩn đoán:

```bash
.venv/bin/python scripts/run_e2e_scenarios.py --verbose
```

Chạy riêng một case:

```bash
.venv/bin/python scripts/run_e2e_scenarios.py --scenario E2E-03 --verbose
```

Mỗi lần chạy ghi vào `artifacts/e2e_scenarios/<UTC timestamp>/`: `REPORT.md`, `summary.json`, cùng artifact request/snapshot/candidate/validation/evidence của từng case. `validity_rate` dùng `candidate_attempts_before_filter`; duplicate attempt vẫn là một attempt nếu đã tiêu search budget.

Kết quả E2E xác nhận contract MVP trên dữ liệu research/proxy, không thay thế policy học vụ chính thức hay trả lời RQ1/RQ2 một cách thống kê.
