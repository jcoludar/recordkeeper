#!/usr/bin/env python3
# masterbook/substrate/session-manifest/hooks/manifest_stop_update.py
"""Stop hook (non-blocking RECORDER): maintain the session-manifest machine state.

Every Stop (turn boundary): resolve the in-flight log, allocate session_no if absent,
write/refresh the in-flight pointer (clear it once the log is status: done), and
regenerate sessions/INDEX.md. Fails OPEN (exit 0 on any error) per tier-1/hook-resilience.
This hook NEVER finalizes a session (no ended_at writes — that's the timing hook on done).
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import _manifest_atomic as atomic
import _manifest_index as index
import _manifest_pointer as pointer


def _frontmatter_region(text: str) -> str | None:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    return text[4:end] if end != -1 else None


def _field(text: str, key: str) -> str | None:
    fm = _frontmatter_region(text)
    if fm is None:
        return None
    m = re.search(rf"^{re.escape(key)}:\s*(\S.*)$", fm, re.MULTILINE)
    return m.group(1).strip() if m else None


def _has_ended_at(text: str) -> bool:
    return bool(_field(text, "ended_at"))


def _insert_field(text: str, key: str, value: str) -> str:
    """Insert `key: value` just before the closing frontmatter fence."""
    end = text.find("\n---\n", 4)
    if end == -1:
        return text
    return text[:end] + f"\n{key}: {value}" + text[end:]


def _resolve_inflight(sessions_dir: Path, project_dir: Path) -> Path | None:
    """Pointer first (if it names an existing log — `main()` decides whether it is
    still in-flight or now done and the pointer must be cleared); else most-recent-mtime
    log whose status is in_progress and has no ended_at."""
    state_dir = project_dir / ".claude" / "state"
    ptr = pointer.read_pointer(state_dir)
    if ptr:
        cand = project_dir / ptr["log"]
        try:
            # Same frontmatter guard as the mtime branch below: a fence-less/corrupt log
            # must NOT be resolved as in-flight (else main() burns a session_no every Stop
            # while _insert_field silently no-ops). A `done` log keeps a valid fence, so it
            # still resolves here and main() clears the pointer.
            if cand.is_file() and _frontmatter_region(cand.read_text()) is not None:
                return cand
        except OSError:
            pass
    candidates: list[Path] = []
    for p in sessions_dir.glob("*.md"):
        if p.name in ("INDEX.md", "README.md"):
            continue
        try:
            text = p.read_text()
        except OSError:
            continue
        if _frontmatter_region(text) is None:
            continue
        if _has_ended_at(text):
            continue
        if _field(text, "status") == "done":
            continue
        candidates.append(p)
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def main() -> int:
    try:
        project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
        sessions_dir = project_dir / "sessions"
        state_dir = project_dir / ".claude" / "state"
        if not sessions_dir.is_dir():
            return 0

        log = _resolve_inflight(sessions_dir, project_dir)
        if log is not None:
            text = log.read_text()
            status = _field(text, "status")
            if status == "done":
                pointer.clear_pointer(state_dir)
            else:
                if _field(text, "session_no") is None:
                    n = atomic.bump_counter(state_dir / "session-manifest" / "counter")
                    log.write_text(_insert_field(text, "session_no", str(n)))
                rel = str(log.relative_to(project_dir))
                pointer.write_pointer(
                    state_dir, log=rel,
                    slug=_field(log.read_text(), "slug") or log.stem,
                    started_at=_field(log.read_text(), "started_at") or "",
                )
        index.regenerate_index(sessions_dir)
        return 0
    except Exception as exc:  # noqa: BLE001 — recorder fails open
        print(f"manifest_stop_update: degraded (exit 0) — {exc}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
