#!/usr/bin/env python3
"""PreToolUse hook for Bash — enforce shell hygiene rules.

Blocks (hard, exit 2):
  - Chained shells: unquoted `|`, `;`, `&&`, `||`, embedded newline
  - Heredoc append: `cat <<` / `cat <<-` (EXCEPT inside `$(cat <<...)`,
    which is the common `git commit -m "$(cat <<'EOF' ... EOF)"`
    convention)
  - Shell-side text append: `echo ... >>`, `printf ... >>`
  - `python -c "..."` blocks
  - `.venv/bin/<non-python-binary>` invocations (venv has Python only;
    invoking e.g. `.venv/bin/grep` ENOENTs at exec — use Read/Grep/Glob)

Quote-aware: pipes/semicolons/newlines/etc. inside single or double
quotes (e.g. inside a `jq` filter argument or a `$(cat <<EOF ... EOF)`
heredoc body nested in `"..."`) are NOT flagged. Backslash-escaped
operators (`\\;`, `\\|`) and line-continuations (`\\` followed by
newline) are also not flagged — the scanner consumes the escaped char
as one unit.

Bash treats an unquoted newline as a statement separator equivalent to
`;`, so it blocks on the same rule as `;` — running commands as
separate Bash calls keeps each invocation reviewable.

Exit 2 = block tool with stderr message visible to Claude.
Exit 0 = allow.
"""
import json
import re
import sys


def find_unquoted_operators(cmd: str) -> dict[str, bool]:
    """Scan cmd character by character, tracking quote/escape state.

    Returns a dict of which shell-control patterns appear OUTSIDE quotes.
    """
    found = {"pipe": False, "or": False, "and": False, "semi": False, "newline": False}

    in_single = False
    in_double = False
    i = 0
    n = len(cmd)
    while i < n:
        c = cmd[i]

        # Backslash escapes the next char in non-single-quoted contexts.
        # This also consumes `\<newline>` line continuations correctly.
        if c == "\\" and not in_single and i + 1 < n:
            i += 2
            continue

        if c == "'" and not in_double:
            in_single = not in_single
            i += 1
            continue

        if c == '"' and not in_single:
            in_double = not in_double
            i += 1
            continue

        if not in_single and not in_double:
            if c == "|":
                if i + 1 < n and cmd[i + 1] == "|":
                    found["or"] = True
                    i += 2
                    continue
                found["pipe"] = True
                i += 1
                continue
            if c == "&" and i + 1 < n and cmd[i + 1] == "&":
                found["and"] = True
                i += 2
                continue
            if c == ";":
                found["semi"] = True
                i += 1
                continue
            if c == "\n":
                found["newline"] = True
                i += 1
                continue

        i += 1

    return found


def find_unquoted_token_patterns(cmd: str) -> dict[str, bool]:
    """Sister to find_unquoted_operators: scan cmd for the three
    forbidden token patterns (cat-heredoc, echo/printf append,
    python -c) considering ONLY positions that are outside quotes and
    (for the cat-heredoc case) outside `$(...)` substitution.

    A regex-on-raw-string check fires false positives on literal
    substrings inside heredoc bodies (the `git commit -m "$(cat <<'EOF'
    ... EOF)"` convention) and quoted strings — making a quote-aware
    scanner necessary.

    Returns a dict with three booleans:
      - "cat_heredoc": `cat <<` (or `cat <<-`) outside quotes/substitution.
        ALLOWED inside `$(cat <<...)` — the commit-message-via-heredoc
        convention.
      - "echo_append": `echo|printf ... >> file` outside quotes.
      - "python_dash_c": `python[suffix] -c` outside quotes.

    The scanner mirrors find_unquoted_operators's quote/escape state
    machine and additionally tracks `$(` depth to support the heredoc-
    in-substitution exemption.
    """
    found = {"cat_heredoc": False, "echo_append": False, "python_dash_c": False}

    in_single = False
    in_double = False
    # Depth of unmatched `$(` opens — heredocs nested inside count as
    # "in substitution" (the allowed pattern).
    sub_depth = 0
    i = 0
    n = len(cmd)
    # Pre-compile the three token regexes for use at each candidate
    # position. Anchoring at `i` is done by `re.match`.
    cat_re = re.compile(r"\bcat\s+<<-?")
    # `echo|printf` followed by anything that isn't a `|` (the existing
    # quote-aware pipe check handles real pipes), then `>> path`.
    echo_re = re.compile(r"\b(?:echo|printf)\b[^|]*?>>\s*\S")
    py_re = re.compile(r"\bpython\S*\s+-c\b")

    def _try_match_at(idx: int) -> None:
        """Test the three token regexes anchored at position idx; record
        a hit only if outside quotes and outside `$(cat <<...)` for the
        cat-heredoc pattern."""
        if cat_re.match(cmd, idx) and sub_depth == 0:
            found["cat_heredoc"] = True
        if echo_re.match(cmd, idx):
            found["echo_append"] = True
        if py_re.match(cmd, idx):
            found["python_dash_c"] = True

    while i < n:
        c = cmd[i]

        if c == "\\" and not in_single and i + 1 < n:
            i += 2
            continue

        if c == "'" and not in_double:
            in_single = not in_single
            i += 1
            continue

        if c == '"' and not in_single:
            in_double = not in_double
            i += 1
            continue

        # Track `$(` open / `)` close to give cat-heredoc its exemption.
        # Both branches gate on `not in_single and not in_double` so the
        # depth tracker stays symmetric: inside double-quotes the depth
        # doesn't change at all (any `"$(...)"` is invisible to it), so
        # a bare `cat <<` AFTER a closing `)"` doesn't get falsely
        # exempted by an inflated depth value.
        #
        # The cat-heredoc-inside-double-quotes case (`git commit -m
        # "$(cat <<'EOF'...EOF)"`) is still allowed: the cat-heredoc
        # check itself fires only when `not in_single and not in_double`
        # (see _try_match_at call site), so the entire heredoc body is
        # already exempt by virtue of being inside `"..."`. The depth
        # tracker is purely for the OUTSIDE-quotes case.
        if (
            not in_single
            and not in_double
            and c == "$"
            and i + 1 < n
            and cmd[i + 1] == "("
        ):
            sub_depth += 1
            i += 2
            continue
        if not in_single and not in_double and c == ")" and sub_depth > 0:
            sub_depth -= 1
            i += 1
            continue

        if not in_single and not in_double:
            _try_match_at(i)

        i += 1

    return found


