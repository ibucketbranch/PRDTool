#!/bin/bash

echo "🔍 Checking Docker status..."
echo ""

# Check if Docker process is running
if ps aux | grep -i "Docker.app" | grep -v grep > /dev/null; then
    echo "✅ Docker Desktop process is running"
else
    echo "❌ Docker Desktop is not running"
    echo "   Run: open -a Docker"
    exit 1
fi

# Check if Docker daemon is responsive
if docker ps &>/dev/null; then
    echo "✅ Docker daemon is responsive"
    echo ""
    echo "📦 Running containers:"
    docker ps --format "table {{.Names}}\t{{.Status}}"
else
    echo "⏳ Docker daemon is starting (not ready yet)"
    echo "   Wait 30-60 seconds and try again"
    exit 1
fi
