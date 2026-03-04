#!/usr/bin/env python3
"""
Smart Resume Consolidation:
- MY resumes → directly in Employment/Resumes/ (no nested folders)
- OTHER people's resumes → Employment/Resumes/Others/
- Flatten nested structures, don't create Resume/Resume duplicates
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

icloud_base = "/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs"

SKIP_PATTERNS = [
    'node_modules', '.git', '__pycache__', '.xcodeproj', '.xcworkspace',
    'build/', 'dist/', 'lib/', 'src/', 'test/', 'tests/',
    'ProjectGatita', 'XcodeProjects', 'PhoneGapLib'
]

# Names that indicate MY resumes
MY_RESUME_INDICATORS = [
    'michael', 'mike', 'mvalderrama', 'valderrama', 'm v', 'mv_',
    'mvalderrama', 'm_valderrama'
]

# Names that indicate OTHER people's resumes
OTHER_PEOPLE_INDICATORS = [
    'andres', 'katerina', 'dave dressler', 'george teron',
    'others', 'other', 'candidate', 'applicant'
]

def is_my_resume(file_or_folder_name):
    """Check if this is MY resume."""
    name_lower = file_or_folder_name.lower()
    return any(indicator in name_lower for indicator in MY_RESUME_INDICATORS)

def is_other_person_resume(file_or_folder_name):
    """Check if this is someone else's resume."""
    name_lower = file_or_folder_name.lower()
    return any(indicator in name_lower for indicator in OTHER_PEOPLE_INDICATORS)

def find_all_resume_items():
    """Find all resume folders and files."""
    print("="*80)
    print("🔍 FINDING ALL RESUME ITEMS")
    print("="*80)
    
    resume_folders = []
    resume_files = []
    
    for root, dirs, files in os.walk(icloud_base):
        dirs[:] = [d for d in dirs if not any(pattern in d for pattern in SKIP_PATTERNS)]
        if any(pattern in root for pattern in SKIP_PATTERNS):
            continue
        
        # Check folders
        for d in dirs:
            if 'resume' in d.lower() or 'cv' in d.lower():
                folder_path = os.path.join(root, d)
                relative = os.path.relpath(folder_path, icloud_base)
                
                # Skip if already in target location
                if 'Employment/Resumes' in relative:
                    continue
                
                resume_folders.append({
                    'name': d,
                    'path': folder_path,
                    'relative': relative
                })
        
        # Check files
        for f in files:
            if f.startswith('.'):
                continue
            if 'resume' in f.lower() or 'cv' in f.lower():
                file_path = os.path.join(root, f)
                relative = os.path.relpath(file_path, icloud_base)
                
                # Skip if already in target location
                if 'Employment/Resumes' in relative:
                    continue
                
                resume_files.append({
                    'name': f,
                    'path': file_path,
                    'relative': relative
                })
    
    print(f"\n📊 Found:")
    print(f"   Resume folders: {len(resume_folders)}")
    print(f"   Resume files: {len(resume_files)}")
    
    return resume_folders, resume_files

