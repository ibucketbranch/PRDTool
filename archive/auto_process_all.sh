#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "╔════════════════════════════════════════════════════════════╗"
echo "║  🔄 AUTO-RESUME BATCH PROCESSOR (FREE TIER)                ║"
echo "║  Processes files continuously, auto-waits on rate limits   ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Activate venv
source venv/bin/activate

# Set API key
# Set in .env: export GROQ_API_KEY="your_key"
[ -f ../.env ] && set -a && source ../.env && set +a

echo "📊 Starting Status:"
python3 check_status.py
echo ""

echo "🎯 Target: Process all remaining files"
echo "⏰ Strategy: Process → Wait 10min → Resume"
echo "🛑 Press Ctrl+C anytime to stop (progress is saved!)"
echo ""

# Counter for batches
batch_num=1

while true; do
    echo ""
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║  📦 BATCH #$batch_num                                       "
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""
    
    # Run batch processing (newest first, 500 at a time)
    python3 process_newest_first.py --batch-size 500
    
    # Check if we're done
    status=$(python3 -c "
import json
from pathlib import Path
progress_file = Path.home() / '.document_system' / 'batch_progress.json'
if progress_file.exists():
    with open(progress_file) as f:
        progress = json.load(f)
    
    # Load cache to see total
    cache_file = Path.home() / '.document_system' / 'pdf_cache.json'
    with open(cache_file) as f:
        cache = json.load(f)
    
    total = len(cache.get('pdfs', []))
    processed = len(progress.get('processed_files', []))
    
    if processed >= total:
        print('DONE')
    else:
        print(f'{processed}/{total}')
else:
    print('0/?')
")
    
    echo ""
    echo "📊 Progress: $status"
    
    if [ "$status" = "DONE" ]; then
        echo ""
        echo "╔════════════════════════════════════════════════════════════╗"
        echo "║  🎉 ALL FILES PROCESSED!                                   ║"
        echo "╚════════════════════════════════════════════════════════════╝"
        echo ""
        python3 check_status.py
        echo ""
        python3 analyze_collected.py
        echo ""
        echo "✅ Data collection complete!"
        echo "💡 Next: Review results and plan post-processing"
        exit 0
    fi
    
    # Wait for rate limit to reset
    echo ""
    echo "⏳ Waiting 10 minutes for rate limit to reset..."
    echo "   Started: $(date '+%H:%M:%S')"
    echo "   Will resume at: $(date -v+10M '+%H:%M:%S')"
    
    # Sleep for 10 minutes (600 seconds)
    sleep 600
    
    batch_num=$((batch_num + 1))
done
