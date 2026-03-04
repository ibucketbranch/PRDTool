#!/bin/bash
# Compress NetV videos to HEVC (H.265) format
# Uses hardware acceleration for faster processing on Apple Silicon

NETV_DIR="$HOME/Library/Mobile Documents/com~apple~CloudDocs/Personal Bin/NetV"
BACKUP_DIR="$HOME/Desktop/NetV_Backups"
TEMP_DIR="$HOME/Desktop/NetV_Temp"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}NetV Video Compression Script${NC}"
echo "================================"
echo ""

# Create backup and temp directories
mkdir -p "$BACKUP_DIR"
mkdir -p "$TEMP_DIR"

# Get list of MP4 files
cd "$NETV_DIR" || exit 1
files=($(ls -1S *.mp4 2>/dev/null))
total=${#files[@]}

if [ $total -eq 0 ]; then
    echo -e "${RED}No MP4 files found in NetV directory${NC}"
    exit 1
fi

echo "Found $total video files to compress"
echo "Starting compression using hardware acceleration (M3 Pro)"
echo ""

# Process each file
for i in "${!files[@]}"; do
    file="${files[$i]}"
    file_num=$((i + 1))
    
    input="$NETV_DIR/$file"
    output="$TEMP_DIR/${file%.mp4}_compressed.mp4"
    
    # Get original file size
    original_size=$(stat -f%z "$input" 2>/dev/null)
    original_size_mb=$((original_size / 1024 / 1024))
    
    echo -e "${YELLOW}[$file_num/$total] Processing: $file${NC}"
    echo "  Original size: ${original_size_mb}MB"
    echo "  Output: $output"
    
    # Use hardware acceleration (hevc_videotoolbox) with quality setting
    # Using bitrate mode for hardware encoder (CRF not supported)
    # Targeting ~3-4Mbps bitrate (should give ~60% reduction)
    start_time=$(date +%s)
    
    ffmpeg -i "$input" \
        -c:v hevc_videotoolbox \
        -b:v 3500k \
        -tag:v hvc1 \
        -c:a aac \
        -b:a 128k \
        -movflags +faststart \
        "$output" \
        -y \
        -loglevel error \
        -stats \
        2>&1 | grep -E "time=|frame="
    
    if [ ${PIPESTATUS[0]} -eq 0 ] && [ -f "$output" ]; then
        # Check compressed file size
        compressed_size=$(stat -f%z "$output" 2>/dev/null)
        compressed_size_mb=$((compressed_size / 1024 / 1024))
        reduction=$((100 - (compressed_size * 100 / original_size)))
        end_time=$(date +%s)
        duration=$((end_time - start_time))
        
        echo -e "${GREEN}  ✓ Compressed: ${compressed_size_mb}MB (${reduction}% reduction)${NC}"
        echo "  Time taken: ${duration}s"
        
        # Ask before replacing (comment out for automatic)
        # For now, we'll backup and replace
        echo "  Backing up original..."
        cp "$input" "$BACKUP_DIR/$file" || echo -e "${RED}  ✗ Backup failed!${NC}"
        
        echo "  Replacing original with compressed version..."
        mv "$output" "$input" || echo -e "${RED}  ✗ Replace failed!${NC}"
        
        echo ""
    else
        echo -e "${RED}  ✗ Compression failed for $file${NC}"
        rm -f "$output"
        echo ""
    fi
done

echo -e "${GREEN}Compression complete!${NC}"
echo ""
echo "Backups saved to: $BACKUP_DIR"
echo "You can delete backups after verifying compressed videos work correctly"
