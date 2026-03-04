#!/usr/bin/env python3
"""
Scan iCloud for media files and check which are in Photos app.
Media files should be in Photos, not in folders.
"""
import os
import subprocess
from pathlib import Path
from collections import defaultdict

icloud_base = "/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs"

MEDIA_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.heic', '.heif',
    '.mov', '.mp4', '.avi', '.mkv', '.m4v', '.mpg', '.mpeg', '.wmv', '.flv',
    '.cr2', '.nef', '.orf', '.raf', '.rw2', '.arw', '.dng', '.webp', '.svg'
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

def find_media_files_in_icloud():
    """Find all media files in iCloud."""
    print(f"\n🔍 Scanning iCloud for media files...")
    print(f"   Path: {icloud_base}")
    
    media_files = []
    by_type = defaultdict(list)
    by_folder = defaultdict(list)
    total_size = 0
    
    count = 0
    for root, dirs, files in os.walk(icloud_base):
        # Skip system folders
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'Library']
        
        for file in files:
            if file.startswith('.'):
                continue
            
            ext = os.path.splitext(file)[1].lower()
            if ext in MEDIA_EXTENSIONS:
                file_path = os.path.join(root, file)
                try:
                    file_size = os.path.getsize(file_path)
                    relative_path = os.path.relpath(file_path, icloud_base)
                    folder = '/'.join(relative_path.split('/')[:-1])
                    
                    media_files.append({
                        'path': file_path,
                        'name': file,
                        'ext': ext,
                        'size': file_size,
                        'folder': folder
                    })
                    by_type[ext].append(file)
                    by_folder[folder].append(file)
                    total_size += file_size
                    count += 1
                    
                    if count % 100 == 0:
                        print(f"   Found {count} media files...")
                except Exception as e:
                    pass
    
    print(f"\n📊 Found {len(media_files):,} media files ({total_size / (1024**3):.2f} GB)")
    
    print(f"\n   By type:")
    for ext, files in sorted(by_type.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"      {ext}: {len(files):,} files")
    
    return media_files, by_folder

def check_photos_status(media_files, photos_filenames):
    """Check which media files are in Photos."""
    print(f"\n{'='*80}")
    print("📊 MEDIA FILES STATUS")
    print(f"{'='*80}")
    
    in_photos = []
    not_in_photos = []
    
    for item in media_files:
        filename = item['name']
        if filename in photos_filenames:
            in_photos.append(item)
        else:
            not_in_photos.append(item)
    
    print(f"\n✅ In Photos app: {len(in_photos):,} files")
    print(f"⚠️  NOT in Photos app: {len(not_in_photos):,} files")
    
    # Calculate sizes
    in_photos_size = sum(item['size'] for item in in_photos)
    not_in_photos_size = sum(item['size'] for item in not_in_photos)
    
    print(f"\n   Size in Photos: {in_photos_size / (1024**3):.2f} GB")
    print(f"   Size NOT in Photos: {not_in_photos_size / (1024**3):.2f} GB")
    
    # Show files not in Photos by folder
    if not_in_photos:
        print(f"\n{'='*80}")
        print(f"⚠️  MEDIA FILES NOT IN PHOTOS (by folder)")
        print(f"{'='*80}")
        
        by_folder = defaultdict(list)
        for item in not_in_photos:
            by_folder[item['folder']].append(item)
        
        for folder, items in sorted(by_folder.items(), key=lambda x: len(x[1]), reverse=True)[:20]:
            folder_size = sum(i['size'] for i in items)
            print(f"\n  📁 {folder}: {len(items)} files ({folder_size / (1024**2):.1f} MB)")
            for item in items[:5]:
                print(f"     - {item['name']}")
            if len(items) > 5:
                print(f"     ... and {len(items) - 5} more")
    
    return in_photos, not_in_photos

def main():
    print("="*80)
    print("📸 iCLOUD MEDIA FILES SCAN")
    print("="*80)
    print("\n💡 Media files should be in Photos app, not in folders.")
    print("="*80)
    
    # Get Photos filenames
    photos_filenames = get_photos_filenames()
    
    # Find media files in iCloud
    media_files, by_folder = find_media_files_in_icloud()
    
    if not media_files:
        print("\n✅ No media files found in iCloud")
        return
    
    # Check Photos status
    in_photos, not_in_photos = check_photos_status(media_files, photos_filenames)
    
    # Summary
    print(f"\n{'='*80}")
    print("📋 SUMMARY")
    print(f"{'='*80}")
    
    total = len(media_files)
    in_photos_pct = (len(in_photos) / total * 100) if total > 0 else 0
    
    if len(not_in_photos) == 0:
        print(f"\n✅ ALL MEDIA FILES ARE IN PHOTOS")
        print(f"   Perfect! All {len(in_photos):,} media files are in Photos app.")
    elif in_photos_pct >= 95:
        print(f"\n⚠️  MOSTLY IN PHOTOS - {in_photos_pct:.1f}%")
        print(f"   {len(not_in_photos)} files still need to be imported to Photos")
    else:
        print(f"\n⚠️  NEEDS ATTENTION - Only {in_photos_pct:.1f}% in Photos")
        print(f"   {len(not_in_photos)} files need to be imported to Photos")
    
    if not_in_photos:
        print(f"\n💡 To import remaining files to Photos:")
        print(f"   python3 scripts/import_icloud_media_to_photos.py")
    
    print(f"\n{'='*80}")

if __name__ == "__main__":
    main()
