"""Run one real Agent → ontology → beam → validator trace from project data."""
from __future__ import annotations

import io
import json
import logging
import sys
from pathlib import Path

# Fix UTF-8 output on Windows terminal
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)

if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.agent import AgentOrchestrator, run_agent_pipeline
from backend.app.config import Config
from backend.app.schemas import PlanningRequest
from backend.app.services.agent_run_store import AgentRunStore
from backend.app.services.ontology_evidence_service import OntologyEvidenceService
from backend.app.services.recommendation_engine import RecommendationEngine
from backend.app.services.student_data_service import StudentDataService


class ReadableTextFilter(logging.Filter):
    """Repair legacy mojibake in logs while preserving normal Unicode text."""
    def filter(self, record):
        message = record.getMessage()
        if "Ã" in message or "Ä" in message:
            try:
                message = message.encode("latin1").decode("utf-8")
            except UnicodeError:
                pass
        record.msg, record.args = message, ()
        return True


def setup_logging(log_path: Path):
    """Configure logging for clear terminal output."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)-7s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(log_path, encoding="utf-8")],
    )
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.addFilter(ReadableTextFilter())
    logging.getLogger("backend.app.agent.pipeline").setLevel(logging.INFO)
    logging.getLogger("backend.app.capabilities").setLevel(logging.INFO)


def main(student_id: str = "SV001") -> int:
    output_dir = ROOT / "artifacts" / "agent_runs"
    output_dir.mkdir(parents=True, exist_ok=True)
    setup_logging(output_dir / f"demo-{student_id}.log")
    logger = logging.getLogger(__name__)

    logger.info("=" * 68)
    logger.info("        AGENT PIPELINE DEMO - ORCHESTRATOR + 5 CAPABILITIES")
    logger.info("=" * 68)
    logger.info("")

    # Initialize services
    logger.info("Initializing services...")
    try:
        students = StudentDataService(Config.STUDENT_DATA_JSON, Config.STUDENT_DATA_CSV)
        profile = students.get_student(student_id)
        if profile is None:
            logger.error("Student %s not found", student_id)
            return 2

        engine = RecommendationEngine(
            Config.ONTOLOGY_PATH,
            beam_width=Config.BEAM_WIDTH,
            min_credits=Config.REGISTER_MIN_CREDITS,
            max_credits=Config.REGISTER_MAX_CREDITS,
            elective_quotas=Config.ELECTIVE_QUOTAS,
        )
        evidence = OntologyEvidenceService(Config.ONTOLOGY_PATH)
        orchestrator = AgentOrchestrator()
        logger.info("[OK] All services initialized successfully")
        logger.info("")
    except Exception as exc:
        logger.exception("Failed to initialize services: %s", exc)
        return 1

    # Create planning request
    request = PlanningRequest(
        request_id="demo-" + student_id,
        student_id=student_id,
        target_term_id="next-term",
        goal="on_time",
        target_credits=15,
    )

    # Run pipeline
    result = run_agent_pipeline(request, students, engine, evidence, orchestrator)

    # Save to store
    logger.info("\n--- SAVING RUN ARTIFACTS ---")
    store = AgentRunStore(output_dir)
    store.root.mkdir(parents=True, exist_ok=True)
    artifact_path = store.root / f"{request.request_id}.json"
    artifact_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    logger.info("Artifacts saved to: %s", artifact_path)
    logger.info("Step log saved to: %s", output_dir / f"demo-{student_id}.log")

    # Print summary
    logger.info("\n" + "=" * 68)
    logger.info("                          DEMO COMPLETE")
    logger.info("=" * 68)

    final_status = result.get("status")
    if result.get("success") and final_status == "awaiting_feedback":
        logger.info("Status: SUCCESS — valid plans passed Validator, Risk, Ranking and Explanation")
        logger.info("Final state: %s", final_status)
        logger.info("Candidates generated: %d", len(result.get("candidates", [])))
        logger.info("Valid plans: %d", sum(1 for v in result.get("validations", []) if v.get("status") == "valid"))
        logger.info("Invalid plans: %d", sum(1 for v in result.get("validations", []) if v.get("status") != "valid"))
        logger.info("Selected plans: %s", result.get("ranking", {}).get("selected_plans", []))
        logger.info("Trace summary:")
        for event in result.get("trace", []):
            logger.info("  %s | %s | call=%s | output=%s", event["action"], event["outcome"],
                        event["call_id"], event.get("output_hash") or "-")
        return 0
    if result.get("success") and final_status in {"replanning", "no_plan_found"}:
        logger.warning("Status: COMPLETE — no valid plan is available yet; this is not a system error")
        logger.warning("Final state: %s", final_status)
        logger.warning("Read validation violations in the artifact before changing any rule or data.")
        return 0
    else:
        logger.error("Status: FAILED — pipeline could not accept its final tool output")
        logger.error("Final state: %s", final_status)
        error = result.get("error", {})
        logger.error("Error: %s - %s", error.get("code"), error.get("message"))
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "SV001"))
