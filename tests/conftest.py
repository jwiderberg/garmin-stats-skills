import pytest


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Every test gets its own GARMIN_STATS_HOME — never touch the real one."""
    monkeypatch.setenv("GARMIN_STATS_HOME", str(tmp_path / "gs-home"))
    return tmp_path / "gs-home"
