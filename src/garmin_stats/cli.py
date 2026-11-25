"""`garmin-stats` command line. Beginners never need it: the installer runs
`garmin-stats setup`, and Claude handles re-sign-in via garmin_connect.

    garmin-stats setup             sign in, first sync, start hourly sync
    garmin-stats login [--terminal]  sign in (macOS dialogs by default)
    garmin-stats sync [--days N]   sync now
    garmin-stats status            sign-in + cache summary
    garmin-stats schedule [--off]  start/stop the background sync
    garmin-stats plugin-zip [--reveal]  build "Garmin-Stats.zip" for Cowork
    garmin-stats logout
    garmin-stats mcp               MCP server on stdio (Claude starts this)
"""

from __future__ import annotations

import argparse
import getpass
import sys
from datetime import date

from garmin_stats import __version__, client, config, mac, paths, schedule, sync


def _terminal_prompt(label: str, hidden: bool = False) -> str:
    if hidden:
        return getpass.getpass(label)
    try:
        with open("/dev/tty") as tty:
            sys.stderr.write(label)
            sys.stderr.flush()
            return tty.readline().strip()
    except OSError:
        return input(label).strip()


def do_login(terminal: bool, force: bool = True) -> bool:
    use_dialogs = mac.is_mac() and not terminal
    ask = (lambda p, h=False: mac.ask(p, hidden=h)) if use_dialogs else _terminal_prompt
    try:
        email = ask("Garmin Connect email: ")
        password = ask("Garmin Connect password: ", True)
        name = client.login(
            email,
            password,
            force=force,
            prompt_mfa=lambda: ask("Garmin sent you a verification code. Enter it: "),
        )
    except mac.Cancelled:
        print("Sign-in cancelled.")
        return False
    except Exception as e:  # noqa: BLE001
        msg = f"Sign-in failed: {e}"
        print(msg, file=sys.stderr)
        if use_dialogs:
            mac.alert(msg)
        return False
    print(f"✓ Signed in to Garmin as {name}. (Your password was not saved.)")
    return True


IMPORT_CHOICES = (30, 60, 90)


def _minutes(days: int, cfg: config.Config) -> int:
    per_request = cfg.request_delay_seconds * 1.25 + 0.35  # pacing + Garmin's response time
    return max(1, round(days * sync.calls_per_day(cfg) * per_request / 60))


def _ask_days(terminal: bool) -> int:
    cfg = config.load()
    est = ", ".join(f"{n} days ≈ {_minutes(n, cfg)} min" for n in IMPORT_CHOICES)
    prompt = (
        "How much of your Garmin history should I import now?\n\n"
        f"It downloads everything Garmin keeps, slowly on purpose so Garmin doesn't "
        f"block you: {est}.\n\n"
        "You can close Terminal any time: the rest carries on in the background."
    )
    if mac.is_mac() and not terminal:
        picked = mac.choose(prompt, [f"{n} days" for n in IMPORT_CHOICES], "30 days")
        return int(picked.split()[0])
    print(prompt)
    raw = _terminal_prompt("Days to import [30/60/90, default 30]: ")
    return int(raw) if raw in {str(n) for n in IMPORT_CHOICES} else 30


def _existing_days(cfg: config.Config) -> tuple[int, str | None, str | None]:
    if not cfg.db_path.exists():
        return 0, None, None
    from garmin_stats import db

    conn = db.connect(cfg.db_path)
    try:
        n, lo, hi = conn.execute("SELECT count(*), min(date), max(date) FROM daily").fetchone()
    finally:
        conn.close()
    return n, lo, hi


def cmd_setup(args: argparse.Namespace) -> int:
    from garmin_stats.live import Live

    cfg = config.load()

    # 1. Garmin sign-in
    if args.relogin or not paths.token_file().exists():
        print("→ Signing in to Garmin. Look for the window on your screen.")
        if not do_login(args.terminal):
            return 1
    else:
        print("✓ Already signed in to Garmin.")

    # Already imported before? Then this is an update: don't import again.
    n, lo, hi = _existing_days(cfg)
    if n and not args.reimport:
        print(f"✓ You already have {n} days saved ({lo} → {hi}). Skipping the first import;")
        print("  the hourly sync keeps it fresh. (garmin-stats setup --reimport to redo it.)")
        if mac.is_mac():
            schedule.install(cfg.sync_interval_minutes)
        return 0

    # 2. How much history
    try:
        days = args.days or _ask_days(args.terminal)
    except mac.Cancelled:
        days = 30
    config.set_value("history_days", days)
    cfg = config.load()
    print(f"✓ Keeping {days} days of history (change it later in {config.config_file()}).")

    # 3. Background sync first, so closing Terminal mid-import is safe
    if mac.is_mac():
        print("→ Switching on the hourly background sync.")
        print("  macOS will show a notice: “garmin-stats can run in the background”.")
        print("  That's this sync, and it's expected. You can switch it off any time in")
        print("  System Settings → General → Login Items & Extensions.")
        schedule.install(cfg.sync_interval_minutes)
        print(f"✓ Background sync on: every {cfg.sync_interval_minutes} minutes.")

    # 4. Slow, visible import (newest day first, so the useful part lands first)
    print(f"→ Importing {days} days from Garmin, newest first, one request at a time.")
    print("  You can close this window any time; the rest imports in the background.")
    with Live() as live:
        r = sync.run(cfg, days=days, patient=True, progress=live)
    if r.get("skipped"):
        print("   A background sync is already running; it will finish the import.")
        return 0
    if r.get("interrupted"):
        print(f"✓ Stopped after {r['refreshed']} days. The rest imports in the background.")
        return 0
    if not r["ok"]:
        print(f"! {r.get('message')}", file=sys.stderr)
        print("   What's saved is kept; the background sync will retry later.", file=sys.stderr)
        return 1
    print(f"✓ Imported {r['refreshed']} days and {r['activities']} workouts.")
    return 0


