#!/bin/bash
# Resume processing Google Drive documents
# This script will process any remaining unprocessed files

cd "$(dirname "$0")/.."

echo "=================================================================================="
echo "🔄 RESUMING GOOGLE DRIVE PROCESSING"
echo "=================================================================================="
echo ""

# Check if already running
if pgrep -f "process_unprocessed_by_hash.py" > /dev/null; then
    echo "⚠️  Processing script is already running!"
    echo "   Check status with: python3 scripts/quick_status.py"
    exit 1
fi

# Check database connection
echo "📊 Checking database connection..."
python3 -c "
from supabase import create_client
import os
supabase = create_client('http://127.0.0.1:54421', os.getenv('SUPABASE_SERVICE_ROLE_KEY'))
print('✅ Database connected')
" 2>/dev/null || {
    echo "❌ Cannot connect to database. Is Supabase running?"
    exit 1
}

echo ""
echo "🚀 Starting processing..."
echo "   This will run in the background"
echo "   Monitor with: python3 scripts/quick_status.py"
echo "   Or check log: tail -f /tmp/gdrive_hash_processing.log"
echo ""

# Start processing in background
nohup python3 scripts/process_unprocessed_by_hash.py > /tmp/gdrive_hash_processing.log 2>&1 &

echo "✅ Processing started (PID: $!)"
echo ""
echo "💡 To stop processing:"
echo "   python3 scripts/stop_processing.py"
echo ""
echo "💡 To check status:"
echo "   python3 scripts/quick_status.py"
echo ""
