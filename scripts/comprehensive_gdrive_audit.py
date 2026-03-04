#!/usr/bin/env python3
"""
Comprehensive audit of ALL file types in Google Drive.
Matches with database by filename and hash.
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

# Files/folders to skip
SKIP_PATTERNS = [
    '.DS_Store', '.git', 'node_modules', '__pycache__',
    '.build', '.pbxindex', '.pbxbtree', '.pbxsymbols',
    '.o', '.a', '.dylib', '.framework',
    'build/', '.xcodeproj/', '.xcworkspace/',
]

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

def get_db_files():
    """Get all files from database by filename and hash."""
    print("📊 Loading database files...")
    
    db_by_name = {}
    db_by_hash = {}
    
    try:
        result = supabase.table('documents')\
            .select('id,file_name,current_path,file_hash')\
            .limit(50000)\
            .execute()
        
        if result.data:
            for doc in result.data:
                file_name = doc.get('file_name', '')
                file_hash = doc.get('file_hash')
                
                if file_name:
                    db_by_name[file_name.lower()] = doc
                if file_hash:
                    db_by_hash[file_hash] = doc
        
        print(f"   Found {len(db_by_name)} files by name")
        print(f"   Found {len(db_by_hash)} files by hash")
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
    
    return db_by_name, db_by_hash

def scan_all_files():
    """Scan ALL files in Google Drive."""
    print(f"\n🔍 Scanning ALL files in Google Drive...")
    
    if not os.path.exists(google_drive_path):
        print(f"   ❌ Google Drive path does not exist!")
        return {}
    
    all_files = {}
    by_type = defaultdict(list)
    by_folder = defaultdict(list)
    
    total_size = 0
    count = 0
    
    for root, dirs, files in os.walk(google_drive_path):
        # Filter dirs to skip
        dirs[:] = [d for d in dirs if not any(pattern in d for pattern in SKIP_PATTERNS)]
        
        for file in files:
            if file.startswith('.'):
                continue
            
            # Skip system files
            if any(pattern in file for pattern in SKIP_PATTERNS):
                continue
            
            file_path = os.path.join(root, file)
            count += 1
            
            try:
                file_size = os.path.getsize(file_path)
                total_size += file_size
                
                ext = os.path.splitext(file)[1].lower()
                relative_path = os.path.relpath(file_path, google_drive_path)
                folder = '/'.join(relative_path.split('/')[:-1])
                if not folder:
                    folder = '(root)'
                
                # Calculate hash for important file types
                important_exts = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', 
                                 '.txt', '.rtf', '.pages', '.numbers', '.key', '.zip']
                file_hash = None
                if ext in important_exts:
                    file_hash = get_file_hash(file_path)
                
                file_info = {
                    'name': file,
                    'path': file_path,
                    'relative_path': relative_path,
                    'folder': folder,
                    'size': file_size,
                    'hash': file_hash,
                    'ext': ext
                }
                
                all_files[file_path] = file_info
                by_type[ext or '(no extension)'].append(file_info)
                by_folder[folder].append(file_info)
                
                if count % 1000 == 0:
                    print(f"   Scanned {count:,} files...")
                    
            except Exception as e:
                pass
    
    print(f"   Found {len(all_files):,} files ({total_size / (1024**3):.2f} GB)")
    
    return all_files, by_type, by_folder

def match_files(all_files, db_by_name, db_by_hash):
    """Match Google Drive files with database."""
    print(f"\n🔗 Matching files with database...")
    
    matched_by_name = []
    matched_by_hash = []
    unmatched = []
    
    for file_path, file_info in all_files.items():
        file_name_lower = file_info['name'].lower()
        file_hash = file_info.get('hash')
        
        matched = False
        
        # Try matching by hash first (most reliable)
        if file_hash and file_hash in db_by_hash:
            matched_by_hash.append({
                'file_info': file_info,
                'db_record': db_by_hash[file_hash],
                'match_method': 'hash'
            })
            matched = True
        
        # Try matching by filename
        elif file_name_lower in db_by_name:
            matched_by_name.append({
                'file_info': file_info,
                'db_record': db_by_name[file_name_lower],
                'match_method': 'filename'
            })
            matched = True
        
        if not matched:
            unmatched.append(file_info)
    
    print(f"   ✅ Matched by hash: {len(matched_by_hash)}")
    print(f"   ✅ Matched by filename: {len(matched_by_name)}")
    print(f"   ⚠️  Unmatched: {len(unmatched)}")
    
    return matched_by_hash, matched_by_name, unmatched

def analyze_by_type(by_type, matched_by_hash, matched_by_name, unmatched):
    """Analyze files by type."""
    print(f"\n{'='*80}")
    print("📊 ANALYSIS BY FILE TYPE")
    print(f"{'='*80}")
    
    # Create sets of matched files
    matched_paths = set()
    for m in matched_by_hash + matched_by_name:
        matched_paths.add(m['file_info']['path'])
    
    # Analyze each file type
    type_stats = []
    
    for ext, files in sorted(by_type.items(), key=lambda x: len(x[1]), reverse=True):
        total = len(files)
        matched = sum(1 for f in files if f['path'] in matched_paths)
        unmatched_count = total - matched
        
        if total > 0:
            match_rate = (matched / total * 100)
            type_stats.append({
                'ext': ext,
                'total': total,
                'matched': matched,
                'unmatched': unmatched_count,
                'match_rate': match_rate
            })
    
    print(f"\n{'Extension':<20} {'Total':<10} {'Matched':<10} {'Unmatched':<10} {'Match %':<10}")
    print(f"{'-'*70}")
    
    for stat in type_stats[:30]:  # Top 30
        print(f"{stat['ext']:<20} {stat['total']:<10} {stat['matched']:<10} {stat['unmatched']:<10} {stat['match_rate']:.1f}%")
    
    return type_stats

def show_unmatched_by_type(unmatched, by_type):
    """Show unmatched files grouped by type."""
    print(f"\n{'='*80}")
    print("⚠️  UNMATCHED FILES BY TYPE")
    print(f"{'='*80}")
    
    unmatched_by_type = defaultdict(list)
    for item in unmatched:
        unmatched_by_type[item['ext']].append(item)
    
    for ext, files in sorted(unmatched_by_type.items(), key=lambda x: len(x[1]), reverse=True)[:20]:
        print(f"\n📄 {ext or '(no extension)'}: {len(files)} files")
        
        # Show by folder
        by_folder = defaultdict(list)
        for item in files[:100]:  # Limit for display
            by_folder[item['folder']].append(item)
        
        for folder, items in sorted(by_folder.items(), key=lambda x: len(x[1]), reverse=True)[:5]:
            print(f"   📁 {folder}: {len(items)} files")
            for item in items[:3]:
                print(f"      - {item['name']}")
            if len(items) > 3:
                print(f"      ... and {len(items) - 3} more")

def main():
    print("="*80)
    print("📋 COMPREHENSIVE GOOGLE DRIVE AUDIT - ALL FILE TYPES")
    print("="*80)
    
    # Load database
    db_by_name, db_by_hash = get_db_files()
    
    # Scan all files
    all_files, by_type, by_folder = scan_all_files()
    
    if not all_files:
        print("\n❌ No files found in Google Drive")
        return
    
    # Match files
    matched_by_hash, matched_by_name, unmatched = match_files(all_files, db_by_name, db_by_hash)
    
    # Analyze by type
    type_stats = analyze_by_type(by_type, matched_by_hash, matched_by_name, unmatched)
    
    # Show unmatched by type
    show_unmatched_by_type(unmatched, by_type)
    
    # Summary
    total_files = len(all_files)
    total_matched = len(matched_by_hash) + len(matched_by_name)
    match_rate = (total_matched / total_files * 100) if total_files > 0 else 0
    
    print(f"\n{'='*80}")
    print("📊 SUMMARY")
    print(f"{'='*80}")
    print(f"  Total files in Google Drive: {total_files:,}")
    print(f"  Matched in database: {total_matched:,} ({match_rate:.1f}%)")
    print(f"  Unmatched: {len(unmatched):,} ({100-match_rate:.1f}%)")
    print(f"  File types: {len(by_type)}")
    print(f"  Folders: {len(by_folder)}")
    
    # Show top unmatched file types
    print(f"\n⚠️  TOP UNMATCHED FILE TYPES:")
    unmatched_by_type = defaultdict(int)
    for item in unmatched:
        unmatched_by_type[item['ext']] += 1
    
    for ext, count in sorted(unmatched_by_type.items(), key=lambda x: x[1], reverse=True)[:15]:
        print(f"   {ext or '(no extension)'}: {count:,} files")
    
    print(f"\n{'='*80}")
    print("✅ Audit complete")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
