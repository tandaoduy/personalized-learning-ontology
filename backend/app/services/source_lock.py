"""Cooperative process lock for mutable JSON knowledge sources in the MVP."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import fcntl


@contextmanager
def exclusive_source_lock(path: str | Path):
    """Prevent a confirm and an in-app JSON source writer from crossing.

    The lock file survives atomic replacement of the data file.  Every writer
    managed by this application uses this same lock; external source imports
    must do so too before they are treated as a supported live source.
    """
    source = Path(path).resolve()
    lock_path = source.with_name(f".{source.name}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
