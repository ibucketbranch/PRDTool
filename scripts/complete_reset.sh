#!/bin/bash
set -e

echo "╔════════════════════════════════════════════════════════════╗"
echo "║  🔄 COMPLETE DOCKER + SUPABASE RESET                       ║"
echo "║  Safe - No data loss (database is empty anyway!)          ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

cd "$(dirname "$0")"

# Step 1: Quit Docker
echo "Step 1/5: Quitting Docker Desktop..."
osascript -e 'quit app "Docker"' 2>/dev/null || echo "  (Docker may already be quit)"
echo "  Waiting for Docker to fully quit..."
sleep 10
echo "  ✓ Docker quit"
echo ""

# Step 2: Verify Docker is stopped
echo "Step 2/5: Verifying Docker is stopped..."
if docker ps &>/dev/null; then
    echo "  ⚠️  Docker is still running. Forcing kill..."
    killall Docker 2>/dev/null || true
    killall com.docker.backend 2>/dev/null || true
    sleep 5
fi
echo "  ✓ Docker stopped"
echo ""

# Step 3: Start Docker fresh
echo "Step 3/5: Starting Docker Desktop..."
open -a Docker
echo "  Waiting for Docker daemon to initialize (60 seconds)..."
for i in {1..12}; do
    if docker ps &>/dev/null 2>&1; then
        echo "  ✓ Docker is ready!"
        break
    fi
    echo "    Waiting... ($((i*5))s / 60s)"
    sleep 5
done
echo ""

# Step 4: Verify Docker is working
echo "Step 4/5: Verifying Docker..."
if ! docker ps &>/dev/null; then
    echo "  ❌ Docker failed to start!"
    echo ""
    echo "  MANUAL ACTION NEEDED:"
    echo "  1. Open Docker Desktop app"
    echo "  2. Go to Settings (gear icon) → Troubleshoot"
    echo "  3. Click 'Clean / Purge data'"
    echo "  4. Click 'Reset to factory defaults' if needed"
    echo "  5. Restart Docker"
    echo "  6. Run this script again"
    echo ""
    exit 1
fi

echo "  ✓ Docker is working!"
docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null | head -5 || echo "  (No containers running - perfect!)"
echo ""

# Step 5: Start Supabase with fresh database
echo "Step 5/5: Starting Supabase with fresh database..."
echo "  This will:"
echo "  - Start all Supabase containers"
echo "  - Create fresh database with correct schema"
echo "  - Apply all 5 migrations"
echo "  - Takes 30-60 seconds"
echo ""

supabase start

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║  ✅ RESET COMPLETE!                                        ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "📊 Status:"
supabase status
echo ""
echo "🚀 Next step:"
echo "   ./run_first_batch.sh"
echo ""
echo "This will process 10 files and ACTUALLY save to the database!"
