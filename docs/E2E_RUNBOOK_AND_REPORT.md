# Chạy E2E đa hồ sơ và nội dung báo cáo

Tài liệu này có hai mục đích: hướng dẫn chạy lại End-to-End (E2E) trên terminal, và cung cấp phần có thể đưa vào báo cáo. E2E kiểm tra contract của MVP trên các hồ sơ đại diện; nó không phải là thí nghiệm thống kê để kết luận RQ1/RQ2 hoặc xác nhận quy định học vụ chính thức.

## 1. Ma trận E2E

Ma trận nguồn nằm ở `experiments/e2e_scenario_matrix.json`. Các fixture được tạo trong lúc chạy từ bản sao ẩn danh của dữ liệu mẫu. E2E-07 và E2E-08 là `controlled_fixture`, chỉ dùng kiểm tra kỹ thuật và không được diễn giải là policy của Trường.

## 2. Chạy từng bước trên terminal

### Bước 1 — Mở terminal tại thư mục gốc

```bash
cd /Users/tandaoduy/tandd/nckh/personalized-learning-ontology
```

Kiểm tra môi trường Python:

```bash
.venv/bin/python --version
```

Trên Windows PowerShell, thay `.venv/bin/python` bằng `.\.venv\Scripts\python.exe`.

### Bước 2 — Chạy một case để kiểm tra nhanh

```bash
.venv/bin/python scripts/run_e2e_scenarios.py --scenario E2E-01 --verbose
```

Terminal phải lần lượt hiện `planning`, `negative probe`, `replan`, `confirm` và `PASS` hoặc `FAIL`. `--verbose` bật log của từng capability Agent; bỏ cờ này nếu chỉ cần log tóm tắt theo case.

### Bước 3 — Chạy toàn bộ ma trận

```bash
.venv/bin/python scripts/run_e2e_scenarios.py --verbose
```

Muốn chỉ định thư mục output (thư mục phải chưa có dữ liệu):

```bash
.venv/bin/python scripts/run_e2e_scenarios.py --output-dir artifacts/e2e_scenarios/final-run
```

### Bước 4 — Kiểm tra kết quả

Runner in đường dẫn artifact cuối cùng. Mỗi lần chạy có cấu trúc:

```text
artifacts/e2e_scenarios/<UTC timestamp>/
├── REPORT.md
├── summary.json
└── E2E-xx/
    ├── result.json
    ├── invalid-probe.json
    ├── replanned.json             (nếu áp dụng)
    ├── confirmed.json             (nếu áp dụng)
    └── scenario-contract.json
```

Đọc `REPORT.md` trước. Khi một case thất bại, dùng `scenario-contract.json` để biết tiêu chí thất bại, `result.json` để xem candidates/validations/evidence, và `replanned.json` để kiểm tra adjustment. Không thay số liệu cũ trong báo cáo bằng lần chạy mới nếu source manifest, config, seed hoặc ma trận case đã đổi.

### Bước 5 — Điều kiện chấp nhận

Một case PASS khi mọi điều kiện áp dụng đều đúng: trạng thái thuộc tập kỳ vọng, negative probe thật sự kích hoạt rule kỳ vọng, re-planning đạt trạng thái kỳ vọng (nếu áp dụng), confirm thành công (nếu bắt buộc), và artifact có request/snapshot/validation/evidence. `validity_rate` dùng số **candidate attempts trước lọc** làm mẫu số; duplicate attempt vẫn được tính vì đã tiêu search budget.

## 3. Nội dung đề xuất chèn vào báo cáo

### 9.x. Kiểm thử End-to-End trên các hồ sơ sinh viên đại diện

Thay vì chỉ minh họa một hồ sơ SV001, hệ thống được chạy qua ma trận E2E đa hồ sơ. Mỗi case thực thi toàn bộ chuỗi Student Context → Ontology/Eligibility → Candidate Generation → Standard Validator → Risk/Ranking → Grounded Explanation; khi có plan hợp lệ, runner còn kiểm tra Feedback/Re-planning và Final Validation/Confirm theo tiêu chí của case. Các negative probe được tạo riêng để xác minh Validator thật sự phát hiện loại ràng buộc cần kiểm tra; chúng không phải plan được đề xuất cho sinh viên.

