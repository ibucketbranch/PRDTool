#!/usr/bin/env python3
"""
Find files in Google Drive that haven't been processed yet.
"""
import os
import hashlib
from supabase import create_client

supabase_url = "http://127.0.0.1:54421"
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(supabase_url, supabase_key)

google_drive_path = "/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive"

def get_file_hash(file_path):
    """Calculate SHA256 hash."""
    try:
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    except:
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

def find_unprocessed():
    """Find unprocessed files."""
    print(f"\n🔍 Finding unprocessed files in Google Drive...")
    
    important_exts = ['.pdf', '.docx', '.xlsx', '.pptx', '.txt', '.rtf']
    unprocessed = []
    
    db_hashes = get_db_hashes()
    
    count = 0
    for root, dirs, files in os.walk(google_drive_path):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        
        for file in files:
            if file.startswith('.'):
                continue
            
            ext = os.path.splitext(file)[1].lower()
            if ext in important_exts:
                file_path = os.path.join(root, file)
                count += 1
                
                # Check by hash
                file_hash = get_file_hash(file_path)
                if file_hash and file_hash not in db_hashes:
                    unprocessed.append({
                        'path': file_path,
                        'name': file,
                        'ext': ext,
                        'hash': file_hash
                    })
                
                if count % 100 == 0:
                    print(f"   Checked {count} files...")
    
    print(f"\n📊 Found {len(unprocessed)} unprocessed files")
    
    # Group by type
    by_type = {}
    for item in unprocessed:
        ext = item['ext']
        if ext not in by_type:
            by_type[ext] = []
        by_type[ext].append(item)
    
    print(f"\n📁 Unprocessed by type:")
    for ext, items in sorted(by_type.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"   {ext}: {len(items)} files")
    
    return unprocessed

if __name__ == "__main__":
    unprocessed = find_unprocessed()
    
    if unprocessed:
        print(f"\n💡 To process these files, run:")
        print(f"   python3 scripts/process_all_gdrive_documents.py")
        print(f"\n   Then to move them to iCloud:")
        print(f"   python3 scripts/move_gdrive_to_icloud.py")
