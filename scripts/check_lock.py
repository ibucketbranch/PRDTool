#!/usr/bin/env python3
"""Quick lock file checker for bash scripts"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from lock_manager import read_lock, check_warnings
from datetime import datetime

lock = read_lock()
warnings = check_warnings()

if warnings:
    print("⚠️  WARNINGS DETECTED:")
    for w in warnings:
        print(f"   - {w}")
    sys.exit(1)

if lock.get("processing_active"):
    print("⚠️  Processing is currently active!")
    sys.exit(1)

print("✅ Lock file check passed")
sys.exit(0)
