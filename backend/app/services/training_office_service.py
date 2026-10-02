"""Versioned, auditable ontology administration for the Training Office role."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from rdflib import Graph, Literal, Namespace, RDF, URIRef

from backend.app.services.source_lock import exclusive_source_lock

BASE = Namespace("http://www.semanticweb.org/henrydao/ontologies/2025/7/TrainingProgramOntology#")


class TrainingOfficeService:
    def __init__(self, ontology_path: str | Path, data_dir: str | Path, artifact_dir: str | Path):
        self.ontology_path = Path(ontology_path).resolve()
        self.data_dir = Path(data_dir).resolve()
        self.artifact_dir = Path(artifact_dir).resolve() / "ontology_versions"
        self.assignment_path = self.data_dir / "advisor_class_assignments.json"
        self.audit_path = self.data_dir / "training_office_audit.json"

    def _json(self, path: Path, default):
        if not path.exists(): return default
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_json(self, path: Path, value) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

    def _hash(self) -> str:
        return "sha256:" + sha256(self.ontology_path.read_bytes()).hexdigest()

    def _graph(self) -> Graph:
        return Graph().parse(self.ontology_path, format="xml")

    def _course(self, graph: Graph, code: str) -> URIRef:
        code = str(code or "").strip().upper()
        matches = list(graph.subjects(BASE.courseCode, Literal(code)))
        if len(matches) != 1 or not isinstance(matches[0], URIRef):
            raise ValueError(f"COURSE_NOT_FOUND_OR_AMBIGUOUS:{code}")
        return matches[0]

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
        program_id, name = str(program_id or "").strip().upper(), str(name or "").strip()
        if not name: raise ValueError("INVALID_PROGRAM_NAME")
        graph = self._graph(); node = BASE["TrainingProgram_" + program_id]
        if (node, RDF.type, BASE.TrainingProgram) not in graph: raise ValueError("PROGRAM_NOT_FOUND")
        graph.set((node, BASE.programName, Literal(name)))
        return self._publish(graph, actor, "program_updated", {"program_id": program_id, "name": name})

    def archive_program(self, actor: str, program_id: str) -> dict:
        graph = self._graph(); node = BASE["TrainingProgram_" + str(program_id).strip().upper()]
        if (node, RDF.type, BASE.TrainingProgram) not in graph: raise ValueError("PROGRAM_NOT_FOUND")
        graph.set((node, BASE.isArchived, Literal(True)))
        return self._publish(graph, actor, "program_archived", {"program_id": str(program_id).strip().upper()})

    def assignments(self) -> list[dict]: return self._json(self.assignment_path, [])

    def assign_advisor(self, actor: str, advisor_username: str, academic_class: str) -> dict:
        advisor_username, academic_class = str(advisor_username or "").strip(), str(academic_class or "").strip()
        if not advisor_username or not academic_class: raise ValueError("ADVISOR_AND_CLASS_REQUIRED")
        rows = [row for row in self.assignments() if not (row["advisor_username"] == advisor_username and row["academic_class"] == academic_class)]
        record = {"advisor_username": advisor_username, "academic_class": academic_class,
                  "assigned_by": actor, "assigned_at": datetime.now(timezone.utc).isoformat()}
        rows.append(record); self._write_json(self.assignment_path, rows)
        audit = self._json(self.audit_path, []); audit.append({"at": record["assigned_at"], "actor": actor, "action": "advisor_class_assigned", "payload": record})
        self._write_json(self.audit_path, audit); return record

    def revoke_advisor(self, actor: str, advisor_username: str, academic_class: str) -> None:
        rows = self.assignments(); kept = [row for row in rows if not (row["advisor_username"] == advisor_username and row["academic_class"] == academic_class)]
        if len(kept) == len(rows): raise ValueError("ASSIGNMENT_NOT_FOUND")
        self._write_json(self.assignment_path, kept)
