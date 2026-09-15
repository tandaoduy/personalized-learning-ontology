# Protocol Giai đoạn 6 — Baseline công bằng

Mỗi baseline phải chạy trên cùng danh sách pseudonymised profiles, cùng target term, target credits, seed, candidate/search budget và cùng `StandardValidator` hậu kiểm. Artifact mỗi lần chạy phải lưu source-manifest hash, config hash, runtime và candidate attempts trước lọc.

`candidate_output_cap` là 3 cho mọi baseline. Baseline xác định có thể chỉ sinh một candidate; đây không phải candidate bị sao chép để đủ ba. Báo cáo phải giữ `candidate_attempts_before_filter` thực tế làm mẫu số validity rate, không được diễn giải số candidate sinh ra là bằng nhau.

| ID | Generation/ranking | Ontology trong generation/ranking | Validator |
|---|---|---|---|
| BL-01 | Rule-based | Theo rule baseline công bố | Standard Validator hậu kiểm |
| BL-02 | Greedy | Theo heuristic baseline công bố | Standard Validator hậu kiểm |
| BL-03 | Beam Search | Theo cấu hình beam công bố | Standard Validator hậu kiểm |
| BL-04 | Agent ablation | Không dùng prerequisite/corequisite/specialization/offering/quota ontology evidence, không nhận validation feedback | Standard Validator hậu kiểm duy nhất |
| BL-05 | Agent + Ontology | Dùng ontology evidence theo pipeline | Standard Validator trong pipeline và hậu kiểm ghi nhận |

Không được dùng `get_eligible_courses()` hoặc bất kỳ output của `StandardValidator` để chọn/rank candidate trong BL-04. Catalog snapshot dùng chung chỉ là universe học phần; mọi violation của BL-04 phải do Standard Validator hậu kiểm phát hiện.

Chỉ số: candidate-attempt valid rate, violation theo prerequisite/corequisite/curriculum membership/offering/quota/credit, pairwise diversity, latency và evidence coverage. So sánh BL-04/BL-05 là analysis chính cho đóng góp ontology; không báo cáo superiority nếu cấu hình/budget/source manifest khác nhau.
