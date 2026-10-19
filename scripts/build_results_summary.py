"""Build paper-ready results tables and dependency-free SVG figures from frozen artifacts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
E2E = ROOT / "artifacts/e2e_scenarios/20260916T115000Z/summary.json"
CONFIRMATION = ROOT / "artifacts/confirmation_experiment/20261006T034141939726Z/summary.json"
OUT_DOC = ROOT / "docs/EXPERIMENTAL_RESULTS.md"
OUT_ASSETS = ROOT / "docs/assets"
FULL_PROFILE_COUNT = 364
FULL_SEEDS = list(range(41, 51))


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def latest_run(directory: Path, protocol: str) -> Path:
    """Return only a complete frozen run, never a smoke-test artifact."""
    matches = []
    for manifest_path in directory.glob("*/manifest.json"):
        manifest = load(manifest_path)
        if (
            manifest.get("protocol") == protocol
            and manifest.get("profiles") == FULL_PROFILE_COUNT
            and manifest.get("seeds") == FULL_SEEDS
            and (manifest_path.parent / "summary.json").exists()
        ):
            matches.append(manifest_path.parent)
    if not matches:
        raise FileNotFoundError(f"No completed {protocol} artifact found in {directory}")
    return max(matches, key=lambda path: path.name)


def pct(value: float | None) -> str:
    return "N/A" if value is None else f"{value * 100:.2f}%"


def pm(metric: dict) -> str:
    if metric["sd"] is not None:
        return f"{pct(metric['mean'])} +/- {metric['sd'] * 100:.2f}%"
    if metric["sd"] is None:
        return pct(metric["mean"])
    return f"{pct(metric['mean'])} ± {metric['sd'] * 100:.2f}%"


def bar_svg(path: Path, title: str, rows: list[tuple[str, float]], *, color: str) -> None:
    width, left, top, row_h, bar_w = 900, 280, 72, 48, 540
    height = top + len(rows) * row_h + 42
    items = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
             '<style>text{font-family:Arial,sans-serif;fill:#1e293b}.title{font-size:20px;font-weight:700}.label{font-size:14px}.value{font-size:14px;font-weight:700}</style>',
             f'<text x="24" y="34" class="title">{title}</text>',
             f'<text x="{left}" y="56" class="label">0%</text><text x="{left + bar_w - 28}" y="56" class="label">100%</text>']
    for i, (label, value) in enumerate(rows):
        y = top + i * row_h
        value = max(0, min(1, value))
        items += [f'<text x="24" y="{y + 20}" class="label">{label}</text>',
                  f'<rect x="{left}" y="{y}" width="{bar_w}" height="24" rx="4" fill="#e2e8f0"/>',
                  f'<rect x="{left}" y="{y}" width="{bar_w * value:.1f}" height="24" rx="4" fill="{color}"/>',
                  f'<text x="{left + bar_w + 14}" y="{y + 19}" class="value">{value * 100:.2f}%</text>']
    items.append("</svg>")
    path.write_text("\n".join(items), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build results only from frozen, harmonised v6/v3 artifacts")
    parser.add_argument("--baseline-dir", type=Path, default=None)
    parser.add_argument("--ablation-dir", type=Path, default=None)
    args = parser.parse_args()
    baseline_dir = (args.baseline_dir or latest_run(
        ROOT / "artifacts/stage6_baselines", "stage6-baselines-frozen-v6")).resolve()
    ablation_dir = (args.ablation_dir or latest_run(
        ROOT / "artifacts/ontology_ablation", "stage7-ontology-component-ablation-v3")).resolve()
    baseline_manifest = load(baseline_dir / "manifest.json")
    ablation_manifest = load(ablation_dir / "manifest.json")
    baseline = load(baseline_dir / "summary.json")
    ablation, e2e, confirmation = load(ablation_dir / "summary.json"), load(E2E), load(CONFIRMATION)
    combined = dict(baseline)
    order = ["BL-01-rule-based", "BL-02-greedy", "BL-03-beam-search", "BL-04-agent-without-ontology", "BL-05-agent-with-ontology"]
    labels = {"BL-01-rule-based": "BL-01 Rule-based", "BL-02-greedy": "BL-02 Greedy", "BL-03-beam-search": "BL-03 Beam Search", "BL-04-agent-without-ontology": "BL-04 Agent without Ontology Guidance + Full Validator", "BL-05-agent-with-ontology": "BL-05 Agent có Ontology"}
    OUT_ASSETS.mkdir(parents=True, exist_ok=True)
    labels["BL-05-agent-with-ontology"] = "BL-05 Agent c" + chr(0x00F3) + " Ontology"
    bar_svg(OUT_ASSETS / "results-baseline-emitted-candidate-validity.svg", "Emitted Candidate Validity theo baseline", [(labels[k], combined[k]["emitted_candidate_validity"]["mean"]) for k in order], color="#2563eb")
    ablation_order = ["full_ontology", "without_prerequisite", "without_corequisite", "without_curriculum_relation", "without_semester_offering", "without_elective_quota"]
    ablation_labels = {"full_ontology": "Ontology đầy đủ", "without_prerequisite": "Bỏ tiên quyết", "without_corequisite": "Bỏ song hành", "without_curriculum_relation": "Bỏ quan hệ CTĐT", "without_semester_offering": "Bỏ kỳ mở", "without_elective_quota": "Bỏ quota tự chọn"}
    bar_svg(OUT_ASSETS / "results-ontology-ablation.svg", "Ablation ontology — Emitted Candidate Validity", [(ablation_labels[k], ablation[k]["emitted_candidate_validity"]["mean"]) for k in ablation_order], color="#7c3aed")

    ablation_labels = {
        "full_ontology": "Ontology " + chr(0x0111) + chr(0x1EA7) + "y " + chr(0x0111) + chr(0x1EE7),
        "without_prerequisite": "B" + chr(0x1ECF) + " ti" + chr(0x00EA) + "n quy" + chr(0x1EBF) + "t",
        "without_corequisite": "B" + chr(0x1ECF) + " song h" + chr(0x00E0) + "nh",
        "without_curriculum_relation": "B" + chr(0x1ECF) + " quan h" + chr(0x1EC7) + " CT" + chr(0x0110) + "T",
        "without_semester_offering": "B" + chr(0x1ECF) + " k" + chr(0x1EF3) + " m" + chr(0x1EDF),
        "without_elective_quota": "B" + chr(0x1ECF) + " quota t" + chr(0x1EF1) + " ch" + chr(0x1ECD) + "n",
    }
    bar_svg(OUT_ASSETS / "results-ontology-ablation.svg", "Ontology ablation — Emitted Candidate Validity", [(ablation_labels[k], ablation[k]["emitted_candidate_validity"]["mean"]) for k in ablation_order], color="#7c3aed")
    bar_svg(OUT_ASSETS / "results-ontology-ablation.svg", "Ontology ablation - Emitted Candidate Validity", [(ablation_labels[k], ablation[k]["emitted_candidate_validity"]["mean"]) for k in ablation_order], color="#7c3aed")
    baseline_rows = []
    for key in order:
        item = combined[key]
        baseline_rows.append(f"| {labels[key]} | {pm(item['internal_generation_yield'])} | {pm(item['emitted_candidate_validity'])} | {pm(item['final_recommendation_coverage'])} | {pct(item['no_plan_rate']['mean'])} | {item['mean_latency_seconds']:.3f} |")
    full = ablation["full_ontology"]["emitted_candidate_validity"]["mean"]
    rule_for = {"without_prerequisite": "prerequisite", "without_corequisite": "corequisite", "without_curriculum_relation": "curriculum_membership", "without_semester_offering": "semester_offering", "without_elective_quota": "elective_quota"}
    ablation_rows = []
    for key in ablation_order:
        item = ablation[key]
        violations = "0" if key == "full_ontology" else str(item["violations_by_rule"][rule_for[key]])
        delta = 0 if key == "full_ontology" else (item["emitted_candidate_validity"]["mean"] - full) * 100
        ablation_rows.append(f"| {ablation_labels[key]} | {pm(item['internal_generation_yield'])} | {pm(item['emitted_candidate_validity'])} | {pm(item['final_recommendation_coverage'])} | {delta:+.2f} pp | {violations} |")
    metrics = confirmation["metrics"]
    same_source_revision = (
        baseline_manifest["source_provenance"]["git_commit"] == ablation_manifest["source_provenance"]["git_commit"]
        and baseline_manifest["source_provenance"]["git_tree"] == ablation_manifest["source_provenance"]["git_tree"]
    )
    provenance_note = (
        "Baseline and ablation use the same frozen source revision."
        if same_source_revision else
        "Baseline and ablation have different frozen source revisions; report their tables separately and rerun the ablation at the baseline revision before making a paired comparative claim."
    )
    text = f"""# Experimental Results

