#!/bin/bash
# Universal Conversation Analysis Pipeline
# Supports: PDF, TXT, JSON, CSV, images, WhatsApp, iMessage, Messenger, etc.

set -e

FILE_PATH="$1"

if [ -z "$FILE_PATH" ]; then
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  UNIVERSAL CONVERSATION ANALYSIS"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Usage: ./analyze_any.sh <file_path>"
    echo ""
    echo "Supported formats:"
    echo "  📄 PDF files"
    echo "  💬 WhatsApp exports (.txt)"
    echo "  📱 iMessage/iPhone backup (.txt)"
    echo "  📊 JSON exports (Messenger, etc.)"
    echo "  📋 CSV files"
    echo "  📝 Plain text conversations"
    echo "  🖼️  Images (with OCR)"
    echo "  🌐 HTML exports"
    echo ""
    echo "Examples:"
    echo "  ./analyze_any.sh conversation.pdf"
    echo "  ./analyze_any.sh whatsapp_chat.txt"
    echo "  ./analyze_any.sh messenger_export.json"
    echo "  ./analyze_any.sh screenshot.png"
    exit 1
fi

if [ ! -f "$FILE_PATH" ]; then
    echo "❌ Error: File not found: $FILE_PATH"
    exit 1
fi

cd "$(dirname "$0")"

# Get file extension
EXT="${FILE_PATH##*.}"
EXT_LOWER=$(echo "$EXT" | tr '[:upper:]' '[:lower:]')

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  CONVERSATION ANALYSIS PIPELINE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "File: $FILE_PATH"
echo "Type: $EXT_LOWER"
echo ""

# Activate venv
source venv/bin/activate

# Install dependencies if needed
if ! python -c "import groq" 2>/dev/null; then
    echo "📦 Installing dependencies..."
    pip install -q groq
fi

# Step 1: Parse based on file type
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 1: Parse Conversation"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ "$EXT_LOWER" = "pdf" ]; then
    # PDF requires OCR
    echo "PDF detected - running OCR..."
    
    if [ -f "ocr_raw_text.txt" ]; then
        read -p "Use existing OCR? (y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            python parse_pdf_ocr.py "$FILE_PATH" <<< "y"
        fi
    else
        python parse_pdf_ocr.py "$FILE_PATH" <<< "y"
    fi
    
    python parse_iphone_backup.py ocr_raw_text.txt conversation_data.json
else
    # Use universal parser
    python universal_parser.py "$FILE_PATH" conversation_data.json
fi

if [ ! -f "conversation_data.json" ]; then
    echo "❌ Error: Parsing failed"
    exit 1
fi

echo "✓ Parsed successfully"

# Step 2: Groq Analysis
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 2: AI Therapist Analysis (Groq)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -z "$GROQ_API_KEY" ]; then
    echo "⚠️  Warning: GROQ_API_KEY not set"
    echo "Set it with: export GROQ_API_KEY='your-key'"
    read -p "Continue with basic analysis? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

python groq_analyze.py conversation_data.json analysis_results.json

echo "✓ Analysis complete"

# Step 3: Supabase
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 3: Database (Local Supabase)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if supabase status > /dev/null 2>&1; then
    echo "✓ Supabase running"
else
    echo "Starting Supabase..."
    supabase start > /dev/null 2>&1 || echo "Note: Supabase start may take a moment"
fi

python populate_database.py conversation_data.json analysis_results.json

# Final Summary
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✨ ANALYSIS COMPLETE!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📊 Files created:"
echo "   • conversation_data.json - Parsed messages"
echo "   • analysis_results.json - AI analysis"
echo ""
echo "🔍 Quick verdict:"
python -c "
import json
with open('analysis_results.json', 'r') as f:
    data = json.load(f)
    survival = data.get('relationship', {}).get('survival_assessment', {})
    verdict = survival.get('assessment', 'unknown').upper()
    prob = survival.get('survival_probability', 0) * 100
    reason = survival.get('assessment_text', 'N/A')[:250]
    print(f'   Verdict: {verdict}')
    print(f'   Probability: {prob:.0f}%')
    print(f'   Reasoning: {reason}...')
" 2>/dev/null || cat analysis_results.json | grep -A 3 "survival_assessment"

echo ""
echo "🌐 Explore data:"
echo "   • Supabase Studio: http://localhost:54423"
echo "   • View analysis_results.json for full details"
echo ""
