"""Run the Agent pipeline over every anonymised student profile.

This is the Stage 3 descriptive batch, not an outcome/accuracy experiment.
It uses a fixed seed and the same Agent, generator, and Standard Validator
configuration for each profile.  Source student records are never modified and
identifiers/names are replaced before any per-profile artifact is written.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from statistics import mean
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.agent.orchestrator import AgentOrchestrator
from backend.app.agent.pipeline import AgentPipeline
from backend.app.config import Config
from backend.app.schemas import PlanningRequest
from backend.app.services.ontology_evidence_service import OntologyEvidenceService
from backend.app.services.recommendation_engine import RecommendationEngine
from backend.app.services.student_data_service import StudentDataService


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def source_hash(path: Path) -> str:
    return "sha256:" + sha256(path.read_bytes()).hexdigest()


def goal_for(record: dict) -> str:
    """Map the persisted Vietnamese goal to the PlanningRequest contract."""
    value = str(record.get("study_goal", "")).casefold()
    return "accelerated" if "vượt" in value or "vuot" in value else "on_time"


def anonymised_record(record: dict, pseudonym: str) -> dict:
    """Return the minimum faithful profile record with no direct identifiers."""
    fixture = dict(record)
    fixture["student_id"] = pseudonym
    fixture["name"] = "ANONYMIZED"
    fixture["academic_class"] = "ANONYMIZED"
    return fixture


def violation_histogram(result: dict) -> Counter[str]:
    counter: Counter[str] = Counter()
    for validation in result.get("validations") or []:
        for violation in validation.get("violations") or []:
            if violation.get("constraint_id"):
                counter[violation["constraint_id"]] += 1
    return counter


def evidence_coverage(result: dict) -> tuple[int, int]:
    decisions = with_evidence = 0
    for validation in result.get("validations") or []:
        for rule in validation.get("rule_checks") or []:
            decisions += 1
            with_evidence += bool(rule.get("evidence_ids"))
    return decisions, with_evidence


def diversity_values(result: dict) -> list[float]:
    ranking = result.get("ranking") or {}
    return [float(item["distance"]) for item in ranking.get("pairwise_diversity") or []]


def artifact_complete(result: dict) -> bool:
    if not all(result.get(key) for key in ("request", "student_snapshot", "knowledge_snapshot")):
        return False
    validations = result.get("validations") or []
    return bool(validations) and any(
        item.get("evidence") or any(check.get("evidence_ids") for check in item.get("rule_checks") or [])
        for item in validations
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 3 anonymised Agent batch")
    parser.add_argument("--limit", type=int, default=0, help="Run only the first N sorted source records (0 = all).")
    parser.add_argument("--target-credits", type=float, default=18.0)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if args.limit < 0 or args.target_credits <= 0:
        parser.error("--limit must be >= 0 and --target-credits must be positive")

    source_path = Path(Config.STUDENT_DATA_JSON)
    records = json.loads(source_path.read_text(encoding="utf-8"))
    records = sorted(records, key=lambda item: str(item.get("student_id", "")))
    if args.limit:
        records = records[:args.limit]
    if not records:
        raise ValueError("No source profiles selected")

    run_dir = ROOT / "artifacts" / "anonymized_batch" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir.mkdir(parents=True)
    engine = RecommendationEngine(
        Config.ONTOLOGY_PATH, beam_width=Config.BEAM_WIDTH,
        min_credits=Config.REGISTER_MIN_CREDITS, max_credits=Config.REGISTER_MAX_CREDITS,
        elective_quotas=Config.ELECTIVE_QUOTAS,
    )
    evidence = OntologyEvidenceService(Config.ONTOLOGY_PATH)
    manifest = {
        "protocol": "stage3-anonymized-agent-batch-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_data_sha256": source_hash(source_path),
        "source_profile_count": len(records),
        "source_ids_are_not_exported": True,
        "target_term_id": "next-term",
        "target_credits": args.target_credits,
        "seed": args.seed,
        "beam_width": Config.BEAM_WIDTH,
        "validator": "StandardValidator",
        "limitations": [
            "next-term is a system proxy, not a mapped institutional calendar.",
            "Academic Risk is a proxy and not an official academic warning.",
            "This batch measures pipeline behaviour, not student outcomes or policy completeness.",
        ],
    }
    write_json(run_dir / "manifest.json", manifest)

    rows: list[dict] = []
    knowledge_source_manifest: dict | None = None
    statuses: Counter[str] = Counter()
    violations: Counter[str] = Counter()
    candidate_count = valid_count = evidence_total = evidence_linked = 0
    diversity: list[float] = []
    latencies: list[float] = []

    for index, record in enumerate(records, start=1):
        pseudonym = f"B{index:04d}"
        case_dir = run_dir / pseudonym
        case_dir.mkdir()
        fixture = anonymised_record(record, pseudonym)
        fixture_path = case_dir / "student_fixture.json"
        write_json(fixture_path, [fixture])
        service = StudentDataService(str(fixture_path), Config.STUDENT_DATA_CSV)
        pipeline = AgentPipeline(service, engine, evidence, AgentOrchestrator(seed=args.seed))
        request = PlanningRequest(
            request_id=f"BATCH-{pseudonym}", student_id=pseudonym,
            target_term_id="next-term", goal=goal_for(record), target_credits=args.target_credits,
        )
        try:
            result = pipeline.run_planning_flow(request)
        except Exception as exc:  # Preserve the batch and expose a per-case diagnostic.
            result = {"success": False, "status": "runner_error", "error": {"message": str(exc)}}
        write_json(case_dir / "result.json", result)
        if knowledge_source_manifest is None:
            knowledge_source_manifest = (result.get("knowledge_snapshot") or {}).get("source_manifest")

        candidate_n = len(result.get("candidates") or [])
        valid_n = sum(item.get("status") == "valid" for item in result.get("validations") or [])
        decisions, linked = evidence_coverage(result)
        distances = diversity_values(result)
        per_case_violations = violation_histogram(result)
        row = {
            "profile": pseudonym,
            "status": result.get("status", "runner_error"),
            "success": bool(result.get("success")),
            "candidate_count": candidate_n,
            "valid_candidates": valid_n,
            "latency_seconds": result.get("elapsed_seconds"),
            "evidence_rule_decisions": decisions,
            "evidence_linked_decisions": linked,
            "evidence_coverage": round(linked / decisions, 4) if decisions else None,
            "pairwise_diversity_count": len(distances),
            "pairwise_diversity_mean": round(mean(distances), 4) if distances else None,
            "violation_histogram": dict(per_case_violations),
            "artifact_complete": artifact_complete(result),
        }
        write_json(case_dir / "case_summary.json", row)
        rows.append(row)
        statuses[row["status"]] += 1
        violations.update(per_case_violations)
        candidate_count += candidate_n
        valid_count += valid_n
        evidence_total += decisions
        evidence_linked += linked
        diversity.extend(distances)
        if row["latency_seconds"] is not None:
            latencies.append(float(row["latency_seconds"]))

    manifest["knowledge_source_manifest"] = knowledge_source_manifest
    write_json(run_dir / "manifest.json", manifest)
    summary = {
        "manifest": manifest,
        "profiles": rows,
        "status_histogram": dict(statuses),
        "validity": {
            "candidate_count": candidate_count,
            "valid_candidates": valid_count,
            "validity_rate": round(valid_count / candidate_count, 4) if candidate_count else 0.0,
        },
        "violation_histogram": dict(violations),
        "diversity": {"pairwise_count": len(diversity), "mean": round(mean(diversity), 4) if diversity else None},
        "latency": {"mean_seconds": round(mean(latencies), 4) if latencies else None, "max_seconds": round(max(latencies), 4) if latencies else None},
        "evidence_coverage": {"rule_decisions": evidence_total, "linked_decisions": evidence_linked,
                              "coverage": round(evidence_linked / evidence_total, 4) if evidence_total else 0.0},
        "artifact_complete": {"complete": sum(row["artifact_complete"] for row in rows), "total": len(rows)},
    }
    write_json(run_dir / "summary.json", summary)
    report = ["# Stage 3 anonymized Agent batch", "", f"- Profiles: **{len(rows)}**", f"- Statuses: `{dict(statuses)}`",
              f"- Validity: **{valid_count}/{candidate_count}** ({summary['validity']['validity_rate']:.2%})",
              f"- Evidence coverage: **{summary['evidence_coverage']['coverage']:.2%}** ({evidence_linked}/{evidence_total})",
              f"- Mean pairwise diversity: **{summary['diversity']['mean']}**", f"- Latency mean/max: **{summary['latency']['mean_seconds']}s / {summary['latency']['max_seconds']}s**",
              f"- Complete artifacts: **{summary['artifact_complete']['complete']}/{len(rows)}**", "", "## Violations", "",
              "| Rule | Count |", "|---|---:|"]
    report.extend(f"| {key} | {value} |" for key, value in sorted(violations.items()))
    report.extend(["", "Each case artifact is pseudonymised; source student IDs and names are not exported.",
                   "These results describe system behaviour under the stated proxy policies, not official academic decisions or student outcome accuracy."])
    (run_dir / "REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(run_dir.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
