# Confirmation & freshness experiment

- Protocol: `confirmation-freshness-v1`
- Confirmation cases: 20
- Replaced non-feedback-ready profiles: 2

| Metric | Value |
|---|---:|
| feedback_ready_coverage | 90.91% |
| confirmation_success_rate | 100.00% |
| final_validation_pass_rate | 100.00% |
| stale_detection_rate | 100.00% |
| unsafe_confirmation_rate | 0.00% |
| refresh_lineage_rate | 100.00% |

| Case | Stratum | Condition | Outcome |
|---|---|---|---|
| C-01 | accelerated_or_high_load | unchanged | confirmed |
| C-02 | on_track | unchanged | confirmed |
| C-03 | specialization | unchanged | confirmed |
| C-04 | accelerated_or_high_load | unchanged | confirmed |
| C-05 | on_track | unchanged | confirmed |
| C-06 | retake_or_debt | unchanged | confirmed |
| C-07 | specialization | unchanged | confirmed |
| C-08 | accelerated_or_high_load | unchanged | confirmed |
| C-09 | on_track | unchanged | confirmed |
| C-10 | retake_or_debt | unchanged | confirmed |
| C-11 | specialization | unchanged | confirmed |
| C-12 | accelerated_or_high_load | unchanged | confirmed |
| C-13 | on_track | student_stale | awaiting_feedback |
| C-14 | retake_or_debt | student_stale | awaiting_feedback |
| C-15 | specialization | student_stale | awaiting_feedback |
| C-16 | accelerated_or_high_load | student_stale | awaiting_feedback |
| C-17 | on_track | knowledge_stale | awaiting_feedback |
| C-18 | retake_or_debt | knowledge_stale | awaiting_feedback |
| C-19 | accelerated_or_high_load | knowledge_stale | awaiting_feedback |
| C-20 | on_track | knowledge_stale | awaiting_feedback |
