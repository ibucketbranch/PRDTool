#!/bin/bash
# Uninstall Document Monitor LaunchAgent

set -e

echo "========================================"
echo "Document Monitor Uninstallation"
echo "========================================"
echo ""

LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
INSTALLED_PLIST="$LAUNCH_AGENTS_DIR/com.user.document-monitor.plist"

# Check if installed
if [ ! -f "$INSTALLED_PLIST" ]; then
    echo "ℹ️  Document monitor is not installed"
    exit 0
fi

# Unload
if launchctl list | grep -q "com.user.document-monitor"; then
    echo "📤 Unloading LaunchAgent..."
    launchctl unload "$INSTALLED_PLIST"
fi

# Remove plist
echo "🗑️  Removing configuration..."
rm "$INSTALLED_PLIST"

echo ""
echo "✅ Document monitor uninstalled"
echo ""
echo "Note: Log files and state files were NOT removed:"
echo "  ~/.document_monitor.log"
echo "  ~/.document_monitor_state.json"
echo "  ~/.document_monitor_stdout.log"
echo "  ~/.document_monitor_stderr.log"
echo ""
echo "To remove them manually:"
echo "  rm ~/.document_monitor*"
echo ""
