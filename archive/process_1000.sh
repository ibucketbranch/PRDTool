#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "╔════════════════════════════════════════════════════════════╗"
echo "║  📦 PROCESSING 1000 FILES                                  ║"
echo "║  Estimated time: 30-50 minutes                            ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Activate venv
source venv/bin/activate

# Set API key
# Set in .env: export GROQ_API_KEY="your_key"
[ -f ../.env ] && set -a && source ../.env && set +a

# Show current status
echo "📊 Current Status:"
python3 check_status.py
echo ""

# Process 1000 files
echo "🚀 Starting batch processing..."
echo "   You can press Ctrl+C at any time - progress is saved!"
echo ""

python3 process_oldest_first.py --batch-size 1000

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║  ✅ BATCH COMPLETE!                                        ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Show final status
echo "📊 Final Status:"
python3 check_status.py
echo ""

echo "🎉 Done! View logs with: ./view_logs.sh"
