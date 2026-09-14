"""Run the controlled, anonymised multi-profile E2E scenario matrix.

This runner executes the full Agent flow for every scenario in
``experiments/e2e_scenario_matrix.json`` and writes per-case artifacts plus
a consolidated ``summary.json`` and ``REPORT.md``. Pass criteria are
strict: status must match contract, the negative-probe must actually trigger
the expected rule, the re-plan (when applicable) must produce the expected
post-adjustment state, and confirm (when required) must reach ``confirmed``.

The script also aggregates violation histograms, evidence coverage, latency,
controlled vs data-derived fixture split and overall validity rate so the
batch can be reviewed without re-reading individual ``result.json`` files.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.agent.pipeline import AgentPipeline
from backend.app.config import Config
from backend.app.schemas import (
    CandidateCourse,
    CandidatePlan,
    FeedbackOperation,
    FeedbackRequest,
    KnowledgeSnapshot,
    PlanningRequest,
    RankingResult,
    StudentSnapshot,
)
from backend.app.services.ontology_evidence_service import OntologyEvidenceService
from backend.app.services.grounded_explanation_service import ranking_hash
from backend.app.services.recommendation_engine import RecommendationEngine
from backend.app.services.student_data_service import StudentDataService
from backend.app.validation.validator import StandardValidator


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _build_plan_for_probe(
    code: str, catalog: dict, student: StudentSnapshot, multi: bool
) -> tuple | None:
    """Build a probe plan for a single course or a 2-course bundle.

    For multi-course probes (corequisite / prerequisite):
    - corequisite: filler must NOT have any corequisites, otherwise the plan
      satisfies the coreq before the validator even checks it.
    - prerequisite: any unrelated filler works (prereqs are checked against
      completed_courses, not the plan).
    """
    if not multi:
        return (CandidateCourse(
            course_code=code,
            credits=float(catalog.get(code, {}).get("credits", 3)),
        ),)

    # 2-course bundle for corequisite: pick a filler without corequisites.
    # 2-course bundle for prerequisite: any filler works.
    filler = None
    codes = sorted(catalog)
    for other in codes:
        if other == code:
            continue
        if other in student.completed_courses:
            continue
        if catalog.get(other, {}).get("corequisites", []):
            continue  # filler must not satisfy or introduce another coreq rule
        filler = other
        break
    if filler is None:
        return None
    return (
        CandidateCourse(course_code=code, credits=float(catalog.get(code, {}).get("credits", 3))),
        CandidateCourse(course_code=filler, credits=float(catalog.get(filler, {}).get("credits", 3))),
    )


def invalid_probe(result: dict, engine: RecommendationEngine, evidence: OntologyEvidenceService, expected: str) -> dict:
    """Search a real catalog candidate that deterministically triggers the expected validator rule.

    Strategy by rule:
    - ``completed_course_retake``: single-course probe over the student's
      ``completed_courses`` set.
    - ``corequisite``: 2-course probe where the first course carries the rule
      and the second is an unrelated filler. We test against a synthetic
      student snapshot whose ``completed_courses`` does NOT contain the
      target's corequisite, otherwise the rule would already be satisfied
      via history for every on-track student.
    - ``prerequisite``: 2-course probe with any unrelated filler.
    - All others: single-course probe over the catalog.

    The probe succeeds only when the validator actually reports the expected
    ``constraint_id`` in its ``violations`` list.
    """
    student = StudentSnapshot.model_validate(result["student_snapshot"])
    knowledge = KnowledgeSnapshot.model_validate(result["knowledge_snapshot"])
    validator = StandardValidator(evidence, min_credits=engine.min_credits, max_credits=engine.max_credits)
    catalog = engine.course_data

    if expected == "completed_course_retake":
        candidates = [(code, student) for code in list(student.completed_courses)]
    elif expected == "corequisite":
        candidates = []
        for code in sorted(catalog):
            coreqs = set(catalog.get(code, {}).get("corequisites", []) or [])
            if not coreqs:
                continue
            # Build a probe snapshot where the target's coreq is missing.
            stripped = frozenset(
                c for c in student.completed_courses
                if c != code and c not in coreqs
            )
            probe_student = student.model_copy(update={"completed_courses": stripped,
                "student_id": f"probe-{code}"})
            candidates.append((code, probe_student))
    elif expected == "prerequisite":
        candidates = []
        for code in sorted(catalog):
            prereqs = catalog.get(code, {}).get("prereqs", []) or []
            if not prereqs:
                continue
            stripped = frozenset(c for c in student.completed_courses if c not in prereqs)
            probe_student = student.model_copy(update={"completed_courses": stripped,
                "student_id": f"probe-{code}"})
            candidates.append((code, probe_student))
    else:
        candidates = [(code, student) for code in sorted(catalog)]

    for code, probe_student in candidates[:200]:
        multi = expected in {"corequisite", "prerequisite"}
        courses = _build_plan_for_probe(code, catalog, probe_student, multi)
        if courses is None:
            continue
        plan = CandidatePlan(
            plan_id=f"probe-{expected}-{code}",
            plan_version="e2e-probe-v1",
            request_id=result["request"]["request_id"],
            student_id=probe_student.student_id,
            target_term_id="next-term",
            knowledge_versions=knowledge.versions,
            plan_type="safe",
            courses=courses,
        )
        checked = validator.validate(plan, probe_student, knowledge)
        violations = [item.constraint_id for item in checked.violations]
        if expected in violations:
            return {
                "passed": True,
                "expected_violation": expected,
                "course_code": code,
                "validation": checked.model_dump(mode="json"),
            }
    return {
        "passed": False,
        "expected_violation": expected,
        "diagnostic": "No catalog probe triggered this rule for the scenario snapshot.",
    }


def _has_request_snapshot_validation_evidence_artifact(result: dict) -> dict:
    """Check the artefact has the four pieces needed for full traceability."""
    missing: list[str] = []
    if not result.get("request"):
        missing.append("request")
    if not result.get("student_snapshot"):
        missing.append("student_snapshot")
    if not result.get("knowledge_snapshot"):
        missing.append("knowledge_snapshot")
    validations = result.get("validations") or []
    if not validations:
        missing.append("validation")
    has_evidence = False
    for v in validations:
        if v.get("evidence"):
            has_evidence = True
            break
        for rc in v.get("rule_checks", []):
            if rc.get("evidence_ids"):
                has_evidence = True
                break
        if has_evidence:
            break
    if not has_evidence:
        missing.append("evidence")
    return {"complete": not missing, "missing": missing}


def _violation_histogram(result: dict) -> dict[str, int]:
    """Tally violations across all plan validations."""
    counter: Counter[str] = Counter()
    for v in result.get("validations") or []:
        for item in v.get("violations") or []:
            cid = item.get("constraint_id")
            if cid:
                counter[cid] += 1
    return dict(counter)


def _evidence_coverage(result: dict) -> dict[str, float | int]:
    """Compute evidence coverage: fraction of rule decisions with at least one evidence_id."""
    total = 0
    with_evidence = 0
    for v in result.get("validations") or []:
        for rc in v.get("rule_checks", []):
            total += 1
            if rc.get("evidence_ids"):
                with_evidence += 1
    if total == 0:
        return {"total_rule_decisions": 0, "decisions_with_evidence": 0, "coverage": 0.0}
    return {
        "total_rule_decisions": total,
        "decisions_with_evidence": with_evidence,
        "coverage": round(with_evidence / total, 4),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", action="append", dest="scenario_ids", help="Run only one or more scenario IDs")
    args = parser.parse_args()
    matrix = json.loads((ROOT / "experiments" / "e2e_scenario_matrix.json").read_text(encoding="utf-8"))
    source = json.loads(Path(Config.STUDENT_DATA_JSON).read_text(encoding="utf-8"))
    by_id = {item["student_id"]: item for item in source}
    folder = ROOT / "artifacts" / "e2e_scenarios" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder.mkdir(parents=True)
    rows: list[dict] = []
    knowledge_source_manifest: dict | None = None
    scenarios = [item for item in matrix["scenarios"] if not args.scenario_ids or item["id"] in args.scenario_ids]
    if args.scenario_ids and len(scenarios) != len(set(args.scenario_ids)):
        raise ValueError("Unknown scenario ID")
    for scenario in scenarios:
        raw = dict(by_id[scenario["source_student_id"]])
        raw["student_id"] = scenario["id"]
        raw["name"] = "ANONYMIZED"
        if "specialization" in scenario:
            raw["specialization"] = scenario["specialization"]
        case_dir = folder / scenario["id"]
        case_dir.mkdir()
        fixture = case_dir / "student_fixture.json"
        write_json(fixture, [raw])
        quotas = dict(Config.ELECTIVE_QUOTAS)
        quotas.update(scenario.get("quota_override", {}))
        engine = RecommendationEngine(
            Config.ONTOLOGY_PATH,
            beam_width=Config.BEAM_WIDTH,
            min_credits=Config.REGISTER_MIN_CREDITS,
            max_credits=Config.REGISTER_MAX_CREDITS,
            elective_quotas=quotas,
        )
        pipeline = AgentPipeline(
            StudentDataService(str(fixture), Config.STUDENT_DATA_CSV),
            engine,
            OntologyEvidenceService(Config.ONTOLOGY_PATH),
        )
        request = PlanningRequest(
            request_id=scenario["id"],
            student_id=scenario["id"],
            target_term_id="next-term",
            goal=scenario["goal"],
            target_credits=scenario["target_credits"],
        )
        result = pipeline.run_planning_flow(request)
        write_json(case_dir / "result.json", result)
        if knowledge_source_manifest is None:
            knowledge_source_manifest = (result.get("knowledge_snapshot") or {}).get("source_manifest")
        probe = invalid_probe(result, engine, pipeline.evidence, scenario["expected_violation"])
        write_json(case_dir / "invalid-probe.json", probe)
        replan = confirmation = None
        if result.get("status") == "awaiting_feedback":
            feedback = FeedbackRequest(
                feedback_id=f"{scenario['id']}-modify",
                run_id=result["run_id"],
                displayed_result_hash=ranking_hash(RankingResult.model_validate(result["ranking"])),
                actor_pseudonym="e2e-advisor",
                actor_role="advisor",
                action="modify",
                selected_plan_id=result["ranking"]["recommended_plan_id"],
                operations=(FeedbackOperation(kind="change_goal", goal=scenario["goal"]),),
                reason="Controlled E2E re-planning verification.",
                created_at=datetime.now(timezone.utc),
            )
            replan = pipeline.replan_from_feedback(result, feedback)
            write_json(case_dir / "replanned.json", replan)
            if replan.get("status") == "awaiting_feedback":
                confirm = FeedbackRequest(
                    feedback_id=f"{scenario['id']}-confirm",
                    run_id=replan["run_id"],
                    displayed_result_hash=ranking_hash(RankingResult.model_validate(replan["ranking"])),
                    actor_pseudonym="e2e-advisor",
                    actor_role="advisor",
                    action="confirm",
                    selected_plan_id=replan["ranking"]["recommended_plan_id"],
                    created_at=datetime.now(timezone.utc),
                )
                confirmation = pipeline.confirm_from_feedback(replan, confirm)
                write_json(case_dir / "confirmed.json", confirmation)

        # ---- Strict pass criteria -----------------------------------------------
        status_ok = result["status"] in scenario["expected_statuses"]
        probe_ok = probe["passed"]
        artifact_check = _has_request_snapshot_validation_evidence_artifact(result)

        # Re-plan only runs when the initial plan reached awaiting_feedback.
        replan_status = replan.get("status") if replan else None
        if result["status"] == "awaiting_feedback":
            replan_ok: bool | None = (
                replan_status in scenario["expected_statuses"] if replan_status else False
            )
        else:
            replan_ok = None  # not applicable

        # Confirm only when scenario.confirm is true.
        confirm_status = confirmation.get("status") if confirmation else None
        if scenario.get("confirm"):
            confirm_ok: bool | None = confirm_status == "confirmed"
        else:
            confirm_ok = None  # not required

        criteria = {
            "status_ok": status_ok,
            "invalid_probe_passed": probe_ok,
            "replan_ok": replan_ok,
            "confirm_ok": confirm_ok,
            "artifact_complete": artifact_check["complete"],
        }
        passed_contract = all(value for value in criteria.values() if value is not None)

        row = {
            "scenario_id": scenario["id"],
            "label": scenario["label"],
            "controlled_fixture": scenario.get("controlled_fixture", False),
            "status": result["status"],
            "expected_statuses": scenario["expected_statuses"],
            "valid_candidates": sum(v["status"] == "valid" for v in result.get("validations", [])),
            "candidate_count": len(result.get("candidates", [])),
            "latency_seconds": result.get("elapsed_seconds"),
            "expected_invalid_probe": scenario["expected_violation"],
            "invalid_probe_passed": probe_ok,
            "invalid_probe_course_code": probe.get("course_code"),
            "replan_status": replan_status,
            "confirm_required": scenario.get("confirm", False),
            "confirm_status": confirm_status,
            "artifact_complete": artifact_check["complete"],
            "artifact_missing": artifact_check["missing"],
            "criteria": criteria,
            "passed_contract": passed_contract,
            "violation_histogram": _violation_histogram(result),
            "evidence_coverage": _evidence_coverage(result),
            "replan_criterion": scenario.get("replan"),
        }
        write_json(case_dir / "scenario-contract.json", {"scenario": scenario, "result_summary": row})
        rows.append(row)

    # ---- Aggregate metrics -----------------------------------------------------
    total = len(rows)
    passed = sum(1 for r in rows if r["passed_contract"])
    validity_attempts = sum(r["candidate_count"] for r in rows)
    validity_valid = sum(r["valid_candidates"] for r in rows)
    validity_rate = round(validity_valid / validity_attempts, 4) if validity_attempts else 0.0
    violation_counter: Counter[str] = Counter()
    for r in rows:
        violation_counter.update(r["violation_histogram"])
    probe_pass = sum(1 for r in rows if r["invalid_probe_passed"])
    replan_total = sum(1 for r in rows if r["criteria"]["replan_ok"] is not None)
    replan_pass = sum(1 for r in rows if r["criteria"]["replan_ok"] is True)
    confirm_total = sum(1 for r in rows if r["criteria"]["confirm_ok"] is not None)
    confirm_pass = sum(1 for r in rows if r["criteria"]["confirm_ok"] is True)
    controlled_count = sum(1 for r in rows if r["controlled_fixture"])
    data_derived_count = total - controlled_count
    coverage_values = [
        r["evidence_coverage"]["coverage"]
        for r in rows
        if r["evidence_coverage"]["total_rule_decisions"]
    ]
    overall_coverage = round(sum(coverage_values) / len(coverage_values), 4) if coverage_values else 0.0
    latency_vals = [r["latency_seconds"] for r in rows if r["latency_seconds"] is not None]
    latency_avg = round(sum(latency_vals) / len(latency_vals), 4) if latency_vals else 0.0
    latency_max = round(max(latency_vals), 4) if latency_vals else 0.0

    summary = {
        "matrix_version": matrix["version"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "knowledge_source_manifest": knowledge_source_manifest,
        "cases": rows,
        "passed": passed,
        "total": total,
        "controlled_fixture_count": controlled_count,
        "data_derived_fixture_count": data_derived_count,
        "validity": {
            "candidate_attempts": validity_attempts,
            "valid_candidates": validity_valid,
            "validity_rate": validity_rate,
        },
        "violation_histogram": dict(violation_counter),
        "invalid_probe": {"passed": probe_pass, "total": total},
        "replan": {"passed": replan_pass, "total": replan_total},
        "confirm": {"passed": confirm_pass, "total": confirm_total},
        "evidence_coverage_avg": overall_coverage,
        "latency": {"avg_seconds": latency_avg, "max_seconds": latency_max},
    }
    write_json(folder / "summary.json", summary)

    # ---- Markdown report -------------------------------------------------------
    lines = ["# E2E multi-profile summary", ""]
    lines.append("| Case | Status | Contract | Valid/Cand | Probe | Replan | Confirm | Latency (s) | Evidence cov. |")
    lines.append("|---|---|---|---:|---|---:|---:|---:|---:|")
    for r in rows:
        crit = r["criteria"]
        replan_m = "—" if crit["replan_ok"] is None else ("PASS" if crit["replan_ok"] else f"FAIL({r.get('replan_status')})")
        confirm_m = "—" if crit["confirm_ok"] is None else ("PASS" if crit["confirm_ok"] else f"FAIL({r.get('confirm_status')})")
        cov = r["evidence_coverage"]["coverage"]
        lines.append(
            f"| {r['scenario_id']} — {r['label']} | {r['status']} | "
            f"{'PASS' if r['passed_contract'] else 'FAIL'} | "
            f"{r['valid_candidates']}/{r['candidate_count']} | "
            f"{'PASS' if r['invalid_probe_passed'] else 'FAIL'} | "
            f"{replan_m} | {confirm_m} | "
            f"{r['latency_seconds'] or 0:.2f} | {cov:.0%} |"
        )
    lines.append("")
    lines.append("## Aggregate metrics")
    lines.append("")
    lines.append(f"- Pass rate: **{passed}/{total}** ({round(passed / total * 100, 1) if total else 0}%)")
    lines.append(
        f"- Validity rate: **{validity_valid}/{validity_attempts}** ({validity_rate:.2%})"
    )
    lines.append(f"- Invalid probe pass rate: **{probe_pass}/{total}**")
    if replan_total:
        lines.append(f"- Re-plan pass rate (when applicable): **{replan_pass}/{replan_total}**")
    if confirm_total:
        lines.append(f"- Confirm pass rate (when required): **{confirm_pass}/{confirm_total}**")
    lines.append(f"- Average evidence coverage: **{overall_coverage:.2%}**")
    lines.append(f"- Latency avg / max: **{latency_avg:.2f}s / {latency_max:.2f}s**")
    lines.append(f"- Controlled fixtures: **{controlled_count}**; data-derived: **{data_derived_count}**")
    if violation_counter:
        lines.append("")
        lines.append("## Violation histogram")
        lines.append("")
        lines.append("| Rule | Count |")
        lines.append("|---|---:|")
        for rule_id, count in sorted(violation_counter.items(), key=lambda kv: (-kv[1], kv[0])):
            lines.append(f"| {rule_id} | {count} |")
    lines.append("")
    lines.append("Controlled fixtures are explicitly labelled and are not institutional policy data.")
    (folder / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(folder)
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
