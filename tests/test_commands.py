# tests/test_commands.py
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _frontmatter(text: str) -> str:
    assert text.startswith("---")
    return text.split("---", 2)[1]


def test_begin_session_command_has_description():
    text = (ROOT / "commands" / "begin-session.md").read_text()
    assert "description:" in _frontmatter(text)


def test_debrief_command_has_description():
    text = (ROOT / "commands" / "debrief.md").read_text()
    assert "description:" in _frontmatter(text)


def test_debrief_attributes_ended_at_to_sessionend_not_stop():
    text = (ROOT / "commands" / "debrief.md").read_text()
    assert "SessionEnd" in text
    assert "Stop hook fills" not in text
