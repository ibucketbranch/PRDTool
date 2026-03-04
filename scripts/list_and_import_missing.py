#!/usr/bin/env python3
"""
List missing files from From_GDrive_Unsorted and import them into Photos.
"""
import os
import subprocess
import json
from datetime import datetime

def get_photos_filenames():
    """Get all filenames from Photos library."""
    script = '''tell application "Photos"
        set photoNames to filename of media items
        return photoNames
    end tell'''
    
    try:
        result = subprocess.run(['osascript', '-e', script], 
                              capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            return set([n.strip() for n in result.stdout.split(',') if n.strip()])
    except:
        pass
    return set()

def import_to_photos(file_path, filename):
    """Import a single file into Photos and verify it completed."""
    import time
    
    # First check if it's already there (in case of race condition)
    photos_filenames = get_photos_filenames()
    if filename in photos_filenames:
        return True
    
    # Import the file
    script = f'''tell application "Photos"
        try
            import POSIX file "{file_path}"
            return "SUCCESS"
        on error errMsg
            return "ERROR|" & errMsg
        end try
    end tell'''
    
    try:
        result = subprocess.run(['osascript', '-e', script], 
                              capture_output=True, text=True, timeout=30)
        output = result.stdout.strip()
        
        if "ERROR" in output or "import" in output.lower():
            error_msg = output.split("|", 1)[1] if "|" in output else output
            if "in progress" in error_msg.lower() or "another" in error_msg.lower():
                # Photos is busy - wait and retry
                time.sleep(5)
                return import_to_photos(file_path, filename)  # Retry once
        
        if result.returncode == 0 and "SUCCESS" in output:
            # Wait a moment for Photos to process
            time.sleep(2)
            
            # Verify it's now in Photos
            photos_filenames = get_photos_filenames()
            if filename in photos_filenames:
                return True
            else:
                # Sometimes Photos needs more time - wait a bit longer
                time.sleep(3)
                photos_filenames = get_photos_filenames()
                return filename in photos_filenames
    except Exception as e:
        print(f"Error: {e}")
        pass
    return False

def main():
    unsorted_root = "/Users/michaelvalderrama/Documents/Google Pictures/From_GDrive_Unsorted"
    
    print("="*80)
    print("📋 STEP 1: Identifying Missing Files")
    print("="*80)
    
    # Get all files
    all_files = []
    if os.path.exists(unsorted_root):
        for root, dirs, files in os.walk(unsorted_root):
            for f in files:
                if not f.startswith('.'):
                    full_path = os.path.join(root, f)
                    all_files.append((f, full_path))
    
    print(f"✅ Found {len(all_files)} total files in From_GDrive_Unsorted")
    
    # Get Photos filenames
    print(f"\n📸 Fetching Photos library filenames...")
    photos_filenames = get_photos_filenames()
    print(f"✅ Found {len(photos_filenames)} files in Photos library")
    
    # Find missing files
    missing_files = []
    for filename, file_path in all_files:
        if filename not in photos_filenames:
            missing_files.append((filename, file_path))
    
    print(f"\n{'='*80}")
    print(f"📊 RESULTS:")
    print(f"{'='*80}")
    print(f"  Total files: {len(all_files)}")
    print(f"  Missing from Photos: {len(missing_files)}")
    print(f"{'='*80}")
    
    # Save list to file
    list_file = "/tmp/missing_files_from_unsorted.json"
    missing_data = []
    total_size = 0
    
    for filename, file_path in missing_files:
        try:
            size = os.path.getsize(file_path)
            total_size += size
            missing_data.append({
                "filename": filename,
                "path": file_path,
                "size_bytes": size,
                "size_mb": round(size / (1024*1024), 2)
            })
        except:
            missing_data.append({
                "filename": filename,
                "path": file_path,
                "size_bytes": 0,
                "size_mb": 0
            })
    
    with open(list_file, 'w') as f:
        json.dump(missing_data, f, indent=2)
    
    print(f"\n✅ Saved list to: {list_file}")
    print(f"   Total size of missing files: {total_size / (1024*1024):.2f} MB")
    
    # Display first 10
    print(f"\n📋 First 10 missing files:")
    for i, item in enumerate(missing_data[:10], 1):
        print(f"  {i}. {item['filename']} ({item['size_mb']} MB)")
    
    if len(missing_data) > 10:
        print(f"  ... and {len(missing_data) - 10} more")
    
    # Step 2: Import
    if missing_files:
        print(f"\n{'='*80}")
        print(f"📥 STEP 2: Importing Missing Files into Photos")
        print(f"{'='*80}")
        
        print(f"\n⚠️  This will import {len(missing_files)} files into Photos.")
        print(f"   This may take several minutes...")
        
        imported = 0
        failed = 0
        
        import time
        
        for i, (filename, file_path) in enumerate(missing_files, 1):
            print(f"\n[{i}/{len(missing_files)}] Importing: {filename}...", end=" ", flush=True)
            
            if import_to_photos(file_path, filename):
                imported += 1
                print("✅ Imported & Verified")
            else:
                failed += 1
                print("❌ FAILED or not verified")
            
            # Small delay between imports to avoid overwhelming Photos
            if i < len(missing_files):
                time.sleep(1)
            
            # Progress update every 10 files
            if i % 10 == 0:
                print(f"\n   Progress: {i}/{len(missing_files)} ({i/len(missing_files)*100:.1f}%) - Imported: {imported}, Failed: {failed}")
        
        print(f"\n{'='*80}")
        print(f"✅ IMPORT COMPLETE")
        print(f"{'='*80}")
        print(f"  Successfully imported: {imported}/{len(missing_files)}")
        print(f"  Failed: {failed}/{len(missing_files)}")
        print(f"{'='*80}")
    else:
        print(f"\n✅ All files are already in Photos! Nothing to import.")

if __name__ == "__main__":
    main()
