"""Garmin Connect login and a tokens-only session.

Login happens once (`garmin-stats login`, or the `garmin_connect` tool from
Claude): email + password (+ MFA code). garminconnect writes a token file;
the password is never stored. The hourly sync and everything else run
tokens-only, and an MFA challenge there fails fast instead of hanging.
"""

from __future__ import annotations

from collections.abc import Callable

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectTooManyRequestsError,
)

from garmin_stats import paths

LOGIN_HINT = 'Ask Claude to "reconnect my Garmin", or run: garmin-stats login'


class NotLoggedIn(RuntimeError):
    """No usable Garmin session on this computer."""


class RateLimited(RuntimeError):
    """Garmin answered 429/427."""


def login(email: str, password: str, prompt_mfa: Callable[[], str], force: bool = False) -> str:
    """Interactive login; saves tokens and returns the account's name."""
    tdir = paths.token_dir()
    tdir.mkdir(parents=True, exist_ok=True)
    if force:
        paths.token_file().unlink(missing_ok=True)
    try:
        client = Garmin(email, password, prompt_mfa=prompt_mfa)
        client.login(str(tdir))
    except GarminConnectTooManyRequestsError as e:
        raise RateLimited(
            "Garmin is limiting sign-ins right now. Wait 15 minutes and try again."
        ) from e
    paths.secure(tdir)
    return client.get_full_name() or email


def logout() -> bool:
    f = paths.token_file()
    existed = f.exists()
    f.unlink(missing_ok=True)
    return existed


def _no_mfa() -> str:
    raise NotLoggedIn(f"Garmin is asking for a new sign-in code. {LOGIN_HINT}")


def session_client() -> Garmin:
    """Tokens-only client for unattended use (sync, MCP server)."""
    if not paths.token_file().exists():
        raise NotLoggedIn(f"Not signed in to Garmin on this Mac. {LOGIN_HINT}")
    client = Garmin(prompt_mfa=_no_mfa)
    try:
        client.login(str(paths.token_dir()))
    except GarminConnectAuthenticationError as e:
        raise NotLoggedIn(f"The Garmin sign-in has expired. {LOGIN_HINT}") from e
    except GarminConnectTooManyRequestsError as e:
        raise RateLimited(
            "Garmin is rate-limiting this Mac; the next hourly sync will retry."
        ) from e
    paths.secure(paths.token_dir())
    return client
