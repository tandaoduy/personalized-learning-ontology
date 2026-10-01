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
import random
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

PROTOCOL = "stage6-baselines-frozen-v3"
CANDIDATE_CAP = 3
DEFAULT_SEEDS = (41, 42, 43, 44, 45, 46, 47, 48, 49, 50)
RULE_GROUPS = ("prerequisite", "corequisite", "curriculum_membership", "semester_offering", "elective_quota", "credit_limit")
STOCHASTIC_METHODS = frozenset({"BL-03-beam-search", "BL-04-agent-without-ontology", "BL-05-agent-with-ontology"})
METHOD_IDS = ("BL-01-rule-based", "BL-02-greedy", "BL-03-beam-search",
              "BL-04-agent-without-ontology", "BL-05-agent-with-ontology")


def digest(value: object) -> str:
    return "sha256:" + sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def file_digest(path: Path) -> str:
    return "sha256:" + sha256(path.read_bytes()).hexdigest()


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


def no_ontology_plans(engine: RecommendationEngine, profile, target_credits: float, seed: int) -> list[list[str]]:
    """Generate three catalog-only plans without querying ontology relations.

    This ablation may use a course's code, credit, and published recommended
    semester as flat catalog metadata plus the student's completed-course list.
    It must not inspect prerequisites, co-requisites, curriculum/specialization
    membership, offering, elective quota, eligibility, or validator output.
    """
    completed = set(profile.passed_courses) | set(profile.failed_courses)
    next_semester = max(1, int(profile.current_semester or 1)) + 1
    catalog = []
    for code, info in engine.course_data.items():
        credit = float(engine.course_data[code].get("credit", 0))
        if code not in completed and credit > 0:
            recommended = int(info.get("recommended_sem", next_semester) or next_semester)
            catalog.append((code, credit, abs(recommended - next_semester)))
    plans = []
    for offset in range(CANDIDATE_CAP):
        rng = random.Random(f"bl04-catalog-{seed}-{profile.student_id}-{offset}")
        # Seeded tie-breaking provides candidate diversity without relation data.
        ordered = sorted(catalog, key=lambda item: (item[2], rng.random(), item[0]))
        selected, credits = [], 0.0
        for code, credit, _ in ordered:
            if credits + credit <= target_credits:
                selected.append(code)
                credits += credit
        if selected:
            plans.append(selected)
    return plans


def candidate_row(method, pseudo, seed, plan, validation, elapsed, diversity=(), *, timeout_seconds: int) -> dict:
    checks = list(validation.rule_checks)
    return {"method": method, "student": pseudo, "seed": seed, "plan_id": plan.plan_id,
        "status": validation.status, "total_credits": plan.total_credits,
        "violations": [item.constraint_id for item in validation.violations],
        "evidence_checks": len(checks), "evidenced_checks": sum(bool(item.evidence_ids) for item in checks),
        "latency_seconds": elapsed, "diversity": list(diversity),
        "timeout_budget_seconds": timeout_seconds, "over_timeout_budget": elapsed > timeout_seconds}


def request_row(method, pseudo, seed, attempts, validations) -> dict:
    """One outcome per request, preserving pre-filter and released-plan measures."""
    valid = sum(item.status == "valid" for item in validations)
    released = valid > 0  # Only a validator-valid plan may reach a user.
    return {"method": method, "student": pseudo, "seed": seed,
        "candidate_attempts_before_filter": attempts, "valid_candidate_attempts": valid,
        "final_recommendation_delivered": released, "final_recommendation_valid": released,
        "final_recommendation_reason": "validator_valid_plan_available" if released else "no_validator_valid_plan"}


