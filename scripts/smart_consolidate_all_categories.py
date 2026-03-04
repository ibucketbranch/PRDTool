#!/usr/bin/env python3
"""
Smart Consolidation for ALL Categories:
- Flattens nested structures (no Resume/Resume/, Tax/Tax/, etc.)
- MY files → directly in main category folder
- OTHER people's files → in subfolder (Others/)
- Applies to all categories: Resume, Tax, Contract, Invoice, Statement, Insurance, Medical, etc.
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

# Code project indicators - if a folder contains these, it's a code project and should be skipped entirely
CODE_PROJECT_INDICATORS = [
    'package.json', 'requirements.txt', 'setup.py', 'pom.xml', 'build.gradle',
    'Cargo.toml', 'go.mod', 'composer.json', 'Gemfile', 'Makefile',
    '.gitignore', '.git', '.vscode', '.idea', 'tsconfig.json', 'webpack.config.js',
    'Dockerfile', '.dockerignore', 'docker-compose.yml', 'yarn.lock', 'package-lock.json'
]

# VA document patterns - these should be excluded from category consolidation
VA_PATTERNS = [
    'VBA-', 'VA-20-', 'VA-21-', 'DBQ', 'Supplemental Claim',
    'Veterans Affairs', 'VA Docs', 'VA Claims', 'VA Benefits',
    'VA Form', 'VA Blue Button', 'CalVet', 'Calvet', 'DVS40'
]

# Names/keywords that identify MY documents
MY_NAMES = [
    'michael', 'mike', 'mvalderrama', 'valderrama', 'm v', 'mv_',
    'mvalderrama', 'm_valderrama'
]

# Names/keywords that identify OTHER people's documents
OTHER_PEOPLE_NAMES = [
    'andres', 'katerina', 'dave dressler', 'george teron',
    'others', 'other', 'candidate', 'applicant'
]

# Categories to consolidate with their keywords and target paths
CONSOLIDATION_CATEGORIES = {
    'Resume': {
        'keywords': ['resume', 'cv', 'curriculum'],
        'target': 'Employment/Resumes',
        'description': 'All resume-related folders and files'
    },
    'Tax': {
        'keywords': ['tax', 'turbotax', 'w2', '1099', 'irs', 'tax return'],
        'target': 'Finances Bin/Taxes',
        'description': 'All tax-related documents'
    },
    'Contract': {
        'keywords': ['contract', 'agreement', 'sow', 'mou', 'nda'],
        'target': 'Legal Bin/Contracts',
        'description': 'All contracts and agreements'
    },
    'Invoice': {
        'keywords': ['invoice', 'bill', 'receipt'],
        'target': 'Finances Bin/Invoices',
        'description': 'All invoices and bills'
    },
    'Statement': {
        'keywords': ['statement', 'estmt', 'bank statement', 'account statement'],
        'target': 'Finances Bin/Statements',
        'description': 'All bank and financial statements'
    },
    'Insurance': {
        'keywords': ['insurance', 'policy', 'coverage', 'ins policy'],
        'target': 'Personal Bin/Insurance',
        'description': 'All insurance documents'
    },
    'Medical': {
        'keywords': ['medical', 'health', 'doctor', 'hospital', 'prescription', 'medical record'],
        'target': 'Personal Bin/Medical',
        'description': 'All medical records and documents'
    },
    'Vehicle': {
        'keywords': ['vehicle', 'car', 'registration', 'dmv', 'auto', 'tesla'],
        'target': 'Personal Bin/Vehicles',
        'description': 'All vehicle-related documents'
    }
}

def is_my_document(file_or_folder_name):
    """Check if this is MY document."""
    name_lower = file_or_folder_name.lower()
    return any(name in name_lower for name in MY_NAMES)

def is_other_person_document(file_or_folder_name):
    """Check if this is someone else's document."""
    name_lower = file_or_folder_name.lower()
    return any(name in name_lower for name in OTHER_PEOPLE_NAMES)

def is_code_project(path):
    """Check if a path is a code project by looking for project indicators."""
    try:
        items = os.listdir(path)
        # Check if any code project indicators exist
        for indicator in CODE_PROJECT_INDICATORS:
            if indicator in items:
                return True
        # Check if .git directory exists
        if '.git' in items:
            return True
    except:
        pass
    return False

def is_va_document(file_or_folder_name, path=None):
    """Check if this is a VA document that should be excluded from category consolidation."""
    name_lower = (file_or_folder_name or '').lower()
    path_lower = (path or '').lower()
    
    # Check name
    if any(pattern.lower() in name_lower for pattern in VA_PATTERNS):
        return True
    
    # Check path
    if any(pattern.lower() in path_lower for pattern in VA_PATTERNS):
        return True
    
    # Check if in VA Docs folder
    if 'va docs' in path_lower or 'va docs and apps' in path_lower:
        return True
    
    return False

