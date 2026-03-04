#!/bin/bash
# Quick status check for video compression

NETV_DIR="$HOME/Library/Mobile Documents/com~apple~CloudDocs/Personal Bin/NetV"
LOG_FILE="$HOME/Websites/TheConversation/compression_log.txt"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=== Video Compression Status ===${NC}"
echo ""

# Check if process is running
if pgrep -f "compress_netv_videos.sh" > /dev/null; then
    echo -e "${GREEN}✓ Compression script is RUNNING${NC}"
    
    # Get current file being processed
    current_file=$(ps aux | grep "ffmpeg.*NetV" | grep -v grep | head -1 | sed 's/.*NetV\///' | sed 's/_compressed.*//' | sed 's/.*-i.*\///' | awk '{print $NF}')
    if [ ! -z "$current_file" ]; then
        echo -e "  Currently processing: ${YELLOW}$current_file${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Compression script is NOT running${NC}"
fi

echo ""

# Count completed files (files modified today, excluding test file)
cd "$NETV_DIR" 2>/dev/null || exit 1
today=$(date +%Y%m%d)
today_count=$(stat -f "%Sm %N" -t "%Y%m%d" *.mp4 2>/dev/null | grep "^$today" | grep -v test | wc -l | tr -d ' ')
total_count=$(ls -1 *.mp4 2>/dev/null | grep -v "compressed_test" | wc -l | tr -d ' ')

echo -e "${BLUE}Progress:${NC} $today_count / $total_count files compressed"
if [ $total_count -gt 0 ]; then
    percent=$((today_count * 100 / total_count))
    echo -e "  ${GREEN}$percent% complete${NC}"
    remaining=$((total_count - today_count))
    echo "  $remaining files remaining"
fi

echo ""

# Show recent activity from log
if [ -f "$LOG_FILE" ]; then
    echo -e "${BLUE}Recent activity:${NC}"
    grep -i "compressed:" "$LOG_FILE" 2>/dev/null | tail -3 | sed 's/.*✓/  ✓/' || echo "  (checking log...)"
    
    # Show current processing
    current_line=$(tail -20 "$LOG_FILE" 2>/dev/null | grep -i "processing:" | tail -1)
    if [ ! -z "$current_line" ]; then
        echo ""
        echo -e "${YELLOW}Current:${NC} $current_line" | sed 's/.*\[/  \[/'
    fi
fi

echo ""

# Show size savings
echo -e "${BLUE}Current folder size:${NC}"
du -sh "$NETV_DIR" 2>/dev/null | awk '{print "  " $1}'
