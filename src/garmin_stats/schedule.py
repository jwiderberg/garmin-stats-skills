"""Hourly background sync on macOS via a per-user launchd agent."""

from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

from garmin_stats import paths

LABEL = "com.garmin-stats-skills.sync"


def plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def _exe() -> str:
    return shutil.which("garmin-stats") or str(Path(sys.argv[0]).resolve())


def install(interval_minutes: int) -> Path:
    p = plist_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    log = str(paths.home() / "sync.log")
    spec = {
        "Label": LABEL,
        "ProgramArguments": [_exe(), "sync", "--quiet"],
        "EnvironmentVariables": {"GARMIN_STATS_HOME": str(paths.home())},
        "StartInterval": interval_minutes * 60,
        "RunAtLoad": False,  # setup runs the first import itself, in the foreground
        "ProcessType": "Background",
        "LowPriorityIO": True,
        "StandardOutPath": log,
        "StandardErrorPath": log,
    }
    uid = os.getuid()
    subprocess.run(["launchctl", "bootout", f"gui/{uid}/{LABEL}"], capture_output=True)
    with p.open("wb") as f:
        plistlib.dump(spec, f)
    subprocess.run(
        ["launchctl", "bootstrap", f"gui/{uid}", str(p)], check=True, capture_output=True
    )
    return p


def remove() -> bool:
    p = plist_path()
    subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}/{LABEL}"], capture_output=True)
    existed = p.exists()
    p.unlink(missing_ok=True)
    return existed


def is_installed() -> bool:
    return plist_path().exists()
