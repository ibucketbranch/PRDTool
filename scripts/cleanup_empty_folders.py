#!/usr/bin/env python3
"""
Find and delete empty folders after processing.
Also checks database to confirm files were moved before deleting.
"""
import os
import sys
from pathlib import Path
from supabase import create_client
from collections import defaultdict

supabase_url = "http://127.0.0.1:54421"
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(supabase_url, supabase_key)

def check_files_in_folder(folder_path):
    """Check if database has any files from this folder - DEEP SEARCH."""
    try:
        folder_name = os.path.basename(folder_path.rstrip())
        folder_normalized = folder_path.strip().replace('\\', '/')
        
        all_found = []
        
        # Strategy 1: Exact path match
        result = supabase.table('documents')\
            .select('id,file_name,current_path')\
            .ilike('current_path', f'%{folder_path}%')\
            .execute()
        
        if result.data:
            all_found.extend(result.data)
        
        # Strategy 2: Check document_locations with exact path
        result = supabase.table('document_locations')\
            .select('document_id,location_path,location_type')\
            .ilike('location_path', f'%{folder_path}%')\
            .execute()
        
        if result.data:
            doc_ids = list(set([loc['document_id'] for loc in result.data]))
            docs_result = supabase.table('documents')\
                .select('id,file_name,current_path')\
                .in_('id', doc_ids)\
                .execute()
            
            # Add unique documents
            existing_ids = {doc['id'] for doc in all_found}
            for doc in docs_result.data:
                if doc['id'] not in existing_ids:
                    all_found.append(doc)
        
        # Strategy 3: Folder name match (more comprehensive)
        # Get all document_locations and check if folder name appears in path
        result = supabase.table('document_locations')\
            .select('document_id,location_path,location_type')\
            .ilike('location_path', f'%{folder_name}%')\
            .limit(500)\
            .execute()
        
        if result.data:
            # Filter to only those that actually contain this specific folder
            for loc in result.data:
                loc_path = loc['location_path'].strip().replace('\\', '/')
                # Check if this path actually contains our folder (not just similar name)
                if folder_normalized.lower() in loc_path.lower():
                    doc_id = loc['document_id']
                    # Check if we already have this doc
                    if not any(doc['id'] == doc_id for doc in all_found):
                        docs_result = supabase.table('documents')\
                            .select('id,file_name,current_path')\
                            .eq('id', doc_id)\
                            .execute()
                        
                        if docs_result.data:
                            all_found.append(docs_result.data[0])
        
        return all_found
    except Exception as e:
        print(f"   ⚠️  Error checking database: {e}")
        import traceback
        traceback.print_exc()
        return []

