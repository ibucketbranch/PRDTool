#!/bin/bash
# Quick Database Reset (Simplified)

echo "🔧 Resetting database..."
echo ""

cd /Users/michaelvalderrama/Websites/TheConversation

# Method 1: Try supabase CLI
echo "Attempting: supabase db reset..."
supabase db reset &
RESET_PID=$!

# Wait up to 60 seconds
COUNTER=0
while kill -0 $RESET_PID 2>/dev/null && [ $COUNTER -lt 60 ]; do
    echo -n "."
    sleep 1
    COUNTER=$((COUNTER + 1))
done
echo ""

if kill -0 $RESET_PID 2>/dev/null; then
    echo "⏱️  Still running... this takes time"
    echo "Let it finish in background"
    echo ""
    echo "Check status with: supabase status"
else
    echo "✅ Database reset complete!"
    echo ""
    echo "Now try processing again:"
    echo "  python3 process_oldest_first.py --batch-size 10"
fi
