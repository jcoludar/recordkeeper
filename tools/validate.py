"""Self-validate the recordkeeper tree.

Every check returns a `list[str]` of problems (empty == clean) rather than raising
on the first fault. This is deliberate: a fail-fast validator masks latent failures
behind whichever one it hits first, so real problems get peeled off one run at a
time. Collecting all faults means one run gives the whole health picture.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Reuse parse_frontmatter from assemble.py.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from assemble import parse_frontmatter, FrontmatterError, _module_id


# Substrate modules use a leaner schema; tier-1/tier-2 modules must carry the
# full 8-field convention (the three list fields can be empty, but must be present).
# Substrate module.md files are also reference-length (a whole substrate's contract,
# predicate vocabulary, and enforcement flow), so they get their own, looser
# per_substrate_module_words budget rather than the tier per_module_words budget.
REQUIRED_MODULE_FIELDS = {"id", "name", "tier", "default", "summary"}
REQUIRED_TIER_MODULE_FIELDS = REQUIRED_MODULE_FIELDS | {
    "applies_when",
    "conflicts_with",
    "requires",
}


def validate_module(
    path: Path,
    *,
    masterbook_root: Path,
    max_words: int,
    required_fields: set[str] = REQUIRED_MODULE_FIELDS,
) -> list[str]:
    """Frontmatter parses; required fields present; id matches path; length under budget."""
    try:
        fm, body = parse_frontmatter(path.read_text())
    except FrontmatterError as exc:
        # Nothing else is checkable without frontmatter.
        return [f"{path}: {exc}"]

    errors: list[str] = []

    missing = required_fields - set(fm)
    if missing:
        errors.append(f"{path}: missing required frontmatter fields: {sorted(missing)}")

    if "id" in fm:
        expected_id = _module_id(path, masterbook_root)
        if fm["id"] != expected_id:
            errors.append(f"{path}: id '{fm['id']}' does not match path '{expected_id}'")

    n = len(body.split())
    if n > max_words:
        errors.append(f"{path}: body is {n} words; exceeds per-module budget of {max_words}")

    return errors


_INDEX_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def validate_index(masterbook_root: Path) -> list[str]:
    """INDEX.md references every module file and no orphans."""
    index = masterbook_root / "INDEX.md"
    if not index.is_file():
        return [f"INDEX.md not found at {index}"]

    text = index.read_text()
    # Strip any `#fragment` (and `?query`) before removing the `.md` suffix, or a
    # link like `tier-1/foo.md#section` would never match the module id `tier-1/foo`.
    referenced = set(
        m.group(2).split("#", 1)[0].split("?", 1)[0].removesuffix(".md")
        for m in _INDEX_LINK_RE.finditer(text)
    )

    actual: set[str] = set()
    for tier_dir in ("tier-1", "tier-2"):
        for p in (masterbook_root / tier_dir).glob("*.md"):
            actual.add(f"{tier_dir}/{p.stem}")

    errors: list[str] = []

    missing = actual - referenced
    if missing:
        errors.append(f"INDEX missing references: {sorted(missing)}")

    orphans = referenced - actual - {"parking-lot"}
    orphans = {o for o in orphans if o.startswith(("tier-1/", "tier-2/"))}
    if orphans:
        errors.append(f"INDEX has orphan references: {sorted(orphans)}")

    return errors


import ast
import json


def validate_settings_fragments(masterbook_root: Path) -> list[str]:
    """Top-level settings-fragments/*.json AND substrate/*/settings-fragment.json parse as JSON."""
    candidates: list[Path] = []
    frag_dir = masterbook_root / "settings-fragments"
    if frag_dir.is_dir():
        candidates.extend(frag_dir.glob("*.json"))
    substrate_root = masterbook_root / "substrate"
    if substrate_root.is_dir():
        for sub_dir in substrate_root.iterdir():
            if sub_dir.is_dir():
                frag = sub_dir / "settings-fragment.json"
                if frag.is_file():
                    candidates.append(frag)
    errors: list[str] = []
    for p in sorted(candidates):
        try:
            json.loads(p.read_text())
        except json.JSONDecodeError as exc:
            errors.append(f"{p}: invalid JSON: {exc}")
    return errors


def validate_hooks(masterbook_root: Path) -> list[str]:
    """Each .py file under baseline-hooks/, hooks/, and substrate/*/hooks/ parses with `ast.parse`.

    `baseline-hooks/` is the assembler's always-on hook source; `hooks/` is the
    Claude Code plugin's hook surface. Both are syntax-checked.
    """
    candidates: list[Path] = []
    for top in ("baseline-hooks", "hooks"):
        hooks_dir = masterbook_root / top
        if hooks_dir.is_dir():
            candidates.extend(hooks_dir.glob("*.py"))
    substrate_root = masterbook_root / "substrate"
    if substrate_root.is_dir():
        for sub_dir in substrate_root.iterdir():
            if sub_dir.is_dir():
                sub_hooks = sub_dir / "hooks"
                if sub_hooks.is_dir():
                    candidates.extend(sub_hooks.glob("*.py"))
    errors: list[str] = []
    for p in sorted(candidates):
        try:
            ast.parse(p.read_text())
        except SyntaxError as exc:
            errors.append(f"{p}: syntax error: {exc}")
    return errors


_COMMAND_FILENAME_RE = re.compile(r"^[a-z][a-z0-9-]*\.md$")


def validate_commands(masterbook_root: Path) -> list[str]:
    """Each .md under commands/ and substrate/*/commands/ has well-formed frontmatter.

    Requirements per command file:
      - filename matches [a-z][a-z0-9-]*\\.md
      - frontmatter parses; `description:` field is a non-empty single line, <= 100 chars
      - body is non-empty after frontmatter strip
    """
    candidates: list[Path] = []
    top_dir = masterbook_root / "commands"
    if top_dir.is_dir():
        candidates.extend(top_dir.glob("*.md"))
    substrate_root = masterbook_root / "substrate"
    if substrate_root.is_dir():
        for sub_dir in substrate_root.iterdir():
            if sub_dir.is_dir():
                sub_cmds = sub_dir / "commands"
                if sub_cmds.is_dir():
                    candidates.extend(sub_cmds.glob("*.md"))

    errors: list[str] = []
    for p in sorted(candidates):
        if not _COMMAND_FILENAME_RE.match(p.name):
            errors.append(
                f"{p}: invalid filename '{p.name}' (must match [a-z][a-z0-9-]*\\.md)"
            )
            continue
        try:
            fm, body = parse_frontmatter(p.read_text())
        except FrontmatterError as exc:
            errors.append(f"{p}: {exc}")
            continue
        desc = fm.get("description")
        if not isinstance(desc, str) or not desc.strip():
            errors.append(f"{p}: missing or empty `description:` frontmatter field")
            continue
        desc_clean = desc.strip()
        if "\n" in desc_clean or len(desc_clean) > 100:
            errors.append(f"{p}: `description:` must be a single line, <= 100 chars")
        if not body.strip():
            errors.append(f"{p}: empty body")
    return errors


import argparse


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the recordkeeper tree.")
    parser.add_argument("masterbook_root", type=Path)
    args = parser.parse_args(argv)

    root: Path = args.masterbook_root.resolve()

    # Read per-module budget from VERSION.
    version_text = (root / "VERSION").read_text()
    version_fm, _ = parse_frontmatter(version_text)
    length_budget = version_fm.get("length_budget", {})
    per_module = int(length_budget.get("per_module_words", 600))
    # Substrate module.md docs are reference-length (whole-substrate contracts), longer
    # than tier-1/tier-2 principle modules; fall back to per_module if unset.
    per_substrate_module = int(length_budget.get("per_substrate_module_words", per_module))

    errors: list[str] = []

    for tier_dir in ("tier-1", "tier-2"):
        for p in sorted((root / tier_dir).glob("*.md")):
            errors.extend(
                validate_module(
                    p, masterbook_root=root, max_words=per_module,
                    required_fields=REQUIRED_TIER_MODULE_FIELDS,
                )
            )

    # Substrates are first-class modules with frontmatter; walk them too.
    substrate_root = root / "substrate"
    if substrate_root.is_dir():
        for sub_dir in sorted(p for p in substrate_root.iterdir() if p.is_dir()):
            mod = sub_dir / "module.md"
            if mod.is_file():
                errors.extend(
                    validate_module(mod, masterbook_root=root, max_words=per_substrate_module)
                )

    errors.extend(validate_index(root))
    errors.extend(validate_settings_fragments(root))
    errors.extend(validate_hooks(root))
    errors.extend(validate_commands(root))

    if errors:
        for e in errors:
            print(f"VALIDATION ERROR: {e}", file=sys.stderr)
        return 1

    print(f"recordkeeper OK: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
