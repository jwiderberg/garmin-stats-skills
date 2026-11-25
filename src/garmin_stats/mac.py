"""Native macOS UI via osascript: sign-in dialogs and notifications, so
nobody has to type into a terminal."""

from __future__ import annotations

import subprocess
import sys


def is_mac() -> bool:
    return sys.platform == "darwin"


def _q(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


class Cancelled(RuntimeError):
    pass


def ask(prompt: str, hidden: bool = False, default: str = "") -> str:
    """Modal text dialog. Raises Cancelled if the user clicks Cancel."""
    script = (
        f"display dialog {_q(prompt)} default answer {_q(default)}"
        f'{" with hidden answer" if hidden else ""} with title "Garmin Stats" '
        'buttons {"Cancel", "OK"} default button "OK" with icon note'
    )
    r = subprocess.run(
        ["osascript", "-e", f"text returned of ({script})"],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        raise Cancelled("Sign-in cancelled.")
    return r.stdout.rstrip("\n")


def notify(message: str, title: str = "Garmin Stats") -> None:
    subprocess.run(
        ["osascript", "-e", f"display notification {_q(message)} with title {_q(title)}"],
        capture_output=True,
    )


def alert(message: str) -> None:
    subprocess.run(
        [
            "osascript",
            "-e",
            f'display dialog {_q(message)} with title "Garmin Stats" buttons {{"OK"}} '
            'default button "OK" with icon note',
        ],
        capture_output=True,
    )


def choose(prompt: str, buttons: list[str], default: str) -> str:
    """Dialog with up to three buttons; returns the one clicked."""
    btns = ", ".join(_q(b) for b in buttons)
    script = (
        f'display dialog {_q(prompt)} with title "Garmin Stats" '
        f"buttons {{{btns}}} default button {_q(default)} with icon note"
    )
    r = subprocess.run(
        ["osascript", "-e", f"button returned of ({script})"],
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode != 0:
        raise Cancelled("Cancelled.")
    return r.stdout.strip()
