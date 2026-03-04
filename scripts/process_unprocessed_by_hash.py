#!/usr/bin/env python3
"""
Process files from Google Drive that are NOT in database by hash.
This is more accurate than path-based checking.
"""
import os
import sys
import hashlib
from pathlib import Path
from supabase import create_client

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from document_processor import DocumentProcessor

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
        print(f"   ⚠️  Error hashing {os.path.basename(file_path)}: {e}")
        return None

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
                
                # Check by hash
                file_hash = get_file_hash(file_path)
                if file_hash and file_hash not in db_hashes:
                    unprocessed.append(file_path)
                
                if count % 100 == 0:
                    print(f"   Checked {count} files, found {len(unprocessed)} unprocessed...")
    
    print(f"\n📊 Found {len(unprocessed)} unprocessed files (by hash)")
    
    # Group by type
    by_type = {}
    for file_path in unprocessed:
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in by_type:
            by_type[ext] = []
        by_type[ext].append(file_path)
    
    print(f"\n📁 Unprocessed by type:")
    for ext, files in sorted(by_type.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"   {ext}: {len(files)} files")
    
    return unprocessed

def main():
    print("="*80)
    print("📋 PROCESS UNPROCESSED FILES (BY HASH)")
    print("="*80)
    
    # Get database hashes
    db_hashes = get_db_hashes()
    
    # Find unprocessed files
    unprocessed = find_unprocessed_files(db_hashes)
    
    if not unprocessed:
        print("\n✅ All files are already processed!")
        return
    
    # Initialize processor
    print(f"\n🤖 Initializing document processor...")
    processor = DocumentProcessor()
    
    # Process files
    print(f"\n{'='*80}")
    print("📦 PROCESSING FILES")
    print(f"{'='*80}")
    
    processed = 0
    skipped = 0
    errors = 0
    
    for i, file_path in enumerate(unprocessed, 1):
        filename = os.path.basename(file_path)
        print(f"\n[{i}/{len(unprocessed)}] Processing: {filename}")
        
        try:
            result = processor.process_document(file_path, skip_if_exists=False)
            if result.get('status') == 'success':
                processed += 1
                print(f"   ✅ Processed")
            elif result.get('status') == 'skipped':
                skipped += 1
                print(f"   ⊘ Skipped (already exists)")
            else:
                errors += 1
                error_msg = result.get('error', 'Unknown error')
                print(f"   ❌ Error: {error_msg}")
        except Exception as e:
            errors += 1
            print(f"   ❌ Exception: {e}")
    
    print(f"\n{'='*80}")
    print("📊 SUMMARY")
    print(f"{'='*80}")
    print(f"  Processed: {processed}")
    print(f"  Skipped: {skipped}")
    print(f"  Errors: {errors}")
    print(f"  Total: {len(unprocessed)}")
    print(f"\n{'='*80}")
    print("✅ Processing complete")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
