"""Garmin Connect → local SQLite. The only code that talks to Garmin.

Each run (hourly via launchd):
  1. refreshes the last `refresh_days` days (Garmin revises recent days),
  2. backfills up to `backfill_per_run` missing older days, newest first,
     until `history_days` of history exist,
  3. pulls activities, weigh-ins and blood pressure for those spans,
  4. prunes anything older than `history_days`.
Every Garmin request is spaced `request_delay_seconds` apart (plus random
jitter), so even a 90-day import looks like a person browsing, not a
scraper. If Garmin still pushes back, a patient run (the first import)
waits 1, 3, then 5 minutes; an hourly run just stops and the next one picks
up where it left off. Only one sync runs at a time (file lock).
"""

from __future__ import annotations

import fcntl
import random
import time
from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import Any

from garmin_stats import client, db, paths, summarize
from garmin_stats.config import Config

SLEEP: Callable[[float], None] = time.sleep  # swapped out in tests
BACKOFF_S = (60, 180, 300)  # patient runs: waits after Garmin says "slow down"
Progress = Callable[..., None]


class Throttled:
    """Wraps a garminconnect client so consecutive requests are at least
    `delay` seconds apart (+0–50% jitter), and Garmin's 429 becomes
    client.RateLimited."""

    def __init__(self, garmin: Any, delay: float) -> None:
        self._g = garmin
        self._delay = delay
        self._next = 0.0

    def __getattr__(self, name: str) -> Any:
        fn = getattr(self._g, name)

        def call(*args: Any, **kwargs: Any) -> Any:
            wait = self._next - time.monotonic()
            if wait > 0:
                SLEEP(wait)
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                if "TooManyRequests" in type(e).__name__:
                    raise client.RateLimited("Garmin asked us to slow down.") from e
                raise
            finally:
                self._next = time.monotonic() + self._delay * (1 + random.random() * 0.5)

        return call


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _try(fn: Callable[[], Any]) -> Any:
    """One endpoint failing (feature unsupported on this watch) shouldn't
    sink the day; rate limits and auth problems still propagate."""
    try:
        return fn()
    except (client.RateLimited, client.NotLoggedIn):
        raise
    except Exception as e:
        name = type(e).__name__
        if "TooManyRequests" in name or "Authentication" in name:
            raise
        return None


def plan(conn, cfg: Config, today: date) -> tuple[list[date], list[date]]:
    """(refresh_days, backfill_days) for this run."""
    refresh = [today - timedelta(days=i) for i in range(cfg.refresh_days)]
    have = {r[0] for r in conn.execute("SELECT date FROM daily")}
    oldest = today - timedelta(days=cfg.history_days - 1)
    backfill: list[date] = []
    d = today - timedelta(days=cfg.refresh_days)
    while d >= oldest and len(backfill) < cfg.backfill_per_run:
        if d.isoformat() not in have:
            backfill.append(d)
        d -= timedelta(days=1)
    return refresh, backfill


def day_row(g: Any, day: date, conn, store_raw: bool) -> dict[str, Any]:
    iso = day.isoformat()
    stats = _try(lambda: g.get_stats(iso))
    sleep = _try(lambda: g.get_sleep_data(iso))
    hrv = _try(lambda: g.get_hrv_data(iso))
    ts = _try(lambda: g.get_training_status(iso))
    ready = _try(lambda: g.get_training_readiness(iso))
    if store_raw:
        for kind, payload in (
            ("stats", stats),
            ("sleep", sleep),
            ("hrv", hrv),
            ("training_status", ts),
            ("readiness", ready),
        ):
            db.put_raw(conn, iso, kind, payload)

    d, s, h = summarize.daily(stats), summarize.sleep(sleep), summarize.hrv(hrv)
    t, r = summarize.training_status(ts), summarize.training_readiness(ready)
    row = {
        k: v
        for k, v in d.items()
        if k not in ("date", "resting_hr_7d_avg", "sedentary_min", "active_min")
    }
    row |= {
        k: s[k]
        for k in (
            "sleep_score",
            "sleep_min",
            "deep_min",
            "light_min",
            "rem_min",
            "awake_min",
            "nap_min",
            "sleep_start_local",
            "sleep_end_local",
            "avg_sleep_hr",
            "avg_sleep_stress",
            "skin_temp_deviation_c",
        )
    }
    row |= {
        "hrv_last_night_ms": h["last_night_avg_ms"],
        "hrv_weekly_avg_ms": h["weekly_avg_ms"],
        "hrv_status": h["status"],
        "hrv_baseline_low_ms": h["baseline_low_ms"],
        "hrv_baseline_high_ms": h["baseline_high_ms"],
        "training_status": t["status"],
        "acute_load_7d": t["acute_load_7d"],
        "chronic_load_28d": t["chronic_load_28d"],
        "acute_chronic_ratio": t["acute_chronic_ratio"],
        "acwr_status": t["acwr_status"],
        "vo2max": t["vo2max"],
        "fitness_age": t["fitness_age"],
        "readiness_score": r["score"],
        "readiness_level": r["level"],
    }
    row["date"] = iso
    row["synced_at"] = _now()
    return row


