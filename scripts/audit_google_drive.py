#!/usr/bin/env python3
"""
Comprehensive audit of Google Drive - account for all files and folders.
Compare with database to see what's been processed, moved, or is missing.
"""
import os
import sys
from pathlib import Path
from collections import defaultdict
from supabase import create_client
import hashlib

supabase_url = "http://127.0.0.1:54421"
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(supabase_url, supabase_key)

google_drive_path = "/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive"

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

def get_all_database_files():
    """Get all files from database (current and historical paths)."""
    print("📊 Loading database files...")
    
    all_files = {}
    
    try:
        # Get all documents
        result = supabase.table('documents')\
            .select('id,file_name,current_path,file_hash')\
            .limit(50000)\
            .execute()
        
        if result.data:
            for doc in result.data:
                file_hash = doc.get('file_hash')
                file_name = doc.get('file_name')
                if file_hash:
                    all_files[file_hash] = {
                        'id': doc['id'],
                        'file_name': file_name,
                        'current_path': doc.get('current_path'),
                        'source': 'documents'
                    }
        
        # Get all document_locations (original/previous paths)
        result = supabase.table('document_locations')\
            .select('document_id,location_path,location_type')\
            .ilike('location_path', '%GoogleDrive%')\
            .limit(10000)\
            .execute()
        
        if result.data:
            doc_ids = list(set([loc['document_id'] for loc in result.data]))
            
            batch_size = 100
            for i in range(0, len(doc_ids), batch_size):
                batch = doc_ids[i:i+batch_size]
                docs_result = supabase.table('documents')\
                    .select('id,file_name,file_hash,current_path')\
                    .in_('id', batch)\
                    .execute()
                
                if docs_result.data:
                    for doc in docs_result.data:
                        file_hash = doc.get('file_hash')
                        if file_hash and file_hash not in all_files:
                            all_files[file_hash] = {
                                'id': doc['id'],
                                'file_name': doc.get('file_name'),
                                'current_path': doc.get('current_path'),
                                'source': 'document_locations'
                            }
    except Exception as e:
        print(f"   ⚠️  Error loading database: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"   Loaded {len(all_files)} unique files from database")
    return all_files

def scan_google_drive(root_path):
    """Scan Google Drive and collect all files."""
    print(f"\n🔍 Scanning Google Drive: {root_path}")
    
    if not os.path.exists(root_path):
        print(f"   ❌ Google Drive path does not exist!")
        return {}, {}
    
    all_files = {}
    folder_structure = defaultdict(list)
    errors = []
    
    total_files = 0
    total_size = 0
    
    for root, dirs, files in os.walk(root_path):
        # Skip hidden/system folders
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        
        folder_path = root
        relative_folder = os.path.relpath(folder_path, root_path)
        
        for file in files:
            if file.startswith('.'):
                continue
            
            file_path = os.path.join(root, file)
            total_files += 1
            
            try:
                file_size = os.path.getsize(file_path)
                total_size += file_size
                
                # Calculate hash for PDFs and important files
                file_ext = os.path.splitext(file)[1].lower()
                if file_ext in ['.pdf', '.doc', '.docx', '.txt']:
                    file_hash = get_file_hash(file_path)
                else:
                    file_hash = None
                
                all_files[file_path] = {
                    'name': file,
                    'path': file_path,
                    'relative_path': os.path.relpath(file_path, root_path),
                    'folder': relative_folder,
                    'size': file_size,
                    'hash': file_hash,
                    'ext': file_ext
                }
                
                folder_structure[relative_folder].append(file)
                
            except Exception as e:
                errors.append((file_path, str(e)))
    
    print(f"   Found {total_files:,} files ({total_size / (1024**3):.2f} GB)")
    if errors:
        print(f"   ⚠️  {len(errors)} errors accessing files")
    
    return all_files, folder_structure

def match_files(google_files, db_files):
    """Match Google Drive files with database records."""
    print(f"\n🔗 Matching files...")
    
    matched = []
    unmatched_google = []
    unmatched_db_hashes = set()
    
    # Match by hash (most reliable)
    for file_path, file_info in google_files.items():
        file_hash = file_info.get('hash')
        if file_hash and file_hash in db_files:
            matched.append({
                'file_path': file_path,
                'file_info': file_info,
                'db_record': db_files[file_hash],
                'match_method': 'hash'
            })
        else:
            # Try matching by filename and path
            file_name = file_info['name']
            matched_by_name = False
            
            for db_hash, db_info in db_files.items():
                if db_info['file_name'] == file_name:
                    # Check if path matches
                    if 'GoogleDrive' in db_info.get('current_path', '') or \
                       any('GoogleDrive' in loc.get('location_path', '') for loc in []):  # Would need to check locations
                        matched.append({
                            'file_path': file_path,
                            'file_info': file_info,
                            'db_record': db_info,
                            'match_method': 'filename'
                        })
                        matched_by_name = True
                        break
            
            if not matched_by_name:
                unmatched_google.append({
                    'file_path': file_path,
                    'file_info': file_info
                })
    
    # Find database files that reference Google Drive but aren't matched
    for db_hash, db_info in db_files.items():
        current_path = db_info.get('current_path', '')
        if 'GoogleDrive' in current_path:
            # Check if we have this file in Google Drive
            found = False
            for match in matched:
                if match['db_record']['id'] == db_info['id']:
                    found = True
                    break
            if not found:
                unmatched_db_hashes.add(db_hash)
    
    print(f"   Matched: {len(matched)}")
    print(f"   Unmatched in Google Drive: {len(unmatched_google)}")
    print(f"   Database references to Google Drive (not found): {len(unmatched_db_hashes)}")
    
    return matched, unmatched_google, unmatched_db_hashes

def main():
    print("="*80)
    print("📋 GOOGLE DRIVE COMPREHENSIVE AUDIT")
    print("="*80)
    
    # Load database
    db_files = get_all_database_files()
    
    # Scan Google Drive
    google_files, folder_structure = scan_google_drive(google_drive_path)
    
    # Match files
    matched, unmatched_google, unmatched_db = match_files(google_files, db_files)
    
    # Report
    print(f"\n{'='*80}")
    print("📊 AUDIT SUMMARY")
    print(f"{'='*80}")
    print(f"  Google Drive files: {len(google_files):,}")
    print(f"  Database files: {len(db_files):,}")
    print(f"  Matched: {len(matched):,}")
    print(f"  Unmatched in Google Drive: {len(unmatched_google):,}")
    print(f"  Database references (not found): {len(unmatched_db)}")
    
    # Show folder structure
    print(f"\n{'='*80}")
    print("📁 GOOGLE DRIVE FOLDER STRUCTURE")
    print(f"{'='*80}")
    
    top_folders = sorted(folder_structure.keys(), key=lambda x: len(folder_structure[x]), reverse=True)[:20]
    
    for folder in top_folders:
        file_count = len(folder_structure[folder])
        print(f"\n  📁 {folder or '(root)'}")
        print(f"     Files: {file_count}")
        
        # Check how many are matched
        matched_in_folder = sum(1 for m in matched if m['file_info']['folder'] == folder)
        unmatched_in_folder = sum(1 for u in unmatched_google if u['file_info']['folder'] == folder)
        
        if matched_in_folder > 0:
            print(f"     ✅ Matched in DB: {matched_in_folder}")
        if unmatched_in_folder > 0:
            print(f"     ⚠️  Not in DB: {unmatched_in_folder}")
    
    # Show unmatched files (sample)
    if unmatched_google:
        print(f"\n{'='*80}")
        print("⚠️  FILES IN GOOGLE DRIVE NOT IN DATABASE (Sample)")
        print(f"{'='*80}")
        
        # Group by folder
        by_folder = defaultdict(list)
        for item in unmatched_google[:100]:  # Limit to first 100
            folder = item['file_info']['folder']
            by_folder[folder].append(item)
        
        for folder, items in sorted(by_folder.items(), key=lambda x: len(x[1]), reverse=True)[:10]:
            print(f"\n  📁 {folder or '(root)'}: {len(items)} files")
            for item in items[:5]:
                print(f"     - {item['file_info']['name']}")
            if len(items) > 5:
                print(f"     ... and {len(items) - 5} more")
    
    # Show database references to Google Drive that aren't found
    if unmatched_db:
        print(f"\n{'='*80}")
        print("⚠️  DATABASE REFERENCES TO GOOGLE DRIVE (Files Not Found)")
        print(f"{'='*80}")
        
        for db_hash in list(unmatched_db)[:20]:
            db_info = db_files[db_hash]
            print(f"  - {db_info['file_name']}")
            print(f"    Current: {db_info.get('current_path', 'Unknown')[:100]}...")
    
    print(f"\n{'='*80}")
    print("✅ AUDIT COMPLETE")
    print(f"{'='*80}")
    
    return {
        'google_files': google_files,
        'db_files': db_files,
        'matched': matched,
        'unmatched_google': unmatched_google,
        'folder_structure': folder_structure
    }

if __name__ == "__main__":
    results = main()
