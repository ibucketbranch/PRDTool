#!/bin/bash
# Fix Database Issues

echo "🔧 Fixing database issues..."
echo ""

cd /Users/michaelvalderrama/Websites/TheConversation

echo "1. Resetting database and applying all migrations..."
supabase db reset

echo ""
echo "2. Checking database status..."
supabase status

echo ""
echo "✅ Database should be fixed!"
echo ""
echo "Now try processing again:"
echo "  python3 process_oldest_first.py --batch-size 10"
