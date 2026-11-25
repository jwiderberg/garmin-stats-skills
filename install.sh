#!/bin/bash
# Garmin Stats for Claude: installer for macOS.
#
#   curl -fsSL https://raw.githubusercontent.com/jwiderberg/garmin-stats-skills/main/install.sh | bash
#
# Safe to run again at any time; that's also how you update.
# Developer options: --ref <branch|tag>, --no-setup, --no-claude-code, --yes
set -euo pipefail

REPO="${GARMIN_STATS_REPO:-jwiderberg/garmin-stats-skills}"
REF="main"
DO_SETUP=1
DO_CLAUDE_CODE=1
ASSUME_YES=0
while [ $# -gt 0 ]; do
    case "$1" in
        --ref) REF="$2"; shift ;;
        --no-setup) DO_SETUP=0 ;;
        --no-claude-code) DO_CLAUDE_CODE=0 ;;
        --yes|-y) ASSUME_YES=1 ;;
        *) echo "Unknown option: $1" >&2; exit 2 ;;
    esac
    shift
done

APP_HOME="${GARMIN_STATS_HOME:-$HOME/.garmin-stats-skills}"
INTERACTIVE=0   # typing possible: a real Terminal window
[ -t 0 ] && [ -t 1 ] && INTERACTIVE=1
GUI=1           # Mac windows possible: logged-in desktop, not SSH or CI
{ [ -n "${SSH_CONNECTION:-}" ] || [ -n "${CI:-}" ]; } && GUI=0

B=""; D=""; G=""; Y=""; R=""; N=""
if [ -t 1 ]; then
    B=$'\033[1m'; D=$'\033[2m'; G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; N=$'\033[0m'
fi
step() { printf '\n%s%s%s\n' "$B" "$*" "$N"; }
say()  { printf '   %s\n' "$*"; }
note() { printf '   %s%s%s\n' "$D" "$*" "$N"; }
ok()   { printf '   %s✓%s %s\n' "$G" "$N" "$*"; }
warn() { printf '   %s!%s %s\n' "$Y" "$N" "$*"; }
fail() {
    printf '\n   %s✗ %s%s\n' "$R" "$*" "$N" >&2
    printf '   Nothing was changed that could break anything. Run the installer again to retry.\n' >&2
    exit 1
}
trap 'printf "\n"; warn "Installer stopped. Run it again any time to pick up where it left off."; exit 130' INT

[ "$(uname -s)" = "Darwin" ] || fail "This installer is for macOS."

# From a downloaded copy of the repo? Install that copy.
SRC=""
if [ -n "${BASH_SOURCE[0]:-}" ] && [ -f "${BASH_SOURCE[0]}" ]; then
    _dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    grep -qs 'name = "garmin-stats-skills"' "$_dir/pyproject.toml" && SRC="$_dir"
fi
# Otherwise install from GitHub as an archive: no git or Xcode tools needed.
PKG="${SRC:-garmin-stats-skills @ https://github.com/${REPO}/archive/refs/heads/${REF}.tar.gz}"

cat <<EOF

${B}Garmin Stats for Claude${N}

This sets up Claude so it can answer questions about your Garmin data.
Here's what will happen:

  1. Install a small helper program (in your user folder; no admin password)
  2. Sign in to Garmin, in a normal Mac window
  3. Choose how many days of history to import: 30, 60 or 90
  4. Import everything Garmin keeps, slowly, so Garmin doesn't block you
  5. Create the plugin file you add to Claude

Everything stays on this Mac. Your Garmin password is never saved.
EOF

if [ "$INTERACTIVE" = 1 ] && [ "$ASSUME_YES" = 0 ]; then
    printf '\n%sPress Return to start%s (or Ctrl-C to cancel) ' "$B" "$N"
    read -r _ </dev/tty || true
fi

# ── 1 ─────────────────────────────────────────────────────────────────────
step "Step 1 of 5 · Installing the helper"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
if command -v uv >/dev/null 2>&1; then
    ok "uv already installed ($(uv --version | awk '{print $2}'))"
else
    say "Downloading uv, the tool that installs and runs the helper…"
    note "(from astral.sh; it lives in ~/.local/bin and doesn't touch the rest of your Mac)"
    curl -LsSf https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 sh >/dev/null 2>&1 \
        || fail "Couldn't download uv. Check your internet connection."
    ok "uv installed"
fi
UV="$(command -v uv)" || fail "uv didn't install."

say "Installing Garmin Stats (and a private copy of Python, if needed)…"
note "(first time this can take a minute)"
"$UV" tool install --quiet --force --reinstall --python 3.12 "$PKG" >/dev/null 2>&1 \
    || "$UV" tool install --force --reinstall --python 3.12 "$PKG" \
    || fail "Couldn't install Garmin Stats."
