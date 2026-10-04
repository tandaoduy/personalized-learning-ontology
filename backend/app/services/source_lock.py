"""Cooperative process lock for mutable JSON knowledge sources in the MVP."""
from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path

if os.name == "nt":
    import msvcrt
else:
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
        # Windows locks a byte range; ensure the range exists before locking.
        if os.name == "nt":
            lock_file.seek(0)
            lock_file.write("0")
            lock_file.flush()
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
        else:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == "nt":
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
