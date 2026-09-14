# E2E multi-profile summary

| Case | Status | Contract | Valid/Cand | Probe | Replan | Confirm | Latency (s) | Evidence cov. |
|---|---|---|---:|---|---:|---:|---:|---:|
| E2E-03 — missing_prerequisite | replanning | PASS | 0/2 | PASS | — | — | 1.31 | 100% |
| E2E-04 — corequisite | awaiting_feedback | PASS | 2/2 | PASS | PASS | — | 1.58 | 100% |
| E2E-05 — undeclared_specialization | replanning | PASS | 0/3 | PASS | — | — | 1.32 | 100% |

## Aggregate metrics

- Pass rate: **3/3** (100.0%)
- Validity rate: **2/7** (28.57%)
- Invalid probe pass rate: **3/3**
- Re-plan pass rate (when applicable): **1/1**
- Average evidence coverage: **100.00%**
- Latency avg / max: **1.41s / 1.58s**
- Controlled fixtures: **0**; data-derived: **3**

## Violation histogram

| Rule | Count |
|---|---:|
| catalog_credit_match | 5 |

Controlled fixtures are explicitly labelled and are not institutional policy data.
