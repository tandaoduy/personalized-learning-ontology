"""Agent pipeline coordinating capabilities with structured logging."""
from __future__ import annotations

from hashlib import sha256
import json
import logging
from time import perf_counter

from backend.app.agent.orchestrator import AgentOrchestrator
from backend.app.capabilities import (
    build_course_space,
    generate_candidates,
    load_knowledge_context,
    load_student_context,
    assess_plan_risks,
    rank_plans,
    validate_candidate,
)
from backend.app.schemas import PlanningRequest, Provenance, ToolError, ToolResult, ValidatedPlan
from backend.app.services.ontology_evidence_service import OntologyEvidenceService
from backend.app.services.ranking_context_service import build_ranking_context
from backend.app.services.recommendation_engine import RecommendationEngine
from backend.app.services.student_data_service import StudentDataService

logger = logging.getLogger(__name__)


def digest(value: object) -> str:
    return "sha256:" + sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


class _RunEvidenceCache:
    """Read-through cache: identical RDF facts are queried once per planning run."""
    def __init__(self, service: OntologyEvidenceService):
        self._service = service
        self._cache: dict[tuple, object] = {}

    def __getattr__(self, name):
        attribute = getattr(self._service, name)
        if not callable(attribute) or not name.startswith("get_"):
            return attribute
        def cached(*args, **kwargs):
            key = (name, args, tuple(sorted(kwargs.items())))
            if key not in self._cache:
                self._cache[key] = attribute(*args, **kwargs)
            return self._cache[key]
        return cached


