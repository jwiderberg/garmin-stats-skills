# Garmin metrics glossary

Field names are as returned by the `garmin` tools. Units are in the name.

## Daily (`daily_summary`, `daily_range`)

| Field | Meaning |
|---|---|
| `steps`, `step_goal` | Steps for the day and Garmin's (auto-adjusting) goal |
| `distance_km` | Walking/running distance from the step counter |
| `active_kcal`, `total_kcal` | Calories burned above resting / including resting (BMR) |
| `intensity_min_moderate`, `intensity_min_vigorous` | Intensity minutes; Garmin counts vigorous ×2 toward the weekly 150 goal |
| `resting_hr`, `resting_hr_7d_avg` | Lowest 30-min average HR of the day (bpm); 7-day average |
| `stress_avg`, `stress_max` | Garmin stress 0–100 from HRV. 0–25 rest, 26–50 low, 51–75 medium, 76–100 high |
| `body_battery_high/low/at_wake` | Garmin's 0–100 energy estimate; `charged`/`drained` are the day's totals |
| `spo2_avg`, `spo2_lowest` | Blood-oxygen saturation % (only with Pulse Ox enabled) |
| `respiration_avg_waking` | Breaths per minute while awake |

## Sleep (`sleep`)

| Field | Meaning |
|---|---|
| `sleep_score` | 0–100. 90+ excellent, 80–89 good, 60–79 fair, <60 poor (Garmin's bands) |
| `sleep_min`, `deep_min`, `light_min`, `rem_min`, `awake_min` | Minutes in each stage |
| `nap_min` | Daytime naps recorded that day |
| `overnight_hrv_ms` | Average overnight HRV (ms, RMSSD) |
| `hrv_status` | BALANCED / UNBALANCED / LOW / POOR relative to the user's baseline |
| `body_battery_change` | Body Battery recharged overnight |
| `skin_temp_deviation_c` | Deviation from the user's baseline skin temperature (supported watches) |

## HRV (`hrv`)

`last_night_avg_ms` vs the personal `baseline_low_ms`–`baseline_high_ms`
(Garmin's "balanced" range, built from ~3 weeks of data) and `weekly_avg_ms`.
A single low night matters less than a run of nights below baseline.

## Training (`training_status`, `training_readiness`, `activities`)

| Field | Meaning |
|---|---|
| `status` | Garmin's label: PRODUCTIVE, MAINTAINING, PEAKING, RECOVERY, UNPRODUCTIVE, DETRAINING, STRAINED, OVERREACHING |
| `acute_load_7d` | Garmin's 7-day acute training load (EPOC-based) |
| `chronic_load_28d` | 28-day chronic load (the fitness base) |
| `acute_chronic_ratio`, `acwr_status` | Acute ÷ chronic and Garmin's verdict (LOW / OPTIMAL / HIGH / VERY_HIGH) |
| `vo2max`, `fitness_age` | Estimated VO2max (ml/kg/min) and Garmin's fitness age |
| `monthly_load_*` | 4-week load split into low aerobic / high aerobic / anaerobic |
| readiness `score`, `level` | 0–100 Training Readiness and its band, with factor percentages |
| `aerobic_training_effect`, `anaerobic_training_effect` | 0–5 per workout (3–4 = improving) |
| `training_load` (activity) | That workout's EPOC load contribution |

## Body (`body_composition`, `blood_pressure`)

Weigh-ins are only what the user logged (scale or manual). Body-fat and
muscle fields need a smart scale. Blood pressure is manual entries or a
connected cuff; `category` is Garmin's classification.
