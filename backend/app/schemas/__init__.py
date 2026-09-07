"""Public schema contracts for planning capabilities (Pydantic v2)."""
from .common import KnowledgeVersion
from .snapshot import CourseAttemptSnapshot, StudentSnapshot, KnowledgeSnapshot, PriorStudyRequirement, ElectiveQuota
from .planning import PlanningRequest, CandidateCourse, CandidatePlan
from .evidence import RDFTriple, QueryBinding, EvidenceRecord, OntologyFactEvidence
from .validation import ValidationIssue, ValidationResult

__all__ = [
    "PriorStudyRequirement", "ElectiveQuota", "KnowledgeVersion", "CourseAttemptSnapshot", "StudentSnapshot", "KnowledgeSnapshot",
    "PlanningRequest", "CandidateCourse", "CandidatePlan", "RDFTriple", "QueryBinding",
    "EvidenceRecord", "OntologyFactEvidence", "ValidationIssue", "ValidationResult",
]
