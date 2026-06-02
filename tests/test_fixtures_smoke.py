"""Smoke test that fixtures load."""
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def test_mini_masterbook_exists():
    assert (FIXTURES / "mini_masterbook" / "VERSION").exists()
    assert (FIXTURES / "mini_masterbook" / "tier-1" / "example.md").exists()


def test_sample_project_exists():
    assert (FIXTURES / "sample_project" / "CLAUDE.source.md").exists()
