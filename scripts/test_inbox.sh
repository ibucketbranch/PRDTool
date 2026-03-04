#!/bin/bash
# Quick test of inbox processor

echo "=================================="
echo "🧪 INBOX PROCESSOR TEST"
echo "=================================="
echo ""

# Navigate to project
cd /Users/michaelvalderrama/Websites/TheConversation

# Test 1: Setup inbox structure
echo "Test 1: Setting up inbox structure..."
python3 inbox_processor.py --setup-only
echo ""

# Test 2: Check if folders exist
echo "Test 2: Verifying folders..."
if [ -d "$HOME/Library/Mobile Documents/com~apple~CloudDocs/In-Box" ]; then
    echo "✅ In-Box exists"
else
    echo "❌ In-Box not found"
fi

if [ -d "$HOME/Library/Mobile Documents/com~apple~CloudDocs/In-Box/Processing Errors" ]; then
    echo "✅ Processing Errors exists"
else
    echo "❌ Processing Errors not found"
fi
echo ""

# Test 3: Show inbox contents
echo "Test 3: Checking inbox contents..."
INBOX_PATH="$HOME/Library/Mobile Documents/com~apple~CloudDocs/In-Box"
PDF_COUNT=$(find "$INBOX_PATH" -maxdepth 1 -name "*.pdf" 2>/dev/null | wc -l)
echo "📄 PDFs in inbox: $PDF_COUNT"
echo ""

# Test 4: Dry-run (if PDFs exist)
if [ $PDF_COUNT -gt 0 ]; then
    echo "Test 4: Running dry-run preview..."
    python3 inbox_processor.py --dry-run
else
    echo "Test 4: No PDFs to process (inbox is empty)"
    echo ""
    echo "To test processing:"
    echo "1. Copy a test PDF to: $INBOX_PATH"
    echo "2. Run: python3 inbox_processor.py --dry-run"
    echo "3. Review output"
    echo "4. Run: python3 inbox_processor.py --process"
fi

echo ""
echo "=================================="
echo "✅ TEST COMPLETE"
echo "=================================="
