"""Run a reproducible confirmation and stale-snapshot experiment.

The runner never writes to the student or ontology source files.  Stale cases
change only the capability result in memory during confirmation, reproducing a
source-version mismatch without contaminating the experimental dataset.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.agent import pipeline as pipeline_module
from backend.app.agent.pipeline import AgentPipeline
from backend.app.config import Config
from backend.app.schemas import FeedbackRequest, PlanningRequest, RankingResult
from backend.app.services.grounded_explanation_service import ranking_hash
from backend.app.services.ontology_evidence_service import OntologyEvidenceService
from backend.app.services.recommendation_engine import RecommendationEngine
from backend.app.services.student_data_service import StudentDataService

PROTOCOL = "confirmation-freshness-v1"
CONDITIONS = ("unchanged", "student_stale", "knowledge_stale")


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def pseudonym(student_id: str) -> str:
    return "PSEUDO-" + sha256(student_id.encode("utf-8")).hexdigest()[:10].upper()


def redact(value: object, replacements: dict[str, str]) -> object:
    """Remove direct identifiers before an artifact is written."""
    if isinstance(value, dict):
        return {key: redact(item, replacements) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item, replacements) for item in value]
    if isinstance(value, tuple):
        return [redact(item, replacements) for item in value]
    if isinstance(value, str):
        for original, replacement in replacements.items():
            value = value.replace(original, replacement)
    return value


def profile_group(profile) -> str:
    specialization = str(profile.specialization or "").casefold()
    goal = str(profile.study_goal or "").casefold()
    if profile.current_semester >= 7:
        return "near_graduation"
    if profile.failed_courses:
        return "retake_or_debt"
    if specialization and "chưa chọn" not in specialization:
        return "specialization"
    if "vượt" in goal or "vuot" in goal:
        return "accelerated_or_high_load"
    return "on_track"


def requested_credits(profile) -> int:
    return 18 if profile_group(profile) in {"near_graduation", "accelerated_or_high_load"} else 15


@contextmanager
def stale_probe(condition: str, marker: str):
    """Inject one changed source version only while Confirm refreshes snapshots."""
    student_loader = pipeline_module.load_student_context
    knowledge_loader = pipeline_module.load_knowledge_context
    injected = {"student": False, "knowledge": False}

    def changed_student(context, *args, **kwargs):
        result = student_loader(context, *args, **kwargs)
        if condition == "student_stale" and context.call_id.startswith("CALL_REFRESH_STUDENT_") and not injected["student"]:
            snapshot = result.output.student_snapshot.model_copy(update={
                "student_version": f"{result.output.student_snapshot.student_version}-probe-{marker}"
            })
            injected["student"] = True
            return result.model_copy(update={"output": result.output.model_copy(update={"student_snapshot": snapshot})})
        return result

    def changed_knowledge(context, *args, **kwargs):
        result = knowledge_loader(context, *args, **kwargs)
        if condition == "knowledge_stale" and context.call_id.startswith("CALL_REFRESH_KNOWLEDGE_") and not injected["knowledge"]:
            snapshot = result.output.knowledge_snapshot
            versions = snapshot.versions.model_copy(update={
                "ontology_version": f"{snapshot.versions.ontology_version}-probe-{marker}"
            })
            injected["knowledge"] = True
            return result.model_copy(update={"output": result.output.model_copy(update={
                "knowledge_snapshot": snapshot.model_copy(update={"versions": versions})
            })})
        return result

    pipeline_module.load_student_context = changed_student
    pipeline_module.load_knowledge_context = changed_knowledge
    try:
        yield injected
    finally:
        pipeline_module.load_student_context = student_loader
        pipeline_module.load_knowledge_context = knowledge_loader


def make_pipeline() -> AgentPipeline:
    students = StudentDataService(Config.STUDENT_DATA_JSON, Config.STUDENT_DATA_CSV)
    engine = RecommendationEngine(Config.ONTOLOGY_PATH, beam_width=Config.BEAM_WIDTH,
        min_credits=Config.REGISTER_MIN_CREDITS, max_credits=Config.REGISTER_MAX_CREDITS,
        elective_quotas=dict(Config.ELECTIVE_QUOTAS))
    return AgentPipeline(students, engine, OntologyEvidenceService(Config.ONTOLOGY_PATH))


def run_case(pipeline: AgentPipeline, profile, condition: str, case_id: str, output_dir: Path) -> dict:
    start = perf_counter()
    request = PlanningRequest(request_id=f"confirmation-{case_id}", student_id=profile.student_id,
        target_term_id="next-term", goal="accelerated" if "vượt" in str(profile.study_goal).casefold() else "on_time",
        target_credits=requested_credits(profile))
    initial = pipeline.run_planning_flow(request)
    replacement = {profile.student_id: pseudonym(profile.student_id), profile.name: "ANONYMIZED"}
    case_dir = output_dir / case_id
    case_dir.mkdir()
    write_json(case_dir / "initial.json", redact(initial, replacement))
    row = {"case_id": case_id, "anonymous_student_id": pseudonym(profile.student_id), "stratum": profile_group(profile),
           "condition": condition, "initial_status": initial.get("status"), "confirmation_attempted": False,
           "confirmed": False, "confirmation_refresh_required": False, "unsafe_confirmation": False,
           "final_validation_status": None, "parent_run_id_present": False, "elapsed_seconds": None}
    if initial.get("status") != "awaiting_feedback" or not initial.get("ranking", {}).get("recommended_plan_id"):
        row["outcome"] = "no_feedback_ready_plan"
        row["elapsed_seconds"] = round(perf_counter() - start, 6)
        write_json(case_dir / "summary.json", row)
        return row

    feedback = FeedbackRequest(feedback_id=f"confirmation-{case_id}-accept", run_id=initial["run_id"],
        displayed_result_hash=ranking_hash(RankingResult.model_validate(initial["ranking"])), actor_pseudonym="experiment-advisor",
        actor_role="advisor", action="confirm", selected_plan_id=initial["ranking"]["recommended_plan_id"],
        created_at=datetime.now(timezone.utc))
    write_json(case_dir / "accept-feedback.json", feedback.model_dump(mode="json"))
    row["confirmation_attempted"] = True
    with stale_probe(condition, case_id) as injected:
        result = pipeline.confirm_from_feedback(initial, feedback)
    write_json(case_dir / "confirmation.json", redact(result, replacement))
    row.update({
        "outcome": result.get("status"), "confirmed": result.get("status") == "confirmed",
        "confirmation_refresh_required": bool(result.get("confirmation_refresh_required")),
        "parent_run_id_present": bool(result.get("parent_run_id")), "stale_injected": injected,
        "final_validation_status": (result.get("confirmation") or {}).get("validation", {}).get("status"),
    })
    row["unsafe_confirmation"] = condition != "unchanged" and row["confirmed"]
    row["elapsed_seconds"] = round(perf_counter() - start, 6)
    write_json(case_dir / "summary.json", row)
    return row


def select_profiles(service: StudentDataService, limit: int) -> list:
    buckets: dict[str, list] = {}
    for profile in sorted(service.get_all_students(force_reload=True), key=lambda item: item.student_id):
        buckets.setdefault(profile_group(profile), []).append(profile)
    selected, index = [], 0
    groups = sorted(buckets)
    while len(selected) < limit and any(buckets.values()):
        group = groups[index % len(groups)]
        if buckets[group]: selected.append(buckets[group].pop(0))
        index += 1
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description="Confirmation and anti-stale experiment")
    parser.add_argument("--limit", type=int, default=20, help="Maximum profiles (default: 20)")
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    if not 1 <= args.limit <= 20:
        parser.error("--limit must be between 1 and 20")
    run_dir = args.output_dir or ROOT / "artifacts" / "confirmation_experiment" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_dir.mkdir(parents=True, exist_ok=False)
    service = StudentDataService(Config.STUDENT_DATA_JSON, Config.STUDENT_DATA_CSV)
    all_profiles = service.get_all_students(force_reload=True)
    profiles = select_profiles(service, len(all_profiles))
    normal = min(12, args.limit)
    student_stale = min(4, max(0, args.limit - normal))
    conditions = ["unchanged"] * normal + ["student_stale"] * student_stale + ["knowledge_stale"] * (args.limit - normal - student_stale)
    manifest = {"protocol": PROTOCOL, "created_at": datetime.now(timezone.utc).isoformat(), "profile_target": args.limit,
                "conditions": Counter(conditions), "source_mutated": False,
                "selection": "deterministic round-robin stratification; non-feedback-ready profiles are replaced"}
    write_json(run_dir / "manifest.json", manifest)
    pipeline = make_pipeline()
    rows, skipped = [], []
    for attempt, profile in enumerate(profiles, start=1):
        if len(rows) >= len(conditions): break
        condition = conditions[len(rows)]
        case_id = f"TRY-{attempt:03d}"
        print(f"[{case_id}] {condition} ({profile_group(profile)})", flush=True)
        try:
            row = run_case(pipeline, profile, condition, case_id, run_dir)
            if row.get("confirmation_attempted"):
                row["analysis_case_id"] = f"C-{len(rows) + 1:02d}"
                rows.append(row)
            else:
                skipped.append(row)
        except Exception as exc:
            skipped.append({"case_id": case_id, "anonymous_student_id": pseudonym(profile.student_id), "stratum": profile_group(profile),
                         "condition": condition, "outcome": "runner_error", "error": str(exc), "confirmation_attempted": False})
    attempted = [row for row in rows if row.get("confirmation_attempted")]
    unchanged = [row for row in attempted if row["condition"] == "unchanged"]
    stale = [row for row in attempted if row["condition"] != "unchanged"]
    summary = {"protocol": PROTOCOL, "cases": rows, "skipped_profiles": skipped, "metrics": {
        "feedback_ready_coverage": len(attempted) / (len(rows) + len(skipped)) if rows or skipped else 0,
        "confirmation_success_rate": sum(row["confirmed"] for row in unchanged) / len(unchanged) if unchanged else None,
        "final_validation_pass_rate": sum(row["final_validation_status"] == "valid" for row in unchanged) / len(unchanged) if unchanged else None,
        "stale_detection_rate": sum(row["confirmation_refresh_required"] for row in stale) / len(stale) if stale else None,
        "unsafe_confirmation_rate": sum(row["unsafe_confirmation"] for row in stale) / len(stale) if stale else None,
        "refresh_lineage_rate": sum(row["parent_run_id_present"] for row in stale) / len(stale) if stale else None,
    }}
    write_json(run_dir / "summary.json", summary)
    lines = ["# Confirmation & freshness experiment", "", f"- Protocol: `{PROTOCOL}`", f"- Confirmation cases: {len(rows)}", f"- Replaced non-feedback-ready profiles: {len(skipped)}", "",
             "| Metric | Value |", "|---|---:|"]
    for key, value in summary["metrics"].items():
        lines.append(f"| {key} | {'N/A' if value is None else f'{value:.2%}'} |")
    lines += ["", "| Case | Stratum | Condition | Outcome |", "|---|---|---|---|"]
    lines += [f"| {row.get('analysis_case_id', row['case_id'])} | {row['stratum']} | {row['condition']} | {row.get('outcome')} |" for row in rows]
    (run_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
