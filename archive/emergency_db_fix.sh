#!/bin/bash
set -e

echo "🚨 EMERGENCY DATABASE FIX"
echo "========================="
echo ""

cd "$(dirname "$0")"

echo "Step 1: Killing stuck Supabase processes..."
killall supabase 2>/dev/null || true
pkill -f "supabase" 2>/dev/null || true
echo "✓ Killed"
echo ""

echo "Step 2: Checking Docker..."
if ! docker ps &>/dev/null; then
    echo "❌ Docker is not responding!"
    echo ""
    echo "MANUAL FIX REQUIRED:"
    echo "1. Open Docker Desktop app"
    echo "2. Quit Docker completely"
    echo "3. Wait 10 seconds"
    echo "4. Restart Docker"
    echo "5. Run this script again"
    exit 1
fi
echo "✓ Docker is running"
echo ""

echo "Step 3: Stopping Supabase containers..."
timeout 30 docker stop $(docker ps -q --filter "name=supabase_" 2>/dev/null) 2>/dev/null || echo "No containers to stop"
echo "✓ Stopped"
echo ""

echo "Step 4: Removing Supabase containers..."
docker rm $(docker ps -aq --filter "name=supabase_" 2>/dev/null) 2>/dev/null || echo "No containers to remove"
echo "✓ Removed"
echo ""

echo "Step 5: Starting Supabase fresh..."
echo "(This takes 30-60 seconds)"
echo ""
supabase start
echo ""

echo "Step 6: Verifying database..."
supabase status
echo ""

echo "✅ DATABASE FIXED!"
echo ""
echo "Now run: ./run_first_batch.sh"
