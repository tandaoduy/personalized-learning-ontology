# E2E multi-profile summary

| Case | Status | Contract | Valid/Cand | Probe | Replan | Confirm | Latency (s) | Evidence cov. |
|---|---|---|---:|---|---:|---:|---:|---:|
| E2E-01 — on_track | awaiting_feedback | PASS | 2/2 | PASS | PASS | PASS | 2.83 | 100% |
| E2E-02 — retake | replanning | PASS | 0/1 | PASS | — | — | 0.39 | 100% |
| E2E-03 — missing_prerequisite | awaiting_feedback | PASS | 2/2 | PASS | PASS | — | 2.25 | 100% |
| E2E-04 — corequisite | awaiting_feedback | PASS | 2/2 | PASS | PASS | — | 3.05 | 100% |
| E2E-05 — undeclared_specialization | awaiting_feedback | PASS | 3/3 | PASS | PASS | — | 2.58 | 100% |
| E2E-06 — specialization_cnpm | awaiting_feedback | PASS | 2/2 | PASS | PASS | — | 2.81 | 100% |
| E2E-07 — specialization_httt_controlled | awaiting_feedback | PASS | 2/2 | PASS | PASS | — | 2.78 | 100% |
| E2E-08 — elective_quota_near_full_controlled | awaiting_feedback | PASS | 1/1 | PASS | PASS | — | 0.62 | 100% |
| E2E-09 — low_credit_load | awaiting_feedback | PASS | 2/2 | PASS | PASS | — | 2.55 | 100% |
| E2E-10 — high_credit_load | awaiting_feedback | PASS | 2/2 | PASS | PASS | — | 2.31 | 100% |
| E2E-11 — accelerated_near_graduation | replanning | PASS | 0/1 | PASS | — | — | 0.64 | 100% |

## Aggregate metrics

- Pass rate: **11/11** (100.0%)
- Validity rate: **18/20** (90.00%)
- Invalid probe pass rate: **11/11**
- Re-plan pass rate (when applicable): **9/9**
- Confirm pass rate (when required): **1/1**
- Average evidence coverage: **100.00%**
- Latency avg / max: **2.07s / 3.05s**
- Controlled fixtures: **2**; data-derived: **9**

## Violation histogram

| Rule | Count |
|---|---:|
| credit_limit | 5 |

Controlled fixtures are explicitly labelled and are not institutional policy data.
