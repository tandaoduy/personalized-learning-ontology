"""Build reproducible, anonymised human-evaluation packages for advisors.

The runner reads the local student/ontology sources but never modifies them.
It creates a frozen manifest, one de-identified profile artifact per selected
student, and 60 advisor-specific packages (20 for each of three advisors).
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import logging
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.agent.pipeline import AgentPipeline
from backend.app.config import Config
from backend.app.schemas import PlanningRequest
from backend.app.services.ontology_evidence_service import OntologyEvidenceService
from backend.app.services.recommendation_engine import RecommendationEngine
from backend.app.services.student_data_service import StudentDataService

PROTOCOL = "human-eval-pack-v1"
FORM_VERSION = "human-eval-advisor-v1"
SELECTION_SEED = 20261006
ADVISORS = ("ADVISOR-01", "ADVISOR-02", "ADVISOR-03")
QUOTA = 6


def digest(value: object) -> str:
    return "sha256:" + sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def pseudonym(student_id: str) -> str:
    return "PSEUDO-" + sha256(student_id.encode()).hexdigest()[:10].upper()


def goal(profile) -> str:
    return "accelerated" if "vượt" in str(profile.study_goal).casefold() or "vuot" in str(profile.study_goal).casefold() else "on_time"


def stratum(profile) -> str | None:
    """Use only strata actually supported by the current anonymised dataset."""
    has_debt = bool(profile.failed_courses)
    selected_specialization = bool(profile.specialization and "chưa chọn" not in profile.specialization.casefold())
    if profile.current_semester <= 2 and not has_debt and goal(profile) == "on_time":
        return "G1_early_on_time"
    if profile.current_semester <= 2 and not has_debt and goal(profile) == "accelerated":
        return "G2_early_accelerated"
    if profile.current_semester >= 5 and selected_specialization and not has_debt:
        return "G3_specialization_on_track"
    if profile.current_semester <= 2 and has_debt:
        return "G4_early_debt"
    if profile.current_semester >= 5 and has_debt:
        return "G5_specialization_debt"
    return None


def select_profiles(service: StudentDataService) -> tuple[list, list[dict]]:
    buckets: dict[str, list] = {}
    for profile in service.get_all_students(force_reload=True):
        group = stratum(profile)
        if group:
            buckets.setdefault(group, []).append(profile)
    selected, excluded = [], []
    for group in ("G1_early_on_time", "G2_early_accelerated", "G3_specialization_on_track", "G4_early_debt", "G5_specialization_debt"):
        candidates = sorted(buckets.get(group, []), key=lambda item: pseudonym(item.student_id))
        if len(candidates) < QUOTA:
            raise RuntimeError(f"Insufficient profiles for {group}: need {QUOTA}, found {len(candidates)}")
        selected.extend((group, item) for item in candidates[:QUOTA])
        excluded.extend({"anonymous_student_id": pseudonym(item.student_id), "stratum": group,
                         "reason": "not_selected_after_deterministic_quota"} for item in candidates[QUOTA:])
    return selected, excluded


def make_pipeline() -> AgentPipeline:
    service = StudentDataService(Config.STUDENT_DATA_JSON, Config.STUDENT_DATA_CSV)
    engine = RecommendationEngine(Config.ONTOLOGY_PATH, beam_width=Config.BEAM_WIDTH,
        min_credits=Config.REGISTER_MIN_CREDITS, max_credits=Config.REGISTER_MAX_CREDITS,
        elective_quotas=dict(Config.ELECTIVE_QUOTAS))
    return AgentPipeline(service, engine, OntologyEvidenceService(Config.ONTOLOGY_PATH))


def profile_context(result: dict, profile) -> dict:
    snapshot = result["student_snapshot"]
    return {
        "current_semester": snapshot["current_semester"],
        "major_id": snapshot["major_id"],
        "specialization_present": snapshot["specialization_id"] is not None,
        "study_goal": goal(profile),
        "accumulated_credits": snapshot.get("accumulated_credits"),
        "completed_course_count": len(snapshot["completed_courses"]),
        "failed_courses": sorted(snapshot["failed_courses"]),
    }


def render_plan(plan_id: str, result: dict) -> dict:
    candidates = {item["plan_id"]: item for item in result["candidates"]}
    catalog = {item["course_code"]: item for item in result["knowledge_context"]["catalog"]}
    candidate = candidates[plan_id]
    claims = next((item["claims"] for item in result.get("explanations", {}).get("explanations", [])
                   if item["plan_id"] == plan_id), [])
    courses = [{"course_code": course["course_code"],
                "course_name": catalog.get(course["course_code"], {}).get("course_name", "Không có tên học phần"),
                "credits": course["credits"]} for course in candidate["courses"]]
    return {"plan_id": plan_id, "total_credits": sum(item["credits"] for item in courses),
            "courses": courses,
            "explanation_claims": [{"kind": claim["kind"], "text": claim["text"],
                                    "evidence_count": len(claim["evidence_ids"])} for claim in claims]}


def selected_plan_ids(result: dict) -> list[str]:
    return [item["plan_id"] for item in result["ranking"]["selected_plans"]]


def render_markdown(package: dict) -> str:
    lines = [f"# Phiếu đánh giá {package['evaluation_id']}", "",
             "Không sử dụng dữ liệu nhận diện bên ngoài để suy đoán sinh viên. Đánh giá độc lập trước khi trao đổi với người khác.", "",
             "## Bối cảnh học tập", ""]
    context = package["student_context"]
    lines.extend([f"- Hồ sơ: `{package['profile_pseudonym']}`", f"- Học kỳ hiện tại: {context['current_semester']}",
                  f"- Mục tiêu: {context['study_goal']}", f"- Số học phần đã hoàn thành: {context['completed_course_count']}",
                  f"- Học phần chưa đạt liên quan: {', '.join(context['failed_courses']) or 'Không có'}", ""])
    for label in package["displayed_order"]:
        plan = package["displayed_plans"][label]
        lines.extend([f"## Phương án {label} ({plan['total_credits']:g} tín chỉ)", ""])
        lines.extend(f"- `{item['course_code']}` — {item['course_name']} ({item['credits']:g} TC)" for item in plan["courses"])
        lines.extend(["", "**Giải thích có căn cứ**"])
        lines.extend(f"- {claim['text']}" for claim in plan["explanation_claims"])
        lines.append("")
    if package["ranking_metrics_eligible"]:
        lines.append("Có đủ ba phương án để xếp hạng Top-3.")
    else:
        lines.append("Lưu ý: hệ thống hiện chỉ tạo được ít hơn ba phương án khác biệt, vì vậy hồ sơ này không dùng để tính NDCG@3/MRR.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build anonymised advisor evaluation packages")
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    run_dir = args.output_dir or ROOT / "artifacts" / "human_evaluation" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "profiles").mkdir()
    (run_dir / "advisor_packages").mkdir()
    logging.getLogger().setLevel(logging.WARNING)

    service = StudentDataService(Config.STUDENT_DATA_JSON, Config.STUDENT_DATA_CSV)
    selected, excluded = select_profiles(service)
    pipeline = make_pipeline()
    profile_rows = []
    ready = []
    for position, (group, profile) in enumerate(selected, start=1):
        profile_id = f"H{position:02d}" if position <= 15 else f"R{position - 15:02d}"
        request = PlanningRequest(request_id=f"human-eval-{profile_id}", student_id=profile.student_id,
            target_term_id="next-term", goal="accelerated" if goal(profile) == "accelerated" else "on_time",
            target_credits=18 if goal(profile) == "accelerated" else 15)
        result = pipeline.run_planning_flow(request)
        if result.get("status") != "awaiting_feedback" or not result.get("ranking"):
            excluded.append({"anonymous_student_id": pseudonym(profile.student_id), "stratum": group,
                             "reason": f"no_feedback_ready_plan:{result.get('status')}"})
            continue
        plan_ids = selected_plan_ids(result)
        if not plan_ids:
            excluded.append({"anonymous_student_id": pseudonym(profile.student_id), "stratum": group, "reason": "no_selected_plan"})
            continue
        artifact = {"protocol": PROTOCOL, "profile_id": profile_id, "profile_pseudonym": pseudonym(profile.student_id),
                    "stratum": group, "run_id": result["run_id"], "source_manifest_hash": digest(result["knowledge_snapshot"]),
                    "ranking_config_hash": result["ranking"]["config_hash"], "student_context": profile_context(result, profile),
                    "plans": [render_plan(plan_id, result) for plan_id in plan_ids],
                    "ranking_metrics_eligible": len(plan_ids) == 3}
        write_json(run_dir / "profiles" / f"{profile_id}.json", artifact)
        ready.append(artifact)
        profile_rows.append({"profile_id": profile_id, "profile_pseudonym": artifact["profile_pseudonym"], "stratum": group,
                             "run_id": result["run_id"], "plan_count": len(plan_ids),
                             "ranking_metrics_eligible": artifact["ranking_metrics_eligible"]})
    if len(ready) != 30:
        raise RuntimeError(f"Only {len(ready)}/30 profiles are feedback-ready; batch is not publishable")

    assignments = {ADVISORS[0]: [f"H{i:02d}" for i in range(1, 16)] + [f"R{i:02d}" for i in range(1, 6)],
                   ADVISORS[1]: [f"H{i:02d}" for i in range(1, 16)] + [f"R{i:02d}" for i in range(6, 11)],
                   ADVISORS[2]: [f"H{i:02d}" for i in range(1, 16)] + [f"R{i:02d}" for i in range(11, 16)]}
    by_id = {item["profile_id"]: item for item in ready}
    package_rows = []
    for advisor, profile_ids in assignments.items():
        advisor_dir = run_dir / "advisor_packages" / advisor
        advisor_dir.mkdir()
        for profile_id in profile_ids:
            artifact = by_id[profile_id]
            plans = list(artifact["plans"])
            rng = random.Random(f"{SELECTION_SEED}:{advisor}:{profile_id}")
            rng.shuffle(plans)
            labels = ["A", "B", "C"][:len(plans)]
            package = {"protocol": PROTOCOL, "form_version": FORM_VERSION,
                       "evaluation_id": f"HEV-{advisor}-{profile_id}", "advisor_pseudonym": advisor,
                       "profile_id": profile_id, "profile_pseudonym": artifact["profile_pseudonym"],
                       "stratum": artifact["stratum"], "run_id": artifact["run_id"],
                       "source_manifest_hash": artifact["source_manifest_hash"], "config_hash": artifact["ranking_config_hash"],
                       "student_context": artifact["student_context"], "displayed_order": labels,
                       "displayed_to_plan_id": {label: plan["plan_id"] for label, plan in zip(labels, plans)},
                       "displayed_plans": {label: plan for label, plan in zip(labels, plans)},
                       "ranking_metrics_eligible": artifact["ranking_metrics_eligible"]}
            write_json(advisor_dir / f"{profile_id}.json", package)
            (advisor_dir / f"{profile_id}.md").write_text(render_markdown(package), encoding="utf-8")
            package_rows.append({"evaluation_id": package["evaluation_id"], "advisor_pseudonym": advisor,
                                 "profile_id": profile_id, "profile_pseudonym": artifact["profile_pseudonym"]})
    manifest = {"protocol": PROTOCOL, "form_version": FORM_VERSION, "selection_seed": SELECTION_SEED,
                "created_at": datetime.now(timezone.utc).isoformat(), "profile_count": len(ready),
                "assignment_count": len(package_rows), "source_mutated": False,
                "stratum_definitions": {"G1_early_on_time": "HK<=2, không nợ, đúng hạn",
                                        "G2_early_accelerated": "HK<=2, không nợ, học vượt",
                                        "G3_specialization_on_track": "HK>=5, đã chọn chuyên ngành, không nợ",
                                        "G4_early_debt": "HK<=2, có học phần chưa đạt",
                                        "G5_specialization_debt": "HK>=5, đã chọn chuyên ngành, có học phần chưa đạt"},
                "profiles": profile_rows, "assignments": package_rows,
                "limitations": ["Tập dữ liệu hiện không có hồ sơ học kỳ 7–8; G5 được vận hành là nhóm chuyên ngành có nợ.",
                                "NDCG@3/MRR chỉ tính trên hồ sơ có đủ ba phương án khác biệt."]}
    write_json(run_dir / "human_eval_manifest.json", manifest)
    write_json(run_dir / "excluded_profiles.json", excluded)
    print(json.dumps({"output_dir": str(run_dir), "profiles": len(ready), "packages": len(package_rows),
                      "ranking_eligible_profiles": sum(row["ranking_metrics_eligible"] for row in profile_rows)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
