"""A fake Garmin client returning synthetic, Garmin-shaped payloads."""

from __future__ import annotations


class FakeGarmin:
    def __init__(self, fail_on: str | None = None):
        self.calls: list[tuple] = []
        self.fail_on = fail_on

    def _hit(self, name, *a):
        self.calls.append((name, *a))
        if self.fail_on == name:
            from garmin_stats.client import RateLimited

            raise RateLimited("slow down")

    def get_stats(self, d):
        self._hit("get_stats", d)
        return {"calendarDate": d, "totalSteps": 8000, "restingHeartRate": 52}

    def get_sleep_data(self, d):
        self._hit("get_sleep_data", d)
        return {
            "dailySleepDTO": {
                "calendarDate": d,
                "sleepTimeSeconds": 25200,
                "sleepScores": {"overall": {"value": 81}},
            },
            "sleepLevels": [{"activityLevel": 1}],
        }

    def get_hrv_data(self, d):
        self._hit("get_hrv_data", d)
        return {"hrvSummary": {"lastNightAvg": 55, "status": "BALANCED"}}

    def get_training_status(self, d):
        self._hit("get_training_status", d)
        return {
            "mostRecentTrainingStatus": {
                "latestTrainingStatusData": {
                    "1": {
                        "trainingStatusFeedbackPhrase": "RECOVERY_2",
                        "acuteTrainingLoadDTO": {"dailyTrainingLoadAcute": 150},
                    }
                }
            }
        }

    def get_training_readiness(self, d):
        self._hit("get_training_readiness", d)
        raise ValueError("not supported on this watch")  # per-endpoint failure

    def get_activities_by_date(self, s, e):
        self._hit("get_activities_by_date", s, e)
        return [
            {
                "activityId": 99,
                "activityName": "Run",
                "activityType": {"typeKey": "running"},
                "startTimeLocal": f"{e} 07:00:00",
                "duration": 1800.0,
                "distance": 5000.0,
            }
        ]

    def get_body_composition(self, s, e):
        self._hit("get_body_composition", s, e)
        return {"dateWeightList": [{"calendarDate": e, "weight": 80000.0}]}

    def get_blood_pressure(self, s, e):
        self._hit("get_blood_pressure", s, e)
        return {
            "measurementSummaries": [
                {
                    "measurements": [
                        {
                            "measurementTimestampLocal": f"{e}T08:00:00",
                            "systolic": 120,
                            "diastolic": 80,
                        }
                    ]
                }
            ]
        }
