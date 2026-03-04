#!/bin/bash
# Check status after waiting 15 minutes

echo "⏰ Waiting 15 minutes, then checking status..."
echo "   (Started at $(date))"
sleep 900

echo ""
echo "=================================================================================="
echo "📊 STATUS CHECK (15 MINUTES LATER)"
echo "=================================================================================="
echo "   (Checked at $(date))"
echo ""

cd "$(dirname "$0")/.."

# Check if still running
if pgrep -f "process_unprocessed_by_hash" > /dev/null; then
    echo "🟢 Processing: STILL RUNNING"
else
    echo "⏸️  Processing: COMPLETED or STOPPED"
fi

echo ""
python3 scripts/quick_status.py

echo ""
echo "📝 Recent activity:"
tail -10 /tmp/gdrive_hash_processing.log 2>/dev/null | grep -E "Processing:|Processed|SUMMARY" | tail -3 || echo "   (no recent log entries)"

echo ""
echo "=================================================================================="
