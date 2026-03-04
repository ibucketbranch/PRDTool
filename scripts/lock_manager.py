#!/usr/bin/env python3
"""
Lock File Manager - Tracks critical state for safety system
"""
import json
from pathlib import Path
from datetime import datetime

LOCK_FILE = Path(__file__).parent.parent / '.supabase' / '.lock'

def read_lock():
    """Read lock file, return dict with defaults if missing"""
    if not LOCK_FILE.exists():
        return {
            "last_backup": None,
            "last_backup_count": 0,
            "last_health_check": None,
            "processing_active": False,
            "last_processed_count": 0,
            "warnings": []
        }
    
    try:
        with open(LOCK_FILE, 'r') as f:
            return json.load(f)
    except:
        return {
            "last_backup": None,
            "last_backup_count": 0,
            "last_health_check": None,
            "processing_active": False,
            "last_processed_count": 0,
            "warnings": []
        }

def write_lock(data):
    """Write lock file"""
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOCK_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def update_backup(count):
    """Update lock file after successful backup"""
    lock = read_lock()
    lock["last_backup"] = datetime.now().isoformat()
    lock["last_backup_count"] = count
    write_lock(lock)

def update_health_check():
    """Update lock file after health check"""
    lock = read_lock()
    lock["last_health_check"] = datetime.now().isoformat()
    write_lock(lock)

def set_processing_active(active, count=0):
    """Update processing status"""
    lock = read_lock()
    lock["processing_active"] = active
    if count > 0:
        lock["last_processed_count"] = count
    write_lock(lock)

def check_warnings():
    """Check for warnings and update lock file"""
    lock = read_lock()
    warnings = []
    
    # Check if processing is stale
    if lock.get("processing_active"):
        # If processing_active but no recent update, might be stale
        # (This is a soft check - process.py should update regularly)
        pass
    
    # Check if backup is stale (>2 hours)
    if lock.get("last_backup"):
        last_backup = datetime.fromisoformat(lock["last_backup"])
        hours_since = (datetime.now() - last_backup).total_seconds() / 3600
        if hours_since > 2:
            warnings.append(f"Last backup was {hours_since:.1f} hours ago")
    
    lock["warnings"] = warnings
    write_lock(lock)
    return warnings

if __name__ == "__main__":
    # Test
    lock = read_lock()
    print(json.dumps(lock, indent=2))
