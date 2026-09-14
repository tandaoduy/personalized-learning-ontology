# E2E multi-profile summary

| Case | Status | Contract | Valid/Cand | Probe | Replan | Confirm | Latency (s) | Evidence cov. |
|---|---|---|---:|---|---:|---:|---:|---:|
| E2E-01 — on_track | awaiting_feedback | PASS | 2/2 | PASS | PASS | PASS | 1.37 | 100% |
| E2E-02 — retake | replanning | PASS | 0/1 | PASS | — | — | 0.16 | 100% |
| E2E-03 — missing_prerequisite | replanning | PASS | 0/2 | PASS | — | — | 1.12 | 100% |
| E2E-04 — corequisite | awaiting_feedback | FAIL | 2/2 | FAIL | PASS | — | 2.34 | 100% |
| E2E-05 — undeclared_specialization | replanning | PASS | 0/3 | PASS | — | — | 2.14 | 100% |
| E2E-06 — specialization_cnpm | awaiting_feedback | PASS | 2/2 | PASS | PASS | — | 1.23 | 100% |
| E2E-07 — specialization_httt_controlled | awaiting_feedback | PASS | 2/2 | PASS | PASS | — | 2.53 | 100% |
| E2E-08 — elective_quota_near_full_controlled | awaiting_feedback | PASS | 1/1 | PASS | PASS | — | 0.44 | 100% |
| E2E-09 — low_credit_load | awaiting_feedback | PASS | 2/2 | PASS | PASS | — | 5.69 | 100% |
| E2E-10 — high_credit_load | awaiting_feedback | PASS | 2/2 | PASS | PASS | — | 5.68 | 100% |
| E2E-11 — accelerated_near_graduation | replanning | PASS | 0/1 | PASS | — | — | 0.34 | 100% |

## Aggregate metrics

- Pass rate: **10/11** (90.9%)
- Validity rate: **13/20** (65.00%)
- Invalid probe pass rate: **10/11**
- Re-plan pass rate (when applicable): **7/7**
- Confirm pass rate (when required): **1/1**
- Average evidence coverage: **100.00%**
- Latency avg / max: **2.10s / 5.69s**
- Controlled fixtures: **2**; data-derived: **9**

## Violation histogram

| Rule | Count |
|---|---:|
| catalog_credit_match | 5 |
| credit_limit | 5 |

Controlled fixtures are explicitly labelled and are not institutional policy data.