def cmd_login(args: argparse.Namespace) -> int:
    return 0 if do_login(args.terminal) else 1


def cmd_sync(args: argparse.Namespace) -> int:
    r = sync.run(config.load(), days=args.days)
    if not r["ok"]:
        msg = r.get("message", "sync failed")
        # Tell a beginner once a day, not every hour.
        flag = paths.home() / ".notified"
        today = date.today().isoformat()
        if mac.is_mac() and (not flag.exists() or flag.read_text() != today):
            mac.notify(msg)
            flag.write_text(today)
        print(msg, file=sys.stderr)
        return 1
    if not args.quiet:
        print(
            f"✓ {r['refreshed']} days refreshed, {r['backfilled']} backfilled, "
            f"{r['activities']} activities."
        )
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    from garmin_stats.server import garmin_status

    s = garmin_status()
    print(f"Signed in: {'yes' if s['signed_in'] else 'no'}")
    print(f"Background sync: {s['background_sync']}")
    print(f"Last sync: {s['last_sync']}")
    for t, c in s["coverage"].items():
        print(f"  {t}: {c['rows']} rows ({c['first']} → {c['last']})")
    print(f"Settings: {config.config_file()}")
    return 0 if s["signed_in"] else 1


def cmd_schedule(args: argparse.Namespace) -> int:
    if args.off:
        print("Background sync stopped." if schedule.remove() else "It wasn't running.")
    else:
        mins = config.load().sync_interval_minutes
        schedule.install(mins)
        print(f"Background sync every {mins} minutes.")
    return 0


def cmd_plugin_zip(args: argparse.Namespace) -> int:
    from pathlib import Path

    from garmin_stats import plugin_zip

    out = plugin_zip.build(Path(args.out).expanduser() if args.out else None)
    print(out)
    if args.reveal and mac.is_mac():
        import subprocess

        subprocess.run(["open", "-R", str(out)], check=False)
    return 0


def cmd_logout(_: argparse.Namespace) -> int:
    print("Signed out." if client.logout() else "Wasn't signed in.")
    return 0


def cmd_mcp(_: argparse.Namespace) -> int:
    from garmin_stats import server

    server.serve()
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="garmin-stats")
    p.add_argument("--version", action="version", version=f"garmin-stats {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("setup")
    s.add_argument("--terminal", action="store_true")
    s.add_argument("--relogin", action="store_true")
    s.add_argument("--days", type=int, choices=IMPORT_CHOICES, help="skip the question")
    s.add_argument("--reimport", action="store_true", help="import again even if data exists")
    s.set_defaults(fn=cmd_setup)
    s = sub.add_parser("login")
    s.add_argument("--terminal", action="store_true", help="prompt in the terminal, not dialogs")
    s.set_defaults(fn=cmd_login)
    s = sub.add_parser("sync")
    s.add_argument("--days", type=int, default=None, help="refresh the last N days")
    s.add_argument("--quiet", action="store_true")
    s.set_defaults(fn=cmd_sync)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    s = sub.add_parser("schedule")
    s.add_argument("--off", action="store_true")
    s.set_defaults(fn=cmd_schedule)
    s = sub.add_parser("plugin-zip", help="build the Claude plugin zip for Cowork upload")
    s.add_argument("--out", help="output folder (default ~/.garmin-stats-skills)")
    s.add_argument("--reveal", action="store_true", help="show it in Finder")
    s.set_defaults(fn=cmd_plugin_zip)
    sub.add_parser("logout").set_defaults(fn=cmd_logout)
    sub.add_parser("mcp").set_defaults(fn=cmd_mcp)
    args = p.parse_args(argv)
    return int(args.fn(args) or 0)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
