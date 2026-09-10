"""Build one versioned M4 context from the current deterministic data sources."""
from hashlib import sha256
import json
from pathlib import Path
import unicodedata

from backend.app.models.student import StudentProfile
from backend.app.schemas import KnowledgeSnapshot, PlanningRequest, RankingContext, StudentSnapshot
from backend.app.services.plan_risk_service import load_config
from backend.app.services.progress_risk_analyzer import ProgressRiskAnalyzer


CONTEXT_VERSION = "ranking-context-v1"


def _key(value):
    text = str(value or "").replace("Đ", "D").replace("đ", "d")
    text = unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode().lower()
    return "".join(ch for ch in text if ch.isalnum())


def _source_ref(path: Path) -> str:
    return f"{path.resolve().as_uri()}#sha256={sha256(path.read_bytes()).hexdigest()}"


def build_ranking_context(profile: StudentProfile, student: StudentSnapshot,
                          knowledge: KnowledgeSnapshot, request: PlanningRequest,
                          engine) -> RankingContext:
    config, config_hash = load_config()
    proxy = config["academic_status_proxy"]
    progress = ProgressRiskAnalyzer(engine).assess_student(profile)
    progress_status = progress.get("progress_status")
    academic_status = proxy["mapping"].get(progress_status)
    if academic_status is None:
        raise ValueError("ACADEMIC_STATUS_PROXY_UNAVAILABLE")

    reference = config["reference_credits"]
    reference_credits = float(reference["value"])
    if not engine.min_credits <= reference_credits <= engine.max_credits:
        raise ValueError("REFERENCE_CREDITS_OUTSIDE_POLICY")

    student_major = _key(profile.major)
    student_spec = _key(profile.specialization)
    catalog_credits = {code: float(info.get("credit", 0)) for code, info in engine.course_data.items()}
    required = set()
    dependencies = {}
    for code, info in engine.course_data.items():
        majors = {_key(value) for value in info.get("majors", ())}
        specs = {_key(value) for value in info.get("specializations", ())}
        major_required = bool(info.get("is_required_major")) and (not majors or student_major in majors)
        spec_required = bool(info.get("is_required_specialization")) and bool(student_spec) and student_spec in specs
        if major_required or spec_required:
            required.add(code)
        dependencies[code] = tuple(sorted(set(info.get("prereqs", ())) | set(info.get("corequisites", ()))))

    analyzer_path = Path(__file__).with_name("progress_risk_analyzer.py")
    config_path = Path(__file__).resolve().parents[3] / "knowledge/rules/ranking_pdf3_v1.json"
    source_refs = (
        knowledge.ontology_ref + "#" + knowledge.versions.ontology_version,
        "student:" + student.student_version,
        _source_ref(analyzer_path),
        _source_ref(config_path),
        "config:" + config_hash,
    )
    payload = {
        "version": CONTEXT_VERSION,
        "request_id": request.request_id,
        "knowledge_versions": knowledge.versions.model_dump(mode="json"),
        "credit_min": engine.min_credits,
        "credit_max": engine.max_credits,
        "reference_credits": reference_credits,
        "academic_status": academic_status,
        "progress_status": progress_status,
        "progress_risk_level": progress.get("risk_level"),
        "required_codes": sorted(required),
        "catalog_credits": dict(sorted(catalog_credits.items())),
        "dependency_map": dict(sorted(dependencies.items())),
        "source_refs": source_refs,
    }
    content_hash = "sha256:" + sha256(json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False,
    ).encode()).hexdigest()
    return RankingContext(
        context_id="ranking-context-" + content_hash.removeprefix("sha256:")[:16],
        content_hash=content_hash, context_version=CONTEXT_VERSION,
        knowledge_versions=knowledge.versions,
        credit_min=engine.min_credits, credit_max=engine.max_credits,
        reference_credits=reference_credits,
        reference_credits_source=reference["source"],
        academic_status=academic_status,
        academic_status_source=f"{proxy['version']}:{proxy['source']}:official={proxy['official_academic_warning']}",
        academic_status_is_official=bool(proxy["official_academic_warning"]),
        progress_status=progress_status, progress_risk_level=progress.get("risk_level"),
        required_codes=frozenset(required), catalog_credits=catalog_credits,
        dependency_map=dependencies, source_refs=source_refs,
    )
