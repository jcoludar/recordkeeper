"""Crash-safe IO for session-manifest (vendored).

vendored-from: original to this substrate. Promote to masterbook/helpers/ when a
second substrate needs the same atomic-write/counter logic (rule of three).
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path


def atomic_write_text(path: Path, text: str) -> None:
    """Write text atomically (tempfile + os.replace). Crash-safe; never partial."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_counter(path: Path) -> int:
    """Return the integer counter, or 0 if missing/corrupt."""
    try:
        return int(path.read_text().strip() or "0")
    except (OSError, ValueError):
        return 0


def bump_counter(path: Path) -> int:
    """Read-increment-write the counter atomically; return the new value."""
    n = read_counter(path) + 1
    atomic_write_text(path, f"{n}\n")
    return n
