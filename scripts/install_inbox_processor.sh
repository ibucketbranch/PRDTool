#!/bin/bash
# Install Inbox Processor as macOS LaunchAgent
# This script sets up automatic inbox processing on login and every 10 minutes

set -e

echo "========================================"
echo "Inbox Processor Installation"
echo "========================================"
echo ""

# Get current directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PLIST_FILE="$SCRIPT_DIR/../config/com.user.inbox-processor.plist"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
INSTALLED_PLIST="$LAUNCH_AGENTS_DIR/com.user.inbox-processor.plist"

# Check if Groq API key is set
if [ -z "$GROQ_API_KEY" ]; then
    echo "⚠️  Warning: GROQ_API_KEY environment variable not set"
    echo ""
    read -p "Enter your Groq API key (or press Enter to skip): " api_key
    if [ -n "$api_key" ]; then
        GROQ_API_KEY="$api_key"
    else
        GROQ_API_KEY="YOUR_GROQ_API_KEY_HERE"
        echo "⚠️  You'll need to set GROQ_API_KEY in the plist file manually"
    fi
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
cat "$PLIST_FILE" | sed "s|YOUR_GROQ_API_KEY_HERE|$GROQ_API_KEY|g" | sed "s|/Users/michaelvalderrama|$HOME|g" > "$INSTALLED_PLIST"

echo "✅ LaunchAgent configuration created"

# Unload if already loaded
if launchctl list | grep -q "com.user.inbox-processor"; then
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
echo "The inbox processor will now:"
echo "  • Run automatically on login"
echo "  • Check In-Box folder every 10 minutes"
echo "  • Process new PDFs automatically"
echo "  • Move files to organized locations"
echo ""
echo "Inbox location:"
echo "  ~/Library/Mobile Documents/com~apple~CloudDocs/In-Box/"
echo ""
echo "Configuration file:"
echo "  $INSTALLED_PLIST"
echo ""
echo "Log files:"
echo "  ~/.inbox_processor_stdout.log (output)"
echo "  ~/.inbox_processor_stderr.log (errors)"
echo "  ~/.inbox_processor.log (transaction log)"
echo ""
echo "Commands:"
echo "  • Test (dry-run): PYTHONPATH=. python3 scripts/inbox_processor.py --dry-run"
echo "  • Run once: PYTHONPATH=. python3 scripts/inbox_processor.py --process"
echo "  • Stop: launchctl unload $INSTALLED_PLIST"
echo "  • Start: launchctl load $INSTALLED_PLIST"
echo "  • Check status: launchctl list | grep inbox-processor"
echo "  • View logs: tail -f ~/.inbox_processor_stdout.log"
echo ""
