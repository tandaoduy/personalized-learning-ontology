# CLAUDE.md

File này cung cấp hướng dẫn cho Claude Code (claude.ai/code) khi làm việc với mã nguồn trong repository này.

## Tổng quan dự án

Đây là hệ thống cố vấn học tập dựa trên Ontology, hỗ trợ sinh viên và cố vấn lập kế hoạch học phần. Hệ thống sử dụng ontology RDF/OWL làm nguồn quyết định chính thống cho quy tắc chương trình đào tạo, tiên quyết và các ràng buộc, kết hợp với thuật toán Beam Search để sinh kế hoạch học tập cá nhân hóa.

Codebase đang chuyển đổi từ recommendation engine nguyên khối sang kiến trúc AI Agent dựa trên capability với validation chính thức và theo dõi evidence.

## Lệnh phát triển

### Chạy ứng dụng
```powershell
# Kích hoạt môi trường ảo
.\.venv\Scripts\Activate.ps1

# Khởi động máy chủ Flask (chạy trên http://localhost:5000)
python run_app.py

# Cách khác: Sử dụng Flask CLI
python -m flask --app backend.app.app:app run
```

Điểm WSGI: `backend.app.app:app`

### Kiểm thử
```powershell
# Cài đặt dependencies dành cho dev trước
python -m pip install -r requirements-dev.txt

# Chạy tất cả các test
python -m pytest

# Chạy test với coverage
python -m pytest --cov=backend.app.services --cov-report=term-missing

# Chạy bộ benchmark đầy đủ (sinh file benchmark_results/test_report.md)
python experiments/run_benchmark.py

# Chạy một file test cụ thể
python -m pytest backend/tests/test_recommendation_engine.py -v
```

Cấu hình test: `pytest.ini`
Test fixtures: `backend/tests/conftest.py`

### Build Frontend
```powershell
# Build CSS và copy vendor assets vào backend/app/static/vendor/
npm run build:ui

# Watch mode cho development
npm run watch:css
```

Mã nguồn frontend nằm trong `frontend/`; output vào `backend/app/static/vendor/`

### Migration dữ liệu
```powershell
# Migration dữ liệu sinh viên (dùng pypdf để extract bảng điểm)
python scripts/migrate_student_data.py

# Chạy test truy vấn SPARQL
python backend/tests/test_sparql.py
```

### Cấu hình môi trường
Chế độ development (mặc định):
```powershell
python run_app.py
```

Chế độ production:
```powershell
$env:APP_ENV = "production"
$env:SECRET_KEY = "your-random-secret-key-here"
python run_app.py
```

## Architecture

### Ontology as Source of Truth

The RDF ontology (`knowledge/ontology/ontology_v23.rdf`) is the authoritative source for:
- Curriculum structure and course relationships
- Prerequisites and corequisites
- Course credits, semester offerings, specialization requirements
- Major and specialization course mappings

**Critical principle:** The LLM must NOT generate or infer academic rules, course codes, credit values, or prerequisite relationships. All academic decisions must be grounded in ontology evidence or explicit rule engine results.

### Core Services Architecture

The system is organized into layers:

**1. Data Layer**
- `StudentDataService`: Manages student profiles, history, GPA from JSON/CSV
- Currently uses file-based storage; PostgreSQL/SQLAlchemy is the target architecture

**2. Knowledge Layer**
- `RecommendationEngine`: Loads and queries RDF ontology using RDFLib
- `OntologyEvidenceService`: Extracts and tracks evidence (triples, queries, versions) for every decision
- SPARQL queries in `knowledge/queries/` (structure exists but queries not yet extracted)

**3. Business Logic Layer**
- **Eligibility**: Determines which courses are eligible, conditional, or ineligible based on prerequisites, student progress
- **Candidate Generation**: Uses Beam Search to generate Safe/Balanced/Accelerated course plan candidates
- **Validation**: `StandardValidator` v3 validates plans against 11 hard constraints (prerequisites, corequisites, credit limits, semester offerings, curriculum membership, quotas, etc.)
- **Risk Analysis**: `ProgressRiskAnalyzer` assesses LOW/MEDIUM/HIGH risk based on workload, debt, GPA
- **Explanation**: `ExplanationGenerator` creates natural language explanations grounded in evidence

**4. Agent Architecture (In Progress)**
- `backend/app/agent/`: Orchestrator skeleton exists but not yet implemented
- `backend/app/schemas/`: Pydantic schemas for PlanningRequest, StudentSnapshot, KnowledgeSnapshot, ValidationResult, CandidatePlan, Evidence
- `backend/app/validation/`: StandardValidator v3 is complete with 11 rules but not yet integrated into Agent/API flow

Target architecture uses **capability-based orchestration**: Student Context → Ontology → Eligibility → Candidate Generator → Validator → Risk → Ranking → Explanation → Feedback/Re-planning. Each capability has explicit input/output schemas, preconditions, postconditions, and provenance tracking.

