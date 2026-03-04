#!/usr/bin/env python3
"""
Analyze iCloud folders and files to identify consolidation opportunities.
Finds folders/files with similar/derived names (e.g., Resume, Resume2022, resume, etc.)
and proposes consolidation into main folders.
"""
import os
from pathlib import Path
from collections import defaultdict
import re

icloud_base = "/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs"

def normalize_name(name):
    """Normalize name for comparison (lowercase, remove numbers, spaces, special chars)."""
    # Remove file extensions
    name = os.path.splitext(name)[0]
    # Lowercase
    name = name.lower()
    # Remove numbers and common suffixes
    name = re.sub(r'\d{4}', '', name)  # Remove years like 2022
    name = re.sub(r'\d+', '', name)  # Remove other numbers
    # Remove common suffixes
    name = re.sub(r'\s*(v\d+|version\d+|rev\d+|copy|backup).*$', '', name, flags=re.IGNORECASE)
    # Remove spaces and special chars
    name = re.sub(r'[^a-z]', '', name)
    return name

def find_similar_names(items, threshold=0.7):
    """Group items with similar normalized names."""
    groups = defaultdict(list)
    
    for item in items:
        normalized = normalize_name(item['name'])
        if normalized:
            groups[normalized].append(item)
    
    # Filter groups with multiple items or significant matches
    significant_groups = {}
    for key, group in groups.items():
        if len(group) > 1 or len(key) >= 4:  # At least 2 items or meaningful name
            significant_groups[key] = group
    
    return significant_groups

def scan_icloud_structure():
    """Scan iCloud for folders and files."""
    print("="*80)
    print("🔍 SCANNING iCLOUD FOR CONSOLIDATION OPPORTUNITIES")
    print("="*80)
    
    print(f"\n📁 Scanning: {icloud_base}")
    
    folders = []
    files = []
    
    if not os.path.exists(icloud_base):
        print(f"❌ Path not found: {icloud_base}")
        return [], []
    
    for root, dirs, filenames in os.walk(icloud_base):
        # Skip system folders
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        
        # Record folders
        for d in dirs:
            folder_path = os.path.join(root, d)
            relative = os.path.relpath(folder_path, icloud_base)
            folders.append({
                'name': d,
                'path': folder_path,
                'relative': relative,
                'normalized': normalize_name(d)
            })
        
        # Record files
        for f in filenames:
            if f.startswith('.'):
                continue
            file_path = os.path.join(root, f)
            relative = os.path.relpath(file_path, icloud_base)
            files.append({
                'name': f,
                'path': file_path,
                'relative': relative,
                'normalized': normalize_name(f)
            })
    
    print(f"\n📊 Found:")
    print(f"   Folders: {len(folders):,}")
    print(f"   Files: {len(files):,}")
    
    return folders, files

def analyze_consolidation(folders, files):
    """Analyze and propose consolidation."""
    print(f"\n{'='*80}")
    print("📊 CONSOLIDATION ANALYSIS")
    print(f"{'='*80}")
    
    # Find similar folder names
    print(f"\n📁 FOLDER CONSOLIDATION OPPORTUNITIES:")
    folder_groups = find_similar_names(folders)
    
    # Show top consolidation opportunities
    consolidation_plans = []
    
    for normalized, group in sorted(folder_groups.items(), key=lambda x: len(x[1]), reverse=True):
        if len(group) > 1:  # Multiple folders with similar names
            # Determine main folder name (most common or shortest)
            names = [f['name'] for f in group]
            main_name = min(names, key=len)  # Use shortest as base
            
            # Determine target location (common parent or create new)
            paths = [f['relative'] for f in group]
            common_parts = []
            for parts in [p.split('/')[:-1] for p in paths]:
                if not common_parts:
                    common_parts = parts
                else:
                    common_parts = [p for p in common_parts if p in parts]
            
            target_base = '/'.join(common_parts) if common_parts else 'Documents'
            target_folder = f"{target_base}/{main_name}" if target_base != 'Documents' else f"Documents/{main_name}"
            
            consolidation_plans.append({
                'type': 'folders',
                'normalized': normalized,
                'main_name': main_name,
                'target': target_folder,
                'items': group,
                'count': len(group)
            })
    
    # Show top opportunities
    print(f"\n   Found {len(consolidation_plans)} folder consolidation opportunities:")
    for plan in sorted(consolidation_plans, key=lambda x: x['count'], reverse=True)[:20]:
        print(f"\n   📁 '{plan['main_name']}' variations: {plan['count']} folders")
        print(f"      Target: {plan['target']}")
        for item in plan['items'][:5]:
            print(f"         - {item['relative']}")
        if len(plan['items']) > 5:
            print(f"         ... and {len(plan['items']) - 5} more")
    
    # Find files that match folder patterns
    print(f"\n📄 FILES TO CONSOLIDATE:")
    file_consolidations = []
    
    for plan in consolidation_plans[:10]:  # Top 10 folder patterns
        matching_files = []
        for file in files:
            if plan['normalized'] in file['normalized']:
                matching_files.append(file)
        
        if matching_files:
            file_consolidations.append({
                'pattern': plan['main_name'],
                'target': plan['target'],
                'files': matching_files,
                'count': len(matching_files)
            })
    
    for fc in sorted(file_consolidations, key=lambda x: x['count'], reverse=True)[:10]:
        print(f"\n   📄 '{fc['pattern']}' files: {fc['count']} files")
        print(f"      Target: {fc['target']}")
        for f in fc['files'][:5]:
            print(f"         - {f['relative']}")
        if len(fc['files']) > 5:
            print(f"         ... and {len(fc['files']) - 5} more")
    
    return consolidation_plans, file_consolidations

def main():
    folders, files = scan_icloud_structure()
    
    if not folders and not files:
        print("\n❌ No folders or files found")
        return
    
    consolidation_plans, file_consolidations = analyze_consolidation(folders, files)
    
    print(f"\n{'='*80}")
    print("💡 CONSOLIDATION PLAN")
    print(f"{'='*80}")
    print(f"""
Found consolidation opportunities:
  • {len(consolidation_plans)} folder groups to consolidate
  • {len(file_consolidations)} file groups to move

Next steps:
  1. Review the consolidation opportunities above
  2. Run consolidation script to execute:
     python3 scripts/consolidate_icloud_folders.py --execute
""")
    print("="*80)

if __name__ == "__main__":
    main()
