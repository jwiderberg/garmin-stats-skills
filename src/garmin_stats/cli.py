"""`garmin-stats` command line.

garmin-stats login [--force]   interactive Garmin login (email, password, MFA)
garmin-stats status            is this computer logged in? (exit 0 = yes)
garmin-stats logout            delete the saved session
garmin-stats mcp               run the MCP server on stdio (Claude starts this)
garmin-stats call METHOD ...   print a raw garminconnect response (debugging)
garmin-stats clear-cache       drop cached past-day responses
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import shutil
import sys

from garmin_stats import __version__, paths


def _tty_input(prompt: str) -> str:
    """Read from the terminal even when stdin is a pipe (curl | bash)."""
    try:
        with open("/dev/tty") as tty:
            sys.stderr.write(prompt)
            sys.stderr.flush()
            return tty.readline().strip()
    except OSError:
        return input(prompt).strip()


def cmd_login(args: argparse.Namespace) -> int:
    from garminconnect import GarminConnectAuthenticationError, GarminConnectTooManyRequestsError

    from garmin_stats import client

    if paths.token_file().exists() and not args.force:
        try:
            name = client.session_client().get_full_name()
            print(f"Already logged in to Garmin as {name}. Use --force to log in again.")
            return 0
        except client.NotLoggedIn:
            print("Saved session is no longer valid; logging in again.")
    email = os.environ.get("GARMIN_EMAIL") or _tty_input("Garmin Connect email: ")
    password = os.environ.get("GARMIN_PASSWORD") or getpass.getpass("Garmin Connect password: ")
    try:
        name = client.login(
            email,
            password,
            prompt_mfa=lambda: _tty_input("Garmin MFA code (check your email/app): "),
            force=args.force,
        )
    except GarminConnectAuthenticationError as e:
        print(f"Login failed: {e}", file=sys.stderr)
        return 1
    except GarminConnectTooManyRequestsError:
        print(
            "Garmin is rate-limiting logins from this network. Wait 10-15 minutes and retry.",
            file=sys.stderr,
        )
        return 1
    print(f"Logged in to Garmin as {name}.")
    print(
        f"Session saved to {paths.token_file()} (readable only by you). Your password was not stored."
    )
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    from garmin_stats import client

    if not paths.token_file().exists():
        if not args.quiet:
            print("Not logged in. Run: garmin-stats login")
        return 1
    try:
        name = client.session_client().get_full_name()
    except (client.NotLoggedIn, client.RateLimited) as e:
        if not args.quiet:
            print(str(e))
        return 1
    if not args.quiet:
        print(f"Logged in to Garmin as {name}.")
    return 0


def cmd_logout(_: argparse.Namespace) -> int:
    from garmin_stats import client

    print("Logged out." if client.logout() else "No saved session.")
    return 0


def cmd_mcp(_: argparse.Namespace) -> int:
    from garmin_stats import server

    server.serve()
    return 0


def cmd_call(args: argparse.Namespace) -> int:
    from garmin_stats import client
    from garmin_stats.server import RAW_ALLOWED

    if args.method not in RAW_ALLOWED:
        print(f"Not an allowed read-only method: {args.method}", file=sys.stderr)
        return 2
    result = client.GarminData().call(args.method, *args.args)
    print(json.dumps(result, indent=2, default=str))
    return 0


def cmd_clear_cache(_: argparse.Namespace) -> int:
    shutil.rmtree(paths.cache_dir(), ignore_errors=True)
    print("Cache cleared.")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="garmin-stats", description="Your Garmin Connect data for Claude."
    )
    p.add_argument("--version", action="version", version=f"garmin-stats {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("login", help="log in to Garmin Connect (handles MFA)")
    s.add_argument("--force", action="store_true", help="discard any saved session first")
    s.set_defaults(fn=cmd_login)
    s = sub.add_parser("status", help="check the saved session")
    s.add_argument("--quiet", "-q", action="store_true")
    s.set_defaults(fn=cmd_status)
    sub.add_parser("logout", help="delete the saved session").set_defaults(fn=cmd_logout)
    sub.add_parser("mcp", help="run the MCP server on stdio").set_defaults(fn=cmd_mcp)
    s = sub.add_parser("call", help="print a raw garminconnect response")
    s.add_argument("method")
    s.add_argument("args", nargs="*")
    s.set_defaults(fn=cmd_call)
    sub.add_parser("clear-cache", help="drop cached responses").set_defaults(fn=cmd_clear_cache)
    args = p.parse_args(argv)
    return int(args.fn(args) or 0)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
