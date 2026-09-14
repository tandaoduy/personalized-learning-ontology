"""Regression test cho lệch tín chỉ các môn GDTC (85105, 85108) và NON_GPA.

Nguyên nhân lịch sử:
- Ontology gốc ghi ``credit=0`` cho các môn PhysicalEducationCourse vì chúng không
  tính vào tích lũy GPA, nhưng generator override thành ``1`` (tải đăng ký).
- Validator dùng raw RDF → ``catalog_credit=0`` → sai lệch với generator
  → rule ``catalog_credit_match`` fail trên các môn này.

Quy ước mới:
- ``PHYSICAL_EDUCATION_REGISTRATION_CREDIT`` = 1 (single source of truth).
- Cả ``OntologyMixin._load_ontology`` (generator) và
  ``OntologyEvidenceService._catalog_fact`` (validator) đều phải trả về
  cùng giá trị ``1`` cho 85105 và 85108.

Test này dùng ontology thật (``ontology_v23.rdf``) để chặn tái phát khi
người khác chỉnh sửa override ở một phía.
"""
from pathlib import Path

import pytest

from backend.app.config import Config
from backend.app.services.ontology_evidence_service import OntologyEvidenceService
from backend.app.services.recommendation_engine import RecommendationEngine


REGRESSION_CODES = ("85105", "85108")
PHYSICAL_EDUCATION_REGISTRATION_CREDIT = 1


@pytest.fixture(scope="module")
def ontology_path():
    return Path(Config.ONTOLOGY_PATH).resolve()


@pytest.fixture(scope="module")
def evidence_service(ontology_path):
    return OntologyEvidenceService(ontology_path)


@pytest.fixture(scope="module")
def recommendation_engine(ontology_path):
    return RecommendationEngine(
        ontology_path,
        beam_width=Config.BEAM_WIDTH,
        min_credits=Config.REGISTER_MIN_CREDITS,
        max_credits=Config.REGISTER_MAX_CREDITS,
        elective_quotas=dict(Config.ELECTIVE_QUOTAS),
    )


@pytest.mark.parametrize("course_code", REGRESSION_CODES)
def test_generator_reports_registration_credit_for_physical_education(course_code, recommendation_engine):
    """Generator: PhysicalEducationCourse → credit = PHYSICAL_EDUCATION_REGISTRATION_CREDIT.

    Regression: ontology.py override đã chuyển sang dùng hằng số trong constants.py
    và vẫn phải trả về 1 cho 85105 và 85108 (không phải 0 từ raw RDF).
    """
    info = recommendation_engine.course_data.get(course_code)
    assert info is not None, f"{course_code} not present in catalog"
    assert info.get("is_physical_education_course") is True, (
        f"{course_code} should be tagged PhysicalEducationCourse in ontology"
    )
    assert int(info.get("credit", -1)) == PHYSICAL_EDUCATION_REGISTRATION_CREDIT, (
        f"Generator credit for {course_code} must equal "
        f"{PHYSICAL_EDUCATION_REGISTRATION_CREDIT} (registration credit), "
        f"got {info.get('credit')!r}"
    )


@pytest.mark.parametrize("course_code", REGRESSION_CODES)
def test_evidence_service_reports_matching_catalog_credit(course_code, evidence_service):
    """Validator: cùng giá trị catalog_credit với generator.

    Regression: ``_catalog_fact`` đã được cập nhật để apply override
    PHYSICAL_EDUCATION_REGISTRATION_CREDIT cho mọi PhysicalEducationCourse.
    Trước đây trả 0 (raw RDF), gây sai lệch với generator.
    """
    fact = evidence_service.get_course_credit_evidence(
        course_code, evidence_service.ontology_version
    )
    assert fact.catalog_credit == float(PHYSICAL_EDUCATION_REGISTRATION_CREDIT), (
        f"Evidence catalog_credit for {course_code} must be "
        f"{PHYSICAL_EDUCATION_REGISTRATION_CREDIT}, got {fact.catalog_credit!r}"
    )
    # Triples vẫn phải trỏ về RDF gốc để evidence vẫn truy vết được.
    assert any(
        triple.predicate.endswith("credit") or triple.predicate.endswith("hasCredit")
        for triple in fact.triples
    ), "Expected raw credit triple to be preserved for traceability"


def test_generator_and_evidence_service_agree_on_pe_credits(recommendation_engine, evidence_service):
    """Generator và validator phải đồng bộ cho mọi mã GDTC hiện có.

    Đây là invariant bắt buộc: nếu hai phía lệch nhau thì ``catalog_credit_match``
    sẽ luôn fail với các môn PE và phá vỡ E2E-03, E2E-05.
    """
    pe_codes = [
        code for code, info in recommendation_engine.course_data.items()
        if info.get("is_physical_education_course")
    ]
    assert pe_codes, "Không tìm thấy PhysicalEducationCourse nào trong catalog"
    mismatches = []
    for code in pe_codes:
        gen_credit = int(recommendation_engine.course_data[code].get("credit", -1))
        fact = evidence_service.get_course_credit_evidence(
            code, evidence_service.ontology_version
        )
        ev_credit = fact.catalog_credit
        if gen_credit != ev_credit:
            mismatches.append((code, gen_credit, ev_credit))
    assert not mismatches, (
        "Generator và validator không đồng bộ credit cho PhysicalEducationCourse: "
        + ", ".join(f"{c}: gen={g}, ev={e}" for c, g, e in mismatches)
    )
