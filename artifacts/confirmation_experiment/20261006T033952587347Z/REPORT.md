# Confirmation & freshness experiment

- Protocol: `confirmation-freshness-v1`
- Cases: 20

| Metric | Value |
|---|---:|
| feedback_ready_coverage | 90.00% |
| confirmation_success_rate | 100.00% |
| final_validation_pass_rate | 100.00% |
| stale_detection_rate | 100.00% |
| unsafe_confirmation_rate | 0.00% |
| refresh_lineage_rate | 100.00% |

| Case | Stratum | Condition | Outcome |
|---|---|---|---|
| C-01 | accelerated_or_high_load | unchanged | confirmed |
| C-02 | on_track | unchanged | confirmed |
| C-03 | retake_or_debt | unchanged | no_feedback_ready_plan |
| C-04 | specialization | unchanged | confirmed |
| C-05 | accelerated_or_high_load | unchanged | confirmed |
| C-06 | on_track | unchanged | confirmed |
| C-07 | retake_or_debt | unchanged | confirmed |
| C-08 | specialization | unchanged | confirmed |
| C-09 | accelerated_or_high_load | unchanged | confirmed |
| C-10 | on_track | unchanged | confirmed |
| C-11 | retake_or_debt | unchanged | confirmed |
| C-12 | specialization | unchanged | confirmed |
| C-13 | accelerated_or_high_load | student_stale | awaiting_feedback |
| C-14 | on_track | student_stale | awaiting_feedback |
| C-15 | retake_or_debt | student_stale | awaiting_feedback |
| C-16 | specialization | student_stale | awaiting_feedback |
| C-17 | accelerated_or_high_load | knowledge_stale | awaiting_feedback |
| C-18 | on_track | knowledge_stale | awaiting_feedback |
| C-19 | retake_or_debt | knowledge_stale | awaiting_feedback |
| C-20 | specialization | knowledge_stale | no_feedback_ready_plan |
