"""Where garmin-stats keeps its state. Everything lives under one
directory (default ~/.garmin-stats-skills, override GARMIN_STATS_HOME)
so uninstalling is a single rm -rf."""

from __future__ import annotations

import os
from pathlib import Path


def home() -> Path:
    return Path(os.environ.get("GARMIN_STATS_HOME", "~/.garmin-stats-skills")).expanduser()


def token_dir() -> Path:
    return home() / "tokens"


def token_file() -> Path:
    return token_dir() / "garmin_tokens.json"


def cache_dir() -> Path:
    return home() / "cache"


def secure(path: Path) -> None:
    """Owner-only permissions: the token file is a long-lived credential."""
    if path.is_dir():
        path.chmod(0o700)
        for child in path.iterdir():
            if child.is_file():
                child.chmod(0o600)
    elif path.exists():
        path.chmod(0o600)