def find_empty_folders(root_path, dry_run=True, force_empty=False):
    """Find empty folders and check if they're safe to delete."""
    print("="*80)
    print("🧹 EMPTY FOLDER CLEANUP")
    print("="*80)
    
    if not os.path.exists(root_path):
        print(f"❌ Root path does not exist: {root_path}")
        return
    
    print(f"\n🔍 Scanning: {root_path}")
    print(f"   Mode: {'DRY RUN' if dry_run else 'EXECUTING DELETIONS'}")
    if force_empty:
        print(f"   ⚠️  FORCE MODE: Will delete effectively empty folders (only system files)")
    
    empty_folders = []
    folders_with_moved_files = []
    
    # Find all empty directories
    for root, dirs, files in os.walk(root_path, topdown=False):
        # Skip hidden/system folders
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        
        # Check if directory is empty (only .DS_Store or other system files)
        try:
            items = os.listdir(root)
            # Filter out system files
            real_items = [item for item in items if not item.startswith('.')]
            if len(real_items) == 0:
                empty_folders.append(root)
        except:
            pass
    
    print(f"\n📊 Found {len(empty_folders)} empty folders")
    
    if not empty_folders:
        print("   ✅ No empty folders found")
        return
    
    print(f"\n{'='*80}")
    print("📋 ANALYZING EMPTY FOLDERS:")
    print(f"{'='*80}")
    
    safe_to_delete = []
    needs_review = []
    
    for folder in sorted(empty_folders):
        print(f"\n📁 {folder}")
        
        # Check if files were moved from this folder
        moved_files = check_files_in_folder(folder)
        
        if moved_files:
            print(f"   ✅ Files were moved from this folder ({len(moved_files)} files):")
            for doc in moved_files[:5]:
                print(f"      - {doc.get('file_name')} → {doc.get('current_path', 'Unknown')[:80]}...")
            if len(moved_files) > 5:
                print(f"      ... and {len(moved_files) - 5} more")
            
            safe_to_delete.append({
                'folder': folder,
                'moved_files': len(moved_files),
                'files': moved_files
            })
        else:
            print(f"   ⚠️  No database records found for this folder")
            print(f"      This could mean:")
            print(f"      - Files were never processed")
            print(f"      - Files were deleted manually")
            print(f"      - Folder was created but never used")
            
            needs_review.append({
                'folder': folder,
                'reason': 'No database records'
            })
    
    print(f"\n{'='*80}")
    print("📊 SUMMARY:")
    print(f"{'='*80}")
    print(f"  Total empty folders: {len(empty_folders)}")
    print(f"  Safe to delete (files moved): {len(safe_to_delete)}")
    print(f"  Needs review (no records): {len(needs_review)}")
    
    if safe_to_delete:
        print(f"\n✅ FOLDERS SAFE TO DELETE:")
        for item in safe_to_delete:
            print(f"   - {item['folder']}")
            print(f"     ({item['moved_files']} files were moved)")
    
    if needs_review:
        print(f"\n⚠️  FOLDERS NEEDING REVIEW:")
        for item in needs_review:
            print(f"   - {item['folder']}")
            print(f"     Reason: {item['reason']}")
            # Check if it only has .DS_Store
            try:
                items = os.listdir(item['folder'])
                real_items = [i for i in items if not i.startswith('.')]
                if len(real_items) == 0 and '.DS_Store' in items:
                    print(f"     Note: Only contains .DS_Store (effectively empty)")
            except:
                pass
    
    # Add effectively empty folders if force mode
    if force_empty:
        for item in needs_review:
            folder = item['folder']
            try:
                items = os.listdir(folder)
                real_items = [i for i in items if not i.startswith('.')]
                if len(real_items) == 0:
                    safe_to_delete.append({
                        'folder': folder,
                        'moved_files': 0,
                        'reason': 'Effectively empty (only system files)'
                    })
            except:
                pass
    
    # Execute deletions
    if not dry_run and safe_to_delete:
        print(f"\n{'='*80}")
        print("🗑️  DELETING EMPTY FOLDERS:")
        print(f"{'='*80}")
        
        deleted = 0
        errors = 0
        
        for item in safe_to_delete:
            folder = item['folder']
            try:
                # Remove .DS_Store and other system files if present
                for sys_file in ['.DS_Store', '.localized', '.Trash']:
                    sys_path = os.path.join(folder, sys_file)
                    if os.path.exists(sys_path):
                        os.remove(sys_path)
                
                os.rmdir(folder)
                print(f"   ✅ Deleted: {folder}")
                if item.get('reason'):
                    print(f"      Reason: {item['reason']}")
                deleted += 1
            except OSError as e:
                print(f"   ❌ Error deleting {folder}: {e}")
                errors += 1
        
        print(f"\n{'='*80}")
        print(f"✅ CLEANUP COMPLETE")
        print(f"{'='*80}")
        print(f"  Deleted: {deleted}")
        print(f"  Errors: {errors}")
        print(f"  Needs review: {len(needs_review)}")
    elif dry_run:
        print(f"\n{'='*80}")
        print("💡 DRY RUN COMPLETE")
        print(f"{'='*80}")
        if safe_to_delete:
            print(f"  To delete folders with moved files, run: python3 {sys.argv[0]} --execute")
        if needs_review:
            print(f"\n  ⚠️  {len(needs_review)} folders have no database records")
            print(f"  To delete effectively empty folders (only system files), run:")
            print(f"     python3 {sys.argv[0]} --execute --force-empty")

def main():
    dry_run = '--execute' not in sys.argv
    force_empty = '--force-empty' in sys.argv
    
    # Default to VA Docs and Apps, but allow custom path
    if len(sys.argv) > 1 and not sys.argv[-1].startswith('--'):
        root_path = sys.argv[-1]
    else:
        root_path = "/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs/Personal Bin/VA Docs and Apps"
    
    find_empty_folders(root_path, dry_run=dry_run, force_empty=force_empty)

if __name__ == "__main__":
    main()
