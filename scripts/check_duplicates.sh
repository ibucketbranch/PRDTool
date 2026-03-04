#!/bin/bash
# Quick duplicate check - run this in your terminal to see progress

cd /Users/michaelvalderrama/Websites/TheConversation
source venv/bin/activate

echo "🔍 Analyzing duplicates in your PDF collection..."
echo ""
echo "This will:"
echo "  1. Group PDFs by size (fast)"
echo "  2. Hash files in same-size groups (slower)"
echo "  3. Generate duplicate report"
echo ""
echo "⏱️  Estimated time: 10-15 minutes for 8,171 PDFs"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 0
fi

python3 analyze_duplicates.py

echo ""
echo "✅ Analysis complete!"
echo ""
echo "📋 To see space savings with aliases:"
echo "   python3 analyze_duplicates.py --create-aliases --dry-run"
