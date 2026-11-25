#!/usr/bin/env bash
# garmin-stats-skills uninstaller: removes the Claude Code plugin, the
# garmin-stats command, and ~/.garmin-stats-skills (saved Garmin session +
# cache). Cowork plugins are removed in the app: Customize → Plugins.
set -uo pipefail

APP_HOME="${GARMIN_STATS_HOME:-$HOME/.garmin-stats-skills}"
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:/opt/homebrew/bin:$PATH"

if command -v claude >/dev/null 2>&1; then
    claude plugin uninstall garmin-stats-skills@garmin-stats-skills >/dev/null 2>&1 \
        && echo "✓ removed Claude Code plugin"
    claude plugin marketplace remove garmin-stats-skills >/dev/null 2>&1 \
        && echo "✓ removed marketplace"
fi
if command -v uv >/dev/null 2>&1; then
    uv tool uninstall garmin-stats-skills >/dev/null 2>&1 && echo "✓ removed garmin-stats command"
fi
if [ -d "$APP_HOME" ]; then
    rm -rf "$APP_HOME" && echo "✓ deleted $APP_HOME (Garmin session + cache)"
fi
echo "Done. In Claude Cowork, remove 'Garmin Stats' under Customize → Plugins."
