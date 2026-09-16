# E2E multi-profile summary

| Case | Status | Contract | Valid/Cand | Probe | Replan | Confirm | Latency (s) | Evidence cov. |
|---|---|---|---:|---|---:|---:|---:|---:|
| E2E-01 — on_track | awaiting_feedback | PASS | 2/2 | PASS | PASS | PASS | 0.57 | 100% |
| E2E-02 — retake | replanning | PASS | 0/1 | PASS | — | — | 0.08 | 100% |
| E2E-03 — missing_prerequisite | awaiting_feedback | PASS | 2/2 | PASS | PASS | — | 0.40 | 100% |
| E2E-04 — corequisite | awaiting_feedback | PASS | 2/2 | PASS | PASS | — | 0.56 | 100% |
| E2E-05 — undeclared_specialization | awaiting_feedback | PASS | 3/3 | PASS | PASS | — | 0.46 | 100% |
| E2E-06 — specialization_cnpm | awaiting_feedback | PASS | 2/2 | PASS | PASS | — | 0.54 | 100% |
| E2E-07 — specialization_httt_controlled | awaiting_feedback | PASS | 2/2 | PASS | PASS | — | 0.51 | 100% |
| E2E-08 — elective_quota_near_full_controlled | awaiting_feedback | PASS | 1/1 | PASS | PASS | — | 0.14 | 100% |
| E2E-09 — low_credit_load | awaiting_feedback | PASS | 2/2 | PASS | PASS | — | 0.53 | 100% |
| E2E-10 — high_credit_load | awaiting_feedback | PASS | 2/2 | PASS | PASS | — | 0.56 | 100% |
| E2E-11 — accelerated_near_graduation | replanning | PASS | 0/1 | PASS | — | — | 0.10 | 100% |

## Aggregate metrics

- Pass rate: **11/11** (100.0%)
- Validity rate: **18/33** (54.55%)
- Invalid probe pass rate: **11/11**
- Re-plan pass rate (when applicable): **9/9**
- Confirm pass rate (when required): **1/1**
- Average evidence coverage: **100.00%**
- Latency avg / p50 / p95 / max: **0.40s / 0.51s / 0.56s / 0.57s**
- Controlled fixtures: **2**; data-derived: **9**

## Violation histogram

| Rule | Count |
|---|---:|
| credit_limit | 5 |

Controlled fixtures are explicitly labelled and are not institutional policy data.
