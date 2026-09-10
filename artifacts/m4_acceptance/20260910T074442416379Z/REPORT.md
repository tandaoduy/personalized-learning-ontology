# Minh chứng M4 — SV001

- Hồ sơ: 001, CNTT/CNPM, CURRICULUM-2023; học kỳ 6 → 7.
- Chính sách baseline: 10–27 tín chỉ; mục tiêu 15.
- Validator: 2 plan valid; mỗi plan 15 tín chỉ.
- Risk: 2 plan mức `low`, Risk = 0.1176, Safety = 0.8824.
- Ranking: chọn 2 plan; đề xuất `RUN_m3-SV001-plan-1`; ngưỡng Jaccard 0.30.
- Diversity giữa hai plan: 0.3333, đạt ngưỡng.
- Không có plan thứ ba vì pool chỉ có hai phương án phân biệt; `shortfall_reason=pool_or_diversity_exhausted`.
- Đối chứng: thêm CCN6203 sai chuyên ngành; Validator phát hiện `curriculum_membership`.
- Trạng thái pipeline: `explaining`; kiểm thử: 97/97 đạt.

Risk học vụ hiện dùng proxy `ProgressRiskAnalyzer` có version và được đánh dấu không chính thức. Dữ liệu chi tiết nằm trong `positive.json`, `negative.json`, `source_audit.json`, `summary.json` và `tests.txt`.
