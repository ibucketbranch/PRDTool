#!/bin/bash
# LIVE DEMONSTRATION - Prove data survives crashes/stops
# This script will:
# 1. Show test documents exist
# 2. Stop Supabase (simulating crash)
# 3. Start Supabase
# 4. Prove data still exists

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"
source venv/bin/activate

echo "=================================================================================="
echo "🔥 LIVE PROOF DEMONSTRATION - Data Persistence Test"
echo "=================================================================================="
echo ""

# Step 1: Show documents exist BEFORE
echo "STEP 1: Counting test documents BEFORE restart..."
python3 scripts/show_proof.py
BEFORE_COUNT=$(python3 -c "
from supabase import create_client
import os
supabase = create_client('http://127.0.0.1:54421', os.getenv('SUPABASE_SERVICE_ROLE_KEY'))
result = supabase.table('documents').select('id', count='exact').ilike('file_name', 'STRESS_TEST_%').execute()
print(result.count if hasattr(result, 'count') else len(result.data))
" 2>/dev/null || echo "0")

echo ""
echo "📊 BEFORE: $BEFORE_COUNT test documents"
echo ""

# Step 2: Create backup
echo "STEP 2: Creating backup..."
python3 scripts/auto_backup.py
echo ""

# Step 3: Stop Supabase (simulating crash)
echo "STEP 3: Stopping Supabase (simulating crash/stop)..."
source scripts/safety_wrapper.sh
safe_supabase_stop
echo ""

# Step 4: Wait
echo "STEP 4: Waiting 5 seconds (simulating system down)..."
sleep 5
echo ""

# Step 5: Start Supabase
echo "STEP 5: Starting Supabase (simulating recovery)..."
safe_supabase_start
echo ""

# Step 6: Wait for DB
echo "STEP 6: Waiting for database to be ready..."
for i in {1..30}; do
    if psql postgresql://postgres:postgres@127.0.0.1:54422/postgres -c "SELECT 1;" > /dev/null 2>&1; then
        echo "✅ Database is ready"
        break
    fi
    sleep 1
done
echo ""

# Step 7: Verify documents still exist
echo "STEP 7: Verifying test documents AFTER restart..."
sleep 2
python3 scripts/show_proof.py
AFTER_COUNT=$(python3 -c "
from supabase import create_client
import os
supabase = create_client('http://127.0.0.1:54421', os.getenv('SUPABASE_SERVICE_ROLE_KEY'))
result = supabase.table('documents').select('id', count='exact').ilike('file_name', 'STRESS_TEST_%').execute()
print(result.count if hasattr(result, 'count') else len(result.data))
" 2>/dev/null || echo "0")

echo ""
echo "📊 AFTER: $AFTER_COUNT test documents"
echo ""

# Step 8: Show proof
echo "=================================================================================="
if [ "$BEFORE_COUNT" = "$AFTER_COUNT" ] && [ "$BEFORE_COUNT" -gt 0 ]; then
    echo "✅ PROOF: Data survived restart!"
    echo "   BEFORE: $BEFORE_COUNT documents"
    echo "   AFTER:  $AFTER_COUNT documents"
    echo "   STATUS: ALL DATA PERSISTED"
else
    echo "❌ FAILED: Data loss detected!"
    echo "   BEFORE: $BEFORE_COUNT documents"
    echo "   AFTER:  $AFTER_COUNT documents"
    exit 1
fi
echo "=================================================================================="
