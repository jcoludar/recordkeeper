"""Paperwork-enforcement engine orchestrator.

Given a loaded + interpolated config and the session edit log, evaluate
every rule and return the list of failures.

Build-out:
- T8: evaluate_file_rule (must-exist, must-be-modified, frontmatter)
- T9: when: clause gating
- T10: evaluate_consistency_rule
- T11: format_report
"""
from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import _paperwork_predicates as pred


@dataclass(frozen=True)
class Failure:
    rule_label: str           # human-readable rule identifier for the report
    reason: str               # one-line failure reason
    tier: int = 1             # 1 = blocking (default); 2 = deferred/advisory


def evaluate_file_rule(
    *,
    rule: dict[str, Any],
    project_dir: Path,
    edit_log: list[dict[str, Any]],
) -> list[Failure]:
    """Evaluate a single `files:` entry. Returns all failures.

    Order: when: clause first (skip if false); then must-exist; if it fails,
    skip downstream. Otherwise: must-be-modified, then frontmatter per match.
    """
    if not when_clause_holds(when=rule.get("when"), edit_log=edit_log):
        return []
    pattern = rule["path"]
    tier = rule.get("tier", 1)
    rule_label = f"[files] {pattern}"
    matches = pred.resolve_glob(project_dir, pattern)
    failures: list[Failure] = []

    # must-exist
    if "must-exist" in rule:
        r = pred.must_exist(matches, expected=rule["must-exist"])
        if not r.passed:
            failures.append(Failure(rule_label, r.reason, tier=tier))
            # Cannot run downstream checks on a missing file — return early.
            return failures

    # must-be-modified-this-session
    if "must-be-modified-this-session" in rule:
        r = pred.must_be_modified_this_session(
            matches,
            edit_log=edit_log,
            project_dir=project_dir,
            expected=rule["must-be-modified-this-session"],
        )
        if not r.passed:
            failures.append(Failure(rule_label, r.reason, tier=tier))

    # frontmatter — per match
    if "frontmatter" in rule:
        for match in matches:
            try:
                fm = pred.parse_frontmatter_dict(match)
            except pred.FrontmatterParseError as exc:
                failures.append(Failure(
                    f"[files] {match.relative_to(project_dir)}",
                    f"frontmatter could not be parsed: {exc}",
                    tier=tier,
                ))
                continue
            if fm is None:
                fm = {}
            for field, field_spec in rule["frontmatter"].items():
                results = pred.check_frontmatter(fm=fm, field=field, spec=field_spec)
                for r in results:
                    if not r.passed:
                        failures.append(Failure(
                            f"[files] {match.relative_to(project_dir)}",
                            r.reason,
                            tier=tier,
                        ))

    return failures


# ── when: gating (T9) ─────────────────────────────────────────────────────


def when_clause_holds(*, when: dict[str, Any] | None, edit_log: list[dict[str, Any]]) -> bool:
    """Evaluate a `when:` clause. Returns True if the gate allows the rule to run."""
    if not when:
        return True
    pattern = when.get("when-files-modified-matching")
    if pattern is None:
        return True
    for entry in edit_log:
        path = entry.get("path", "")
        if fnmatch.fnmatch(path, pattern):
            return True
    return False


# ── consistency rules (T10) ───────────────────────────────────────────────


_FM_OPEN = "---\n"
_FM_CLOSE = "\n---\n"


def _strip_frontmatter(text: str) -> str:
    """Return body only (frontmatter excluded). If no well-formed frontmatter, return text as-is."""
    if not text.startswith(_FM_OPEN):
        return text
    end = text.find(_FM_CLOSE, len(_FM_OPEN))
    if end == -1:
        return text
    return text[end + len(_FM_CLOSE):]


def _resolve_target_paths(project_dir: Path, target: str) -> list[Path]:
    """Resolve a target string to one or more paths. Returns the input as a single
    Path if not a glob, else expanded glob matches.
    """
    if any(ch in target for ch in "*?["):
        return pred.resolve_glob(project_dir, target)
    return [project_dir / target]


def _is_glob(s: str) -> bool:
    return any(ch in s for ch in "*?[")


