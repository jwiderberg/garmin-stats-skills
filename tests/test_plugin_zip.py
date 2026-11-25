import json
import zipfile

from garmin_stats import paths, plugin_zip


def test_zip_is_an_uploadable_plugin(tmp_path):
    out = plugin_zip.build(tmp_path)
    assert out.name == "Garmin-Stats.zip"
    with zipfile.ZipFile(out) as z:
        names = set(z.namelist())
        assert {".claude-plugin/plugin.json", ".mcp.json", "skills/garmin-stats/SKILL.md"} <= names
        # a plugin, not a marketplace; and Cowork rejects a top-level bin/
        assert ".claude-plugin/marketplace.json" not in names
        assert not any(n.startswith("bin/") for n in names)
        assert json.loads(z.read(".claude-plugin/plugin.json"))["name"] == "garmin-stats-skills"


def test_default_location_is_app_home():
    assert plugin_zip.build().parent == paths.home()
