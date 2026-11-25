"""MCP server (stdio) for Claude Cowork / Claude Code.

Reads the local SQLite cache that the hourly background sync keeps fresh,
so answers are instant and never touch Garmin's rate limits. Two tools do
reach Garmin, on request: garmin_sync_now (refresh recent days) and
garmin_connect (sign in again via native macOS dialogs).
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import date
from typing import Any

from mcp.server.fastmcp import FastMCP

from garmin_stats import client, config, db, mac, paths, schedule, sync

MAX_ROWS = 2000
_WRITE = re.compile(
    r"\b(insert|update|delete|replace|drop|alter|create|attach|detach|pragma|vacuum|reindex)\b",
    re.IGNORECASE,
)

mcp = FastMCP("garmin-stats")


def _conn() -> sqlite3.Connection:
    cfg = config.load()
    if not cfg.db_path.exists():
        db.connect(cfg.db_path).close()  # create the empty schema so queries work
    return db.connect(cfg.db_path, readonly=True)


@mcp.tool()
def garmin_status() -> dict[str, Any]:
    """Start here. Sign-in state, last background sync, what the cache covers,
    and the table schema for garmin_query."""
    cfg = config.load()
    conn = _conn()
    try:
        cov = {
            t: dict(
                conn.execute(
                    f"SELECT count(*) AS rows, min(date) AS first, max(date) AS last FROM {t}"
                ).fetchone()
            )
            for t in ("daily", "activities", "weigh_ins")
        }
        last = conn.execute(
            "SELECT started_at, ok, message FROM sync_log ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
        tables = ("daily", "activities", "weigh_ins", "blood_pressure", "raw")
        schema = {t: db.columns(conn, t) for t in tables}
    finally:
        conn.close()
    return {
        "signed_in": paths.token_file().exists(),
        "today": date.today().isoformat(),
        "last_sync": dict(last) if last else None,
        "background_sync": f"every {cfg.sync_interval_minutes} min"
        if schedule.is_installed()
        else "off",
        "history_days_target": cfg.history_days,
        "coverage": cov,
        "schema": schema,
    }


@mcp.tool()
def garmin_query(sql: str) -> dict[str, Any]:
    """Run a read-only SQL SELECT against the local Garmin cache (SQLite).
    Tables: daily (one row per day), activities, weigh_ins, blood_pressure, raw.
    Returns up to 2000 rows as {columns, rows}. See garmin_status for columns."""
    if not re.match(r"^\s*(select|with)\b", sql, re.IGNORECASE) or _WRITE.search(sql):
        raise ValueError("Only read-only SELECT / WITH queries are allowed.")
    conn = _conn()
    try:
        cur = conn.execute(sql)
        cols = [d[0] for d in cur.description or []]
        rows = cur.fetchmany(MAX_ROWS + 1)
    finally:
        conn.close()
    return {
        "columns": cols,
        "rows": [list(r) for r in rows[:MAX_ROWS]],
        "truncated": len(rows) > MAX_ROWS,
    }


@mcp.tool()
def garmin_raw(day: str, kind: str) -> Any:
    """Garmin's full original payload for one day, for detail the tables don't
    hold. Day kinds: sleep, stats, hrv, training_status, readiness, heart_rate,
    stress (incl. Body Battery series), body_battery_events, spo2, respiration,
    steps, floors, intensity_minutes, hydration, max_metrics, menstrual,
    all_day_events. Workout kinds: activity:<id>, activity_detail:<id>,
    activity_splits:<id>, activity_hr_zones:<id>, activity_weather:<id>.
    Daily snapshots: snapshot:race_predictions, snapshot:personal_records,
    snapshot:endurance_score, snapshot:hill_score, snapshot:lactate_threshold,
    snapshot:fitness_age, snapshot:devices, snapshot:heart_rate_zones.
    `SELECT DISTINCT kind FROM raw` lists what's cached. Payloads can be large
    (sleep ~150 KB): fetch one at a time, or use json_extract in garmin_query."""
    conn = _conn()
    try:
        row = conn.execute(
            "SELECT payload FROM raw WHERE date = ? AND kind = ?", (day, kind)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return {
            "error": f"No raw '{kind}' payload cached for {day}.",
            "hint": "Raw payloads exist only for synced days, and only if store_raw is on.",
        }
    return json.loads(row[0])


@mcp.tool()
def garmin_sync_now(days: int = 2) -> dict[str, Any]:
    """Fetch the latest data from Garmin right now (default: today and yesterday,
    max 31 days) instead of waiting for the hourly sync. Use when the user asks
    about today and the last sync is old. The watch must have synced to the
    Garmin Connect phone app first."""
    return sync.run(config.load(), days=max(1, min(int(days), 31)))


@mcp.tool()
def garmin_connect() -> dict[str, Any]:
    """Sign in to Garmin Connect. Opens native macOS dialogs on the user's Mac
    asking for email, password and (if Garmin asks) a verification code. The
    password is typed into the dialog, never into the chat, and isn't stored.
    Use when garmin_status shows signed_in false or a sync says the sign-in
    expired. Tell the user to look for the dialog before calling this."""
    if not mac.is_mac():
        return {"ok": False, "message": "Run `garmin-stats login` in a terminal on this computer."}
    try:
        email = mac.ask("Garmin Connect email:")
        password = mac.ask("Garmin Connect password:", hidden=True)
        name = client.login(
            email,
            password,
            force=True,
            prompt_mfa=lambda: mac.ask("Garmin sent you a verification code. Enter it:"),
        )
    except mac.Cancelled:
        return {"ok": False, "message": "The sign-in dialog was cancelled."}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "message": f"Sign-in failed: {e}"}
    if not schedule.is_installed():
        schedule.install(config.load().sync_interval_minutes)
    return {"ok": True, "account": name, "synced": sync.run(config.load(), days=2)}


def serve() -> None:
    mcp.run()
