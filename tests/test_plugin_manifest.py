# tests/test_plugin_manifest.py
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_plugin_manifest_required_fields():
    manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    assert manifest["name"] == "recordkeeper"
    assert manifest["description"]
    assert manifest["version"]


def test_marketplace_lists_recordkeeper():
    mkt = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
    assert mkt["version"] == 1
    names = [p["name"] for p in mkt["plugins"]]
    assert "recordkeeper" in names
    assert all(p.get("source") for p in mkt["plugins"])
