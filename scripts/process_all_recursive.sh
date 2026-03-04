#!/bin/bash
# RECURSIVE BATCH PROCESSOR - Process ALL PDFs in ALL subdirectories
# Tracks status, logs to database, handles corrupted files

set -e

ROOT_DIR="${1:-/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs/ztoolbar_drive}"
PAGES_TO_TEST="${2:-5}"  # Test first N pages

if [ ! -d "$ROOT_DIR" ]; then
    echo "❌ Directory not found: $ROOT_DIR"
    exit 1
fi

cd "$(dirname "$0")"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  RECURSIVE PDF PROCESSOR - ALL FOLDERS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Root Directory: $ROOT_DIR"
echo "Test Mode: First $PAGES_TO_TEST pages per PDF"
echo ""

# Activate venv
source venv/bin/activate

# Install dependencies
echo "📦 Checking dependencies..."
pip install -q groq 2>/dev/null || true

# Start Supabase if not running
echo "🗄️  Checking Supabase..."
if ! supabase status > /dev/null 2>&1; then
    echo "Starting Supabase..."
    supabase start
    sleep 3
fi

# Apply migrations
echo "📋 Applying database migrations..."
supabase db reset --no-seed 2>/dev/null || supabase migration up 2>/dev/null || true

# Create results directory
mkdir -p results

# Count all PDFs recursively
echo ""
echo "🔍 Scanning for PDFs..."
TOTAL_PDFS=$(find "$ROOT_DIR" -type f -name "*.pdf" | wc -l | tr -d ' ')
echo "Found $TOTAL_PDFS PDF files across all folders"
echo ""

if [ "$TOTAL_PDFS" -eq 0 ]; then
    echo "❌ No PDF files found"
    exit 1
fi

# Confirm before processing
echo "⚠️  About to process $TOTAL_PDFS PDFs"
echo "   This will take significant time!"
echo ""
read -p "Continue? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Cancelled."
    exit 0
fi

# Initialize counters
PROCESSED=0
SUCCEEDED=0
FAILED=0
CORRUPTED=0
EMPTY=0
SKIPPED=0

# Log file
LOG_FILE="processing_log_$(date +%Y%m%d_%H%M%S).txt"
echo "📝 Logging to: $LOG_FILE"
echo ""