### Recommendation Engine Implementation

The recommendation engine (`backend/app/services/recommendation_engine.py`) combines multiple concerns via mixins:
- Ontology querying (prerequisites, corequisites, offerings, specializations)
- Eligibility checking (student-specific constraint validation)
- Candidate generation (Beam Search with configurable beam width)
- Plan risk assessment (workload, prerequisite debt, course links)

**Internal organization:** Core algorithm components are in `backend/app/services/recommendation/`:
- `constants.py`: URIs, property names, credit limits, weights
- `ontology.py`: RDF graph operations
- `eligibility.py`: Course filtering logic
- `candidate_generation.py`: Beam Search implementation
- `plan_risk.py`: Risk scoring heuristics

These use shared context via mixins, not yet refactored to independent capabilities.

### Validation Architecture

`StandardValidator` (version `standard-academic-v3`) enforces 11 required rules:
1. `course_existence`: Course exists in ontology
2. `catalog_credit_match`: Credit value matches catalog
3. `duplicate_course`: No duplicate courses in plan
4. `completed_course_retake`: Cannot retake completed courses
5. `credit_limit`: Total credits within min/max bounds (default 10-27)
6. `prerequisite`: Prerequisites satisfied from history or earlier in plan
7. `corequisite`: Corequisites co-registered or already completed
8. `curriculum_membership`: Course belongs to student's major/specialization curriculum
9. `prior_study`: No course from student's completed history
10. `semester_offering`: Course offered in target semester
11. `elective_quota`: Elective quotas not exceeded

**Key invariants:**
- Validation is deterministic: same plan + same snapshot → same result
- Validation requires version coherence: plan's `knowledge_versions` must match `StudentSnapshot` and `KnowledgeSnapshot` versions
- Only plans with `status="valid"` proceed to ranking and display
- Invalid plans return specific `ValidationIssue` records with evidence
- Validation errors (missing data, version mismatch) are distinguished from violations

Each rule produces evidence pointing back to ontology triples, SPARQL results, or rule inputs for full traceability.

### Configuration

Configuration lives in `backend/app/config.py` with environment-based overrides:
- `ONTOLOGY_PATH`: Path to RDF file (default: `knowledge/ontology/ontology_v23.rdf`)
- `STUDENT_DATA_JSON/CSV`: Student data paths
- `REGISTER_MIN_CREDITS`, `REGISTER_MAX_CREDITS`: Credit bounds (10-27)
- `BEAM_WIDTH`: Beam Search beam width (default 8)
- `WEIGHT_DEBT`, `WEIGHT_LINK`, `WEIGHT_DELAY`: Heuristic weights for Beam Search scoring
- `ELECTIVE_QUOTAS`: Quota limits for general/physical/foundation/specialization electives

Paths use relative references from `BASE_DIR` for portability across machines.

### Routes and API Structure

**Student Role:** `/student/*`
- `/student`: Dashboard
- `/student/history`: Course history
- `/student/profile`: Profile editor
- `/student/plan`: Study plan recommendations

**Advisor Role:** `/advisor/*`
- `/advisor/students`: Student list
- `/advisor/at-risk`: At-risk student analysis
- `/advisor/student-editor`: Student data editor
- `/advisor/scenarios`: Scenario modeling
- `/advisor/consultation`: Consultation records
- `/advisor/reports`: Reporting

**API Endpoints:** `/api/*`
- `/api/auth/*`: Authentication (login, logout, register)
- `/api/students/*`: CRUD operations for student records
- `/api/recommendations`: Generate recommendations
- `/api/courses/<course_code>/prerequisite-chain`: Prerequisite dependency chain
- `/api/health`: Health check
- `/api/debug/pipeline/<student_id>`: Debug pipeline (development only)

Development-only routes (`/components/*`, `/api/debug/*`) return 404 in production mode.

## Important Patterns and Constraints

### Version Tracking and Provenance

Every decision must be traceable:
- Ontology files have version metadata (`.properties` files alongside `.rdf`/`.owl`)
- Student data includes `student_version`
- Validation results store `knowledge_versions`, `validator_version`, `validated_at`
- Evidence records include `ontology_version`, `rule_version`, query IDs/hashes

When ontology or student data changes, dependent validation results become stale and must be re-validated.

### Hard Constraints vs. Preferences

**Hard constraints** (enforced by StandardValidator):
- Prerequisites, corequisites
- Credit limits
- Semester offerings
- Curriculum membership
- Elective quotas

**Preferences** (used for ranking):
- Course recommended semester
- Workload balance
- Prerequisite debt minimization
- Degree completion speed (Safe/Balanced/Accelerated)

Ranking and Learning-to-Rank can only reorder valid plans; they cannot override hard constraints or generate invalid plans.

### UTF-8 Handling

The codebase handles Vietnamese text throughout. `run_app.py` includes UTF-8 reconfiguration for Windows terminals to prevent encoding errors.

### Special Course Handling

