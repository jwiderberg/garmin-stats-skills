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


def test_requests_are_spaced_out(monkeypatch):
    import time as _t

    waits = []
    monkeypatch.setattr(sync, "SLEEP", waits.append)
    clock = iter(range(0, 10_000))
    monkeypatch.setattr(_t, "monotonic", lambda: next(clock) * 0.0)  # frozen clock
    c = cfg(request_delay_seconds=1.0)
    sync.run(c, garmin=FakeGarmin(), today=TODAY, days=1)
    # 5 day endpoints + 3 span endpoints = 8 calls → 7 waits, each 1.0–1.5 s
    assert len(waits) == 7 and all(1.0 <= w <= 1.5 for w in waits)


def test_patient_run_backs_off_then_continues(monkeypatch):
    waits = []
    monkeypatch.setattr(sync, "SLEEP", waits.append)

    class Flaky(FakeGarmin):
        hits = 0

        def get_hrv_data(self, d):
            Flaky.hits += 1
            if Flaky.hits == 1:
                from garmin_stats.client import RateLimited

                raise RateLimited("slow down")
            return super().get_hrv_data(d)

    events = []
    c = cfg(request_delay_seconds=0.5)
    r = sync.run(
        c,
        garmin=Flaky(),
        today=TODAY,
        days=2,
        patient=True,
        progress=lambda e, **k: events.append((e, k.get("seconds"))),
    )
    assert r["ok"] and r["refreshed"] == 2
    assert ("pause", 60) in events and 60 in waits


def test_only_one_sync_at_a_time():
    import fcntl

    from garmin_stats import paths

    paths.home().mkdir(parents=True, exist_ok=True)
    with (paths.home() / "sync.lock").open("w") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        r = sync.run(cfg(), garmin=FakeGarmin(), today=TODAY, days=1)
    assert r.get("skipped")


def test_progress_reports_each_day():
    seen = []
    sync.run(
        cfg(),
        garmin=FakeGarmin(),
        today=TODAY,
        days=3,
        progress=lambda e, **k: seen.append((e, k.get("i"), k.get("n"))),
    )
    assert [s for s in seen if s[0] == "day"] == [("day", 1, 3), ("day", 2, 3), ("day", 3, 3)]


class FullGarmin(FakeGarmin):
    """Answers every other get_* with a small payload, and FIT downloads with bytes."""

    def __getattr__(self, name):
        if name.startswith("get_"):
            return lambda *a, **k: (self.calls.append((name, *a)), {"from": name})[1]
        raise AttributeError(name)

    def download_activity(self, activity_id, dl_fmt=None):
        self.calls.append(("download_activity", activity_id))
        return b"PK fit-zip"


def test_full_detail_stores_everything():
    from garmin_stats import paths

    c = cfg(refresh_days=1, backfill_per_run=0, detail="full")
    g = FullGarmin()
    sync.run(c, garmin=g, today=TODAY)
    kinds = {k for (k,) in rows(c, "SELECT kind FROM raw")}
    for k in (
        "heart_rate",
        "stress",
        "spo2",
        "respiration",
        "steps",
        "hydration",
        "menstrual",
        "all_day_events",
        "max_metrics",
    ):
        assert k in kinds, k
    for k in (
        "activity_detail:99",
        "activity_splits:99",
        "activity_weather:99",
        "snapshot:race_predictions",
        "snapshot:personal_records",
        "snapshot:devices",
    ):
        assert k in kinds, k
    fits = list((paths.home() / "activities").glob("*_99.zip"))
    assert len(fits) == 1 and fits[0].read_bytes() == b"PK fit-zip"
    # raw JSON is queryable with SQLite's json_extract
    assert rows(c, "SELECT json_extract(payload, '$.from') FROM raw WHERE kind='heart_rate'") == [
        ("get_heart_rates",)
    ]


def test_activity_detail_and_snapshots_fetched_once():
    c = cfg(refresh_days=1, backfill_per_run=0, detail="full")
    sync.run(c, garmin=FullGarmin(), today=TODAY)
    g2 = FullGarmin()
    sync.run(c, garmin=g2, today=TODAY)
    called = {name for name, *_ in g2.calls}
    assert "get_activity" not in called and "download_activity" not in called
    assert "get_race_predictions" not in called


def test_core_detail_is_lean():
    c = cfg(refresh_days=1, backfill_per_run=0, detail="core")
    g = FullGarmin()
    sync.run(c, garmin=g, today=TODAY)
    per_day = [n for n, *a in g.calls if a and a[0] == TODAY.isoformat()]
    assert len(per_day) == sync.CORE_CALLS_PER_DAY
    assert not any(n == "download_activity" for n, *_ in g.calls)


def test_long_import_fetches_older_workouts_too():
    c = cfg(detail="core")
    g = FullGarmin()
    sync.run(c, garmin=g, today=TODAY, days=60)
    spans = [a for n, *a in g.calls if n == "get_activities_by_date"]
    assert min(s for s, _ in spans) == "2026-03-22"  # 60 days back, not just 30
