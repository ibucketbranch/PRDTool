#!/usr/bin/env python3
"""
Delete duplicate document files (same name + same size).
Keeps the "best" copy (prefers organized bins over archives).
Updates database after deletion.
"""
import os
import sys
from collections import defaultdict
from supabase import create_client
from datetime import datetime

supabase_url = "http://127.0.0.1:54421"
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(supabase_url, supabase_key)

icloud_base = "/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs"

# Document extensions
DOC_EXTENSIONS = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.rtf', '.pages', '.numbers', '.key'}

# Priority order for keeping files (higher priority = keep this one)
KEEP_PRIORITY = {
    'personal bin': 100,
    'work bin': 100,
    'finances bin': 100,
    'legal bin': 100,
    'family bin': 100,
    'projects bin': 100,
    'employment': 90,
    'documents': 80,
    'archive': 10,
    'wysearchive': 5,
    'old': 5,
    'backup': 5,
}

def get_keep_priority(path):
    """Get priority score for keeping a file (higher = better to keep)."""
    path_lower = path.lower()
    for keyword, priority in KEEP_PRIORITY.items():
        if keyword in path_lower:
            return priority
    return 50  # Default priority

def find_duplicates():
    """Find duplicate documents by name + size."""
    print("="*80)
    print("🔍 FINDING DUPLICATE DOCUMENTS")
    print("="*80)
    print()
    
    size_map = defaultdict(list)
    doc_count = 0
    
    print("Scanning files...")
    for root, dirs, files in os.walk(icloud_base):
        dirs[:] = [d for d in dirs if d not in ['.git', 'node_modules', '__pycache__', '.Trash']]
        
        for f in files:
            if f.startswith('.'):
                continue
            ext = os.path.splitext(f)[1].lower()
            if ext not in DOC_EXTENSIONS:
                continue
                
            file_path = os.path.join(root, f)
            try:
                size = os.path.getsize(file_path)
                if size > 0:
                    size_map[size].append(file_path)
                    doc_count += 1
            except:
                pass
    
    print(f"Scanned {doc_count:,} document files")
    
    # Find duplicates by name + size
    duplicates = []
    for size, paths in size_map.items():
        if len(paths) > 1:
            name_map = defaultdict(list)
            for p in paths:
                name = os.path.basename(p)
                name_map[name].append(p)
            
            for name, same_name_paths in name_map.items():
                if len(same_name_paths) > 1:
                    duplicates.append({
                        'name': name,
                        'size': size,
                        'paths': same_name_paths
                    })
    
    print(f"Found {len(duplicates):,} duplicate groups")
    total_dup_files = sum(len(d['paths']) for d in duplicates)
    print(f"Total duplicate files: {total_dup_files:,}")
    
    return duplicates

def delete_duplicates(duplicates, dry_run=True):
    """Delete duplicate files, keeping the best copy."""
    print(f"\n{'='*80}")
    if dry_run:
        print("📦 DUPLICATE DELETION PLAN (DRY RUN)")
    else:
        print("🗑️  DELETING DUPLICATES")
    print(f"{'='*80}")
    print()
    
    deleted_count = 0
    errors = []
    total_space_saved = 0
    
    for dup in duplicates:
        paths = dup['paths']
        if len(paths) <= 1:
            continue
        
        # Sort by priority (keep highest priority)
        paths_sorted = sorted(paths, key=lambda p: get_keep_priority(p), reverse=True)
        keep_path = paths_sorted[0]
        delete_paths = paths_sorted[1:]
        
        if dry_run:
            print(f"📄 {dup['name']} ({len(paths)} copies, {dup['size']:,} bytes)")
            print(f"   ✅ KEEP: {os.path.relpath(keep_path, icloud_base)}")
            for dp in delete_paths:
                print(f"   🗑️  DELETE: {os.path.relpath(dp, icloud_base)}")
        else:
            for dp in delete_paths:
                try:
                    if os.path.exists(dp):
                        file_size = os.path.getsize(dp)
                        os.remove(dp)
                        total_space_saved += file_size
                        deleted_count += 1
                        
                        # Update database
                        try:
                            result = supabase.table('documents')\
                                .select('id')\
                                .eq('current_path', dp)\
                                .limit(1)\
                                .execute()
                            
                            if result.data:
                                doc_id = result.data[0]['id']
                                # Mark as deleted in database
                                supabase.table('documents')\
                                    .update({
                                        'current_path': None,
                                        'notes': f'Deleted duplicate of {keep_path}'
                                    })\
                                    .eq('id', doc_id)\
                                    .execute()
                        except:
                            pass
                        
                        print(f"   ✅ Deleted: {os.path.basename(dp)}")
                except Exception as e:
                    errors.append({'file': dp, 'error': str(e)})
                    print(f"   ❌ Error deleting {os.path.basename(dp)}: {e}")
    
    print(f"\n{'='*80}")
    if dry_run:
        print("📊 DELETION PLAN SUMMARY")
    else:
        print("✅ DELETION COMPLETE")
    print(f"{'='*80}")
    
    if dry_run:
        total_to_delete = sum(len(d['paths']) - 1 for d in duplicates)
        print(f"Files to delete: {total_to_delete:,}")
        total_space = sum((len(d['paths']) - 1) * d['size'] for d in duplicates)
        print(f"Space to free: {total_space / (1024*1024):.1f} MB")
    else:
        print(f"Files deleted: {deleted_count:,}")
        print(f"Space freed: {total_space_saved / (1024*1024):.1f} MB")
        print(f"Errors: {len(errors)}")
    
    if errors and not dry_run:
        print(f"\nErrors encountered:")
        for err in errors[:10]:
            print(f"   - {err['file']}: {err['error']}")
    
    if dry_run:
        print(f"\n💡 To execute deletion, run:")
        print(f"   python3 {sys.argv[0]} --execute")

def main():
    dry_run = '--execute' not in sys.argv
    
    duplicates = find_duplicates()
    
    if not duplicates:
        print("\n✅ No duplicates found!")
        return
    
    delete_duplicates(duplicates, dry_run=dry_run)

if __name__ == "__main__":
    main()
