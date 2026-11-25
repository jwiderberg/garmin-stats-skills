from dataclasses import replace
from datetime import date

from fakes import FakeGarmin

from garmin_stats import config, db, sync

TODAY = date(2026, 5, 20)


def cfg(**kw):
    return replace(config.load(), **kw)


def rows(c, sql):
    conn = db.connect(c.db_path)
    try:
        return [tuple(r) for r in conn.execute(sql)]
    finally:
        conn.close()


def test_first_run_refreshes_and_backfills():
    c = cfg(refresh_days=2, backfill_per_run=3, history_days=30)
    r = sync.run(c, garmin=FakeGarmin(), today=TODAY)
    assert r["ok"] and (r["refreshed"], r["backfilled"]) == (2, 3)
    dates = [d for (d,) in rows(c, "SELECT date FROM daily ORDER BY date")]
    assert (
        dates
        == ["2026-05-15", "2026-05-16", "2026-05-17", "2026-05-18", "2026-05-19", "2026-05-20"][1:]
    )  # 5 days: 05-16..05-20
    d = rows(
        c,
        "SELECT steps, sleep_score, hrv_last_night_ms, training_status, acute_load_7d,"
        " readiness_score FROM daily WHERE date='2026-05-20'",
    )[0]
    assert d == (8000, 81, 55.0, "RECOVERY", 150.0, None)  # readiness unsupported → NULL


def test_backfill_continues_where_it_left_off():
    c = cfg(refresh_days=1, backfill_per_run=2, history_days=10)
    sync.run(c, garmin=FakeGarmin(), today=TODAY)
    sync.run(c, garmin=FakeGarmin(), today=TODAY)
    n = rows(c, "SELECT count(*) FROM daily")[0][0]
    assert n == 5  # 1 refreshed + 2 + 2 backfilled


def test_backfill_stops_at_history_limit_and_prunes():
    c = cfg(refresh_days=1, backfill_per_run=50, history_days=4)
    sync.run(c, garmin=FakeGarmin(), today=TODAY)
    assert rows(c, "SELECT min(date), count(*) FROM daily")[0] == ("2026-05-17", 4)
    sync.run(
        cfg(refresh_days=1, backfill_per_run=0, history_days=2), garmin=FakeGarmin(), today=TODAY
    )
    assert rows(c, "SELECT min(date) FROM daily")[0][0] == "2026-05-19"


def test_activities_body_and_raw_are_stored():
    c = cfg(refresh_days=1, backfill_per_run=0)
    sync.run(c, garmin=FakeGarmin(), today=TODAY)
    assert rows(c, "SELECT activity_id, type, distance_km FROM activities") == [
        ("99", "running", 5.0)
    ]
    assert rows(c, "SELECT weight_kg FROM weigh_ins") == [(80.0,)]
    assert rows(c, "SELECT systolic FROM blood_pressure") == [(120,)]
    kinds = {k for (k,) in rows(c, "SELECT kind FROM raw")}
    assert {"stats", "sleep", "hrv", "training_status", "activity:99"} <= kinds


def test_store_raw_off():
    c = cfg(refresh_days=1, backfill_per_run=0, store_raw=False)
    sync.run(c, garmin=FakeGarmin(), today=TODAY)
    assert rows(c, "SELECT count(*) FROM raw")[0][0] == 0


def test_rate_limit_stops_early_and_is_logged():
    c = cfg(refresh_days=3, backfill_per_run=0)
    r = sync.run(c, garmin=FakeGarmin(fail_on="get_hrv_data"), today=TODAY)
    assert not r["ok"] and "slow down" in r["message"]
    assert rows(c, "SELECT ok, message FROM sync_log") == [(0, "slow down")]


def test_forced_days():
    c = cfg()
    r = sync.run(c, garmin=FakeGarmin(), today=TODAY, days=4)
    assert (r["refreshed"], r["backfilled"]) == (4, 0)
