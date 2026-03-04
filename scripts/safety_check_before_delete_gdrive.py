#!/usr/bin/env python3
"""
Safety check before deleting Google Drive.
Verifies:
1. All files are accounted for in database
2. Media files (photos/videos) are imported to Photos app
3. Creates a deletion safety report
"""
import os
import sys
import subprocess
from pathlib import Path
from collections import defaultdict
from supabase import create_client
import hashlib

supabase_url = "http://127.0.0.1:54421"
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(supabase_url, supabase_key)

google_drive_path = "/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive"

# Media file extensions
MEDIA_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.heic', '.heif',
    '.mov', '.mp4', '.avi', '.mkv', '.m4v', '.mpg', '.mpeg', '.wmv', '.flv',
    '.cr2', '.nef', '.orf', '.raf', '.rw2', '.arw', '.dng'
}

def get_file_hash(file_path):
    """Calculate SHA256 hash of file."""
    try:
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    except:
        return None

def get_photos_filenames():
    """Get all filenames from Photos app."""
    print("   📸 Checking Photos app...")
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
            # Parse the AppleScript list output
            filenames = []
            for line in result.stdout.strip().split('\n'):
                line = line.strip()
                if line and not line.startswith('{') and not line.startswith('}'):
                    # Remove quotes and commas
                    filename = line.replace('"', '').replace(',', '').strip()
                    if filename:
                        filenames.append(filename)
            return set(filenames)
    except:
        pass
    
    return set()

def get_db_files():
    """Get all files from database."""
    print("   📊 Loading database files...")
    
    db_files = {}
    
    try:
        result = supabase.table('documents')\
            .select('id,file_name,current_path,file_hash')\
            .limit(50000)\
            .execute()
        
        if result.data:
            for doc in result.data:
                file_hash = doc.get('file_hash')
                if file_hash:
                    db_files[file_hash] = {
                        'id': doc['id'],
                        'file_name': doc.get('file_name'),
                        'current_path': doc.get('current_path')
                    }
        
        print(f"      Found {len(db_files)} files in database")
    except Exception as e:
        print(f"      ⚠️  Error: {e}")
    
    return db_files

def scan_google_drive():
    """Scan Google Drive and categorize files."""
    print(f"\n🔍 Scanning Google Drive: {google_drive_path}")
    
    if not os.path.exists(google_drive_path):
        print(f"   ❌ Google Drive path does not exist!")
        return {}, {}
    
    all_files = {}
    media_files = {}
    by_type = defaultdict(list)
    
    total_size = 0
    media_size = 0
    
    for root, dirs, files in os.walk(google_drive_path):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        
        for file in files:
            if file.startswith('.'):
                continue
            
            file_path = os.path.join(root, file)
            
            try:
                file_size = os.path.getsize(file_path)
                total_size += file_size
                
                ext = os.path.splitext(file)[1].lower()
                relative_path = os.path.relpath(file_path, google_drive_path)
                
                # Calculate hash for important files
                if ext in ['.pdf', '.doc', '.docx', '.txt'] or ext in MEDIA_EXTENSIONS:
                    file_hash = get_file_hash(file_path)
                else:
                    file_hash = None
                
                file_info = {
                    'name': file,
                    'path': file_path,
                    'relative_path': relative_path,
                    'size': file_size,
                    'hash': file_hash,
                    'ext': ext
                }
                
                all_files[file_path] = file_info
                by_type[ext or '(no extension)'].append(file_info)
                
                # Track media files separately
                if ext in MEDIA_EXTENSIONS:
                    media_files[file_path] = file_info
                    media_size += file_size
                    
            except Exception as e:
                pass
    
    print(f"   Found {len(all_files):,} files ({total_size / (1024**3):.2f} GB)")
    print(f"   Found {len(media_files):,} media files ({media_size / (1024**3):.2f} GB)")
    
    return all_files, media_files

