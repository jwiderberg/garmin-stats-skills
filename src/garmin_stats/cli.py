"""`garmin-stats` command line. Beginners never need it: the installer runs
`garmin-stats setup`, and Claude handles re-sign-in via garmin_connect.

    garmin-stats setup             sign in, first sync, start hourly sync
    garmin-stats login [--terminal]  sign in (macOS dialogs by default)
    garmin-stats sync [--days N]   sync now
    garmin-stats status            sign-in + cache summary
    garmin-stats schedule [--off]  start/stop the background sync
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


def cmd_setup(args: argparse.Namespace) -> int:
    cfg = config.load()
    needs_login = args.relogin or not paths.token_file().exists()
    if needs_login and not do_login(args.terminal):
        return 1
    print("Downloading your recent Garmin data (about a minute)…")
    r = sync.run(cfg, days=cfg.refresh_days + cfg.backfill_per_run)
    if not r["ok"]:
        print(f"Sync problem: {r.get('message')}", file=sys.stderr)
        return 1
    print(f"✓ Saved {r['refreshed']} days and {r['activities']} activities.")
    if mac.is_mac():
        schedule.install(cfg.sync_interval_minutes)
        print(
            f"✓ Background sync every {cfg.sync_interval_minutes} minutes "
            f"(older history fills in gradually, up to {cfg.history_days} days)."
        )
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
    sub.add_parser("logout").set_defaults(fn=cmd_logout)
    sub.add_parser("mcp").set_defaults(fn=cmd_mcp)
    args = p.parse_args(argv)
    return int(args.fn(args) or 0)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
