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

PROTOCOL = "stage7-ontology-component-ablation-v2"
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


def request_row(configuration: str, disabled: str | None, pseudo: str, seed: int, generation, validations) -> dict:
    """Build the same request-level accounting record used by Stage 6."""
    internal_attempts = len(generation.attempt_records)
    emitted = len(generation.candidates)
    valid = sum(status == "valid" for status, _, _ in validations)
    if emitted > internal_attempts or valid > emitted or len(validations) != emitted:
        raise ValueError("INVALID_GENERATION_METRIC_COUNTS")
    return {
        "configuration": configuration,
        "disabled_relation": disabled or "none",
        "student": pseudo,
        "seed": seed,
        "internal_attempt_count": internal_attempts,
        "emitted_candidate_count": emitted,
        "valid_emitted_candidate_count": valid,
        "request_has_valid_final_plan": valid > 0,
        "validator_error_count": sum(status == "error" for status, _, _ in validations),
    }


def summarize(candidate_rows: list[dict], request_rows: list[dict], seeds: tuple[int, ...]) -> dict:
    grouped_requests: dict[tuple[str, int], list[dict]] = defaultdict(list)
    grouped_candidates: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for row in request_rows: grouped_requests[(row["configuration"], row["seed"])].append(row)
    for row in candidate_rows: grouped_candidates[(row["configuration"], row["seed"])].append(row)
    output = {}
    for configuration, _ in CONFIGS:
        per_seed, yields, validities, coverage, violations = [], [], [], [], Counter()
        for seed in seeds:
            requests = grouped_requests[(configuration, seed)]
            candidates = grouped_candidates[(configuration, seed)]
            attempts = sum(item["internal_attempt_count"] for item in requests)
            emitted = sum(item["emitted_candidate_count"] for item in requests)
            valid = sum(item["valid_emitted_candidate_count"] for item in requests)
            delivered = sum(item["request_has_valid_final_plan"] for item in requests)
            profile_count = len(requests)
            if emitted > attempts or valid > emitted:
                raise ValueError("INVALID_GENERATION_METRIC_COUNTS")
            generation_yield = emitted / attempts if attempts else None
            emitted_validity = valid / emitted if emitted else None
            cover = delivered / profile_count if profile_count else 0.0
            per_seed.append({"seed": seed, "profiles": profile_count,
                "internal_attempt_count": attempts, "emitted_candidate_count": emitted,
                "valid_emitted_candidate_count": valid, "requests_with_valid_final_plan": delivered,
                "validator_errors": sum(item["validator_error_count"] for item in requests),
                "internal_generation_yield": generation_yield,
                "emitted_candidate_validity": emitted_validity,
                "final_recommendation_coverage": cover, "no_plan_rate": 1 - cover})
            if generation_yield is not None: yields.append(generation_yield)
            if emitted_validity is not None: validities.append(emitted_validity)
            coverage.append(cover)
            for item in candidates: violations.update(item["violations"])
        output[configuration] = {"per_seed": per_seed,
            "internal_generation_yield": metric(yields),
            "emitted_candidate_validity": metric(validities),
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
    candidate_rows, request_rows = [], []
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
                generation = require_output(generated)
                validations = []
                profile_candidate_rows = []
                for attempt, plan in enumerate(generation.candidates, 1):
                    checked = validate_candidate(context(run_id, f"validate-{attempt}", plan.model_dump()), plan, student, knowledge, evidence,
                        min_credits=full_engine.min_credits, max_credits=full_engine.max_credits)
                    validations.append(validation_outcome(checked))
                    if validations[-1][0] == "error":
                        print(f"[ablation] {run_id}, attempt {attempt}: {validations[-1][2]}", file=sys.stderr, flush=True)
                for attempt, (validation_status, violations, validator_error) in enumerate(validations):
                    profile_candidate_rows.append({"configuration": name, "disabled_relation": disabled or "none", "seed": seed,
                        "student": f"B{number:04d}", "emitted_candidate_index": attempt + 1,
                        "validation_status": validation_status,
                        "violations": violations, "validator_error": validator_error,
                        "released": any(status == "valid" for status, _, _ in validations)})
                profile_request_row = request_row(name, disabled, f"B{number:04d}", seed, generation, validations)
                # One complete profile per line, preserved even if a later call fails.
                with (run_dir / "completed_profiles.jsonl").open("a", encoding="utf-8") as journal:
                    journal.write(json.dumps({"request": profile_request_row, "candidates": profile_candidate_rows}, ensure_ascii=False) + "\n")
                candidate_rows.extend(profile_candidate_rows)
                request_rows.append(profile_request_row)
                if args.progress_every and (number % args.progress_every == 0 or number == len(profiles)):
                    elapsed = perf_counter() - started
                    print(f"[ablation] {name}, seed {seed}: {number}/{len(profiles)}; elapsed {elapsed:.0f}s", flush=True)
    summary = summarize(candidate_rows, request_rows, args.seeds)
    manifest = {"protocol": PROTOCOL, "profiles": len(profiles), "seeds": list(args.seeds), "target_credits": args.target_credits,
        "candidate_output_cap": 3, "generator_ablation": "One relation family removed only from generation; full ontology StandardValidator remains the evaluator.",
        "metric_definitions": {
            "internal_generation_yield": "emitted candidates / internal generation attempts",
            "emitted_candidate_validity": "validator-valid emitted candidates / emitted candidates",
            "final_recommendation_coverage": "requests with at least one validator-valid final plan / all requests",
        },
        "configurations": [{"name": name, "disabled_relation": disabled} for name, disabled in CONFIGS],
        "source_profile_data_sha256": "sha256:" + sha256(Path(Config.STUDENT_DATA_JSON).read_bytes()).hexdigest()}
    write_json(run_dir / "manifest.json", manifest); write_json(run_dir / "candidate_results.json", candidate_rows)
    write_json(run_dir / "request_results.json", request_rows); write_json(run_dir / "summary.json", summary)
    print(run_dir)
    error_count = sum(item["validation_status"] == "error" for item in candidate_rows)
    if error_count:
        print(f"[ablation] WARNING: {error_count} validator errors; inspect results before reporting metrics.", file=sys.stderr)
    return 1 if error_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
