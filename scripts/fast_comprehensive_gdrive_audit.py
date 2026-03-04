#!/usr/bin/env python3
"""
Fast comprehensive audit of ALL file types in Google Drive.
Matches by filename (no hashing for speed).
"""
import os
from collections import defaultdict
from supabase import create_client

supabase_url = "http://127.0.0.1:54421"
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(supabase_url, supabase_key)

google_drive_path = "/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive"

SKIP_PATTERNS = [
    '.DS_Store', '.git', 'node_modules', '__pycache__',
    '.build', '.pbxindex', '.pbxbtree', '.pbxsymbols',
    '.o', '.a', '.dylib', '.framework',
    'build/', '.xcodeproj/', '.xcworkspace/',
]

def get_db_files_by_name():
    """Get all files from database by filename."""
    print("📊 Loading database files...")
    
    db_by_name = {}
    
    try:
        result = supabase.table('documents')\
            .select('id,file_name,current_path')\
            .limit(50000)\
            .execute()
        
        if result.data:
            for doc in result.data:
                file_name = doc.get('file_name', '')
                if file_name:
                    db_by_name[file_name.lower()] = doc
        
        print(f"   Found {len(db_by_name)} files in database")
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
    
    return db_by_name

def scan_all_files():
    """Scan ALL files in Google Drive - fast version."""
    print(f"\n🔍 Scanning ALL files in Google Drive...")
    
    if not os.path.exists(google_drive_path):
        print(f"   ❌ Google Drive path does not exist!")
        return {}, {}, {}
    
    all_files = {}
    by_type = defaultdict(list)
    by_folder = defaultdict(list)
    
    total_size = 0
    count = 0
    
    for root, dirs, files in os.walk(google_drive_path):
        dirs[:] = [d for d in dirs if not any(pattern in d for pattern in SKIP_PATTERNS)]
        
        for file in files:
            if file.startswith('.'):
                continue
            
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
                
                file_info = {
                    'name': file,
                    'path': file_path,
                    'relative_path': relative_path,
                    'folder': folder,
                    'size': file_size,
                    'ext': ext
                }
                
                all_files[file_path] = file_info
                by_type[ext or '(no extension)'].append(file_info)
                by_folder[folder].append(file_info)
                
                if count % 5000 == 0:
                    print(f"   Scanned {count:,} files...")
                    
            except:
                pass
    
    print(f"   Found {len(all_files):,} files ({total_size / (1024**3):.2f} GB)")
    
    return all_files, by_type, by_folder

def match_files(all_files, db_by_name):
    """Match Google Drive files with database by filename."""
    print(f"\n🔗 Matching files with database...")
    
    matched = []
    unmatched = []
    
    for file_path, file_info in all_files.items():
        file_name_lower = file_info['name'].lower()
        
        if file_name_lower in db_by_name:
            matched.append({
                'file_info': file_info,
                'db_record': db_by_name[file_name_lower],
                'match_method': 'filename'
            })
        else:
            unmatched.append(file_info)
    
    print(f"   ✅ Matched: {len(matched)}")
    print(f"   ⚠️  Unmatched: {len(unmatched)}")
    
    return matched, unmatched

def analyze_by_type(by_type, matched, unmatched):
    """Analyze files by type."""
    print(f"\n{'='*80}")
    print("📊 ANALYSIS BY FILE TYPE")
    print(f"{'='*80}")
    
    matched_paths = {m['file_info']['path'] for m in matched}
    
    type_stats = []
    
    for ext, files in sorted(by_type.items(), key=lambda x: len(x[1]), reverse=True):
        total = len(files)
        matched_count = sum(1 for f in files if f['path'] in matched_paths)
        unmatched_count = total - matched_count
        
        if total > 0:
            match_rate = (matched_count / total * 100)
            type_stats.append({
                'ext': ext,
                'total': total,
                'matched': matched_count,
                'unmatched': unmatched_count,
                'match_rate': match_rate
            })
    
    print(f"\n{'Extension':<20} {'Total':<12} {'Matched':<12} {'Unmatched':<12} {'Match %':<10}")
    print(f"{'-'*80}")
    
    for stat in type_stats[:40]:  # Top 40 file types
        print(f"{stat['ext']:<20} {stat['total']:<12} {stat['matched']:<12} {stat['unmatched']:<12} {stat['match_rate']:.1f}%")
    
    return type_stats

def show_unmatched_important_types(unmatched):
    """Show unmatched files for important document types."""
    print(f"\n{'='*80}")
    print("⚠️  UNMATCHED IMPORTANT DOCUMENT TYPES")
    print(f"{'='*80}")
    
    important_exts = {
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
        '.txt', '.rtf', '.pages', '.numbers', '.key', '.csv'
    }
    
    unmatched_by_type = defaultdict(list)
    for item in unmatched:
        if item['ext'] in important_exts:
            unmatched_by_type[item['ext']].append(item)
    
    for ext, files in sorted(unmatched_by_type.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"\n📄 {ext}: {len(files)} files not in database")
        
        # Show by folder
        by_folder = defaultdict(list)
        for item in files[:200]:
            by_folder[item['folder']].append(item)
        
        for folder, items in sorted(by_folder.items(), key=lambda x: len(x[1]), reverse=True)[:10]:
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
    db_by_name = get_db_files_by_name()
    
    # Scan all files
    all_files, by_type, by_folder = scan_all_files()
    
    if not all_files:
        print("\n❌ No files found in Google Drive")
        return
    
    # Match files
    matched, unmatched = match_files(all_files, db_by_name)
    
    # Analyze by type
    type_stats = analyze_by_type(by_type, matched, unmatched)
    
    # Show unmatched important types
    show_unmatched_important_types(unmatched)
    
    # Summary
    total_files = len(all_files)
    total_matched = len(matched)
    match_rate = (total_matched / total_files * 100) if total_files > 0 else 0
    
    print(f"\n{'='*80}")
    print("📊 SUMMARY")
    print(f"{'='*80}")
    print(f"  Total files in Google Drive: {total_files:,}")
    print(f"  Matched in database: {total_matched:,} ({match_rate:.1f}%)")
    print(f"  Unmatched: {len(unmatched):,} ({100-match_rate:.1f}%)")
    print(f"  File types: {len(by_type)}")
    print(f"  Folders: {len(by_folder)}")
    
    # Count important unmatched files
    important_exts = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.rtf', '.pages', '.numbers', '.key', '.csv'}
    important_unmatched = [f for f in unmatched if f['ext'] in important_exts]
    
    print(f"\n⚠️  IMPORTANT DOCUMENTS NOT IN DATABASE:")
    print(f"   {len(important_unmatched)} files need processing")
    
    # Breakdown by type
    print(f"\n   Breakdown:")
    for ext in sorted(important_exts):
        count = sum(1 for f in unmatched if f['ext'] == ext)
        if count > 0:
            print(f"   {ext}: {count:,} files")
    
    print(f"\n{'='*80}")
    print("✅ Audit complete")
    print(f"{'='*80}")
    print(f"\n💡 To process unmatched files, run:")
    print(f"   python3 document_processor.py --path '{google_drive_path}'")

if __name__ == "__main__":
    main()
