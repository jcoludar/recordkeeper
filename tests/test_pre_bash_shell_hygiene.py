"""Tests for pre_bash_shell_hygiene.find_unquoted_operators.

Run from repo root:
    .venv/bin/python -m pytest .claude/hooks/test_pre_bash_shell_hygiene.py -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pre_bash_shell_hygiene import (  # noqa: E402
    find_unquoted_operators,
    find_unquoted_token_patterns,
    _VENV_NONPY_RE,
)


def test_simple_command_has_no_operators():
    ops = find_unquoted_operators("ls")
    assert ops == {"pipe": False, "or": False, "and": False, "semi": False, "newline": False}


def test_unquoted_and_is_flagged():
    assert find_unquoted_operators("ls && pwd")["and"] is True


def test_unquoted_or_is_flagged():
    assert find_unquoted_operators("ls || pwd")["or"] is True


def test_unquoted_pipe_is_flagged():
    assert find_unquoted_operators("ls | grep foo")["pipe"] is True


def test_unquoted_semicolon_is_flagged():
    assert find_unquoted_operators("ls; pwd")["semi"] is True


def test_pipe_in_single_quotes_is_not_flagged():
    # JQ filter: '.foo | .bar'
    assert find_unquoted_operators("jq '.foo | .bar' file")["pipe"] is False


def test_pipe_in_double_quotes_is_not_flagged():
    assert find_unquoted_operators('jq ".foo | .bar" file')["pipe"] is False


def test_semicolon_in_single_quotes_is_not_flagged():
    assert find_unquoted_operators("find . -name 'a;b'")["semi"] is False


def test_escaped_semicolon_is_not_flagged():
    # find -exec ... \;  (the backslash escapes ;)
    assert find_unquoted_operators("find . -exec rm {} \\;")["semi"] is False


def test_escaped_pipe_is_not_flagged():
    assert find_unquoted_operators("echo foo \\| bar")["pipe"] is False


def test_double_pipe_is_or_not_pipe():
    ops = find_unquoted_operators("ls || pwd")
    assert ops["or"] is True
    assert ops["pipe"] is False


def test_awk_program_with_pipes_is_not_flagged():
    cmd = "awk 'BEGIN { FS=\"|\" } { print $1 }' /tmp/x"
    assert find_unquoted_operators(cmd)["pipe"] is False


def test_pipe_inside_quotes_then_unquoted_pipe_flags_unquoted():
    cmd = "jq '.a | .b' x | head"
    ops = find_unquoted_operators(cmd)
    assert ops["pipe"] is True


def test_embedded_newline_is_flagged_as_statement_separator():
    # Bash treats unquoted \n as equivalent to `;` — should block.
    cmd = "ls\npwd"
    assert find_unquoted_operators(cmd)["newline"] is True


def test_newline_inside_single_quotes_is_not_flagged():
    cmd = "echo 'multi\nline'"
    assert find_unquoted_operators(cmd)["newline"] is False


def test_backslash_newline_line_continuation_is_not_flagged():
    # `\` followed by newline is a line-continuation — one logical command.
    cmd = "ls \\\n  -la"
    assert find_unquoted_operators(cmd)["newline"] is False


def test_cat_heredoc_outside_substitution_is_flagged():
    cmd = "cat <<EOF\nhello\nEOF"
    assert find_unquoted_token_patterns(cmd)["cat_heredoc"] is True


def test_cat_heredoc_inside_dollar_paren_substitution_is_exempt():
    # The commit-message-via-heredoc convention:
    #   git commit -m "$(cat <<'EOF' ... EOF)"
    # The body inside `"..."` is already exempted by quote-awareness;
    # but a bare `$(cat <<...)` should also be exempt.
    cmd = "git commit -F <(cat $(cat <<'EOF'\nmsg\nEOF\n))"
    assert find_unquoted_token_patterns(cmd)["cat_heredoc"] is False


def test_cat_heredoc_inside_double_quoted_substitution_is_exempt():
    # The common case: `git commit -m "$(cat <<'EOF' ... EOF)"`.
    # Everything inside the outer `"..."` is invisible to the token
    # scanner (quote-aware), so cat-heredoc must NOT be flagged.
    cmd = "git commit -m \"$(cat <<'EOF'\nmessage body\nEOF\n)\""
    assert find_unquoted_token_patterns(cmd)["cat_heredoc"] is False


def test_python_dash_c_inside_single_quotes_is_not_flagged():
    # Quote-aware loosening: a literal `python -c` substring inside
    # single-quotes is documentation, not an invocation.
    cmd = "echo 'do not use python -c here'"
    assert find_unquoted_token_patterns(cmd)["python_dash_c"] is False


def test_python_dash_c_outside_quotes_is_flagged():
    cmd = "python -c 'print(1)'"
    assert find_unquoted_token_patterns(cmd)["python_dash_c"] is True


def test_venv_bin_grep_is_flagged():
    # .venv has Python only — grep via .venv/bin/grep ENOENTs.
    assert _VENV_NONPY_RE.search(".venv/bin/grep -r foo .") is not None


def test_venv_bin_python_is_not_flagged():
    # python/pip/pytest are real venv binaries — must NOT match.
    assert _VENV_NONPY_RE.search(".venv/bin/python script.py") is None


def test_venv_bin_pytest_is_not_flagged():
    assert _VENV_NONPY_RE.search(".venv/bin/pytest tests/") is None
