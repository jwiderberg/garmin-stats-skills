"""Packaging invariants that Cowork / Claude Code rely on."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(p):
    return json.loads((ROOT / p).read_text())


def test_names_match_everywhere():
    plugin = load(".claude-plugin/plugin.json")
    market = load(".claude-plugin/marketplace.json")
    assert plugin["name"] == market["name"] == market["plugins"][0]["name"] == "garmin-stats-skills"
    assert market["plugins"][0]["source"] == "./"


def test_versions_agree():
    plugin = load(".claude-plugin/plugin.json")["version"]
    py = re.search(
        r'^version = "([^"]+)"', (ROOT / "pyproject.toml").read_text(), re.MULTILINE
    ).group(1)
    init = re.search(
        r'__version__ = "([^"]+)"', (ROOT / "src/garmin_stats/__init__.py").read_text()
    ).group(1)
    assert plugin == py == init


def test_mcp_json_points_at_installer_launcher():
    cfg = load(".mcp.json")["mcpServers"]["garmin"]
    script = " ".join(cfg["args"])
    assert ".garmin-stats-skills/run-mcp.sh" in script
    assert "run-mcp.sh" in (ROOT / "install.sh").read_text()
    # Claude expands ${VAR}; the shell snippet must not use brace syntax.
    assert "${" not in script


def test_no_top_level_bin_dir():
    """Cowork refuses to install a repo with a top-level bin/ directory."""
    assert not (ROOT / "bin").exists()


def test_skill_frontmatter():
    for skill in (ROOT / "skills").iterdir():
        text = (skill / "SKILL.md").read_text()
        m = re.match(r"---\nname: (.+)\ndescription: (.+?)\n---\n", text, re.DOTALL)
        assert m, f"{skill.name}: bad frontmatter"
        assert m.group(1).strip() == skill.name
        assert len(m.group(2)) < 1024
