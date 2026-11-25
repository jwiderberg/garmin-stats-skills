---
name: garmin-stats
description: Answer questions about the user's own Garmin watch data — sleep, HRV, resting heart rate, stress, Body Battery, steps, calories, workouts, training status and load, Training Readiness, VO2max, weight, blood pressure — and trends over days, weeks or months. Use whenever the user asks how they slept, how recovered or fit they are, about a run/ride/workout, or wants a health or training summary from Garmin. Also use when they ask to connect or reconnect Garmin.
---

# Garmin stats

The `garmin` tools read a **local copy** of the user's Garmin Connect data,
kept on their Mac and refreshed every hour in the background. Queries are
instant and don't contact Garmin. Nothing is ever written to Garmin.

## Tools

| Tool | Use |
|---|---|
| `garmin_status` | **Call first** in a conversation. Sign-in state, last sync, date coverage, and every table's columns. |
| `garmin_query(sql)` | Read-only SQLite `SELECT` over the cache. This is how you answer almost everything. |
| `garmin_raw(day, kind)` | Garmin's full payload for one day: `sleep` (minute-level stages, HR, SpO2), `stats`, `hrv`, `training_status`, `readiness`, `activity:<id>`. Large; one at a time. |
| `garmin_sync_now(days)` | Pull fresh data from Garmin now (default today + yesterday). Use when the question is about today and `last_sync` is over ~30 min old. |
| `garmin_connect()` | Opens a macOS sign-in window on the user's Mac. |

## First, check the connection

Call `garmin_status`:

- **`signed_in: false`**, or a sync message says the sign-in expired: tell the
  user *"A Garmin sign-in window is about to open on your Mac. Enter your
  Garmin email, password, and the code if Garmin sends one."* Then call
  `garmin_connect`. **Never ask for the password in chat.**
- **`coverage.daily.rows` is small**: history is still filling in. The hourly
  sync backfills older days gradually. Answer with what's there, and say so.
- **The `garmin` tools are missing or fail to start**: the helper isn't
  installed on this Mac. Tell the user to open the Terminal app, paste this,
  and press Return:
  `curl -fsSL https://raw.githubusercontent.com/jwiderberg/garmin-stats-skills/main/install.sh | bash`

## Tables (SQLite, dates are `YYYY-MM-DD` local)

- **`daily`**, one row per day: `steps`, `distance_km`, `active_kcal`,
  `intensity_min_moderate/vigorous`, `resting_hr`, `stress_avg`,
  `body_battery_high/low/at_wake`, `spo2_avg`, `respiration_avg_waking`;
  sleep `sleep_score`, `sleep_min`, `deep_min`, `light_min`, `rem_min`,
  `awake_min`, `nap_min`, `sleep_start_local`/`sleep_end_local`;
  `hrv_last_night_ms`, `hrv_weekly_avg_ms`, `hrv_status`,
  `hrv_baseline_low_ms`/`hrv_baseline_high_ms`; training `training_status`,
  `acute_load_7d`, `chronic_load_28d`, `acute_chronic_ratio`, `acwr_status`,
  `vo2max`, `fitness_age`, `readiness_score`, `readiness_level`.
  **Sleep is filed under the morning it ended**, so last night is today's row.
- **`activities`**: `activity_id`, `date`, `start_local`, `type` (e.g.
  `running`, `cycling`, `strength_training`, `lap_swimming`), `name`,
  `duration_min`, `distance_km`, `avg_pace_min_per_km`, `avg_hr`, `max_hr`,
  `calories`, `elevation_gain_m`, `aerobic_training_effect`,
  `anaerobic_training_effect`, `training_load`.
- **`weigh_ins`**: `date`, `weight_kg`, `bmi`, `body_fat_pct`, `muscle_mass_kg`.
- **`blood_pressure`**: `measured_local`, `systolic`, `diastolic`, `pulse`, `category`.

`garmin_status.schema` is the authoritative column list.

- **`raw`**: `(date, kind, payload)`, Garmin's original JSON for everything
  else it keeps. Per day: `heart_rate` (all-day samples), `stress` (3-minute
  stress plus the Body Battery series), `body_battery_events`, `spo2`,
  `respiration`, `steps` (15-minute), `floors`, `intensity_minutes`,
  `hydration`, `max_metrics`, `menstrual`, `all_day_events`, plus `sleep`,
  `stats`, `hrv`, `training_status`, `readiness`. Per workout:
  `activity_detail:<id>`, `activity_splits:<id>` (laps), `activity_hr_zones:<id>`,
  `activity_weather:<id>`. Latest-state snapshots, stored once a day:
  `snapshot:race_predictions`, `snapshot:personal_records`,
  `snapshot:endurance_score`, `snapshot:hill_score`,
  `snapshot:lactate_threshold`, `snapshot:fitness_age`, `snapshot:devices`,
  `snapshot:heart_rate_zones`. Run `SELECT DISTINCT kind FROM raw` to see
  what's there. Pull fields out with SQLite JSON functions rather than
  fetching whole payloads.
- Each workout's original recording is also saved as a zipped `.fit` file in
  `~/.garmin-stats-skills/activities/`.

## Example queries

```sql
-- last night
SELECT sleep_score, sleep_min, deep_min, rem_min, hrv_last_night_ms, hrv_status
FROM daily WHERE date = date('now','localtime');

-- 30-day trend
SELECT date, resting_hr, hrv_last_night_ms, sleep_score, stress_avg
FROM daily WHERE date >= date('now','localtime','-29 days') ORDER BY date;

-- this week vs last week
SELECT CASE WHEN date >= date('now','localtime','-6 days') THEN 'this week' ELSE 'last week' END AS wk,
       round(avg(sleep_min)/60.0,1) AS sleep_h, round(avg(hrv_last_night_ms)) AS hrv,
       round(avg(resting_hr)) AS rhr, sum(steps) AS steps
FROM daily WHERE date >= date('now','localtime','-13 days') GROUP BY wk;

-- hydration (from raw JSON)
SELECT date, json_extract(payload, '$.valueInML') AS ml
FROM raw WHERE kind = 'hydration' ORDER BY date DESC LIMIT 14;

-- latest race predictions
SELECT payload FROM raw WHERE kind = 'snapshot:race_predictions' ORDER BY date DESC LIMIT 1;

-- running by month
SELECT strftime('%Y-%m', date) AS month, count(*) AS runs, round(sum(distance_km),1) AS km,
       round(avg(avg_pace_min_per_km),2) AS pace
FROM activities WHERE type LIKE '%running%' GROUP BY month ORDER BY month;
```

## Reading the data honestly

- **NULL means no data** (watch not worn, feature unsupported, not synced),
  never zero. Say "no data for Tuesday". Exclude NULLs from averages (SQL
  `avg()` already does) and mention gaps.
- Today's totals are partial until the day ends, and only include what the
  watch has synced to the Garmin Connect phone app.
- `training_status`, `readiness_*` and `acwr_status` are Garmin's own labels:
  attribute them ("Garmin rates you *productive*"). Training load 0 on a
  rest day is real.
- HRV is personal: compare it with the user's `hrv_baseline_low_ms`–
  `hrv_baseline_high_ms` and recent average, not with population norms.
- Lead with the numbers (a small table or chart), then the pattern, then caveats.

## Boundaries

This is the user's own data, for their own insight. Describe what it shows
and don't diagnose. If something looks medically concerning (very high blood
pressure, resting HR far above their normal, persistently low SpO2), say
plainly that it's worth raising with a doctor.
