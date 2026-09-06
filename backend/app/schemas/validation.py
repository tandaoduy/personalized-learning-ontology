"""Independent Validator output bound to plan and knowledge versions."""
from typing import Literal
from pydantic import AwareDatetime, Field, model_validator
from .common import CourseCode, Identifier, KnowledgeVersion, SchemaModel
from .evidence import EvidenceRecord, OntologyFactEvidence

REQUIRED_RULES = ("course_existence", "duplicate_course", "catalog_credit_match", "prerequisite", "prior_study", "corequisite", "curriculum_membership", "semester_offering", "credit_limit", "completed_course_retake", "elective_quota")

class ValidationErrorRecord(SchemaModel):
    code: Identifier
    message: Identifier
    course_code: CourseCode | None = None


class ValidationIssue(SchemaModel):
    constraint_id: Identifier
    message: Identifier
    course_codes: tuple[CourseCode, ...] = ()
    evidence_ids: tuple[Identifier, ...] = Field(min_length=1)

class RuleCheckResult(SchemaModel):
    rule_id: Identifier
    course_code: CourseCode
    status: Literal["pass", "fail", "skipped", "error"]
    reason: Identifier | None = None
    evidence_ids: tuple[Identifier, ...] = ()

class ValidationResult(SchemaModel):
    plan_id: Identifier
    plan_version: Identifier
    knowledge_versions: KnowledgeVersion
    validator_version: Identifier
    validated_at: AwareDatetime
    status: Literal["valid", "invalid", "partially_validated", "error"]
    rule_checks: tuple[RuleCheckResult, ...] = ()
    checked_rules: tuple[Identifier, ...] = ()
    pending_rules: tuple[Identifier, ...] = REQUIRED_RULES
    errors: tuple[ValidationErrorRecord, ...] = ()
    ontology_evidence: tuple[OntologyFactEvidence, ...] = ()
    violations: tuple[ValidationIssue, ...] = ()
    warnings: tuple[ValidationIssue, ...] = ()
    evidence: tuple[EvidenceRecord, ...] = ()

    @model_validator(mode="after")
    def consistent_verdict(self):
        checked, pending = set(self.checked_rules), set(self.pending_rules)
        if len(checked) != len(self.checked_rules) or len(pending) != len(self.pending_rules):
            raise ValueError("Duplicate scope entries")
        if checked & pending or checked | pending != set(REQUIRED_RULES):
            raise ValueError("Scope must partition the required rules")
        if bool(self.errors) != (self.status == "error"):
            raise ValueError("Error status requires structured errors")
        if self.status == "valid" and (pending or self.violations):
            raise ValueError("Valid requires complete scope without violations")
        if self.status == "invalid" and not self.violations:
            raise ValueError("Invalid requires violations")
        if self.status == "partially_validated" and (not pending or self.violations):
            raise ValueError("Partial requires pending rules without violations")
        if self.status != "error" and (not checked or not self.evidence):
            raise ValueError("A verdict requires completed checks and evidence")
        facts = {item.evidence_id: item for item in self.ontology_evidence}
        if len(facts) != len(self.ontology_evidence):
            raise ValueError("Duplicate ontology evidence IDs")
        for fact in facts.values():
            if fact.ontology_version != self.knowledge_versions.ontology_version:
                raise ValueError("Ontology fact version mismatch")
        for item in self.evidence:
            for ref in item.supporting_evidence_ids:
                if ref not in facts or facts[ref].course_code != item.course_code:
                    raise ValueError("Missing or incompatible supporting fact")
        ids = [item.evidence_id for item in self.evidence]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate evidence IDs")
        for item in self.evidence:
            if item.knowledge_versions != self.knowledge_versions:
                raise ValueError("Evidence snapshot differs from validation snapshot")
        for check in self.rule_checks:
            if check.status in {"pass", "fail"} and not check.evidence_ids:
                raise ValueError("Completed rule check requires evidence")
            if check.status in {"skipped", "error"} and not check.reason:
                raise ValueError("Incomplete rule check requires reason")
            if not set(check.evidence_ids).issubset(ids):
                raise ValueError("Check references missing evidence")
            if check.rule_id in checked and check.status in {"skipped", "error"}:
                raise ValueError("Incomplete rule cannot be checked")
        for issue in self.violations + self.warnings:
            if not set(issue.evidence_ids).issubset(ids):
                raise ValueError("Issue references missing evidence")
        return self
