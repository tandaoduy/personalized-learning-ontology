"""Read-only prerequisite facts from a private, content-versioned RDF snapshot."""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from rdflib import Graph, URIRef
from backend.app.schemas.evidence import OntologyFactEvidence, RDFTriple

BASE = "http://www.semanticweb.org/henrydao/ontologies/2025/7/TrainingProgramOntology#"
CODE = URIRef(BASE + "courseCode")
PREREQ = URIRef(BASE + "hasPrerequisiteCourse")
QUERY_PATH = Path(__file__).resolve().parents[3] / "knowledge" / "queries" / "prerequisites.rq"

class EvidenceSourceError(ValueError):
    """Missing/ambiguous facts or snapshot mismatch; never an academic verdict."""

class OntologyEvidenceService:
    def __init__(self, ontology_path: str | Path):
        path = Path(ontology_path).resolve()
        content = path.read_bytes()
        self.ontology_version = "sha256:" + sha256(content).hexdigest()
        self.source_ref = path.as_uri()
        self._graph = Graph().parse(data=content, format="xml", publicID=self.source_ref)
        self.query_text = QUERY_PATH.read_text(encoding="utf-8")
        self.query_version = "sha256:" + sha256(self.query_text.encode()).hexdigest()
        self._codes = {}
        for subject, value in self._graph.subject_objects(CODE):
            self._codes.setdefault(str(value).strip().upper(), set()).add(subject)

    def get_prerequisite_evidence(self, course_code: str, expected_ontology_version: str) -> OntologyFactEvidence:
        if expected_ontology_version != self.ontology_version:
            raise EvidenceSourceError("Ontology snapshot version mismatch")
        code = course_code.strip().upper()
        subjects = self._codes.get(code, set())
        if len(subjects) != 1:
            raise EvidenceSourceError("Course code is unknown or ambiguous: " + code)
        subject = next(iter(subjects))
        if not isinstance(subject, URIRef):
            raise EvidenceSourceError("Course must have a stable IRI")
        relations, codes = [], []
        for row in self._graph.query(self.query_text, initBindings={"course": subject}):
            obj = row[0]
            if not isinstance(obj, URIRef):
                raise EvidenceSourceError("Prerequisite must have a stable IRI")
            values = list(self._graph.objects(obj, CODE))
            if len(values) != 1:
                raise EvidenceSourceError("Prerequisite has missing or ambiguous course code")
            target = str(values[0]).strip().upper()
            if self._codes.get(target) != {obj}:
                raise EvidenceSourceError("Ambiguous prerequisite course code")
            codes.append(target)
            relations.append(RDFTriple(subject=str(subject), predicate=str(PREREQ), object=str(obj)))
            # Include the exact code mapping used to compare with student history.
            relations.append(RDFTriple(subject=str(obj), predicate=str(CODE), object=str(values[0]),
                object_kind="literal", datatype=str(values[0].datatype) if values[0].datatype else None,
                language=values[0].language))
        identifier = sha256((self.ontology_version + self.query_version + str(subject)).encode()).hexdigest()
        return OntologyFactEvidence(evidence_id="ONTO_" + identifier, course_code=code,
            source_ref=self.source_ref, ontology_version=self.ontology_version,
            query_id="Q_PREREQ_01", query_version=self.query_version, query_text=self.query_text,
            subject_uri=str(subject), triples=tuple(relations), prerequisite_codes=tuple(codes),
            captured_at=datetime.now(timezone.utc))

    def _catalog_fact(self, code, expected_version, credit=False):
        from decimal import Decimal, InvalidOperation
        from rdflib import Literal
        if expected_version != self.ontology_version:
            raise EvidenceSourceError("Ontology snapshot version mismatch")
        code = code.strip().upper()
        query_id = "Q_CREDIT_01" if credit else "Q_COURSE_01"
        query_text = (QUERY_PATH.parent / ("course_credit.rq" if credit else "course_exists.rq")).read_text(encoding="utf-8")
        rows = list(self._graph.query(query_text, initBindings={"code": Literal(code)}))
        subjects = {row[0] for row in rows}
        if len(subjects) > 1:
            raise EvidenceSourceError("CATALOG_COURSE_AMBIGUOUS")
        triples, values = [], set()
        for row in rows:
            subject, predicate, value = row
            if not isinstance(subject, URIRef) or not isinstance(value, Literal):
                raise EvidenceSourceError("CATALOG_DATA_INVALID")
            triples.append(RDFTriple(subject=str(subject), predicate=str(predicate), object=str(value), object_kind="literal",
                datatype=str(value.datatype) if value.datatype else None, language=value.language))
            if credit:
                try:
                    number = Decimal(str(value))
                    if not number.is_finite() or number < 0: raise InvalidOperation()
                    values.add(number)
                except InvalidOperation:
                    raise EvidenceSourceError("CATALOG_CREDIT_AMBIGUOUS")
        if credit and len(values) != 1:
            raise EvidenceSourceError("CATALOG_CREDIT_AMBIGUOUS")
        triples = tuple(sorted(set(triples), key=lambda t: t.model_dump_json()))
        qversion = "sha256:" + sha256(query_text.encode()).hexdigest()
        identifier = sha256((self.ontology_version + qversion + code).encode()).hexdigest()
        return OntologyFactEvidence(evidence_id="ONTO_" + identifier, course_code=code, source_ref=self.source_ref,
            ontology_version=self.ontology_version, query_id=query_id, query_version=qversion, query_text=query_text,
            subject_uri=str(next(iter(subjects))) if subjects else "urn:unresolved-course:" + code,
            exists=bool(subjects), catalog_credit=float(next(iter(values))) if credit else None,
            triples=triples, captured_at=datetime.now(timezone.utc))

    def get_corequisite_evidence(self, course_code: str, expected_ontology_version: str) -> OntologyFactEvidence:
        if expected_ontology_version != self.ontology_version:
            raise EvidenceSourceError("Ontology snapshot version mismatch")
        code = course_code.strip().upper()
        subjects = self._codes.get(code, set())
        if len(subjects) != 1:
            raise EvidenceSourceError("Course code is unknown or ambiguous: " + code)
        subject = next(iter(subjects))
        if not isinstance(subject, URIRef):
            raise EvidenceSourceError("Course must have a stable IRI")
        query_path = QUERY_PATH.parent / "corequisites.rq"
        query_text = query_path.read_text(encoding="utf-8")
        query_version = "sha256:" + sha256(query_text.encode()).hexdigest()
        relations, codes = [], []
        coreq_prop = URIRef(BASE + "corequisiteWith")
        for row in self._graph.query(query_text, initBindings={"course": subject}):
            obj = row[0]
            if not isinstance(obj, URIRef):
                raise EvidenceSourceError("Corequisite must have a stable IRI")
            values = list(self._graph.objects(obj, CODE))
            if len(values) != 1:
                raise EvidenceSourceError("Corequisite has missing or ambiguous course code")
            target = str(values[0]).strip().upper()
            if self._codes.get(target) != {obj}:
                raise EvidenceSourceError("Ambiguous corequisite course code")
            codes.append(target)
            relations.append(RDFTriple(subject=str(subject), predicate=str(coreq_prop), object=str(obj)))
            relations.append(RDFTriple(subject=str(obj), predicate=str(CODE), object=str(values[0]),
                object_kind="literal", datatype=str(values[0].datatype) if values[0].datatype else None,
                language=values[0].language))
        identifier = sha256((self.ontology_version + query_version + str(subject)).encode()).hexdigest()
        return OntologyFactEvidence(evidence_id="ONTO_" + identifier, course_code=code,
            source_ref=self.source_ref, ontology_version=self.ontology_version,
            query_id="Q_COREQ_01", query_version=query_version, query_text=query_text,
            subject_uri=str(subject), triples=tuple(relations), corequisite_codes=tuple(codes),
            captured_at=datetime.now(timezone.utc))

    def get_semester_offering_evidence(self, course_code: str, expected_ontology_version: str) -> OntologyFactEvidence:
        from rdflib import Literal
        if expected_ontology_version != self.ontology_version:
            raise EvidenceSourceError("Ontology snapshot version mismatch")
        code = course_code.strip().upper()
        subjects = self._codes.get(code, set())
        if len(subjects) > 1:
            raise EvidenceSourceError("CATALOG_COURSE_AMBIGUOUS")
        query_path = QUERY_PATH.parent / "semester_offering.rq"
        query_text = query_path.read_text(encoding="utf-8")
        query_version = "sha256:" + sha256(query_text.encode()).hexdigest()
        rows = list(self._graph.query(query_text, initBindings={"code": Literal(code)}))
        triples = []
        open_types = set()
        open_sem_type = None
        rec_sem = None
        for row in rows:
            subject, predicate, value = row
            pred_str = str(predicate)
            if pred_str.endswith("openSemesterType") and not isinstance(value, Literal):
                raise EvidenceSourceError("SEMESTER_OFFERING_INVALID")
            if isinstance(value, Literal):
                triples.append(RDFTriple(subject=str(subject), predicate=pred_str, object=str(value), object_kind="literal",
                    datatype=str(value.datatype) if value.datatype else None, language=value.language))
                if pred_str.endswith("openSemesterType"):
                    try:
                        parsed = int(str(value).strip())
                        if parsed not in (1, 2, 3, 12):
                            raise ValueError()
                        open_types.add(3 if parsed == 12 else parsed)
                    except ValueError:
                        raise EvidenceSourceError("SEMESTER_OFFERING_INVALID")
            elif isinstance(value, URIRef):
                triples.append(RDFTriple(subject=str(subject), predicate=pred_str, object=str(value), object_kind="iri"))
                if pred_str.endswith("recommendedInSemester"):
                    sem_str = str(value).split("#")[-1]
                    if sem_str.startswith("Semester"):
                        try:
                            rec_sem = int(sem_str.replace("Semester", ""))
                        except ValueError:
                            pass
        if len(open_types) > 1:
            raise EvidenceSourceError("SEMESTER_OFFERING_AMBIGUOUS")
        open_sem_type = next(iter(open_types)) if open_types else None
        triples = tuple(sorted(set(triples), key=lambda t: t.model_dump_json()))
        identifier = sha256((self.ontology_version + query_version + code).encode()).hexdigest()
        return OntologyFactEvidence(evidence_id="ONTO_" + identifier, course_code=code, source_ref=self.source_ref,
            ontology_version=self.ontology_version, query_id="Q_SEMESTER_01", query_version=query_version,
            query_text=query_text, subject_uri=str(next(iter(subjects))) if subjects else "urn:unresolved-course:" + code,
            exists=bool(subjects), open_semester_type=open_sem_type, recommended_semester=rec_sem, triples=triples,
            captured_at=datetime.now(timezone.utc))

    def get_course_category_evidence(self, course_code: str, expected_ontology_version: str) -> OntologyFactEvidence:
        from rdflib import Literal
        if expected_ontology_version != self.ontology_version:
            raise EvidenceSourceError("Ontology snapshot version mismatch")
        code = course_code.strip().upper()
        subjects = self._codes.get(code, set())
        if len(subjects) > 1:
            raise EvidenceSourceError("CATALOG_COURSE_AMBIGUOUS")
        query_path = QUERY_PATH.parent / "course_category.rq"
        query_text = query_path.read_text(encoding="utf-8")
        query_version = "sha256:" + sha256(query_text.encode()).hexdigest()
        rows = list(self._graph.query(query_text, initBindings={"code": Literal(code)}))
        triples = []
        is_req_major = False
        is_elec_major = False
        is_gen_ed = False
        is_phys_ed = False
        is_found = False
        is_spec_elec = False
        specs, majors = [], []
        is_req_spec = False
        for row in rows:
            subject, predicate, value = row
            pred_str = str(predicate)
            if not isinstance(value, URIRef):
                raise EvidenceSourceError("COURSE_CATEGORY_INVALID")
            val_str = str(value)
            kind = "iri" if isinstance(value, URIRef) else "literal"
            triples.append(RDFTriple(subject=str(subject), predicate=pred_str, object=val_str, object_kind=kind))
            if pred_str.endswith("type"):
                if val_str.endswith("GeneralEducationCourse"): is_gen_ed = True
                elif val_str.endswith("PhysicalEducationCourse"): is_phys_ed = True
                elif val_str.endswith("FoundationCourse"): is_found = True
            elif pred_str.endswith("isRequiredForMajor"):
                is_req_major = True
                majors.append(val_str)
            elif pred_str.endswith("isElectiveForMajor"):
                is_elec_major = True
                majors.append(val_str)
            elif pred_str.endswith("isRequiredForSpecialization"):
                is_req_spec = True
                specs.append(val_str)
            elif pred_str.endswith("offeredInSpecialization"):
                specs.append(val_str)
            elif pred_str.endswith("isElectiveForSpecialization"):
                is_spec_elec = True
                specs.append(val_str)
        if (is_req_major or is_req_spec) and (is_elec_major or is_spec_elec):
            raise EvidenceSourceError("COURSE_CATEGORY_AMBIGUOUS")
        if not (is_req_major or is_req_spec or is_elec_major or is_spec_elec or is_phys_ed or is_gen_ed or is_found):
            raise EvidenceSourceError("COURSE_CATEGORY_MISSING")
        category = None
        if is_req_major or is_req_spec: pass
        elif is_phys_ed: category = "physical"
        elif is_gen_ed: category = "general"
        elif is_found: category = "foundation"
        elif is_spec_elec or is_elec_major: category = "specialization" if is_spec_elec else "general"

        triples = tuple(sorted(set(triples), key=lambda t: t.model_dump_json()))
        identifier = sha256((self.ontology_version + query_version + code).encode()).hexdigest()
        return OntologyFactEvidence(evidence_id="ONTO_" + identifier, course_code=code, source_ref=self.source_ref,
            ontology_version=self.ontology_version, query_id="Q_CATEGORY_01", query_version=query_version,
            query_text=query_text, subject_uri=str(next(iter(subjects))) if subjects else "urn:unresolved-course:" + code,
            exists=bool(subjects), elective_category=category, is_required_major=is_req_major, is_elective_major=is_elec_major,
            specializations=tuple(sorted(set(specs))), majors=tuple(sorted(set(majors))), triples=triples, captured_at=datetime.now(timezone.utc))


    def get_course_evidence(self, course_id, expected_version):
        return self._catalog_fact(course_id, expected_version)

    def get_course_credit_evidence(self, course_id, expected_version):
        return self._catalog_fact(course_id, expected_version, credit=True)
