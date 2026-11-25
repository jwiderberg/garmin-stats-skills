"""MCP server (stdio): read-only tools over the user's own Garmin Connect data.

Dates are ISO YYYY-MM-DD in the computer's local calendar; "today" and
"yesterday" are accepted too. Tools return compact summaries; pass
raw=true to get Garmin's full payload instead.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from mcp.server.fastmcp import FastMCP

from garmin_stats import paths, summarize
from garmin_stats.client import GarminData, NotLoggedIn, parse_date

MAX_RANGE_DAYS = 31
MAX_LIST_RANGE_DAYS = 366

# get_* methods exposed through garmin_raw — read-only by construction.
RAW_ALLOWED = frozenset(
    {
        "get_stats",
        "get_user_summary",
        "get_daily_summaries",
        "get_sleep_data",
        "get_hrv_data",
        "get_stress_data",
        "get_body_battery",
        "get_heart_rates",
        "get_rhr_day",
        "get_steps_data",
        "get_floors",
        "get_intensity_minutes_data",
        "get_spo2_data",
        "get_respiration_data",
        "get_hydration_data",
        "get_training_status",
        "get_training_readiness",
        "get_max_metrics",
        "get_endurance_score",
        "get_hill_score",
        "get_fitnessage_data",
        "get_race_predictions",
        "get_lactate_threshold",
        "get_personal_record",
        "get_activities_by_date",
        "get_activity",
        "get_activity_splits",
        "get_activity_hr_in_timezones",
        "get_activity_details",
        "get_body_composition",
        "get_blood_pressure",
        "get_devices",
        "get_user_profile",
        "get_full_name",
    }
)

mcp = FastMCP("garmin-stats")
data = GarminData()


def _date(value: str | None) -> date:
    return parse_date(value, data.today())


def _span(start: str, end: str | None, cap: int) -> tuple[date, date]:
    s, e = _date(start), _date(end)
    if e < s:
        s, e = e, s
    if (e - s).days + 1 > cap:
        raise ValueError(f"Range too long: {(e - s).days + 1} days (max {cap}). Split it up.")
    return s, e


def _days(s: date, e: date) -> list[date]:
    return [s + timedelta(days=i) for i in range((e - s).days + 1)]


@mcp.tool()
def garmin_status() -> dict[str, Any]:
    """Check the Garmin connection: whether this computer is logged in and as whom.
    Call this first if any other tool reports a login problem."""
    if not paths.token_file().exists():
        return {"logged_in": False, "fix": "Open Terminal and run:  garmin-stats login"}
    try:
        name = data.call("get_full_name")
    except NotLoggedIn as e:
        return {"logged_in": False, "fix": str(e)}
    return {"logged_in": True, "account": name, "today": data.today().isoformat()}


@mcp.tool()
def daily_summary(day: str = "today", raw: bool = False) -> dict[str, Any]:
    """One day's totals: steps, distance, calories, intensity minutes, resting HR,
    stress, Body Battery, SpO2, respiration."""
    d = _date(day)
    r = data.call("get_stats", d.isoformat(), cache_until=d)
    return r if raw else summarize.daily(r)


@mcp.tool()
def sleep(day: str = "today", raw: bool = False) -> dict[str, Any]:
    """The sleep that ENDED on `day` (so 'today' = last night): score, duration,
    deep/light/REM/awake minutes, naps, overnight HRV, sleep HR/stress/SpO2,
    skin-temperature deviation. raw=true adds minute-level stages and epochs."""
    d = _date(day)
    r = data.call("get_sleep_data", d.isoformat(), cache_until=d)
    return r if raw else summarize.sleep(r)


@mcp.tool()
def hrv(day: str = "today", raw: bool = False) -> dict[str, Any]:
    """Overnight heart-rate variability for `day`: last-night average, weekly
    average, status and the personal baseline range."""
    d = _date(day)
    r = data.call("get_hrv_data", d.isoformat(), cache_until=d)
    return (r or {}) if raw else summarize.hrv(r)


@mcp.tool()
def daily_range(
    start: str,
    end: str = "today",
    include: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Day-by-day trend over [start, end] inclusive (max 31 days per call): one
    row per day merging daily totals with sleep and HRV. `include` picks parts
    from ["daily", "sleep", "hrv"] (default all three). Days already in the past
    are cached locally, so repeated or overlapping ranges are fast."""
    parts = set(include or ["daily", "sleep", "hrv"])
    s, e = _span(start, end, MAX_RANGE_DAYS)
    rows = []
    for d in _days(s, e):
        iso = d.isoformat()
        row: dict[str, Any] = {"date": iso}
        if "daily" in parts:
            row |= {
                k: v
                for k, v in summarize.daily(data.call("get_stats", iso, cache_until=d)).items()
                if k != "date"
            }
        if "sleep" in parts:
            sl = summarize.sleep(data.call("get_sleep_data", iso, cache_until=d))
            row |= {
                f"sleep_{k}" if not k.startswith("sleep") else k: v
                for k, v in sl.items()
                if k not in ("date", "feedback")
            }
        if "hrv" in parts:
            h = summarize.hrv(data.call("get_hrv_data", iso, cache_until=d))
            row |= {"hrv_last_night_ms": h["last_night_avg_ms"], "hrv_status": h["status"]}
        rows.append(row)
    return rows


