#!/bin/bash
# Test compression on a single video to verify quality

NETV_DIR="$HOME/Library/Mobile Documents/com~apple~CloudDocs/Personal Bin/NetV"
TEST_FILE="indica-1.mp4"  # Change this to test different video

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

cd "$NETV_DIR" || exit 1

if [ ! -f "$TEST_FILE" ]; then
    echo -e "${RED}Test file not found: $TEST_FILE${NC}"
    exit 1
fi

input="$NETV_DIR/$TEST_FILE"
output="$NETV_DIR/${TEST_FILE%.mp4}_compressed_test.mp4"

# Get original size
original_size=$(stat -f%z "$input")
original_size_mb=$((original_size / 1024 / 1024))

echo -e "${GREEN}Testing compression on: $TEST_FILE${NC}"
echo "Original size: ${original_size_mb}MB"
echo "Output: $output"
echo ""

echo "Compressing using hardware acceleration..."
start_time=$(date +%s)

ffmpeg -i "$input" \
    -c:v hevc_videotoolbox \
    -b:v 3500k \
    -tag:v hvc1 \
    -c:a aac \
    -b:a 128k \
    -movflags +faststart \
    "$output" \
    -y

if [ $? -eq 0 ] && [ -f "$output" ]; then
    end_time=$(date +%s)
    duration=$((end_time - start_time))
    
    compressed_size=$(stat -f%z "$output")
    compressed_size_mb=$((compressed_size / 1024 / 1024))
    reduction=$((100 - (compressed_size * 100 / original_size)))
    
    echo ""
    echo -e "${GREEN}✓ Compression successful!${NC}"
    echo "Original: ${original_size_mb}MB"
    echo "Compressed: ${compressed_size_mb}MB"
    echo "Reduction: ${reduction}%"
    echo "Time taken: ${duration}s"
    echo ""
    echo "Please review the compressed file: $output"
    echo "If quality is acceptable, you can delete the test file and run the full compression script."
else
    echo -e "${RED}✗ Compression failed${NC}"
    rm -f "$output"
fi