def spans(g: Any, conn, start: date, end: date, store_raw: bool) -> int:
    """Activities, weigh-ins and BP for [start, end]. Returns activity count."""
    s, e = start.isoformat(), end.isoformat()
    acts = _try(lambda: g.get_activities_by_date(s, e)) or []
    for a in acts:
        row = summarize.activity(a)
        if row["activity_id"] is None:
            continue
        row["activity_id"] = str(row["activity_id"])
        row["date"] = (row["start_local"] or "")[:10] or None
        row.pop("vo2max", None)
        row["synced_at"] = _now()
        db.upsert(conn, "activities", row)
        if store_raw and row["date"]:
            db.put_raw(conn, row["date"], f"activity:{row['activity_id']}", a)
    for w in summarize.weigh_ins(_try(lambda: g.get_body_composition(s, e))):
        if w["date"] and w["weight_kg"] is not None:
            db.upsert(conn, "weigh_ins", w)
    for b in summarize.blood_pressure(_try(lambda: g.get_blood_pressure(s, e))):
        if b["measured_local"]:
            db.upsert(conn, "blood_pressure", b)
    return len(acts)


def _fetch_day(g: Any, d: date, conn, cfg: Config, patient: bool, progress: Progress) -> dict:
    for attempt in range(len(BACKOFF_S) + 1):
        try:
            return day_row(g, d, conn, cfg.store_raw)
        except client.RateLimited:
            if not patient or attempt == len(BACKOFF_S):
                raise
            progress("pause", seconds=BACKOFF_S[attempt])
            SLEEP(BACKOFF_S[attempt])
    raise AssertionError("unreachable")


def run(
    cfg: Config,
    garmin: Any | None = None,
    today: date | None = None,
    days: int | None = None,
    patient: bool = False,
    progress: Progress | None = None,
) -> dict[str, Any]:
    """One sync pass. `days` imports/refreshes exactly the last N days
    (newest first); otherwise refresh + gradual backfill. `progress` gets
    ("day", i=, n=, date=, row=), ("pause", seconds=) and ("extras",)."""
    progress = progress or (lambda *a, **k: None)
    today = today or date.today()
    report: dict[str, Any] = {"refreshed": 0, "backfilled": 0, "activities": 0, "ok": True}

    paths.home().mkdir(parents=True, exist_ok=True)
    lock = (paths.home() / "sync.lock").open("w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close()
        return report | {"skipped": "another sync is already running"}

    started = _now()
    conn = db.connect(cfg.db_path)
    try:
        if days:
            refresh, backfill = [today - timedelta(days=i) for i in range(days)], []
        else:
            refresh, backfill = plan(conn, cfg, today)
        g = Throttled(garmin or client.session_client(), cfg.request_delay_seconds)
        todo = refresh + backfill
        for i, d in enumerate(todo, 1):
            row = _fetch_day(g, d, conn, cfg, patient, progress)
            db.upsert(conn, "daily", row)
            conn.commit()
            report["refreshed" if d in refresh else "backfilled"] += 1
            progress("day", i=i, n=len(todo), date=d.isoformat(), row=row)
        progress("extras")
        recent_start = min(min(refresh), today - timedelta(days=30))
        report["activities"] += spans(g, conn, recent_start, today, cfg.store_raw)
        if backfill:
            report["activities"] += spans(g, conn, min(backfill), max(backfill), cfg.store_raw)
        conn.commit()
        cutoff = (today - timedelta(days=cfg.history_days - 1)).isoformat()
        for table in ("daily", "activities", "weigh_ins", "raw"):
            conn.execute(f"DELETE FROM {table} WHERE date < ?", (cutoff,))
        conn.execute("DELETE FROM blood_pressure WHERE substr(measured_local,1,10) < ?", (cutoff,))
    except (client.NotLoggedIn, client.RateLimited) as e:
        report |= {"ok": False, "message": str(e)}
    except KeyboardInterrupt:
        report |= {"ok": False, "message": "stopped", "interrupted": True}
    finally:
        conn.execute(
            "INSERT INTO sync_log VALUES (?, ?, ?, ?, ?)",
            (
                started,
                _now(),
                f"{report['refreshed']}+{report['backfilled']}",
                int(report["ok"]),
                report.get("message", ""),
            ),
        )
        conn.execute(
            "DELETE FROM sync_log WHERE rowid NOT IN "
            "(SELECT rowid FROM sync_log ORDER BY started_at DESC LIMIT 200)"
        )
        conn.commit()
        conn.close()
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()
    return report
