"""Tests for _paperwork_interpolation."""
import sys
from pathlib import Path

import pytest

SUBSTRATE_HOOKS = (
    Path(__file__).resolve().parent.parent
    / "substrate"
    / "paperwork-enforcement"
    / "hooks"
)
if str(SUBSTRATE_HOOKS) not in sys.path:
    sys.path.insert(0, str(SUBSTRATE_HOOKS))

import _paperwork_interpolation as interp  # noqa: E402


# ── expand_tokens ─────────────────────────────────────────────────────────


def test_expand_tokens_replaces_today():
    result = interp.expand_tokens(
        "sessions/{today}-foo.md",
        today="2026-05-13",
        session_slug="bar",
    )
    assert result == "sessions/2026-05-13-foo.md"


def test_expand_tokens_replaces_session_slug():
    result = interp.expand_tokens(
        "sessions/{today}-{session-slug}.md",
        today="2026-05-13",
        session_slug="wave-3",
    )
    assert result == "sessions/2026-05-13-wave-3.md"


def test_expand_tokens_returns_input_unchanged_when_no_tokens():
    assert interp.expand_tokens("plain", today="2026-05-13", session_slug="x") == "plain"


def test_expand_tokens_raises_when_session_slug_referenced_but_none():
    with pytest.raises(interp.UnresolvedToken) as exc_info:
        interp.expand_tokens(
            "sessions/{session-slug}.md",
            today="2026-05-13",
            session_slug=None,
        )
    assert "session-slug" in str(exc_info.value)


def test_expand_tokens_raises_when_today_referenced_but_none():
    with pytest.raises(interp.UnresolvedToken):
        interp.expand_tokens("{today}", today=None, session_slug=None)


def test_expand_tokens_today_resolved_even_if_session_slug_none():
    assert (
        interp.expand_tokens("{today}", today="2026-05-13", session_slug=None)
        == "2026-05-13"
    )


def test_expand_tokens_unknown_token_left_alone():
    """Tokens we don't know about (e.g., {ticket-id}) are not touched — surface as glob mismatch later."""
    assert (
        interp.expand_tokens("{ticket-id}", today="2026-05-13", session_slug="x")
        == "{ticket-id}"
    )


# ── needs_session_context ─────────────────────────────────────────────────


def test_needs_session_context_true_when_session_slug_referenced():
    assert interp.needs_session_context("sessions/{session-slug}.md") is True


def test_needs_session_context_true_when_today_referenced():
    assert interp.needs_session_context("sessions/{today}.md") is True


def test_needs_session_context_false_when_no_tokens():
    assert interp.needs_session_context("plain") is False


# ── apply_recursive ───────────────────────────────────────────────────────


def test_apply_recursive_expands_in_nested_dicts():
    config = {
        "files": [
            {
                "path": "sessions/{today}-{session-slug}.md",
                "frontmatter": {"date": {"equals": "{today}"}},
            }
        ]
    }
    out = interp.apply_recursive(
        config, today="2026-05-13", session_slug="wave-3"
    )
    assert out["files"][0]["path"] == "sessions/2026-05-13-wave-3.md"
    assert out["files"][0]["frontmatter"]["date"]["equals"] == "2026-05-13"


def test_apply_recursive_expands_in_lists():
    config = {"in": ["a", "{today}", "c"]}
    out = interp.apply_recursive(config, today="2026-05-13", session_slug="x")
    assert out["in"] == ["a", "2026-05-13", "c"]


def test_apply_recursive_does_not_mutate_input():
    config = {"path": "{today}.md"}
    out = interp.apply_recursive(config, today="2026-05-13", session_slug="x")
    assert config == {"path": "{today}.md"}
    assert out == {"path": "2026-05-13.md"}


def test_apply_recursive_passes_through_non_string_scalars():
    config = {"must-exist": True, "depth": 3, "skip": None}
    out = interp.apply_recursive(config, today="2026-05-13", session_slug="x")
    assert out == config


def test_apply_recursive_raises_on_unresolved_with_path_context():
    config = {"files": [{"path": "{session-slug}.md"}]}
    with pytest.raises(interp.UnresolvedToken) as exc_info:
        interp.apply_recursive(config, today="2026-05-13", session_slug=None)
    assert "session-slug" in str(exc_info.value)


# ── {session-date} token (cross-midnight) ─────────────────────────────────


def test_expand_tokens_replaces_session_date():
    result = interp.expand_tokens(
        "sessions/{session-date}-{session-slug}.md",
        today="2026-06-12",
        session_slug="night-owl",
        session_date="2026-06-11",
    )
    assert result == "sessions/2026-06-11-night-owl.md"


def test_expand_tokens_raises_when_session_date_referenced_but_none():
    with pytest.raises(interp.UnresolvedToken) as exc_info:
        interp.expand_tokens(
            "{session-date}", today="2026-06-12", session_slug="x", session_date=None
        )
    assert "session-date" in str(exc_info.value)


def test_needs_session_context_true_when_session_date_referenced():
    assert interp.needs_session_context("sessions/{session-date}.md") is True


def test_apply_recursive_expands_session_date():
    config = {
        "files": [
            {
                "path": "sessions/{session-date}-{session-slug}.md",
                "frontmatter": {"date": {"equals": "{session-date}"}},
            }
        ]
    }
    out = interp.apply_recursive(
        config,
        today="2026-06-12",
        session_slug="night-owl",
        session_date="2026-06-11",
    )
    assert out["files"][0]["path"] == "sessions/2026-06-11-night-owl.md"
    assert out["files"][0]["frontmatter"]["date"]["equals"] == "2026-06-11"
