#!/bin/bash
# View processing logs in real-time

LOG_FILE="$HOME/.document_system/processing.log"

if [ -f "$LOG_FILE" ]; then
    echo "📋 Viewing processing log (Ctrl+C to exit):"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    tail -f "$LOG_FILE"
else
    echo "❌ No log file found yet at: $LOG_FILE"
    echo ""
    echo "Start processing first, then run this again!"
fi
