"""Regression guard: the masterbook tree contains zero publishability violations."""
import sys
from pathlib import Path

# scripts/ is the home of the audit module.
SCRIPTS = Path(__file__).resolve().parent.parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

from publishability_audit import (  # noqa: E402
    DEFAULT_GLOBS,
    audit_directory,
    scan_text,
)

MASTERBOOK = Path(__file__).resolve().parent.parent


def test_masterbook_tree_has_no_publishability_violations():
    """tier-1, tier-2, helpers, commands, substrate/*/module.md must be clean."""
    violations = audit_directory(MASTERBOOK, glob_patterns=DEFAULT_GLOBS)
    assert violations == [], (
        "Publishability violations found:\n"
        + "\n".join(
            f"  {v.file_path.relative_to(MASTERBOOK)}:{v.line_number}: "
            f"{v.pattern_name}: {v.matched_text}"
            for v in violations
        )
    )


def test_assemble_banner_is_clean():
    """The BANNER constant in assemble.py is emitted into every assembled CLAUDE.md.

    It must not contain any local-path or personal-info leak. Direct text scan
    rather than AST extraction — we just want to know if any violation appears
    in the file's text region around BANNER.
    """
    assemble_py = MASTERBOOK / "tools" / "assemble.py"
    text = assemble_py.read_text(encoding="utf-8")
    violations = scan_text(text)
    assert violations == [], (
        "Publishability violations in assemble.py:\n"
        + "\n".join(
            f"  line {v.line_number}: {v.pattern_name}: {v.matched_text}"
            for v in violations
        )
    )
