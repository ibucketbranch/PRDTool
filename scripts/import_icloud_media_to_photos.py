#!/usr/bin/env python3
"""
Import media files from iCloud folders to Photos app.
Media files should be in Photos, not in folders.
"""
import os
import sys
import subprocess
import time
from pathlib import Path
from collections import defaultdict

icloud_base = "/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs"

MEDIA_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.heic', '.heif',
    '.mov', '.mp4', '.avi', '.mkv', '.m4v', '.mpg', '.mpeg', '.wmv', '.flv',
    '.cr2', '.nef', '.orf', '.raf', '.rw2', '.arw', '.dng', '.webp'
}

def get_photos_filenames():
    """Get all filenames from Photos app."""
    print("📸 Checking Photos app...")
    try:
        script = '''tell application "Photos"
            set photoNames to {}
            set allItems to media items
            repeat with item in allItems
                try
                    set end of photoNames to filename of item
                end try
            end repeat
            return photoNames
        end tell'''
        
        result = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True,
            text=True,
            timeout=90
        )
        
        if result.returncode == 0:
            filenames = []
            for line in result.stdout.strip().split('\n'):
                line = line.strip()
                if line and not line.startswith('{') and not line.startswith('}'):
                    filename = line.replace('"', '').replace(',', '').strip()
                    if filename:
                        filenames.append(filename)
            print(f"   Found {len(filenames):,} files in Photos app")
            return set(filenames)
    except Exception as e:
        print(f"   ⚠️  Error checking Photos: {e}")
    
    return set()

def find_media_files():
    """Find all media files in iCloud."""
    print(f"\n🔍 Finding media files in iCloud...")
    
    media_files = []
    by_type = defaultdict(list)
    
    count = 0
    for root, dirs, files in os.walk(icloud_base):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'Library']
        
        for file in files:
            if file.startswith('.'):
                continue
            
            ext = os.path.splitext(file)[1].lower()
            if ext in MEDIA_EXTENSIONS:
                file_path = os.path.join(root, file)
                try:
                    file_size = os.path.getsize(file_path)
                    media_files.append({
                        'path': file_path,
                        'name': file,
                        'ext': ext,
                        'size': file_size
                    })
                    by_type[ext].append(file)
                    count += 1
                    
                    if count % 500 == 0:
                        print(f"   Found {count} media files...")
                except:
                    pass
    
    print(f"   Found {len(media_files):,} media files")
    
    return media_files

def import_to_photos(file_path: str, filename: str, is_video: bool = False) -> bool:
    """Import a single file into Photos."""
    script = f'''tell application "Photos"
        try
            import POSIX file "{file_path}" without prompting skipDuplicates true
            return "SUCCESS"
        on error errMsg
            return "ERROR|" & errMsg
        end try
    end tell'''
    
    try:
        timeout = 180 if is_video else 30
        result = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        output = result.stdout.strip()
        
        if "ERROR" in output:
            return False
        
        if result.returncode == 0 and "SUCCESS" in output:
            if is_video:
                time.sleep(5)
            else:
                time.sleep(1)
            return True
        
        return False
    except subprocess.TimeoutExpired:
        if is_video:
            time.sleep(10)
        return True  # Assume success for timeout
    except Exception as e:
        return False

def main():
    print("="*80)
    print("📸 IMPORT iCLOUD MEDIA FILES TO PHOTOS")
    print("="*80)
    
    # Get Photos filenames
    photos_filenames = get_photos_filenames()
    
    # Find media files
    media_files = find_media_files()
    
    if not media_files:
        print("\n✅ No media files found in iCloud")
        return
    
    # Filter out files already in Photos
    to_import = []
    already_in_photos = []
    
    for item in media_files:
        if item['name'] in photos_filenames:
            already_in_photos.append(item)
        else:
            to_import.append(item)
    
    print(f"\n📊 Status:")
    print(f"   Already in Photos: {len(already_in_photos):,}")
    print(f"   Need to import: {len(to_import):,}")
    
    if not to_import:
        print("\n✅ All media files are already in Photos!")
        return
    
    # Confirm import
    if '--execute' not in sys.argv:
        print(f"\n⚠️  This will import {len(to_import):,} media files to Photos")
        print(f"   This will take a VERY long time (hours/days for this many files)")
        print(f"   Total size: {sum(i['size'] for i in to_import) / (1024**3):.1f} GB")
        print(f"\n   To proceed, run:")
        print(f"   python3 {sys.argv[0]} --execute")
        print(f"\n   Or import specific folders manually via Photos app")
        return
    
    # Import files
    print(f"\n{'='*80}")
    print("📥 IMPORTING FILES TO PHOTOS")
    print(f"{'='*80}")
    print(f"\n⚠️  This will take a VERY long time. Consider importing manually via Photos app.")
    print(f"   Processing {len(to_import):,} files...")
    
    imported = 0
    failed = 0
    is_video_exts = {'.mov', '.mp4', '.avi', '.mkv', '.m4v', '.mpg', '.mpeg', '.wmv', '.flv'}
    
    for i, item in enumerate(to_import, 1):
        filename = item['name']
        file_path = item['path']
        is_video = item['ext'] in is_video_exts
        
        if i % 100 == 0:
            print(f"\n[{i}/{len(to_import)}] Progress: {i/len(to_import)*100:.1f}% - Imported: {imported}, Failed: {failed}")
        
        if import_to_photos(file_path, filename, is_video=is_video):
            imported += 1
        else:
            failed += 1
        
        # Delay between imports
        if i < len(to_import):
            time.sleep(0.5 if not is_video else 2)
    
    print(f"\n{'='*80}")
    print("📊 IMPORT SUMMARY")
    print(f"{'='*80}")
    print(f"  Total files: {len(to_import):,}")
    print(f"  ✅ Imported: {imported:,}")
    print(f"  ❌ Failed: {failed:,}")
    print(f"  Already in Photos: {len(already_in_photos):,}")
    print(f"\n{'='*80}")

if __name__ == "__main__":
    main()
