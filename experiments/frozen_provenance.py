"""Git provenance guard for frozen experimental artifacts."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import subprocess


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, text=True, capture_output=True, check=True
    )
    return result.stdout.strip()


def frozen_source_provenance(root: Path, *, allow_dirty: bool = False) -> dict:
    """Return immutable Git identifiers and reject an unfrozen worktree."""
    status = _git(root, "status", "--porcelain=v1")
    if status and not allow_dirty:
        raise RuntimeError(
            "FROZEN_SOURCE_REQUIRED: commit or stash all changes before an official run; "
            "use --allow-dirty only for smoke tests."
        )
    return {
        "git_commit": _git(root, "rev-parse", "HEAD"),
        "git_tree": _git(root, "rev-parse", "HEAD^{tree}"),
        "working_tree_clean": not bool(status),
        "working_tree_status_sha256": "sha256:" + sha256(status.encode()).hexdigest(),
    }
