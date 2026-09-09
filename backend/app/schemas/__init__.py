"""Public schema contracts for planning capabilities (Pydantic v2)."""
from .common import KnowledgeVersion
from .snapshot import CourseAttemptSnapshot, StudentSnapshot, KnowledgeSnapshot, PriorStudyRequirement, ElectiveQuota
from .planning import PlanningRequest, CandidateCourse, CandidatePlan
from .evidence import RDFTriple, QueryBinding, EvidenceRecord, OntologyFactEvidence
from .validation import ValidationIssue, ValidationResult
from .capability import ToolCallContext, ToolError, Provenance, ToolResult
from .feedback import AdjustmentRequest, FeedbackOperation, FeedbackReceipt, FeedbackRequest
from .agent_state import AgentState, ToolTraceEvent, ValidationSummary
from .capability_output import (
    StudentContextOutput, KnowledgeContext, PolicyManifest, CourseInfo,
    CourseSpace, EligibilityDecision, GenerationResult, GenerationAttemptRecord, ValidatedPlan
)

__all__ = [
    "PriorStudyRequirement", "ElectiveQuota", "KnowledgeVersion", "CourseAttemptSnapshot", "StudentSnapshot", "KnowledgeSnapshot",
    "PlanningRequest", "CandidateCourse", "CandidatePlan", "RDFTriple", "QueryBinding",
    "EvidenceRecord", "OntologyFactEvidence", "ValidationIssue", "ValidationResult",
    "ToolCallContext", "ToolError", "Provenance", "ToolResult", "AgentState",
    "ToolTraceEvent", "ValidationSummary", "FeedbackOperation", "FeedbackRequest",
    "AdjustmentRequest", "FeedbackReceipt",
    "StudentContextOutput", "KnowledgeContext", "PolicyManifest", "CourseInfo",
    "CourseSpace", "EligibilityDecision", "GenerationResult", "GenerationAttemptRecord", "ValidatedPlan",
]
