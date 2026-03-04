#!/bin/bash
# Quick batch processor - Use this!

# Set GROQ_API_KEY in .env or: export GROQ_API_KEY="your_key"
[ -f .env ] && source .env

cd /Users/michaelvalderrama/Websites/TheConversation
source venv/bin/activate

echo "🚀 Ready to batch process!"
echo ""
echo "Choose a folder to start with:"
echo ""
echo "1. Books folder (oldest, Dec 2021)"
echo "   ./run_this.sh books"
echo ""
echo "2. Personal Bin"
echo "   ./run_this.sh personal"
echo ""
echo "3. Work Bin"
echo "   ./run_this.sh work"
echo ""
echo "4. Custom path"
echo "   ./run_this.sh custom \"/path/to/folder\""
echo ""

case "$1" in
    books)
        FOLDER="/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs/Books"
        ;;
    personal)
        FOLDER="/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs/Personal Bin"
        ;;
    work)
        FOLDER="/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs/Work Bin"
        ;;
    custom)
        FOLDER="$2"
        ;;
    *)
        echo "Usage: ./run_this.sh [books|personal|work|custom]"
        exit 1
        ;;
esac

echo "📁 Processing: $FOLDER"
echo ""
echo "🔍 Step 1: Dry-run (preview only)"
python3 batch_processor.py "$FOLDER" --dry-run --batch-size 5

echo ""
read -p "👉 Look good? Process for real? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "🚀 Step 2: Processing batch..."
    python3 batch_processor.py "$FOLDER" --process --batch-size 5
fi
