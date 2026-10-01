# Stage 6 — Kết quả baseline trên toàn bộ hồ sơ ẩn danh

## Thiết lập thực nghiệm

- Hồ sơ: 364 hồ sơ sinh viên đã pseudonym hóa.
- Seed: 41–50 (10 seed); `target_term_id=next-term`; target-credit cap: 18.
- Budget chung: output cap 3, candidate-attempt limit 60, expanded-state limit 5.000, active budget 120 giây.
- Hậu kiểm: `StandardValidator`; không có candidate nào vượt timeout budget.
- `Final Recommendation Validity` chỉ tính các kế hoạch đã qua validator và được phát hành. Vì vậy chỉ số này phải luôn được đọc cùng `Final Recommendation Coverage` và **không phải** độ chính xác hệ thống.

| Method | Candidate Attempt Validity | Final Recommendation Validity | Final Recommendation Coverage | No-plan Rate | Mean latency (s) |
|---|---:|---:|---:|---:|---:|
| BL-01 Rule-based | 91,48% | 100,00% | 91,48% | 8,52% | 0,763 |
| BL-02 Greedy | 91,48% | 100,00% | 91,48% | 8,52% | 0,567 |
| BL-03 Beam Search | 91,48% ± 0,00% | 100,00% ± 0,00% | 91,48% | 8,52% | 0,575 |
| BL-04 Agent không Ontology | 0,38% ± 0,14% | 100,00%* | 1,13% | 98,87% | 2,381 |
| BL-05 Agent có Ontology | 62,87% ± 8,87% | 100,00% ± 0,00% | 91,48% | 8,52% | 0,571 |

`*` BL-04 chỉ phát hành một số rất ít kế hoạch hợp lệ; do validator gate, mọi kế hoạch đã phát hành đều hợp lệ. Không diễn giải 100% này là BL-04 hiệu quả hoặc chính xác.

Với phương pháp có ngẫu nhiên, giá trị sau dấu `±` là sample SD giữa 10 seed. CI 95% half-width của BL-04 Candidate Attempt Validity là **0,09 điểm phần trăm**; của BL-05 là **5,50 điểm phần trăm**. BL-01 và BL-02 là tất định nên SD/CI không áp dụng.

## So sánh ablation chính cho RQ1

BL-04 và BL-05 dùng cùng dữ liệu, seed list, target-credit cap, search budget và validator. Cả ba hash kiểm soát đều trùng khớp:

- Config hash: `sha256:f6f77370401e6c0f627a642f13cdcd029eca0850ff5deb1876126855abeabbe7`
- Source-manifest hash: `sha256:8f7bccd48c23901a708938ccc7734f121a13f5cfaff8c66f49f905c72f033650`
- Source-profile-data hash: `sha256:e15f814759468e73988a1515b5cc4351ccad33817dab1eb1f0625c709a9583ae`

BL-04 chỉ dùng metadata catalog phẳng (mã môn, tín chỉ, học kỳ khuyến nghị) và seed-diversification; không dùng ontology eligibility, prerequisite, co-requisite, curriculum/specialization relation, semester offering, elective quota hoặc validator feedback trong generation/ranking. BL-05 dùng ontology evidence và deterministic validator trong pipeline.

Kết quả cho thấy khi bỏ ontology khỏi Agent, Candidate Attempt Validity giảm từ **62,87%** xuống **0,38%** (giảm 62,49 điểm phần trăm), còn Coverage giảm từ **91,48%** xuống **1,13%** (giảm 90,36 điểm phần trăm). Điều này là bằng chứng thực nghiệm ban đầu rằng các ràng buộc ontology giúp Agent tìm được kế hoạch hợp lệ; Validator vẫn bảo vệ đầu ra cuối trong cả hai điều kiện.

## Vi phạm BL-04 (tổng trên 10.920 candidate đã validator kiểm tra)

| Loại vi phạm | Số lượng |
|---|---:|
| Prerequisite | 13.479 |
| Co-requisite | 4.648 |
| Curriculum membership | 21.862 |
| Semester offering | 0 |
| Elective quota | 22.307 |
| Credit limit | 0 |

Các count này là tổng rule violations trên các candidate trước lọc, không phải số hồ sơ vi phạm. Chúng sẽ được thay thế/bổ sung bởi ontology-component ablation (bỏ từng loại relation) trong bảng RQ1 chính thức.

## Provenance artifact

- BL-01, BL-02, BL-03 và BL-05: [`artifacts/stage6_baselines/20260930T034342Z`](../artifacts/stage6_baselines/20260930T034342Z)
- BL-04 rerun: [`artifacts/stage6_baselines/20261001T004802Z`](../artifacts/stage6_baselines/20261001T004802Z)

Các quy định học vụ trong source manifest vẫn là provisional/proxy cho đến khi có đối chiếu nguồn chính thức, version và effective date; không diễn giải kết quả như xác nhận chính sách chính thức của Trường.
