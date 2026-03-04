#!/bin/bash
# Install Document Monitor as macOS LaunchAgent
# This script sets up automatic monitoring on login

set -e

echo "========================================"
echo "Document Monitor Installation"
echo "========================================"
echo ""

# Get current directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PLIST_FILE="$SCRIPT_DIR/com.user.document-monitor.plist"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
INSTALLED_PLIST="$LAUNCH_AGENTS_DIR/com.user.document-monitor.plist"

# Check if Groq API key is set
if [ -z "$GROQ_API_KEY" ]; then
    echo "⚠️  Warning: GROQ_API_KEY environment variable not set"
    echo ""
    read -p "Enter your Groq API key: " api_key
    if [ -z "$api_key" ]; then
        echo "❌ Error: API key is required"
        exit 1
    fi
    GROQ_API_KEY="$api_key"
fi

# Check if plist file exists
if [ ! -f "$PLIST_FILE" ]; then
    echo "❌ Error: plist file not found: $PLIST_FILE"
    exit 1
fi

# Create LaunchAgents directory if it doesn't exist
mkdir -p "$LAUNCH_AGENTS_DIR"

# Copy and customize plist file
echo "📝 Creating LaunchAgent configuration..."
cat "$PLIST_FILE" | sed "s|YOUR_GROQ_API_KEY_HERE|$GROQ_API_KEY|g" > "$INSTALLED_PLIST"

# Update paths in plist to use current user's home directory
sed -i '' "s|/Users/michaelvalderrama|$HOME|g" "$INSTALLED_PLIST"

echo "✅ LaunchAgent configuration created"

# Unload if already loaded
if launchctl list | grep -q "com.user.document-monitor"; then
    echo "📤 Unloading existing LaunchAgent..."
    launchctl unload "$INSTALLED_PLIST" 2>/dev/null || true
fi

# Load the LaunchAgent
echo "📥 Loading LaunchAgent..."
launchctl load "$INSTALLED_PLIST"

echo ""
echo "========================================"
echo "✅ Installation Complete!"
echo "========================================"
echo ""
echo "The document monitor will now:"
echo "  • Run automatically on login"
echo "  • Check for new PDFs every 5 minutes"
echo "  • Send notifications for new files"
echo "  • Process PDFs automatically"
echo ""
echo "Monitored directories:"
echo "  • ~/Library/Mobile Documents/com~apple~CloudDocs (iCloud)"
echo "  • ~/Downloads"
echo "  • ~/Documents"
echo ""
echo "Configuration file:"
echo "  $INSTALLED_PLIST"
echo ""
echo "Log files:"
echo "  ~/.document_monitor.log (monitor log)"
echo "  ~/.document_monitor_stdout.log (system stdout)"
echo "  ~/.document_monitor_stderr.log (system stderr)"
echo ""
echo "Commands:"
echo "  • Test: python document_monitor.py --test"
echo "  • Run once: python document_monitor.py --once"
echo "  • Stop: launchctl unload $INSTALLED_PLIST"
echo "  • Start: launchctl load $INSTALLED_PLIST"
echo "  • Uninstall: ./uninstall_monitor.sh"
echo ""

# Test notification
echo "📱 Sending test notification..."
python3 "$SCRIPT_DIR/document_monitor.py" --test

echo ""
echo "✅ If you saw a notification, everything is working!"
echo ""
