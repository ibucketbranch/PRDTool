#!/usr/bin/env python3
"""
Import media files from Google Drive to Photos app.
Stages files for manual import if automated import fails.
"""
import os
import shutil
from pathlib import Path
from collections import defaultdict

google_drive_path = "/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive"
staging_folder = "/Users/michaelvalderrama/Documents/Google Pictures/To_Import_From_GDrive"

MEDIA_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.heic', '.heif',
    '.mov', '.mp4', '.avi', '.mkv', '.m4v', '.mpg', '.mpeg', '.wmv', '.flv',
    '.cr2', '.nef', '.orf', '.raf', '.rw2', '.arw', '.dng'
}

def find_media_files():
    """Find all media files in Google Drive."""
    print("="*80)
    print("🔍 FINDING MEDIA FILES IN GOOGLE DRIVE")
    print("="*80)
    
    media_files = []
    by_folder = defaultdict(list)
    
    for root, dirs, files in os.walk(google_drive_path):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        
        for file in files:
            if file.startswith('.'):
                continue
            
            ext = os.path.splitext(file)[1].lower()
            if ext in MEDIA_EXTENSIONS:
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, google_drive_path)
                folder = '/'.join(relative_path.split('/')[:-1])
                
                media_files.append(file_path)
                by_folder[folder].append(file_path)
    
    print(f"\n📊 Found {len(media_files)} media files")
    print(f"   In {len(by_folder)} folders")
    
    # Show breakdown
    print(f"\n📁 Top folders with media:")
    for folder, files in sorted(by_folder.items(), key=lambda x: len(x[1]), reverse=True)[:10]:
        print(f"   {folder}: {len(files)} files")
    
    return media_files

def stage_for_import(media_files):
    """Stage media files for import into Photos."""
    print(f"\n{'='*80}")
    print("📦 STAGING FILES FOR IMPORT")
    print(f"{'='*80}")
    
    # Create staging folder
    os.makedirs(staging_folder, exist_ok=True)
    
    staged = 0
    errors = 0
    
    for file_path in media_files[:1000]:  # Limit to first 1000 for now
        try:
            filename = os.path.basename(file_path)
            dest_path = os.path.join(staging_folder, filename)
            
            # Handle duplicates
            counter = 1
            while os.path.exists(dest_path):
                name, ext = os.path.splitext(filename)
                dest_path = os.path.join(staging_folder, f"{name}_{counter}{ext}")
                counter += 1
            
            shutil.copy2(file_path, dest_path)
            staged += 1
            
            if staged % 100 == 0:
                print(f"   Staged {staged} files...")
                
        except Exception as e:
            errors += 1
    
    print(f"\n✅ Staged {staged} files in: {staging_folder}")
    if errors > 0:
        print(f"   ⚠️  {errors} errors")
    
    print(f"\n💡 Next steps:")
    print(f"   1. Open Photos app")
    print(f"   2. Go to File → Import...")
    print(f"   3. Navigate to: {staging_folder}")
    print(f"   4. Select all files and click 'Import All'")
    
    return staged

if __name__ == "__main__":
    media_files = find_media_files()
    
    if media_files:
        print(f"\n💡 To stage files for import, run:")
        print(f"   python3 scripts/import_gdrive_media_to_photos.py --stage")
        
        if '--stage' in sys.argv:
            stage_for_import(media_files)
