# garmin-stats-skills

Ask Claude about **your own Garmin data**: sleep, HRV, resting heart rate,
stress, Body Battery, steps, workouts, training status and load, Training
Readiness, VO2max, race predictions, weight and blood pressure.

It's a plugin for **Claude Cowork** and **Claude Code**. It has two parts:

- a small **MCP server** that runs on your computer and reads Garmin Connect
  with your own login, using
  [python-garminconnect](https://github.com/cyberjunky/python-garminconnect)
- a **skill** that teaches Claude which tool answers which question, and how
  to read the numbers honestly (gaps are gaps, not zeros)

The plugin is read-only: nothing is written to your Garmin account. Your
password goes only to Garmin, once, at login. After that, only Garmin's
session token is kept, in `~/.garmin-stats-skills/` and readable only by you.

> Garmin has no official personal API. This uses the same unofficial login
> the Garmin Connect app uses, so Garmin could change it at any time. Use it
> for your own account only.

## Install (macOS / Linux)

### 1. Run the installer in Terminal

```bash
curl -fsSL https://raw.githubusercontent.com/jwiderberg/garmin-stats-skills/main/install.sh | bash
```

The installer:

1. installs [uv](https://docs.astral.sh/uv/), if you don't have it
2. installs the `garmin-stats` command; uv fetches Python 3.12 if you need it
3. logs you in to Garmin Connect: email, password, and the MFA code if your account has MFA
4. adds the plugin to Claude Code, if you have it

It's safe to re-run, and re-running is also how you upgrade.

### 2. Add it to Claude Cowork

In the Claude desktop app, go to **Customize → Plugins → Add marketplace**,
then enter:

```
jwiderberg/garmin-stats-skills
```

Install **Garmin Stats**, then ask: *"How did I sleep last night?"*

### Claude Code

The installer handles Claude Code automatically. To do it by hand:

```
/plugin install garmin-stats-skills --marketplace jwiderberg/garmin-stats-skills
```

On older Claude Code versions, use `/plugin marketplace add jwiderberg/garmin-stats-skills`,
then `/plugin install garmin-stats-skills@garmin-stats-skills`.

## Things to ask

- "How did I sleep this week compared with last week?"
- "Am I recovered enough for a hard session today?"
- "Show my HRV and resting heart rate trend for the last 30 days."
- "Summarise my running in October: distance, pace, training effect."
- "What's Garmin's training status, and is my load ramping too fast?"
- "Plot my weight since January."

## Tools

| Tool | What it returns |
|---|---|
| `garmin_status` | Whether you're logged in, and as whom |
| `daily_summary(day)` | Steps, calories, intensity minutes, resting HR, stress, Body Battery, SpO2 |
| `daily_range(start, end)` | One row per day (up to 31 per call), merging daily totals, sleep and HRV |
| `sleep(day)` | Score, stages, naps, overnight HRV, sleep HR/stress/SpO2, skin temperature |
| `hrv(day)` | Last-night average, weekly average, status, personal baseline |
| `heart_rate(day)`, `stress_and_body_battery(day)` | All-day detail |
| `activities(start, end, type)` | Workouts, up to a year per call |
| `activity_detail(id)` | One workout, with optional laps/splits |
| `training_status(day)` | Status, 7-day acute vs 28-day chronic load, ACWR, VO2max, load balance |
| `training_readiness(day)` | Readiness score and its contributing factors |
| `performance()` | VO2max, fitness age, race predictions, personal records |
| `body_composition(start, end)`, `blood_pressure(start, end)` | Weigh-ins and BP readings |
| `garmin_raw(method, args)` | Any allow-listed read-only garminconnect method, as a raw response |

Every tool accepts `raw=true` to return Garmin's full payload instead of the compact view.
Days before yesterday are cached locally, so repeated questions don't hit Garmin again.

## Command line

```
garmin-stats login [--force]   log in, or log in again (handles MFA)
garmin-stats status            check the saved session
garmin-stats logout            delete the saved session
garmin-stats call get_stats 2026-11-20   print a raw response
garmin-stats clear-cache
```

## Troubleshooting

- **"Not logged in" / "session is no longer valid"**: run `garmin-stats login`.
  Garmin occasionally expires sessions, and changing your password also ends them.
- **"rate-limiting"**: Garmin throttles logins and bursts of requests. Wait
  10–15 minutes, and don't retry in a loop.
- **Cowork says the Garmin server failed to start**: the installer hasn't run
  on this computer yet. Run step 1.
- **No data for today**: sync your watch in the Garmin Connect app first.

## Uninstall

```bash
curl -fsSL https://raw.githubusercontent.com/jwiderberg/garmin-stats-skills/main/uninstall.sh | bash
```

Then remove **Garmin Stats** in Cowork, under **Customize → Plugins**.

## Development

```bash
uv sync --extra dev
uv run pytest
./install.sh --no-login      # install this checkout
claude plugin validate .
```

MIT licensed. Not affiliated with Garmin.
