"""Garmin Connect access: login, a reusable session, and a small disk cache.

Login is interactive and happens once, in a terminal (`garmin-stats login`):
email + password (+ MFA code if the account has it). garminconnect writes a
token file; the password is never stored. Everything else — the MCP server
in particular — runs *tokens only*: it never has a password, and an MFA
challenge fails fast with instructions instead of hanging.

Past days don't change once Garmin has processed them, so date-keyed calls
for days before yesterday are cached on disk. That keeps repeated questions
("compare this month to last month") cheap and well clear of Garmin's rate
limits. Today and yesterday are always fetched live.
"""

from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectTooManyRequestsError,
)

from garmin_stats import paths

LOGIN_HINT = "Open Terminal and run:  garmin-stats login"


class NotLoggedIn(RuntimeError):
    """No usable Garmin session on this computer."""


class RateLimited(RuntimeError):
    """Garmin answered 429/427."""


# ─────────────────────────── login ───────────────────────────


def login(
    email: str,
    password: str,
    prompt_mfa: Callable[[], str],
    force: bool = False,
) -> str:
    """Interactive login. Saves tokens under paths.token_dir(); returns the
    account's display name. `force` discards any existing session first."""
    tdir = paths.token_dir()
    tdir.mkdir(parents=True, exist_ok=True)
    if force:
        paths.token_file().unlink(missing_ok=True)
    client = Garmin(email, password, prompt_mfa=prompt_mfa)
    client.login(str(tdir))
    paths.secure(tdir)
    return client.get_full_name() or email


def logout() -> bool:
    """Delete the saved session. Returns True if there was one."""
    f = paths.token_file()
    existed = f.exists()
    f.unlink(missing_ok=True)
    return existed


def _no_mfa() -> str:
    raise NotLoggedIn(f"Garmin is asking for an MFA code. {LOGIN_HINT}")


def session_client() -> Garmin:
    """Tokens-only client for unattended use (MCP server)."""
    if not paths.token_file().exists():
        raise NotLoggedIn(f"Not logged in to Garmin on this computer. {LOGIN_HINT}")
    client = Garmin(prompt_mfa=_no_mfa)
    try:
        client.login(str(paths.token_dir()))
    except GarminConnectAuthenticationError as e:
        raise NotLoggedIn(f"The saved Garmin session is no longer valid ({e}). {LOGIN_HINT}") from e
    except GarminConnectTooManyRequestsError as e:
        raise RateLimited(
            "Garmin is rate-limiting this computer; try again in a few minutes."
        ) from e
    paths.secure(paths.token_dir())
    return client


# ─────────────────────────── calls ───────────────────────────


class GarminData:
    """Lazily logged-in client + cached calls. One per process."""

    def __init__(
        self,
        factory: Callable[[], Any] = session_client,
        today: Callable[[], date] = date.today,
    ) -> None:
        self._factory = factory
        self._today = today
        self._client: Any = None
        self._lock = threading.Lock()

    def today(self) -> date:
        return self._today()

    def _get(self) -> Any:
        with self._lock:
            if self._client is None:
                self._client = self._factory()
            return self._client

    def call(self, method: str, *args: Any, cache_until: date | None = None, **kwargs: Any) -> Any:
        """Call a garminconnect method. When `cache_until` (the newest date the
        result depends on) is before yesterday, the result is cached on disk."""
        cacheable = cache_until is not None and cache_until < self.today() - timedelta(days=1)
        key_path = None
        if cacheable:
            key = json.dumps([method, args, kwargs], sort_keys=True, default=str)
            digest = hashlib.sha256(key.encode()).hexdigest()[:24]
            key_path = paths.cache_dir() / method / f"{digest}.json"
            if key_path.exists():
                try:
                    return json.loads(key_path.read_text())
                except ValueError:
                    key_path.unlink(missing_ok=True)

        result = self._invoke(method, *args, **kwargs)

        if key_path is not None and result not in (None, {}, []):
            key_path.parent.mkdir(parents=True, exist_ok=True)
            key_path.write_text(json.dumps(result, default=str))
        return result

    def _invoke(self, method: str, *args: Any, **kwargs: Any) -> Any:
        client = self._get()
        try:
            return getattr(client, method)(*args, **kwargs)
        except GarminConnectTooManyRequestsError as e:
            raise RateLimited("Garmin is rate-limiting requests; wait a few minutes.") from e
        except GarminConnectAuthenticationError:
            # Token may have been rotated underneath us: re-login once from disk.
            with self._lock:
                self._client = None
            client = self._get()
            return getattr(client, method)(*args, **kwargs)


def parse_date(value: str | None, today: date) -> date:
    """'2026-11-20', 'today', 'yesterday', or None (= today)."""
    if value is None or value == "" or value.lower() == "today":
        return today
    if value.lower() == "yesterday":
        return today - timedelta(days=1)
    return date.fromisoformat(value)
