"""Build the Claude plugin as a zip for Cowork's Customize → Plugins →
Upload plugin. The plugin files ship inside the wheel (pyproject
force-include) so the zip always matches the installed helper's version;
in a source checkout they're read from the repo root."""

from __future__ import annotations

import zipfile
from pathlib import Path

from garmin_stats import paths

ZIP_NAME = "Garmin Stats.zip"
PLUGIN_ITEMS = (".claude-plugin/plugin.json", ".mcp.json", "skills", "README.md", "LICENSE")


def plugin_root() -> Path:
    bundled = Path(__file__).parent / "plugin"
    if (bundled / ".claude-plugin" / "plugin.json").exists():
        return bundled
    repo = Path(__file__).resolve().parents[2]
    if (repo / ".claude-plugin" / "plugin.json").exists():
        return repo
    raise FileNotFoundError("Plugin files not found in this installation.")


def build(out_dir: Path | None = None) -> Path:
    root = plugin_root()
    out_dir = out_dir or paths.home()
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / ZIP_NAME
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for item in PLUGIN_ITEMS:
            src = root / item
            if src.is_file():
                z.write(src, item)
            elif src.is_dir():
                for f in sorted(src.rglob("*")):
                    if f.is_file() and "__pycache__" not in f.parts:
                        z.write(f, f.relative_to(root).as_posix())
    return out
