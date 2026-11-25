import asyncio
from datetime import date

import pytest
from fakes import FakeGarmin

from garmin_stats import config, server, sync


@pytest.fixture()
def synced():
    sync.run(config.load(), garmin=FakeGarmin(), today=date.today(), days=3)


def test_tools():
    names = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert names == {
        "garmin_status",
        "garmin_query",
        "garmin_raw",
        "garmin_sync_now",
        "garmin_connect",
    }


def test_status_on_empty_cache():
    s = server.garmin_status()
    assert s["signed_in"] is False and s["coverage"]["daily"]["rows"] == 0
    assert "sleep_score" in s["schema"]["daily"]


def test_query(synced):
    r = server.garmin_query("SELECT date, steps FROM daily ORDER BY date")
    assert r["columns"] == ["date", "steps"] and len(r["rows"]) == 3 and not r["truncated"]


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM daily",
        "UPDATE daily SET steps=0",
        "DROP TABLE daily",
        "SELECT 1; DELETE FROM daily",
        "PRAGMA table_info(daily)",
        "WITH x AS (SELECT 1) INSERT INTO daily(date) SELECT 1",
        "ATTACH DATABASE '/tmp/x' AS x",
    ],
)
def test_query_rejects_writes(synced, sql):
    with pytest.raises(ValueError):
        server.garmin_query(sql)


def test_query_connection_is_readonly_even_if_regex_missed(synced):
    import sqlite3

    conn = server._conn()
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("INSERT INTO daily(date) VALUES ('x')")


def test_raw(synced):
    today = date.today().isoformat()
    assert server.garmin_raw(today, "sleep")["sleepLevels"]
    assert "error" in server.garmin_raw("1999-01-01", "sleep")
