"""Run controlled ontology-component ablations with the full StandardValidator.

Each configuration removes one constraint family from *generation only*.  The
same full ontology snapshot and deterministic validator evaluate every emitted
candidate, so differences measure the contribution of that family to finding
valid plans rather than weakening the evaluator.
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

from backend.app.capabilities import generate_candidates, load_knowledge_context, load_student_context, validate_candidate
from backend.app.config import Config
from backend.app.schemas import PlanningRequest, ToolCallContext
from backend.app.services.ontology_evidence_service import OntologyEvidenceService
from backend.app.services.recommendation_engine import RecommendationEngine
from backend.app.services.student_data_service import StudentDataService

PROTOCOL = "stage7-ontology-component-ablation-v1"
SEEDS = tuple(range(41, 51))
RULES = ("prerequisite", "corequisite", "curriculum_membership", "semester_offering", "elective_quota", "credit_limit")
CONFIGS = (
    ("full_ontology", None),
    ("without_prerequisite", "prerequisite"),
    ("without_corequisite", "corequisite"),
    ("without_curriculum_relation", "curriculum"),
    ("without_semester_offering", "offering"),
    ("without_elective_quota", "quota"),
)


def digest(value: object) -> str:
    return "sha256:" + sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def write_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    temporary.replace(path)


def require_output(result):
    if result.status == "error":
        raise RuntimeError(f"{result.provenance.tool_name}: {result.error.code}: {result.error.message}")
    return result.output


def validation_outcome(checked):
    if checked.status == "error":
        return "error", [], f"{checked.error.code}: {checked.error.message}"
    validation = checked.output.validation if hasattr(checked.output, "validation") else checked.output
    errors = "; ".join(f"{item.code}: {item.message}" for item in validation.errors)
    return validation.status, [item.constraint_id for item in validation.violations], errors or None


def parse_seeds(value: str) -> tuple[int, ...]:
    try:
        result = tuple(dict.fromkeys(int(item.strip()) for item in value.split(",") if item.strip()))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--seeds must be comma-separated integers") from exc
    if not result:
        raise argparse.ArgumentTypeError("--seeds must not be empty")
    return result


def context(run_id: str, call_id: str, payload: object) -> ToolCallContext:
    return ToolCallContext(run_id=run_id, call_id=call_id, iteration=0, contract_version=PROTOCOL,
        deadline_at=datetime.now(timezone.utc) + timedelta(seconds=180), attempt=1, input_hash=digest(payload))


def goal(profile) -> str:
    return "accelerated" if "vượt" in str(profile.study_goal).casefold() or "vuot" in str(profile.study_goal).casefold() else "on_time"


def make_engine(target_credits: float, disabled: str | None) -> RecommendationEngine:
    engine = RecommendationEngine(Config.ONTOLOGY_PATH, beam_width=Config.BEAM_WIDTH,
        min_credits=Config.REGISTER_MIN_CREDITS, max_credits=target_credits,
        elective_quotas=dict(Config.ELECTIVE_QUOTAS))
    if disabled == "prerequisite":
        for info in engine.course_data.values(): info["prereqs"] = []
    elif disabled == "corequisite":
        for info in engine.course_data.values(): info["corequisites"] = []
    elif disabled == "curriculum":
        for info in engine.course_data.values():
            info["specializations"] = []
            info["is_required_specialization"] = False
            info["is_elective_specialization"] = False
    elif disabled == "offering":
        for info in engine.course_data.values(): info["openSemesterType"] = 3
    elif disabled == "quota":
        engine.elective_quotas = {key: 10_000 for key in engine.elective_quotas}
    return engine


def metric(values: list[float]) -> dict:
    if not values: return {"mean": None, "sd": None, "ci95_half_width": None, "n_seeds": 0}
    sd = stdev(values) if len(values) > 1 else 0.0
    return {"mean": round(mean(values), 6), "sd": round(sd, 6), "ci95_half_width": round(1.96 * sd / sqrt(len(values)), 6), "n_seeds": len(values)}


def summarize(rows: list[dict], seeds: tuple[int, ...]) -> dict:
    grouped: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for row in rows: grouped[(row["configuration"], row["seed"])].append(row)
    output = {}
    for configuration, _ in CONFIGS:
        per_seed, rates, coverage, violations = [], [], [], Counter()
        for seed in seeds:
            items = grouped[(configuration, seed)]
            attempts = sum(item["attempt"] > 0 for item in items)
            valid = sum(item["validation_status"] == "valid" for item in items)
            delivered = sum(item["released"] for item in items if item["request_marker"])
            profile_count = sum(item["request_marker"] for item in items)
            rate = valid / attempts if attempts else 0.0
            cover = delivered / profile_count if profile_count else 0.0
            per_seed.append({"seed": seed, "profiles": profile_count, "candidate_attempts_before_filter": attempts,
                "valid_candidate_attempts": valid, "validator_errors": sum(item["validation_status"] == "error" for item in items), "candidate_attempt_validity": rate,
                "final_recommendation_coverage": cover, "no_plan_rate": 1 - cover})
            rates.append(rate); coverage.append(cover)
            for item in items: violations.update(item["violations"])
        output[configuration] = {"per_seed": per_seed, "candidate_attempt_validity": metric(rates),
            "final_recommendation_coverage": metric(coverage), "no_plan_rate": metric([1 - value for value in coverage]),
            "validator_errors": sum(item["validator_errors"] for item in per_seed),
            "violations_by_rule": {rule: violations[rule] for rule in RULES}}
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Controlled ontology component ablation")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--seeds", type=parse_seeds, default=SEEDS)
    parser.add_argument("--target-credits", type=float, default=18.0)
    parser.add_argument("--progress-every", type=int, default=10)
    args = parser.parse_args()
    if args.limit < 0 or args.progress_every < 0 or not Config.REGISTER_MIN_CREDITS <= args.target_credits <= Config.REGISTER_MAX_CREDITS:
        parser.error("invalid limit/progress/target credits")
    service = StudentDataService(Config.STUDENT_DATA_JSON, Config.STUDENT_DATA_CSV)
    profiles = sorted(service.get_all_students(force_reload=True), key=lambda item: item.student_id)
    if args.limit: profiles = profiles[:args.limit]
    if not profiles: parser.error("No profiles selected")
    full_engine = make_engine(args.target_credits, None)
    evidence = OntologyEvidenceService(Config.ONTOLOGY_PATH)
    generation_engines = {name: make_engine(args.target_credits, disabled) for name, disabled in CONFIGS}
    run_dir = ROOT / "artifacts" / "ontology_ablation" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_dir.mkdir(parents=True)
    print(f"[ablation] artifacts: {run_dir}", flush=True)
    rows = []
    for name, disabled in CONFIGS:
        for seed in args.seeds:
            started = perf_counter()
            print(f"[ablation] {name}, seed {seed}: starting {len(profiles)} profiles", flush=True)
            for number, profile in enumerate(profiles, 1):
                request = PlanningRequest(request_id=f"ABL-{name}-{seed}-{number:04d}", student_id=profile.student_id,
                    target_term_id="next-term", goal=goal(profile), target_credits=args.target_credits)
                run_id = f"RUN_ABL_{name}_{seed}_{number:04d}"
                student_result = load_student_context(context(run_id, "student", request.model_dump()), request, service)
                student = require_output(student_result).student_snapshot
                knowledge_result = load_knowledge_context(context(run_id, "knowledge", request.model_dump()), request,
                    student, full_engine, evidence)
                knowledge = require_output(knowledge_result).knowledge_snapshot
                generated = generate_candidates(context(run_id, "generate", request.model_dump()), request, student, knowledge,
                    profile, generation_engines[name], candidate_limit=3, seed=seed)
                validations = []
                for attempt, plan in enumerate(require_output(generated).candidates, 1):
                    checked = validate_candidate(context(run_id, f"validate-{attempt}", plan.model_dump()), plan, student, knowledge, evidence,
                        min_credits=full_engine.min_credits, max_credits=full_engine.max_credits)
                    validations.append(validation_outcome(checked))
                    if validations[-1][0] == "error":
                        print(f"[ablation] {run_id}, attempt {attempt}: {validations[-1][2]}", file=sys.stderr, flush=True)
                released = any(status == "valid" for status, _, _ in validations)
                profile_rows = []
                if not validations:
                    validations.append(("no_candidates", [], None))
                for attempt, (validation_status, violations, validator_error) in enumerate(validations):
                    profile_rows.append({"configuration": name, "disabled_relation": disabled or "none", "seed": seed,
                        "student": f"B{number:04d}", "attempt": 0 if validation_status == "no_candidates" else attempt + 1, "validation_status": validation_status,
                        "violations": violations, "validator_error": validator_error,
                        "released": released, "request_marker": attempt == 0})
                # One complete profile per line, preserved even if a later call fails.
                with (run_dir / "completed_profiles.jsonl").open("a", encoding="utf-8") as journal:
                    journal.write(json.dumps(profile_rows, ensure_ascii=False) + "\n")
                rows.extend(profile_rows)
                if args.progress_every and (number % args.progress_every == 0 or number == len(profiles)):
                    elapsed = perf_counter() - started
                    print(f"[ablation] {name}, seed {seed}: {number}/{len(profiles)}; elapsed {elapsed:.0f}s", flush=True)
    summary = summarize(rows, args.seeds)
    manifest = {"protocol": PROTOCOL, "profiles": len(profiles), "seeds": list(args.seeds), "target_credits": args.target_credits,
        "candidate_output_cap": 3, "generator_ablation": "One relation family removed only from generation; full ontology StandardValidator remains the evaluator.",
        "configurations": [{"name": name, "disabled_relation": disabled} for name, disabled in CONFIGS],
        "source_profile_data_sha256": "sha256:" + sha256(Path(Config.STUDENT_DATA_JSON).read_bytes()).hexdigest()}
    write_json(run_dir / "manifest.json", manifest); write_json(run_dir / "candidate_results.json", rows); write_json(run_dir / "summary.json", summary)
    print(run_dir)
    error_count = sum(item["validation_status"] == "error" for item in rows)
    if error_count:
        print(f"[ablation] WARNING: {error_count} validator errors; inspect results before reporting metrics.", file=sys.stderr)
    return 1 if error_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
