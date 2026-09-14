"""Capability adapters wrapping business services with ToolResult envelope."""
from .student_context import load_student_context
from .knowledge import load_knowledge_context
from .eligibility import build_course_space
from .generation import generate_candidates
from .validation import validate_candidate
from .risk import assess_plan_risks
from .ranking import rank_plans
from .explanation import explain_plans
from .feedback import normalize_feedback
from .confirmation import confirm_plan

__all__ = [
    "load_student_context",
    "load_knowledge_context",
    "build_course_space",
    "generate_candidates",
    "validate_candidate",
    "assess_plan_risks",
    "rank_plans",
    "explain_plans",
    "normalize_feedback",
    "confirm_plan",
]
