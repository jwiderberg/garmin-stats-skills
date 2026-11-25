import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))  # for `from fakes import ...`


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Every test gets its own GARMIN_STATS_HOME — never the real one — and
    never touches launchd."""
    monkeypatch.setenv("GARMIN_STATS_HOME", str(tmp_path / "gs-home"))
    from garmin_stats import schedule, sync

    monkeypatch.setattr(schedule, "install", lambda mins: None)
    monkeypatch.setattr(schedule, "is_installed", lambda: False)
    monkeypatch.setattr(sync, "PAUSE_S", 0)
    return tmp_path / "gs-home"
