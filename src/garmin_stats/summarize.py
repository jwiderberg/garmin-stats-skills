"""Compact views over Garmin's raw payloads.

Raw Garmin responses are huge (a night of sleep is ~150 KB of epochs) and
full of UI noise. These functions keep the numbers a person asks about,
with units in the key names. Every tool can still return the raw payload
with raw=true. Missing values are None — never 0 — so a day the watch
wasn't worn reads as a gap, not as a bad day.
"""

from __future__ import annotations

import re
from typing import Any


def _d(v: Any) -> dict:
    return v if isinstance(v, dict) else {}


def _num(v: Any) -> float | int | None:
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _min(seconds: Any) -> int | None:
    s = _num(seconds)
    return round(s / 60) if s is not None else None


def _km(meters: Any) -> float | None:
    m = _num(meters)
    return round(m / 1000, 2) if m is not None else None


def _local_iso(ms: Any) -> str | None:
    """Garmin's *Local timestamps are epoch-ms already shifted to the wearer's
    clock, so decode them as UTC to get local wall time: '2026-11-24T22:55:55'."""
    from datetime import UTC, datetime

    v = _num(ms)
    if v is None:
        return ms if isinstance(ms, str) and ms else None
    return datetime.fromtimestamp(v / 1000, UTC).strftime("%Y-%m-%dT%H:%M:%S")


def daily(stats: Any) -> dict[str, Any]:
    """get_stats / get_user_summary → one day's activity + wellness totals."""
    s = _d(stats)
    return {
        "date": s.get("calendarDate"),
        "steps": _num(s.get("totalSteps")),
        "step_goal": _num(s.get("dailyStepGoal")),
        "distance_km": _km(s.get("totalDistanceMeters")),
        "active_kcal": _num(s.get("activeKilocalories")),
        "total_kcal": _num(s.get("totalKilocalories")),
        "floors_up": _num(s.get("floorsAscended")),
        "intensity_min_moderate": _num(s.get("moderateIntensityMinutes")),
        "intensity_min_vigorous": _num(s.get("vigorousIntensityMinutes")),
        "resting_hr": _num(s.get("restingHeartRate")),
        "resting_hr_7d_avg": _num(s.get("lastSevenDaysAvgRestingHeartRate")),
        "hr_min": _num(s.get("minHeartRate")),
        "hr_max": _num(s.get("maxHeartRate")),
        "stress_avg": _num(s.get("averageStressLevel")),
        "stress_max": _num(s.get("maxStressLevel")),
        "body_battery_high": _num(s.get("bodyBatteryHighestValue")),
        "body_battery_low": _num(s.get("bodyBatteryLowestValue")),
        "body_battery_at_wake": _num(s.get("bodyBatteryAtWakeTime")),
        "body_battery_charged": _num(s.get("bodyBatteryChargedValue")),
        "body_battery_drained": _num(s.get("bodyBatteryDrainedValue")),
        "spo2_avg": _num(s.get("averageSpo2")),
        "spo2_lowest": _num(s.get("lowestSpo2")),
        "respiration_avg_waking": _num(s.get("avgWakingRespirationValue")),
        "sedentary_min": _min(s.get("sedentarySeconds")),
        "active_min": _min(s.get("activeSeconds")),
    }


