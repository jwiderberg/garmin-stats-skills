---
name: garmin-stats
description: Answer questions about the user's own Garmin watch data — sleep, HRV, resting heart rate, stress, Body Battery, steps, calories, workouts/runs/rides, training status and load, training readiness, VO2max, race predictions, weight, blood pressure. Use when the user asks how they slept, how recovered or fit they are, what they did in a workout, how a metric is trending, or wants a weekly/monthly health or training review from Garmin.
---

# Garmin stats

You have read-only access to the user's own Garmin Connect account through
the `garmin` MCP server (tools listed below). It runs on the user's computer
with their saved Garmin session; nothing is written back to Garmin.

## Before anything else

If a tool errors with a login/session message, or this is the first Garmin
question in the conversation and you're unsure, call `garmin_status`.
If it says `logged_in: false`, stop and tell the user exactly:

> Open Terminal and run `garmin-stats login` (email, password, and the MFA
> code if Garmin asks). Then ask me again.

If the MCP server itself is missing (no `garmin` tools at all, or the tool
says it isn't set up), the user hasn't run the installer on this computer:

> In Terminal run:
> `curl -fsSL https://raw.githubusercontent.com/jwiderberg/garmin-stats-skills/main/install.sh | bash`

Never ask the user for their Garmin password in chat.

## Picking the tool

| Question | Tool |
|---|---|
| "How did I sleep?" (last night = today's date) | `sleep(day)` |
| "How recovered am I / should I train hard?" | `training_readiness`, `hrv`, `sleep`, `training_status` |
| One day's totals (steps, calories, stress, Body Battery, RHR) | `daily_summary(day)` |
| Trend over days/weeks ("my HRV this month") | `daily_range(start, end)` — ≤31 days per call |
| Workouts list ("my runs in October") | `activities(start, end, activity_type)` |
| One workout in depth, laps/splits | `activity_detail(activity_id, include_splits=true)` |
| Training status, acute vs chronic load, ACWR | `training_status(day)` |
| VO2max, fitness age, race predictions, PRs | `performance()` |
| Weight / body composition | `body_composition(start, end)` |
| Blood pressure | `blood_pressure(start, end)` |
| All-day HR, stress, Body Battery detail | `heart_rate`, `stress_and_body_battery` |
| Anything else Garmin has (floors, endurance/hill score, lactate threshold, devices, SpO2/respiration detail) | `garmin_raw(method, args)` |

Dates: `YYYY-MM-DD`, or `"today"` / `"yesterday"`. Use the user's local
calendar. Sleep is filed under the morning it ended, so "last night" is
`sleep("today")`.

## Working efficiently

- For more than a few days use `daily_range`, not repeated single-day calls.
  For longer spans (a quarter, a year) call it in consecutive ≤31-day chunks.
  Past days are cached on the user's computer, so re-asking is cheap.
- Use `include=["sleep"]` (or `"daily"`, `"hrv"`) when only one part is needed.
- `activities` accepts up to 366 days in one call — use it for workout history.
- Only use `raw=true` when the compact fields don't answer the question
  (e.g. minute-by-minute sleep stages, HR samples, lap-level detail). Raw sleep
  is ~150 KB per night: fetch one night, not a range.
- Garmin rate-limits aggressive use. If a tool reports rate limiting, stop,
  tell the user, and suggest trying again in a few minutes. Don't retry in a loop.

## Reading the data honestly

- `null` means no data (watch not worn, feature not supported, not synced yet),
  **not zero**. Say "no data for Tuesday", never treat it as a bad day.
  Today's numbers are partial until the day ends, and the watch must have
  synced with the Garmin Connect app.
- Training load 0 with status DETRAINING / RECOVERY is real (rest), not missing.
- Training status and readiness are Garmin's own labels — attribute them
  ("Garmin rates your status as *productive*"). Garmin's acute:chronic ratio is
  usually healthy around 0.8–1.5; quote Garmin's `acwr_status` rather than
  inventing thresholds.
- HRV is personal: compare against the user's own `baseline_low_ms`–
  `baseline_high_ms` and weekly average, not population norms.
- Compare like with like (weekdays vs weekdays, same activity type).
- When you summarise a period, show the numbers (a small table works well),
  then the pattern, then caveats about gaps.
- See `references/metrics.md` for what each metric means and its units.

## Boundaries

This is the user's own data, for their own insight. Describe what the data
shows; don't diagnose. If something looks medically concerning (e.g. very
high blood pressure readings, resting HR far outside the user's normal range,
SpO2 persistently low), say plainly that it's worth raising with a doctor —
don't speculate about causes.
