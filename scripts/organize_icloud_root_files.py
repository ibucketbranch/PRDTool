#!/usr/bin/env python3
"""
Find and organize loose files in the root of iCloud.
Files should not be sitting directly in the root - they should be in appropriate folders.
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

# Code project indicators
CODE_PROJECT_INDICATORS = [
    'package.json', 'requirements.txt', 'setup.py', 'pom.xml', 'build.gradle',
    'Cargo.toml', 'go.mod', 'composer.json', 'Gemfile', 'Makefile',
    '.gitignore', '.git', '.vscode', '.idea', 'tsconfig.json', 'webpack.config.js',
    'Dockerfile', '.dockerignore', 'docker-compose.yml', 'yarn.lock', 'package-lock.json'
]

def is_code_project(path):
    """Check if a path is a code project."""
    try:
        items = os.listdir(path)
        for indicator in CODE_PROJECT_INDICATORS:
            if indicator in items:
                return True
        if '.git' in items:
            return True
    except:
        pass
    return False

def get_file_category(file_name, file_path):
    """Determine where a file should go based on its name and path."""
    name_lower = file_name.lower()
    
    # Skip system files
    if file_name.startswith('.'):
        return None
    
    # Skip code project files
    if any(ext in name_lower for ext in ['.dll', '.exe', '.sys', '.tmp', '.log', '.lock']):
        return None
    
    # Check database for existing categorization
    try:
        result = supabase.table('documents')\
            .select('ai_category, context_bin, suggested_folder_structure')\
            .eq('current_path', file_path)\
            .limit(1)\
            .execute()
        
        if result.data and result.data[0]:
            doc = result.data[0]
            if doc.get('suggested_folder_structure'):
                return doc['suggested_folder_structure']
            if doc.get('context_bin') and doc.get('ai_category'):
                # Build path from context bin and category
                bin_name = doc['context_bin']
                category = doc['ai_category']
                return f"{bin_name}/{category}"
    except:
        pass
    
    # Fallback: categorize by filename patterns
    if any(kw in name_lower for kw in ['resume', 'cv', 'curriculum']):
        return 'Employment/Resumes'
    
    if any(kw in name_lower for kw in ['tax', 'w2', '1099', 'irs', 'turbotax']):
        return 'Finances Bin/Taxes'
    
    if any(kw in name_lower for kw in ['contract', 'agreement', 'sow', 'mou', 'nda']):
        return 'Legal Bin/Contracts'
    
    if any(kw in name_lower for kw in ['invoice', 'bill', 'receipt']):
        return 'Finances Bin/Invoices'
    
    if any(kw in name_lower for kw in ['statement', 'bank statement', 'estmt']):
        return 'Finances Bin/Statements'
    
    if any(kw in name_lower for kw in ['insurance', 'policy', 'coverage']):
        return 'Personal Bin/Insurance'
    
    if any(kw in name_lower for kw in ['medical', 'health', 'doctor', 'prescription']):
        return 'Personal Bin/Medical'
    
    if any(kw in name_lower for kw in ['vehicle', 'car', 'registration', 'dmv', 'tesla']):
        return 'Personal Bin/Vehicles'
    
    # Default: put in Documents/Uncategorized
    return 'Documents/Uncategorized'

def find_root_files():
    """Find all files directly in the iCloud root."""
    print("="*80)
    print("🔍 SCANNING FOR LOOSE FILES IN iCLOUD ROOT")
    print("="*80)
    
    root_files = []
    
    try:
        items = os.listdir(icloud_base)
        for item in items:
            item_path = os.path.join(icloud_base, item)
            
            # Skip directories
            if os.path.isdir(item_path):
                continue
            
            # Skip hidden files
            if item.startswith('.'):
                continue
            
            # Skip if it's a code project indicator file
            if item in CODE_PROJECT_INDICATORS:
                continue
            
            root_files.append({
                'name': item,
                'path': item_path,
                'size': os.path.getsize(item_path) if os.path.exists(item_path) else 0
            })
    except Exception as e:
        print(f"Error scanning root: {e}")
    
    print(f"\n📊 Found {len(root_files)} loose files in root")
    
    if root_files:
        print(f"\nFiles found:")
        for f in root_files[:20]:
            size_kb = f['size'] / 1024
            print(f"   - {f['name']} ({size_kb:.1f} KB)")
        if len(root_files) > 20:
            print(f"   ... and {len(root_files) - 20} more")
    
    return root_files

def organize_root_files(root_files, dry_run=True):
    """Organize root files into appropriate folders."""
    print(f"\n{'='*80}")
    if dry_run:
        print("📦 ORGANIZATION PLAN (DRY RUN)")
    else:
        print("📦 ORGANIZING ROOT FILES")
    print(f"{'='*80}")
    
    organized = {}
    errors = []
    
    for file_info in root_files:
        file_name = file_info['name']
        file_path = file_info['path']
        
        # Determine target location
        target_category = get_file_category(file_name, file_path)
        
        if not target_category:
            if dry_run:
                print(f"   ⏭️  Skipping: {file_name} (system/code file)")
            continue
        
        target_dir = os.path.join(icloud_base, target_category)
        target_file = os.path.join(target_dir, file_name)
        
        # Handle duplicates
        counter = 1
        while os.path.exists(target_file):
            name, ext = os.path.splitext(file_name)
            target_file = os.path.join(target_dir, f"{name}_{counter}{ext}")
            counter += 1
        
        if target_category not in organized:
            organized[target_category] = []
        organized[target_category].append({
            'name': file_name,
            'source': file_path,
            'target': target_file
        })
        
        if dry_run:
            print(f"   → {file_name}")
            print(f"      From: {os.path.relpath(file_path, icloud_base)}")
            print(f"      To:   {target_category}/{file_name if counter == 1 else os.path.basename(target_file)}")
        else:
            try:
                # Create target directory
                os.makedirs(target_dir, exist_ok=True)
                
                # Move file
                shutil.move(file_path, target_file)
                
                # Update database
                try:
                    result = supabase.table('documents')\
                        .select('id')\
                        .eq('current_path', file_path)\
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
                                'location_path': file_path,
                                'location_type': 'previous',
                                'discovered_at': datetime.now().isoformat(),
                                'verified_at': datetime.now().isoformat(),
                                'is_accessible': False,
                                'notes': f'Moved from iCloud root to {target_category}/'
                            })\
                            .execute()
                except:
                    pass
                
                print(f"   ✅ {file_name} → {target_category}/")
            except Exception as e:
                print(f"   ❌ {file_name}: {e}")
                errors.append({'file': file_name, 'error': str(e)})
    
    print(f"\n{'='*80}")
    if dry_run:
        print("📊 ORGANIZATION PLAN SUMMARY")
    else:
        print("✅ ORGANIZATION COMPLETE")
    print(f"{'='*80}")
    
    print(f"\nFiles to organize: {len(root_files)}")
    if organized:
        print(f"\nBy destination:")
        for category, files in organized.items():
            print(f"   {category}: {len(files)} files")
    
    if not dry_run:
        print(f"\nErrors: {len(errors)}")
        if errors:
            for err in errors[:10]:
                print(f"   - {err['file']}: {err['error']}")
    
    if dry_run:
        print(f"\n💡 To execute organization, run:")
        print(f"   python3 {sys.argv[0]} --execute")

def main():
    dry_run = '--execute' not in sys.argv
    
    root_files = find_root_files()
    
    if not root_files:
        print("\n✅ No loose files found in iCloud root!")
        return
    
    organize_root_files(root_files, dry_run=dry_run)

if __name__ == "__main__":
    main()
