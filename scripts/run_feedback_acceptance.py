"""Export the reproducible SV001 feedback → re-planning → confirmation case."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.agent.pipeline import AgentPipeline
from backend.app.config import Config
from backend.app.schemas import FeedbackOperation, FeedbackRequest, PlanningRequest, RankingResult
from backend.app.services.grounded_explanation_service import ranking_hash
from backend.app.services.ontology_evidence_service import OntologyEvidenceService
from backend.app.services.recommendation_engine import RecommendationEngine
from backend.app.services.student_data_service import StudentDataService


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def main() -> int:
    folder = ROOT / "artifacts" / "feedback_acceptance" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    folder.mkdir(parents=True)
    students = StudentDataService(Config.STUDENT_DATA_JSON, Config.STUDENT_DATA_CSV)
    engine = RecommendationEngine(
        Config.ONTOLOGY_PATH, beam_width=Config.BEAM_WIDTH,
        min_credits=Config.REGISTER_MIN_CREDITS, max_credits=Config.REGISTER_MAX_CREDITS,
        elective_quotas=Config.ELECTIVE_QUOTAS,
    )
    pipeline = AgentPipeline(students, engine, OntologyEvidenceService(Config.ONTOLOGY_PATH))
    initial = pipeline.run_planning_flow(PlanningRequest(
        request_id="feedback-SV001", student_id="SV001", target_term_id="next-term",
        goal="on_time", target_credits=15,
    ))
    if initial["status"] != "awaiting_feedback":
        raise RuntimeError(f"Initial SV001 planning did not produce feedback-ready plans: {initial['status']}")
    write_json(folder / "initial.json", initial)

    replace = FeedbackRequest(
        feedback_id="feedback-SV001-replace", run_id=initial["run_id"],
        displayed_result_hash=ranking_hash(RankingResult.model_validate(initial["ranking"])),
        actor_pseudonym="advisor-001", actor_role="advisor", action="modify",
        selected_plan_id=initial["ranking"]["recommended_plan_id"],
        operations=(FeedbackOperation(kind="replace", course_code="INT6209", replacement_course_code="SOT366"),),
        reason="Thay học phần theo phản hồi của cố vấn.",
        created_at=datetime.now(timezone.utc),
    )
    write_json(folder / "feedback.json", replace.model_dump(mode="json"))
    replanned = pipeline.replan_from_feedback(initial, replace)
    if replanned["status"] != "awaiting_feedback" or not all(v["status"] == "valid" for v in replanned["validations"]):
        raise RuntimeError("Re-planning did not produce only valid plans")
    for candidate in replanned["candidates"]:
        codes = {course["course_code"] for course in candidate["courses"]}
        if "SOT366" not in codes or "INT6209" in codes:
            raise RuntimeError("Re-planning did not honour the replacement adjustment")
    write_json(folder / "replanned.json", replanned)
    write_json(folder / "adjustment.json", replanned["feedback_normalization"]["adjustment"])
    write_json(folder / "replanning-validations.json", replanned["validations"])
    write_json(folder / "replanning-evidence.json", replanned["explanations"])

    confirm = FeedbackRequest(
        feedback_id="feedback-SV001-confirm", run_id=replanned["run_id"],
        displayed_result_hash=ranking_hash(RankingResult.model_validate(replanned["ranking"])),
        actor_pseudonym="advisor-001", actor_role="advisor", action="confirm",
        selected_plan_id=replanned["ranking"]["recommended_plan_id"],
        created_at=datetime.now(timezone.utc),
    )
    confirmed = pipeline.confirm_from_feedback(replanned, confirm)
    if confirmed["status"] != "confirmed" or confirmed["confirmation"]["validation"]["status"] != "valid":
        raise RuntimeError("Final validation did not confirm a valid plan")
    write_json(folder / "confirmed.json", confirmed)

    manifest = {
        "artifact_version": "feedback-acceptance-v2",
        "run_lineage": {"initial_run_id": initial["run_id"], "replanned_run_id": replanned["run_id"]},
        "request": initial["request"],
        "snapshot_hashes": {
            "initial_student": initial["state"]["student_snapshot_hash"],
            "initial_knowledge": initial["state"]["knowledge_snapshot_hash"],
            "replanned_student": replanned["state"]["student_snapshot_hash"],
            "replanned_knowledge": replanned["state"]["knowledge_snapshot_hash"],
        },
        "files": {
            "initial": "initial.json", "feedback": "feedback.json", "adjustment": "adjustment.json",
            "replanned": "replanned.json", "validations": "replanning-validations.json",
            "evidence": "replanning-evidence.json", "confirmed": "confirmed.json",
        },
        "final_validation": confirmed["confirmation"]["validation"],
    }
    write_json(folder / "manifest.json", manifest)

    summary = {
        "student_id": "SV001",
        "initial_status": initial["status"],
        "feedback_action": "replace INT6209 with SOT366",
        "replanning_iteration": replanned["iteration"],
        "replanned_status": replanned["status"],
        "replanned_plan_ids": [candidate["plan_id"] for candidate in replanned["candidates"]],
        "validator_statuses": [item["status"] for item in replanned["validations"]],
        "explanation_count": len(replanned["explanations"]["explanations"]),
        "confirmed_status": confirmed["status"],
        "final_validation_status": confirmed["confirmation"]["validation"]["status"],
        "trace_actions": [item["action"] for item in confirmed["trace"]],
    }
    write_json(folder / "summary.json", summary)
    (folder / "REPORT.md").write_text(
        "# Ca chấp nhận phản hồi — SV001\n\n"
        "- Sinh viên/cố vấn chọn phương án hiển thị và yêu cầu thay `INT6209` bằng `SOT366`.\n"
        "- `normalize_feedback` kiểm tra schema, hash kết quả đã hiển thị và tạo `AdjustmentRequest`.\n"
        "- Hệ thống chạy lại Generation → Validator → Risk → Ranking → Explanation ở iteration 1.\n"
        "- Candidate mới có `SOT366`, không có `INT6209`; tất cả candidate xuất ra đều `valid`.\n"
        "- Phản hồi `confirm` kích hoạt StandardValidator lần cuối trước trạng thái `confirmed`.\n\n"
        "`manifest.json` liên kết request, snapshot hashes, adjustment, candidates, validations, evidence, trace và confirmation.\n"
        "Chi tiết ở `initial.json`, `feedback.json`, `adjustment.json`, `replanned.json`, `replanning-validations.json`, `replanning-evidence.json`, `confirmed.json` và `summary.json`.\n",
        encoding="utf-8",
    )
    print(folder)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
