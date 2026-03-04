#!/usr/bin/env python3
"""
Investigate remaining unprocessed files and errors.
"""
import os
import hashlib
import sys
from pathlib import Path
from supabase import create_client

supabase_url = "http://127.0.0.1:54421"
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(supabase_url, supabase_key)

google_drive_path = "/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive"

IMPORTANT_EXTENSIONS = {'.pdf', '.docx', '.xlsx', '.pptx', '.txt', '.rtf'}

SKIP_PATTERNS = [
    '.DS_Store', '.git', 'node_modules', '__pycache__',
    '.build', '.pbxindex', '.pbxbtree', '.pbxsymbols',
    'build/', '.xcodeproj/', '.xcworkspace/',
    'My Code Projects/',
]

def get_file_hash(file_path):
    """Calculate SHA256 hash."""
    try:
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    except Exception as e:
        return None, str(e)

def get_db_hashes():
    """Get all file hashes from database."""
    print("📊 Loading database hashes...")
    db_hashes = set()
    
    try:
        result = supabase.table('documents')\
            .select('file_hash')\
            .limit(50000)\
            .execute()
        
        if result.data:
            for doc in result.data:
                file_hash = doc.get('file_hash')
                if file_hash:
                    db_hashes.add(file_hash)
        
        print(f"   Found {len(db_hashes)} file hashes in database")
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
    
    return db_hashes

def find_unprocessed_files(db_hashes):
    """Find files in Google Drive that aren't in database by hash."""
    print(f"\n🔍 Finding unprocessed files in Google Drive...")
    
    unprocessed = []
    errors = []
    count = 0
    
    for root, dirs, files in os.walk(google_drive_path):
        dirs[:] = [d for d in dirs if not any(pattern in d for pattern in SKIP_PATTERNS)]
        
        for file in files:
            if file.startswith('.'):
                continue
            
            if any(pattern in file for pattern in SKIP_PATTERNS):
                continue
            
            ext = os.path.splitext(file)[1].lower()
            if ext in IMPORTANT_EXTENSIONS:
                file_path = os.path.join(root, file)
                count += 1
                
                # Try to get hash
                file_hash = get_file_hash(file_path)
                if isinstance(file_hash, tuple):
                    # Error occurred
                    hash_val, error_msg = file_hash
                    errors.append({
                        'path': file_path,
                        'name': file,
                        'ext': ext,
                        'error': error_msg
                    })
                elif file_hash and file_hash not in db_hashes:
                    unprocessed.append({
                        'path': file_path,
                        'name': file,
                        'ext': ext,
                        'hash': file_hash
                    })
                
                if count % 100 == 0:
                    print(f"   Checked {count} files, found {len(unprocessed)} unprocessed, {len(errors)} errors...")
    
    return unprocessed, errors

def analyze_files(unprocessed, errors):
    """Analyze unprocessed files and errors."""
    print("="*80)
    print("📊 INVESTIGATION RESULTS")
    print("="*80)
    
    print(f"\n❌ FILES WITH ERRORS: {len(errors)}")
    if errors:
        print(f"\n   These files could not be hashed (may be corrupted or inaccessible):")
        for i, item in enumerate(errors[:10], 1):
            print(f"\n   {i}. {item['name']}")
            print(f"      Path: {item['path'][:80]}...")
            print(f"      Error: {item['error']}")
        if len(errors) > 10:
            print(f"\n   ... and {len(errors) - 10} more errors")
    
    print(f"\n⚠️  UNPROCESSED FILES: {len(unprocessed)}")
    if unprocessed:
        # Group by type
        by_type = {}
        for item in unprocessed:
            ext = item['ext']
            if ext not in by_type:
                by_type[ext] = []
            by_type[ext].append(item)
        
        print(f"\n   Breakdown by type:")
        for ext, files in sorted(by_type.items(), key=lambda x: len(x[1]), reverse=True):
            print(f"      {ext}: {len(files)} files")
        
        # Group by folder
        by_folder = {}
        for item in unprocessed:
            relative = os.path.relpath(item['path'], google_drive_path)
            folder = '/'.join(relative.split('/')[:-1])
            if not folder:
                folder = '(root)'
            if folder not in by_folder:
                by_folder[folder] = []
            by_folder[folder].append(item)
        
        print(f"\n   Top folders with unprocessed files:")
        for folder, files in sorted(by_folder.items(), key=lambda x: len(x[1]), reverse=True)[:10]:
            print(f"\n      📁 {folder}: {len(files)} files")
            for item in files[:3]:
                print(f"         - {item['name']}")
            if len(files) > 3:
                print(f"         ... and {len(files) - 3} more")
    
    print(f"\n{'='*80}")
    print("💡 RECOMMENDATIONS")
    print(f"{'='*80}")
    
    if errors:
        print(f"\n1. Investigate {len(errors)} files with errors:")
        print(f"   - Check if files are corrupted or inaccessible")
        print(f"   - Try to repair or manually process these files")
    
    if unprocessed:
        print(f"\n2. Process {len(unprocessed)} remaining files:")
        print(f"   Run: python3 scripts/process_unprocessed_by_hash.py")
        print(f"   (This will process only the unprocessed files)")
    
    if not errors and not unprocessed:
        print(f"\n✅ All files are processed!")
    
    print(f"\n{'='*80}")

def main():
    print("="*80)
    print("🔍 INVESTIGATING REMAINING FILES AND ERRORS")
    print("="*80)
    
    # Get database hashes
    db_hashes = get_db_hashes()
    
    # Find unprocessed files
    unprocessed, errors = find_unprocessed_files(db_hashes)
    
    # Analyze
    analyze_files(unprocessed, errors)
    
    return unprocessed, errors

if __name__ == "__main__":
    unprocessed, errors = main()
