#!/usr/bin/env python3
"""Stop hook: BLOCKING paperwork-enforcement check.

Loads .claude/paperwork.yaml; resolves the project's in-flight session log;
gathers the session's edit log; interpolates {today} / {session-slug}; runs
all file-rule + consistency-rule predicates via _paperwork_engine.run_all;
prints the structured report to stderr on failure.

Exit codes:
  0  — config missing OR all rules passed
  2  — config malformed / unknown keys / required missing
       OR rules need session context but no in-flight log
       OR any rule failed
       OR unexpected internal error (fail-loud)

CLI:
  --validate-config <path>  — validate-only mode, returns 0/2 without stdin context.

Substrate-wide invariant: every produced timestamp uses datetime.now() / date.today().
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import traceback
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

# Helper imports are guarded so a broken dependency fails CLOSED (block) rather
# than fail-open: a bare ImportError exits 1, which for a Stop hook is a
# *non-blocking* error — the gate would silently stop enforcing. A gate that
# cannot run its own code must still block. See tier-1/hook-resilience.
try:
    import _paperwork_config as cfg
    import _paperwork_edit_log as el
    import _paperwork_engine as engine
    import _paperwork_interpolation as interp
    import _paperwork_predicates as pred
    import _paperwork_session_log as sl

    _IMPORT_ERROR: Exception | None = None
except Exception as exc:  # noqa: BLE001 — any import problem must be catchable
    _IMPORT_ERROR = exc

_BYPASS_ENV = "PAPERWORK_ENFORCEMENT_BYPASS"


def _bypass_requested() -> bool:
    """True if the operator set the documented escape hatch to a truthy value.

    Checked before any fragile code path so a broken gate never bricks the
    session (tier-1/hook-resilience: gates fail closed *with a reachable bypass*).
    """
    val = os.environ.get(_BYPASS_ENV, "").strip().lower()
    return val not in ("", "0", "false", "no", "off")


def _today_iso() -> str:
    return dt.date.today().isoformat()


def _config_needs_session_context(config: dict) -> bool:
    """Any rule references {today} / {session-slug} or uses must-be-modified-this-session?"""
    def walk(obj):
        if isinstance(obj, str):
            if interp.needs_session_context(obj):
                yield True
        elif isinstance(obj, dict):
            for v in obj.values():
                yield from walk(v)
        elif isinstance(obj, list):
            for v in obj:
                yield from walk(v)
    for rule in config.get("files", []):
        if "must-be-modified-this-session" in rule:
            return True
        when = rule.get("when")
        if isinstance(when, dict) and "when-frontmatter" in when:
            # Gating on the in-flight log's frontmatter requires that log to exist.
            return True
        if any(walk(rule)):
            return True
    for rule in config.get("consistency", []):
        if any(walk(rule)):
            return True
    return False


def _interpolate_config_skip_unresolved(
    config: dict,
    *,
    today: str | None,
    session_slug: str | None,
    session_date: str | None = None,
) -> dict:
    """Interpolate {today} / {session-slug} / {session-date} in every string value.
    Rules with unresolvable tokens are dropped (with a logged note).
    """
    out = {
        "session-log-dir": config.get("session-log-dir", "sessions"),
        "files": [],
        "consistency": [],
    }
    for rule in config.get("files", []):
        try:
            out["files"].append(
                interp.apply_recursive(
                    rule, today=today, session_slug=session_slug, session_date=session_date
                )
            )
        except interp.UnresolvedToken as exc:
            print(
                f"paperwork-enforcement: skipping file rule (unresolved token: {exc})",
                file=sys.stderr,
            )
    for rule in config.get("consistency", []):
        try:
            out["consistency"].append(
                interp.apply_recursive(
                    rule, today=today, session_slug=session_slug, session_date=session_date
                )
            )
        except interp.UnresolvedToken as exc:
            print(
                f"paperwork-enforcement: skipping consistency rule (unresolved token: {exc})",
                file=sys.stderr,
            )
    return out


def _run_stop_hook(project_dir: Path) -> int:
    config_path = project_dir / ".claude" / "paperwork.yaml"
    if not config_path.is_file():
        return 0  # opt-in via config presence; missing = no-op

    try:
        config = cfg.load_and_validate(config_path)
    except cfg.ConfigError as exc:
        print(f"paperwork-enforcement: {exc}", file=sys.stderr)
        return 2

    sessions_dir = project_dir / config["session-log-dir"]
    inflight = sl.find_in_flight_log(sessions_dir, today=_today_iso())
    started_at: str | None = None
    session_slug: str | None = None
    session_date: str | None = None
    inflight_frontmatter: dict | None = None
    if inflight is not None:
        # The in-flight log's OWN date — used so file rules resolve against the
        # log actually in play, not {today} (they differ across midnight).
        session_date = sl.session_date_from_name(inflight.name)
        try:
            text = inflight.read_text()
        except OSError as exc:
            print(
                f"paperwork-enforcement: could not read in-flight log {inflight}: {exc}",
                file=sys.stderr,
            )
            return 2
        started_at, session_slug = sl.parse_started_at_and_slug(text)
        # Parse the in-flight log's full frontmatter so `when-frontmatter` gates
        # (status-conditional enforcement) can read the session phase. A broken
        # frontmatter leaves it None — gates then evaluate as not-satisfied.
        try:
            inflight_frontmatter = pred.parse_frontmatter_dict(inflight)
        except pred.FrontmatterParseError:
            inflight_frontmatter = None

    if started_at is None and _config_needs_session_context(config):
        print(
            f"paperwork-enforcement: no in-flight session log at {sessions_dir}; "
            f"run /begin-session before stopping.",
            file=sys.stderr,
        )
        return 2

    today = _today_iso()
    resolved = _interpolate_config_skip_unresolved(
        config, today=today, session_slug=session_slug, session_date=session_date
    )

    edit_log_path = project_dir / ".claude" / "state" / "paperwork-edit-log.jsonl"
    all_entries = el.read_entries(edit_log_path)
    session_entries = (
        el.filter_for_session(all_entries, started_at=started_at)
        if started_at is not None
        else []
    )

    failures = engine.run_all(
        config=resolved,
        project_dir=project_dir,
        edit_log=session_entries,
        inflight_frontmatter=inflight_frontmatter,
    )
    # tier 1 (default) blocks the Stop; tier 2 is deferred — surfaced as an
    # advisory but never blocks. See tier:1|2 rule annotation.
    blocking = [f for f in failures if f.tier == 1]
    deferred = [f for f in failures if f.tier != 1]
    if deferred:
        print(engine.format_advisory(deferred), file=sys.stderr, end="")
    if blocking:
        print(engine.format_report(blocking), file=sys.stderr, end="")
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Paperwork-enforcement Stop hook (+ --validate-config)."
    )
    parser.add_argument(
        "--validate-config",
        type=Path,
        default=None,
        help="Validate the given paperwork.yaml and exit (no Stop-hook context).",
    )
    args, _extra = parser.parse_known_args(argv)

    if args.validate_config is not None:
        if _IMPORT_ERROR is not None:
            print(
                f"paperwork-enforcement: hook dependencies failed to load — {_IMPORT_ERROR}",
                file=sys.stderr,
            )
            return 2
        return cfg.validate_config_cli(args.validate_config)

    # Reachable bypass — checked FIRST, before stdin handling or any import that
    # could have failed, so the operator can always clear a broken gate to fix it.
    if _bypass_requested():
        print(
            f"paperwork-enforcement: BYPASSED via {_BYPASS_ENV} — gate not enforced this Stop.",
            file=sys.stderr,
        )
        return 0

    # If our own dependencies could not load, fail CLOSED (block) and advertise
    # the bypass (tier-1/hook-resilience). exit 1 would be non-blocking = fail-open.
    if _IMPORT_ERROR is not None:
        print(
            f"paperwork-enforcement: hook dependencies failed to load — {_IMPORT_ERROR}. "
            f"Failing closed (Stop blocked). Set {_BYPASS_ENV}=1 to override.",
            file=sys.stderr,
        )
        return 2

    # Read the Stop envelope. Honor stop_hook_active: if we already blocked once
    # and Claude is re-invoking Stop, bow out with 0. A blocking Stop hook that
    # ignores this can infinite-loop and lose the whole session (Anthropic #55754).
    raw = ""
    try:
        raw = sys.stdin.read()
    except Exception:
        raw = ""
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        payload = {}
    if isinstance(payload, dict) and payload.get("stop_hook_active"):
        return 0

    project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()).resolve()
    try:
        return _run_stop_hook(project_dir)
    except Exception:
        tb = traceback.format_exc().strip().splitlines()
        last = tb[-1] if tb else "<no traceback>"
        print(f"paperwork-enforcement: internal error — {last}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
