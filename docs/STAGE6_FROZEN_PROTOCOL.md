# Frozen protocol — Stage 6 baselines

**Protocol ID:** `stage6-baselines-frozen-v3`
**Frozen on:** 2026-09-30

Every method uses the same sorted pseudonymised profiles, `target_term_id=next-term`, target-credit cap 18, output cap 3, 60 candidate attempts, 5,000 expanded states, 120-second active budget, frozen config, and post-hoc `StandardValidator`. The target-credit cap is applied equally to every generator and validator; the configured 10–27-credit proxy-policy range is retained in the manifest for provenance. Default seeds are 41–50. Artifacts record source-manifest/config hashes and no source student IDs.

| Measure | Numerator | Denominator | Meaning |
|---|---|---|---|
| Candidate Attempt Validity | Valid candidate attempts | All attempts before filtering | Search efficiency, not accuracy. |
| Final Recommendation Validity | Valid final recommendations | Recommendations actually delivered after validator gate | Safety of user-facing output. |
| Final Recommendation Coverage | Requests with a delivered recommendation | All requests | Required companion to Final Recommendation Validity. |

For stochastic methods, report seed-level values plus mean, sample SD, and 95% CI half-width. Deterministic methods are still executed under every listed seed for an identical artifact layout, but report one point estimate and `SD/CI = N/A`; duplicate deterministic executions are not independent samples. If no final recommendation is delivered, Final Recommendation Validity is `null`; never convert it to 0% or 100%.

`BL-04` uses only flat catalog code/credit/recommended-semester metadata and receives no ontology eligibility, constraint relation evidence, or validator feedback while generating/ranking. It generates up to three seed-diversified plans per request. Secondary metrics are violation groups, latency, diversity, evidence coverage, and no-plan rate. Agent timeouts are enforced by its active budget; the synchronous classic baselines record elapsed time and must be flagged if they exceed the same budget, rather than being described as preemptively stopped. Any change to data, seed list, budget, configuration, or metrics requires a new protocol version.

BL-01–BL-03 call the shared production eligibility filter before their respective ordering/search strategy. They must therefore be labelled **ontology-aware heuristic baselines**, not ontology-free baselines. The ontology ablation comparison is BL-04 versus BL-05; the run manifest records this knowledge scope for every method.

```bash
.venv/bin/python experiments/run_stage6_baselines.py
.venv/bin/python experiments/run_stage6_baselines.py --limit 2 --seeds 41,42
```

The full run can take a long time because it evaluates every profile under ten seeds. It prints progress every ten profiles. First verify the environment with the two-profile command above; use `Ctrl+C` to stop a long run safely (source records are read-only and final artifacts are only written after processing completes).

The run writes `manifest.json`, `candidate_results.json`, `request_results.json`, `summary.json`, and `REPORT.md` under `artifacts/stage6_baselines/`.

Current academic rules remain provisional/proxy unless the source audit has a version-specific approved mapping. Do not call Candidate Attempt Validity “system accuracy”.
