#!/bin/bash
# Fast PDF Discovery - NO EXCLUSIONS - EVERY FOLDER SCANNED

OUTPUT="all_pdfs.txt"
rm -f "$OUTPUT"

echo "🔍 Full Discovery - NO EXCLUSIONS - Scanning EVERYTHING..."
echo "⚠️  This will scan ALL folders including Library, Applications, etc."

# Scan EVERYTHING under home - NO EXCLUSIONS
TARGETS=(
    "$HOME"
)

for dir in "${TARGETS[@]}"; do
    if [ -d "$dir" ]; then
        echo "   Scanning $dir (NO EXCLUSIONS)..."
        # Scan EVERYTHING - NO EXCLUSIONS - all data is good data
        find "$dir" -type f -name "*.pdf" >> "$OUTPUT" 2>/dev/null
    else
        echo "   Skipping (not found): $dir"
    fi
done

# Dedup and Count
if [ -f "$OUTPUT" ]; then
    sort -u "$OUTPUT" -o "$OUTPUT"
    COUNT=$(wc -l < "$OUTPUT" | xargs)
    echo "✅ Discovery complete!"
    echo "   Found $COUNT unique PDFs."
    echo "   List saved to $OUTPUT"
else
    echo "❌ No PDFs found."
fi
