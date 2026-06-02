"""Predicate implementations for paperwork-enforcement rules.

Each predicate returns a PredicateResult dataclass (passed: bool, reason: str).
The engine collects every failing reason into the structured stderr report.

T6 ships must_exist, must_be_modified_this_session, plus the resolve_glob helper.
T7 extends with frontmatter.* predicates.
"""
from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


def _normalize_for_compare(value: Any) -> str:
    """String form of a frontmatter value for equals/in/matches comparisons.

    PyYAML parses unquoted ISO 8601 strings into datetime/date instances; the
    default `str()` on a datetime uses a space separator (`2026-05-13 19:00:00`),
    breaking T-separated ISO regexes and string-equals checks. Normalize via
    `.isoformat()` so the predicate sees the same representation a YAML-quoted
    string would have produced.
    """
    if isinstance(value, (_dt.datetime, _dt.date)):
        return value.isoformat()
    return str(value)


@dataclass(frozen=True)
class PredicateResult:
    passed: bool
    reason: str = ""


def resolve_glob(project_dir: Path, pattern: str) -> list[Path]:
    """Resolve `pattern` (POSIX glob) relative to project_dir. Returns absolute Paths.

    Supports `*`, `**`, `?`, `[abc]` via pathlib.Path.glob semantics.
    """
    return sorted(project_dir.glob(pattern))


def must_exist(matches: list[Path], *, expected: bool) -> PredicateResult:
    """must-exist: true → matches non-empty; false → matches empty."""
    if expected:
        if matches:
            return PredicateResult(True)
        return PredicateResult(False, "no file matches the configured pattern")
    else:
        if matches:
            sample = matches[0].name
            return PredicateResult(
                False, f"file(s) match pattern but must-exist=false (e.g. {sample})"
            )
        return PredicateResult(True)


def must_be_modified_this_session(
    matches: list[Path],
    *,
    edit_log: list[dict[str, Any]],
    project_dir: Path,
    expected: bool,
) -> PredicateResult:
    """must-be-modified-this-session: true → at least one match is in edit_log; false → none are."""
    edited_paths = {e.get("path", "") for e in edit_log}
    project_dir = project_dir.resolve()
    matched_in_log: list[str] = []
    for m in matches:
        try:
            rel = str(m.resolve().relative_to(project_dir))
        except ValueError:
            rel = str(m.resolve())
        if rel in edited_paths:
            matched_in_log.append(rel)
    if expected:
        if matched_in_log:
            return PredicateResult(True)
        return PredicateResult(
            False, "matched file(s) not modified in this session's edit log"
        )
    else:
        if matched_in_log:
            return PredicateResult(
                False,
                f"matched file(s) modified this session but must-be-modified-this-session=false ({matched_in_log[0]})",
            )
        return PredicateResult(True)


# ── Frontmatter parsing & predicates (T7) ─────────────────────────────────


class FrontmatterParseError(Exception):
    """Raised when a target file's frontmatter is structurally broken."""


_FM_OPEN = "---\n"
_FM_CLOSE = "\n---\n"


def parse_frontmatter_dict(path: Path) -> dict[str, Any] | None:
    """Parse a markdown file's YAML frontmatter. Returns dict, or None if absent.

    Raises FrontmatterParseError if frontmatter is present but malformed.
    """
    try:
        text = path.read_text()
    except OSError as exc:
        raise FrontmatterParseError(f"could not read {path}: {exc}") from exc
    if not text.startswith(_FM_OPEN):
        return None
    end = text.find(_FM_CLOSE, len(_FM_OPEN))
    if end == -1:
        return None
    region = text[len(_FM_OPEN):end]
    try:
        data = yaml.safe_load(region)
    except yaml.YAMLError as exc:
        raise FrontmatterParseError(f"{path}: malformed frontmatter YAML: {exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise FrontmatterParseError(
            f"{path}: frontmatter is not a mapping (got {type(data).__name__})"
        )
    return data


def _is_field_present(fm: dict[str, Any], field: str) -> bool:
    return field in fm and fm[field] is not None


def check_frontmatter(
    *,
    fm: dict[str, Any],
    field: str,
    spec: dict[str, Any],
) -> list[PredicateResult]:
    """Apply all sub-key constraints in `spec` to `fm[field]`.

    Returns one PredicateResult per check (typically 1-4 per call). Combines
    naturally via AND in the caller — any failure means the field failed.
    """
    results: list[PredicateResult] = []

    # Determine effective `required`: default True if any other constraint specified.
    has_other_constraints = bool(set(spec.keys()) & {"equals", "in", "matches"})
    required = spec.get("required", has_other_constraints)

    present = _is_field_present(fm, field)
    if required and not present:
        return [PredicateResult(False, f"frontmatter.{field}: required field missing")]
    if not present:
        # required=False and field absent → no other checks needed.
        return [PredicateResult(True)]

    value = fm[field]
    str_value = _normalize_for_compare(value)

    if "equals" in spec:
        expected = _normalize_for_compare(spec["equals"])
        if str_value != expected:
            results.append(PredicateResult(
                False,
                f"frontmatter.{field}: expected `{expected}`, got `{str_value}`",
            ))
        else:
            results.append(PredicateResult(True))

    if "in" in spec:
        valid = [_normalize_for_compare(v) for v in spec["in"]]
        if str_value not in valid:
            results.append(PredicateResult(
                False,
                f"frontmatter.{field}: value `{str_value}` not in {valid}",
            ))
        else:
            results.append(PredicateResult(True))

    if "matches" in spec:
        pattern = spec["matches"]
        if not re.search(pattern, str_value):
            results.append(PredicateResult(
                False,
                f"frontmatter.{field}: value `{str_value}` does not match /{pattern}/",
            ))
        else:
            results.append(PredicateResult(True))

    if not results:
        # required: true, field present, no other constraints → that's a pass.
        results.append(PredicateResult(True))
    return results
