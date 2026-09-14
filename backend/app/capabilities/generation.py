"""Generate reproducible candidate plans by invoking the existing Beam Search."""
from hashlib import sha256
from copy import deepcopy
import random

from backend.app.models.student import StudentProfile
from backend.app.schemas import (CandidateCourse, CandidatePlan, GenerationAttemptRecord, GenerationResult,
    AdjustmentRequest, CourseSpace, KnowledgeSnapshot, PlanningRequest, StudentSnapshot, ToolCallContext, ToolError, ToolResult)
from backend.app.services.recommendation_engine import RecommendationEngine
from ._envelope import fail, now, ok


def generate_candidates(context: ToolCallContext, request: PlanningRequest, student_snapshot: StudentSnapshot,
                        knowledge_snapshot: KnowledgeSnapshot, profile: StudentProfile,
                        engine: RecommendationEngine, *, candidate_limit: int = 3, seed: int = 42,
                        course_space: CourseSpace | None = None,
                        adjustment: AdjustmentRequest | None = None) -> ToolResult[GenerationResult]:
    started = now()
    try:
        plans, attempts, seen = [], [], set()
        eligible, passed, completed_counts, goal = engine.get_eligible_courses(profile)
        if course_space is not None:
            allowed = course_space.eligible_courses | course_space.conditional_courses
            eligible = [item for item in eligible if item.code in allowed]
        eligible = sorted(eligible, key=lambda item: item.code)
        # The legacy public method searches every eligible course and has no
        # expansion budget. Limit its already ranked input before invoking the
        # same Beam Search primitive so an Agent run can honor its time budget.
        for offset in range(candidate_limit):
            rng = random.Random(seed + offset)
            # Legacy ranking adds noise in place; isolate each attempt.
            ranked = engine._random_select_electives(deepcopy(eligible), engine.elective_quotas, goal, rng, seed + offset)
            selected, _ = engine._beam_search_optimize(profile, ranked[:24], completed_counts, goal, rng, passed)
            courses = tuple(CandidateCourse(course_code=item.code, credits=float(item.credits)) for item in selected)
            if not courses:
                attempts.append(GenerationAttemptRecord(attempt_id=f"attempt-{offset + 1}", state_count=0, reason="empty_beam_result"))
                continue
            selected_codes = {course.course_code for course in courses}
            if adjustment and (not adjustment.must_include.issubset(selected_codes)
                               or adjustment.must_exclude & selected_codes):
                attempts.append(GenerationAttemptRecord(attempt_id=f"attempt-{offset + 1}", state_count=len(courses), reason="adjustment_not_satisfied"))
                continue
            plan_type = "accelerated" if request.goal == "accelerated" else ("safe" if offset == 0 else "balanced")
            course_set_hash = "sha256:" + sha256(
                ",".join(sorted(course.course_code for course in courses)).encode()
            ).hexdigest()
            if course_set_hash in seen:
                attempts.append(GenerationAttemptRecord(attempt_id=f"attempt-{offset + 1}", candidate_hash=course_set_hash, state_count=len(courses), reason="duplicate_course_set"))
                continue
            plan = CandidatePlan(plan_id=f"{context.run_id}-plan-{offset + 1}", plan_version="beam-v1",
                request_id=request.request_id, student_id=student_snapshot.student_id, target_term_id=request.target_term_id,
                knowledge_versions=knowledge_snapshot.versions, plan_type=plan_type, courses=courses)
            seen.add(course_set_hash); plans.append(plan)
            attempts.append(GenerationAttemptRecord(attempt_id=f"attempt-{offset + 1}", candidate_hash=course_set_hash, state_count=len(courses), reason="beam_selected"))
        output = GenerationResult(candidates=tuple(plans), attempt_records=tuple(attempts), seed=seed,
            generator_config_hash="sha256:" + sha256(f"legacy-beam:{engine.beam_width}".encode()).hexdigest(),
            expanded_states=sum(item.state_count for item in attempts), generated_count=len(plans) + sum(1 for item in attempts if item.reason == "duplicate_course_set"),
            duplicate_count=sum(1 for item in attempts if item.reason == "duplicate_course_set"),
            stop_reason="target_met" if plans else "no_candidates")
        return ok(context, "generate_candidates", output, started_at=started,
            knowledge_versions=knowledge_snapshot.versions, source_refs=(knowledge_snapshot.ontology_ref,))
    except Exception as exc:
        return fail(context, "generate_candidates", ToolError(code="GENERATION_ERROR", message=str(exc)), started_at=started)
