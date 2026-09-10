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
- `load_student_context`: loads `StudentDataService`, hashes its JSON source, maps only
  `CNTT`/`Công nghệ thông tin` and `KHMT`/`Khoa học máy tính` to ontology IRIs, and rejects
  an unknown major rather than defaulting it to CNTT. Course-attempt statuses are matched
  exactly: `Đạt`, `Miễn`, `Không tính điểm`, `Chưa đạt`.
- `load_knowledge_context`: binds the RDF content hash, catalog and engine policy. The pilot
  accepts only `target_term_id=next-term`, defined as `current_semester + 1`; it rejects a
  historical or arbitrary term until a versioned academic-calendar mapping exists.
- `build_course_space`: invokes the legacy eligibility logic.
- `generate_candidates`: invokes Beam Search on a bounded ranked pool of 24 courses.
- `validate_candidate`: invokes the independent `StandardValidator` and retains its real
  validation result and ontology/rule evidence for both valid and invalid candidates.

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

## Remaining work

The current baseline still needs a curriculum manifest per cohort, an academic-calendar
mapping for terms other than `next-term`, and an official academic-warning source. M4
currently records a versioned research proxy and marks it as non-official in the output.

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

Tests cover the explicit major/status mappings and rejection of unsupported target terms,
alongside evidence, Validator and end-to-end pipeline tests.

See:
- `docs/DAC_TA_TRIEN_KHAI_MVP.md` — capability contracts
- `docs/MAPPING_CAPABILITY_MODULE_TOOL.md` — module mapping
- `backend/app/agent/README.md` — orchestrator state machine
- `backend/app/schemas/README.md` — schema documentation
