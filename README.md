# Garmin Stats for Claude

Ask Claude about your own Garmin data, all of it: sleep, HRV, heart rate,
stress, Body Battery, SpO2, respiration, steps, workouts (with laps, HR zones
and the original FIT files), training status and load, Training Readiness,
VO2max, race predictions, personal records, weight, blood pressure, hydration
and cycle tracking.

I wanted to ask *"am I recovered enough for a hard session?"* and get an answer
grounded in my own numbers, not a generic one. It's my data, so I want all of
it. Garmin's official Personal API leaves out training status, Training
Readiness, blood pressure and race predictions, so this takes the same route
the Garmin Connect app does. It copies everything to your Mac every hour and
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
4. Pick how much history to import: 30, 60 or 90 days. You'll see each day
   arrive as it's saved.
5. A Finder window opens with **Garmin-Stats.zip**. In Claude: **Settings →
   Plugins**, scroll down to **Browse plugins**, then **Add** (top right) →
   **Upload plugin**. Drag the zip in and click **Upload**.
6. Claude warns that *"This plugin includes local MCP servers"*. That's
   expected: the server is the helper you just installed, reading the data on
   your Mac. Click **Continue**.

Then ask Claude *"How did I sleep last night?"*

The import is deliberately slow, about half a minute per day (30 days takes
roughly 15 minutes, 90 days about 40), because it fetches everything and
hammering Garmin gets you blocked. You can close Terminal at any point;
whatever's left carries on in the background. You don't need Python or
developer tools: the installer explains each step and sets up everything itself.

## What you can ask

- *How did I sleep this week compared with last?*
- *Is my HRV trending down?*
- *Summarise my running since September.*
- *What does Garmin say my training status is, and is my load ramping too fast?*
- *Plot my weight and resting heart rate since January.*

## How it works

- **Sync.** A background job on your Mac pulls the latest from Garmin Connect
  every hour. Requests are spaced at least a second apart, with some random
  jitter. If Garmin still says slow down, it backs off and tries again later
  rather than pushing.
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
- When the hourly sync is switched on, macOS shows *"garmin-stats can run in
  the background"*. That's expected. You can turn it off under System
  Settings → General → Login Items & Extensions.
- If Garmin signs you out, you get a notification. Tell Claude *"reconnect my
  Garmin"* and the sign-in window comes back.

This uses the same unofficial sign-in as the Garmin Connect app, via
[python-garminconnect](https://github.com/cyberjunky/python-garminconnect).
Garmin can change that whenever it likes. Use it for your own account.

## Settings

`~/.garmin-stats-skills/config.toml` (in Finder: ⌘⇧G, paste the path):

| Setting | Default | |
|---|---|---|
| `history_days` | your choice at install (30/60/90) | how much history to keep; raise it and older days backfill gradually |
| `detail` | `full` | `full` = everything Garmin keeps; `core` = sleep, HRV, daily totals, training (about 3× faster) |
| `download_fit` | `true` | save each workout's original recording in `activities/` |
| `request_delay_seconds` | `1.0` | minimum gap between Garmin requests (don't go lower) |
| `sync_interval_minutes` | `60` | how often to sync (then run `garmin-stats schedule`) |
| `store_raw` | `true` | keep Garmin's full detail: minute-level sleep, HR samples, splits |
| `db_path` | `~/.garmin-stats-skills/garmin.db` | where the cache lives |

## Update, uninstall

To **update**, run the install line again and upload the new zip. If you'd
rather have updates arrive on their own, add the plugin as a marketplace
instead: **Settings → Plugins → Browse plugins → Add → Add marketplace**, and
paste `https://github.com/jwiderberg/garmin-stats-skills`.

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

Releases attach `Garmin-Stats.zip`.

## Licence and credits

MIT. See [LICENSE](LICENSE). Not affiliated with or endorsed by Garmin.

Built on other people's good work:

- [python-garminconnect](https://github.com/cyberjunky/python-garminconnect)
  by Ron Klinkien and contributors (MIT): all the hard work of talking to
  Garmin Connect
- [curl_cffi](https://github.com/lexiforest/curl_cffi) (MIT), which
  garminconnect uses to sign in
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) (MIT):
  the server Claude talks to
- [uv](https://github.com/astral-sh/uv) by Astral (MIT/Apache-2.0): installs
  the helper and its Python

The full dependency list, with licences, is in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
