#!/bin/bash
# Removes Garmin Stats: background sync, helper, Claude Code plugin, and
# everything in ~/.garmin-stats-skills (sign-in + cached data).
#   curl -fsSL https://raw.githubusercontent.com/jwiderberg/garmin-stats-skills/main/uninstall.sh | bash
set -uo pipefail
APP_HOME="${GARMIN_STATS_HOME:-$HOME/.garmin-stats-skills}"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

launchctl bootout "gui/$(id -u)/com.garmin-stats-skills.sync" 2>/dev/null
rm -f "$HOME/Library/LaunchAgents/com.garmin-stats-skills.sync.plist" && echo "✓ background sync stopped"
if command -v claude >/dev/null 2>&1; then
    claude plugin uninstall garmin-stats-skills@garmin-stats-skills >/dev/null 2>&1
    claude plugin marketplace remove garmin-stats-skills >/dev/null 2>&1
    echo "✓ removed from Claude Code"
fi
command -v uv >/dev/null 2>&1 && uv tool uninstall garmin-stats-skills >/dev/null 2>&1 \
    && echo "✓ helper removed"
rm -rf "$APP_HOME" && echo "✓ deleted $APP_HOME (sign-in + cached data)"
echo "Done. In the Claude app, remove \"Garmin Stats\" under Customize → Plugins."
