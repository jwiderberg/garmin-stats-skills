"""The local cache: one SQLite file, WAL mode so the hourly sync can write
while Claude reads. Summary columns come from summarize.py; full Garmin
payloads go to `raw` when store_raw is on."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS daily (
    date TEXT PRIMARY KEY,               -- YYYY-MM-DD, local calendar day
    steps INTEGER, step_goal INTEGER, distance_km REAL,
    active_kcal INTEGER, total_kcal INTEGER, floors_up REAL,
    intensity_min_moderate INTEGER, intensity_min_vigorous INTEGER,
    resting_hr INTEGER, hr_min INTEGER, hr_max INTEGER,
    stress_avg INTEGER, stress_max INTEGER,
    body_battery_high INTEGER, body_battery_low INTEGER, body_battery_at_wake INTEGER,
    body_battery_charged INTEGER, body_battery_drained INTEGER,
    spo2_avg REAL, spo2_lowest REAL, respiration_avg_waking REAL,
    sleep_score INTEGER, sleep_min INTEGER, deep_min INTEGER, light_min INTEGER,
    rem_min INTEGER, awake_min INTEGER, nap_min INTEGER,
    sleep_start_local TEXT, sleep_end_local TEXT,
    avg_sleep_hr REAL, avg_sleep_stress REAL, skin_temp_deviation_c REAL,
    hrv_last_night_ms REAL, hrv_weekly_avg_ms REAL, hrv_status TEXT,
    hrv_baseline_low_ms REAL, hrv_baseline_high_ms REAL,
    training_status TEXT, acute_load_7d REAL, chronic_load_28d REAL,
    acute_chronic_ratio REAL, acwr_status TEXT, vo2max REAL, fitness_age REAL,
    readiness_score INTEGER, readiness_level TEXT,
    synced_at TEXT
);
CREATE TABLE IF NOT EXISTS activities (
    activity_id TEXT PRIMARY KEY,
    date TEXT, start_local TEXT, type TEXT, name TEXT,
    duration_min REAL, distance_km REAL, avg_pace_min_per_km REAL,
    avg_hr INTEGER, max_hr INTEGER, calories INTEGER, elevation_gain_m REAL,
    aerobic_training_effect REAL, anaerobic_training_effect REAL,
    training_load REAL, avg_power_w REAL, avg_cadence REAL,
    synced_at TEXT
);
CREATE INDEX IF NOT EXISTS activities_date ON activities(date);
CREATE TABLE IF NOT EXISTS weigh_ins (
    date TEXT, weight_kg REAL, bmi REAL, body_fat_pct REAL, body_water_pct REAL,
    muscle_mass_kg REAL, source TEXT,
    PRIMARY KEY (date, weight_kg)
);
CREATE TABLE IF NOT EXISTS blood_pressure (
    measured_local TEXT PRIMARY KEY, systolic INTEGER, diastolic INTEGER,
    pulse INTEGER, category TEXT, notes TEXT
);
CREATE TABLE IF NOT EXISTS raw (
    -- kind: stats | sleep | hrv | training_status | readiness | activity:<id>
    date TEXT, kind TEXT, payload TEXT,
    PRIMARY KEY (date, kind)
);
CREATE TABLE IF NOT EXISTS sync_log (
    started_at TEXT, finished_at TEXT, days TEXT, ok INTEGER, message TEXT
);
"""


def connect(path: Path, readonly: bool = False) -> sqlite3.Connection:
    if readonly:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=10)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA)
        _migrate(conn)
        path.chmod(0o600)
    conn.row_factory = sqlite3.Row
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """v0.3.2 and earlier stored sleep start/end as raw epoch-ms; make them
    readable local times (idempotent)."""
    for col in ("sleep_start_local", "sleep_end_local"):
        conn.execute(
            f"UPDATE daily SET {col} = strftime('%Y-%m-%dT%H:%M:%S', {col} / 1000, 'unixepoch') "
            f"WHERE {col} GLOB '[0-9]*' AND length({col}) >= 12"
        )
    conn.commit()


def upsert(conn: sqlite3.Connection, table: str, row: dict[str, Any]) -> None:
    cols = [c for c in row]
    sql = (
        f"INSERT OR REPLACE INTO {table} ({', '.join(cols)}) "
        f"VALUES ({', '.join('?' for _ in cols)})"
    )
    conn.execute(sql, [row[c] for c in cols])


def columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]


def put_raw(conn: sqlite3.Connection, day: str, kind: str, payload: Any) -> None:
    if payload not in (None, {}, []):
        upsert(conn, "raw", {"date": day, "kind": kind, "payload": json.dumps(payload)})