# `.venv/bin/<non-python-binary>` denylist — these binaries don't exist
# in a Python virtualenv (the venv has python/pip/pytest/etc., not the
# Unix coreutils). Invoking them via `.venv/bin/` ENOENTs at exec. The
# muscle-memory shape is "use venv binary to avoid PATH variance"; for
# non-Python tools that's wrong AND fails. Allowed venv binaries
# (python, pip, pytest, etc.) do not match this denylist.
_VENV_NONPY_RE = re.compile(
    r"(?:^|\s)\S*\.venv/bin/(grep|find|head|tail|cat|sort|uniq|cut|wc|awk|sed|comm|diff|tr|ls)(?=\s|$)"
)


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool = payload.get("tool_name") or payload.get("tool")
    if tool != "Bash":
        sys.exit(0)

    cmd = (payload.get("tool_input") or {}).get("command") or ""

    violations = []

    ops = find_unquoted_operators(cmd)
    if ops["pipe"]:
        violations.append("`|` pipe chain — split into separate Bash calls or write a helper script in scripts/")
    if ops["or"]:
        violations.append("`||` chain — run commands separately (one Bash call each)")
    if ops["and"]:
        violations.append("`&&` chain — run commands separately (one Bash call each)")
    if ops["semi"]:
        violations.append("`;` command separator — run commands separately (one Bash call each)")
    if ops["newline"]:
        violations.append("embedded newline (statement separator) — run commands separately (one Bash call each); for `cd <dir>` + cmd, use `git -C <dir>` or absolute paths")

    # Quote-aware token-pattern scans below replace naive regex-on-raw-
    # string searches that false-positive on literal substrings inside
    # heredoc bodies (`git commit -m "$(cat <<'EOF' ... EOF)"`) or
    # inside quoted strings (`echo 'do not use python -c'`).
    tokens = find_unquoted_token_patterns(cmd)
    if tokens["cat_heredoc"]:
        violations.append("`cat <<` heredoc — use the Write or Edit tool instead (or wrap in `$(cat <<...)` for substitution)")
    if tokens["echo_append"]:
        violations.append("`echo >>` / `printf >>` — use the Edit tool to append")
    if tokens["python_dash_c"]:
        violations.append("`python -c` — write a helper to scripts/ and run it as a file")

    # `.venv/bin/<non-python-binary>` — venv has Python only.
    if _VENV_NONPY_RE.search(cmd):
        violations.append(
            "`.venv/bin/<non-python-binary>` invocation — the venv has Python only, this ENOENTs at exec. "
            "Use Read / Grep / Glob tools (if truly required, drop the `.venv/bin/` prefix — but reconsider first)"
        )

    if violations:
        msg = "Shell hygiene violation:\n" + "\n".join(f"  - {v}" for v in violations)
        msg += "\n\nReference: tier-1/shell-hygiene module."
        print(msg, file=sys.stderr)
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