This document is generated from frozen experiment artifacts by `scripts/build_results_summary.py`. It is a paper-ready Results draft, not a claim that proxy academic policies are official NTU regulations.

## Experimental setting

All baseline and ontology-component ablation runs use 364 pseudonymised profiles, `target_term_id=next-term`, target-credit cap 18, common search budget, and seeds 41–50 for stochastic methods. The no-ontology agent artifact is the controlled rerun used by Stage 6. E2E and confirmation results are reported separately because they evaluate contracts and transaction safety, not comparative recommendation quality.

## Metric interpretation

`Internal Generation Yield` is emitted candidates divided by all internal generation attempts. `Emitted Candidate Validity` is validator-valid emitted candidates divided by candidates emitted for validation. The two quantities must not be merged because duplicate/empty/rejected internal search attempts do not reach validation.

`Final Recommendation Coverage` is the proportion of requests for which at least one validator-valid plan is available. None of these metrics is system accuracy.

## Baseline comparison

| Method | Internal Generation Yield | Emitted Candidate Validity | Final Recommendation Coverage | No-plan Rate | Mean latency (s) |
|---|---:|---:|---:|---:|---:|
{"\n".join(baseline_rows)}

![Emitted Candidate Validity by baseline](assets/results-baseline-emitted-candidate-validity.svg)

