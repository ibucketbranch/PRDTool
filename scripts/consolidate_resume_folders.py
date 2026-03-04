#!/usr/bin/env python3
"""
Consolidate Resume-related folders and files in iCloud.
Finds all folders/files with "resume" in the name and consolidates them.
"""
import os
import shutil
import sys
from pathlib import Path
from collections import defaultdict
from supabase import create_client
from datetime import datetime

supabase_url = "http://127.0.0.1:54421"
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(supabase_url, supabase_key)

icloud_base = "/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs"

# Skip these paths (code projects, system files)
SKIP_PATTERNS = [
    'node_modules', '.git', '__pycache__', '.xcodeproj', '.xcworkspace',
    'build/', 'dist/', 'lib/', 'src/', 'test/', 'tests/',
    'ProjectGatita', 'XcodeProjects', 'PhoneGapLib'
]

def find_resume_items():
    """Find all folders and files with 'resume' in the name."""
    print("="*80)
    print("🔍 FINDING RESUME-RELATED FOLDERS AND FILES")
    print("="*80)
    
    resume_folders = []
    resume_files = []
    
    print(f"\n📁 Scanning: {icloud_base}")
    
    for root, dirs, files in os.walk(icloud_base):
        # Skip code project folders
        dirs[:] = [d for d in dirs if not any(pattern in d for pattern in SKIP_PATTERNS)]
        if any(pattern in root for pattern in SKIP_PATTERNS):
            continue
        
        # Check folders
        for d in dirs:
            if 'resume' in d.lower():
                folder_path = os.path.join(root, d)
                relative = os.path.relpath(folder_path, icloud_base)
                resume_folders.append({
                    'name': d,
                    'path': folder_path,
                    'relative': relative
                })
        
        # Check files
        for f in files:
            if f.startswith('.'):
                continue
            if 'resume' in f.lower():
                file_path = os.path.join(root, f)
                relative = os.path.relpath(file_path, icloud_base)
                resume_files.append({
                    'name': f,
                    'path': file_path,
                    'relative': relative
                })
    
    print(f"\n📊 Found:")
    print(f"   Resume folders: {len(resume_folders)}")
    print(f"   Resume files: {len(resume_files)}")
    
    # Show what we found
    if resume_folders:
        print(f"\n📁 Resume folders found:")
        for folder in resume_folders[:20]:
            print(f"   - {folder['relative']}")
        if len(resume_folders) > 20:
            print(f"   ... and {len(resume_folders) - 20} more")
    
    if resume_files:
        print(f"\n📄 Resume files found:")
        for file in resume_files[:20]:
            print(f"   - {file['relative']}")
        if len(resume_files) > 20:
            print(f"   ... and {len(resume_files) - 20} more")
    
    return resume_folders, resume_files

def determine_target_location():
    """Determine target location for consolidated resumes."""
    # Check if Employment/Resumes exists
    target_base = os.path.join(icloud_base, "Employment", "Resumes")
    
    # If not, check for Work Bin/Employment/Resumes
    work_bin_path = os.path.join(icloud_base, "Work Bin", "Employment", "Resumes")
    if os.path.exists(work_bin_path):
        return work_bin_path
    
    # Or create Employment/Resumes
    return target_base