def consolidate_resumes(resume_folders, resume_files, dry_run=True):
    """Consolidate resumes with smart flattening."""
    print(f"\n{'='*80}")
    if dry_run:
        print("📦 CONSOLIDATION PLAN (DRY RUN)")
    else:
        print("📦 CONSOLIDATING RESUMES")
    print(f"{'='*80}")
    
    # Target locations
    my_resumes_dir = os.path.join(icloud_base, "Employment", "Resumes")
    others_resumes_dir = os.path.join(icloud_base, "Employment", "Resumes", "Others")
    
    print(f"\n🎯 Target locations:")
    print(f"   MY resumes: {os.path.relpath(my_resumes_dir, icloud_base)}")
    print(f"   OTHER people's resumes: {os.path.relpath(others_resumes_dir, icloud_base)}")
    
    if not dry_run:
        os.makedirs(my_resumes_dir, exist_ok=True)
        os.makedirs(others_resumes_dir, exist_ok=True)
    
    moved_folders = 0
    moved_files = 0
    flattened_files = 0
    errors = 0
    
    # Process folders - FLATTEN them (extract files, don't move folder as-is)
    print(f"\n📁 Processing {len(resume_folders)} folders (will FLATTEN - extract files):")
    for folder in resume_folders:
        source_path = folder['path']
        folder_name = folder['name']
        
        # Determine if MY resume or OTHER person's
        is_mine = is_my_resume(folder_name)
        is_other = is_other_person_resume(folder_name)
        
        # Extract all files from folder
        files_in_folder = []
        for root, dirs, files in os.walk(source_path):
            for f in files:
                if f.startswith('.'):
                    continue
                file_path = os.path.join(root, f)
                # Determine by FILE name, not folder name
                file_is_mine = is_my_resume(f)
                file_is_other = is_other_person_resume(f)
                
                # Use folder as hint only if file name doesn't clearly indicate
                if not (file_is_mine or file_is_other):
                    file_is_mine = is_mine  # Use folder hint
                    file_is_other = is_other
                
                files_in_folder.append({
                    'name': f,
                    'path': file_path,
                    'is_mine': file_is_mine,
                    'is_other': file_is_other
                })
        
        if dry_run:
            print(f"   📁 {folder_name}")
            print(f"      Files inside: {len(files_in_folder)}")
            # Show where each file will go
            my_files = [f for f in files_in_folder if f['is_mine']]
            other_files = [f for f in files_in_folder if f['is_other']]
            unknown_files = [f for f in files_in_folder if not (f['is_mine'] or f['is_other'])]
            
            if my_files:
                print(f"      → {len(my_files)} MY resume files → Employment/Resumes/")
                for f in my_files[:3]:
                    print(f"         - {f['name']}")
            if other_files:
                print(f"      → {len(other_files)} OTHER people's resumes → Employment/Resumes/Others/")
                for f in other_files[:3]:
                    print(f"         - {f['name']}")
            if unknown_files:
                print(f"      → {len(unknown_files)} UNKNOWN → Employment/Resumes/Others/")
                for f in unknown_files[:3]:
                    print(f"         - {f['name']}")
            if len(files_in_folder) > 6:
                print(f"      ... and {len(files_in_folder) - 6} more files")
        else:
            # Extract files from folder - categorize by FILE name, not folder
            for file_info in files_in_folder:
                source_file = file_info['path']
                file_name = file_info['name']
                
                # Determine target based on FILE name (not folder name)
                if file_info['is_mine']:
                    final_target = my_resumes_dir
                elif file_info['is_other']:
                    final_target = others_resumes_dir
                else:
                    # Unknown - default to Others (safer than assuming it's mine)
                    final_target = others_resumes_dir
                
                # Create unique target name
                target_file = os.path.join(final_target, file_name)
                counter = 1
                while os.path.exists(target_file):
                    name, ext = os.path.splitext(file_name)
                    target_file = os.path.join(final_target, f"{name}_{counter}{ext}")
                    counter += 1
                
                try:
                    shutil.move(source_file, target_file)
                    flattened_files += 1
                    
                    # Update database
                    try:
                        result = supabase.table('documents')\
                            .select('id')\
                            .eq('current_path', source_file)\
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
                                    'location_path': source_file,
                                    'location_type': 'previous',
                                    'discovered_at': datetime.now().isoformat(),
                                    'verified_at': datetime.now().isoformat(),
                                    'is_accessible': False,
                                    'notes': f'Consolidated to Employment/Resumes/'
                                })\
                                .execute()
                    except:
                        pass
                except Exception as e:
                    print(f"      ❌ Error moving {file_name}: {e}")
                    errors += 1
            
            # After extracting files, try to delete empty folder
            try:
                if not os.listdir(source_path):  # Empty
                    os.rmdir(source_path)
                    moved_folders += 1
            except:
                pass  # Folder not empty or can't delete
    
    # Process standalone files
    print(f"\n📄 Processing {len(resume_files)} standalone files:")
    for file in resume_files:
        source_path = file['path']
        file_name = file['name']
        
        # Determine if MY resume or OTHER person's
        is_mine = is_my_resume(file_name)
        is_other = is_other_person_resume(file_name)
        
        target_dir = my_resumes_dir if is_mine else others_resumes_dir
        
        # Create unique target name
        target_file = os.path.join(target_dir, file_name)
        counter = 1
        while os.path.exists(target_file):
            name, ext = os.path.splitext(file_name)
            target_file = os.path.join(target_dir, f"{name}_{counter}{ext}")
            counter += 1
        
        if dry_run:
            print(f"   → {file_name}")
            print(f"      Type: {'MY resume' if is_mine else 'OTHER person' if is_other else 'UNKNOWN'}")
            print(f"      From: {file['relative']}")
            print(f"      To:   {os.path.relpath(target_file, icloud_base)}")
        else:
            try:
                shutil.move(source_path, target_file)
                
                # Update database
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
                    pass
                
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
    print(f"  Folders to process: {len(resume_folders)}")
    print(f"  Standalone files: {len(resume_files)}")
    if not dry_run:
        print(f"  Files extracted from folders: {flattened_files}")
        print(f"  Standalone files moved: {moved_files}")
        print(f"  Empty folders removed: {moved_folders}")
        print(f"  Errors: {errors}")
    print(f"\n  Structure:")
    print(f"    Employment/Resumes/ (MY resumes - files directly here)")
    print(f"    Employment/Resumes/Others/ (OTHER people's resumes)")
    
    if dry_run:
        print(f"\n💡 To execute consolidation, run:")
        print(f"   python3 {sys.argv[0]} --execute")

def main():
    dry_run = '--execute' not in sys.argv
    
    resume_folders, resume_files = find_all_resume_items()
    
    if not resume_folders and not resume_files:
        print("\n✅ No resume folders or files found")
        return
    
    consolidate_resumes(resume_folders, resume_files, dry_run=dry_run)

if __name__ == "__main__":
    main()
