"""Small JSON file store for Agent runs and immutable run artifacts."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from threading import RLock
from uuid import uuid4
import re

from backend.app.schemas.agent_state import AgentState, ArtifactReference


class RunRevisionConflict(ValueError):
    pass


class AgentRunStore:
    _SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]+$")

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self._lock = RLock()

    def save_state(self, state: AgentState, expected_revision: int | None = None) -> None:
        with self._lock:
            path = self._state_path(state.run_id)
            existing = self.load_state(state.run_id) if path.exists() else None
            if expected_revision is not None and (existing is None or existing.state_revision != expected_revision):
                raise RunRevisionConflict("State revision does not match expected revision")
            if existing is not None and state.state_revision <= existing.state_revision:
                raise RunRevisionConflict("State revision must increase")
            self._atomic_write(path, state.model_dump_json(indent=2).encode("utf-8"))

    def load_state(self, run_id: str) -> AgentState:
        path = self._state_path(run_id)
        return AgentState.model_validate_json(path.read_text(encoding="utf-8"))

    def save_artifact(self, run_id: str, kind: str, content: bytes) -> ArtifactReference:
        self._safe(run_id)
        self._safe(kind)
        digest = "sha256:" + sha256(content).hexdigest()
        artifact_id = f"ART_{uuid4().hex}"
        relative = Path("runs") / run_id / "artifacts" / f"{artifact_id}.{kind}"
        self._atomic_write(self.root / relative, content)
        return ArtifactReference(artifact_id=artifact_id, kind=kind, ref=relative.as_posix(), content_hash=digest)

    def read_artifact(self, reference: ArtifactReference) -> bytes:
        path = (self.root / reference.ref).resolve()
        if self.root not in path.parents:
            raise ValueError("Artifact reference escapes store root")
        content = path.read_bytes()
        if "sha256:" + sha256(content).hexdigest() != reference.content_hash:
            raise ValueError("Artifact content hash mismatch")
        return content

    def _state_path(self, run_id: str) -> Path:
        self._safe(run_id)
        return self.root / "runs" / run_id / "state.json"

    def _safe(self, value: str) -> None:
        if not self._SAFE_ID.fullmatch(value):
            raise ValueError("Run and artifact IDs must be safe path components")

    @staticmethod
    def _atomic_write(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            temporary.write_bytes(content)
            temporary.replace(path)
        finally:
            if temporary.exists():
                temporary.unlink()