Kết quả dưới đây lấy từ artifact `artifacts/e2e_scenarios/20260916T115000Z/summary.json`. Cột `valid/candidate` là số candidate valid trên số candidate được giữ lại để validation trong lần chạy đó; chỉ số validity-rate chính thức của runner dùng attempt trước lọc và phải lấy từ `REPORT.md` của lần chạy đóng băng.

| Case | Đặc điểm hồ sơ | Kết quả mong đợi | Kết quả chạy thực tế |
|---|---|---|---|
| E2E-01 | Đúng tiến độ | Sinh tối đa 3 plan hợp lệ; re-plan và confirm được | PASS; 2/2 candidate valid, re-plan `awaiting_feedback`, confirm `confirmed` |
| E2E-02 | Có môn nợ/học lại | Xử lý học lại phù hợp, không bỏ qua validation | PASS; trạng thái `replanning`, negative probe `completed_course_retake` phát hiện |
| E2E-03 | Thiếu tiên quyết | Không đề xuất plan vi phạm prerequisite | PASS; 2/2 candidate valid, negative probe `prerequisite` phát hiện, re-plan thành công |
| E2E-04 | Có song hành | Kiểm tra co-requisite | PASS; 2/2 candidate valid, negative probe `corequisite` phát hiện, re-plan thành công |
| E2E-05 | Chưa chọn chuyên ngành | Không suy đoán chuyên ngành | PASS; 3/3 candidate valid, negative probe `curriculum_membership` phát hiện |
| E2E-06 | Chuyên ngành CNPM | Kiểm tra course–major/specialization | PASS; 2/2 candidate valid, negative probe `curriculum_membership` phát hiện |
| E2E-07 | Chuyên ngành HTTT (fixture kiểm soát) | Kiểm tra course–major khác | PASS; 2/2 candidate valid, negative probe `curriculum_membership` phát hiện |
| E2E-08 | Quota tự chọn gần đầy (fixture kiểm soát) | Không vượt quota | PASS; 1/1 candidate valid, negative probe `elective_quota` phát hiện |
| E2E-09 | Tải tín chỉ thấp | Validator xử lý credit limit | PASS; 2/2 candidate valid, negative probe `credit_limit` phát hiện |
| E2E-10 | Tải cao/học vượt | Validator và Risk xử lý tải tín chỉ | PASS; 2/2 candidate valid, negative probe `credit_limit` phát hiện |
| E2E-11 | Học vượt, gần tốt nghiệp | Ưu tiên yêu cầu còn thiếu hoặc dừng có chẩn đoán | PASS; trạng thái `replanning`, negative probe `completed_course_retake` phát hiện |

Lần chạy trên đạt 11/11 contract; validity-rate theo candidate attempts trước lọc là 27/33 (81,82%), và evidence coverage trung bình là 100%. Các số liệu này phải được diễn giải là coverage của các rule decisions được runner ghi nhận, không phải chứng minh ontology/policy đã đầy đủ hoặc chính thức. E2E-07 và E2E-08 là fixture kiểm soát, cần ghi chú rõ trong báo cáo.

## 4. Giới hạn khi viết báo cáo

- Không viết “Top-3 valid plans” cho mọi case: hệ thống được phép trả 0, 1, 2 hoặc 3 plan hợp lệ tùy không gian tìm kiếm và ràng buộc.
- Không dùng E2E để kết luận Ontology tốt hơn baseline, advisor agreement cao hơn, hay LTR hiệu quả. Những kết luận đó thuộc thí nghiệm BL-01..BL-06 với split train/validation/test và protocol riêng.
- Các nguồn CTĐT, offering, quota, credit policy và academic calendar hiện vẫn có trạng thái `provisional`, `proxy` hoặc `unavailable`; xem [DATA_LIMITATIONS_AND_SOURCES.md](DATA_LIMITATIONS_AND_SOURCES.md).
