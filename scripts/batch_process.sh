#!/bin/bash
# Batch Process All PDFs in Directory
# Tracks status, handles corrupted files, logs to database

set -e

PDF_DIR="${1:-/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs/ztoolbar_drive/Messages}"
PAGES_TO_PROCESS="${2:-5}"  # Default: first 5 pages per PDF for testing

if [ ! -d "$PDF_DIR" ]; then
    echo "❌ Directory not found: $PDF_DIR"
    exit 1
fi

cd "$(dirname "$0")"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  BATCH PDF PROCESSOR WITH STATUS TRACKING"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Directory: $PDF_DIR"
echo "Pages per PDF: $PAGES_TO_PROCESS (test mode)"
echo ""

# Activate venv
source venv/bin/activate

# Install dependencies
if ! python -c "import groq" 2>/dev/null; then
    pip install -q groq
fi

# Start Supabase if not running
if ! supabase status > /dev/null 2>&1; then
    echo "Starting Supabase..."
    supabase start > /dev/null 2>&1 &
    sleep 5
fi

# Apply new migration if needed
supabase db reset --no-seed 2>/dev/null || true

# Count PDFs
TOTAL_PDFS=$(find "$PDF_DIR" -name "*.pdf" -type f | wc -l | tr -d ' ')
echo "Found $TOTAL_PDFS PDF files"
echo ""

PROCESSED=0
SUCCEEDED=0
FAILED=0
CORRUPTED=0
EMPTY=0

# Process each PDF
find "$PDF_DIR" -name "*.pdf" -type f | sort | while read -r PDF_FILE; do
    PROCESSED=$((PROCESSED + 1))
    FILENAME=$(basename "$PDF_FILE")
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "[$PROCESSED/$TOTAL_PDFS] Processing: $FILENAME"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    START_TIME=$(date +%s)
    
    # Start tracking in database
    RECORD_ID=$(python -c "
from file_tracker import FileTracker
tracker = FileTracker()
record_id = tracker.start_processing('$PDF_FILE')
print(record_id)
" 2>/dev/null || echo "")
    
    if [ -z "$RECORD_ID" ]; then
        echo "⚠️  Warning: Could not create tracking record"
    fi
    
    # Check if file contains deleted content marker
    if [[ "$FILENAME" == *"(contains deleted content)"* ]]; then
        echo "⚠️  SKIPPED: Contains deleted content marker"
        if [ -n "$RECORD_ID" ]; then
            python file_tracker.py mark-corrupted "$RECORD_ID" "Contains deleted content marker" 2>/dev/null || true
        fi
        CORRUPTED=$((CORRUPTED + 1))
        continue
    fi
    
    # Try to process
    rm -f ocr_raw_text.txt ocr_progress.json conversation_data.json analysis_results.json 2>/dev/null || true
    
    # Step 1: OCR
    echo "▶ OCR extraction (pages 1-$PAGES_TO_PROCESS)..."
    if ! python parse_pdf_ocr.py "$PDF_FILE" 1 "$PAGES_TO_PROCESS" > /dev/null 2>&1; then
        echo "❌ OCR FAILED"
        if [ -n "$RECORD_ID" ]; then
            python file_tracker.py mark-corrupted "$RECORD_ID" "OCR extraction failed" 2>/dev/null || true
        fi
        CORRUPTED=$((CORRUPTED + 1))
        continue
    fi
    
    # Check if OCR produced content
    if [ ! -f "ocr_raw_text.txt" ] || [ ! -s "ocr_raw_text.txt" ]; then
        echo "❌ EMPTY: No text extracted"
        if [ -n "$RECORD_ID" ]; then
            python file_tracker.py mark-empty "$RECORD_ID" "No text extracted from PDF" 2>/dev/null || true
        fi
        EMPTY=$((EMPTY + 1))
        continue
    fi
    
    # Step 2: Parse
    echo "▶ Parsing messages..."
    if ! python parse_iphone_backup.py ocr_raw_text.txt conversation_data.json > /dev/null 2>&1; then
        echo "❌ PARSING FAILED"
        if [ -n "$RECORD_ID" ]; then
            python file_tracker.py mark-corrupted "$RECORD_ID" "Message parsing failed" 2>/dev/null || true
        fi
        FAILED=$((FAILED + 1))
        continue
    fi
    
    # Check message count
    MSG_COUNT=$(python -c "
import json
try:
    with open('conversation_data.json', 'r') as f:
        data = json.load(f)
    print(data.get('total_messages', 0))
except:
    print(0)
" 2>/dev/null || echo "0")
    
    if [ "$MSG_COUNT" -eq 0 ]; then
        echo "❌ EMPTY: No messages found"
        if [ -n "$RECORD_ID" ]; then
            python file_tracker.py mark-empty "$RECORD_ID" "No messages found in extracted text" 2>/dev/null || true
        fi
        EMPTY=$((EMPTY + 1))
        continue
    fi
    
    echo "✓ Found $MSG_COUNT messages"
    
    # Step 3: Groq Analysis (optional - only if GROQ_API_KEY is set)
    if [ -n "$GROQ_API_KEY" ]; then
        echo "▶ Running Groq analysis..."
        if python groq_analyze.py conversation_data.json analysis_results.json > /dev/null 2>&1; then
            echo "✓ Analysis complete"
        else
            echo "⚠️  Analysis failed (continuing anyway)"
        fi
    else
        echo "⏭  Skipping Groq analysis (GROQ_API_KEY not set)"
    fi
    
    # Step 4: Populate database
    echo "▶ Saving to database..."
    if python populate_database.py conversation_data.json analysis_results.json > /dev/null 2>&1; then
        echo "✓ Saved to database"
    else
        echo "⚠️  Database save failed"
    fi
    
    # Mark as complete
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    
    if [ -n "$RECORD_ID" ]; then
        python -c "
from file_tracker import FileTracker
import json
tracker = FileTracker()
with open('conversation_data.json', 'r') as f:
    data = json.load(f)
tracker.complete_processing('$RECORD_ID', data, $DURATION)
" 2>/dev/null || true
    fi
    
    SUCCEEDED=$((SUCCEEDED + 1))
    echo "✓ COMPLETED in ${DURATION}s"
    echo ""
done

# Final summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  BATCH PROCESSING COMPLETE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📊 Results:"
echo "   Total PDFs: $TOTAL_PDFS"
echo "   ✓ Succeeded: $SUCCEEDED"
echo "   ❌ Failed: $FAILED"
echo "   🗑️  Corrupted/Skipped: $CORRUPTED"
echo "   📭 Empty: $EMPTY"
echo ""
echo "🔍 View status in Supabase Studio: http://localhost:54423"
echo "   Or run: python file_tracker.py summary"
echo ""