# Process each PDF recursively
find "$ROOT_DIR" -type f -name "*.pdf" | sort | while read -r PDF_FILE; do
    PROCESSED=$((PROCESSED + 1))
    FILENAME=$(basename "$PDF_FILE")
    REL_PATH=$(echo "$PDF_FILE" | sed "s|$ROOT_DIR/||")
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | tee -a "$LOG_FILE"
    echo "[$PROCESSED/$TOTAL_PDFS] $REL_PATH" | tee -a "$LOG_FILE"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | tee -a "$LOG_FILE"
    
    START_TIME=$(date +%s)
    
    # Start tracking
    RECORD_ID=$(python -c "
from file_tracker import FileTracker
import sys
try:
    tracker = FileTracker()
    record_id = tracker.start_processing('$PDF_FILE')
    print(record_id)
except Exception as e:
    sys.stderr.write(f'Error: {e}')
    print('')
" 2>/dev/null)
    
    # Check for corruption indicators
    if [[ "$FILENAME" == *"deleted content"* ]] || [[ "$FILENAME" == *"����"* ]] || [[ "$FILENAME" == *"NSKeyedArchiver"* ]]; then
        echo "⚠️  SKIPPED: Corrupted filename indicator" | tee -a "$LOG_FILE"
        [ -n "$RECORD_ID" ] && python -c "
from file_tracker import FileTracker
FileTracker().mark_corrupted('$RECORD_ID', 'Filename indicates corruption')
" 2>/dev/null || true
        CORRUPTED=$((CORRUPTED + 1))
        continue
    fi
    
    # Check file size
    FILE_SIZE=$(stat -f%z "$PDF_FILE" 2>/dev/null || stat -c%s "$PDF_FILE" 2>/dev/null || echo "0")
    FILE_SIZE_MB=$((FILE_SIZE / 1024 / 1024))
    
    if [ "$FILE_SIZE_MB" -lt 1 ]; then
        echo "⚠️  SKIPPED: Too small (${FILE_SIZE_MB}MB)" | tee -a "$LOG_FILE"
        [ -n "$RECORD_ID" ] && python -c "
from file_tracker import FileTracker
FileTracker().mark_empty('$RECORD_ID', 'File size < 1MB')
" 2>/dev/null || true
        EMPTY=$((EMPTY + 1))
        continue
    fi
    
    echo "Size: ${FILE_SIZE_MB}MB" | tee -a "$LOG_FILE"
    
    # Clean temp files
    rm -f ocr_raw_text.txt ocr_progress.json conversation_data.json analysis_results.json 2>/dev/null || true
    
    # Step 1: OCR (test first N pages)
    echo "▶ OCR extraction (testing pages 1-$PAGES_TO_TEST)..." | tee -a "$LOG_FILE"
    if python parse_pdf_ocr.py "$PDF_FILE" 1 "$PAGES_TO_TEST" > /dev/null 2>&1; then
        if [ -f "ocr_raw_text.txt" ] && [ -s "ocr_raw_text.txt" ]; then
            CHAR_COUNT=$(wc -c < ocr_raw_text.txt)
            echo "✓ Extracted $CHAR_COUNT characters" | tee -a "$LOG_FILE"
            
            if [ "$CHAR_COUNT" -lt 100 ]; then
                echo "⚠️  EMPTY: Insufficient content" | tee -a "$LOG_FILE"
                [ -n "$RECORD_ID" ] && python -c "
from file_tracker import FileTracker
FileTracker().mark_empty('$RECORD_ID', 'Only $CHAR_COUNT characters extracted')
" 2>/dev/null || true
                EMPTY=$((EMPTY + 1))
                continue
            fi
            
            # Step 2: Parse messages
            echo "▶ Parsing messages..." | tee -a "$LOG_FILE"
            if python parse_iphone_backup.py ocr_raw_text.txt conversation_data.json > /dev/null 2>&1; then
                MSG_COUNT=$(python -c "
import json, sys
try:
    with open('conversation_data.json', 'r') as f:
        print(json.load(f).get('total_messages', 0))
except: print(0)
" 2>/dev/null)
                
                if [ "$MSG_COUNT" -gt 0 ]; then
                    echo "✓ Found $MSG_COUNT messages" | tee -a "$LOG_FILE"
                    
                    # Step 3: Groq Analysis (if API key set)
                    if [ -n "$GROQ_API_KEY" ]; then
                        echo "▶ Groq analysis..." | tee -a "$LOG_FILE"
                        python groq_analyze.py conversation_data.json analysis_results.json > /dev/null 2>&1 || echo "⚠️  Analysis failed" | tee -a "$LOG_FILE"
                    fi
                    
                    # Step 4: Save to database
                    echo "▶ Saving to database..." | tee -a "$LOG_FILE"
                    python populate_database.py conversation_data.json analysis_results.json > /dev/null 2>&1 || echo "⚠️  DB save failed" | tee -a "$LOG_FILE"
                    
                    # Mark complete
                    END_TIME=$(date +%s)
                    DURATION=$((END_TIME - START_TIME))
                    
                    [ -n "$RECORD_ID" ] && python -c "
from file_tracker import FileTracker
import json
try:
    tracker = FileTracker()
    with open('conversation_data.json', 'r') as f:
        data = json.load(f)
    tracker.complete_processing('$RECORD_ID', data, $DURATION)
except: pass
" 2>/dev/null || true
                    
                    SUCCEEDED=$((SUCCEEDED + 1))
                    echo "✅ SUCCESS (${DURATION}s)" | tee -a "$LOG_FILE"
                    
                    # Save results
                    SAFE_NAME=$(echo "$FILENAME" | sed 's/[^a-zA-Z0-9._-]/_/g')
                    cp conversation_data.json "results/${SAFE_NAME}_data.json" 2>/dev/null || true
                    cp analysis_results.json "results/${SAFE_NAME}_analysis.json" 2>/dev/null || true
                else
                    echo "⚠️  EMPTY: No messages parsed" | tee -a "$LOG_FILE"
                    [ -n "$RECORD_ID" ] && python -c "
from file_tracker import FileTracker
FileTracker().mark_empty('$RECORD_ID', 'No messages found in text')
" 2>/dev/null || true
                    EMPTY=$((EMPTY + 1))
                fi
            else
                echo "❌ FAILED: Parse error" | tee -a "$LOG_FILE"
                [ -n "$RECORD_ID" ] && python -c "
from file_tracker import FileTracker
FileTracker().mark_failed('$RECORD_ID', 'Message parsing failed')
" 2>/dev/null || true
                FAILED=$((FAILED + 1))
            fi
        else
            echo "❌ EMPTY: OCR produced no output" | tee -a "$LOG_FILE"
            [ -n "$RECORD_ID" ] && python -c "
from file_tracker import FileTracker
FileTracker().mark_empty('$RECORD_ID', 'OCR produced no output file')
" 2>/dev/null || true
            EMPTY=$((EMPTY + 1))
        fi
    else
        echo "❌ FAILED: OCR error" | tee -a "$LOG_FILE"
        [ -n "$RECORD_ID" ] && python -c "
from file_tracker import FileTracker
FileTracker().mark_failed('$RECORD_ID', 'OCR process failed')
" 2>/dev/null || true
        FAILED=$((FAILED + 1))
    fi
    
    # Progress update every 10 files
    if [ $((PROCESSED % 10)) -eq 0 ]; then
        echo "" | tee -a "$LOG_FILE"
        echo "📊 Progress: $PROCESSED/$TOTAL_PDFS" | tee -a "$LOG_FILE"
        echo "   ✅ Success: $SUCCEEDED | ❌ Failed: $FAILED | 🗑️  Corrupted: $CORRUPTED | 📭 Empty: $EMPTY" | tee -a "$LOG_FILE"
        echo "" | tee -a "$LOG_FILE"
    fi
    
    echo "" | tee -a "$LOG_FILE"
done

# Final summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | tee -a "$LOG_FILE"
echo "  🎉 BATCH PROCESSING COMPLETE!" | tee -a "$LOG_FILE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"
echo "📊 Final Results:" | tee -a "$LOG_FILE"
echo "   Total PDFs: $TOTAL_PDFS" | tee -a "$LOG_FILE"
echo "   ✅ Successfully processed: $SUCCEEDED" | tee -a "$LOG_FILE"
echo "   ❌ Failed: $FAILED" | tee -a "$LOG_FILE"
echo "   🗑️  Corrupted/Skipped: $CORRUPTED" | tee -a "$LOG_FILE"
echo "   📭 Empty: $EMPTY" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"
echo "📁 Results saved in: results/" | tee -a "$LOG_FILE"
echo "📝 Full log: $LOG_FILE" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"
echo "🔍 View in Supabase Studio: http://localhost:54423" | tee -a "$LOG_FILE"
echo "   Tables: file_processing_status, problematic_files" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Show database summary
echo "📊 Database Summary:" | tee -a "$LOG_FILE"
python file_tracker.py summary 2>/dev/null | tee -a "$LOG_FILE" || echo "   (Run 'python file_tracker.py summary' to see stats)" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"
