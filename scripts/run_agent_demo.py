"""Run one real Agent → ontology → beam → validator trace from project data."""
from __future__ import annotations

import json
import sys
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.agent import AgentOrchestrator
from backend.app.capabilities import build_course_space, generate_candidates, load_knowledge_context, load_student_context, validate_candidate
from backend.app.config import Config
from backend.app.schemas import PlanningRequest, ToolError, ToolResult
from backend.app.services.agent_run_store import AgentRunStore
from backend.app.services.ontology_evidence_service import OntologyEvidenceService
from backend.app.services.recommendation_engine import RecommendationEngine
from backend.app.services.student_data_service import StudentDataService


def digest(value: object) -> str:
    return "sha256:" + sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def main(student_id: str = "SV001") -> int:
    request = PlanningRequest(request_id="demo-" + student_id, student_id=student_id,
        target_term_id="next-term", goal="on_time", target_credits=15)
    students = StudentDataService(Config.STUDENT_DATA_JSON, Config.STUDENT_DATA_CSV)
    profile = students.get_student(student_id)
    if profile is None:
        print(json.dumps({"error": "STUDENT_NOT_FOUND", "student_id": student_id})); return 2
    engine = RecommendationEngine(Config.ONTOLOGY_PATH, beam_width=Config.BEAM_WIDTH,
        min_credits=Config.REGISTER_MIN_CREDITS, max_credits=Config.REGISTER_MAX_CREDITS,
        elective_quotas=Config.ELECTIVE_QUOTAS)
    evidence = OntologyEvidenceService(Config.ONTOLOGY_PATH)
    orchestrator = AgentOrchestrator()
    store = AgentRunStore(ROOT / "artifacts" / "agent_runs")
    state = orchestrator.start(orchestrator.create_run(request, run_id="DEMO_" + student_id))
    store.save_state(state)

    context = orchestrator.create_call_context(state, "load_student_context", digest(request.model_dump()))
    student_result = load_student_context(context, request, students)
    state = orchestrator.apply_result(state, "load_student_context", context, student_result)
    if student_result.status == "error": return _finish(store, state, student_result.error)
    student = student_result.output.student_snapshot

    context = orchestrator.create_call_context(state, "load_knowledge_context", digest({"request": request.model_dump(), "student": student.model_dump()}))
    knowledge_result = load_knowledge_context(context, request, student, engine, evidence)
    state = orchestrator.apply_result(state, "load_knowledge_context", context, knowledge_result)
    if knowledge_result.status == "error": return _finish(store, state, knowledge_result.error)
    knowledge = knowledge_result.output.knowledge_snapshot

    context = orchestrator.create_call_context(state, "build_course_space", digest({"student": student.model_dump(), "knowledge": knowledge.model_dump()}))
    eligibility_result = build_course_space(context, student, knowledge, profile, engine)
    state = orchestrator.apply_result(state, "build_course_space", context, eligibility_result)
    if eligibility_result.status == "error": return _finish(store, state, eligibility_result.error)

    context = orchestrator.create_call_context(state, "generate_candidates", digest({"space": eligibility_result.output.model_dump(), "seed": state.seed}))
    generation = generate_candidates(context, request, student, knowledge, profile, engine)
    hashes = tuple("sha256:" + sha256(plan.model_dump_json().encode()).hexdigest() for plan in (generation.output.candidates if generation.output else ()))
    state = orchestrator.apply_generation_result(state, context, generation, hashes,
        len(generation.output.attempt_records) if generation.output else 0,
        generation.output.expanded_states if generation.output else 0)
    if generation.status == "error" or not generation.output or not generation.output.candidates:
        return _finish(store, state, generation.error or ToolError(code="NO_CANDIDATES", message="Beam Search returned no candidates"))

    candidate = generation.output.candidates[0]
    context = orchestrator.create_call_context(state, "validate_candidates", digest(candidate.model_dump()))
    validated = validate_candidate(context, candidate, student, knowledge, evidence,
        min_credits=engine.min_credits, max_credits=engine.max_credits)
    if validated.status == "ok":
        item = validated.output.validation if hasattr(validated.output, "validation") else validated.output
        state = orchestrator.apply_validations(state, (item,), context, validated)
    return _finish(store, state, None)


def _finish(store: AgentRunStore, state, error: ToolError | None) -> int:
    store.save_state(state)
    print(json.dumps({"run_id": state.run_id, "status": state.status, "iteration": state.iteration,
        "candidate_attempts": state.candidate_attempts_used, "validations": [v.model_dump() for v in state.validations],
        "errors": [e.model_dump() for e in state.errors] + ([error.model_dump()] if error else []),
        "trace": [event.model_dump() for event in state.trace]}, ensure_ascii=False, default=str, indent=2))
    return 0 if state.status == "assessing_risk" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "SV001"))
