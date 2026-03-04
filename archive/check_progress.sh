#!/bin/bash
# Quick status check - see progress without stopping processing

cd "$(dirname "$0")"
source venv/bin/activate

echo ""
echo "📊 CURRENT PROGRESS"
echo "===================="
python3 check_status.py

# Show when last processed
progress_file="$HOME/.document_system/batch_progress.json"
if [ -f "$progress_file" ]; then
    echo ""
    echo "📅 Last updated:"
    stat -f "%Sm" -t "%Y-%m-%d %H:%M:%S" "$progress_file"
fi

# Estimate time remaining
python3 -c "
import json
from pathlib import Path

progress_file = Path.home() / '.document_system' / 'batch_progress.json'
cache_file = Path.home() / '.document_system' / 'pdf_cache.json'

if progress_file.exists() and cache_file.exists():
    with open(progress_file) as f:
        progress = json.load(f)
    with open(cache_file) as f:
        cache = json.load(f)
    
    total = len(cache.get('pdfs', []))
    processed = len(progress.get('processed_files', []))
    remaining = total - processed
    
    # ~400 files per 10-min cycle
    cycles = (remaining // 400) + 1
    hours = (cycles * 10) / 60
    
    print(f'')
    print(f'⏰ Estimate:')
    print(f'   Remaining: {remaining:,} files')
    print(f'   Cycles: ~{cycles} (10 min each)')
    print(f'   Time: ~{hours:.1f} hours')
"
echo ""
