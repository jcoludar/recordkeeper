"""Read the in-flight session log for paperwork-enforcement.

Mirrors the pattern in session-paperwork's session_stop_log_timing.py but
extracts two specific frontmatter fields (started_at, slug) used by the
paperwork-enforcement Stop hook to scope edits and resolve {session-slug}.
"""
from __future__ import annotations

import re
from pathlib import Path


def frontmatter_region(text: str) -> str | None:
    """Return the YAML region between opening and closing `---` fences, exclusive of both.

    Returns None if no well-formed frontmatter.
    """
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None
    return text[4:end]


_ENDED_AT_RE = re.compile(r"^ended_at:\s*\S", re.MULTILINE)


def has_ended_at(text: str) -> bool:
    """True if the frontmatter region contains an `ended_at:` line with a value."""
    fm = frontmatter_region(text)
    if fm is None:
        return False
    return bool(_ENDED_AT_RE.search(fm))


_STARTED_AT_RE = re.compile(r"^started_at:\s*(.+?)\s*$", re.MULTILINE)
_SLUG_RE = re.compile(r"^slug:\s*(.+?)\s*$", re.MULTILINE)


def _strip_yaml_quotes(value: str) -> str:
    """Strip a single layer of single or double quotes from a YAML scalar."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        return value[1:-1]
    return value


def parse_started_at_and_slug(text: str) -> tuple[str | None, str | None]:
    """Extract `started_at:` and `slug:` from the frontmatter region.

    Returns (started_at, slug). Either may be None if absent.
    Single-line scalars only — multi-line YAML values not supported.
    """
    fm = frontmatter_region(text)
    if fm is None:
        return (None, None)
    started_at: str | None = None
    m = _STARTED_AT_RE.search(fm)
    if m:
        started_at = _strip_yaml_quotes(m.group(1))
    slug: str | None = None
    m = _SLUG_RE.search(fm)
    if m:
        slug = _strip_yaml_quotes(m.group(1))
    return (started_at, slug)


def find_in_flight_log(sessions_dir: Path, today: str | None = None) -> Path | None:
    """Return the session log for the current Stop event.

    Selection rules, in order:
      1. .md files whose name starts with `<today>-` AND whose frontmatter lacks
         `ended_at:` (truly in-flight). Most-recent by mtime if multiple.
      2. .md files whose name starts with `<today>-` regardless of ended_at —
         today's log even if the timing hook already closed it. (Stop hooks run
         in parallel in Claude Code; the timing hook can close the log before
         this check runs, so a closed-today log is still the right context.)
      3. Any .md without ended_at (most-recent by mtime). Conservative fallback
         for projects that don't use date-prefixed filenames.
      4. None.

    Files without parseable frontmatter or without a parseable `started_at:`
    are skipped (they can't supply session context).

    The `today` argument is an ISO date `YYYY-MM-DD`; when omitted, only rules
    3 and 4 apply.
    """
    if not sessions_dir.is_dir():
        return None
    today_open: list[Path] = []
    today_any: list[Path] = []
    other_open: list[Path] = []
    for path in sessions_dir.glob("*.md"):
        try:
            text = path.read_text()
        except OSError:
            continue
        if frontmatter_region(text) is None:
            continue
        started_at, _ = parse_started_at_and_slug(text)
        if started_at is None:
            # Skip malformed logs — they can't supply context.
            continue
        closed = has_ended_at(text)
        is_today = today is not None and path.name.startswith(f"{today}-")
        if is_today and not closed:
            today_open.append(path)
        elif is_today:
            today_any.append(path)
        elif not closed:
            other_open.append(path)
    for pool in (today_open, today_any, other_open):
        if pool:
            pool.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            return pool[0]
    return None
