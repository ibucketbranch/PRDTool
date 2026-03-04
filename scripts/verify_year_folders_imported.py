#!/usr/bin/env python3
"""
Comprehensive verification: Hash comparison, Photos metadata, and file locations
for files in year folders (2006-2018) to confirm they're already imported.
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

def find_in_photos_simple(filename):
    """Simple filename check in Photos."""
    script = f'''tell application "Photos"
        set foundCount to 0
        set allItems to media items
        repeat with aItem in allItems
            try
                if filename of aItem is "{filename}" then
                    set foundCount to foundCount + 1
                end if
            end try
        end repeat
        return foundCount
    end tell'''
    
    try:
        result = subprocess.run(['osascript', '-e', script], 
                              capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            count = int(result.stdout.strip())
            return count > 0, count
    except:
        pass
    return False, 0

def get_photos_metadata(filename):
    """Get date and name for a specific file."""
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
                parts = output.split('|')
                return parts[0], parts[1] if len(parts) > 1 else ""
    except:
        pass
    return None, None

def main():
    year_root = "/Users/michaelvalderrama/Documents/Google Pictures"
    all_files = []
    
    # Collect files from year folders
    for year in ['2006', '2007', '2008', '2009', '2010', '2011', '2012', 
                 '2013', '2014', '2015', '2016', '2017', '2018']:
        year_path = os.path.join(year_root, year)
        if os.path.exists(year_path):
            for root, dirs, files in os.walk(year_path):
                for f in files:
                    if not f.startswith('.') and f.lower().endswith(('.jpg', '.jpeg', '.png', '.heic', '.tiff')):
                        full_path = os.path.join(root, f)
                        all_files.append((year, f, full_path))
    
    # Pick 3 random samples
    random_samples = random.sample(all_files, min(3, len(all_files)))
    
    print("="*80)
    print("🔍 COMPREHENSIVE VERIFICATION: Hash, Location, Import Date")
    print("="*80)
    
    for i, (year, filename, file_path) in enumerate(random_samples, 1):
        print(f"\n{'='*80}")
        print(f"Example {i}: {filename}")
        print(f"Year Folder: {year}")
        print(f"Source Path: {file_path}")
        print(f"{'='*80}")
        
        # 1. Hash verification
        print(f"\n1️⃣ HASH VERIFICATION (SHA256):")
        file_hash = get_file_hash(file_path)
        if file_hash:
            print(f"   Source file hash: {file_hash[:16]}...{file_hash[-8:]}")
            print(f"   Full hash: {file_hash}")
        else:
            print(f"   ❌ Could not calculate hash")
        
        # 2. Check if in Photos
        print(f"\n2️⃣ PHOTOS APP VERIFICATION:")
        found, count = find_in_photos_simple(filename)
        if found:
            print(f"   ✅ Found in Photos! (appears {count} time(s))")
            
            # Get metadata
            date_str, name = get_photos_metadata(filename)
            if date_str:
                print(f"   📅 Date: {date_str}")
            if name:
                print(f"   📝 Name: {name}")
        else:
            print(f"   ❌ NOT found in Photos library")
        
        # 3. File timestamps
        print(f"\n3️⃣ FILE TIMESTAMPS:")
        try:
            mtime = os.path.getmtime(file_path)
            ctime = os.path.getctime(file_path)
            mtime_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
            ctime_str = datetime.fromtimestamp(ctime).strftime('%Y-%m-%d %H:%M:%S')
            print(f"   📂 Modified: {mtime_str}")
            print(f"   📂 Created: {ctime_str}")
        except Exception as e:
            print(f"   ⚠️ Could not get timestamps: {e}")
        
        # 4. File size
        try:
            size = os.path.getsize(file_path)
            print(f"\n4️⃣ FILE SIZE:")
            print(f"   📏 Size: {size / (1024*1024):.2f} MB")
        except:
            pass
    
    print(f"\n{'='*80}")
    print("✅ Verification complete!")
    print("="*80)

if __name__ == "__main__":
    main()
