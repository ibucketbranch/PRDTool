#!/bin/bash
# Test Batch Processor Setup

echo "🧪 Testing Batch Processor"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if virtual environment is active
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Virtual environment not active"
    echo "   Run: source venv/bin/activate"
    echo ""
    exit 1
fi

echo "✅ Virtual environment active"
echo ""

# Check dependencies
echo "📦 Checking dependencies..."
python3 -c "import PyPDF2" 2>/dev/null && echo "   ✅ PyPDF2 installed" || echo "   ❌ PyPDF2 missing"
python3 -c "import supabase" 2>/dev/null && echo "   ✅ supabase installed" || echo "   ❌ supabase missing"
python3 -c "import groq" 2>/dev/null && echo "   ✅ groq installed" || echo "   ❌ groq missing"
python3 -c "import requests" 2>/dev/null && echo "   ✅ requests installed" || echo "   ❌ requests missing"
echo ""

# Show help
echo "📋 Batch Processor Help:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python3 batch_processor.py --help
echo ""

# Test dry-run on current directory (if it exists)
TEST_DIR="$HOME/Documents"
if [ -d "$TEST_DIR" ]; then
    echo "🧪 Test dry-run on: $TEST_DIR"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Command: python3 batch_processor.py \"$TEST_DIR\" --dry-run --batch-size 5"
    echo ""
    read -p "Run test? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        python3 batch_processor.py "$TEST_DIR" --dry-run --batch-size 5
    fi
fi

echo ""
echo "✅ Test complete!"
