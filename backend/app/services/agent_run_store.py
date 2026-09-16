"""Small JSON file store for Agent runs and immutable run artifacts."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from threading import RLock, local
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4
import re

try:  # POSIX is the deployment target (Docker/Linux and macOS development).
    import fcntl
except ImportError:  # pragma: no cover - retained for non-POSIX local tooling.
    fcntl = None

from backend.app.schemas import FeedbackNormalization, FeedbackReceipt, FeedbackRequest
from backend.app.schemas.agent_state import AgentState, ArtifactReference


class RunRevisionConflict(ValueError):
    pass


class FeedbackIdempotencyConflict(ValueError):
    pass


class AgentRunStore:
    _SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]+$")

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self._lock = RLock()
        self._held_run_locks = local()

    def save_state(self, state: AgentState, expected_revision: int | None = None) -> None:
        with self._lock:
            path = self._state_path(state.run_id)
            existing = self.load_state(state.run_id) if path.exists() else None
            if expected_revision is not None and (existing is None or existing.state_revision != expected_revision):
                raise RunRevisionConflict("State revision does not match expected revision")
            if existing is not None and state.state_revision <= existing.state_revision:
                raise RunRevisionConflict("State revision must increase")
            self._atomic_write(path, state.model_dump_json(indent=2).encode("utf-8"))

    def save_result(self, result: dict, expected_revision: int | None = None) -> None:
        """Persist the complete API result and its state as one locked run update."""
        state = AgentState.model_validate(result["state"])
        if result.get("run_id") != state.run_id:
            raise ValueError("Result run_id does not match state")
        with self._run_lock(state.run_id):
            self.save_state(state, expected_revision=expected_revision)
            payload = json.dumps(result, ensure_ascii=False, sort_keys=True,
                                 separators=(",", ":"), default=str).encode("utf-8")
            self._atomic_write(self._result_path(state.run_id), payload)

    @contextmanager
    def confirmation_transaction(self, run_id: str):
        """Serialize final-validation and persistence for one run across processes.

        The caller must reload the result *inside* this context, final-validate it,
        then save it with the loaded revision as its compare-and-swap value.  This
        prevents two web workers from confirming/replanning the same revision.
        Source snapshots are rechecked by ``AgentPipeline`` immediately after final
        validation; source writers must use their corresponding source lock.
        """
        with self._run_lock(run_id):
            yield

    def load_state(self, run_id: str) -> AgentState:
        path = self._state_path(run_id)
        return AgentState.model_validate_json(path.read_text(encoding="utf-8"))

    def load_result(self, run_id: str) -> dict:
        path = self._result_path(run_id)
        result = json.loads(path.read_text(encoding="utf-8"))
        state = AgentState.model_validate(result["state"])
        if state.run_id != run_id or result.get("run_id") != run_id:
            raise ValueError("Stored result run_id mismatch")
        return result

    def save_feedback(self, run_id: str, feedback: FeedbackRequest,
                      normalization: FeedbackNormalization, provenance: dict) -> FeedbackReceipt:
        """Store one normalized feedback record; identical retries are acknowledged once."""
        if feedback.run_id != run_id:
            raise ValueError("Feedback run_id does not match storage run_id")
        if normalization.feedback_id != feedback.feedback_id:
            raise ValueError("Feedback normalization does not match feedback")
        payload = {
            "feedback": feedback.model_dump(mode="json"),
            "normalization": normalization.model_dump(mode="json"),
            "provenance": provenance,
        }
        encoded_payload = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")
        record_hash = "sha256:" + sha256(encoded_payload).hexdigest()
        path = self._feedback_path(run_id, feedback.feedback_id)
        with self._lock:
            if path.exists():
                existing = json.loads(path.read_text(encoding="utf-8"))
                if existing.get("record_hash") != record_hash:
                    raise FeedbackIdempotencyConflict("Feedback ID already exists with different payload")
                return FeedbackReceipt(feedback_id=feedback.feedback_id,
                                       record_hash=record_hash,
                                       stored_at=datetime.fromisoformat(existing["stored_at"]), duplicate=True)
            record = {**payload, "record_hash": record_hash,
                      "stored_at": datetime.now(timezone.utc).isoformat()}
            self._atomic_write(path, json.dumps(record, ensure_ascii=False, sort_keys=True,
                                                 separators=(",", ":")).encode("utf-8"))
            return FeedbackReceipt(feedback_id=feedback.feedback_id, record_hash=record_hash,
                                   stored_at=datetime.fromisoformat(record["stored_at"]), duplicate=False)

    def load_feedback(self, run_id: str, feedback_id: str) -> dict:
        path = self._feedback_path(run_id, feedback_id)
        record = json.loads(path.read_text(encoding="utf-8"))
        payload = {key: record[key] for key in ("feedback", "normalization", "provenance")}
        encoded_payload = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")
        if "sha256:" + sha256(encoded_payload).hexdigest() != record.get("record_hash"):
            raise ValueError("Feedback record hash mismatch")
        return record

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

    def _result_path(self, run_id: str) -> Path:
        self._safe(run_id)
        return self.root / "runs" / run_id / "result.json"

    def _feedback_path(self, run_id: str, feedback_id: str) -> Path:
        self._safe(run_id)
        self._safe(feedback_id)
        return self.root / "runs" / run_id / "feedback" / f"{feedback_id}.json"

    def _safe(self, value: str) -> None:
        if not self._SAFE_ID.fullmatch(value):
            raise ValueError("Run and artifact IDs must be safe path components")

    @contextmanager
    def _run_lock(self, run_id: str):
        """Use an advisory per-run file lock in addition to the in-process lock."""
        self._safe(run_id)
        held = getattr(self._held_run_locks, "run_ids", set())
        if run_id in held:
            # ``save_result`` is deliberately called from inside a confirmation
            # transaction. Do not acquire flock twice through a second FD.
            yield
            return
        lock_path = self.root / "runs" / run_id / ".lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, lock_path.open("a+") as lock_file:
            if fcntl is not None:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            self._held_run_locks.run_ids = held | {run_id}
            try:
                yield
            finally:
                self._held_run_locks.run_ids = held
                if fcntl is not None:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

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