def check_safety(all_files, media_files, db_files, photos_filenames):
    """Check if it's safe to delete Google Drive."""
    print(f"\n{'='*80}")
    print("🛡️  SAFETY CHECK")
    print(f"{'='*80}")
    
    # Check documents
    print(f"\n📄 DOCUMENT FILES:")
    matched_docs = []
    unmatched_docs = []
    
    for file_path, file_info in all_files.items():
        if file_info['ext'] in MEDIA_EXTENSIONS:
            continue  # Skip media, check separately
        
        file_hash = file_info.get('hash')
        if file_hash and file_hash in db_files:
            matched_docs.append(file_info)
        else:
            unmatched_docs.append(file_info)
    
    print(f"   ✅ Matched in database: {len(matched_docs)}")
    print(f"   ⚠️  NOT in database: {len(unmatched_docs)}")
    
    # Check media files
    print(f"\n📸 MEDIA FILES:")
    matched_media = []
    unmatched_media = []
    not_in_photos = []
    
    for file_path, file_info in media_files.items():
        filename = file_info['name']
        
        # Check if in Photos app
        if filename in photos_filenames:
            matched_media.append(file_info)
        else:
            not_in_photos.append(file_info)
        
        # Also check database
        file_hash = file_info.get('hash')
        if file_hash and file_hash in db_files:
            if file_info not in matched_media:
                matched_media.append(file_info)
        else:
            if file_info not in unmatched_media:
                unmatched_media.append(file_info)
    
    print(f"   ✅ In Photos app: {len([m for m in matched_media if m['name'] in photos_filenames])}")
    print(f"   ⚠️  NOT in Photos app: {len(not_in_photos)}")
    print(f"   ⚠️  NOT in database: {len(unmatched_media)}")
    
    # Safety assessment
    print(f"\n{'='*80}")
    print("⚠️  SAFETY ASSESSMENT")
    print(f"{'='*80}")
    
    total_unmatched = len(unmatched_docs) + len(not_in_photos)
    total_files = len(all_files)
    match_rate = ((total_files - total_unmatched) / total_files * 100) if total_files > 0 else 0
    
    print(f"\n  Total files in Google Drive: {total_files:,}")
    print(f"  Matched/Accounted for: {total_files - total_unmatched:,} ({match_rate:.1f}%)")
    print(f"  ⚠️  Unmatched/Unaccounted: {total_unmatched:,} ({100-match_rate:.1f}%)")
    
    if total_unmatched == 0:
        print(f"\n  ✅ SAFE TO DELETE - All files are accounted for!")
        safe = True
    elif match_rate >= 95:
        print(f"\n  ⚠️  MOSTLY SAFE - {match_rate:.1f}% accounted for")
        print(f"     Review {total_unmatched} unmatched files before deleting")
        safe = False
    else:
        print(f"\n  ❌ NOT SAFE - Only {match_rate:.1f}% accounted for")
        print(f"     {total_unmatched} files need to be processed before deleting")
        safe = False
    
    # Show unmatched files
    if unmatched_docs:
        print(f"\n{'='*80}")
        print("⚠️  UNMATCHED DOCUMENTS (Not in Database)")
        print(f"{'='*80}")
        
        by_folder = defaultdict(list)
        for item in unmatched_docs[:200]:  # Limit for display
            folder = '/'.join(item['relative_path'].split('/')[:-1])
            if not folder:
                folder = '(root)'
            by_folder[folder].append(item)
        
        for folder, items in sorted(by_folder.items(), key=lambda x: len(x[1]), reverse=True)[:20]:
            print(f"\n  📁 {folder}: {len(items)} files")
            for item in items[:5]:
                print(f"     - {item['name']}")
            if len(items) > 5:
                print(f"     ... and {len(items) - 5} more")
    
    if not_in_photos:
        print(f"\n{'='*80}")
        print("⚠️  MEDIA FILES NOT IN PHOTOS APP")
        print(f"{'='*80}")
        
        by_folder = defaultdict(list)
        for item in not_in_photos[:200]:
            folder = '/'.join(item['relative_path'].split('/')[:-1])
            if not folder:
                folder = '(root)'
            by_folder[folder].append(item)
        
        for folder, items in sorted(by_folder.items(), key=lambda x: len(x[1]), reverse=True)[:20]:
            print(f"\n  📁 {folder}: {len(items)} files")
            for item in items[:5]:
                print(f"     - {item['name']}")
            if len(items) > 5:
                print(f"     ... and {len(items) - 5} more")
    
    return safe, unmatched_docs, not_in_photos

def main():
    print("="*80)
    print("🛡️  GOOGLE DRIVE DELETION SAFETY CHECK")
    print("="*80)
    
    # Load database
    db_files = get_db_files()
    
    # Get Photos app filenames
    photos_filenames = get_photos_filenames()
    print(f"      Found {len(photos_filenames)} files in Photos app")
    
    # Scan Google Drive
    all_files, media_files = scan_google_drive()
    
    if not all_files:
        print("\n❌ No files found in Google Drive")
        return
    
    # Safety check
    safe, unmatched_docs, not_in_photos = check_safety(
        all_files, media_files, db_files, photos_filenames
    )
    
    # Final recommendation
    print(f"\n{'='*80}")
    print("📋 RECOMMENDATION")
    print(f"{'='*80}")
    
    if safe:
        print(f"\n✅ SAFE TO DELETE GOOGLE DRIVE")
        print(f"   All files are accounted for in database or Photos app")
    else:
        print(f"\n⚠️  NOT YET SAFE TO DELETE")
        print(f"\n   Before deleting, you should:")
        if unmatched_docs:
            print(f"   1. Process {len(unmatched_docs)} unmatched documents into database")
        if not_in_photos:
            print(f"   2. Import {len(not_in_photos)} media files into Photos app")
        print(f"\n   After processing, run this script again to verify safety")
    
    print(f"\n{'='*80}")
    print("✅ Safety check complete")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
