"""Load and validate paperwork.yaml.

Loud failures: malformed YAML (with line number), unknown keys (did-you-mean),
missing required keys. Returns a normalized dict with defaults filled.
"""
from __future__ import annotations

import difflib
import re
import sys
from pathlib import Path
from typing import Any

import yaml


class ConfigError(Exception):
    """Raised on any validation failure in paperwork.yaml."""


# ── Schema vocabularies ───────────────────────────────────────────────────

TOP_LEVEL_KEYS = {"session-log-dir", "files", "consistency"}
FILE_ENTRY_KEYS = {
    "path",
    "must-exist",
    "must-be-modified-this-session",
    "frontmatter",
    "when",
    "tier",
}
FRONTMATTER_FIELD_KEYS = {"required", "equals", "in", "matches"}
WHEN_KEYS = {"when-files-modified-matching"}
CONSISTENCY_KEYS = {"name", "find", "in", "must-also-appear-in", "tier"}
VALID_TIERS = {1, 2}


def _did_you_mean(key: str, valid: set[str]) -> str:
    suggestions = difflib.get_close_matches(key, valid, n=1, cutoff=0.6)
    if suggestions:
        return f" Did you mean `{suggestions[0]}`?"
    return ""


def _check_unknown_keys(obj: dict[str, Any], valid: set[str], context: str) -> None:
    unknown = set(obj.keys()) - valid
    if not unknown:
        return
    first = sorted(unknown)[0]
    raise ConfigError(
        f"{context}: unknown key `{first}`.{_did_you_mean(first, valid)}"
    )


def _require_key(obj: dict[str, Any], key: str, context: str) -> None:
    if key not in obj:
        raise ConfigError(f"{context}: required key `{key}` is missing")


def _validate_frontmatter_field(field_name: str, value: Any, context: str) -> None:
    if not isinstance(value, dict):
        raise ConfigError(
            f"{context}: frontmatter.{field_name} must be a mapping, got {type(value).__name__}"
        )
    _check_unknown_keys(
        value, FRONTMATTER_FIELD_KEYS, f"{context}: frontmatter.{field_name}"
    )


def _validate_when(when_obj: Any, context: str) -> None:
    if not isinstance(when_obj, dict):
        raise ConfigError(f"{context}: `when:` must be a mapping")
    _check_unknown_keys(when_obj, WHEN_KEYS, f"{context}: when")


def _validate_tier(entry: dict[str, Any], context: str) -> None:
    """A rule's optional `tier:` (1=blocking, 2=deferred) must be 1 or 2."""
    if "tier" not in entry:
        return
    tier = entry["tier"]
    if tier not in VALID_TIERS:
        raise ConfigError(
            f"{context}: `tier` must be one of {sorted(VALID_TIERS)} (1=blocking, 2=deferred), got {tier!r}"
        )


def _validate_find_regex(pattern: Any, context: str) -> None:
    """`find:` must compile, and have at most one capturing group — `re.findall`
    returns tuples for >1 group, which the engine's `capture in text` cannot use.
    Caught at load so `--validate-config` (and CI) fail before Stop time."""
    if not isinstance(pattern, str):
        raise ConfigError(f"{context}: `find` must be a string")
    try:
        compiled = re.compile(pattern)
    except re.error as exc:
        raise ConfigError(f"{context}: `find` is not a valid regex: {exc}") from exc
    if compiled.groups > 1:
        raise ConfigError(
            f"{context}: `find` has {compiled.groups} capturing groups; use at most one "
            f"(more than one makes re.findall return tuples)"
        )


def _validate_file_entry(entry: Any, idx: int) -> None:
    context = f"files[{idx}]"
    if not isinstance(entry, dict):
        raise ConfigError(f"{context}: must be a mapping, got {type(entry).__name__}")
    _check_unknown_keys(entry, FILE_ENTRY_KEYS, context)
    _require_key(entry, "path", context)
    if not isinstance(entry["path"], str):
        raise ConfigError(f"{context}: `path` must be a string")
    if "frontmatter" in entry:
        fm = entry["frontmatter"]
        if not isinstance(fm, dict):
            raise ConfigError(f"{context}: `frontmatter` must be a mapping")
        for field_name, field_spec in fm.items():
            _validate_frontmatter_field(field_name, field_spec, context)
    if "when" in entry:
        _validate_when(entry["when"], context)
    _validate_tier(entry, context)


def _validate_consistency_entry(entry: Any, idx: int) -> None:
    context = f"consistency[{idx}]"
    if not isinstance(entry, dict):
        raise ConfigError(f"{context}: must be a mapping, got {type(entry).__name__}")
    _check_unknown_keys(entry, CONSISTENCY_KEYS, context)
    for key in ("name", "find", "in", "must-also-appear-in"):
        _require_key(entry, key, context)
    if not isinstance(entry["must-also-appear-in"], list):
        raise ConfigError(f"{context}: `must-also-appear-in` must be a list")
    _validate_find_regex(entry["find"], context)
    _validate_tier(entry, context)


def load_and_validate(path: Path) -> dict[str, Any]:
    """Load and validate paperwork.yaml. Returns a normalized dict with defaults filled.

    Raises ConfigError on any problem.
    """
    if not path.is_file():
        raise ConfigError(f"paperwork.yaml does not exist: {path}")
    try:
        raw = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        line = getattr(getattr(exc, "problem_mark", None), "line", None)
        line_hint = f" near line {line + 1}" if line is not None else ""
        raise ConfigError(f"{path}: malformed YAML{line_hint}: {exc}") from exc

    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ConfigError(f"{path}: top-level must be a mapping, got {type(raw).__name__}")

    _check_unknown_keys(raw, TOP_LEVEL_KEYS, str(path))

    session_log_dir = raw.get("session-log-dir", "sessions")
    if not isinstance(session_log_dir, str):
        raise ConfigError(f"{path}: `session-log-dir` must be a string")

    files = raw.get("files", []) or []
    if not isinstance(files, list):
        raise ConfigError(f"{path}: `files:` must be a list")
    for i, entry in enumerate(files):
        _validate_file_entry(entry, i)

    consistency = raw.get("consistency", []) or []
    if not isinstance(consistency, list):
        raise ConfigError(f"{path}: `consistency:` must be a list")
    for i, entry in enumerate(consistency):
        _validate_consistency_entry(entry, i)

    return {
        "session-log-dir": session_log_dir,
        "files": files,
        "consistency": consistency,
    }


def validate_config_cli(path: Path) -> int:
    """CLI entry point — returns 0 / 2 with the same parse / unknown-key checks."""
    try:
        load_and_validate(path)
    except ConfigError as exc:
        print(f"paperwork-enforcement: {exc}", file=sys.stderr)
        return 2
    print(f"paperwork-enforcement: config OK ({path})")
    return 0
