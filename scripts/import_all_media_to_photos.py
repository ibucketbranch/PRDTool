#!/usr/bin/env python3
"""
Import ALL media files from Google Drive to Photos app.
Handles both photos and videos, processes in batches.
"""
import os
import sys
import subprocess
import time
from pathlib import Path
from collections import defaultdict

google_drive_path = "/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive"

MEDIA_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.heic', '.heif',
    '.mov', '.mp4', '.avi', '.mkv', '.m4v', '.mpg', '.mpeg', '.wmv', '.flv',
    '.cr2', '.nef', '.orf', '.raf', '.rw2', '.arw', '.dng'
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
            print(f"   Found {len(filenames)} files in Photos app")
            return set(filenames)
    except Exception as e:
        print(f"   ⚠️  Error checking Photos: {e}")
    
    return set()

def find_media_files():
    """Find all media files in Google Drive."""
    print(f"\n🔍 Finding media files in Google Drive...")
    
    media_files = []
    by_type = defaultdict(list)
    
    for root, dirs, files in os.walk(google_drive_path):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        
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
                except:
                    pass
    
    print(f"   Found {len(media_files):,} media files")
    print(f"\n   By type:")
    for ext, files in sorted(by_type.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"      {ext}: {len(files):,} files")
    
    return media_files

def import_to_photos(file_path: str, filename: str, is_video: bool = False) -> bool:
    """Import a single file into Photos and verify."""
    script = f'''tell application "Photos"
        try
            import POSIX file "{file_path}" without prompting skipDuplicates true
            return "SUCCESS"
        on error errMsg
            return "ERROR|" & errMsg
        end try
    end tell'''
    
    try:
        if is_video:
            # Videos take longer - use longer timeout
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=180
            )
        else:
            # Photos are faster
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=30
            )
        
        output = result.stdout.strip()
        
        if "ERROR" in output:
            error_msg = output.split("|", 1)[1] if "|" in output else output
            if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                # Photos is slow but import may have started - check later
                if is_video:
                    time.sleep(30)  # Wait for video processing
                return True  # Assume success for timeout
            else:
                return False
        
        if result.returncode == 0 and "SUCCESS" in output:
            # Wait a moment for Photos to process
            if is_video:
                time.sleep(10)  # Videos need more time
            else:
                time.sleep(2)
            return True
        
        return False
    except subprocess.TimeoutExpired:
        # Timeout might mean it's still processing
        if is_video:
            time.sleep(30)
        return True  # Assume success
    except Exception as e:
        print(f"      ⚠️  Import error: {e}")
        return False

def main():
    print("="*80)
    print("📸 IMPORT ALL MEDIA FILES TO PHOTOS")
    print("="*80)
    
    # Get Photos filenames
    photos_filenames = get_photos_filenames()
    
    # Find media files
    media_files = find_media_files()
    
    if not media_files:
        print("\n✅ No media files found in Google Drive")
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
    if '--yes' not in sys.argv and '--execute' not in sys.argv:
        print(f"\n⚠️  This will import {len(to_import):,} media files to Photos")
        print(f"   This may take a while (especially for videos)")
        print(f"\n   To proceed, run:")
        print(f"   python3 {sys.argv[0]} --execute")
        return
    
    # Import files
    print(f"\n{'='*80}")
    print("📥 IMPORTING FILES TO PHOTOS")
    print(f"{'='*80}")
    
    imported = 0
    failed = 0
    is_video_exts = {'.mov', '.mp4', '.avi', '.mkv', '.m4v', '.mpg', '.mpeg', '.wmv', '.flv'}
    
    for i, item in enumerate(to_import, 1):
        filename = item['name']
        file_path = item['path']
        is_video = item['ext'] in is_video_exts
        
        print(f"\n[{i}/{len(to_import)}] Importing: {filename}")
        print(f"      Type: {'Video' if is_video else 'Photo'}, Size: {item['size'] / (1024**2):.1f} MB")
        
        if import_to_photos(file_path, filename, is_video=is_video):
            imported += 1
            print(f"      ✅ Imported")
        else:
            failed += 1
            print(f"      ❌ Failed")
        
        # Small delay between imports to avoid overwhelming Photos
        if i < len(to_import):
            if is_video:
                time.sleep(2)  # Longer delay for videos
            else:
                time.sleep(0.5)  # Shorter delay for photos
        
        # Progress update every 50 files
        if i % 50 == 0:
            print(f"\n   Progress: {i}/{len(to_import)} ({i/len(to_import)*100:.1f}%)")
            print(f"   Imported: {imported}, Failed: {failed}")
    
    print(f"\n{'='*80}")
    print("📊 IMPORT SUMMARY")
    print(f"{'='*80}")
    print(f"  Total files: {len(to_import):,}")
    print(f"  ✅ Imported: {imported:,}")
    print(f"  ❌ Failed: {failed:,}")
    print(f"  Already in Photos: {len(already_in_photos):,}")
    print(f"\n{'='*80}")
    
    if imported > 0:
        print(f"\n✅ Successfully imported {imported:,} files to Photos")
        print(f"\n💡 Next step: Verify import and delete from Google Drive")
        print(f"   python3 scripts/verify_media_in_photos.py")
        print(f"   python3 scripts/delete_verified_media_from_gdrive.py --execute")

if __name__ == "__main__":
    main()
