#!/usr/bin/env python3
"""
Delete media files from Google Drive that are verified to be in Photos app.
ONLY deletes files that are confirmed to be in Photos - media files belong in Photos, not folders.
"""
import os
import sys
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

def find_verified_media():
    """Find media files in Google Drive that are verified in Photos."""
    print("="*80)
    print("🔍 FINDING VERIFIED MEDIA FILES TO DELETE")
    print("="*80)
    
    # Get Photos filenames
    photos_filenames = get_photos_filenames()
    print(f"   Found {len(photos_filenames):,} files in Photos app")
    
    # Find media files in Google Drive
    print(f"\n🔍 Scanning Google Drive for media files...")
    verified_to_delete = []
    not_verified = []
    
    count = 0
    for root, dirs, files in os.walk(google_drive_path):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        
        for file in files:
            if file.startswith('.'):
                continue
            
            ext = os.path.splitext(file)[1].lower()
            if ext in MEDIA_EXTENSIONS:
                file_path = os.path.join(root, file)
                count += 1
                
                # Check if in Photos
                if file in photos_filenames:
                    try:
                        file_size = os.path.getsize(file_path)
                        verified_to_delete.append({
                            'path': file_path,
                            'name': file,
                            'size': file_size
                        })
                    except:
                        pass
                else:
                    not_verified.append({
                        'path': file_path,
                        'name': file
                    })
                
                if count % 100 == 0:
                    print(f"   Scanned {count} media files...")
    
    print(f"\n📊 Results:")
    print(f"   ✅ Verified in Photos (safe to delete): {len(verified_to_delete):,} files")
    print(f"   ⚠️  NOT in Photos (keep for now): {len(not_verified):,} files")
    
    if verified_to_delete:
        total_size = sum(item['size'] for item in verified_to_delete)
        print(f"   Total size to delete: {total_size / (1024**3):.2f} GB")
    
    return verified_to_delete, not_verified

def delete_verified_files(verified_to_delete, dry_run=True):
    """Delete verified media files from Google Drive."""
    print(f"\n{'='*80}")
    if dry_run:
        print("📦 DELETE PLAN (DRY RUN)")
    else:
        print("🗑️  DELETING VERIFIED MEDIA FILES")
    print(f"{'='*80}")
    
    deleted = 0
    errors = 0
    freed_space = 0
    
    # Group by folder for reporting
    by_folder = defaultdict(list)
    for item in verified_to_delete:
        relative = os.path.relpath(item['path'], google_drive_path)
        folder = '/'.join(relative.split('/')[:-1])
        if not folder:
            folder = '(root)'
        by_folder[folder].append(item)
    
    print(f"\n📁 Files to delete from {len(by_folder)} folders:")
    
    for folder, items in sorted(by_folder.items(), key=lambda x: len(x[1]), reverse=True)[:20]:
        print(f"\n  📁 {folder}: {len(items)} files")
        if not dry_run:
            for item in items[:5]:
                try:
                    os.remove(item['path'])
                    deleted += 1
                    freed_space += item['size']
                    print(f"     ✅ Deleted: {item['name']}")
                except Exception as e:
                    errors += 1
                    print(f"     ❌ Error deleting {item['name']}: {e}")
            if len(items) > 5:
                print(f"     ... deleting {len(items) - 5} more files...")
                for item in items[5:]:
                    try:
                        os.remove(item['path'])
                        deleted += 1
                        freed_space += item['size']
                    except Exception as e:
                        errors += 1
        else:
            for item in items[:3]:
                print(f"     → {item['name']}")
            if len(items) > 3:
                print(f"     ... and {len(items) - 3} more")
    
    if len(by_folder) > 20:
        remaining = sum(len(items) for folder, items in list(by_folder.items())[20:])
        print(f"\n  ... and {remaining} more files in {len(by_folder) - 20} other folders")
        if not dry_run:
            for folder, items in list(by_folder.items())[20:]:
                for item in items:
                    try:
                        os.remove(item['path'])
                        deleted += 1
                        freed_space += item['size']
                    except Exception as e:
                        errors += 1
    
    print(f"\n{'='*80}")
    if dry_run:
        print("📊 DELETE PLAN SUMMARY")
    else:
        print("✅ DELETE COMPLETE")
    print(f"{'='*80}")
    print(f"  Total files: {len(verified_to_delete):,}")
    if not dry_run:
        print(f"  Deleted: {deleted:,}")
        print(f"  Errors: {errors:,}")
        print(f"  Space freed: {freed_space / (1024**3):.2f} GB")
    else:
        print(f"  Would delete: {len(verified_to_delete):,} files")
        print(f"  Would free: {sum(item['size'] for item in verified_to_delete) / (1024**3):.2f} GB")
    
    if dry_run:
        print(f"\n💡 To execute deletion, run:")
        print(f"   python3 {sys.argv[0]} --execute")

def main():
    dry_run = '--execute' not in sys.argv
    
    if not dry_run:
        print("="*80)
        print("⚠️  WARNING: This will DELETE media files from Google Drive")
        print("="*80)
        print("   Only files verified to be in Photos app will be deleted.")
        print("   Media files belong in Photos, not in folders.")
        print()
        response = input("   Continue? (yes/no): ").strip().lower()
        if response != 'yes':
            print("   Cancelled.")
            return
        print()
    
    verified_to_delete, not_verified = find_verified_media()
    
    if not verified_to_delete:
        print("\n✅ No verified media files to delete")
        if not_verified:
            print(f"\n⚠️  {len(not_verified)} media files are NOT in Photos")
            print("   Import them to Photos first, then run this script again")
        return
    
    delete_verified_files(verified_to_delete, dry_run=dry_run)
    
    if not_verified:
        print(f"\n⚠️  NOTE: {len(not_verified)} media files are NOT in Photos")
        print("   These were NOT deleted. Import them to Photos first.")

if __name__ == "__main__":
    main()
