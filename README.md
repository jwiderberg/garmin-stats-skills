# Garmin Stats for Claude

Ask Claude about your own Garmin data, like *"How did I sleep last night?"*,
*"Am I recovered enough to train hard today?"*, or *"How has my running
changed since summer?"*. Claude answers from your sleep, HRV, heart rate,
stress, Body Battery, steps, workouts, training load, VO2max, weight and
blood pressure.

It works in the **Claude desktop app (Cowork)** and **Claude Code** on a Mac.

## Install (about 2 minutes, no technical skills needed)

**1. Open Terminal.** Press **⌘ Space**, type **Terminal**, and press **Return**.

**2. Paste this line and press Return:**

```
curl -fsSL https://raw.githubusercontent.com/jwiderberg/garmin-stats-skills/main/install.sh | bash
```

**3. Sign in to Garmin.** A normal Mac window asks for your Garmin email and
password, and for a code if Garmin emails you one.

**4. Add it to Claude.** When the installer finishes, it copies what you need
and offers to open Claude. In Claude:

1. Click **Customize**, then **Plugins**
2. Click **Add marketplace**, paste (**⌘V**), and press **Return**
3. Click **Install** on **Garmin Stats**

Then ask: *"How did I sleep last night?"*

## How it works

- A small helper on your Mac downloads your Garmin data **every hour** into a
  private file on your Mac. Older history, up to a year, fills in gradually
  over the first day.
- Claude reads that file, so answers are instant.
- Your password goes only to Garmin, once. After that, only Garmin's sign-in
  token is kept, readable only by you. Nothing is ever changed in your Garmin
  account.
- If Garmin ever signs you out, your Mac shows a notification. Just tell
  Claude **"reconnect my Garmin"** and the sign-in window appears again.

> Garmin has no official personal API. This uses the same sign-in the Garmin
> Connect app uses, via
> [python-garminconnect](https://github.com/cyberjunky/python-garminconnect),
> so Garmin could change it at any time. Use it for your own account only.

## Settings

The settings file is `~/.garmin-stats-skills/config.toml`. In Finder, press
**⌘⇧G** and paste that path. You can change:

| Setting | Default | |
|---|---|---|
| `db_path` | `~/.garmin-stats-skills/garmin.db` | where the local copy lives |
| `history_days` | `365` | how much history to keep |
| `sync_interval_minutes` | `60` | how often to sync |
| `store_raw` | `true` | keep Garmin's full detail (minute-level sleep, HR samples, splits) |
| `refresh_days`, `backfill_per_run` | `3`, `14` | how much each sync fetches |

After changing `sync_interval_minutes`, run `garmin-stats schedule` once.

## Update or uninstall

To **update**, run the install line again.

To **uninstall**:

```
curl -fsSL https://raw.githubusercontent.com/jwiderberg/garmin-stats-skills/main/uninstall.sh | bash
```

Then remove **Garmin Stats** in Claude under **Customize → Plugins**.

## For developers

The plugin is a local stdio MCP server, `garmin-stats mcp`, with five tools:

| Tool | Does |
|---|---|
| `garmin_status` | Sign-in state, last sync, coverage, schema |
| `garmin_query(sql)` | Read-only SQL over the local SQLite cache |
| `garmin_raw(day, kind)` | Garmin's full payload for one day |
| `garmin_sync_now(days)` | Sync immediately |
| `garmin_connect()` | Sign in again through native macOS dialogs |

The plugin also ships a skill (`skills/garmin-stats`) that teaches Claude the
schema and how to read the data. A launchd agent
(`com.garmin-stats-skills.sync`) runs `garmin-stats sync` on a schedule.

```
garmin-stats setup | login [--terminal] | sync [--days N] | status | schedule [--off] | logout
```

```bash
uv sync --extra dev && uv run pytest
./install.sh --no-setup        # install this checkout
claude plugin validate .
```

MIT licensed. Not affiliated with Garmin.