def find_items_for_category(category_info):
    """Find folders and files matching a category."""
    keywords = category_info['keywords']
    target = category_info['target']
    
    matching_folders = []
    matching_files = []
    
    for root, dirs, files in os.walk(icloud_base):
        # Skip code projects
        if is_code_project(root):
            dirs[:] = []  # Don't descend into code projects
            continue
        
        dirs[:] = [d for d in dirs if not any(pattern in d for pattern in SKIP_PATTERNS)]
        if any(pattern in root for pattern in SKIP_PATTERNS):
            continue
        
        # Check folders
        for d in dirs:
            d_lower = d.lower()
            if any(kw in d_lower for kw in keywords):
                folder_path = os.path.join(root, d)
                relative = os.path.relpath(folder_path, icloud_base)
                
                # Skip if already in target location
                if target in relative:
                    continue
                
                # Skip if it's a code project
                if is_code_project(folder_path):
                    continue
                
                # Skip if it's a VA document
                if is_va_document(d, folder_path):
                    continue
                
                matching_folders.append({
                    'name': d,
                    'path': folder_path,
                    'relative': relative
                })
        
        # Check files
        for f in files:
            if f.startswith('.'):
                continue
            # Skip system/library files
            if any(ext in f.lower() for ext in ['.dll', '.exe', '.sys', '.tmp', '.log']):
                continue
            # Skip cookie/cache files
            if 'cookie' in root.lower() or 'cache' in root.lower() or 'temp' in root.lower():
                continue
            
            f_lower = f.lower()
            # More precise matching: require keyword to be a word or at start/end
            matches = False
            for kw in keywords:
                # Check if keyword appears as a whole word or at start/end
                if (kw in f_lower and 
                    (f_lower.startswith(kw) or 
                     f_lower.endswith(kw) or 
                     f' {kw}' in f_lower or 
                     f'{kw} ' in f_lower or
                     f'_{kw}' in f_lower or
                     f'{kw}_' in f_lower)):
                    matches = True
                    break
            
            if matches:
                file_path = os.path.join(root, f)
                relative = os.path.relpath(file_path, icloud_base)
                
                # Skip if already in target location
                if target in relative:
                    continue
                
                # Skip if it's a VA document
                if is_va_document(f, file_path):
                    continue
                
                # Skip if parent folder is a code project
                if is_code_project(root):
                    continue
                
                matching_files.append({
                    'name': f,
                    'path': file_path,
                    'relative': relative
                })
    
    return matching_folders, matching_files

def consolidate_category(category_name, category_info, resume_folders, resume_files, dry_run=True):
    """Consolidate a category with smart flattening."""
    print(f"\n{'='*80}")
    if dry_run:
        print(f"📦 {category_name.upper()} CONSOLIDATION PLAN (DRY RUN)")
    else:
        print(f"📦 CONSOLIDATING {category_name.upper()}")
    print(f"{'='*80}")
    
    target_base = category_info['target']
    my_docs_dir = os.path.join(icloud_base, target_base)
    others_docs_dir = os.path.join(icloud_base, target_base, "Others")
    
    print(f"\n🎯 Target locations:")
    print(f"   MY documents: {target_base}")
    print(f"   OTHER people's documents: {target_base}/Others")
    
    if not dry_run:
        os.makedirs(my_docs_dir, exist_ok=True)
        os.makedirs(others_docs_dir, exist_ok=True)
    
    moved_folders = 0
    moved_files = 0
    flattened_files = 0
    errors = 0
    
    # Process folders - FLATTEN them (extract files, don't move folder as-is)
    print(f"\n📁 Processing {len(resume_folders)} folders (will FLATTEN - extract files):")
    for folder in resume_folders:
        source_path = folder['path']
        folder_name = folder['name']
        
        # Determine if MY document or OTHER person's
        is_mine = is_my_document(folder_name)
        is_other = is_other_person_document(folder_name)
        
        # Extract all files from folder
        files_in_folder = []
        for root, dirs, files in os.walk(source_path):
            for f in files:
                if f.startswith('.'):
                    continue
                file_path = os.path.join(root, f)
                # Determine by FILE name, not folder name
                file_is_mine = is_my_document(f)
                file_is_other = is_other_person_document(f)
                
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
            my_files = [f for f in files_in_folder if f['is_mine']]
            other_files = [f for f in files_in_folder if f['is_other']]
            unknown_files = [f for f in files_in_folder if not (f['is_mine'] or f['is_other'])]
            
            if files_in_folder:
                print(f"   📁 {folder_name}")
                print(f"      Files inside: {len(files_in_folder)}")
                if my_files:
                    print(f"      → {len(my_files)} MY documents → {target_base}/")
                    for f in my_files[:2]:
                        print(f"         - {f['name']}")
                if other_files:
                    print(f"      → {len(other_files)} OTHER people's → {target_base}/Others/")
                    for f in other_files[:2]:
                        print(f"         - {f['name']}")
                if unknown_files:
                    print(f"      → {len(unknown_files)} UNKNOWN → {target_base}/Others/")
                    for f in unknown_files[:2]:
                        print(f"         - {f['name']}")
        else:
            # Extract files from folder - categorize by FILE name, not folder
            for file_info in files_in_folder:
                source_file = file_info['path']
                file_name = file_info['name']
                
                # Determine target based on FILE name (not folder name)
                if file_info['is_mine']:
                    final_target = my_docs_dir
                elif file_info['is_other']:
                    final_target = others_docs_dir
                else:
                    # Unknown - default to Others (safer than assuming it's mine)
                    final_target = others_docs_dir
                
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
                                    'notes': f'Consolidated to {target_base}/'
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
        
        # Determine if MY document or OTHER person's
        is_mine = is_my_document(file_name)
        is_other = is_other_person_document(file_name)
        
        target_dir = my_docs_dir if is_mine else others_docs_dir
        
        # Create unique target name
        target_file = os.path.join(target_dir, file_name)
        counter = 1
        while os.path.exists(target_file):
            name, ext = os.path.splitext(file_name)
            target_file = os.path.join(target_dir, f"{name}_{counter}{ext}")
            counter += 1
        
        if dry_run:
            print(f"   → {file_name}")
            print(f"      Type: {'MY document' if is_mine else 'OTHER person' if is_other else 'UNKNOWN'}")
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
                                'notes': f'Consolidated to {target_base}/'
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
        print(f"📊 {category_name.upper()} CONSOLIDATION PLAN SUMMARY")
    else:
        print(f"✅ {category_name.upper()} CONSOLIDATION COMPLETE")
    print(f"{'='*80}")
    print(f"  Folders to process: {len(resume_folders)}")
    print(f"  Standalone files: {len(resume_files)}")
    if not dry_run:
        print(f"  Files extracted from folders: {flattened_files}")
        print(f"  Standalone files moved: {moved_files}")
        print(f"  Empty folders removed: {moved_folders}")
        print(f"  Errors: {errors}")
    print(f"\n  Structure:")
    print(f"    {target_base}/ (MY documents - files directly here)")
    print(f"    {target_base}/Others/ (OTHER people's documents)")
    
    return {
        'folders': len(resume_folders),
        'files': len(resume_files),
        'flattened': flattened_files if not dry_run else 0,
        'moved': moved_files if not dry_run else 0,
        'errors': errors
    }

