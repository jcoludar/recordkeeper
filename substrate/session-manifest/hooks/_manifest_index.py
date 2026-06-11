"""Regenerate sessions/INDEX.md from log frontmatter (stdlib only)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from _manifest_atomic import atomic_write_text

_BANNER = "<!-- regenerated from frontmatter by session-manifest — do not edit by hand -->"
_FIELDS = ("session_no", "date", "slug", "started_at", "ended_at", "status", "predecessor")
_COLS = ("session_no", "date", "slug", "started_at", "ended_at", "status", "predecessor")


def _frontmatter(text: str) -> str | None:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None
    return text[4:end]


def read_fields(path: Path) -> dict | None:
    """Return frontmatter fields as a flat str->str dict, or None if unparseable."""
    fm = _frontmatter(path.read_text())
    if fm is None:
        return None
    out: dict[str, str] = {}
    for line in fm.splitlines():
        mobj = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if mobj:
            out[mobj.group(1)] = mobj.group(2).strip()
    return out


def _row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def regenerate_index(sessions_dir: Path) -> None:
    if not sessions_dir.is_dir():
        return
    parsed: list[dict] = []
    broken: list[str] = []
    for p in sorted(sessions_dir.glob("*.md")):
        if p.name in ("INDEX.md", "README.md"):
            continue
        try:
            fields = read_fields(p)
        except (OSError, ValueError):
            # OSError = unreadable; ValueError covers UnicodeDecodeError (non-UTF-8 log).
            # Either way the file degrades to one ⚠ unparseable row, never aborting regen.
            fields = None
        if fields is None:
            broken.append(p.name)
            continue
        fields["_name"] = p.name
        parsed.append(fields)

    def sort_key(f: dict):
        try:
            return (0, int(f.get("session_no") or 0), f.get("started_at", ""))
        except ValueError:
            return (1, 0, f.get("started_at", ""))

    parsed.sort(key=sort_key)

    lines = [_BANNER, "# Session index", "", _row(list(_COLS)), _row(["---"] * len(_COLS))]
    for f in parsed:
        status = f.get("status", "")
        if status == "in_progress" and not f.get("ended_at"):
            status = "⚠ unclosed"
        lines.append(_row([
            f.get("session_no", ""), f.get("date", ""), f.get("slug", ""),
            f.get("started_at", ""), f.get("ended_at", ""), status, f.get("predecessor", ""),
        ]))
    for name in broken:
        lines.append(_row(["", "", name, "", "", "⚠ unparseable", ""]))
    atomic_write_text(sessions_dir / "INDEX.md", "\n".join(lines) + "\n")
