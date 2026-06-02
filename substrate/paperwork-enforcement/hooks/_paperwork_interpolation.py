"""Token interpolation for paperwork.yaml.

Expands {today} and {session-slug} in any string value. The Stop hook calls
apply_recursive once at load time so predicates see resolved strings only.
"""
from __future__ import annotations

import re
from typing import Any


class UnresolvedToken(Exception):
    """Raised when a string references a token whose value is None at expansion time."""


_TOKEN_RE = re.compile(r"\{(today|session-slug)\}")


def expand_tokens(s: str, *, today: str | None, session_slug: str | None) -> str:
    """Expand {today} and {session-slug} in s. Unknown tokens are left alone.

    Raises UnresolvedToken if a known token is referenced but its value is None.
    """
    def replace(match: re.Match[str]) -> str:
        token = match.group(1)
        if token == "today":
            if today is None:
                raise UnresolvedToken("today")
            return today
        if token == "session-slug":
            if session_slug is None:
                raise UnresolvedToken("session-slug")
            return session_slug
        return match.group(0)  # unreachable given the regex
    return _TOKEN_RE.sub(replace, s)


def needs_session_context(s: str) -> bool:
    """True iff s references any token whose resolution depends on session-paperwork context.

    Both {today} and {session-slug} depend on the substrate being live; {today} is
    technically derivable from system time, but a config that depends on it implies
    the substrate's session-context model is active.
    """
    return bool(_TOKEN_RE.search(s))


def apply_recursive(
    obj: Any, *, today: str | None, session_slug: str | None
) -> Any:
    """Walk obj recursively, expanding tokens in every string value.

    Returns a new structure; the input is not mutated. Raises UnresolvedToken
    when any referenced token has a None value.
    """
    if isinstance(obj, str):
        return expand_tokens(obj, today=today, session_slug=session_slug)
    if isinstance(obj, dict):
        return {
            k: apply_recursive(v, today=today, session_slug=session_slug)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [
            apply_recursive(item, today=today, session_slug=session_slug)
            for item in obj
        ]
    return obj