def consolidate_resumes(resume_folders, resume_files, dry_run=True):
    """Consolidate resume folders and files."""
    print(f"\n{'='*80}")
    if dry_run:
        print("📦 CONSOLIDATION PLAN (DRY RUN)")
    else:
        print("📦 CONSOLIDATING RESUMES")
    print(f"{'='*80}")
    
    target_dir = determine_target_location()
    print(f"\n🎯 Target location: {target_dir}")
    
    if not dry_run:
        os.makedirs(target_dir, exist_ok=True)
    
    moved_folders = 0
    moved_files = 0
    errors = 0
    
    # Consolidate folders
    print(f"\n📁 Consolidating {len(resume_folders)} folders...")
    for folder in resume_folders:
        source_path = folder['path']
        folder_name = folder['name']
        
        # Skip if already in target location
        if target_dir in source_path:
            print(f"   ⊘ {folder_name} (already in target)")
            continue
        
        # Create unique target name
        target_folder = os.path.join(target_dir, folder_name)
        counter = 1
        while os.path.exists(target_folder):
            name, _ = os.path.splitext(folder_name)
            target_folder = os.path.join(target_dir, f"{name}_{counter}")
            counter += 1
        
        if dry_run:
            print(f"   → {folder_name}")
            print(f"      From: {folder['relative']}")
            print(f"      To:   {os.path.relpath(target_folder, icloud_base)}")
        else:
            try:
                shutil.move(source_path, target_folder)
                print(f"   ✅ {folder_name}")
                moved_folders += 1
            except Exception as e:
                print(f"   ❌ {folder_name}: {e}")
                errors += 1
    
    # Consolidate files
    print(f"\n📄 Consolidating {len(resume_files)} files...")
    for file in resume_files:
        source_path = file['path']
        file_name = file['name']
        
        # Skip if already in target location
        if target_dir in source_path:
            print(f"   ⊘ {file_name} (already in target)")
            continue
        
        # Create unique target name
        target_file = os.path.join(target_dir, file_name)
        counter = 1
        while os.path.exists(target_file):
            name, ext = os.path.splitext(file_name)
            target_file = os.path.join(target_dir, f"{name}_{counter}{ext}")
            counter += 1
        
        if dry_run:
            print(f"   → {file_name}")
            print(f"      From: {file['relative']}")
            print(f"      To:   {os.path.relpath(target_file, icloud_base)}")
        else:
            try:
                shutil.move(source_path, target_file)
                
                # Update database if file is tracked
                try:
                    result = supabase.table('documents')\
                        .select('id')\
                        .eq('current_path', source_path)\
                        .limit(1)\
                        .execute()
                    
                    if result.data:
                        doc_id = result.data[0]['id']
                        supabase.table('documents')\
                            .update({'current_path': target_file})\
                            .eq('id', doc_id)\
                            .execute()
                        
                        supabase.table('document_locations')\
                            .insert({
                                'document_id': doc_id,
                                'location_path': source_path,
                                'location_type': 'previous',
                                'discovered_at': datetime.now().isoformat(),
                                'verified_at': datetime.now().isoformat(),
                                'is_accessible': False,
                                'notes': f'Consolidated to Employment/Resumes/'
                            })\
                            .execute()
                except:
                    pass  # File might not be in database
                
                print(f"   ✅ {file_name}")
                moved_files += 1
            except Exception as e:
                print(f"   ❌ {file_name}: {e}")
                errors += 1
    
    print(f"\n{'='*80}")
    if dry_run:
        print("📊 CONSOLIDATION PLAN SUMMARY")
    else:
        print("✅ CONSOLIDATION COMPLETE")
    print(f"{'='*80}")
    print(f"  Folders to consolidate: {len(resume_folders)}")
    print(f"  Files to consolidate: {len(resume_files)}")
    if not dry_run:
        print(f"  Folders moved: {moved_folders}")
        print(f"  Files moved: {moved_files}")
        print(f"  Errors: {errors}")
    print(f"  Target: {os.path.relpath(target_dir, icloud_base)}")
    
    if dry_run:
        print(f"\n💡 To execute consolidation, run:")
        print(f"   python3 {sys.argv[0]} --execute")

def main():
    dry_run = '--execute' not in sys.argv
    
    resume_folders, resume_files = find_resume_items()
    
    if not resume_folders and not resume_files:
        print("\n✅ No resume folders or files found")
        return
    
    consolidate_resumes(resume_folders, resume_files, dry_run=dry_run)

if __name__ == "__main__":
    main()
