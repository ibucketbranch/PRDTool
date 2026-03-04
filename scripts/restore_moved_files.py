#!/usr/bin/env python3
"""Restore files from canonical_move_log.jsonl back to original locations"""
import json
import shutil
from pathlib import Path
import sys

LOG_FILE = Path.home() / ".document_system" / "canonical_move_log.jsonl"

def restore_file(target_path, dry_run=True):
    """Restore a single file from move log"""
    with open(LOG_FILE, 'r') as f:
        for line in f:
            try:
                data = json.loads(line.strip())
                if data.get('dry_run') == False:
                    if data.get('target') == str(target_path):
                        source = Path(data.get('source'))
                        target = Path(data.get('target'))
                        
                        if not target.exists():
                            print(f"❌ Target file not found: {target}")
                            return False
                        
                        if dry_run:
                            print(f"Would restore: {target.name}")
                            print(f"  From: {target}")
                            print(f"  To: {source}")
                        else:
                            source.parent.mkdir(parents=True, exist_ok=True)
                            shutil.move(str(target), str(source))
                            print(f"✅ Restored: {source.name}")
                            print(f"  To: {source}")
                        return True
            except:
                pass
    return False

def restore_by_pattern(pattern, dry_run=True):
    """Restore all files matching pattern"""
    restored = 0
    with open(LOG_FILE, 'r') as f:
        for line in f:
            try:
                data = json.loads(line.strip())
                if data.get('dry_run') == False:
                    source = data.get('source', '')
                    target = data.get('target', '')
                    
                    if pattern.lower() in source.lower() or pattern.lower() in target.lower():
                        source_path = Path(source)
                        target_path = Path(target)
                        
                        if not target_path.exists():
                            continue
                        
                        if dry_run:
                            print(f"Would restore: {target_path.name}")
                            print(f"  From: {target_path}")
                            print(f"  To: {source_path}")
                            print('')
                        else:
                            source_path.parent.mkdir(parents=True, exist_ok=True)
                            shutil.move(str(target_path), str(source_path))
                            print(f"✅ Restored: {source_path.name}")
                        restored += 1
            except Exception as e:
                print(f"Error: {e}")
                pass
    
    return restored

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--pattern", help="Pattern to match (e.g., 'Opportunities 2025', 'resume')")
    parser.add_argument("--execute", action="store_true", help="Actually restore (default: dry-run)")
    args = parser.parse_args()
    
    if args.pattern:
        count = restore_by_pattern(args.pattern, dry_run=not args.execute)
        print(f"\n{'Would restore' if not args.execute else 'Restored'} {count} files")
    else:
        print("Usage: python3 restore_moved_files.py --pattern 'Opportunities 2025' [--execute]")
