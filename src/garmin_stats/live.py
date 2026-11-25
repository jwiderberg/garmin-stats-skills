"""Live terminal progress for the first import: a status line redrawn ten
times a second (spinner, bar, current day and data type, countdown to the
next request, elapsed and ETA), with one permanent line per finished day.
Falls back to plain lines when output isn't a terminal."""

from __future__ import annotations

import shutil
import sys
import threading
import time
from typing import Any, TextIO

LABELS = {
    "get_stats": "daily totals",
    "get_sleep_data": "sleep",
    "get_hrv_data": "HRV",
    "get_training_status": "training status",
    "get_training_readiness": "training readiness",
    "get_heart_rates": "heart rate",
    "get_stress_data": "stress + Body Battery",
    "get_body_battery_events": "Body Battery events",
    "get_spo2_data": "SpO2",
    "get_respiration_data": "respiration",
    "get_steps_data": "steps",
    "get_floors": "floors",
    "get_intensity_minutes_data": "intensity minutes",
    "get_hydration_data": "hydration",
    "get_max_metrics": "VO2max",
    "get_menstrual_data_for_date": "cycle tracking",
    "get_all_day_events": "all-day events",
    "get_activities_by_date": "workouts",
    "get_activity": "workout detail",
    "get_activity_splits": "laps",
    "get_activity_hr_in_timezones": "HR zones",
    "get_activity_weather": "weather",
    "download_activity": "FIT recording",
    "get_body_composition": "weigh-ins",
    "get_blood_pressure": "blood pressure",
    "get_race_predictions": "race predictions",
    "get_personal_record": "personal records",
    "get_endurance_score": "endurance score",
    "get_hill_score": "hill score",
    "get_lactate_threshold": "lactate threshold",
    "get_fitnessage_data": "fitness age",
    "get_devices": "devices",
    "get_heart_rate_zones_v2": "HR zone settings",
    "get_user_profile": "profile",
}
SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


def _mmss(seconds: float) -> str:
    seconds = max(0, int(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


def fmt_day(row: dict[str, Any]) -> str:
    bits = []
    if row.get("sleep_score") is not None:
        bits.append(f"sleep {row['sleep_score']}")
    if row.get("hrv_last_night_ms") is not None:
        bits.append(f"HRV {round(row['hrv_last_night_ms'])}")
    if row.get("resting_hr") is not None:
        bits.append(f"RHR {row['resting_hr']}")
    if row.get("steps") is not None:
        bits.append(f"{row['steps']:,} steps")
    return " · ".join(bits) if bits else "no data (watch not worn?)"


class Live:
    def __init__(self, out: TextIO | None = None, animate: bool | None = None) -> None:
        self.out = out or sys.stdout
        self.animate = self.out.isatty() if animate is None else animate
        self.lock = threading.Lock()
        self.t0 = time.monotonic()
        self.n_days = 0
        self.per_day = 1
        self.total = 1
        self.done = 0
        self.day_i = 0
        self.date = ""
        self.step = 0
        self.label = "connecting to Garmin"
        self.wait_until = 0.0
        self.paused_until = 0.0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._frame = 0

    # ── lifecycle ────────────────────────────────────────────────────────
    def __enter__(self) -> Live:
        if self.animate:
            self.out.write("\033[?25l")  # hide cursor
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join()
        if self.animate:
            with self.lock:
                self.out.write("\r\033[K\033[?25h")
                self.out.flush()

    # ── progress callback (sync.run) ─────────────────────────────────────
    def __call__(self, event: str, **k: Any) -> None:
        with self.lock:
            if event == "plan":
                self.n_days, self.per_day = k["days"], k["per_day"]
                self.total = max(1, self.n_days * self.per_day + 8)
            elif event == "day_start":
                self.day_i, self.date, self.step = k["i"], k["date"], 0
                self.label = "starting"
            elif event == "request":
                self.step += 1
                self.done = min(self.done + 1, self.total - 1)
                self.label = LABELS.get(
                    k["method"], k["method"].replace("get_", "").replace("_", " ")
                )
                self.wait_until = 0.0
            elif event == "wait":
                self.wait_until = time.monotonic() + k["seconds"]
            elif event == "day":
                self._print(f"   ✓ [{k['i']:>3}/{k['n']}] {k['date']}  {fmt_day(k['row'])}")
            elif event == "pause":
                self.paused_until = time.monotonic() + k["seconds"]
                self._print(
                    f"   … Garmin asked us to slow down. Waiting {k['seconds'] // 60} min, "
                    "then carrying on (nothing is lost)."
                )
            elif event == "extras":
                self.date, self.label, self.step = "", "workouts, weigh-ins, records", 0
                if not self.animate:
                    self._print("   Fetching workouts, weigh-ins, blood pressure and records…")

    # ── rendering ────────────────────────────────────────────────────────
    def _print(self, line: str) -> None:
        if self.animate:
            self.out.write("\r\033[K")
        self.out.write(line + "\n")
        self.out.flush()

    def status_line(self, now: float | None = None) -> str:
        """Most useful first (bar, %, time left, day), so a narrow window
        trims only the fine detail at the end."""
        now = now or time.monotonic()
        elapsed = now - self.t0
        frac = self.done / self.total
        cols = shutil.get_terminal_size((100, 20)).columns
        width = 22 if cols >= 110 else 12
        filled = int(frac * width)
        bar = "█" * filled + "░" * (width - filled)
        spin = SPINNER[self._frame % len(SPINNER)]
        if self.done:
            eta = elapsed / self.done * (self.total - self.done)
            timing = f"~{_mmss(eta)} left"
        else:
            timing = f"{_mmss(elapsed)} elapsed"
        if now < self.paused_until:
            what = f"paused for Garmin, resuming in {_mmss(self.paused_until - now)}"
        elif self.date:
            step = f" {self.step}/{self.per_day}" if self.step else ""
            what = f"day {self.day_i}/{self.n_days} {self.date} · {self.label}{step}"
        else:
            what = self.label
        if now < self.wait_until:
            what += f" · next in {self.wait_until - now:.1f}s"
        line = f"   {spin} {bar} {frac:>4.0%} · {timing} · {what}"
        return line if len(line) < cols else line[: cols - 2] + "…"

    def _loop(self) -> None:
        while not self._stop.wait(0.1):
            with self.lock:
                self._frame += 1
                self.out.write("\r\033[K" + self.status_line())
                self.out.flush()
