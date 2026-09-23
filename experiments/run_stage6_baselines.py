"""Run the frozen Stage-6 baseline protocol without exporting student IDs.

Candidate Attempt Validity measures all generation attempts before filtering.
Final Recommendation Validity measures only plans actually released after the
StandardValidator gate. Read it with recommendation coverage.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from math import sqrt
from pathlib import Path
from statistics import mean, stdev
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

PROTOCOL = "stage6-baselines-frozen-v2"
CANDIDATE_CAP = 3
DEFAULT_SEEDS = (41, 42, 43, 44, 45, 46, 47, 48, 49, 50)
RULE_GROUPS = ("prerequisite", "corequisite", "curriculum_membership", "semester_offering", "elective_quota", "credit_limit")


def digest(value: object) -> str:
    return "sha256:" + sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def parse_seeds(value: str) -> tuple[int, ...]:
    try:
        seeds = tuple(dict.fromkeys(int(part.strip()) for part in value.split(",") if part.strip()))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--seeds must be comma-separated integers") from exc
    if not seeds or any(seed < 0 for seed in seeds):
        raise argparse.ArgumentTypeError("--seeds must contain one or more non-negative integers")
    return seeds


def context(run_id: str, call_id: str, payload: object) -> ToolCallContext:
    return ToolCallContext(run_id=run_id, call_id=call_id, iteration=0, contract_version=PROTOCOL,
        deadline_at=datetime.now(timezone.utc) + timedelta(seconds=180), attempt=1, input_hash=digest(payload))


def goal(profile) -> str:
    return "accelerated" if "vượt" in str(profile.study_goal).casefold() or "vuot" in str(profile.study_goal).casefold() else "on_time"


def candidate(method: str, request: PlanningRequest, knowledge, codes: list[str], engine: RecommendationEngine, seed: int) -> CandidatePlan | None:
    codes = list(dict.fromkeys(code.upper() for code in codes if code.upper() in engine.course_data))
    if not codes:
        return None
    return CandidatePlan(plan_id=f"{method}-s{seed}-{request.request_id}", plan_version=PROTOCOL,
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


def candidate_row(method, pseudo, seed, plan, validation, elapsed, diversity=()) -> dict:
    checks = list(validation.rule_checks)
    return {"method": method, "student": pseudo, "seed": seed, "plan_id": plan.plan_id,
        "status": validation.status, "total_credits": plan.total_credits,
        "violations": [item.constraint_id for item in validation.violations],
        "evidence_checks": len(checks), "evidenced_checks": sum(bool(item.evidence_ids) for item in checks),
        "latency_seconds": elapsed, "diversity": list(diversity)}


def request_row(method, pseudo, seed, attempts, validations) -> dict:
    """One outcome per request, preserving pre-filter and released-plan measures."""
    valid = sum(item.status == "valid" for item in validations)
    released = valid > 0  # Only a validator-valid plan may reach a user.
    return {"method": method, "student": pseudo, "seed": seed,
        "candidate_attempts_before_filter": attempts, "valid_candidate_attempts": valid,
        "final_recommendation_delivered": released, "final_recommendation_valid": released,
        "final_recommendation_reason": "validator_valid_plan_available" if released else "no_validator_valid_plan"}


def rate_summary(values: list[float]) -> dict:
    sd = stdev(values) if len(values) > 1 else 0.0
    return {"mean": round(mean(values), 6) if values else None, "sd": round(sd, 6), "n_seeds": len(values),
            "ci95_half_width": round(1.96 * sd / sqrt(len(values)), 6) if values else None}


def summarize(candidate_rows, request_rows, seeds) -> dict:
    by_request, by_candidate = defaultdict(list), defaultdict(list)
    for item in request_rows: by_request[(item["method"], item["seed"])].append(item)
    for item in candidate_rows: by_candidate[(item["method"], item["seed"])].append(item)
    result = {}
    for method in sorted({item["method"] for item in request_rows}):
        per_seed, c_rates, f_rates, coverage = [], [], [], []
        violations, checks, evidenced, latency, diversity = Counter(), 0, 0, [], []
        for seed in seeds:
            requests, candidates = by_request[(method, seed)], by_candidate[(method, seed)]
            attempts = sum(item["candidate_attempts_before_filter"] for item in requests)
            valid_attempts = sum(item["valid_candidate_attempts"] for item in requests)
            delivered = sum(item["final_recommendation_delivered"] for item in requests)
            valid_final = sum(item["final_recommendation_valid"] for item in requests)
            candidate_rate = valid_attempts / attempts if attempts else 0.0
            final_rate = valid_final / delivered if delivered else None
            coverage_rate = delivered / len(requests) if requests else 0.0
            per_seed.append({"seed": seed, "profiles": len(requests), "candidate_attempts_before_filter": attempts,
                "valid_candidate_attempts": valid_attempts, "candidate_attempt_validity": candidate_rate,
                "final_recommendations_delivered": delivered, "final_recommendations_valid": valid_final,
                "final_recommendation_validity": final_rate, "final_recommendation_coverage": coverage_rate})
            c_rates.append(candidate_rate); coverage.append(coverage_rate)
            if final_rate is not None: f_rates.append(final_rate)
            for item in candidates:
                violations.update(item["violations"]); checks += item["evidence_checks"]; evidenced += item["evidenced_checks"]
                latency.append(item["latency_seconds"]); diversity.extend(item["diversity"])
        result[method] = {"per_seed": per_seed, "candidate_attempt_validity": rate_summary(c_rates),
            "final_recommendation_validity": rate_summary(f_rates), "final_recommendation_coverage": rate_summary(coverage),
            "violations_by_rule": {rule: violations[rule] for rule in RULE_GROUPS},
            "mean_latency_seconds": round(mean(latency), 6) if latency else None,
            "mean_pairwise_diversity": round(mean(diversity), 6) if diversity else None,
            "evidence_coverage": round(evidenced / checks, 6) if checks else None}
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Frozen Stage-6 fair baseline protocol")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--seeds", type=parse_seeds, default=DEFAULT_SEEDS, help="Comma-separated seeds (default: 41-50).")
    parser.add_argument("--seed", type=int, default=None, help="Deprecated single-seed compatibility option.")
    parser.add_argument("--target-credits", type=float, default=18.0)
    args = parser.parse_args()
    if args.limit < 0 or args.target_credits <= 0: parser.error("--limit must be >= 0 and --target-credits must be positive")
    seeds = (args.seed,) if args.seed is not None else args.seeds
    students = StudentDataService(Config.STUDENT_DATA_JSON, Config.STUDENT_DATA_CSV)
    profiles = sorted(students.get_all_students(force_reload=True), key=lambda item: item.student_id)
    if args.limit: profiles = profiles[:args.limit]
    if not profiles: parser.error("No profiles selected")
    engine = RecommendationEngine(Config.ONTOLOGY_PATH, beam_width=Config.BEAM_WIDTH,
        min_credits=Config.REGISTER_MIN_CREDITS, max_credits=Config.REGISTER_MAX_CREDITS, elective_quotas=Config.ELECTIVE_QUOTAS)
    evidence = OntologyEvidenceService(Config.ONTOLOGY_PATH)
    run_dir = ROOT / "artifacts" / "stage6_baselines" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir.mkdir(parents=True)
    candidates, requests, source_manifest_hash = [], [], None
    for seed in seeds:
        pipeline = AgentPipeline(students, engine, evidence, AgentOrchestrator(seed=seed, max_candidate_attempts=60, max_expanded_states=5000))
        for number, profile in enumerate(profiles, 1):
            pseudo, run_id = f"B{number:04d}", f"RUN_STAGE6_S{seed}_{number:04d}"
            request = PlanningRequest(request_id=f"STAGE6-S{seed}-{number:04d}", student_id=profile.student_id,
                target_term_id="next-term", goal=goal(profile), target_credits=args.target_credits)
            student_result = load_student_context(context(run_id, f"CALL_STUDENT_{number}", request.model_dump()), request, students)
            if student_result.status == "error": continue
            student = student_result.output.student_snapshot
            knowledge_result = load_knowledge_context(context(run_id, f"CALL_KNOWLEDGE_{number}", student.model_dump()), request, student, engine, evidence)
            if knowledge_result.status == "error": continue
            knowledge = knowledge_result.output.knowledge_snapshot
            source_manifest_hash = knowledge.source_manifest.content_hash if knowledge.source_manifest else None
            classic = {"BL-01-rule-based": lambda: [item.code for item in rule_based_plan(engine, profile)],
                "BL-02-greedy": lambda: [item.code for item in greedy_plan(engine, profile)],
                "BL-03-beam-search": lambda: [item.code for item in beam_search_plan(engine, profile, seed_offset=seed)],
                "BL-04-agent-without-ontology": lambda: no_ontology_plan(engine, profile, args.target_credits)}
            for method, generate in classic.items():
                started, validations = perf_counter(), []
                plan = candidate(method, request, knowledge, generate(), engine, seed)
                if plan:
                    checked = validate_candidate(context(run_id, f"CALL_{method}_{number}", plan.model_dump()), plan, student, knowledge, evidence,
                        min_credits=engine.min_credits, max_credits=engine.max_credits)
                    if checked.status == "ok":
                        validation = checked.output.validation if hasattr(checked.output, "validation") else checked.output
                        validations.append(validation); candidates.append(candidate_row(method, pseudo, seed, plan, validation, perf_counter() - started))
                requests.append(request_row(method, pseudo, seed, 1, validations))
            started = perf_counter(); agent = pipeline.run_planning_flow(request); elapsed = perf_counter() - started
            diversity = [float(item["distance"]) for item in (agent.get("ranking") or {}).get("pairwise_diversity") or []]
            validations = [ValidationResult.model_validate(value) for value in agent.get("validations") or []]
            for plan_data, validation in zip(agent.get("candidates") or [], validations):
                candidates.append(candidate_row("BL-05-agent-with-ontology", pseudo, seed, CandidatePlan.model_validate(plan_data), validation, elapsed, diversity))
            requests.append(request_row("BL-05-agent-with-ontology", pseudo, seed, len((agent.get("generation") or {}).get("attempt_records") or []), validations))
    summary = summarize(candidates, requests, seeds)
    config = {"beam_width": Config.BEAM_WIDTH, "candidate_attempt_limit": 60, "expanded_state_limit": 5000,
              "target_credits": args.target_credits, "credit_bounds": [engine.min_credits, engine.max_credits], "candidate_output_cap": CANDIDATE_CAP}
    manifest = {"protocol": PROTOCOL, "protocol_document": "docs/STAGE6_FROZEN_PROTOCOL.md", "created_at": datetime.now(timezone.utc).isoformat(),
        "profiles": len(profiles), "seeds": list(seeds), "target_term_id": "next-term", "target_credits": args.target_credits,
        "shared_search_budget": config, "config_hash": digest(config), "source_manifest_hash": source_manifest_hash,
        "standard_validator": "backend.app.validation.validator.StandardValidator",
        "metric_definitions": {"candidate_attempt_validity": "valid candidate attempts / all candidate attempts before filtering",
            "final_recommendation_validity": "valid final recommendations / final recommendations delivered after StandardValidator",
            "final_recommendation_coverage": "requests with a final recommendation delivered / all requests"},
        "bl04_constraint": "Catalog-only generation; validator executes post hoc and never feeds BL-04 generation or ranking.", "source_student_ids_exported": False}
    write_json(run_dir / "manifest.json", manifest); write_json(run_dir / "candidate_results.json", candidates)
    write_json(run_dir / "request_results.json", requests); write_json(run_dir / "summary.json", summary)
    report = ["# Frozen Stage 6 baseline report", "", "Candidate Attempt Validity and Final Recommendation Validity are distinct metrics.", ""]
    for method, value in summary.items(): report.extend([f"## {method}", "", "```json", json.dumps(value, ensure_ascii=False, indent=2), "```", ""])
    (run_dir / "REPORT.md").write_text("\n".join(report), encoding="utf-8")
    print(f"Stage 6 complete: {len(profiles)} profiles x {len(seeds)} seeds, {len(candidates)} validated candidates")
    print(run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
