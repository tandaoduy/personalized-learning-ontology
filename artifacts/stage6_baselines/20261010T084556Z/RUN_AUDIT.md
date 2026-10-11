# Stage-6 Run Audit

## Integrity checks

| Check | Expected | Observed | Status |
|---|---:|---:|---|
| Protocol | `stage6-baselines-frozen-v4` | `stage6-baselines-frozen-v4` | Pass |
| Methods x profiles x seeds | 5 x 364 x 10 | 18,200 request records | Pass |
| Method/seed groups | 5 x 10 | 50 groups, each with 364 profiles | Pass |
| Candidate records | Derived from emitted candidates | 29,239 | Pass |
| Validator error records | 0 required for a reportable run | 0 | Pass |
| `emitted_candidate_count <= internal_attempt_count` | Every request | 0 violations | Pass |
| `valid_emitted_candidate_count <= emitted_candidate_count` | Every request | 0 violations | Pass |
| Required output files | Manifest, request/candidate results, summary, report | Present | Pass |

Candidate validation outcomes were 16,891 `valid` and 12,348 `invalid`; no validation outcome had status `error`.

## Timing disclosure

The common active-time budget is 120 seconds. The following candidates exceeded that budget and are retained in the artifact:

| Method | Over-budget candidate count |
|---|---:|
| BL-01 Rule-based | 0 |
| BL-02 Greedy | 0 |
| BL-03 Beam Search | 1 |
| BL-04 Agent without Ontology Guidance + Full Validator | 12 |
| BL-05 Agent with Ontology | 3 |
| Total | 16 |

This is an accounting disclosure, not a validation error. Any paper discussion of timing must state that classic synchronous baselines record elapsed time and are not preemptively terminated by the runner.

## Provenance

- Source profile file is represented only by its SHA-256 digest in `manifest.json`; source student IDs are not exported.
- Results were generated under configuration hash `sha256:f6f77370401e6c0f627a642f13cdcd029eca0850ff5deb1876126855abeabbe7`.
- This audit does not certify the underlying curriculum/policy data as official. The protocol explicitly classifies them as provisional/proxy until a versioned source audit is available.

## Reporting decision

This run is suitable for the baseline table in the Results section. A combined paper-results document must wait for a completed `stage7-ontology-component-ablation-v2` artifact so both sections use the same metric contract.
