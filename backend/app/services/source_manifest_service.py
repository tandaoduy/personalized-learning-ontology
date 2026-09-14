"""Resolve the versioned local policy-source inventory into a hashed manifest."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from backend.app.schemas.snapshot import PolicySource, SourceManifest

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_PATH = ROOT / "knowledge" / "source_manifest.json"

def _hash(path: Path) -> str | None:
    return "sha256:" + sha256(path.read_bytes()).hexdigest() if path.is_file() else None

def resolve_source_manifest() -> SourceManifest:
    """Bind locally available declared sources to their exact bytes hash."""
    raw = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
    sources = tuple(PolicySource(
        domain=item["domain"], source_ref=item["source_ref"], version=item["version"],
        effective_date=item.get("effective_date"),
        content_hash=_hash(ROOT / item["source_path"]) if item.get("source_path") else None,
        authority_status=item["authority_status"], limitation=item.get("limitation"),
    ) for item in raw["sources"])
    payload = {"manifest_id": raw["manifest_id"], "version": raw["version"],
               "sources": [item.model_dump(mode="json") for item in sources]}
    return SourceManifest(manifest_id=raw["manifest_id"], manifest_ref="knowledge/source_manifest.json",
        version=raw["version"], content_hash="sha256:" + sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest(), sources=sources)
