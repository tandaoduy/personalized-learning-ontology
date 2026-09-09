# Capability Adapters

Capability adapters wrap business services with the `ToolResult[T]` envelope required by `AgentOrchestrator`. Each adapter:
- Takes `ToolCallContext` + typed business parameters
- Returns `ToolResult[OutputSchema]` with `Provenance`
- Uses helper functions from `_envelope.py` (`ok`/`fail`) to build results

## Adapter Signatures

```python
# Student Context
load_student_context(context: ToolCallContext) -> ToolResult[StudentContextOutput]
  # Full impl: call StudentDataService.get_profile(), normalize history

# Knowledge Context  
load_knowledge_context(context: ToolCallContext) -> ToolResult[KnowledgeContext]
  # Full impl: call OntologyEvidenceService.load(), extract catalog/policy

# Eligibility
build_course_space(
    context: ToolCallContext,
    student_snapshot: StudentSnapshot,
    knowledge_snapshot: KnowledgeSnapshot
) -> ToolResult[CourseSpace]
  # Full impl: call eligibility service, produce EligibilityDecision per course

# Generation
generate_candidates(
    context: ToolCallContext, 
    student_snapshot: StudentSnapshot,
    knowledge_snapshot: KnowledgeSnapshot
) -> ToolResult[GenerationResult]
  # Full impl: call Beam Search, track attempts/states/duplicates

# Validation
validate_candidate(
    context: ToolCallContext,
    candidate: CandidatePlan,
    student_snapshot: StudentSnapshot,
    knowledge_snapshot: KnowledgeSnapshot
) -> ToolResult[ValidatedPlan]
  # Full impl: call StandardValidator.validate(), only return ValidatedPlan if status="valid"
```

## Current State

All five adapters use project data and deterministic services:
- `load_student_context`: loads `StudentDataService` and hashes its JSON source.
- `load_knowledge_context`: binds the RDF content hash, catalog and engine policy.
- `build_course_space`: invokes the legacy eligibility logic.
- `generate_candidates`: invokes Beam Search on a bounded ranked pool of 24 courses.
- `validate_candidate`: mock `ValidationResult` with all 11 `REQUIRED_RULES` checked, minimal ontology `EvidenceRecord` per course; course code `INVALID` → `ToolError` `VALIDATION_FAILED`

## Integration with Orchestrator

The orchestrator calls adapters via:

```python
# 1. Create context
context = orchestrator.create_call_context(state, action="load_student_context", input_hash=...)

# 2. Call adapter with typed args
result = load_student_context(context)  # or with snapshots/candidate as needed

# 3. Apply result
state = orchestrator.apply_result(state, action="load_student_context", context=context, result=result)
```

For `generate_candidates` and `validate_candidates`, use dedicated `apply_generation_result` / `apply_validations`.

## Wiring Full Implementation

To wire real services:

1. **Student Context** (`student_context.py`):
   - Import `StudentDataService` from `backend.app.services`
   - Call `service.get_profile(student_id)` 
   - Normalize history, compute GPA, check warnings
   - Build real `StudentSnapshot` with completed/failed courses

2. **Knowledge Context** (`knowledge.py`):
   - Import `RecommendationEngine` or `OntologyEvidenceService`
   - Load RDF graph from `config.ONTOLOGY_PATH`
   - Extract catalog via SPARQL: course codes, credits, names
   - Build `PolicyManifest` with real credit bounds, completeness flags
   - Set `knowledge_versions` from ontology properties

3. **Eligibility** (`eligibility.py`):
   - Import eligibility logic from `backend.app.services.recommendation.eligibility`
   - For each course in curriculum, check prerequisites/corequisites/history
   - Produce `EligibilityDecision` with status + evidence_ids
   - Link to ontology triples for prerequisite/corequisite relations

4. **Generation** (`generation.py`):
   - Import `backend.app.services.recommendation.candidate_generation`
   - Run Beam Search with `beam_width`, `seed`, eligible courses
   - Track `expanded_states`, `generated_count`, `duplicate_count`
   - Return `CandidatePlan` tuple with `plan_type` (safe/balanced/accelerated)

5. **Validation** (`validation.py`):
   - Import `StandardValidator` from `backend.app.validation`
   - Instantiate with `engine`, `student_snapshot`, `knowledge_snapshot`
   - Call `validator.validate(candidate)` → `ValidationResult`
   - If `status != "valid"`, return `ToolResult` with status="error" + `ToolError` code="VALIDATION_FAILED"
   - Only create `ValidatedPlan` if `status == "valid"`

## Evidence Tracking

Full implementations must:
- Populate `Provenance.knowledge_versions` from `KnowledgeSnapshot.versions`
- Include `source_refs` pointing to ontology files, student data, SPARQL queries
- For validation: include `evidence_ids` referencing `EvidenceRecord` / `OntologyFactEvidence`
- Set `output_hash` via `_envelope.output_hash(output)`

## Testing

Unit tests in `backend/tests/test_capabilities.py`:
- `test_load_student_context_success`: checks `StudentContextOutput` structure
- `test_load_knowledge_context_success`: checks `KnowledgeContext` + versions
- `test_build_course_space_success`: checks `CourseSpace` envelope
- `test_generate_candidates_success`: checks `GenerationResult` with attempt records
- `test_validate_candidate_valid_plan`: expects `ValidatedPlan` with status="valid"
- `test_validate_candidate_invalid_plan`: expects `ToolResult` status="error" for invalid plans

All tests pass against skeleton implementations.

## Next Steps

1. Wire `load_student_context` to `StudentDataService`
2. Wire `load_knowledge_context` to `RecommendationEngine` / `OntologyEvidenceService`
3. Wire `build_course_space` to eligibility logic
4. Wire `generate_candidates` to Beam Search
5. Wire `validate_candidate` to `StandardValidator` with evidence
6. Add integration test: orchestrator → adapters → real services → assert state transitions
7. Connect orchestrator to Flask route `/api/recommendations`

See:
- `docs/DAC_TA_TRIEN_KHAI_MVP.md` — capability contracts
- `docs/MAPPING_CAPABILITY_MODULE_TOOL.md` — module mapping
- `backend/app/agent/README.md` — orchestrator state machine
- `backend/app/schemas/README.md` — schema documentation