def sleep(raw: Any) -> dict[str, Any]:
    """get_sleep_data → last night's sleep."""
    r = _d(raw)
    dto = _d(r.get("dailySleepDTO"))
    scores = _d(dto.get("sleepScores"))
    return {
        "date": dto.get("calendarDate"),
        "sleep_score": _num(_d(scores.get("overall")).get("value")),
        "sleep_quality": _d(scores.get("overall")).get("qualifierKey"),
        "sleep_min": _min(dto.get("sleepTimeSeconds")),
        "deep_min": _min(dto.get("deepSleepSeconds")),
        "light_min": _min(dto.get("lightSleepSeconds")),
        "rem_min": _min(dto.get("remSleepSeconds")),
        "awake_min": _min(dto.get("awakeSleepSeconds")),
        "nap_min": _min(dto.get("napTimeSeconds")),
        "sleep_start_local": _local_iso(dto.get("sleepStartTimestampLocal")),
        "sleep_end_local": _local_iso(dto.get("sleepEndTimestampLocal")),
        "avg_sleep_hr": _num(dto.get("avgHeartRate")),
        "avg_sleep_stress": _num(dto.get("avgSleepStress")),
        "avg_sleep_respiration": _num(dto.get("averageRespirationValue")),
        "avg_sleep_spo2": _num(_d(r.get("wellnessSpO2SleepSummaryDTO")).get("averageSPO2")),
        "overnight_hrv_ms": _num(r.get("avgOvernightHrv")),
        "hrv_status": r.get("hrvStatus"),
        "body_battery_change": _num(r.get("bodyBatteryChange")),
        "resting_hr": _num(r.get("restingHeartRate")),
        "skin_temp_deviation_c": _num(r.get("avgSkinTempDeviationC")),
        "restless_moments": _num(r.get("restlessMomentsCount")),
        "feedback": dto.get("sleepScoreFeedback"),
    }


def hrv(raw: Any) -> dict[str, Any]:
    """get_hrv_data → overnight HRV summary + baseline."""
    s = _d(_d(raw).get("hrvSummary"))
    base = _d(s.get("baseline"))
    return {
        "date": s.get("calendarDate"),
        "last_night_avg_ms": _num(s.get("lastNightAvg")),
        "last_night_5min_high_ms": _num(s.get("lastNight5MinHigh")),
        "weekly_avg_ms": _num(s.get("weeklyAvg")),
        "status": s.get("status"),
        "baseline_low_ms": _num(base.get("balancedLow")),
        "baseline_high_ms": _num(base.get("balancedUpper")),
        "feedback": s.get("feedbackPhrase"),
    }


def _first_device_entry(m: Any) -> dict:
    for v in _d(m).values():
        if isinstance(v, dict):
            return v
    return {}


def training_status(raw: Any) -> dict[str, Any]:
    """get_training_status → status label, acute/chronic load, VO2max.
    Garmin's feedback phrase ("PRODUCTIVE_3") is the reliable label; the
    integer code's meaning is undocumented, so it's only a fallback."""
    r = _d(raw)
    latest = _first_device_entry(
        _d(r.get("mostRecentTrainingStatus")).get("latestTrainingStatusData")
    )
    phrase = latest.get("trainingStatusFeedbackPhrase")
    status = re.sub(r"_\d+$", "", phrase) if isinstance(phrase, str) and phrase else None
    load = _d(latest.get("acuteTrainingLoadDTO"))
    vo2 = _d(_d(r.get("mostRecentVO2Max")).get("generic"))
    balance = _first_device_entry(
        _d(r.get("mostRecentTrainingLoadBalance")).get("metricsTrainingLoadBalanceDTOMap")
    )
    return {
        "date": latest.get("calendarDate"),
        "status": status,
        "status_code": _num(latest.get("trainingStatus")),
        "acute_load_7d": _num(load.get("dailyTrainingLoadAcute")),
        "chronic_load_28d": _num(load.get("dailyTrainingLoadChronic")),
        "acute_chronic_ratio": _num(load.get("dailyAcuteChronicWorkloadRatio")),
        "acwr_status": load.get("acwrStatus"),
        "vo2max": _num(vo2.get("vo2MaxPreciseValue")) or _num(vo2.get("vo2MaxValue")),
        "fitness_age": _num(vo2.get("fitnessAge")),
        "monthly_load_aerobic_low": _num(balance.get("monthlyLoadAerobicLow")),
        "monthly_load_aerobic_high": _num(balance.get("monthlyLoadAerobicHigh")),
        "monthly_load_anaerobic": _num(balance.get("monthlyLoadAnaerobic")),
        "load_balance_feedback": balance.get("trainingBalanceFeedbackPhrase"),
    }


