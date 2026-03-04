#!/bin/bash
# Safe Resume Moving Script
# Moves resumes carefully with dry-run by default

set -e

cd /Users/michaelvalderrama/Websites/TheConversation

SUPABASE_KEY="${SUPABASE_SERVICE_ROLE_KEY:-}"  # Set in .env

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🛡️  SAFE RESUME MOVING - BATCH PROCESSOR"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Default to dry-run if no argument provided
BATCH_SIZE=${1:-5}
EXECUTE=${2:-""}

if [ "$EXECUTE" != "--execute" ]; then
    echo "⚠️  DRY-RUN MODE (no files will be moved)"
    echo "   To actually move files, run: $0 <batch-size> --execute"
    echo ""
    DRY_RUN_FLAG=""
else
    echo "🚨 EXECUTE MODE - Files WILL be moved!"
    echo "   Press Ctrl+C within 5 seconds to cancel..."
    sleep 5
    DRY_RUN_FLAG="--execute"
fi

echo "📋 Processing batch of $BATCH_SIZE resumes..."
echo ""

# Run the resume-only move script
if [ -z "$DRY_RUN_FLAG" ]; then
    SUPABASE_SERVICE_ROLE_KEY="$SUPABASE_KEY" python3 scripts/apply_resume_moves.py \
        --batch-size "$BATCH_SIZE" \
        --supabase-key "$SUPABASE_KEY"
else
    SUPABASE_SERVICE_ROLE_KEY="$SUPABASE_KEY" python3 scripts/apply_resume_moves.py \
        --batch-size "$BATCH_SIZE" \
        --supabase-key "$SUPABASE_KEY" \
        --execute
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ -z "$DRY_RUN_FLAG" ]; then
    echo "✅ Dry-run complete. Review output above."
    echo "   To execute: $0 $BATCH_SIZE --execute"
else
    echo "✅ Batch complete! Files moved and database updated."
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
