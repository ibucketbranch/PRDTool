#!/bin/bash
# Safety Check - Verifies Rule #1: Never Delete Files
# This script checks that core processing code never deletes or moves files

echo "🛡️  SAFETY CHECK - RULE #1: Never Delete or Move Files"
echo "=" | head -c 80 && echo ""
echo ""

ERRORS=0
WARNINGS=0

# Check document_processor.py
echo "Checking document_processor.py..."
if grep -qi "shutil\|\.remove\|\.unlink\|os\.remove\|os\.unlink" document_processor.py; then
    echo "   ❌ CRITICAL: Found file deletion/movement code in document_processor.py"
    echo "      This violates Rule #1!"
    ERRORS=$((ERRORS + 1))
    grep -ni "shutil\|\.remove\|\.unlink\|os\.remove\|os\.unlink" document_processor.py
else
    echo "   ✅ PASS: No file deletion/movement code found"
fi

# Check reprocess_by_priority.py
echo ""
echo "Checking scripts/reprocess_by_priority.py..."
if grep -qi "shutil\|\.remove\|\.unlink\|os\.remove\|os\.unlink" scripts/reprocess_by_priority.py; then
    echo "   ❌ CRITICAL: Found file deletion/movement code in reprocess_by_priority.py"
    echo "      This violates Rule #1!"
    ERRORS=$((ERRORS + 1))
    grep -ni "shutil\|\.remove\|\.unlink\|os\.remove\|os\.unlink" scripts/reprocess_by_priority.py
else
    echo "   ✅ PASS: No file deletion/movement code found"
fi

# Check for safety guarantees in code
echo ""
echo "Checking for safety guarantees..."
if grep -qi "RULE #1\|SAFETY GUARANTEE\|never.*delete\|never.*move" document_processor.py; then
    echo "   ✅ PASS: Safety guarantees documented in document_processor.py"
else
    echo "   ⚠️  WARNING: Safety guarantees not found in document_processor.py"
    WARNINGS=$((WARNINGS + 1))
fi

if grep -qi "RULE #1\|SAFETY GUARANTEE\|never.*delete\|never.*move" scripts/reprocess_by_priority.py; then
    echo "   ✅ PASS: Safety guarantees documented in reprocess_by_priority.py"
else
    echo "   ⚠️  WARNING: Safety guarantees not found in reprocess_by_priority.py"
    WARNINGS=$((WARNINGS + 1))
fi

# Summary
echo ""
echo "=" | head -c 80 && echo ""
if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo "✅ ALL CHECKS PASSED - Rule #1 is being followed"
    echo "   Your files are safe!"
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo "⚠️  WARNINGS FOUND - Safety documentation may be missing"
    echo "   But no file deletion code found"
    exit 0
else
    echo "❌ CRITICAL ERRORS FOUND - Rule #1 is violated!"
    echo "   File deletion/movement code detected"
    exit 1
fi
