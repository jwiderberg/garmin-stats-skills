# Garmin Stats for Claude

Ask Claude about your own Garmin data: sleep, HRV, resting heart rate, stress,
Body Battery, steps, workouts, training load, VO2max, weight and blood pressure.

I wanted to ask *"am I recovered enough for a hard session?"* and get an answer
grounded in my own numbers, not a generic one. Garmin has no personal API, so
this does it the practical way: it copies your data to your Mac every hour and
lets Claude query that copy.

Works in the Claude desktop app (Cowork) and Claude Code. macOS only.

## Install

1. Open **Terminal** (⌘ Space, type *Terminal*, Return).
2. Paste this and press Return:

   ```
   curl -fsSL https://raw.githubusercontent.com/jwiderberg/garmin-stats-skills/main/install.sh | bash
   ```

3. Sign in to Garmin in the window that pops up. If Garmin emails you a code,
   enter that too.
4. A Finder window opens with **Garmin-Stats.zip**. In Claude, go to
   **Customize → Plugins → Upload plugin** and choose it.

Then ask Claude *"How did I sleep last night?"*

The whole thing takes about two minutes. You don't need Python or developer
tools; the installer sets up everything it needs.

## What you can ask

- *How did I sleep this week compared with last?*
- *Is my HRV trending down?*
- *Summarise my running since September.*
- *What does Garmin say my training status is, and is my load ramping too fast?*
- *Plot my weight and resting heart rate since January.*

## How it works

- **Sync.** A background job on your Mac pulls from Garmin Connect every hour.
  On the first run it takes the last two weeks, then backfills the rest of the
  year a bit at a time, so Garmin doesn't throttle it.
- **Cache.** Everything lands in one SQLite file in `~/.garmin-stats-skills/`.
  Claude reads that file, so answers are instant and don't touch Garmin.
- **Skill.** The plugin gives Claude five read-only tools (status, SQL query,
  raw payload, sync now, sign in) and a skill that explains the data, including
  the parts that are easy to get wrong: a missing day is a gap, not a zero, and
  last night's sleep is filed under today.

## Your data

- Your password goes to Garmin once and is never stored. Only Garmin's sign-in
  token is kept on your Mac, readable by you alone.
- Nothing is sent anywhere else, and nothing is ever written back to Garmin.
- If Garmin signs you out, you get a notification. Tell Claude *"reconnect my
  Garmin"* and the sign-in window comes back.

This uses the same unofficial sign-in as the Garmin Connect app, via
[python-garminconnect](https://github.com/cyberjunky/python-garminconnect).
Garmin can change that whenever it likes. Use it for your own account.

## Settings

`~/.garmin-stats-skills/config.toml` (in Finder: ⌘⇧G, paste the path):

| Setting | Default | |
|---|---|---|
| `history_days` | `365` | how much history to keep |
| `sync_interval_minutes` | `60` | how often to sync (then run `garmin-stats schedule`) |
| `store_raw` | `true` | keep Garmin's full detail: minute-level sleep, HR samples, splits |
| `db_path` | `~/.garmin-stats-skills/garmin.db` | where the cache lives |

## Update, uninstall

To **update**, run the install line again and upload the new zip. If you'd
rather have updates arrive on their own, add `jwiderberg/garmin-stats-skills`
under **Customize → Plugins → Add marketplace** instead of uploading the zip.

To **uninstall**, run this, then remove the plugin in Claude:

```
curl -fsSL https://raw.githubusercontent.com/jwiderberg/garmin-stats-skills/main/uninstall.sh | bash
```

## Under the hood

A local stdio MCP server (`garmin-stats mcp`), a launchd agent running
`garmin-stats sync`, and a skill in `skills/garmin-stats`. The command line is
there if you want it:

```
garmin-stats status | sync [--days N] | login | schedule [--off] | plugin-zip | logout
```

```bash
uv sync --extra dev && uv run pytest    # tests
./install.sh --no-setup                 # install this checkout
```

Releases attach `Garmin-Stats.zip`. MIT licence. Not affiliated with Garmin.
