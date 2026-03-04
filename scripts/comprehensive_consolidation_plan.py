#!/usr/bin/env python3
"""
Comprehensive consolidation plan for iCloud folders.
Identifies all duplicate/similar folders and files that should be consolidated.
"""
import os
import re
from pathlib import Path
from collections import defaultdict

icloud_base = "/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs"

SKIP_PATTERNS = [
    'node_modules', '.git', '__pycache__', '.xcodeproj', '.xcworkspace',
    'build/', 'dist/', 'lib/', 'src/', 'test/', 'tests/',
    'ProjectGatita', 'XcodeProjects', 'PhoneGapLib'
]

# Categories to consolidate
CONSOLIDATION_CATEGORIES = {
    'Resume': {
        'keywords': ['resume', 'cv', 'curriculum'],
        'target': 'Employment/Resumes',
        'description': 'All resume-related folders and files'
    },
    'Tax': {
        'keywords': ['tax', 'turbotax', 'w2', '1099', 'irs'],
        'target': 'Finances Bin/Taxes',
        'description': 'All tax-related documents'
    },
    'Contract': {
        'keywords': ['contract', 'agreement', 'sow', 'mou'],
        'target': 'Legal Bin/Contracts',
        'description': 'All contracts and agreements'
    },
    'Invoice': {
        'keywords': ['invoice', 'bill', 'receipt'],
        'target': 'Finances Bin/Invoices',
        'description': 'All invoices and bills'
    },
    'Statement': {
        'keywords': ['statement', 'estmt', 'bank statement'],
        'target': 'Finances Bin/Statements',
        'description': 'All bank and financial statements'
    },
    'Insurance': {
        'keywords': ['insurance', 'policy', 'coverage'],
        'target': 'Personal Bin/Insurance',
        'description': 'All insurance documents'
    },
    'Medical': {
        'keywords': ['medical', 'health', 'doctor', 'hospital', 'prescription'],
        'target': 'Personal Bin/Medical',
        'description': 'All medical records and documents'
    }
}

def normalize_name(name):
    """Normalize name for matching."""
    name = os.path.splitext(name)[0].lower()
    name = re.sub(r'\d{4}', '', name)
    name = re.sub(r'\d+', '', name)
    name = re.sub(r'\s*(v\d+|version\d+|rev\d+|copy|backup).*$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'[^a-z]', '', name)
    return name.strip()

def find_items_for_category(category_info):
    """Find folders and files matching a category."""
    keywords = category_info['keywords']
    target = category_info['target']
    
    matching_folders = []
    matching_files = []
    
    for root, dirs, files in os.walk(icloud_base):
        dirs[:] = [d for d in dirs if not any(pattern in d for pattern in SKIP_PATTERNS)]
        if any(pattern in root for pattern in SKIP_PATTERNS):
            continue
        
        # Check folders
        for d in dirs:
            normalized = normalize_name(d)
            if any(kw in normalized for kw in keywords):
                folder_path = os.path.join(root, d)
                relative = os.path.relpath(folder_path, icloud_base)
                
                # Skip if already in target
                if target in relative:
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
            normalized = normalize_name(f)
            if any(kw in normalized for kw in keywords):
                file_path = os.path.join(root, f)
                relative = os.path.relpath(file_path, icloud_base)
                
                # Skip if already in target
                if target in relative:
                    continue
                
                matching_files.append({
                    'name': f,
                    'path': file_path,
                    'relative': relative
                })
    
    return matching_folders, matching_files

def main():
    print("="*80)
    print("📋 COMPREHENSIVE CONSOLIDATION PLAN")
    print("="*80)
    print("""
This script identifies duplicate/similar folders and files that should be consolidated.
The document processor created folders without checking if similar folders already existed.
""")
    
    all_plans = {}
    
    for category, info in CONSOLIDATION_CATEGORIES.items():
        print(f"\n{'='*80}")
        print(f"📁 {category.upper()} CONSOLIDATION")
        print(f"{'='*80}")
        print(f"Description: {info['description']}")
        print(f"Target: {info['target']}")
        
        folders, files = find_items_for_category(info)
        
        print(f"\n📊 Found:")
        print(f"   Folders: {len(folders)}")
        print(f"   Files: {len(files)}")
        
        if folders:
            print(f"\n   Folders to consolidate:")
            for folder in folders[:10]:
                print(f"      - {folder['relative']}")
            if len(folders) > 10:
                print(f"      ... and {len(folders) - 10} more")
        
        if files:
            print(f"\n   Files to consolidate:")
            for file in files[:10]:
                print(f"      - {file['relative']}")
            if len(files) > 10:
                print(f"      ... and {len(files) - 10} more")
        
        all_plans[category] = {
            'info': info,
            'folders': folders,
            'files': files
        }
    
    # Summary
    print(f"\n{'='*80}")
    print("📊 CONSOLIDATION SUMMARY")
    print(f"{'='*80}")
    
    total_folders = sum(len(plan['folders']) for plan in all_plans.values())
    total_files = sum(len(plan['files']) for plan in all_plans.values())
    
    print(f"\nTotal items to consolidate:")
    print(f"   Folders: {total_folders}")
    print(f"   Files: {total_files}")
    
    print(f"\nBy category:")
    for category, plan in all_plans.items():
        folder_count = len(plan['folders'])
        file_count = len(plan['files'])
        if folder_count > 0 or file_count > 0:
            print(f"   {category}: {folder_count} folders, {file_count} files")
    
    print(f"\n{'='*80}")
    print("💡 NEXT STEPS")
    print(f"{'='*80}")
    print(f"""
1. Review the consolidation opportunities above
2. Execute consolidation for specific categories:
   python3 scripts/consolidate_resume_folders.py --execute
   
3. After consolidation, the filing manager will prevent future duplicates
   by checking existing folders before creating new ones
""")
    print("="*80)

if __name__ == "__main__":
    main()