def evaluate_consistency_rule(
    *,
    rule: dict[str, Any],
    project_dir: Path,
) -> list[Failure]:
    """Evaluate a single `consistency:` entry. Returns all failures."""
    name = rule["name"]
    find_pattern = rule["find"]
    src_glob = rule["in"]
    targets = rule["must-also-appear-in"]
    tier = rule.get("tier", 1)
    rule_label = f"[consistency: {name}]"

    failures: list[Failure] = []
    source_paths = pred.resolve_glob(project_dir, src_glob) if _is_glob(src_glob) else [project_dir / src_glob]
    if not source_paths:
        return failures  # No source files matched — consistency rule simply doesn't fire.

    regex = re.compile(find_pattern)

    for src in source_paths:
        try:
            text = src.read_text()
        except OSError:
            continue
        body = _strip_frontmatter(text)
        captures = sorted(set(regex.findall(body)))
        if not captures:
            continue

        for capture in captures:
            for target in targets:
                target_paths = _resolve_target_paths(project_dir, target)
                if _is_glob(target):
                    # Glob target: capture must appear in at least one match.
                    found = False
                    for tp in target_paths:
                        try:
                            if capture in tp.read_text():
                                found = True
                                break
                        except OSError:
                            continue
                    if not found:
                        try:
                            src_rel = str(src.relative_to(project_dir))
                        except ValueError:
                            src_rel = str(src)
                        failures.append(Failure(
                            rule_label,
                            f'"{capture}" found in {src_rel} but missing in any {target}',
                            tier=tier,
                        ))
                else:
                    # Single path: capture must appear in that file.
                    tp = target_paths[0]
                    try:
                        present = capture in tp.read_text()
                    except OSError:
                        present = False
                    if not present:
                        try:
                            src_rel = str(src.relative_to(project_dir))
                        except ValueError:
                            src_rel = str(src)
                        failures.append(Failure(
                            rule_label,
                            f'"{capture}" found in {src_rel} but missing in {target}',
                            tier=tier,
                        ))
    return failures


# ── run_all + format_report (T11) ─────────────────────────────────────────


def run_all(
    *,
    config: dict[str, Any],
    project_dir: Path,
    edit_log: list[dict[str, Any]],
) -> list[Failure]:
    """Top-level engine entry point — walks every files: rule and every consistency: rule."""
    failures: list[Failure] = []
    for rule in config.get("files", []):
        failures.extend(evaluate_file_rule(
            rule=rule, project_dir=project_dir, edit_log=edit_log,
        ))
    for rule in config.get("consistency", []):
        failures.extend(evaluate_consistency_rule(
            rule=rule, project_dir=project_dir,
        ))
    return failures


def _grouped_body(failures: list[Failure]) -> list[str]:
    """Group failures by rule_label, preserving first-seen order."""
    by_label: dict[str, list[Failure]] = {}
    for f in failures:
        by_label.setdefault(f.rule_label, []).append(f)
    lines: list[str] = []
    for label, items in by_label.items():
        lines.append(label)
        for f in items:
            lines.append(f"  ✗ {f.reason}")
        lines.append("")
    return lines


def format_report(failures: list[Failure]) -> str:
    """Render the blocking (tier-1) stderr report. Empty list → empty string."""
    if not failures:
        return ""
    n = len(failures)
    lines: list[str] = [f"paperwork-enforcement: {n} rule(s) failed.", ""]
    lines.extend(_grouped_body(failures))
    lines.append("To unblock: fix each item above, then end the session again.")
    return "\n".join(lines) + "\n"


def format_advisory(failures: list[Failure]) -> str:
    """Render deferred (tier-2) failures as a non-blocking advisory — surfaced but
    not held against the session. Empty list → empty string."""
    if not failures:
        return ""
    n = len(failures)
    lines: list[str] = [
        f"paperwork-enforcement: {n} deferred (tier-2) item(s) — advisory, not blocking this session.",
        "",
    ]
    lines.extend(_grouped_body(failures))
    lines.append("These are deferred: address when convenient; they do not block Stop.")
    return "\n".join(lines) + "\n"