@mcp.tool()
def heart_rate(day: str = "today", raw: bool = False) -> dict[str, Any]:
    """Heart rate for one day: resting, min, max, 7-day resting average.
    raw=true adds the all-day HR samples."""
    d = _date(day)
    r = data.call("get_heart_rates", d.isoformat(), cache_until=d)
    if raw:
        return r
    return {
        "date": r.get("calendarDate"),
        "resting_hr": r.get("restingHeartRate"),
        "min_hr": r.get("minHeartRate"),
        "max_hr": r.get("maxHeartRate"),
        "resting_hr_7d_avg": r.get("lastSevenDaysAvgRestingHeartRate"),
    }


@mcp.tool()
def stress_and_body_battery(day: str = "today", raw: bool = False) -> dict[str, Any]:
    """All-day stress and Body Battery for one day. Compact view gives averages,
    highs/lows and time in each stress band; raw=true adds the 3-minute series."""
    d = _date(day)
    r = data.call("get_stress_data", d.isoformat(), cache_until=d)
    if raw:
        return r
    stats = summarize.daily(data.call("get_stats", d.isoformat(), cache_until=d))
    return {
        "date": d.isoformat(),
        "stress_avg": r.get("avgStressLevel"),
        "stress_max": r.get("maxStressLevel"),
        "body_battery_high": stats["body_battery_high"],
        "body_battery_low": stats["body_battery_low"],
        "body_battery_at_wake": stats["body_battery_at_wake"],
        "body_battery_charged": stats["body_battery_charged"],
        "body_battery_drained": stats["body_battery_drained"],
    }


@mcp.tool()
def activities(
    start: str,
    end: str = "today",
    activity_type: str | None = None,
) -> list[dict[str, Any]]:
    """Workouts recorded between start and end (inclusive, max 366 days): type,
    duration, distance, pace, HR, calories, training effect and load. Filter with
    activity_type, e.g. "running", "cycling", "strength_training", "swimming"."""
    s, e = _span(start, end, MAX_LIST_RANGE_DAYS)
    r = data.call(
        "get_activities_by_date", s.isoformat(), e.isoformat(), activity_type, cache_until=e
    )
    return [summarize.activity(a) for a in (r or [])]


@mcp.tool()
def activity_detail(
    activity_id: str, include_splits: bool = False, raw: bool = False
) -> dict[str, Any]:
    """One workout in depth (use an activity_id from `activities`). include_splits
    adds per-lap splits; raw=true returns Garmin's full record."""
    r = data.call("get_activity", str(activity_id), cache_until=date(2000, 1, 1))
    out: dict[str, Any] = r if raw else summarize.activity(r)
    if include_splits:
        splits = data.call("get_activity_splits", str(activity_id), cache_until=date(2000, 1, 1))
        laps = (splits or {}).get("lapDTOs") or []
        out = dict(out)
        out["splits"] = laps if raw else [summarize.activity(lap) for lap in laps]
    return out


