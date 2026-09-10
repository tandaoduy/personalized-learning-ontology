"""Reproduce the real SV001 case and a deliberately invalid curriculum control."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import logging
from pathlib import Path
import subprocess
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.agent.pipeline import AgentPipeline, _RunEvidenceCache, digest
from backend.app.agent.trace import TraceRecorder
from backend.app.capabilities import validate_candidate
from backend.app.config import Config
from backend.app.schemas import CandidatePlan, KnowledgeSnapshot, PlanningRequest, StudentSnapshot, ToolCallContext
from backend.app.schemas.agent_state import AgentState
from backend.app.services.ontology_evidence_service import OntologyEvidenceService
from backend.app.services.recommendation_engine import RecommendationEngine
from backend.app.services.student_data_service import StudentDataService
from run_agent_demo import setup_logging


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def main(with_tests=False):
    folder = ROOT / "artifacts" / "m4_acceptance" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    folder.mkdir(parents=True)
    setup_logging(folder / "pipeline.log")
    started = perf_counter()
    students = StudentDataService(Config.STUDENT_DATA_JSON, Config.STUDENT_DATA_CSV)
    engine = RecommendationEngine(Config.ONTOLOGY_PATH, beam_width=Config.BEAM_WIDTH,
        min_credits=Config.REGISTER_MIN_CREDITS, max_credits=Config.REGISTER_MAX_CREDITS,
        elective_quotas=Config.ELECTIVE_QUOTAS)
    evidence = OntologyEvidenceService(Config.ONTOLOGY_PATH)
    request = PlanningRequest(request_id="m4-SV001", student_id="SV001", target_term_id="next-term",
        goal="on_time", target_credits=15)
    result = AgentPipeline(students, engine, evidence).run_planning_flow(request)
    write_json(folder / "positive.json", result)
    if result.get("status") != "explaining":
        raise RuntimeError(f"Positive case did not pass the orchestration gate: {folder}")
    # These reads prove the exported collections/timestamps are real JSON, not repr strings.
    student = StudentSnapshot.model_validate(result["student_snapshot"])
    knowledge = KnowledgeSnapshot.model_validate(result["knowledge_snapshot"])
    AgentState.model_validate(result["state"])
    valid_ids = {v["plan_id"] for v in result["validations"] if v["status"] == "valid"}
    candidate = next(CandidatePlan.model_validate(p) for p in result["candidates"] if p["plan_id"] in valid_ids)
    selected_codes = {c.course_code for c in candidate.courses}
    cache = _RunEvidenceCache(evidence)
    forbidden = None
    for code in sorted(engine.course_data):
        if code in selected_codes or code in student.completed_courses:
            continue
        fact = cache.get_course_category_evidence(code, knowledge.versions.ontology_version)
        if fact.specializations and student.specialization_id not in fact.specializations:
            forbidden = code
            break
    if forbidden is None:
        raise RuntimeError("No wrong-specialization control course found in the actual ontology")
    credit = cache.get_course_credit_evidence(forbidden, knowledge.versions.ontology_version).catalog_credit
    bad_data = candidate.model_dump(mode="json")
    bad_data["plan_id"] += "-wrong-specialization"
    bad_data["courses"].append({"course_code": forbidden, "credits": credit})
    bad = CandidatePlan.model_validate(bad_data)
    context = ToolCallContext(run_id=result["run_id"] + "-control", call_id="CALL_curriculum_control",
        iteration=0, contract_version="agent-orchestrator-v1", attempt=1,
        deadline_at=datetime.now(timezone.utc) + timedelta(seconds=60), input_hash=digest(bad.model_dump(mode="json")))
    output = validate_candidate(context, bad, student, knowledge, cache,
        min_credits=engine.min_credits, max_credits=engine.max_credits)
    if output.status != "ok":
        raise RuntimeError(output.error)
    validation = output.output
    control_passed = validation.status == "invalid" and any(
        v.constraint_id == "curriculum_membership" and forbidden in v.course_codes for v in validation.violations)
    trace = TraceRecorder.from_result("validate_candidates", output, 0, context.deadline_at, 1)
    write_json(folder / "negative.json", {
        "purpose": "Controlled invalid candidate; actual student, ontology and policies unchanged",
        "mutation": {"operation": "add_course", "course_code": forbidden, "credits": credit},
        "parent_plan_id": candidate.plan_id, "request": result["request"],
        "student_snapshot": result["student_snapshot"], "knowledge_snapshot": result["knowledge_snapshot"],
        "candidate": bad.model_dump(mode="json"), "tool_result": output.model_dump(mode="json"),
        "trace": [trace.model_dump(mode="json")], "expected_violation_detected": control_passed})
    if not control_passed:
        raise RuntimeError("Validator did not detect the intended curriculum violation")

    sources = []
    for file in [Path(Config.STUDENT_DATA_JSON), Path(Config.ONTOLOGY_PATH), ROOT / "backend/app/config.py",
                 ROOT / "backend/app/services/recommendation/constants.py"]:
        sources.append({"path": file.relative_to(ROOT).as_posix(), "sha256": sha256(file.read_bytes()).hexdigest()})
    audit = {
        "scope": "Local MVP baseline, not certification of current university regulations",
        "student_alias": "SV001", "stored_student_id": student.student_id,
        "curriculum_id": student.curriculum_id, "major_id": student.major_id,
        "specialization_id": student.specialization_id, "current_semester": student.current_semester,
        "target_semester": student.current_semester + 1, "target_semester_type": knowledge.target_semester_type,
        "target_term_mapping": "next-term = current_semester + 1; no academic-calendar date mapping",
        "credit_policy": {"min": engine.min_credits, "max": engine.max_credits, "target": request.target_credits,
                          "source": "backend/app/config.py"},
        "elective_quotas": engine.elective_quotas, "sources": sources,
        "limitations": [
            "CURRICULUM-2023 is a derived cohort label; no independently versioned cohort curriculum manifest.",
            "Prior-study requirements are the explicit empty legacy baseline, not a verified university policy.",
            "History uses the stored profile at its current semester; arbitrary past-term reconstruction is not supported.",
            "Academic risk uses the versioned ProgressRiskAnalyzer proxy; it is not an official academic-warning status.",
            "expanded_states currently counts selected courses per attempt, not actual Beam Search expansions.",
        ],
    }
    write_json(folder / "source_audit.json", audit)
    test_result = {"executed": False}
    if with_tests:
        command = [sys.executable, "-m", "pytest", "backend/tests/test_student_specialization.py",
            "backend/tests/test_target_term_mapping.py",
            "backend/tests/test_ontology_evidence.py", "backend/tests/test_standard_validator.py",
            "backend/tests/test_agent_pipeline.py", "backend/tests/test_agent_pipeline_fast.py",
            "backend/tests/test_m4_scoring.py",
            "-m", "integration or not integration", "--tb=short", "-q",
            "--basetemp=" + str(folder / "pytest-tmp"), "--junitxml=" + str(folder / "tests.xml")]
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        (folder / "tests.txt").write_text(completed.stdout + completed.stderr, encoding="utf-8")
        test_result = {"executed": True, "exit_code": completed.returncode, "command": command}
    ranking = result["ranking"]
    risk = result["risk"]
    summary = {"positive_passed": True, "negative_passed": control_passed, "m4_passed": True,
        "valid_plans": len(valid_ids), "candidate_attempts": len(result["generation"]["attempt_records"]),
        "distinct_candidates": len(result["candidates"]), "duplicates": result["generation"]["duplicate_count"],
        "positive_elapsed_seconds": result["elapsed_seconds"], "total_elapsed_seconds": perf_counter() - started,
        "positive_plan_courses": sorted(selected_codes), "positive_plan_credits": sum(c.credits for c in candidate.courses),
        "control_course": forbidden, "risk_results": len(risk["results"]),
        "selected_plans": ranking["selected_plans"], "recommended_plan_id": ranking["recommended_plan_id"],
        "diversity_threshold": 0.30, "ranking_shortfall_reason": ranking["shortfall_reason"], "tests": test_result}
    write_json(folder / "summary.json", summary)
    (folder / "REPORT.md").write_text(
        f"# Minh chứng M4 — SV001\n\n"
        f"- Hồ sơ: {student.student_id}, CNTT/CNPM, {student.curriculum_id}; học kỳ {student.current_semester} → {student.current_semester + 1}.\n"
        f"- Chính sách baseline: {engine.min_credits}–{engine.max_credits} tín chỉ; mục tiêu 15.\n"
        f"- Validator: {len(valid_ids)} plan valid; phương án đầu {summary['positive_plan_credits']:g} tín chỉ.\n"
        f"- Risk: {len(risk['results'])} plan, mức {risk['results'][0]['risk_level']}, score {risk['results'][0]['risk_score']:.4f}.\n"
        f"- Ranking: chọn {len(ranking['selected_plans'])} plan; đề xuất `{ranking['recommended_plan_id']}`; ngưỡng Jaccard 0.30.\n"
        f"- Diversity giữa hai plan: {ranking['pairwise_diversity'][0]['distance']:.4f}.\n"
        f"- Đối chứng: thêm {forbidden} sai chuyên ngành; Validator phát hiện `curriculum_membership`.\n"
        f"- Trạng thái pipeline: `{result['status']}`; kiểm thử: {'đạt' if test_result.get('exit_code') == 0 else 'xem tests.txt / chưa chạy'}.\n\n"
        "Risk học vụ hiện dùng proxy ProgressRiskAnalyzer có version và được đánh dấu không chính thức. "
        "Dữ liệu chi tiết nằm trong positive.json, negative.json, source_audit.json, summary.json và tests.txt.\n",
        encoding="utf-8")
    logging.info("Acceptance artifacts: %s", folder)
    return 0 if not with_tests or test_result["exit_code"] == 0 else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--with-tests", action="store_true")
    args = parser.parse_args()
    raise SystemExit(main(args.with_tests))
