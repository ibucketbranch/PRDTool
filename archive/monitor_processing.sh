#!/bin/bash
# Monitor the PDF processing progress

echo "======================================================================"
echo "PDF PROCESSING MONITOR"
echo "======================================================================"
echo ""

# Check if process is running
if pgrep -f "simple_direct_processor.py" > /dev/null; then
    echo "✅ Processing is RUNNING"
    echo ""
else
    echo "⏸️  Processing is NOT running"
    echo ""
fi

# Show database count
echo "📊 Database Statistics:"
python3 << 'EOF'
from supabase import create_client
client = create_client('http://127.0.0.1:54421', os.getenv('SUPABASE_SERVICE_ROLE_KEY'))
resp = client.table('documents').select('id', count='exact').execute()
print(f"   Total documents: {resp.count}")
EOF

echo ""
echo "📝 Latest Processing Output:"
echo "----------------------------------------------------------------------"

# Find the latest terminal output
TERMINAL_DIR="/Users/michaelvalderrama/.cursor/projects/Users-michaelvalderrama-Websites-TheConversation/terminals"
LATEST=$(ls -t "$TERMINAL_DIR"/*.txt 2>/dev/null | grep -v "ext-" | head -1)

if [ -n "$LATEST" ]; then
    # Show last 40 lines
    tail -40 "$LATEST"
else
    echo "No terminal output found"
fi

echo ""
echo "======================================================================"
echo "To watch live progress: tail -f $LATEST"
echo "======================================================================"