def rate_summary(values: list[float], *, stochastic: bool) -> dict:
    """Do not present repeated deterministic executions as independent samples."""
    if not values:
        return {"mean": None, "sd": None, "n_seeds": 0, "ci95_half_width": None}
    if not stochastic:
        return {"mean": round(mean(values), 6), "sd": None, "n_seeds": 1,
                "ci95_half_width": None, "note": "deterministic_method; CI not applicable"}
    sd = stdev(values) if len(values) > 1 else 0.0
    return {"mean": round(mean(values), 6) if values else None, "sd": round(sd, 6), "n_seeds": len(values),
            "ci95_half_width": round(1.96 * sd / sqrt(len(values)), 6) if values else None}


def summarize(candidate_rows, request_rows, seeds) -> dict:
    by_request, by_candidate = defaultdict(list), defaultdict(list)
    for item in request_rows: by_request[(item["method"], item["seed"])].append(item)
    for item in candidate_rows: by_candidate[(item["method"], item["seed"])].append(item)
    result = {}
    for method in sorted({item["method"] for item in request_rows}):
        per_seed, c_rates, f_rates, coverage, no_plan_rates = [], [], [], [], []
        violations, checks, evidenced, latency, diversity, over_timeout = Counter(), 0, 0, [], [], 0
        for seed in seeds:
            requests, candidates = by_request[(method, seed)], by_candidate[(method, seed)]
            attempts = sum(item["candidate_attempts_before_filter"] for item in requests)
            valid_attempts = sum(item["valid_candidate_attempts"] for item in requests)
            delivered = sum(item["final_recommendation_delivered"] for item in requests)
            valid_final = sum(item["final_recommendation_valid"] for item in requests)
            candidate_rate = valid_attempts / attempts if attempts else 0.0
            final_rate = valid_final / delivered if delivered else None
            coverage_rate = delivered / len(requests) if requests else 0.0
            no_plan_rate = 1 - coverage_rate
            per_seed.append({"seed": seed, "profiles": len(requests), "candidate_attempts_before_filter": attempts,
                "valid_candidate_attempts": valid_attempts, "candidate_attempt_validity": candidate_rate,
                "final_recommendations_delivered": delivered, "final_recommendations_valid": valid_final,
                "final_recommendation_validity": final_rate, "final_recommendation_coverage": coverage_rate,
                "no_plan_rate": no_plan_rate})
            c_rates.append(candidate_rate); coverage.append(coverage_rate); no_plan_rates.append(no_plan_rate)
            if final_rate is not None: f_rates.append(final_rate)
            for item in candidates:
                violations.update(item["violations"]); checks += item["evidence_checks"]; evidenced += item["evidenced_checks"]
                latency.append(item["latency_seconds"]); diversity.extend(item["diversity"])
                over_timeout += bool(item["over_timeout_budget"])
        stochastic = method in STOCHASTIC_METHODS
        result[method] = {"stochastic": stochastic, "per_seed": per_seed, "candidate_attempt_validity": rate_summary(c_rates, stochastic=stochastic),
            "final_recommendation_validity": rate_summary(f_rates, stochastic=stochastic),
            "final_recommendation_coverage": rate_summary(coverage, stochastic=stochastic),
            "no_plan_rate": rate_summary(no_plan_rates, stochastic=stochastic),
            "violations_by_rule": {rule: violations[rule] for rule in RULE_GROUPS},
            "mean_latency_seconds": round(mean(latency), 6) if latency else None,
            "over_timeout_candidate_count": over_timeout,
            "mean_pairwise_diversity": round(mean(diversity), 6) if diversity else None,
            "evidence_coverage": round(evidenced / checks, 6) if checks else None}
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Frozen Stage-6 fair baseline protocol")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--seeds", type=parse_seeds, default=DEFAULT_SEEDS, help="Comma-separated seeds (default: 41-50).")
    parser.add_argument("--seed", type=int, default=None, help="Deprecated single-seed compatibility option.")
    parser.add_argument("--target-credits", type=float, default=18.0,
        help="Shared planning-credit cap for every method; must be within the configured policy bounds.")
    parser.add_argument("--candidate-attempt-limit", type=int, default=60)
    parser.add_argument("--expanded-state-limit", type=int, default=5000)
    parser.add_argument("--max-active-seconds", type=int, default=120)
    parser.add_argument("--progress-every", type=int, default=10,
        help="Print progress after this many profiles per seed (0 disables progress output).")
    parser.add_argument("--methods", default=",".join(METHOD_IDS),
        help="Comma-separated method IDs; use BL-04-agent-without-ontology to rerun only the ablation.")
    args = parser.parse_args()
    if (args.limit < 0 or args.target_credits <= 0 or args.candidate_attempt_limit < 1
            or args.expanded_state_limit < 1 or args.max_active_seconds < 1 or args.progress_every < 0):
        parser.error("limits must be positive and --limit must be >= 0")
    seeds = (args.seed,) if args.seed is not None else args.seeds
    selected_methods = tuple(dict.fromkeys(value.strip() for value in args.methods.split(",") if value.strip()))
    unknown_methods = set(selected_methods) - set(METHOD_IDS)
    if not selected_methods or unknown_methods:
        parser.error(f"--methods must be a non-empty subset of: {', '.join(METHOD_IDS)}")
    students = StudentDataService(Config.STUDENT_DATA_JSON, Config.STUDENT_DATA_CSV)
    profiles = sorted(students.get_all_students(force_reload=True), key=lambda item: item.student_id)
    if args.limit: profiles = profiles[:args.limit]
    if not profiles: parser.error("No profiles selected")
    if not Config.REGISTER_MIN_CREDITS <= args.target_credits <= Config.REGISTER_MAX_CREDITS:
        parser.error(f"--target-credits must be within [{Config.REGISTER_MIN_CREDITS}, {Config.REGISTER_MAX_CREDITS}]")
    # The target is an experimental planning cap, so every generator and the
    # shared validator see exactly the same credit condition.  The underlying
    # institutional/proxy policy bounds remain recorded separately below.
    engine = RecommendationEngine(Config.ONTOLOGY_PATH, beam_width=Config.BEAM_WIDTH,
        min_credits=Config.REGISTER_MIN_CREDITS, max_credits=args.target_credits, elective_quotas=Config.ELECTIVE_QUOTAS)
    evidence = OntologyEvidenceService(Config.ONTOLOGY_PATH)
    run_dir = ROOT / "artifacts" / "stage6_baselines" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir.mkdir(parents=True)
    candidates, requests, source_manifest_hash = [], [], None
    for seed in seeds:
        seed_started = perf_counter()
        print(f"[stage6] seed {seed}: starting {len(profiles)} profiles", flush=True)
        pipeline = AgentPipeline(students, engine, evidence, AgentOrchestrator(
            seed=seed, max_candidate_attempts=args.candidate_attempt_limit,
            max_expanded_states=args.expanded_state_limit, max_active_seconds=args.max_active_seconds))
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
                "BL-04-agent-without-ontology": lambda: no_ontology_plans(engine, profile, args.target_credits, seed)}
            for method, generate in classic.items():
                if method not in selected_methods:
                    continue
                started, validations = perf_counter(), []
                generated = generate()
                if method != "BL-04-agent-without-ontology":
                    generated = [generated]
                for attempt, codes in enumerate(generated, 1):
                    plan = candidate(method, request, knowledge, codes, engine, seed)
                    if plan:
                        checked = validate_candidate(context(run_id, f"CALL_{method}_{number}_{attempt}", plan.model_dump()), plan, student, knowledge, evidence,
                            min_credits=engine.min_credits, max_credits=engine.max_credits)
                        if checked.status == "ok":
                            validation = checked.output.validation if hasattr(checked.output, "validation") else checked.output
                            validations.append(validation); candidates.append(candidate_row(
                                method, pseudo, seed, plan, validation, perf_counter() - started,
                                timeout_seconds=args.max_active_seconds))
                requests.append(request_row(method, pseudo, seed, len(generated), validations))
            if "BL-05-agent-with-ontology" in selected_methods:
                started = perf_counter(); agent = pipeline.run_planning_flow(request); elapsed = perf_counter() - started
                diversity = [float(item["distance"]) for item in (agent.get("ranking") or {}).get("pairwise_diversity") or []]
                validations = [ValidationResult.model_validate(value) for value in agent.get("validations") or []]
                for plan_data, validation in zip(agent.get("candidates") or [], validations):
                    candidates.append(candidate_row(
                        "BL-05-agent-with-ontology", pseudo, seed, CandidatePlan.model_validate(plan_data),
                        validation, elapsed, diversity, timeout_seconds=args.max_active_seconds))
                requests.append(request_row("BL-05-agent-with-ontology", pseudo, seed, len((agent.get("generation") or {}).get("attempt_records") or []), validations))
            if args.progress_every and (number % args.progress_every == 0 or number == len(profiles)):
                elapsed = perf_counter() - seed_started
                per_profile = elapsed / number
                remaining = int(per_profile * (len(profiles) - number))
                print(
                    f"[stage6] seed {seed}: {number}/{len(profiles)} profiles; "
                    f"elapsed {elapsed:.0f}s; estimated remaining {remaining}s",
                    flush=True,
                )
        print(f"[stage6] seed {seed}: complete in {perf_counter() - seed_started:.1f}s", flush=True)
    summary = summarize(candidates, requests, seeds)
    config = {"beam_width": Config.BEAM_WIDTH, "candidate_attempt_limit": args.candidate_attempt_limit,
              "expanded_state_limit": args.expanded_state_limit, "max_active_seconds": args.max_active_seconds,
              "target_credits": args.target_credits, "experimental_credit_bounds": [engine.min_credits, engine.max_credits],
              "configured_policy_credit_bounds": [Config.REGISTER_MIN_CREDITS, Config.REGISTER_MAX_CREDITS],
              "candidate_output_cap": CANDIDATE_CAP}
    source_data_path = Path(Config.STUDENT_DATA_JSON)
    manifest = {"protocol": PROTOCOL, "protocol_document": "docs/STAGE6_FROZEN_PROTOCOL.md", "created_at": datetime.now(timezone.utc).isoformat(),
        "profiles": len(profiles), "seeds": list(seeds), "target_term_id": "next-term", "target_credits": args.target_credits,
        "shared_search_budget": config, "config_hash": digest(config), "source_manifest_hash": source_manifest_hash,
        "source_profile_data_sha256": file_digest(source_data_path),
        "source_profile_data_path": source_data_path.name,
        "standard_validator": "backend.app.validation.validator.StandardValidator",
        "metric_definitions": {"candidate_attempt_validity": "valid candidate attempts / all candidate attempts before filtering",
            "final_recommendation_validity": "valid final recommendations / final recommendations delivered after StandardValidator",
            "final_recommendation_coverage": "requests with a final recommendation delivered / all requests"},
        "methods": list(selected_methods), "baseline_knowledge_scope": {
            "BL-01-rule-based": "Uses the shared production eligibility filter, then deterministic recommended-semester ordering.",
            "BL-02-greedy": "Uses the shared production eligibility filter, then deterministic priority ordering.",
            "BL-03-beam-search": "Uses the shared production eligibility filter and beam-search heuristic.",
            "BL-04-agent-without-ontology": "Uses flat catalog code/credit/recommended-semester metadata and seeded diversification only; no ontology eligibility, constraint relation evidence, or validator feedback.",
            "BL-05-agent-with-ontology": "Uses ontology-backed eligibility/evidence and in-pipeline deterministic validation."
        },
        "bl04_constraint": "Catalog-only generation; validator executes post hoc and never feeds BL-04 generation or ranking.",
        "timeout_accounting": "Agent enforces max_active_seconds internally. Classical baselines are synchronous and their elapsed time is recorded; any timing comparison must flag an over-budget run rather than claim preemptive termination.",
        "source_student_ids_exported": False}
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