@mcp.tool()
def training_status(day: str = "today", raw: bool = False) -> dict[str, Any]:
    """Garmin's training status on `day` (productive, maintaining, recovery,
    detraining, strained, ...), 7-day acute vs 28-day chronic load and their
    ratio, VO2max, fitness age and the 4-week load balance."""
    d = _date(day)
    r = data.call("get_training_status", d.isoformat(), cache_until=d)
    return r if raw else summarize.training_status(r)


@mcp.tool()
def training_readiness(day: str = "today", raw: bool = False) -> dict[str, Any]:
    """Garmin's Training Readiness score for `day` with its contributing factors
    and recovery time. Not every watch supports it (empty result if not)."""
    d = _date(day)
    r = data.call("get_training_readiness", d.isoformat(), cache_until=d)
    return {"items": r} if raw else summarize.training_readiness(r)


@mcp.tool()
def body_composition(start: str, end: str = "today", raw: bool = False) -> Any:
    """Weigh-ins between start and end (max 366 days): weight, BMI, body fat,
    water and muscle mass (scale-dependent)."""
    s, e = _span(start, end, MAX_LIST_RANGE_DAYS)
    r = data.call("get_body_composition", s.isoformat(), e.isoformat(), cache_until=e)
    return r if raw else summarize.weigh_ins(r)


@mcp.tool()
def blood_pressure(start: str, end: str = "today", raw: bool = False) -> Any:
    """Blood-pressure readings logged in Garmin Connect between start and end
    (max 366 days)."""
    s, e = _span(start, end, MAX_LIST_RANGE_DAYS)
    r = data.call("get_blood_pressure", s.isoformat(), e.isoformat(), cache_until=e)
    return r if raw else summarize.blood_pressure(r)


@mcp.tool()
def performance(raw: bool = False) -> dict[str, Any]:
    """Current fitness markers: VO2max and fitness age, race-time predictions
    (5K/10K/half/marathon), and personal records."""
    today = data.today().isoformat()
    preds = data.call("get_race_predictions") or {}
    prs = data.call("get_personal_record") or []
    ts = summarize.training_status(data.call("get_training_status", today))
    if raw:
        return {"race_predictions": preds, "personal_records": prs}

    def hms(sec: Any) -> str | None:
        if not isinstance(sec, (int, float)):
            return None
        sec = int(sec)
        return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}"

    p = preds[0] if isinstance(preds, list) and preds else preds
    return {
        "vo2max": ts["vo2max"],
        "fitness_age": ts["fitness_age"],
        "race_predictions": {
            "5k": hms(p.get("time5K")),
            "10k": hms(p.get("time10K")),
            "half_marathon": hms(p.get("timeHalfMarathon")),
            "marathon": hms(p.get("timeMarathon")),
        },
        "personal_records": prs,
    }


@mcp.tool()
def garmin_raw(method: str, args: list[Any] | None = None) -> Any:
    """Escape hatch: call any read-only garminconnect method directly and get the
    raw response, for data the other tools don't cover (e.g. "get_floors",
    "get_endurance_score", "get_hill_score", "get_lactate_threshold",
    "get_devices", "get_spo2_data", "get_respiration_data"). args are positional,
    dates as YYYY-MM-DD. Only allow-listed get_* methods are accepted."""
    if method not in RAW_ALLOWED:
        raise ValueError(f"Method not allowed: {method}. Allowed: {', '.join(sorted(RAW_ALLOWED))}")
    return data.call(method, *(args or []))


def serve() -> None:
    mcp.run()


if __name__ == "__main__":  # pragma: no cover
    serve()


__all__ = ["data", "mcp", "serve"]
