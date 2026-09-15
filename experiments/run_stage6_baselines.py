"""Run Stage-6 baselines without exporting student identifiers.

BL-04 is the ontology ablation.  Its generator reads only catalog codes and
registration credits; it never calls ontology eligibility and never receives
validator output as feedback.  The StandardValidator is post-hoc measurement.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from statistics import mean
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.agent.orchestrator import AgentOrchestrator
from backend.app.agent.pipeline import AgentPipeline
from backend.app.capabilities import load_knowledge_context, load_student_context, validate_candidate
from backend.app.config import Config
from backend.app.schemas import CandidateCourse, CandidatePlan, PlanningRequest, ToolCallContext, ValidationResult
from backend.app.services.ontology_evidence_service import OntologyEvidenceService
from backend.app.services.recommendation_engine import RecommendationEngine
from backend.app.services.student_data_service import StudentDataService
from experiments.benchmark_algorithms import beam_search_plan, greedy_plan, rule_based_plan

PROTOCOL = "stage6-baselines-v1"
CANDIDATE_CAP = 3
RULE_GROUPS = ("prerequisite", "corequisite", "curriculum_membership", "semester_offering", "elective_quota", "credit_limit")


def digest(value: object) -> str:
    return "sha256:" + sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def context(run_id: str, call_id: str, payload: object) -> ToolCallContext:
    return ToolCallContext(run_id=run_id, call_id=call_id, iteration=0, contract_version=PROTOCOL,
        deadline_at=datetime.now(timezone.utc) + timedelta(seconds=180), attempt=1, input_hash=digest(payload))


def goal(profile) -> str:
    return "accelerated" if "vượt" in str(profile.study_goal).casefold() or "vuot" in str(profile.study_goal).casefold() else "on_time"


def candidate(method: str, request: PlanningRequest, knowledge, codes: list[str], engine: RecommendationEngine) -> CandidatePlan | None:
    codes = list(dict.fromkeys(code.upper() for code in codes if code.upper() in engine.course_data))
    if not codes:
        return None
    return CandidatePlan(plan_id=f"{method}-{request.request_id}", plan_version=PROTOCOL,
        request_id=request.request_id, student_id=request.student_id, target_term_id=request.target_term_id,
        knowledge_versions=knowledge.versions, plan_type="balanced",
        courses=tuple(CandidateCourse(course_code=code, credits=float(engine.course_data[code].get("credit", 0))) for code in codes))


def no_ontology_plan(engine: RecommendationEngine, profile, target_credits: float) -> list[str]:
    """Catalog-only generation for BL-04; do not add ontology calls here."""
    selected, credits = [], 0.0
    completed = set(profile.passed_courses) | set(profile.failed_courses)
    for code in sorted(engine.course_data):
        credit = float(engine.course_data[code].get("credit", 0))
        if code not in completed and credit > 0 and credits + credit <= target_credits:
            selected.append(code)
            credits += credit
    return selected


def row(method: str, pseudo: str, plan: CandidatePlan, validation: ValidationResult, elapsed: float, diversity=()) -> dict:
    checks = list(validation.rule_checks)
    return {"method": method, "student": pseudo, "plan_id": plan.plan_id,
        "candidate_attempts": 1, "valid_candidates": int(validation.status == "valid"),
        "status": validation.status, "total_credits": plan.total_credits,
        "violations": [item.constraint_id for item in validation.violations],
        "evidence_checks": len(checks), "evidenced_checks": sum(bool(item.evidence_ids) for item in checks),
        "latency_seconds": elapsed, "diversity": list(diversity)}


def summarize(rows: list[dict]) -> dict:
    groups = defaultdict(list)
    for item in rows:
        groups[item["method"]].append(item)
    result = {}
    for method, values in groups.items():
        violations = Counter(v for item in values for v in item["violations"])
        attempts = sum(item["candidate_attempts"] for item in values)
        checks = sum(item["evidence_checks"] for item in values)
        diversity = [v for item in values for v in item["diversity"]]
        result[method] = {"profiles": len({item["student"] for item in values}),
            "candidate_attempts_before_filter": attempts, "valid_candidates": sum(item["valid_candidates"] for item in values),
            "valid_plan_rate": round(sum(item["valid_candidates"] for item in values) / max(1, attempts), 6),
            "violations_by_rule": {rule: violations[rule] for rule in RULE_GROUPS},
            "mean_latency_seconds": round(mean(item["latency_seconds"] for item in values), 6),
            "mean_pairwise_diversity": round(mean(diversity), 6) if diversity else None,
            "evidence_coverage": round(sum(item["evidenced_checks"] for item in values) / max(1, checks), 6)}
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 6 fair baseline protocol")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--target-credits", type=float, default=18.0)
    args = parser.parse_args()
    if args.limit < 0 or args.target_credits <= 0:
        parser.error("--limit must be >= 0 and --target-credits must be positive")
    students = StudentDataService(Config.STUDENT_DATA_JSON, Config.STUDENT_DATA_CSV)
    profiles = sorted(students.get_all_students(force_reload=True), key=lambda item: item.student_id)
    if args.limit:
        profiles = profiles[:args.limit]
    engine = RecommendationEngine(Config.ONTOLOGY_PATH, beam_width=Config.BEAM_WIDTH,
        min_credits=Config.REGISTER_MIN_CREDITS, max_credits=Config.REGISTER_MAX_CREDITS,
        elective_quotas=Config.ELECTIVE_QUOTAS)
    evidence = OntologyEvidenceService(Config.ONTOLOGY_PATH)
    pipeline = AgentPipeline(students, engine, evidence, AgentOrchestrator(seed=args.seed, max_candidate_attempts=60, max_expanded_states=5000))
    run_dir = ROOT / "artifacts" / "stage6_baselines" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir.mkdir(parents=True)
    rows = []
    source_manifest_hash = None
    for number, profile in enumerate(profiles, 1):
        pseudo, run_id = f"B{number:04d}", f"RUN_STAGE6_{number:04d}"
        request = PlanningRequest(request_id=f"STAGE6-{number:04d}", student_id=profile.student_id,
            target_term_id="next-term", goal=goal(profile), target_credits=args.target_credits)
        student_result = load_student_context(context(run_id, f"CALL_STUDENT_{number}", request.model_dump()), request, students)
        if student_result.status == "error":
            continue
        student = student_result.output.student_snapshot
        knowledge_result = load_knowledge_context(context(run_id, f"CALL_KNOWLEDGE_{number}", student.model_dump()), request, student, engine, evidence)
        if knowledge_result.status == "error":
            continue
        knowledge = knowledge_result.output.knowledge_snapshot
        source_manifest_hash = knowledge.source_manifest.content_hash if knowledge.source_manifest else None
        classic = {"BL-01-rule-based": lambda: [item.code for item in rule_based_plan(engine, profile)],
            "BL-02-greedy": lambda: [item.code for item in greedy_plan(engine, profile)],
            "BL-03-beam-search": lambda: [item.code for item in beam_search_plan(engine, profile)],
            "BL-04-agent-without-ontology": lambda: no_ontology_plan(engine, profile, args.target_credits)}
        for method, generate in classic.items():
            started = perf_counter()
            plan = candidate(method, request, knowledge, generate(), engine)
            if not plan:
                continue
            checked = validate_candidate(context(run_id, f"CALL_{method}_{number}", plan.model_dump()), plan, student, knowledge, evidence,
                min_credits=engine.min_credits, max_credits=engine.max_credits)
            if checked.status == "ok":
                validation = checked.output.validation if hasattr(checked.output, "validation") else checked.output
                rows.append(row(method, pseudo, plan, validation, perf_counter() - started))
        started = perf_counter()
        agent = pipeline.run_planning_flow(request)
        elapsed = perf_counter() - started
        diversity = [float(item["distance"]) for item in (agent.get("ranking") or {}).get("pairwise_diversity") or []]
        for plan_data, validation_data in zip(agent.get("candidates") or [], agent.get("validations") or []):
            rows.append(row("BL-05-agent-with-ontology", pseudo, CandidatePlan.model_validate(plan_data),
                ValidationResult.model_validate(validation_data), elapsed, diversity))
    summary = summarize(rows)
    config = {"beam_width": Config.BEAM_WIDTH, "candidate_attempt_limit": 60, "expanded_state_limit": 5000,
              "target_credits": args.target_credits, "credit_bounds": [engine.min_credits, engine.max_credits]}
    manifest = {"protocol": PROTOCOL, "created_at": datetime.now(timezone.utc).isoformat(), "profiles": len(profiles),
        "seed": args.seed, "target_credits": args.target_credits,
        "shared_search_budget": config | {"candidate_output_cap": CANDIDATE_CAP},
        "config_hash": digest(config | {"candidate_output_cap": CANDIDATE_CAP}), "source_manifest_hash": source_manifest_hash,
        "standard_validator": "backend.app.validation.validator.StandardValidator",
        "bl04_constraint": "Catalog-only generation; validator executes post hoc and never feeds BL-04 generation or ranking.",
        "candidate_fairness": "All methods have a maximum output budget of 3 candidates. Deterministic baselines may emit fewer; results.json records each actual candidate attempt and summary rates use that denominator.",
        "source_student_ids_exported": False}
    write_json(run_dir / "manifest.json", manifest)
    write_json(run_dir / "results.json", rows)
    write_json(run_dir / "summary.json", summary)
    (run_dir / "REPORT.md").write_text("# Stage 6 baseline report\n\n```json\n" + json.dumps(summary, ensure_ascii=False, indent=2) + "\n```\n", encoding="utf-8")
    print(f"Stage 6 complete: {len(profiles)} profiles, {len(rows)} validated attempts")
    print(run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
