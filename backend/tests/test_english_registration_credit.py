"""Regression guard for the non-GPA English registration-credit policy.

FLS310, FLS312 and FLS313 each carry four registration credits.  They do not
contribute to GPA, but their registration credit must be identical in the
generator and the evidence read by StandardValidator.
"""
from pathlib import Path

import pytest

from backend.app.config import Config
from backend.app.services.ontology_evidence_service import OntologyEvidenceService
from backend.app.services.recommendation.constants import ENGLISH_COURSE_CREDITS
from backend.app.services.recommendation_engine import RecommendationEngine


ENGLISH_REGISTRATION_COURSES = ("FLS310", "FLS312", "FLS313")


@pytest.fixture(scope="module")
def engine() -> RecommendationEngine:
    return RecommendationEngine(
        Path(Config.ONTOLOGY_PATH), beam_width=Config.BEAM_WIDTH,
        min_credits=Config.REGISTER_MIN_CREDITS, max_credits=Config.REGISTER_MAX_CREDITS,
        elective_quotas=dict(Config.ELECTIVE_QUOTAS),
    )


@pytest.fixture(scope="module")
def evidence() -> OntologyEvidenceService:
    return OntologyEvidenceService(Path(Config.ONTOLOGY_PATH))


@pytest.mark.parametrize("course_code", ENGLISH_REGISTRATION_COURSES)
def test_english_registration_credit_is_shared_by_generator_and_validator(course_code, engine, evidence):
    assert engine.course_data[course_code]["credit"] == ENGLISH_COURSE_CREDITS
    fact = evidence.get_course_credit_evidence(course_code, evidence.ontology_version)
    assert fact.catalog_credit == float(ENGLISH_COURSE_CREDITS)
