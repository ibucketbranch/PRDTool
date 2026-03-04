#!/usr/bin/env python3
"""
Move processed Google Drive files to iCloud based on AI-suggested folder structures.
Only moves files that have been processed and have suggested folder structures.
"""
import os
import shutil
import sys
from pathlib import Path
from supabase import create_client
from datetime import datetime

supabase_url = "http://127.0.0.1:54421"
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(supabase_url, supabase_key)

google_drive_path = "/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive"
icloud_base = "/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs/Documents"

def get_files_to_move():
    """Get all processed Google Drive files with suggested folder structures."""
    print("="*80)
    print("🔍 FINDING FILES TO MOVE FROM GOOGLE DRIVE TO iCLOUD")
    print("="*80)
    
    print(f"\n📊 Loading processed files from Google Drive...")
    
    files_to_move = []
    
    try:
        # Get all documents currently in Google Drive
        result = supabase.table('documents')\
            .select('id,file_name,current_path,suggested_folder_structure,context_bin,ai_category')\
            .ilike('current_path', f'%{google_drive_path}%')\
            .limit(50000)\
            .execute()
        
        if result.data:
            for doc in result.data:
                current_path = doc.get('current_path', '')
                suggested = doc.get('suggested_folder_structure', '')
                context_bin = doc.get('context_bin')
                ai_category = doc.get('ai_category')
                
                # Only move if file exists and we have a suggested structure or context bin
                if os.path.exists(current_path):
                    if suggested or context_bin:
                        files_to_move.append({
                            'doc_id': doc['id'],
                            'file_name': doc.get('file_name'),
                            'current_path': current_path,
                            'suggested_folder_structure': suggested,
                            'context_bin': context_bin,
                            'ai_category': ai_category
                        })
        
        print(f"   Found {len(files_to_move)} files ready to move")
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
        import traceback
        traceback.print_exc()
    
    return files_to_move

def determine_target_path(file_info):
    """Determine target path in iCloud based on suggested structure or context bin."""
    suggested = file_info.get('suggested_folder_structure', '')
    context_bin = file_info.get('context_bin')
    ai_category = file_info.get('ai_category', '')
    file_name = file_info.get('file_name', '')
    
    # Use suggested folder structure if available
    if suggested:
        # Clean up the suggested path (remove "Bin" suffix if it's just the bin name)
        if suggested.startswith(context_bin) if context_bin else False:
            target_path = os.path.join(icloud_base, suggested)
        else:
            # If suggested path doesn't start with context_bin, prepend it
            if context_bin:
                target_path = os.path.join(icloud_base, context_bin, suggested.replace(f"{context_bin}/", ""))
            else:
                target_path = os.path.join(icloud_base, suggested)
    elif context_bin:
        # Use context bin + category
        category_folder = ai_category.replace('_', ' ').title() if ai_category else 'Other'
        target_path = os.path.join(icloud_base, context_bin, category_folder)
    else:
        # Fallback: use category
        category_folder = ai_category.replace('_', ' ').title() if ai_category else 'Other'
        target_path = os.path.join(icloud_base, 'General', category_folder)
    
    # Ensure target is a directory (add filename)
    target_dir = target_path
    target_file = os.path.join(target_dir, file_name)
    
    return target_dir, target_file

def unique_target_path(target_dir, filename):
    """Generate unique target path if file exists."""
    target_path = Path(target_dir) / filename
    
    if not target_path.exists():
        return target_path
    
    # File exists, append counter
    stem = Path(filename).stem
    ext = Path(filename).suffix
    counter = 1
    
    while target_path.exists():
        new_filename = f"{stem}_{counter}{ext}"
        target_path = Path(target_dir) / new_filename
        counter += 1
    
    return target_path

def move_files(files_to_move, dry_run=True):
    """Move files from Google Drive to iCloud."""
    print(f"\n{'='*80}")
    if dry_run:
        print("📦 MOVE PLAN (DRY RUN)")
    else:
        print("📦 MOVING FILES")
    print(f"{'='*80}")
    
    moved = 0
    errors = 0
    skipped = 0
    
    # Group by target directory
    by_target = {}
    for file_info in files_to_move:
        target_dir, target_file = determine_target_path(file_info)
        if target_dir not in by_target:
            by_target[target_dir] = []
        by_target[target_dir].append((file_info, target_file))
    
    print(f"\n📁 Files will be organized into {len(by_target)} target directories")
    
    for target_dir, files in sorted(by_target.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"\n📁 {target_dir}: {len(files)} files")
        
        if not dry_run:
            os.makedirs(target_dir, exist_ok=True)
        
        for file_info, target_file in files[:10]:  # Show first 10
            source_path = file_info['current_path']
            filename = file_info['file_name']
            
            # Generate unique target
            target_path = unique_target_path(Path(target_dir), filename)
            
            if dry_run:
                print(f"   → {filename}")
                print(f"      From: {source_path[:80]}...")
                print(f"      To:   {target_path}")
            else:
                try:
                    # Move file
                    shutil.move(str(source_path), str(target_path))
                    
                    # Update database
                    supabase.table('documents')\
                        .update({'current_path': str(target_path)})\
                        .eq('id', file_info['doc_id'])\
                        .execute()
                    
                    # Record old path
                    supabase.table('document_locations')\
                        .insert({
                            'document_id': file_info['doc_id'],
                            'location_path': source_path,
                            'location_type': 'previous',
                            'discovered_at': datetime.now().isoformat(),
                            'verified_at': datetime.now().isoformat(),
                            'is_accessible': False,
                            'notes': f'Moved from Google Drive to iCloud: {target_dir}'
                        })\
                        .execute()
                    
                    print(f"   ✅ {filename}")
                    moved += 1
                except Exception as e:
                    print(f"   ❌ {filename}: {e}")
                    errors += 1
        
        if len(files) > 10:
            print(f"   ... and {len(files) - 10} more files")
    
    print(f"\n{'='*80}")
    if dry_run:
        print("📊 MOVE PLAN SUMMARY")
    else:
        print("✅ MOVE COMPLETE")
    print(f"{'='*80}")
    print(f"  Total files: {len(files_to_move)}")
    if not dry_run:
        print(f"  Moved: {moved}")
        print(f"  Errors: {errors}")
    print(f"  Target directories: {len(by_target)}")
    
    if dry_run:
        print(f"\n💡 To execute moves, run:")
        print(f"   python3 {sys.argv[0]} --execute")

def main():
    dry_run = '--execute' not in sys.argv
    
    files_to_move = get_files_to_move()
    
    if not files_to_move:
        print("\n✅ No files to move (all already processed and moved, or no suggested structures)")
        return
    
    move_files(files_to_move, dry_run=dry_run)

if __name__ == "__main__":
    main()
