"""Settings from ~/.garmin-stats-skills/config.toml (created with defaults
on first use). Every key is optional."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from garmin_stats import paths

DEFAULT_TOML = """\
# garmin-stats-skills settings. Edit, then run: garmin-stats schedule
# (only needed after changing sync_interval_minutes).

# Where the local cache lives (SQLite).
db_path = "~/.garmin-stats-skills/garmin.db"

# How far back to keep history. Older days are backfilled gradually,
# backfill_per_run days per sync, to stay clear of Garmin's rate limits.
history_days = 365
backfill_per_run = 14

# Each sync re-fetches the most recent days (Garmin keeps revising them).
refresh_days = 3

# Background sync interval on macOS (launchd).
sync_interval_minutes = 60

# Minimum gap between requests to Garmin (random extra 0-50% is added).
# Keeps imports slow enough that Garmin doesn't block you. Don't go below 1.
request_delay_seconds = 1.0

# Keep Garmin's full raw payloads (sleep epochs, HR samples, splits, ...).
# ~50 KB per day. Turn off to keep only the summary tables.
store_raw = true
"""


@dataclass(frozen=True)
class Config:
    db_path: Path
    history_days: int = 365
    backfill_per_run: int = 14
    refresh_days: int = 3
    sync_interval_minutes: int = 60
    store_raw: bool = True
    request_delay_seconds: float = 1.0


def config_file() -> Path:
    return paths.home() / "config.toml"


def load() -> Config:
    f = config_file()
    if not f.exists():
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(DEFAULT_TOML)
    raw = tomllib.loads(f.read_text())
    db = Path(raw.get("db_path", str(paths.home() / "garmin.db"))).expanduser()
    if raw.get("db_path") == "~/.garmin-stats-skills/garmin.db":
        db = paths.home() / "garmin.db"  # follow GARMIN_STATS_HOME overrides
    return Config(
        db_path=db,
        history_days=max(1, int(raw.get("history_days", 365))),
        backfill_per_run=max(0, int(raw.get("backfill_per_run", 14))),
        refresh_days=max(1, int(raw.get("refresh_days", 3))),
        sync_interval_minutes=max(5, int(raw.get("sync_interval_minutes", 60))),
        store_raw=bool(raw.get("store_raw", True)),
        request_delay_seconds=max(0.5, float(raw.get("request_delay_seconds", 1.0))),
    )


def set_value(key: str, value: int | float | bool | str) -> None:
    """Rewrite one `key = value` line in config.toml, keeping comments."""
    import re

    load()  # make sure the file exists
    f = config_file()
    lit = (
        ("true" if value else "false")
        if isinstance(value, bool)
        else f'"{value}"'
        if isinstance(value, str)
        else str(value)
    )
    text = f.read_text()
    pattern = re.compile(rf"^{re.escape(key)}\s*=.*$", re.M)
    if pattern.search(text):
        text = pattern.sub(f"{key} = {lit}", text)
    else:
        text += f"\n{key} = {lit}\n"
    f.write_text(text)
