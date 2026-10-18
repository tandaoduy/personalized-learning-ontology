"""Run a controlled, pseudonymised Agentic Re-planning experiment.

Each included profile first receives an initial plan.  The runner then creates
one deterministic advisor feedback item (exclude course, require course,
reduce credit load, or change ``on_time`` to ``accelerated``) and executes the
identical AdjustmentRequest through two conditions:

* ``stateful``: ``AgentPipeline.replan_from_feedback`` retains the parent
  AgentState, feedback lineage, and iteration.
* ``stateless``: a newly-created pipeline receives the same request and
  adjustment, but no parent state.

The emitted artifacts use only experiment pseudonyms.  This is a controlled
systems experiment, not a claim about student outcomes or official policy.
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
from backend.app.schemas import AdjustmentRequest, FeedbackOperation, FeedbackRequest, PlanningRequest, RankingResult
from backend.app.services.grounded_explanation_service import ranking_hash
from backend.app.services.ontology_evidence_service import OntologyEvidenceService
from backend.app.services.recommendation_engine import RecommendationEngine
from backend.app.services.student_data_service import StudentDataService


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def source_hash(path: Path) -> str:
    return "sha256:" + sha256(path.read_bytes()).hexdigest()


def goal_for(record: dict) -> str:
    value = str(record.get("study_goal", "")).casefold()
    return "accelerated" if "vượt" in value or "vuot" in value else "on_time"


def anonymise(record: dict, pseudonym: str) -> dict:
    copy = dict(record)
    copy.update({"student_id": pseudonym, "name": "ANONYMIZED", "academic_class": "ANONYMIZED"})
    return copy


def make_pipeline(fixture_path: Path, seed: int, engine: RecommendationEngine,
                  evidence: OntologyEvidenceService) -> AgentPipeline:
    return AgentPipeline(
        StudentDataService(str(fixture_path), Config.STUDENT_DATA_CSV), engine,
        evidence, AgentOrchestrator(seed=seed),
    )


def plan_codes(result: dict) -> set[str]:
    ranking = result.get("ranking") or {}
    recommended = ranking.get("recommended_plan_id")
    for plan in result.get("candidates") or []:
        if plan.get("plan_id") == recommended:
            return {course["course_code"] for course in plan.get("courses") or []}
    return set()


def eligible_not_in_plan(result: dict, codes: set[str]) -> str | None:
    decisions = (result.get("course_space") or {}).get("decisions") or []
    eligible = sorted(
        decision["course_code"] for decision in decisions
        if decision.get("status") == "eligible" and decision.get("course_code") not in codes
    )
    return eligible[0] if eligible else None


def feedback_for(result: dict, request: PlanningRequest, ordinal: int) -> tuple[str, FeedbackOperation] | None:
    """Create an achievable-looking, deterministic controlled intervention.

    Course operations deliberately use codes from the displayed recommendation
    or its eligible course space.  Whether they are satisfiable remains an
    experimental outcome, and is never silently converted to a success.
    """
    codes = plan_codes(result)
    kinds = ("exclude_course", "require_course", "reduce_credits", "accelerate")
    for offset in range(len(kinds)):
        kind = kinds[(ordinal + offset) % len(kinds)]
        if kind == "exclude_course" and codes:
            return kind, FeedbackOperation(kind="remove", course_code=sorted(codes)[0])
        if kind == "require_course":
            course = eligible_not_in_plan(result, codes)
            if course:
                return kind, FeedbackOperation(kind="add", course_code=course)
        if kind == "reduce_credits" and request.target_credits > Config.REGISTER_MIN_CREDITS:
            return kind, FeedbackOperation(
                kind="change_target_credits",
                target_credits=max(float(Config.REGISTER_MIN_CREDITS), request.target_credits - 3),
            )
        if kind == "accelerate" and request.goal == "on_time":
            return kind, FeedbackOperation(kind="change_goal", goal="accelerated")
    return None


def evidence_coverage(result: dict) -> tuple[int, int]:
    total = linked = 0
    for validation in result.get("validations") or []:
        for check in validation.get("rule_checks") or []:
            total += 1
            linked += bool(check.get("evidence_ids"))
    return total, linked


def adjustment_satisfied(result: dict, adjustment: AdjustmentRequest) -> bool:
    if result.get("status") != "awaiting_feedback":
        return False
    plans = result.get("candidates") or []
    validations = result.get("validations") or []
    valid_ids = {item.get("plan_id") for item in validations if item.get("status") == "valid"}
    if not plans or not valid_ids:
        return False
    for plan in plans:
        codes = {course["course_code"] for course in plan.get("courses") or []}
        if plan.get("plan_id") not in valid_ids:
            return False
        if not set(adjustment.must_include).issubset(codes) or set(adjustment.must_exclude) & codes:
            return False
    request = result.get("request") or {}
    return ((adjustment.new_target_credits is None or request.get("target_credits") == adjustment.new_target_credits)
            and (adjustment.new_goal is None or request.get("goal") == adjustment.new_goal))


def condition_row(condition: str, result: dict, adjustment: AdjustmentRequest) -> dict:
    decisions, linked = evidence_coverage(result)
    validations = result.get("validations") or []
    return {
        "condition": condition,
        "status": result.get("status"),
        "valid_and_feedback_satisfied": adjustment_satisfied(result, adjustment),
        # A valid result has passed every unchanged StandardValidator rule;
        # feedback adds an adjustment but never relaxes prior hard constraints.
        "old_constraints_retained": bool(validations) and all(item.get("status") == "valid" for item in validations),
        "replanning_rounds": 1 if result.get("status") == "awaiting_feedback" else None,
        "iteration": result.get("iteration"),
        "latency_seconds": result.get("elapsed_seconds"),
        "evidence_rule_decisions": decisions,
        "evidence_linked_decisions": linked,
        "evidence_coverage": linked / decisions if decisions else None,
        "plan_codes": sorted(plan_codes(result)),
        "state_lineage_retained": bool(result.get("parent_run_id")),
    }


def aggregate(rows: list[dict]) -> dict:
    output = {}
    for condition in ("stateful", "stateless"):
        values = [row[condition] for row in rows]
        applicable = [item for item in values if item["status"] is not None]
        success = [item for item in applicable if item["valid_and_feedback_satisfied"]]
        retained = [item for item in applicable if item["old_constraints_retained"]]
        latencies = [float(item["latency_seconds"]) for item in applicable if item["latency_seconds"] is not None]
        coverages = [float(item["evidence_coverage"]) for item in applicable if item["evidence_coverage"] is not None]
        output[condition] = {
            "cases": len(applicable),
            "valid_and_feedback_satisfied": len(success),
            "success_rate": len(success) / len(applicable) if applicable else None,
            "old_constraints_retained": len(retained),
            "old_constraints_retention_rate": len(retained) / len(applicable) if applicable else None,
            "mean_replanning_rounds": mean([item["replanning_rounds"] for item in success]) if success else None,
            "mean_latency_seconds": mean(latencies) if latencies else None,
            "mean_evidence_coverage": mean(coverages) if coverages else None,
            "status_histogram": dict(Counter(item["status"] for item in applicable)),
        }
    paired = [(row["stateful"], row["stateless"]) for row in rows]
    output["paired"] = {
        "both_success": sum(a["valid_and_feedback_satisfied"] and b["valid_and_feedback_satisfied"] for a, b in paired),
        "stateful_only_success": sum(a["valid_and_feedback_satisfied"] and not b["valid_and_feedback_satisfied"] for a, b in paired),
        "stateless_only_success": sum(not a["valid_and_feedback_satisfied"] and b["valid_and_feedback_satisfied"] for a, b in paired),
        "both_failed": sum(not a["valid_and_feedback_satisfied"] and not b["valid_and_feedback_satisfied"] for a, b in paired),
    }
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Controlled stateful vs stateless Agentic Re-planning experiment")
    parser.add_argument("--profiles", type=int, default=100, help="Maximum feedback-ready profiles to include.")
    parser.add_argument("--target-credits", type=float, default=18.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--smoke", action="store_true", help="Run at most four profiles for a quick contract check.")
    args = parser.parse_args()
    if args.profiles <= 0 or args.target_credits <= 0:
        parser.error("--profiles and --target-credits must be positive")
    target = min(args.profiles, 4) if args.smoke else args.profiles

    source_path = Path(Config.STUDENT_DATA_JSON)
    records = sorted(json.loads(source_path.read_text(encoding="utf-8")), key=lambda item: str(item.get("student_id", "")))
    # Microseconds prevent two independently launched experiment processes from
    # ever sharing a run directory.
    run_dir = ROOT / "artifacts" / "agentic_replanning" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_dir.mkdir(parents=True)
    manifest = {
        "protocol": "agentic-replanning-stateful-vs-stateless-v1",
        "created_at": datetime.now(timezone.utc).isoformat(), "requested_profiles": target,
        "seed": args.seed, "target_credits": args.target_credits,
        "source_profile_count": len(records), "source_data_sha256": source_hash(source_path),
        "source_ids_are_not_exported": True,
        "conditions": {"stateful": "replan_from_feedback retains parent AgentState and lineage",
                       "stateless": "fresh pipeline receives identical normalized AdjustmentRequest without parent state"},
        "feedback_types": ["exclude_course", "require_course", "reduce_credits", "accelerate"],
        "outcomes": ["valid_and_feedback_satisfied", "replanning_rounds", "latency_seconds",
                     "old_constraints_retained", "evidence_coverage"],
        "limitations": ["One controlled feedback item is issued per profile; successful cases therefore require one re-planning round.",
                        "Curriculum and calendar policies remain experimental unless separately source-verified."],
    }
    write_json(run_dir / "manifest.json", manifest)

    rows: list[dict] = []
    skipped = Counter()
    # These services are read-only at experiment scope.  Pipelines receive a
    # new orchestrator and StudentDataService per condition; sharing ontology
    # parsing is an infrastructure optimisation, not shared Agent state.
    shared_engine = RecommendationEngine(
        Config.ONTOLOGY_PATH, beam_width=Config.BEAM_WIDTH,
        min_credits=Config.REGISTER_MIN_CREDITS, max_credits=Config.REGISTER_MAX_CREDITS,
        elective_quotas=Config.ELECTIVE_QUOTAS,
    )
    shared_evidence = OntologyEvidenceService(Config.ONTOLOGY_PATH)
    for source_index, record in enumerate(records, start=1):
        if len(rows) >= target:
            break
        pseudonym = f"RP{len(rows) + 1:04d}"
        # Keep the filesystem directory tied to traversal order.  A profile
        # skipped after its initial diagnostic must not consume/reuse an RP
        # pseudonym and collide with the next included profile.
        case_dir = run_dir / f"case-{source_index:04d}"
        case_dir.mkdir()
        fixture_path = case_dir / "student_fixture.json"
        write_json(fixture_path, [anonymise(record, pseudonym)])
        request = PlanningRequest(request_id=f"REPLAN-{pseudonym}", student_id=pseudonym,
                                  target_term_id="next-term", goal=goal_for(record), target_credits=args.target_credits)
        # Stateful condition must continue through the same orchestrator instance
        # that created the displayed result; the fresh instance below is reserved
        # for the stateless control.
        stateful_pipeline = make_pipeline(fixture_path, args.seed, shared_engine, shared_evidence)
        initial = stateful_pipeline.run_planning_flow(request)
        if initial.get("status") != "awaiting_feedback":
            skipped[initial.get("status", "runner_error")] += 1
            write_json(case_dir / "initial_diagnostic.json", initial)
            continue
        controlled = feedback_for(initial, request, len(rows))
        if controlled is None:
            skipped["no_feasible_controlled_feedback"] += 1
            write_json(case_dir / "initial_diagnostic.json", initial)
            continue
        feedback_type, operation = controlled
        feedback = FeedbackRequest(
            feedback_id=f"{pseudonym}-feedback", run_id=initial["run_id"],
            displayed_result_hash=ranking_hash(RankingResult.model_validate(initial["ranking"])),
            actor_pseudonym="controlled-advisor", actor_role="advisor", action="modify",
            selected_plan_id=initial["ranking"]["recommended_plan_id"], operations=(operation,),
            reason=f"Controlled Agentic Re-planning experiment: {feedback_type}.", created_at=datetime.now(timezone.utc),
        )
        write_json(case_dir / "initial.json", initial)
        write_json(case_dir / "feedback.json", feedback.model_dump(mode="json"))

        stateful = stateful_pipeline.replan_from_feedback(initial, feedback)
        adjustment = AdjustmentRequest.model_validate(stateful["feedback_normalization"]["adjustment"])
        stateless_request = request.model_copy(update={
            "request_id": request.request_id + "-stateless",
            "target_credits": adjustment.new_target_credits or request.target_credits,
            "goal": adjustment.new_goal or request.goal,
        })
        stateless = make_pipeline(fixture_path, args.seed, shared_engine, shared_evidence).run_planning_flow(
            stateless_request, adjustment=adjustment)
        write_json(case_dir / "stateful.json", stateful)
        write_json(case_dir / "stateless.json", stateless)
        write_json(case_dir / "adjustment.json", adjustment.model_dump(mode="json"))
        row = {
            "profile": pseudonym, "feedback_type": feedback_type,
            "initial_plan_codes": sorted(plan_codes(initial)), "feedback": feedback.model_dump(mode="json"),
            "stateful": condition_row("stateful", stateful, adjustment),
            "stateless": condition_row("stateless", stateless, adjustment),
        }
        write_json(case_dir / "case_summary.json", row)
        rows.append(row)

    summary = {"manifest": manifest, "included_profiles": len(rows), "skipped_profiles": dict(skipped),
               "feedback_type_histogram": dict(Counter(row["feedback_type"] for row in rows)),
               "profiles": rows, "metrics": aggregate(rows)}
    write_json(run_dir / "summary.json", summary)
    metrics = summary["metrics"]
    report = ["# Controlled Agentic Re-planning experiment", "",
              f"- Included pseudonymised profiles: **{len(rows)}/{target}**", f"- Skipped before inclusion: `{dict(skipped)}`",
              f"- Feedback types: `{summary['feedback_type_histogram']}`", "",
              "| Condition | Valid + feedback satisfied | Mean latency (s) | Mean evidence coverage |", "|---|---:|---:|---:|"]
    for condition in ("stateful", "stateless"):
        item = metrics[condition]
        rate = f"{item['success_rate']:.2%}" if item["success_rate"] is not None else "N/A"
        report.append(f"| {condition} | {item['valid_and_feedback_satisfied']}/{item['cases']} ({rate}) | {item['mean_latency_seconds'] if item['mean_latency_seconds'] is not None else 'N/A'} | {item['mean_evidence_coverage'] if item['mean_evidence_coverage'] is not None else 'N/A'} |")
    report.extend(["", f"- Paired outcomes: `{metrics['paired']}`.",
                   "- Each success is validated by StandardValidator and must satisfy the normalized feedback adjustment.",
                   "- One feedback item per profile means every successful outcome uses one re-planning round; this runner does not claim a multi-turn dialogue efficiency advantage."])
    (run_dir / "REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(run_dir.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
