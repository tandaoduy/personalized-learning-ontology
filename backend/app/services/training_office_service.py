"""Versioned, auditable ontology administration for the Training Office role."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from tempfile import NamedTemporaryFile

from rdflib import Graph, Literal, Namespace, RDF, URIRef, OWL

from backend.app.services.source_lock import exclusive_source_lock

BASE = Namespace("http://www.semanticweb.org/henrydao/ontologies/2025/7/TrainingProgramOntology#")


class TrainingOfficeService:
    def __init__(self, ontology_path: str | Path, data_dir: str | Path, artifact_dir: str | Path):
        self.ontology_path = Path(ontology_path).resolve()
        self.data_dir = Path(data_dir).resolve()
        self.artifact_dir = Path(artifact_dir).resolve() / "ontology_versions"
        self.assignment_path = self.data_dir / "advisor_class_assignments.json"
        self.audit_path = self.data_dir / "training_office_audit.json"
        self.course_catalog_path = self.data_dir / "course_catalog.json"
        self._graph_cache = None
        self._course_cache = None

    def _json(self, path: Path, default):
        if not path.exists(): return default
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_json(self, path: Path, value) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

    def _hash(self) -> str:
        return "sha256:" + sha256(self.ontology_path.read_bytes()).hexdigest()

    def _graph(self) -> Graph:
        # The ontology is ~35 MB; parsing it for every click made course lookup unusable.
        # It is invalidated only after this service publishes an ontology update.
        if self._graph_cache is None:
            self._graph_cache = Graph().parse(self.ontology_path, format="xml")
        return self._graph_cache

    def _course(self, graph: Graph, code: str) -> URIRef:
        code = str(code or "").strip().upper()
        matches = list(graph.subjects(BASE.courseCode, Literal(code)))
        if len(matches) != 1 or not isinstance(matches[0], URIRef):
            raise ValueError(f"COURSE_NOT_FOUND_OR_AMBIGUOUS:{code}")
        return matches[0]

    def _program(self, graph: Graph, program_id: str) -> URIRef:
        """Resolve both legacy `TrainingProgram_<id>` and ontology-native IDs."""
        key = str(program_id or "").strip()
        for node in (BASE[key], BASE["TrainingProgram_" + key]):
            if (node, RDF.type, BASE.TrainingProgram) in graph:
                return node
        matches = [node for node in graph.subjects(BASE.programCode, Literal(key))
                   if (node, RDF.type, BASE.TrainingProgram) in graph]
        if len(matches) == 1:
            return matches[0]
        raise ValueError("PROGRAM_NOT_FOUND")

    def _publish(self, graph: Graph, actor: str, action: str, payload: dict) -> dict:
        before = self._hash()
        # Round-trip validation occurs before replacing the active source.
        data = graph.serialize(format="xml", encoding="utf-8")
        Graph().parse(data=data, format="xml")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        backup = self.artifact_dir / f"{stamp}_{before.removeprefix('sha256:')}.rdf"
        with exclusive_source_lock(self.ontology_path):
            backup.write_bytes(self.ontology_path.read_bytes())
            with NamedTemporaryFile(dir=self.ontology_path.parent, delete=False) as handle:
                handle.write(data); temp = Path(handle.name)
            os.replace(temp, self.ontology_path)
        after = self._hash()
        self._graph_cache = graph
        self._course_cache = None
        record = {"at": datetime.now(timezone.utc).isoformat(), "actor": actor, "action": action,
                  "before_hash": before, "after_hash": after, "backup": str(backup), "payload": payload}
        audit = self._json(self.audit_path, [])
        audit.append(record); self._write_json(self.audit_path, audit)
        return record

    def list_relations(self) -> list[dict]:
        graph = self._graph(); rows = []
        for course in graph.subjects(BASE.courseCode, None):
            code = str(graph.value(course, BASE.courseCode) or "").strip().upper()
            for predicate, kind in ((BASE.hasPrerequisiteCourse, "prerequisite"), (BASE.corequisiteWith, "corequisite")):
                for target in graph.objects(course, predicate):
                    target_code = str(graph.value(target, BASE.courseCode) or "").strip().upper()
                    if code and target_code: rows.append({"type": kind, "course_code": code, "related_course_code": target_code})
        return sorted(rows, key=lambda item: (item["type"], item["course_code"], item["related_course_code"]))

    def list_courses(self) -> list[dict]:
        if self._course_cache is not None:
            return self._course_cache
        # This compact catalog avoids parsing the 35 MB RDF/XML document during a search.
        # It is refreshed whenever a course is saved below.
        if self.course_catalog_path.exists():
            self._course_cache = self._json(self.course_catalog_path, [])
            if self._course_cache:
                return self._course_cache
        graph = self._graph()
        rows = []
        for course in graph.subjects(BASE.courseCode, None):
            code = str(graph.value(course, BASE.courseCode) or "").strip().upper()
            if code:
                rows.append({"code": code, "name": str(graph.value(course, BASE.courseName) or "").strip(),
                             "credits": float(graph.value(course, BASE.credit) or 0)})
        self._course_cache = sorted(rows, key=lambda item: item["code"])
        self._write_json(self.course_catalog_path, self._course_cache)
        return self._course_cache

    def course_detail(self, course_code: str) -> dict:
        code = str(course_code or "").strip().upper()
        # Selecting a result must be instant; the prebuilt catalog contains the
        # relationship view needed by the editor, so avoid RDF parsing here.
        if self._graph_cache is None and self.course_catalog_path.exists():
            for row in self._json(self.course_catalog_path, []):
                if row.get("code") == code:
                    return dict(row)
        graph = self._graph(); course = self._course(graph, course_code)
        def code_of(node): return str(graph.value(node, BASE.courseCode) or "").strip().upper()
        prerequisites = sorted({code_of(node) for node in graph.objects(course, BASE.hasPrerequisiteCourse) if code_of(node)})
        corequisites = sorted({code_of(node) for node in graph.objects(course, BASE.corequisiteWith) if code_of(node)})
        required_by = sorted({code_of(node) for node in graph.subjects(BASE.hasPrerequisiteCourse, course) if code_of(node)})
        # All transitive prerequisite edges, used by the UI to display the dependency chain.
        chain, visited, queue = [], {str(course)}, [course]
        while queue:
            source = queue.pop(0); source_code = code_of(source)
            for target in graph.objects(source, BASE.hasPrerequisiteCourse):
                target_code = code_of(target)
                if not target_code: continue
                chain.append({"from": source_code, "to": target_code})
                if str(target) not in visited:
                    visited.add(str(target)); queue.append(target)
        types = {str(node).split("#")[-1] for node in graph.objects(course, RDF.type)}
        course_type = next((kind for kind in self.course_form_options()["course_types"] if kind in types), "Course")
        curriculum = []
        for predicate, scope in ((BASE.isRequiredForMajor, "required_major"), (BASE.isElectiveForMajor, "elective_major"),
                                 (BASE.isRequiredForSpecialization, "required_specialization"), (BASE.isElectiveForSpecialization, "elective_specialization")):
            curriculum.extend({"scope": scope, "target": str(node).split("#")[-1]} for node in graph.objects(course, predicate))
        semester_node = graph.value(course, BASE.recommendedInSemester)
        semester_text = str(semester_node).split("#")[-1] if semester_node else ""
        return {"code": code_of(course), "name": str(graph.value(course, BASE.courseName) or "").strip(),
                "credits": float(graph.value(course, BASE.credit) or 0), "prerequisites": prerequisites,
                "corequisites": corequisites, "required_by": required_by, "prerequisite_chain": chain,
                "course_type": course_type, "recommended_semester": semester_text.removeprefix("Semester") or None,
                "open_semester_type": int(graph.value(course, BASE.openSemesterType) or 0) or None,
                "curriculum": curriculum}

    def course_form_options(self) -> dict:
        """Ontology-backed choices required to create a complete Course individual."""
        graph = self._graph()
        def codes(kind):
            return sorted(str(node).split("#")[-1] for node in graph.subjects(RDF.type, kind))
        return {
            "course_types": ["CoreCourse", "ElectiveCourse", "FoundationCourse", "GeneralEducationCourse", "GraduationCourse", "PhysicalEducationCourse"],
            "majors": codes(BASE.Major), "specializations": codes(BASE.Specialization),
            "semesters": [int(str(node).split("#")[-1].removeprefix("Semester")) for node in graph.subjects(RDF.type, BASE.Semester)],
            "open_semester_types": [1, 2, 12],
        }

    def create_course(self, actor: str, course_code: str, name: str, credits) -> dict:
        """Create the shared course catalog entry; CTĐT owns its semester placement."""
        course_code = str(course_code or "").strip().upper()
        name = str(name or "").strip()
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{1,63}", course_code):
            raise ValueError("INVALID_COURSE_CODE")
        try:
            credits = float(credits)
        except (TypeError, ValueError):
            raise ValueError("INVALID_CREDITS")
        if not name or credits < 0 or credits > 30:
            raise ValueError("INVALID_COURSE_DATA")

        graph = self._graph()
        if list(graph.subjects(BASE.courseCode, Literal(course_code))):
            raise ValueError("COURSE_ALREADY_EXISTS")

        course = BASE[course_code]
        graph.add((course, RDF.type, BASE.Course))
        graph.add((course, RDF.type, OWL.NamedIndividual))
        graph.add((course, BASE.courseCode, Literal(course_code)))
        graph.add((course, BASE.courseName, Literal(name)))
        graph.add((course, BASE.credit, Literal(credits)))
        self._publish(graph, actor, "course_created", {
            "course_code": course_code, "name": name, "credits": credits,
        })

        detail = self.course_detail(course_code)
        catalog = [row for row in self._json(self.course_catalog_path, []) if row.get("code") != course_code]
        catalog.append(detail)
        self._course_cache = sorted(catalog, key=lambda item: item["code"])
        self._write_json(self.course_catalog_path, self._course_cache)
        return detail

    def update_course(self, actor: str, course_code: str, name: str, credits, prerequisites, corequisites) -> dict:
        graph = self._graph(); course = self._course(graph, course_code)
        name = str(name or "").strip()
        try: credits = float(credits)
        except (TypeError, ValueError): raise ValueError("INVALID_CREDITS")
        if not name or credits < 0 or credits > 30: raise ValueError("INVALID_COURSE_DATA")
        def resolve_many(values):
            nodes = []
            for value in values or []:
                node = self._course(graph, value)
                if node == course: raise ValueError("SELF_RELATION_NOT_ALLOWED")
                if node not in nodes: nodes.append(node)
            return nodes
        prereq_nodes, coreq_nodes = resolve_many(prerequisites), resolve_many(corequisites)
        # Avoid adding any prerequisite edge that closes a cycle.
        def reaches(start, wanted):
            seen, queue = set(), [start]
            while queue:
                node = queue.pop()
                if node == wanted: return True
                if node in seen: continue
                seen.add(node); queue.extend(graph.objects(node, BASE.hasPrerequisiteCourse))
            return False
        if any(reaches(node, course) for node in prereq_nodes): raise ValueError("PREREQUISITE_CYCLE_NOT_ALLOWED")
        graph.set((course, BASE.courseName, Literal(name)))
        graph.set((course, BASE.credit, Literal(credits)))
        graph.remove((course, BASE.hasPrerequisiteCourse, None))
        for node in prereq_nodes: graph.add((course, BASE.hasPrerequisiteCourse, node))
        # Keep corequisite links symmetric while replacing the selected course's links.
        old_coreqs = list(graph.objects(course, BASE.corequisiteWith))
        graph.remove((course, BASE.corequisiteWith, None))
        for node in old_coreqs: graph.remove((node, BASE.corequisiteWith, course))
        for node in coreq_nodes:
            graph.add((course, BASE.corequisiteWith, node)); graph.add((node, BASE.corequisiteWith, course))
        self._publish(graph, actor, "course_updated", {"course_code": course_code.upper(), "name": name,
                      "credits": credits, "prerequisites": [code_of for code_of in (str(graph.value(n, BASE.courseCode)) for n in prereq_nodes)],
                      "corequisites": [code_of for code_of in (str(graph.value(n, BASE.courseCode)) for n in coreq_nodes)]})
        # Refresh the one changed entry in the lightweight search index.
        detail = self.course_detail(course_code)
        catalog = self._json(self.course_catalog_path, [])
        replacement = detail
        catalog = [replacement if row.get("code") == course_code.upper() else row for row in catalog]
        if not any(row.get("code") == course_code.upper() for row in catalog): catalog.append(replacement)
        self._course_cache = sorted(catalog, key=lambda item: item["code"])
        self._write_json(self.course_catalog_path, self._course_cache)
        return detail

    def set_relation(self, actor: str, relation: str, course_code: str, related_course_code: str, enabled: bool) -> dict:
        if relation not in {"prerequisite", "corequisite"}: raise ValueError("INVALID_RELATION")
        graph = self._graph(); course, related = self._course(graph, course_code), self._course(graph, related_course_code)
        if course == related: raise ValueError("SELF_RELATION_NOT_ALLOWED")
        predicate = BASE.hasPrerequisiteCourse if relation == "prerequisite" else BASE.corequisiteWith
        if enabled: graph.add((course, predicate, related))
        else: graph.remove((course, predicate, related))
        # Corequisites are symmetric by contract.
        if relation == "corequisite":
            if enabled: graph.add((related, predicate, course))
            else: graph.remove((related, predicate, course))
        return self._publish(graph, actor, f"{relation}_{'added' if enabled else 'removed'}", {
            "course_code": course_code.upper(), "related_course_code": related_course_code.upper()})

    def list_programs(self) -> list[dict]:
        graph = self._graph(); rows = []
        for subject in graph.subjects(RDF.type, BASE.TrainingProgram):
            rows.append({"program_id": str(graph.value(subject, BASE.programCode) or subject).split("#")[-1],
                         "name": str(graph.value(subject, BASE.programName) or ""),
                         "archived": str(graph.value(subject, BASE.isArchived) or "false").lower() == "true"})
        return sorted(rows, key=lambda item: item["program_id"])

    def create_program(self, actor: str, program_id: str, name: str) -> dict:
        program_id = str(program_id or "").strip().upper(); name = str(name or "").strip()
        if not program_id or not name or not program_id.replace("_", "").replace("-", "").isalnum(): raise ValueError("INVALID_PROGRAM")
        graph = self._graph(); node = BASE["TrainingProgram_" + program_id]
        if (node, RDF.type, BASE.TrainingProgram) in graph: raise ValueError("PROGRAM_ALREADY_EXISTS")
        graph.add((node, RDF.type, BASE.TrainingProgram)); graph.add((node, BASE.programCode, Literal(program_id)))
        graph.add((node, BASE.programName, Literal(name))); graph.add((node, BASE.isArchived, Literal(False)))
        return self._publish(graph, actor, "program_created", {"program_id": program_id, "name": name})

    def update_program(self, actor: str, program_id: str, name: str) -> dict:
        program_id, name = str(program_id or "").strip(), str(name or "").strip()
        if not name: raise ValueError("INVALID_PROGRAM_NAME")
        graph = self._graph(); node = self._program(graph, program_id)
        graph.set((node, BASE.programName, Literal(name)))
        return self._publish(graph, actor, "program_updated", {"program_id": program_id, "name": name})

    def archive_program(self, actor: str, program_id: str) -> dict:
        graph = self._graph(); node = self._program(graph, str(program_id).strip())
        graph.set((node, BASE.isArchived, Literal(True)))
        return self._publish(graph, actor, "program_archived", {"program_id": str(program_id).strip().upper()})

    def assignments(self) -> list[dict]: return self._json(self.assignment_path, [])

    def assign_advisor(self, actor: str, advisor_username: str, academic_class: str) -> dict:
        advisor_username, academic_class = str(advisor_username or "").strip(), str(academic_class or "").strip()
        if not advisor_username or not academic_class: raise ValueError("ADVISOR_AND_CLASS_REQUIRED")
        # A class has one active advisor; assigning again replaces the previous advisor.
        rows = [row for row in self.assignments() if row["academic_class"] != academic_class]
        record = {"advisor_username": advisor_username, "academic_class": academic_class,
                  "assigned_by": actor, "assigned_at": datetime.now(timezone.utc).isoformat()}
        rows.append(record); self._write_json(self.assignment_path, rows)
        audit = self._json(self.audit_path, []); audit.append({"at": record["assigned_at"], "actor": actor, "action": "advisor_class_assigned", "payload": record})
        self._write_json(self.audit_path, audit); return record

    def revoke_advisor(self, actor: str, advisor_username: str, academic_class: str) -> None:
        rows = self.assignments(); kept = [row for row in rows if not (row["advisor_username"] == advisor_username and row["academic_class"] == academic_class)]
        if len(kept) == len(rows): raise ValueError("ASSIGNMENT_NOT_FOUND")
        self._write_json(self.assignment_path, kept)