def training_readiness(raw: Any) -> dict[str, Any]:
    """get_training_readiness (a list, newest first) → today's score."""
    items = raw if isinstance(raw, list) else [raw]
    r = _d(items[0]) if items else {}
    return {
        "date": r.get("calendarDate"),
        "score": _num(r.get("score")),
        "level": r.get("level"),
        "feedback": r.get("feedbackShort"),
        "recovery_time_h": round(_num(r.get("recoveryTime")) / 60, 1)
        if _num(r.get("recoveryTime")) is not None
        else None,
        "sleep_score_factor_pct": _num(r.get("sleepScoreFactorPercent")),
        "hrv_factor_pct": _num(r.get("hrvFactorPercent")),
        "acute_load_factor_pct": _num(r.get("acwrFactorPercent")),
        "stress_history_factor_pct": _num(r.get("stressHistoryFactorPercent")),
    }


def activity(raw: Any) -> dict[str, Any]:
    """One activity (list entry or get_activity) → the headline numbers."""
    a = _d(raw)
    summary = _d(a.get("summaryDTO"))  # get_activity nests numbers here

    def g(key: str, alt: str | None = None) -> Any:
        v = a.get(key)
        if v is None:
            v = summary.get(alt or key)
        return v

    atype = a.get("activityType") or a.get("activityTypeDTO")
    duration = _num(g("duration"))
    distance = _num(g("distance"))
    speed = _num(g("averageSpeed"))
    return {
        "activity_id": a.get("activityId"),
        "name": a.get("activityName"),
        "type": _d(atype).get("typeKey") if isinstance(atype, dict) else atype,
        "start_local": a.get("startTimeLocal") or summary.get("startTimeLocal"),
        "duration_min": round(duration / 60, 1) if duration is not None else None,
        "distance_km": _km(distance),
        "avg_pace_min_per_km": round(1000 / speed / 60, 2) if speed else None,
        "avg_hr": _num(g("averageHR", "averageHR")),
        "max_hr": _num(g("maxHR", "maxHR")),
        "calories": _num(g("calories")),
        "elevation_gain_m": _num(g("elevationGain")),
        "aerobic_training_effect": _num(g("aerobicTrainingEffect", "trainingEffect")),
        "anaerobic_training_effect": _num(g("anaerobicTrainingEffect")),
        "training_load": _num(g("activityTrainingLoad")),
        "avg_power_w": _num(g("avgPower", "averagePower")),
        "avg_cadence": _num(g("averageRunningCadenceInStepsPerMinute"))
        or _num(g("averageBikingCadenceInRevPerMinute")),
        "vo2max": _num(a.get("vO2MaxValue")),
    }


def weigh_ins(raw: Any) -> list[dict[str, Any]]:
    """get_body_composition → one entry per weigh-in (weight is grams raw)."""
    out = []
    for w in _d(raw).get("dateWeightList") or []:
        w = _d(w)
        grams = _num(w.get("weight"))
        out.append(
            {
                "date": w.get("calendarDate"),
                "weight_kg": round(grams / 1000, 2) if grams is not None else None,
                "bmi": _num(w.get("bmi")),
                "body_fat_pct": _num(w.get("bodyFat")),
                "body_water_pct": _num(w.get("bodyWater")),
                "muscle_mass_kg": round(_num(w.get("muscleMass")) / 1000, 2)
                if _num(w.get("muscleMass")) is not None
                else None,
                "source": w.get("sourceType"),
            }
        )
    return out


def blood_pressure(raw: Any) -> list[dict[str, Any]]:
    """get_blood_pressure → one entry per reading."""
    out = []
    for day in _d(raw).get("measurementSummaries") or []:
        for m in _d(day).get("measurements") or []:
            m = _d(m)
            out.append(
                {
                    "measured_local": m.get("measurementTimestampLocal"),
                    "systolic": _num(m.get("systolic")),
                    "diastolic": _num(m.get("diastolic")),
                    "pulse": _num(m.get("pulse")),
                    "category": m.get("category"),
                    "notes": m.get("notes"),
                }
            )
    return out