All final recommendations are validator-gated. Therefore, the central ontology comparison is BL-04 versus BL-05, reported with the three harmonised metrics after both experiments are rerun. The BL-05 baseline and `full_ontology` ablation are distinct experimental pipelines and must be reported in their own tables, never pooled as one observation. Do not reuse pre-v5 values because their denominators or validator-error accounting are not comparable with the frozen protocol.

## RQ1 — Ontology component ablation

| Generator configuration | Internal Generation Yield | Emitted Candidate Validity | Final Recommendation Coverage | Change from full | Violations of removed rule |
|---|---:|---:|---:|---:|---:|
{"\n".join(ablation_rows)}

![Ontology component ablation](assets/results-ontology-ablation.svg)

The full ontology evaluator remains active in every ablation; therefore the table measures the contribution of each relation family to **generating valid candidates**, rather than weakening the evaluator. Numerical claims must be regenerated under the harmonised metric contract.

## End-to-end contract evidence

The frozen E2E matrix reports {e2e['passed']}/{e2e['total']} passed contracts, {e2e['validity']['valid_candidates']}/{e2e['validity']['candidate_attempts']} Candidate Attempt Validity ({pct(e2e['validity']['validity_rate'])}), {e2e['invalid_probe']['passed']}/{e2e['invalid_probe']['total']} negative probes, {e2e['replan']['passed']}/{e2e['replan']['total']} applicable re-planning cases, and {pct(e2e['evidence_coverage_avg'])} average evidence coverage. These results establish integration/contract coverage only; they do not establish superiority over baselines or completeness of institutional policies.

## Confirmation and freshness experiment

The confirmation experiment contains 20 feedback-ready, pseudonymised profiles: 12 unchanged-source confirmations, 4 student-snapshot stale probes, and 4 knowledge-snapshot stale probes. The runner replaced two non-feedback-ready profiles during deterministic selection.

| Metric | Result |
|---|---:|
| Confirmation Success Rate (unchanged source) | {pct(metrics['confirmation_success_rate'])} |
| Final Validation Pass Rate (unchanged source) | {pct(metrics['final_validation_pass_rate'])} |
| Stale Detection Rate | {pct(metrics['stale_detection_rate'])} |
| Unsafe Confirmation Rate | {pct(metrics['unsafe_confirmation_rate'])} |
| Refresh Lineage Rate | {pct(metrics['refresh_lineage_rate'])} |
| Feedback-ready coverage while sampling | {pct(metrics['feedback_ready_coverage'])} |

No stale probe was committed as confirmed. This supports transaction freshness of the human-in-the-loop confirmation workflow; it is not a human acceptance study.

{provenance_note}

## Scope and limitations

- Curriculum, prerequisite/corequisite, quota, offering and calendar sources remain provisional/proxy/unavailable until mapped to versioned official NTU documents.
- Human evaluation has not yet been conducted; Advisor Agreement, Acceptance Rate, Edit Distance, NDCG@3/MRR, usefulness and trust must not be reported as measured results.
- External validation on the Illinois prerequisite dataset remains future work.

## Artifact provenance

- Baselines: `{baseline_dir.relative_to(ROOT)}`.
- Ablation: `{ablation_dir.relative_to(ROOT)}`.
- Baseline provenance: `{baseline_manifest['source_provenance']['git_commit']}` / tree `{baseline_manifest['source_provenance']['git_tree']}`.
- Ablation provenance: `{ablation_manifest['source_provenance']['git_commit']}` / tree `{ablation_manifest['source_provenance']['git_tree']}`.
- E2E: `artifacts/e2e_scenarios/20260916T115000Z`.
- Confirmation: `artifacts/confirmation_experiment/20261006T034141939726Z`.
"""
    OUT_DOC.write_text(text, encoding="utf-8")
    print(OUT_DOC)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
