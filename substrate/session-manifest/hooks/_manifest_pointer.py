"""Authoritative in-flight session pointer: .claude/state/session-manifest/in-flight.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from _manifest_atomic import atomic_write_text


def pointer_path(state_dir: Path) -> Path:
    """state_dir is `<project>/.claude/state`."""
    return state_dir / "session-manifest" / "in-flight.json"


def read_pointer(state_dir: Path) -> dict | None:
    """Return the pointer dict (must carry a truthy `log`), or None if absent/corrupt."""
    try:
        data = json.loads(pointer_path(state_dir).read_text())
    except (OSError, ValueError):
        return None
    if isinstance(data, dict) and data.get("log"):
        return data
    return None


def write_pointer(state_dir: Path, *, log: str, slug: str, started_at: str) -> None:
    atomic_write_text(
        pointer_path(state_dir),
        json.dumps({"log": log, "slug": slug, "started_at": started_at}),
    )


def clear_pointer(state_dir: Path) -> None:
    try:
        pointer_path(state_dir).unlink()
    except OSError:
        pass
