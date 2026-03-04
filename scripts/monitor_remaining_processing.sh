#!/bin/bash
# Monitor the remaining files processing

echo "=================================================================================="
echo "📊 MONITORING REMAINING FILES PROCESSING"
echo "=================================================================================="
echo ""

# Check if running
if pgrep -f "process_unprocessed_by_hash" > /dev/null; then
    echo "🟢 Processing: RUNNING"
else
    echo "⏸️  Processing: COMPLETED or STOPPED"
fi

echo ""
echo "📊 Current Status:"
cd "$(dirname "$0")/.."
python3 scripts/quick_status.py

echo ""
echo "📝 Recent Activity (last 10 lines):"
tail -10 /tmp/gdrive_remaining_processing.log 2>/dev/null | grep -E "Processing:|Processed|SUMMARY|Error" | tail -5 || echo "   (no recent activity)"

echo ""
echo "💡 To see full log:"
echo "   tail -f /tmp/gdrive_remaining_processing.log"
echo ""
echo "=================================================================================="
