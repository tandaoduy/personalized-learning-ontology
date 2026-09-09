"""Load a versioned StudentSnapshot from the project's student-data source."""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from backend.app.models.student import StudentProfile
from backend.app.schemas import PlanningRequest, StudentContextOutput, StudentSnapshot, ToolCallContext, ToolError, ToolResult
from backend.app.services.student_data_service import StudentDataService
from ._envelope import fail, now, ok


def _student_version(service: StudentDataService) -> str:
    path = Path(service.json_path)
    if not path.is_file():
        raise FileNotFoundError("STUDENT_SOURCE_MISSING")
    return "sha256:" + sha256(path.read_bytes()).hexdigest()


def _major_id(major: str) -> str:
    base = "http://www.semanticweb.org/henrydao/ontologies/2025/7/TrainingProgramOntology#"
    normalized = "".join(ch for ch in major.upper() if ch.isalnum())
    return base + ("KHMT" if "KHOAHOCMAYTINH" in normalized else "CNTT")


def snapshot_from_profile(profile: StudentProfile, version: str, captured_at: datetime) -> StudentSnapshot:
    attempts = []
    for item in profile.course_attempts:
        status = item.status.casefold()
        outcome = "passed" if "đạt" in status or "mien" in status or "miễn" in status else "failed"
        attempts.append({"course_code": item.course_code, "term_id": str(item.semester_taken or "unknown"),
                         "outcome": outcome, "grade": item.grade if item.grade_specified else None})
    return StudentSnapshot(
        student_id=profile.student_id, student_version=version, captured_at=captured_at,
        curriculum_id=f"CURRICULUM-{profile.year_admitted}", major_id=_major_id(profile.major),
        specialization_id=None, current_semester=profile.current_semester,
        completed_courses=frozenset(profile.passed_courses), failed_courses=frozenset(profile.failed_courses),
        attempts=tuple(attempts), earned_credits=profile.total_credits_accumulated,
        gpa=profile.gpa_accumulated if profile.gpa_accumulated >= 0 else None,
        gpa_scale=10 if profile.gpa_accumulated > 4 else 4,
    )


def load_student_context(context: ToolCallContext, request: PlanningRequest,
                         student_service: StudentDataService) -> ToolResult[StudentContextOutput]:
    """Read the requested student record and bind it to a content hash."""
    started = now()
    try:
        profile = student_service.get_student(request.student_id)
        if profile is None:
            return fail(context, "load_student_context", ToolError(code="STUDENT_NOT_FOUND", message="Student does not exist"), started_at=started)
        version = _student_version(student_service)
        snapshot = snapshot_from_profile(profile, version, started)
        return ok(context, "load_student_context", StudentContextOutput(
            student_snapshot=snapshot, source_manifest_ref=Path(student_service.json_path).resolve().as_uri(),
            target_term_id=request.target_term_id, history_cutoff=str(profile.current_semester),
            normalization_rule_version="student-snapshot-v1",
        ), started_at=started, source_refs=(Path(student_service.json_path).resolve().as_uri(),))
    except (ValueError, FileNotFoundError) as exc:
        return fail(context, "load_student_context", ToolError(code=str(exc), message=str(exc)), started_at=started)
    except Exception as exc:
        return fail(context, "load_student_context", ToolError(code="STUDENT_CONTEXT_ERROR", message=str(exc)), started_at=started)
