"""Wrap legacy eligibility decisions without letting it mutate Agent State."""
from backend.app.models.student import StudentProfile
from backend.app.schemas import CourseSpace, EligibilityDecision, KnowledgeSnapshot, StudentSnapshot, ToolCallContext, ToolError, ToolResult
from backend.app.services.recommendation_engine import RecommendationEngine
from ._envelope import fail, now, ok


def build_course_space(context: ToolCallContext, student_snapshot: StudentSnapshot,
                       knowledge_snapshot: KnowledgeSnapshot, profile: StudentProfile,
                       engine: RecommendationEngine) -> ToolResult[CourseSpace]:
    started = now()
    try:
        eligible, _, _, _ = engine.get_eligible_courses(profile)
        eligible_codes = {item.code for item in eligible}
        decisions = []
        for code in sorted(knowledge_snapshot.curriculum_courses or frozenset(engine.course_data)):
            if code in eligible_codes:
                decisions.append(EligibilityDecision(course_code=code, status="eligible", reason_code="ENGINE_ELIGIBLE"))
            elif code in student_snapshot.completed_courses:
                decisions.append(EligibilityDecision(course_code=code, status="ineligible", reason_code="ALREADY_COMPLETED"))
            else:
                decisions.append(EligibilityDecision(course_code=code, status="ineligible", reason_code="ENGINE_FILTERED"))
        output = CourseSpace(snapshot_id=f"space-{student_snapshot.student_id}-{knowledge_snapshot.snapshot_id}", decisions=tuple(decisions))
        return ok(context, "build_course_space", output, started_at=started,
                  knowledge_versions=knowledge_snapshot.versions,
                  source_refs=(knowledge_snapshot.ontology_ref,))
    except Exception as exc:
        return fail(context, "build_course_space", ToolError(code="ELIGIBILITY_ERROR", message=str(exc)), started_at=started)
