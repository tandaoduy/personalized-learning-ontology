"""Traceable evidence; structural checks do not certify source authenticity."""
from typing import Literal
from pydantic import AwareDatetime, model_validator
from .common import CourseCode, Identifier, KnowledgeVersion, SchemaModel

class RDFTriple(SchemaModel):
    subject: Identifier
    predicate: Identifier
    object: str
    object_kind: Literal["iri", "literal", "blank_node"] = "iri"
    datatype: Identifier | None = None
    language: Identifier | None = None

    @model_validator(mode="after")
    def valid_literal_metadata(self):
        if (self.datatype or self.language) and self.object_kind != "literal":
            raise ValueError("Only literals may carry datatype/language")
        if self.datatype and self.language:
            raise ValueError("Use either datatype or language")
        return self

class QueryBinding(SchemaModel):
    variable: Identifier
    value: str

class EvidenceRecord(SchemaModel):
    evidence_id: Identifier
    course_code: CourseCode
    decision: Literal["eligible", "ineligible", "selected", "not_selected", "constraint_check"]
    result: Literal["pass", "fail", "warning"]
    source_type: Literal["ontology", "sparql", "rule"]
    source_ref: Identifier
    knowledge_versions: KnowledgeVersion
    captured_at: AwareDatetime
    triples: tuple[RDFTriple, ...] = ()
    query_id: Identifier | None = None
    query_text: Identifier | None = None
    query_rows: tuple[tuple[QueryBinding, ...], ...] = ()
    query_boolean: bool | None = None
    query_executed: bool = False
    supporting_evidence_ids: tuple[Identifier, ...] = ()
    rule_id: Identifier | None = None
    rule_inputs: tuple[QueryBinding, ...] = ()
    rule_result: Identifier | None = None

    @model_validator(mode="after")
    def require_source_payload(self):
        if self.source_type == "ontology" and not self.triples:
            raise ValueError("Ontology evidence requires triples")
        if self.source_type == "sparql" and not (self.query_id and self.query_text and self.query_executed):
            raise ValueError("SPARQL evidence requires query identity, text and execution confirmation")
        if self.source_type == "rule" and not (self.rule_id and self.rule_inputs and self.rule_result):
            raise ValueError("Rule evidence requires rule identity, inputs and result")
        return self


class OntologyFactEvidence(SchemaModel):
    """Query result only: absence of relations is not an eligibility verdict."""
    evidence_id: Identifier
    course_code: CourseCode
    source_ref: Identifier
    ontology_version: Identifier
    query_id: Identifier
    query_version: Identifier
    query_text: Identifier
    subject_uri: Identifier
    triples: tuple[RDFTriple, ...] = ()
    exists: bool | None = None
    catalog_credit: float | None = None
    prerequisite_codes: tuple[CourseCode, ...] = ()
    corequisite_codes: tuple[CourseCode, ...] = ()
    open_semester_type: int | None = None
    recommended_semester: int | None = None
    elective_category: Identifier | None = None
    is_required_major: bool | None = None
    is_elective_major: bool | None = None
    specializations: tuple[Identifier, ...] = ()
    majors: tuple[Identifier, ...] = ()
    captured_at: AwareDatetime
