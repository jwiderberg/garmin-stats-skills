"""Summarizers against synthetic payloads shaped like Garmin's (no real data)."""

from garmin_stats import summarize as s

STATS = {
    "calendarDate": "2026-05-02",
    "totalSteps": 9120,
    "dailyStepGoal": 8000,
    "totalDistanceMeters": 7034.0,
    "activeKilocalories": 512,
    "restingHeartRate": 51,
    "averageStressLevel": 27,
    "bodyBatteryHighestValue": 88,
    "bodyBatteryLowestValue": 21,
    "bodyBatteryAtWakeTime": 80,
    "averageSpo2": 95,
    "sedentarySeconds": 36000,
}
SLEEP = {
    "dailySleepDTO": {
        "calendarDate": "2026-05-02",
        "sleepTimeSeconds": 26400,
        "deepSleepSeconds": 5400,
        "lightSleepSeconds": 14400,
        "remSleepSeconds": 6600,
        "awakeSleepSeconds": 900,
        "napTimeSeconds": 1200,
        "sleepScores": {"overall": {"value": 84, "qualifierKey": "GOOD"}},
    },
    "avgOvernightHrv": 58.0,
    "hrvStatus": "BALANCED",
    "bodyBatteryChange": 61,
}
HRV = {
    "hrvSummary": {
        "calendarDate": "2026-05-02",
        "lastNightAvg": 58,
        "weeklyAvg": 55,
        "status": "BALANCED",
        "baseline": {"balancedLow": 49, "balancedUpper": 66},
    }
}
TS = {
    "mostRecentTrainingStatus": {
        "latestTrainingStatusData": {
            "3456": {
                "calendarDate": "2026-05-02",
                "trainingStatus": 7,
                "trainingStatusFeedbackPhrase": "PRODUCTIVE_3",
                "acuteTrainingLoadDTO": {
                    "dailyTrainingLoadAcute": 412,
                    "dailyTrainingLoadChronic": 380,
                    "dailyAcuteChronicWorkloadRatio": 1.1,
                    "acwrStatus": "OPTIMAL",
                },
            }
        }
    },
    "mostRecentVO2Max": {"generic": {"vo2MaxPreciseValue": 51.3, "fitnessAge": 38}},
}


def test_daily_units_and_values():
    d = s.daily(STATS)
    assert d["steps"] == 9120 and d["distance_km"] == 7.03
    assert d["sedentary_min"] == 600 and d["body_battery_at_wake"] == 80


def test_missing_values_are_none_not_zero():
    d = s.daily({"calendarDate": "2026-05-03"})
    assert d["steps"] is None and d["resting_hr"] is None
    assert s.sleep(None)["sleep_score"] is None
    assert s.hrv(None)["status"] is None
    # booleans are not numbers
    assert s.daily({"totalSteps": True})["steps"] is None


def test_sleep_minutes_and_score():
    sl = s.sleep(SLEEP)
    assert (sl["sleep_score"], sl["sleep_min"], sl["deep_min"], sl["nap_min"]) == (84, 440, 90, 20)
    assert sl["overnight_hrv_ms"] == 58.0 and sl["hrv_status"] == "BALANCED"


def test_hrv_baseline():
    h = s.hrv(HRV)
    assert (h["baseline_low_ms"], h["baseline_high_ms"]) == (49, 66)


def test_training_status_uses_feedback_phrase():
    t = s.training_status(TS)
    assert t["status"] == "PRODUCTIVE"
    assert t["acute_load_7d"] == 412 and t["acute_chronic_ratio"] == 1.1
    assert t["vo2max"] == 51.3 and t["fitness_age"] == 38


def test_activity_from_list_entry():
    a = s.activity(
        {
            "activityId": 1,
            "activityName": "Run",
            "activityType": {"typeKey": "running"},
            "duration": 1800.0,
            "distance": 5000.0,
            "averageSpeed": 2.7778,
            "averageHR": 150,
            "activityTrainingLoad": 95.5,
        }
    )
    assert a["type"] == "running" and a["duration_min"] == 30.0 and a["distance_km"] == 5.0
    assert a["avg_pace_min_per_km"] == 6.0 and a["training_load"] == 95.5


def test_activity_from_detail_summary_dto():
    a = s.activity(
        {
            "activityId": 2,
            "activityTypeDTO": {"typeKey": "cycling"},
            "summaryDTO": {"duration": 3600.0, "distance": 30000.0, "averageHR": 140},
        }
    )
    assert a["type"] == "cycling" and a["duration_min"] == 60.0 and a["avg_hr"] == 140


def test_weigh_ins_and_bp():
    w = s.weigh_ins(
        {
            "dateWeightList": [
                {
                    "calendarDate": "2026-05-01",
                    "weight": 78600.0,
                    "muscleMass": 35000.0,
                    "bodyFat": 18.2,
                }
            ]
        }
    )
    assert w == [
        {
            "date": "2026-05-01",
            "weight_kg": 78.6,
            "bmi": None,
            "body_fat_pct": 18.2,
            "body_water_pct": None,
            "muscle_mass_kg": 35.0,
            "source": None,
        }
    ]
    bp = s.blood_pressure(
        {
            "measurementSummaries": [
                {
                    "measurements": [
                        {"systolic": 118, "diastolic": 76, "pulse": 60, "category": "NORMAL"}
                    ]
                }
            ]
        }
    )
    assert bp[0]["systolic"] == 118 and bp[0]["category"] == "NORMAL"
