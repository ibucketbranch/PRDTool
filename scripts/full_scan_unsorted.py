#!/usr/bin/env python3
"""
Full scan of From_GDrive_Unsorted folder with hash, filename, and import date verification.
"""
import os
import hashlib
import subprocess
import random
from datetime import datetime

def get_file_hash(file_path):
    """Calculate SHA256 hash of file."""
    try:
        with open(file_path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception as e:
        return None

def get_photos_metadata(filename):
    """Get date and name for a specific file in Photos."""
    script = f'''tell application "Photos"
        set foundItem to missing value
        set allItems to media items
        repeat with aItem in allItems
            try
                if filename of aItem is "{filename}" then
                    set foundItem to aItem
                    exit repeat
                end if
            end try
        end repeat
        
        if foundItem is not missing value then
            set itemDate to date of foundItem
            set itemName to name of foundItem
            return (itemDate as string) & "|" & itemName
        else
            return "NOT_FOUND"
        end if
    end tell'''
    
    try:
        result = subprocess.run(['osascript', '-e', script], 
                              capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            output = result.stdout.strip()
            if output != "NOT_FOUND" and "|" in output:
                parts = output.split('|', 1)
                return parts[0], parts[1] if len(parts) > 1 else ""
    except:
        pass
    return None, None

def main():
    unsorted_root = "/Users/michaelvalderrama/Documents/Google Pictures/From_GDrive_Unsorted"
    all_files = []
    
    print("="*80)
    print("🔍 FULL SCAN: From_GDrive_Unsorted Folder")
    print("="*80)
    
    # Collect all files
    print(f"\n📂 Scanning folder: {unsorted_root}")
    if os.path.exists(unsorted_root):
        for root, dirs, files in os.walk(unsorted_root):
            for f in files:
                if not f.startswith('.'):
                    full_path = os.path.join(root, f)
                    all_files.append((f, full_path))
    
    total_files = len(all_files)
    print(f"✅ Found {total_files} total files")
    
    # Get all Photos filenames
    print(f"\n📸 Fetching all Photos filenames...")
    script = '''tell application "Photos"
        set photoNames to filename of media items
        return photoNames
    end tell'''
    
    photos_filenames = set()
    try:
        result = subprocess.run(['osascript', '-e', script], 
                              capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            photos_filenames = set([n.strip() for n in result.stdout.split(',') if n.strip()])
            print(f"✅ Found {len(photos_filenames)} files in Photos library")
    except Exception as e:
        print(f"❌ Error fetching Photos filenames: {e}")
        return
    
    # Categorize files
    found_files = []
    not_found_files = []
    
    print(f"\n🔍 Categorizing files...")
    for filename, file_path in all_files:
        if filename in photos_filenames:
            found_files.append((filename, file_path))
        else:
            not_found_files.append((filename, file_path))
    
    found_count = len(found_files)
    not_found_count = len(not_found_files)
    match_rate = (found_count / total_files * 100) if total_files > 0 else 0
    
    print(f"\n{'='*80}")
    print(f"📊 SCAN RESULTS:")
    print(f"{'='*80}")
    print(f"  Total files scanned: {total_files}")
    print(f"  ✅ Found in Photos: {found_count} ({match_rate:.1f}%)")
    print(f"  ❌ NOT in Photos: {not_found_count} ({100-match_rate:.1f}%)")
    print(f"{'='*80}")
    
    # Pick examples for detailed verification
    print(f"\n{'='*80}")
    print(f"🔐 DETAILED VERIFICATION EXAMPLES")
    print(f"{'='*80}")
    
    # 3 examples of FOUND files
    print(f"\n✅ EXAMPLES OF FILES FOUND IN PHOTOS:")
    if found_files:
        examples_found = random.sample(found_files, min(3, len(found_files)))
        for i, (filename, file_path) in enumerate(examples_found, 1):
            print(f"\n  Example {i}: {filename}")
            print(f"  {'-'*76}")
            
            # Hash
            file_hash = get_file_hash(file_path)
            if file_hash:
                print(f"    🔐 SHA256 Hash: {file_hash[:32]}...{file_hash[-16:]}")
            
            # File info
            try:
                stat = os.stat(file_path)
                size = stat.st_size / (1024*1024)
                mtime = datetime.fromtimestamp(stat.st_mtime)
                print(f"    📏 Size: {size:.2f} MB")
                print(f"    📂 File Modified: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
            except:
                pass
            
            # Photos metadata
            date_str, name = get_photos_metadata(filename)
            if date_str:
                print(f"    📅 Import Date: {date_str}")
            if name:
                print(f"    📝 Name in Photos: {name}")
            print(f"    📍 Source Path: {file_path}")
    
    # 3 examples of NOT FOUND files
    print(f"\n❌ EXAMPLES OF FILES NOT FOUND IN PHOTOS:")
    if not_found_files:
        examples_not_found = random.sample(not_found_files, min(3, len(not_found_files)))
        for i, (filename, file_path) in enumerate(examples_not_found, 1):
            print(f"\n  Example {i}: {filename}")
            print(f"  {'-'*76}")
            
            # Hash
            file_hash = get_file_hash(file_path)
            if file_hash:
                print(f"    🔐 SHA256 Hash: {file_hash[:32]}...{file_hash[-16:]}")
            
            # File info
            try:
                stat = os.stat(file_path)
                size = stat.st_size / (1024*1024)
                mtime = datetime.fromtimestamp(stat.st_mtime)
                print(f"    📏 Size: {size:.2f} MB")
                print(f"    📂 File Modified: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
            except:
                pass
            
            print(f"    ⚠️ Status: NOT FOUND in Photos library")
            print(f"    📍 Source Path: {file_path}")
    else:
        print(f"    ✅ All files are in Photos!")
    
    print(f"\n{'='*80}")
    print(f"✅ FULL SCAN COMPLETE")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
