#!/usr/bin/env python3
"""
Filing Manager: Consolidate duplicate/similar folders and update document processor logic.

The issue: Document processor created folders without checking if similar folders already exist.
Solution: 
1. Scan for duplicate/similar folder patterns
2. Consolidate them into logical main folders
3. Update document processor to check existing folders before creating new ones
"""
import os
import re
from pathlib import Path
from collections import defaultdict

icloud_base = "/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs"

# Skip code projects and system folders
SKIP_PATTERNS = [
    'node_modules', '.git', '__pycache__', '.xcodeproj', '.xcworkspace',
    'build/', 'dist/', 'lib/', 'src/', 'test/', 'tests/',
    'ProjectGatita', 'XcodeProjects', 'PhoneGapLib', '.DS_Store'
]

def normalize_folder_name(name):
    """Normalize folder name for matching (remove numbers, years, versions)."""
    # Remove file extensions if any
    name = os.path.splitext(name)[0]
    # Lowercase
    name = name.lower()
    # Remove years (4 digits)
    name = re.sub(r'\d{4}', '', name)
    # Remove version numbers (v1, v2, rev1, etc.)
    name = re.sub(r'\s*(v\d+|version\d+|rev\d+|copy|backup|\d+).*$', '', name, flags=re.IGNORECASE)
    # Remove leading numbers (like "1Resumes" -> "resumes")
    name = re.sub(r'^\d+', '', name)
    # Remove spaces and special chars for comparison
    name = re.sub(r'[^a-z]', '', name)
    return name.strip()

def find_existing_folders():
    """Build a map of existing folders by normalized name."""
    print("="*80)
    print("📁 BUILDING FOLDER INDEX")
    print("="*80)
    
    folder_index = defaultdict(list)  # normalized_name -> [folders]
    all_folders = []
    
    print(f"\n🔍 Scanning: {icloud_base}")
    
    for root, dirs, files in os.walk(icloud_base):
        # Skip code projects
        dirs[:] = [d for d in dirs if not any(pattern in d for pattern in SKIP_PATTERNS)]
        if any(pattern in root for pattern in SKIP_PATTERNS):
            continue
        
        for d in dirs:
            folder_path = os.path.join(root, d)
            relative = os.path.relpath(folder_path, icloud_base)
            
            folder_info = {
                'name': d,
                'path': folder_path,
                'relative': relative,
                'normalized': normalize_folder_name(d)
            }
            
            all_folders.append(folder_info)
            
            normalized = folder_info['normalized']
            if normalized and len(normalized) >= 3:  # Only meaningful names
                folder_index[normalized].append(folder_info)
    
    print(f"   Found {len(all_folders):,} folders")
    print(f"   Indexed {len(folder_index):,} unique normalized names")
    
    return folder_index, all_folders

def find_duplicate_folders(folder_index):
    """Find folders with duplicate/similar names that should be consolidated."""
    print(f"\n{'='*80}")
    print("🔍 FINDING DUPLICATE FOLDER PATTERNS")
    print(f"{'='*80}")
    
    duplicates = {}
    
    for normalized, folders in folder_index.items():
        if len(folders) > 1:  # Multiple folders with same normalized name
            # Determine the "best" main folder (shortest name, or in logical location)
            main_folder = None
            main_score = float('inf')
            
            for folder in folders:
                # Score: prefer folders in logical locations (Employment, Work Bin, etc.)
                score = len(folder['name'])
                relative = folder['relative'].lower()
                
                # Prefer folders in logical locations
                if 'employment' in relative or 'work' in relative:
                    score -= 100
                if 'personal' in relative or 'family' in relative:
                    score -= 50
                
                if score < main_score:
                    main_score = score
                    main_folder = folder
            
            duplicates[normalized] = {
                'main': main_folder,
                'duplicates': [f for f in folders if f != main_folder],
                'count': len(folders)
            }
    
    # Sort by count (most duplicates first)
    sorted_duplicates = sorted(duplicates.items(), key=lambda x: x[1]['count'], reverse=True)
    
    print(f"\n📊 Found {len(sorted_duplicates)} folder patterns with duplicates:")
    
    for normalized, info in sorted_duplicates[:30]:  # Top 30
        print(f"\n   📁 '{normalized}' - {info['count']} folders")
        print(f"      Main: {info['main']['relative']}")
        for dup in info['duplicates'][:5]:
            print(f"      Duplicate: {dup['relative']}")
        if len(info['duplicates']) > 5:
            print(f"      ... and {len(info['duplicates']) - 5} more")
    
    return duplicates

def propose_consolidation_plan(duplicates):
    """Propose consolidation plan for duplicate folders."""
    print(f"\n{'='*80}")
    print("📋 CONSOLIDATION PLAN")
    print(f"{'='*80}")
    
    # Group by category
    categories = {
        'Resume': ['resume', 'resumes', 'cv'],
        'Tax': ['tax', 'taxes', 'turbotax'],
        'Contract': ['contract', 'contracts', 'agreement'],
        'Invoice': ['invoice', 'invoices', 'bill'],
        'Statement': ['statement', 'statements', 'estmt'],
        'Insurance': ['insurance', 'ins'],
        'Medical': ['medical', 'health', 'doctor'],
        'Legal': ['legal', 'law', 'attorney'],
    }
    
    consolidation_plans = []
    
    for category, keywords in categories.items():
        matching_duplicates = []
        for normalized, info in duplicates.items():
            if any(kw in normalized for kw in keywords):
                matching_duplicates.append((normalized, info))
        
        if matching_duplicates:
            consolidation_plans.append({
                'category': category,
                'keywords': keywords,
                'duplicates': matching_duplicates
            })
    
    # Show plans
    for plan in consolidation_plans:
        print(f"\n📁 {plan['category']} Consolidation:")
        total_folders = sum(len(info['duplicates']) for _, info in plan['duplicates'])
        print(f"   {total_folders} duplicate folders to consolidate")
        
        for normalized, info in plan['duplicates'][:5]:
            print(f"      - {normalized}: {info['count']} folders")
            print(f"        Main: {info['main']['relative']}")
    
    return consolidation_plans

def main():
    print("="*80)
    print("🗂️  FILING MANAGER - FOLDER CONSOLIDATION ANALYSIS")
    print("="*80)
    print("""
Purpose: Identify duplicate/similar folders created by document processor.
The processor created folders without checking if similar folders already existed.
This script will help consolidate them into logical main folders.
""")
    
    # Build folder index
    folder_index, all_folders = find_existing_folders()
    
    # Find duplicates
    duplicates = find_duplicate_folders(folder_index)
    
    # Propose consolidation
    consolidation_plans = propose_consolidation_plan(duplicates)
    
    print(f"\n{'='*80}")
    print("💡 NEXT STEPS")
    print(f"{'='*80}")
    print(f"""
1. Review the duplicate folder patterns above
2. Execute consolidation for specific categories:
   python3 scripts/consolidate_resume_folders.py --execute
   
3. After consolidation, update document_processor.py to:
   - Check for existing folders before creating new ones
   - Use the filing manager logic to match documents to existing folders
""")
    print("="*80)

if __name__ == "__main__":
    main()
