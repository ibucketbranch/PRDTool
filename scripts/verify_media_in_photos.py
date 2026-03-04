#!/usr/bin/env python3
"""
Verify which media files from Google Drive are in Photos app.
Media files should be in Photos, not in folders - once verified, they can be deleted from Google Drive.
"""
import os
import subprocess
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
            timeout=30
        )
        
        if result.returncode == 0:
            filenames = []
            for line in result.stdout.strip().split('\n'):
                line = line.strip()
                if line and not line.startswith('{') and not line.startswith('}'):
                    filename = line.replace('"', '').replace(',', '').strip()
                    if filename:
                        filenames.append(filename)
            return set(filenames)
    except Exception as e:
        print(f"   ⚠️  Error checking Photos: {e}")
    
    return set()

def find_media_files():
    """Find all media files in Google Drive."""
    print(f"\n🔍 Finding media files in Google Drive...")
    
    media_files = []
    by_type = defaultdict(list)
    
    count = 0
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
                    count += 1
                except:
                    pass
    
    print(f"   Found {len(media_files):,} media files")
    print(f"\n   By type:")
    for ext, files in sorted(by_type.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"      {ext}: {len(files):,} files")
    
    return media_files

def verify_in_photos(media_files, photos_filenames):
    """Verify which media files are in Photos."""
    print(f"\n{'='*80}")
    print("📊 VERIFICATION RESULTS")
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
    
    # Safety assessment
    total = len(media_files)
    in_photos_pct = (len(in_photos) / total * 100) if total > 0 else 0
    
    print(f"\n{'='*80}")
    print("🛡️  SAFETY ASSESSMENT")
    print(f"{'='*80}")
    
    if len(not_in_photos) == 0:
        print(f"\n✅ ALL MEDIA FILES ARE IN PHOTOS")
        print(f"   Safe to delete all media files from Google Drive")
        safe = True
    elif in_photos_pct >= 95:
        print(f"\n⚠️  MOSTLY SAFE - {in_photos_pct:.1f}% in Photos")
        print(f"   {len(not_in_photos)} files still need to be imported")
        safe = False
    else:
        print(f"\n❌ NOT SAFE - Only {in_photos_pct:.1f}% in Photos")
        print(f"   {len(not_in_photos)} files need to be imported before deletion")
        safe = False
    
    # Show files not in Photos (sample)
    if not_in_photos:
        print(f"\n{'='*80}")
        print(f"⚠️  MEDIA FILES NOT IN PHOTOS (Sample - {len(not_in_photos)} total)")
        print(f"{'='*80}")
        
        by_folder = defaultdict(list)
        for item in not_in_photos[:100]:
            relative = os.path.relpath(item['path'], google_drive_path)
            folder = '/'.join(relative.split('/')[:-1])
            if not folder:
                folder = '(root)'
            by_folder[folder].append(item)
        
        for folder, items in sorted(by_folder.items(), key=lambda x: len(x[1]), reverse=True)[:10]:
            print(f"\n  📁 {folder}: {len(items)} files")
            for item in items[:3]:
                print(f"     - {item['name']}")
            if len(items) > 3:
                print(f"     ... and {len(items) - 3} more")
    
    return safe, in_photos, not_in_photos

def main():
    print("="*80)
    print("📸 VERIFY MEDIA FILES IN PHOTOS APP")
    print("="*80)
    print("\n💡 Media files should be in Photos app, not in folders.")
    print("   Once verified in Photos, they can be safely deleted from Google Drive.")
    print("="*80)
    
    # Get Photos filenames
    photos_filenames = get_photos_filenames()
    print(f"   Found {len(photos_filenames):,} files in Photos app")
    
    # Find media files in Google Drive
    media_files = find_media_files()
    
    if not media_files:
        print("\n✅ No media files found in Google Drive")
        return
    
    # Verify
    safe, in_photos, not_in_photos = verify_in_photos(media_files, photos_filenames)
    
    # Recommendation
    print(f"\n{'='*80}")
    print("📋 RECOMMENDATION")
    print(f"{'='*80}")
    
    if safe:
        print(f"\n✅ SAFE TO DELETE MEDIA FILES FROM GOOGLE DRIVE")
        print(f"\n   All {len(in_photos):,} media files are verified in Photos app")
        print(f"\n   To delete verified media files, run:")
        print(f"   python3 scripts/delete_verified_media_from_gdrive.py --execute")
    else:
        print(f"\n⚠️  IMPORT REMAINING FILES FIRST")
        print(f"\n   {len(not_in_photos)} media files need to be imported to Photos")
        print(f"\n   After importing, run this script again to verify")
        print(f"   Then delete verified files with:")
        print(f"   python3 scripts/delete_verified_media_from_gdrive.py --execute")
    
    print(f"\n{'='*80}")

if __name__ == "__main__":
    main()