class AgentPipeline:
    """Coordinates capability execution with orchestrator state management and detailed logging."""

    def __init__(
        self,
        student_service: StudentDataService,
        engine: RecommendationEngine,
        evidence: OntologyEvidenceService,
        orchestrator: AgentOrchestrator | None = None,
    ):
        self.student_service = student_service
        self.engine = engine
        self.evidence = evidence
        self.orchestrator = orchestrator or AgentOrchestrator()

    def run_planning_flow(self, request: PlanningRequest) -> dict:
        """Execute full planning flow: context → eligibility → generation → validation."""
        run_id = f"RUN_{request.request_id}"
        run_started = perf_counter()
        tool_provenance = []
        evidence = _RunEvidenceCache(self.evidence)
        logger.info("=== AGENT PIPELINE START ===")
        logger.info("Run ID: %s", run_id)
        logger.info("Student ID: %s, Target: %s, Goal: %s", request.student_id, request.target_term_id, request.goal)

        state = self.orchestrator.create_run(request, run_id=run_id)
        state = self.orchestrator.start(state)
        logger.info("Initial state: %s (revision=%d)", state.status, state.state_revision)

        # Step 1: Load Student Context
        logger.info("\n--- [1/5] LOADING STUDENT CONTEXT ---")
        context = self.orchestrator.create_call_context(state, "load_student_context", digest(request.model_dump()))
        logger.info("Call ID: %s, Deadline: %s", context.call_id, context.deadline_at.isoformat())

        student_result = load_student_context(context, request, self.student_service)
        logger.info("Status: %s", student_result.status)
        if student_result.status == "error":
            logger.error("Error code: %s, message: %s", student_result.error.code, student_result.error.message)
            return self._error_response(state, student_result.error)

        state = self.orchestrator.apply_result(state, "load_student_context", context, student_result)
        tool_provenance.append(student_result.provenance)
        if state.status == "failed":
            return self._error_response(state, state.errors[-1])
        student = student_result.output.student_snapshot
        logger.info("Student loaded: %s, completed=%d courses, GPA=%.2f", student.student_id, len(student.completed_courses), student.gpa or 0)
        logger.info("State transition: loading_context → %s (revision=%d)", state.status, state.state_revision)

        # Step 2: Load Knowledge Context
        logger.info("\n--- [2/5] LOADING KNOWLEDGE CONTEXT ---")
        context = self.orchestrator.create_call_context(
            state, "load_knowledge_context", digest({"request": request.model_dump(), "student": student.model_dump()})
        )
        logger.info("Call ID: %s", context.call_id)

        knowledge_result = load_knowledge_context(context, request, student, self.engine, evidence)
        logger.info("Status: %s", knowledge_result.status)
        if knowledge_result.status == "error":
            logger.error("Error: %s", knowledge_result.error.message)
            return self._error_response(state, knowledge_result.error)

        state = self.orchestrator.apply_result(state, "load_knowledge_context", context, knowledge_result)
        tool_provenance.append(knowledge_result.provenance)
        if state.status == "failed":
            return self._error_response(state, state.errors[-1])
        knowledge = knowledge_result.output.knowledge_snapshot
        catalog = knowledge_result.output.catalog
        logger.info("Ontology loaded: version=%s, catalog=%d courses", knowledge.versions.ontology_version, len(catalog))
        logger.info("Policy: credits=%d-%d, quotas=%s", self.engine.min_credits, self.engine.max_credits, self.engine.elective_quotas)
        logger.info("State transition: loading_knowledge → %s (revision=%d)", state.status, state.state_revision)

        # Step 3: Build Course Space (Eligibility)
        logger.info("\n--- [3/5] BUILD COURSE SPACE (ELIGIBILITY) ---")
        profile = self.student_service.get_student(request.student_id)
        context = self.orchestrator.create_call_context(
            state, "build_course_space", digest({"student": student.model_dump(), "knowledge": knowledge.model_dump()})
        )
        logger.info("Call ID: %s", context.call_id)

        eligibility_result = build_course_space(context, student, knowledge, profile, self.engine)
        logger.info("Status: %s", eligibility_result.status)
        if eligibility_result.status == "error":
            logger.error("Error: %s", eligibility_result.error.message)
            return self._error_response(state, eligibility_result.error)

        state = self.orchestrator.apply_result(state, "build_course_space", context, eligibility_result)
        tool_provenance.append(eligibility_result.provenance)
        if state.status == "failed":
            return self._error_response(state, state.errors[-1])
        decisions = eligibility_result.output.decisions
        eligible_count = sum(1 for d in decisions if d.status == "eligible")
        ineligible_count = sum(1 for d in decisions if d.status == "ineligible")
        logger.info("Course space built: eligible=%d, ineligible=%d (total=%d)", eligible_count, ineligible_count, len(decisions))
        logger.info("State transition: building_course_space → %s (revision=%d)", state.status, state.state_revision)

        # Step 4: Generate Candidates
        logger.info("\n--- [4/5] GENERATE CANDIDATES (BEAM SEARCH) ---")
        context = self.orchestrator.create_call_context(
            state, "generate_candidates", digest({"space": eligibility_result.output.model_dump(), "seed": state.seed}),
            timeout_seconds=60,
        )
        logger.info("Call ID: %s, Seed: %d, Beam width: %d", context.call_id, state.seed, self.engine.beam_width)

        generation = generate_candidates(context, request, student, knowledge, profile, self.engine,
            candidate_limit=3, seed=state.seed, course_space=eligibility_result.output)
        logger.info("Status: %s", generation.status)
        if generation.status == "error" or not generation.output or not generation.output.candidates:
            error = generation.error or ToolError(code="NO_CANDIDATES", message="Beam Search returned no candidates")
            logger.error("Generation failed: %s", error.message)
            return self._error_response(state, error)

        hashes = tuple("sha256:" + sha256(plan.model_dump_json().encode()).hexdigest() for plan in generation.output.candidates)
        state = self.orchestrator.apply_generation_result(
            state,
            context,
            generation,
            hashes,
            len(generation.output.attempt_records),
            generation.output.expanded_states,
        )
        tool_provenance.append(generation.provenance)
        if state.status != "validating":
            return self._error_response(state, state.errors[-1])
        logger.info("Candidates generated: %d plans, attempts=%d, expanded_states=%d, duplicates=%d",
                    len(generation.output.candidates), len(generation.output.attempt_records),
                    generation.output.expanded_states, generation.output.duplicate_count)
        for i, candidate in enumerate(generation.output.candidates):
            logger.info("  Plan %d: type=%s, courses=%d, credits=%.1f",
                        i + 1, candidate.plan_type, len(candidate.courses), sum(c.credits for c in candidate.courses))
        logger.info("State transition: generating → %s (revision=%d)", state.status, state.state_revision)

        # Step 5: Validate Candidates
        # One shared call context so provenance.call_id / input_hash match apply_validations.
        logger.info("\n--- [5/5] VALIDATE CANDIDATES ---")
        batch_hash = digest([c.model_dump() for c in generation.output.candidates])
        context = self.orchestrator.create_call_context(
            state, "validate_candidates", batch_hash, timeout_seconds=180
        )
        logger.info("Call ID: %s (batch of %d)", context.call_id, len(generation.output.candidates))

        validation_results = []
        validated_plans = []
        batch_tool_result = None
        validation_started = None
        for i, candidate in enumerate(generation.output.candidates):
            logger.info("Validating plan %d/%d: %s", i + 1, len(generation.output.candidates), candidate.plan_id)
            validated = validate_candidate(
                context,
                candidate,
                student,
                knowledge,
                evidence,
                min_credits=self.engine.min_credits,
                max_credits=self.engine.max_credits,
            )
            tool_provenance.append(validated.provenance)
            if validation_started is None:
                validation_started = validated.provenance.started_at
            logger.info("  Status: %s", validated.status)
            if validated.status == "error":
                logger.error("  Validator error: %s", validated.error.message if validated.error else "unknown")
                return self._error_response(state, validated.error)
            item = validated.output.validation if hasattr(validated.output, "validation") else validated.output
            if isinstance(validated.output, ValidatedPlan):
                validated_plans.append(validated.output)
            logger.info("  Validation result: status=%s, checked=%d/%d, violations=%d, evidence=%d, ontology_facts=%d",
                        item.status, len(item.checked_rules), len(item.checked_rules) + len(item.pending_rules),
                        len(item.violations), len(item.evidence), len(item.ontology_evidence))
            logger.info("  Versions: ontology=%s rule=%s validator=%s",
                        item.knowledge_versions.ontology_version, item.knowledge_versions.rule_version,
                        item.validator_version)
            if item.violations:
                for v in item.violations[:3]:
                    courses_str = ",".join(v.course_codes) if v.course_codes else "N/A"
                    logger.info("    Violation: constraint=%s, courses=%s, evidence=%s",
                                v.constraint_id, courses_str, ",".join(v.evidence_ids))
            validation_results.append(item)
            batch_tool_result = validated

        if not validation_results or batch_tool_result is None:
            error = ToolError(code="VALIDATION_ERROR", message="No validation results produced")
            logger.error("Validation failed: %s", error.message)
            return self._error_response(state, error)

        # Bind the trace to the entire batch, not just the last candidate.
        batch_tool_result = ToolResult(status="ok", output=tuple(validation_results),
            provenance=Provenance(
                call_id=context.call_id, tool_name="validate_candidates",
                tool_version=batch_tool_result.provenance.tool_version,
                input_hash=context.input_hash,
                output_hash=digest([v.model_dump(mode="json") for v in validation_results]),
                knowledge_versions=knowledge.versions, source_refs=(knowledge.ontology_ref,),
                evidence_ids=tuple(e.evidence_id for v in validation_results for e in v.evidence),
                started_at=validation_started, finished_at=batch_tool_result.provenance.finished_at))
        state = self.orchestrator.apply_validations(
            state, tuple(validation_results), context, batch_tool_result
        )
        valid_count = sum(1 for v in validation_results if v.status == "valid")
        invalid_count = sum(1 for v in validation_results if v.status != "valid")
        logger.info("Validation complete: valid=%d, invalid=%d", valid_count, invalid_count)
        logger.info("State transition: validating → %s (revision=%d)", state.status, state.state_revision)

        ranking_context = None
        risk_batch = None
        ranking_result = None
        if state.status == "assessing_risk":
            logger.info("\n--- [6/7] ASSESS PLAN RISK ---")
            try:
                ranking_context = build_ranking_context(profile, student, knowledge, request, self.engine)
            except Exception as exc:
                error = ToolError(code="RANKING_CONTEXT_ERROR", message=str(exc))
                state = self.orchestrator.fail_for_missing_data(state, error)
                return self._result(state, request, student, knowledge_result, eligibility_result,
                    generation, validation_results, tool_provenance, run_started,
                    ranking_context=None, risk_batch=None, ranking_result=None)
            context = self.orchestrator.create_call_context(state, "assess_plan_risk",
                digest({"plans": [p.candidate_hash for p in validated_plans],
                        "ranking_context": ranking_context.model_dump(mode="json")}), timeout_seconds=10)
            risk_result = assess_plan_risks(context, tuple(validated_plans), student, ranking_context)
            state = self.orchestrator.apply_result(state, "assess_plan_risk", context, risk_result)
            tool_provenance.append(risk_result.provenance)
            if risk_result.status == "error" or state.status == "failed":
                return self._error_response(state, risk_result.error or state.errors[-1])
            risk_batch = risk_result.output
            logger.info("Risk complete: plans=%d, status=%s", len(risk_batch.results), state.status)

            logger.info("\n--- [7/7] RANK VALID PLANS + DIVERSITY ---")
            context = self.orchestrator.create_call_context(state, "rank_valid_plans",
                digest({"risk": risk_batch.model_dump(mode="json"),
                        "ranking_context": ranking_context.model_dump(mode="json")}), timeout_seconds=10)
            ranked = rank_plans(context, tuple(validated_plans), risk_batch, ranking_context,
                request, profile, self.engine)
            state = self.orchestrator.apply_result(state, "rank_valid_plans", context, ranked)
            tool_provenance.append(ranked.provenance)
            if ranked.status == "error" or state.status == "failed":
                return self._error_response(state, ranked.error or state.errors[-1])
            ranking_result = ranked.output
            logger.info("Ranking complete: scored=%d, selected=%d, recommended=%s, status=%s",
                len(ranking_result.scored_plans), len(ranking_result.selected_plans),
                ranking_result.recommended_plan_id, state.status)

        logger.info("\n=== AGENT PIPELINE COMPLETE ===")
        logger.info("Final state: %s", state.status)
        logger.info("Budget used: candidates=%d/%d, expanded_states=%d/%d",
                    state.candidate_attempts_used, state.max_candidate_attempts,
                    state.expanded_states_used, state.max_expanded_states)

        return self._result(state, request, student, knowledge_result, eligibility_result,
            generation, validation_results, tool_provenance, run_started,
            ranking_context=ranking_context, risk_batch=risk_batch, ranking_result=ranking_result)

    def _result(self, state, request, student, knowledge_result, eligibility_result,
                generation, validation_results, tool_provenance, run_started, *,
                ranking_context, risk_batch, ranking_result):
        knowledge = knowledge_result.output.knowledge_snapshot
        return {
            "success": state.status != "failed",
            "run_id": state.run_id,
            "status": state.status,
            "iteration": state.iteration,
            "request": request.model_dump(mode="json"),
            "state": state.model_dump(mode="json"),
            "student_snapshot": student.model_dump(mode="json"),
            "knowledge_snapshot": knowledge.model_dump(mode="json"),
            "knowledge_context": knowledge_result.output.model_dump(mode="json"),
            "course_space": eligibility_result.output.model_dump(mode="json"),
            "generation": generation.output.model_dump(mode="json"),
            "candidates": [c.model_dump(mode="json") for c in generation.output.candidates],
            "validations": [v.model_dump(mode="json") for v in validation_results],
            "ranking_context": ranking_context.model_dump(mode="json") if ranking_context else None,
            "risk": risk_batch.model_dump(mode="json") if risk_batch else None,
            "ranking": ranking_result.model_dump(mode="json") if ranking_result else None,
            "tool_provenance": [p.model_dump(mode="json") for p in tool_provenance],
            "elapsed_seconds": perf_counter() - run_started,
            "errors": [e.model_dump(mode="json") for e in state.errors],
            "budget": {
                "candidate_attempts_used": state.candidate_attempts_used,
                "candidate_attempts_max": state.max_candidate_attempts,
                "expanded_states_used": state.expanded_states_used,
                "expanded_states_max": state.max_expanded_states,
            },
            "trace": [event.model_dump(mode="json") for event in state.trace],
        }

    def _error_response(self, state, error: ToolError) -> dict:
        """Build error response with state snapshot."""
        return {
            "success": False,
            "error": error.model_dump(),
            "run_id": state.run_id,
            "status": state.status,
            "iteration": state.iteration,
            "trace": [event.model_dump() for event in state.trace],
        }


def run_agent_pipeline(
    request: PlanningRequest,
    student_service: StudentDataService,
    engine: RecommendationEngine,
    evidence: OntologyEvidenceService,
    orchestrator: AgentOrchestrator | None = None,
) -> dict:
    """Convenience entrypoint for Flask routes and demo scripts."""
    return AgentPipeline(student_service, engine, evidence, orchestrator).run_planning_flow(request)