def main():
    dry_run = '--execute' not in sys.argv
    specific_category = None
    if len(sys.argv) > 1 and sys.argv[1] not in ['--execute', '--yes']:
        specific_category = sys.argv[1]
    
    print("="*80)
    print("🔍 SMART CONSOLIDATION FOR ALL CATEGORIES")
    print("="*80)
    print("\nLogic:")
    print("  • Flattens nested structures (no Resume/Resume/, Tax/Tax/, etc.)")
    print("  • MY documents → directly in main category folder")
    print("  • OTHER people's documents → in subfolder (Others/)")
    print("  • Files categorized by FILE name, not folder name")
    print("\nExclusions:")
    print("  • Code projects (package.json, .git, etc.) - kept together, not touched")
    print("  • VA documents and claims - kept together in VA Docs and Apps")
    print()
    
    categories_to_process = [specific_category] if specific_category else list(CONSOLIDATION_CATEGORIES.keys())
    
    all_results = {}
    
    for category_name in categories_to_process:
        if category_name not in CONSOLIDATION_CATEGORIES:
            print(f"⚠️  Unknown category: {category_name}")
            continue
        
        category_info = CONSOLIDATION_CATEGORIES[category_name]
        print(f"\n{'='*80}")
        print(f"🔍 SCANNING FOR {category_name.upper()}")
        print(f"{'='*80}")
        
        folders, files = find_items_for_category(category_info)
        
        if not folders and not files:
            print(f"✅ No {category_name} folders or files found to consolidate")
            continue
        
        print(f"Found: {len(folders)} folders, {len(files)} files")
        
        result = consolidate_category(category_name, category_info, folders, files, dry_run=dry_run)
        all_results[category_name] = result
    
    # Final summary
    print(f"\n{'='*80}")
    print("📊 FINAL SUMMARY")
    print(f"{'='*80}")
    
    total_folders = sum(r['folders'] for r in all_results.values())
    total_files = sum(r['files'] for r in all_results.values())
    
    print(f"\nTotal items to consolidate:")
    print(f"  Folders: {total_folders}")
    print(f"  Files: {total_files}")
    
    print(f"\nBy category:")
    for cat, result in all_results.items():
        if result['folders'] > 0 or result['files'] > 0:
            print(f"  {cat}: {result['folders']} folders, {result['files']} files")
    
    if dry_run:
        print(f"\n💡 To execute consolidation for all categories, run:")
        print(f"   python3 {sys.argv[0]} --execute")
        print(f"\n💡 To execute for a specific category, run:")
        print(f"   python3 {sys.argv[0]} Resume --execute")
        print(f"   python3 {sys.argv[0]} Tax --execute")
        print(f"   etc.")

if __name__ == "__main__":
    main()