EXE="$("$UV" tool dir --bin)/garmin-stats"
[ -x "$EXE" ] || fail "Garmin Stats didn't install correctly."
mkdir -p "$APP_HOME" && chmod 700 "$APP_HOME"
cat > "$APP_HOME/run-mcp.sh" <<EOF
#!/bin/sh
# Started by Claude. Rewritten each time install.sh runs.
export GARMIN_STATS_HOME="$APP_HOME"
exec "$EXE" mcp "\$@"
EOF
chmod 755 "$APP_HOME/run-mcp.sh"
ok "$("$EXE" --version) installed"
note "Your data and settings will live in $APP_HOME"

# ── 2–4 ───────────────────────────────────────────────────────────────────
step "Steps 2–4 of 5 · Garmin sign-in and first import"
if [ "$DO_SETUP" = 1 ]; then
    say "A window will ask for your Garmin email and password. If Garmin emails"
    say "you a code, a second window asks for that. The password goes only to Garmin."
    echo
    if [ "$GUI" = 1 ]; then          # sign-in + choice in Mac windows; no typing here
        GARMIN_STATS_HOME="$APP_HOME" "$EXE" setup </dev/null || true
    elif [ "$INTERACTIVE" = 1 ]; then  # e.g. over SSH: ask in this terminal
        GARMIN_STATS_HOME="$APP_HOME" "$EXE" setup --terminal || true
    else
        warn "No screen or keyboard here, so the sign-in is skipped."
    fi
else
    ok "skipped (--no-setup)"
fi

# ── 5 ─────────────────────────────────────────────────────────────────────
step "Step 5 of 5 · Adding it to Claude"
if [ "$DO_CLAUDE_CODE" = 1 ] && command -v claude >/dev/null 2>&1; then
    say "Claude Code found; adding the plugin there too…"
    MP="${SRC:-$REPO}"
    claude plugin marketplace list 2>/dev/null | grep -q garmin-stats-skills \
        && claude plugin marketplace update garmin-stats-skills >/dev/null 2>&1 \
        || claude plugin marketplace add "$MP" >/dev/null 2>&1 || true
    if claude plugin install garmin-stats-skills@garmin-stats-skills >/dev/null 2>&1 \
        || claude plugin update garmin-stats-skills@garmin-stats-skills >/dev/null 2>&1; then
        ok "added to Claude Code"
    else
        warn "couldn't add it to Claude Code automatically (not needed for the Claude app)"
    fi
fi
ZIP="$(GARMIN_STATS_HOME="$APP_HOME" "$EXE" plugin-zip)" || fail "Couldn't build the plugin file."
ok "plugin file created: $ZIP"

SIGNED_IN=0; SYNCING=0
GARMIN_STATS_HOME="$APP_HOME" "$EXE" status >/dev/null 2>&1 && SIGNED_IN=1
[ -f "$HOME/Library/LaunchAgents/com.garmin-stats-skills.sync.plist" ] && SYNCING=1

echo
if [ "$SIGNED_IN" = 1 ]; then
    printf '%sDone. One last step, in the Claude app:%s\n' "$B" "$N"
else
    printf '%sInstalled, but not connected to Garmin yet.%s\n' "$Y" "$N"
    say "Nothing was imported. Sign in later in either of these ways:"
    say "  • in Claude, once the plugin is added: ask \"connect my Garmin\""
    say "  • or run this installer again"
    echo
    printf '%sTo add it to the Claude app:%s\n' "$B" "$N"
fi
cat <<EOF

   1. Click ${B}Customize${N} (left sidebar), then ${B}Plugins${N}
   2. Click ${B}Upload plugin${N} and choose ${B}Garmin-Stats.zip${N}
      (it's in $APP_HOME; a Finder window shows it)

   Then ask Claude: ${B}"How did I sleep last night?"${N}

EOF
if [ "$SYNCING" = 1 ]; then
    say "• Every hour your Mac fetches new Garmin data in the background."
    say "• If Garmin signs you out, you'll get a notification; ask Claude to reconnect."
else
    say "• The hourly background sync switches on after you sign in."
fi
say "• To update: run this installer again. To remove everything:"
say "  curl -fsSL https://raw.githubusercontent.com/$REPO/main/uninstall.sh | bash"

[ "$GUI" = 1 ] || exit 0
open -R "$ZIP" 2>/dev/null || true
if [ "$SIGNED_IN" = 1 ]; then
    MSG="Garmin Stats is installed and your data is importing.

One last step, in the Claude app:
  1. Customize → Plugins
  2. Upload plugin → choose Garmin-Stats.zip
     (the Finder window behind this one is showing it)

Then ask Claude: How did I sleep last night?"
else
    MSG="Garmin Stats is installed, but not connected to Garmin yet.

Add it to the Claude app (Customize → Plugins → Upload plugin → Garmin-Stats.zip), then ask Claude: connect my Garmin"
fi
CHOICE="$(osascript - "$MSG" <<'OSA' 2>/dev/null || true
on run argv
    button returned of (display dialog (item 1 of argv) with title "Garmin Stats" buttons {"Done", "Open Claude"} default button "Open Claude" with icon note giving up after 600)
end run
OSA
)"
if [ "$CHOICE" = "Open Claude" ]; then
    open -a Claude 2>/dev/null || open "https://claude.ai/download"
fi
