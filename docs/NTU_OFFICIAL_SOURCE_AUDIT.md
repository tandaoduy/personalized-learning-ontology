# NTU official-source audit

**Audit date:** 2026-09-23. A public NTU source is not proof that it matches the precise curriculum version and cohort encoded in this repository.

| Domain | Official NTU source located | Current status | Closure requirement |
|---|---|---|---|
| Training regulation / registration credits | [Undergraduate training regulation](https://thanhnien.ntu.edu.vn/tin-tuc/ban-hanh-dao-tao-trinh-do-dai-hoc-cua-truong-dai-hoc-nha-trang-ap-dung-tu-nam-hoc) | `unmapped` | Archive decision number, effective date and cohorts; map every enforced credit rule. |
| Curriculum, course credits, prerequisite | [NTU IT programme](https://tuyensinh.ntu.edu.vn/nganh-cong-nghe-thong-tin) | `unmapped` | Select applicable signed programme decision; reconcile every course code, credit and prerequisite. |
| Curriculum version / specialization | [Curriculum legal-document index](https://pdtdaihoc.ntu.edu.vn/van-ban-phap-quy/quan-ly-chuong-trinh-dao-tao) | `unmapped` | Attach signed decision and effective date for each curriculum/specialization. |
| Calendar / offering | [Annual training plan](https://ntu.edu.vn/%C4%91ao-tao/ke-hoach-%C4%91ao-tao-nam-hoc) | `unmapped` | Archive applicable term timetable and offering list; map `next-term` to the actual term. |
| Elective quota | Applicable signed curriculum decision and appendices | `not located for current mapping` | Reconcile definition, unit, cohort and specialization. |

## Decision

The runtime manifest stays `provisional`, `proxy`, or `unavailable`. This audit does not upgrade authority status. RDF rules, quota configuration, registration-credit overrides, `openSemesterType`, and `next-term` remain research artifacts/proxies.

Before official use: archive immutable source documents with SHA-256; record issuer/version/effective date/scope; produce reviewed course-level mappings; update `knowledge/source_manifest.json` only for verified domains; then freeze a new manifest and rerun E2E, Stage 6, confirmation, and regression tests.
