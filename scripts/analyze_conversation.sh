#!/bin/bash
# Full Pipeline: PDF → OCR → Parse → Groq Analysis → Supabase DB
# Usage: ./analyze_conversation.sh <path_to_pdf> [start_page] [end_page]

set -e  # Exit on error

PDF_PATH="$1"
START_PAGE="${2:-1}"
END_PAGE="${3:-all}"

if [ -z "$PDF_PATH" ]; then
    echo "Usage: ./analyze_conversation.sh <pdf_path> [start_page] [end_page]"
    echo ""
    echo "Examples:"
    echo "  ./analyze_conversation.sh conversation.pdf"
    echo "  ./analyze_conversation.sh conversation.pdf 1 50"
    exit 1
fi

if [ ! -f "$PDF_PATH" ]; then
    echo "Error: PDF file not found: $PDF_PATH"
    exit 1
fi

# Check for GROQ_API_KEY
if [ -z "$GROQ_API_KEY" ]; then
    echo "Warning: GROQ_API_KEY not set. Will use basic analysis."
    echo "Set it with: export GROQ_API_KEY='your-key-here'"
    read -p "Continue anyway? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

cd "$(dirname "$0")"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  CONVERSATION ANALYSIS PIPELINE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "PDF: $PDF_PATH"
echo "Pages: $START_PAGE to $END_PAGE"
echo ""

# Activate virtual environment
echo "▶ Activating virtual environment..."
source venv/bin/activate

# Install dependencies if needed
if ! python -c "import groq" 2>/dev/null; then
    echo "▶ Installing Groq..."
    pip install -q groq
fi

# Step 1: OCR the PDF
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 1: OCR Extraction"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -f "ocr_raw_text.txt" ]; then
    echo "Found existing ocr_raw_text.txt"
    read -p "Re-run OCR? This will take time. (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -f ocr_raw_text.txt ocr_progress.json
        if [ "$END_PAGE" = "all" ]; then
            python parse_pdf_ocr.py "$PDF_PATH" $START_PAGE <<< "y"
        else
            python parse_pdf_ocr.py "$PDF_PATH" $START_PAGE $END_PAGE
        fi
    fi
else
    if [ "$END_PAGE" = "all" ]; then
        python parse_pdf_ocr.py "$PDF_PATH" $START_PAGE <<< "y"
    else
        python parse_pdf_ocr.py "$PDF_PATH" $START_PAGE $END_PAGE
    fi
fi

if [ ! -f "ocr_raw_text.txt" ]; then
    echo "Error: OCR failed to produce output"
    exit 1
fi

echo "✓ OCR complete"

# Step 2: Parse messages
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 2: Parse Messages"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

python parse_iphone_backup.py ocr_raw_text.txt conversation_data.json

if [ ! -f "conversation_data.json" ]; then
    echo "Error: Message parsing failed"
    exit 1
fi

echo "✓ Messages parsed"

# Step 3: Groq Analysis
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 3: AI Analysis (Groq)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

python groq_analyze.py conversation_data.json analysis_results.json

if [ ! -f "analysis_results.json" ]; then
    echo "Error: Analysis failed"
    exit 1
fi

echo "✓ Analysis complete"

# Step 4: Start Supabase
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 4: Start Supabase"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if supabase status > /dev/null 2>&1; then
    echo "✓ Supabase already running"
else
    echo "Starting Supabase..."
    supabase start
    echo "✓ Supabase started"
fi

# Get Supabase connection info
API_URL=$(supabase status | grep "API URL" | awk '{print $3}')
echo "Local Supabase: $API_URL"

# Step 5: Populate Database
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 5: Populate Database"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

python populate_database.py conversation_data.json analysis_results.json

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✓ PIPELINE COMPLETE!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📊 Results:"
echo "  • Conversation data: conversation_data.json"
echo "  • Analysis: analysis_results.json"
echo "  • Supabase Studio: http://localhost:54423"
echo ""
echo "🔍 Quick Summary:"
cat analysis_results.json | python -c "
import json, sys
data = json.load(sys.stdin)
survival = data.get('relationship', {}).get('survival_assessment', {})
print(f\"  Assessment: {survival.get('assessment', 'N/A').upper()}\")
print(f\"  Probability: {survival.get('survival_probability', 0)*100:.0f}%\")
print(f\"  Reasoning: {survival.get('assessment_text', 'N/A')[:200]}...\")
" 2>/dev/null || echo "  (See analysis_results.json for full details)"

echo ""
echo "Next steps:"
echo "  • Open Supabase Studio to explore data"
echo "  • View analysis_results.json for full therapist insights"
echo "  • Run 'supabase stop' when done"
echo ""
