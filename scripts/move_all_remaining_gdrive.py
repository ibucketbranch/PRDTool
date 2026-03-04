#!/usr/bin/env python3
"""
Move ALL remaining Google Drive files to iCloud.
For uncategorized files, create sensible default folders.
"""
import os
import shutil
import sys
from pathlib import Path
from datetime import datetime
from supabase import create_client

supabase_url = "http://127.0.0.1:54421"
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(supabase_url, supabase_key)

google_drive_path = "/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive"
icloud_base = "/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs/Documents"

IMPORTANT_EXTENSIONS = {'.pdf', '.docx', '.xlsx', '.pptx', '.txt', '.rtf'}

def get_all_remaining_files():
    """Get all remaining files in Google Drive."""
    print("="*80)
    print("🔍 FINDING ALL REMAINING GOOGLE DRIVE FILES")
    print("="*80)
    
    files_to_move = []
    
    # Get files from database that are still in Google Drive
    try:
        result = supabase.table('documents')\
            .select('id,file_name,current_path,suggested_folder_structure,context_bin,ai_category,file_type')\
            .ilike('current_path', f'%{google_drive_path}%')\
            .limit(50000)\
            .execute()
        
        if result.data:
            for doc in result.data:
                current_path = doc.get('current_path', '')
                if os.path.exists(current_path):
                    files_to_move.append({
                        'doc_id': doc['id'],
                        'file_name': doc.get('file_name'),
                        'current_path': current_path,
                        'suggested_folder_structure': doc.get('suggested_folder_structure'),
                        'context_bin': doc.get('context_bin'),
                        'ai_category': doc.get('ai_category'),
                        'file_type': doc.get('file_type', 'unknown')
                    })
        
        print(f"   Found {len(files_to_move)} files in database")
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
    
    # Also find files in Google Drive that aren't in database
    print(f"\n🔍 Scanning Google Drive for unprocessed files...")
    unprocessed = []
    
    for root, dirs, files in os.walk(google_drive_path):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        
        for file in files:
            if file.startswith('.'):
                continue
            
            ext = os.path.splitext(file)[1].lower()
            if ext in IMPORTANT_EXTENSIONS:
                file_path = os.path.join(root, file)
                
                # Check if already in our list
                if not any(f['current_path'] == file_path for f in files_to_move):
                    unprocessed.append({
                        'doc_id': None,
                        'file_name': file,
                        'current_path': file_path,
                        'suggested_folder_structure': None,
                        'context_bin': None,
                        'ai_category': None,
                        'file_type': ext.lstrip('.')
                    })
    
    print(f"   Found {len(unprocessed)} unprocessed files")
    
    all_files = files_to_move + unprocessed
    print(f"\n📊 Total files to move: {len(all_files)}")
    
    return all_files

def determine_target_path(file_info):
    """Determine target path in iCloud."""
    suggested = file_info.get('suggested_folder_structure', '')
    context_bin = file_info.get('context_bin')
    ai_category = file_info.get('ai_category', '')
    file_type = file_info.get('file_type', 'unknown')
    file_name = file_info.get('file_name', '')
    
    # Use suggested folder structure if available
    if suggested:
        if context_bin and not suggested.startswith(context_bin):
            target_path = os.path.join(icloud_base, context_bin, suggested.replace(f"{context_bin}/", ""))
        else:
            target_path = os.path.join(icloud_base, suggested)
        return os.path.dirname(target_path), os.path.join(target_path, file_name)
    
    # Use context bin + category if available
    if context_bin:
        category_folder = ai_category.replace('_', ' ').title() if ai_category else 'Uncategorized'
        target_dir = os.path.join(icloud_base, context_bin, category_folder)
        return target_dir, os.path.join(target_dir, file_name)
    
    # Default: Create "From Google Drive" folder organized by file type and date
    # Extract year from file if possible, or use "Unknown Date"
    year = "Unknown Date"
    try:
        # Try to extract year from filename or path
        path_parts = file_info.get('current_path', '').split('/')
        for part in path_parts:
            if len(part) == 4 and part.isdigit() and 1990 <= int(part) <= 2030:
                year = part
                break
    except:
        pass
    
    # Organize by file type and year
    type_folder = file_type.upper() if file_type != 'unknown' else 'Other'
    target_dir = os.path.join(icloud_base, "From Google Drive", type_folder, year)
    return target_dir, os.path.join(target_dir, file_name)

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

def move_files(files_to_move, dry_run=False):
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
        
        for file_info, target_file in files:
            source_path = file_info['current_path']
            filename = file_info['file_name']
            
            if not os.path.exists(source_path):
                print(f"   ⚠️  {filename} - Source file not found")
                errors += 1
                continue
            
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
                    
                    # Update database if file is in database
                    if file_info['doc_id']:
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
        print(f"  Skipped: {skipped}")
    print(f"  Target directories: {len(by_target)}")
    
    if dry_run:
        print(f"\n💡 To execute moves, run:")
        print(f"   python3 {sys.argv[0]} --execute")

def main():
    dry_run = '--execute' not in sys.argv
    auto_yes = '--yes' in sys.argv or '--execute' in sys.argv
    
    if not dry_run and not auto_yes:
        print("="*80)
        print("⚠️  WARNING: This will MOVE all remaining files from Google Drive to iCloud")
        print("="*80)
        print("   Uncategorized files will go to: iCloud/Documents/From Google Drive/")
        print()
        try:
            response = input("   Continue? (yes/no): ").strip().lower()
            if response != 'yes':
                print("   Cancelled.")
                return
        except EOFError:
            print("   ⚠️  Non-interactive mode, proceeding automatically...")
        print()
    
    files_to_move = get_all_remaining_files()
    
    if not files_to_move:
        print("\n✅ No files to move")
        return
    
    move_files(files_to_move, dry_run=dry_run)

if __name__ == "__main__":
    main()
