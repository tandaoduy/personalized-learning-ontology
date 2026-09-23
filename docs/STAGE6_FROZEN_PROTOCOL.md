# Frozen protocol — Stage 6 baselines

**Protocol ID:** `stage6-baselines-frozen-v2`  
**Frozen on:** 2026-09-23

Every method uses the same sorted pseudonymised profiles, `target_term_id=next-term`, target credits 18, output cap 3, 60 candidate attempts, 5,000 expanded states, frozen config, and post-hoc `StandardValidator`. Default seeds are 41–50. Artifacts record source-manifest/config hashes and no source student IDs.

| Measure | Numerator | Denominator | Meaning |
|---|---|---|---|
| Candidate Attempt Validity | Valid candidate attempts | All attempts before filtering | Search efficiency, not accuracy. |
| Final Recommendation Validity | Valid final recommendations | Recommendations actually delivered after validator gate | Safety of user-facing output. |
| Final Recommendation Coverage | Requests with a delivered recommendation | All requests | Required companion to Final Recommendation Validity. |

Report seed-level values plus mean, sample SD, and 95% CI half-width. If no final recommendation is delivered, Final Recommendation Validity is `null`; never convert it to 0% or 100%.

`BL-04` is catalog-only and receives no ontology eligibility or validator feedback while generating/ranking. Secondary metrics are violation groups, latency, diversity, evidence coverage, and no-plan rate. Any change to data, seed list, budget, configuration, or metrics requires a new protocol version.

```bash
python experiments/run_stage6_baselines.py
python experiments/run_stage6_baselines.py --limit 2 --seeds 41,42
```

The run writes `manifest.json`, `candidate_results.json`, `request_results.json`, `summary.json`, and `REPORT.md` under `artifacts/stage6_baselines/`.

Current academic rules remain provisional/proxy unless the source audit has a version-specific approved mapping. Do not call Candidate Attempt Validity “system accuracy”.
