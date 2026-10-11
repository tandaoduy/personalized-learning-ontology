# Stage-6 Baseline Results

## Run identity

- Protocol: `stage6-baselines-frozen-v4`
- Completed: 2026-10-11 15:06:02 ICT (08:06:02 UTC)
- Profiles: 364 pseudonymised student profiles
- Seeds: 41-50
- Methods: BL-01-BL-05
- Target term / credit cap: `next-term` / 18 credits
- Validator: `backend.app.validation.validator.StandardValidator`
- Source manifest hash: `sha256:8f7bccd48c23901a708938ccc7734f121a13f5cfaff8c66f49f905c72f033650`
- Configuration hash: `sha256:f6f77370401e6c0f627a642f13cdcd029eca0850ff5deb1876126855abeabbe7`

## Harmonised metric definitions

| Metric | Definition |
|---|---|
| Internal Generation Yield | Emitted candidates / internal generation attempts |
| Emitted Candidate Validity | Validator-valid emitted candidates / emitted candidates |
| Final Recommendation Coverage | Requests with at least one validator-valid plan / all requests |

The values below use these definitions only. They must not be combined with the pre-v4 `candidate_attempt_validity` metric.

## Results

| Method | Internal Generation Yield | Emitted Candidate Validity | Final Recommendation Coverage | No-plan rate | Mean latency (s) | Over-budget candidates | Mean pairwise diversity |
|---|---:|---:|---:|---:|---:|---:|---:|
| BL-01 Rule-based | 100.00% | 91.48% | 91.48% | 8.52% | 1.243 | 0 | N/A |
| BL-02 Greedy | 100.00% | 91.48% | 91.48% | 8.52% | 0.919 | 0 | N/A |
| BL-03 Beam Search | 100.00% (SD 0.00%) | 91.48% (SD 0.00%) | 91.48% (SD 0.00%) | 8.52% | 1.060 | 1 | N/A |
| BL-04 Agent without Ontology Guidance + Full Validator | 100.00% (SD 0.00%) | 0.38% (SD 0.14%) | 1.13% (SD 0.42%) | 98.87% | 12.230 | 12 | N/A |
| BL-05 Agent with Ontology | 67.79% (SD 9.74%) | 92.75% (SD 0.34%) | 91.43% (SD 0.17%) | 8.57% | 2.406 | 3 | 0.430 |

For deterministic BL-01 and BL-02, SD/CI are not applicable; the same result is repeated for artifact-layout consistency. For stochastic methods, SD is the seed-level sample SD, not a confidence interval.

## Interpretation permitted by this run

- BL-04 versus BL-05 is the controlled ontology-guidance comparison: BL-04 generates from flat catalog metadata and is evaluated post hoc by the same full validator; BL-05 receives ontology guidance during generation.
- Ontology guidance improves emitted-candidate validity from 0.38% to 92.75% and final coverage from 1.13% to 91.43% under this protocol.
- BL-01, BL-02 and BL-03 obtain 91.48% coverage, essentially the same as BL-05 (91.43%). Therefore this run does **not** support a claim that the agent is superior to these ontology-aware heuristic baselines in final plan coverage.
- BL-01-BL-03 use the shared production eligibility filter, so they must be described as ontology-aware heuristic baselines, not ontology-free methods.
- All reported final plans are validator-gated. These metrics are not system accuracy and do not establish that proxy academic policies are official institutional regulations.

## Read with the following limitations

- This is the harmonised Stage-6 baseline run only; it is not the ontology-component ablation result.
- No paired statistical test, human evaluation, controlled agentic re-planning evaluation, or external validation is included here.
- The 16 over-budget candidates must be disclosed in any latency comparison; this runner records them rather than claiming that synchronous methods were preemptively stopped.

## Source files

- `manifest.json`: protocol, data/configuration provenance and knowledge scope.
- `request_results.json`: request-level metric denominators and numerators.
- `candidate_results.json`: candidate-level validation, latency, diversity and evidence records.
- `summary.json`: seed-level and aggregate statistics.
- `RUN_AUDIT.md`: integrity checks for this run.
