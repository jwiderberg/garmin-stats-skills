#!/bin/bash
# Garmin Stats for Claude: installer for macOS.
#
#   curl -fsSL https://raw.githubusercontent.com/jwiderberg/garmin-stats-skills/main/install.sh | bash
#
# Safe to run again at any time (that's also how you update). It:
#   1. installs uv (Astral's tool that manages Python) if needed
#   2. installs the garmin-stats helper (Python is downloaded automatically)
#   3. asks you to sign in to Garmin in a normal Mac window
#   4. downloads your recent data and turns on the hourly background sync
#   5. adds the plugin to Claude Code if you have it, and builds
#      "Garmin-Stats.zip" to upload in the Claude desktop app (Cowork)
#
# Developer options: --ref <branch|tag>, --no-setup, --no-claude-code
set -euo pipefail

REPO="${GARMIN_STATS_REPO:-jwiderberg/garmin-stats-skills}"
REF="main"
DO_SETUP=1
DO_CLAUDE_CODE=1
while [ $# -gt 0 ]; do
    case "$1" in
        --ref) REF="$2"; shift ;;
        --no-setup) DO_SETUP=0 ;;
        --no-claude-code) DO_CLAUDE_CODE=0 ;;
        *) echo "Unknown option: $1" >&2; exit 2 ;;
    esac
    shift
done

APP_HOME="${GARMIN_STATS_HOME:-$HOME/.garmin-stats-skills}"
step() { printf '\n\033[1m%s\033[0m\n' "$*"; }
ok() { printf '   \033[32m✓\033[0m %s\n' "$*"; }
fail() {
    printf '\n   \033[31m✗ %s\033[0m\n' "$*" >&2
    printf '   Nothing was broken. You can safely run the installer again.\n' >&2
    exit 1
}

[ "$(uname -s)" = "Darwin" ] || fail "This installer is for macOS."

# From a downloaded copy of the repo? Install that copy.
SRC=""
if [ -n "${BASH_SOURCE[0]:-}" ] && [ -f "${BASH_SOURCE[0]}" ]; then
    _dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    grep -qs 'name = "garmin-stats-skills"' "$_dir/pyproject.toml" && SRC="$_dir"
fi
# Otherwise install from GitHub as an archive: no git / Xcode tools needed.
PKG="${SRC:-garmin-stats-skills @ https://github.com/${REPO}/archive/refs/heads/${REF}.tar.gz}"

printf '\n\033[1mGarmin Stats for Claude\033[0m: setting up. This takes 1–2 minutes.\n'

step "1/4  Getting the tools ready"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 sh >/dev/null 2>&1 \
        || fail "Couldn't download uv. Check your internet connection."
fi
UV="$(command -v uv)" || fail "uv didn't install."
ok "ready"

step "2/4  Installing Garmin Stats"
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
ok "$("$EXE" --version)"

step "3/4  Connecting your Garmin account"
if [ "$DO_SETUP" = 1 ]; then
    echo "   A window will ask for your Garmin email and password (and a code if"
    echo "   Garmin sends you one). Your password goes only to Garmin and isn't saved."
    if GARMIN_STATS_HOME="$APP_HOME" "$EXE" setup; then
        ok "connected, data downloaded, hourly sync on"
    else
        printf '   \033[33m!\033[0m Not connected yet. No problem: later, just ask Claude\n'
        printf '     "connect my Garmin" and the sign-in window will appear again.\n'
    fi
else
    ok "skipped (--no-setup)"
fi

step "4/4  Adding it to Claude"
if [ "$DO_CLAUDE_CODE" = 1 ] && command -v claude >/dev/null 2>&1; then
    MP="${SRC:-$REPO}"
    claude plugin marketplace list 2>/dev/null | grep -q garmin-stats-skills \
        && claude plugin marketplace update garmin-stats-skills >/dev/null 2>&1 \
        || claude plugin marketplace add "$MP" >/dev/null 2>&1 || true
    { claude plugin install garmin-stats-skills@garmin-stats-skills >/dev/null 2>&1 \
        || claude plugin update garmin-stats-skills@garmin-stats-skills >/dev/null 2>&1; } \
        && ok "added to Claude Code"
fi
ZIP="$(GARMIN_STATS_HOME="$APP_HOME" "$EXE" plugin-zip)" || fail "Couldn't build the plugin file."
ok "plugin file ready: $ZIP"

INTERACTIVE=0
[ -t 1 ] && INTERACTIVE=1   # a real Terminal window, not a script / CI

cat <<EOF

$(printf '\033[1mAlmost done. One step left, in the Claude app:\033[0m')
   1. Click Customize (left sidebar), then Plugins
   2. Click Upload plugin (under "+" or "Add") and choose "Garmin-Stats.zip"
      (a Finder window is showing it; you can also drag it in)
   Then ask Claude: "How did I sleep last night?"

   (Prefer automatic updates? Use "Add marketplace" with $REPO instead.)
EOF

[ "$INTERACTIVE" = 1 ] || exit 0
open -R "$ZIP" 2>/dev/null || true   # show the zip in Finder, ready to drag
CHOICE="$(osascript -e 'button returned of (display dialog "Garmin Stats is installed.

One step left, in the Claude app:
  1. Customize → Plugins
  2. Upload plugin → choose \"Garmin-Stats.zip\"
     (the Finder window behind this one is showing it)

Then ask Claude: \"How did I sleep last night?\"" with title "Garmin Stats" buttons {"Done", "Open Claude"} default button "Open Claude" with icon note)' 2>/dev/null || true)"
if [ "$CHOICE" = "Open Claude" ]; then
    open -a Claude 2>/dev/null || open "https://claude.ai/download"
fi
