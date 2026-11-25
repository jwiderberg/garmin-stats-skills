import asyncio
from datetime import date

import pytest

from garmin_stats import client, server


@pytest.fixture()
def fake_data(monkeypatch):
    class Fake:
        def get_stats(self, d):
            return {"calendarDate": d, "totalSteps": 5000}

        def get_sleep_data(self, d):
            return {
                "dailySleepDTO": {
                    "calendarDate": d,
                    "sleepTimeSeconds": 25200,
                    "sleepScores": {"overall": {"value": 80}},
                }
            }

        def get_hrv_data(self, d):
            return {"hrvSummary": {"lastNightAvg": 50, "status": "BALANCED"}}

        def get_full_name(self):
            return "Test User"

    data = client.GarminData(factory=Fake, today=lambda: date(2026, 5, 10))
    monkeypatch.setattr(server, "data", data)
    return data


def test_all_tools_registered():
    names = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert {
        "garmin_status",
        "sleep",
        "daily_range",
        "activities",
        "training_status",
        "performance",
        "garmin_raw",
    } <= names


def test_daily_range_merges_parts(fake_data):
    rows = server.daily_range("2026-05-08", "2026-05-10")
    assert [r["date"] for r in rows] == ["2026-05-08", "2026-05-09", "2026-05-10"]
    r = rows[0]
    assert r["steps"] == 5000 and r["sleep_score"] == 80 and r["sleep_min"] == 420
    assert r["hrv_last_night_ms"] == 50


def test_daily_range_include_subset(fake_data):
    rows = server.daily_range("2026-05-10", "today", include=["sleep"])
    assert "steps" not in rows[0] and rows[0]["sleep_score"] == 80


def test_range_cap(fake_data):
    with pytest.raises(ValueError, match="max 31"):
        server.daily_range("2026-01-01", "2026-05-10")


def test_raw_is_allowlisted(fake_data):
    with pytest.raises(ValueError, match="not allowed"):
        server.garmin_raw("upload_activity", ["x"])
    with pytest.raises(ValueError, match="not allowed"):
        server.garmin_raw("delete_blood_pressure", [])
    assert all(m.startswith("get_") for m in server.RAW_ALLOWED)


def test_status_without_login():
    assert server.garmin_status()["logged_in"] is False