Certain course categories have hardcoded logic due to business rules not fully captured in ontology:
- English courses: Credits and prerequisites managed separately
- National Defense courses: Special handling for credit/prerequisite logic
- Physical Education: Non-GPA 1-credit courses

These are defined in `backend/app/services/recommendation/constants.py` as:
- `ENGLISH_COURSES`, `ENGLISH_COURSE_CREDITS`, `ENGLISH_COURSE_PREREQUISITES`
- `NATIONAL_DEFENSE_COURSES`
- `NON_GPA_ONE_CREDIT_COURSES`
- `EQUIVALENT_COURSES` (course substitution map)

### Testing Strategy

The test suite (`backend/tests/`) includes:
- **Unit tests:** Individual service methods (recommendation engine, risk analyzer, data service)
- **Schema tests:** Pydantic model validation
- **Validation tests:** Each of the 11 StandardValidator rules tested independently
- **API integration tests:** Full request/response cycles
- **UI integration tests:** Frontend rendering and interaction
- **Security tests:** Authentication, authorization, input validation
- **Deep business rules tests:** Complex prerequisite chains, quota calculations

Test fixtures in `conftest.py` provide:
- Mock `StudentDataService` (avoids file I/O in tests)
- Sample `StudentProfile` instances
- Minimal `RecommendationEngine` (bypasses RDF loading for fast unit tests)

### Development vs. Production Modes

Controlled by `APP_ENV` environment variable:
- **Development** (`APP_ENV=development`, default):
  - Debug mode enabled
  - `/components/*` and `/api/debug/*` routes accessible
  - SESSION_COOKIE_SECURE=False
  - Uses default SECRET_KEY

- **Production** (`APP_ENV=production`):
  - Debug mode disabled
  - `/components/*` and `/api/debug/*` return 404
  - SESSION_COOKIE_SECURE=True
  - Requires SECRET_KEY environment variable (will fail to start without it)

## Current Development State

**Completed:**
- RDF ontology v23 with course catalog, prerequisites, offerings
- Beam Search recommendation engine
- StandardValidator v3 with 11 rules and evidence tracking
- OntologyEvidenceService for provenance
- Pydantic schemas for Agent architecture
- Flask routes for student/advisor roles
- Frontend with Tailwind CSS, DaisyUI, Alpine.js, HTMX
- Comprehensive pytest suite
- Benchmark scripts with markdown reporting

**In Progress (see docs/LO_TRINH_MVP.md, docs/DAC_TA_TRIEN_KHAI_MVP.md):**
- Agent Orchestrator (skeleton exists, not yet wired)
- Capability contracts and integration
- Ranking and diversity logic (design complete, implementation pending)
- Grounded explanation generator (basic version exists, needs evidence integration)
- Feedback and re-planning loop
- Learning-to-Rank for preference optimization

**Not Yet Started:**
- PostgreSQL/SQLAlchemy migration (currently using JSON/CSV)
- LangGraph integration for agent orchestration
- Extracted SPARQL queries in `knowledge/queries/`
- Versioned rules in `knowledge/rules/`

The system currently works as a traditional recommendation engine with validation; the AI Agent architecture is being built to add orchestration, evidence tracking, and human-in-the-loop capabilities on top of the existing foundation.

## Key Documentation

- `README.md`: Installation, running, testing
- `docs/THIET_KE_AI_AGENT.md`: AI Agent architecture design (Vietnamese)
- `docs/DAC_TA_TRIEN_KHAI_MVP.md`: MVP implementation specification with capability contracts (Vietnamese)
- `docs/LO_TRINH_MVP.md`: Development roadmap and completed milestones (Vietnamese)
- `docs/BA_AI_AGENT.md`: Business analysis for AI Agent (Vietnamese)
- `docs/CONG_NGHE_VA_TOOLS.md`: Technology stack details (Vietnamese)
- `docs/CD.md`: CI/CD and Docker deployment guide (Vietnamese)
- `backend/app/schemas/README.md`: Schema documentation
- `backend/app/validation/README.md`: Validator contracts and limitations
- `HDSD_HeThong_CoVanHocTap.md`: User guide (Vietnamese)

## Notes for AI Assistants

When working with this codebase:
1. **Never generate academic rules**: Always query the ontology or refer to existing validation rules
2. **Trace evidence**: Every recommendation or validation decision must cite ontology triples, SPARQL results, or rule engine output
3. **Respect validation architecture**: Only `status="valid"` plans can be ranked or displayed; never bypass StandardValidator
4. **Preserve version tracking**: Maintain `knowledge_versions`, `validator_version`, and provenance metadata
5. **Run from project root**: Commands like `python run_app.py`, `python -m pytest`, `npm run build:ui` expect to be run from the repository root
6. **Test changes**: Run `python -m pytest` before committing; the suite is fast and comprehensive
7. **Check Vietnamese encoding**: UTF-8 handling is critical for proper display of course names and student data
