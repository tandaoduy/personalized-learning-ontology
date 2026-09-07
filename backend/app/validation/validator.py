"""Whole-plan validation with deterministic rules and ontology evidence."""
from datetime import datetime, timezone
from pathlib import Path
from backend.app.schemas.planning import CandidatePlan
from backend.app.schemas.snapshot import StudentSnapshot, KnowledgeSnapshot
from backend.app.schemas.validation import ValidationResult, ValidationIssue, ValidationErrorRecord, REQUIRED_RULES, RuleCheckResult
from backend.app.services.ontology_evidence_service import OntologyEvidenceService
from .prerequisite_rule import evaluate_prerequisites, RULE_VERSION

from .rules import (
    catalog_credit_match,
    completed_course_retake,
    corequisite,
    course_existence,
    credit_limit,
    curriculum_membership,
    duplicate_course,
    elective_quota,
    prior_study,
    semester_offering,
)

class StandardValidator:
    VERSION = "standard-academic-v3"

    def __init__(self, evidence_service: OntologyEvidenceService, min_credits: float = 0.0, max_credits: float = 27.0):
        self.evidence_service = evidence_service
        self.min_credits = min_credits
        self.max_credits = max_credits

    def validate(self, plan: CandidatePlan, student_snapshot: StudentSnapshot,
                 knowledge_snapshot: KnowledgeSnapshot) -> ValidationResult:
        student, knowledge = student_snapshot, knowledge_snapshot
        facts, evidence, issues, errors, checks = [], [], [], [], []
        def finish(checked=()):
            pending = tuple(rule for rule in REQUIRED_RULES if rule not in checked)
            status = "error" if errors else "invalid" if issues else "valid" if not pending else "partially_validated"
            return ValidationResult(plan_id=plan.plan_id, plan_version=plan.plan_version,
                knowledge_versions=knowledge.versions, validator_version=self.VERSION,
                validated_at=datetime.now(timezone.utc),
                status=status,
                rule_checks=tuple(checks), checked_rules=checked, pending_rules=pending, errors=tuple(errors),
                ontology_evidence=tuple(facts), evidence=tuple(evidence), violations=tuple(issues))

        if (plan.student_id != student.student_id or plan.target_term_id != knowledge.target_term_id
            or plan.knowledge_versions != knowledge.versions
            or student.student_version != knowledge.versions.student_version
            or student.curriculum_id != knowledge.curriculum_id
            or knowledge.versions.ontology_version != self.evidence_service.ontology_version
            or knowledge.versions.rule_version != RULE_VERSION):
            errors.append(ValidationErrorRecord(code="SNAPSHOT_MISMATCH", message="Plan, student, knowledge or rule version mismatch"))
            return finish()

        source = knowledge.ontology_ref
        if source != self.evidence_service.source_ref and Path(source).resolve().as_uri() != self.evidence_service.source_ref:
            errors.append(ValidationErrorRecord(code="SOURCE_MISMATCH", message="Ontology reference differs from loaded snapshot"))
            return finish()

        def record(rule, code, item, fact=None):
            if fact is not None and not any(f.evidence_id == fact.evidence_id for f in facts):
                facts.append(fact)
            evidence.append(item)
            checks.append(RuleCheckResult(rule_id=rule, course_code=code, status=item.result, evidence_ids=(item.evidence_id,)))
            if item.result == "fail":
                issues.append(ValidationIssue(constraint_id=rule, message=item.rule_result,
                    course_codes=(code,), evidence_ids=(item.evidence_id,)))

        def failed(rule, code, exc):
            message = str(exc) or type(exc).__name__
            errors.append(ValidationErrorRecord(code=message if message.startswith("CATALOG_") else "EVIDENCE_ERROR", message=message, course_code=code))
            checks.append(RuleCheckResult(rule_id=rule, course_code=code, status="error", reason=message))

        # 1. Whole-plan & Independent rules per course
        for code in sorted({course.course_code for course in plan.courses}):
            # Duplicate check
            record("duplicate_course", code, duplicate_course.evaluate(plan, code))
            # Credit limit check (plan total credits)
            record("credit_limit", code, credit_limit.evaluate(plan, code, min_credits=self.min_credits, max_credits=self.max_credits))
            # Completed retake check
            record("completed_course_retake", code, completed_course_retake.evaluate(plan, code, student))
            # Prior study check
            try:
                record("prior_study", code, prior_study.evaluate(plan, code, student, knowledge))
            except Exception as exc:
                failed("prior_study", code, exc)

            # Course existence check
            exists = False
            dependency = "DEPENDENCY_ERROR: course_existence"
            try:
                fact_course = self.evidence_service.get_course_evidence(code, knowledge.versions.ontology_version)
                record("course_existence", code, course_existence.evaluate(plan, code, fact_course), fact_course)
                exists = fact_course.exists
                dependency = "DEPENDENCY_FAILED: course_existence"
            except Exception as exc:
                failed("course_existence", code, exc)

            # Dependent ontology rules
            dependent_rules = ("catalog_credit_match", "prerequisite", "corequisite", "semester_offering", "curriculum_membership", "elective_quota")
            for rule in dependent_rules:
                if not exists:
                    checks.append(RuleCheckResult(rule_id=rule, course_code=code, status="skipped", reason=dependency))
                    continue
                try:
                    if rule == "catalog_credit_match":
                        fact = self.evidence_service.get_course_credit_evidence(code, knowledge.versions.ontology_version)
                        item = catalog_credit_match.evaluate(plan, code, fact)
                    elif rule == "prerequisite":
                        fact = self.evidence_service.get_prerequisite_evidence(code, knowledge.versions.ontology_version)
                        item = evaluate_prerequisites(fact, student, knowledge.versions)
                    elif rule == "corequisite":
                        fact = self.evidence_service.get_corequisite_evidence(code, knowledge.versions.ontology_version)
                        item = corequisite.evaluate(plan, code, student, fact)
                    elif rule == "semester_offering":
                        fact = self.evidence_service.get_semester_offering_evidence(code, knowledge.versions.ontology_version)
                        item = semester_offering.evaluate(plan, code, knowledge, fact)
                    elif rule in ("curriculum_membership", "elective_quota"):
                        fact = self.evidence_service.get_course_category_evidence(code, knowledge.versions.ontology_version)
                        if rule == "curriculum_membership":
                            item = curriculum_membership.evaluate(plan, code, student, fact, knowledge)
                        else:
                            category_facts = {code: fact}
                            if fact.elective_category is not None:
                                for other in sorted(set(student.completed_courses) | {c.course_code for c in plan.courses}):
                                    other_fact = self.evidence_service.get_course_category_evidence(other, knowledge.versions.ontology_version)
                                    category_facts[other] = other_fact
                                    if not any(f.evidence_id == other_fact.evidence_id for f in facts):
                                        facts.append(other_fact)
                            item = elective_quota.evaluate(plan, code, fact, student, knowledge, category_facts)
                    record(rule, code, item, fact)
                except Exception as exc:
                    failed(rule, code, exc)

        checked = tuple(rule for rule in REQUIRED_RULES if any(c.rule_id == rule for c in checks)
            and all(c.status in {"pass", "fail"} for c in checks if c.rule_id == rule))
        return finish(checked)
