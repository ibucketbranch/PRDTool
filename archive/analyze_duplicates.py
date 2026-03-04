#!/usr/bin/env python3
"""
Duplicate Analyzer - Find duplicate PDFs and calculate space savings
Supports creating macOS aliases to save space while maintaining organization
"""

import os
import sys
import hashlib
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict

def calculate_file_hash(file_path: Path) -> str:
    """Calculate SHA256 hash of file."""
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except Exception as e:
        print(f"Error hashing {file_path}: {e}")
        return None


def analyze_duplicates(cache_file: str = None):
    """Analyze PDFs for duplicates."""
    
    if cache_file is None:
        cache_file = Path.home() / '.document_system' / 'pdf_cache.json'
    else:
        cache_file = Path(cache_file)
    
    if not cache_file.exists():
        print("❌ No PDF cache found!")
        print("   Run: python3 discover_pdfs.py <folder>")
        return
    
    # Load PDF cache
    with open(cache_file, 'r') as f:
        cache_data = json.load(f)
    
    all_pdfs = cache_data['pdfs']
    
    print(f"\n{'='*80}")
    print(f"🔍 DUPLICATE ANALYSIS")
    print(f"{'='*80}\n")
    
    print(f"📊 Analyzing {len(all_pdfs)} PDFs...")
    print(f"   This will hash files to detect duplicates...")
    print()
    
    # Group by size first (quick filter)
    print("Step 1: Grouping by size...")
    size_groups = defaultdict(list)
    for pdf in all_pdfs:
        size_groups[pdf['size']].append(pdf)
    
    # Only hash files with same size
    potential_duplicates = {size: pdfs for size, pdfs in size_groups.items() if len(pdfs) > 1}
    
    print(f"   ✅ Found {len(potential_duplicates)} size groups with potential duplicates")
    print()
    
    # Hash files in potential duplicate groups
    print("Step 2: Hashing files to confirm duplicates...")
    hash_groups = defaultdict(list)
    total_to_hash = sum(len(pdfs) for pdfs in potential_duplicates.values())
    hashed = 0
    
    for size, pdfs in potential_duplicates.items():
        for pdf in pdfs:
            file_hash = calculate_file_hash(Path(pdf['path']))
            if file_hash:
                hash_groups[file_hash].append(pdf)
                hashed += 1
                if hashed % 100 == 0:
                    print(f"   Hashed {hashed}/{total_to_hash} files...", end='\r')
    
    print(f"   ✅ Hashed {hashed} files                    ")
    print()
    
    # Find duplicates
    duplicates = {h: pdfs for h, pdfs in hash_groups.items() if len(pdfs) > 1}
    
    # Calculate statistics
    total_duplicates = sum(len(pdfs) - 1 for pdfs in duplicates.values())
    wasted_space = sum((len(pdfs) - 1) * pdfs[0]['size'] for pdfs in duplicates.values())
    
    print(f"{'='*80}")
    print(f"📊 DUPLICATE REPORT")
    print(f"{'='*80}\n")
    
    print(f"Total PDFs: {len(all_pdfs)}")
    print(f"Unique files: {len(all_pdfs) - total_duplicates}")
    print(f"Duplicate copies: {total_duplicates}")
    print(f"Duplicate sets: {len(duplicates)}")
    print()
    
    print(f"💾 SPACE SAVINGS POTENTIAL")
    print(f"   Wasted space: {wasted_space / 1024 / 1024:.1f} MB ({wasted_space / 1024 / 1024 / 1024:.2f} GB)")
    print(f"   Savings with aliases: {(wasted_space - total_duplicates * 1024) / 1024 / 1024:.1f} MB")
    print(f"   (Aliases are ~1 KB each)")
    print()
    
    # Show top duplicates
    if duplicates:
        print(f"🔝 TOP 10 DUPLICATED FILES (by wasted space):\n")
        
        # Sort by wasted space
        sorted_dups = sorted(
            duplicates.items(),
            key=lambda x: (len(x[1]) - 1) * x[1][0]['size'],
            reverse=True
        )
        
        for i, (file_hash, pdfs) in enumerate(sorted_dups[:10], 1):
            copies = len(pdfs)
            size = pdfs[0]['size']
            wasted = (copies - 1) * size
            
            print(f"[{i}] {pdfs[0]['name']}")
            print(f"    Copies: {copies}")
            print(f"    Size each: {size / 1024:.1f} KB")
            print(f"    Wasted: {wasted / 1024:.1f} KB")
            print(f"    Locations:")
            for pdf in pdfs:
                accessed = datetime.fromtimestamp(pdf['accessed']).strftime('%Y-%m-%d')
                print(f"      • {Path(pdf['folder']).name}/ (accessed: {accessed})")
            print()
    
    # Save duplicate report
    report_file = Path.home() / '.document_system' / 'duplicate_report.json'
    report_data = {
        'analyzed_at': datetime.now().isoformat(),
        'total_pdfs': len(all_pdfs),
        'unique_files': len(all_pdfs) - total_duplicates,
        'duplicate_copies': total_duplicates,
        'duplicate_sets': len(duplicates),
        'wasted_space_bytes': wasted_space,
        'duplicates': {
            h: [{
                'path': pdf['path'],
                'folder': pdf['folder'],
                'name': pdf['name'],
                'size': pdf['size'],
                'accessed': pdf['accessed']
            } for pdf in pdfs]
            for h, pdfs in duplicates.items()
        }
    }
    
    with open(report_file, 'w') as f:
        json.dump(report_data, f, indent=2)
    
    print(f"💾 Duplicate report saved: {report_file}")
    print()
    
    return report_data


def create_aliases(dry_run: bool = True):
    """Create macOS aliases for duplicate files to save space."""
    
    report_file = Path.home() / '.document_system' / 'duplicate_report.json'
    
    if not report_file.exists():
        print("❌ No duplicate report found!")
        print("   Run: python3 analyze_duplicates.py")
        return
    
    with open(report_file, 'r') as f:
        report = json.load(f)
    
    duplicates = report['duplicates']
    
    if not duplicates:
        print("✅ No duplicates found!")
        return
    
    print(f"\n{'='*80}")
    print(f"🔗 CREATE ALIASES FOR DUPLICATES")
    if dry_run:
        print(f"⚠️  DRY-RUN MODE")
    print(f"{'='*80}\n")
    
    total_space_saved = 0
    actions = []
    
    for file_hash, pdfs in duplicates.items():
        # Keep the most recently accessed as original
        pdfs_sorted = sorted(pdfs, key=lambda x: x['accessed'], reverse=True)
        original = pdfs_sorted[0]
        dups = pdfs_sorted[1:]
        
        for dup in dups:
            action = {
                'original': original['path'],
                'duplicate': dup['path'],
                'size_saved': dup['size']
            }
            actions.append(action)
            total_space_saved += dup['size']
    
    print(f"📊 Summary:")
    print(f"   Files to alias: {len(actions)}")
    print(f"   Space to save: {total_space_saved / 1024 / 1024:.1f} MB")
    print()
    
    if dry_run:
        print(f"Preview of first 10 actions:\n")
        for i, action in enumerate(actions[:10], 1):
            print(f"[{i}] {Path(action['duplicate']).name}")
            print(f"    Original: {Path(action['original']).parent.name}/")
            print(f"    Replace: {Path(action['duplicate']).parent.name}/")
            print(f"    Save: {action['size_saved'] / 1024:.1f} KB")
            print()
        
        print(f"{'='*80}")
        print(f"To actually create aliases:")
        print(f"  python3 analyze_duplicates.py --create-aliases")
        print(f"{'='*80}\n")
    else:
        print(f"⚠️  WARNING: This will replace files with aliases!")
        print(f"   Make sure you have backups!")
        print()
        response = input("Type 'YES' to proceed: ")
        
        if response != 'YES':
            print("Cancelled.")
            return
        
        print(f"\nCreating aliases...\n")
        
        success = 0
        errors = 0
        
        for i, action in enumerate(actions, 1):
            try:
                original = Path(action['original'])
                duplicate = Path(action['duplicate'])
                
                # Backup duplicate to .bak
                backup = duplicate.with_suffix(duplicate.suffix + '.bak')
                duplicate.rename(backup)
                
                # Create alias using ln -s (symbolic link)
                os.symlink(original, duplicate)
                
                # Remove backup
                backup.unlink()
                
                success += 1
                print(f"[{i}/{len(actions)}] ✅ {duplicate.name}")
                
            except Exception as e:
                errors += 1
                print(f"[{i}/{len(actions)}] ❌ {duplicate.name}: {e}")
                
                # Restore backup if exists
                if backup.exists():
                    backup.rename(duplicate)
        
        print(f"\n{'='*80}")
        print(f"📊 ALIAS CREATION COMPLETE")
        print(f"{'='*80}")
        print(f"   ✅ Success: {success}")
        print(f"   ❌ Errors: {errors}")
        print(f"   💾 Space saved: {(success * (total_space_saved / len(actions))) / 1024 / 1024:.1f} MB")
        print(f"{'='*80}\n")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Analyze duplicates and create space-saving aliases',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze for duplicates
  python3 analyze_duplicates.py
  
  # Preview alias creation
  python3 analyze_duplicates.py --create-aliases --dry-run
  
  # Actually create aliases (saves space!)
  python3 analyze_duplicates.py --create-aliases
  
macOS Aliases:
  - Aliases are symbolic links that point to the original
  - They use ~1 KB instead of full file size
  - They work transparently with all apps
  - Original file locations are preserved
        """
    )
    
    parser.add_argument('--create-aliases', action='store_true',
                       help='Create aliases for duplicates')
    parser.add_argument('--dry-run', action='store_true',
                       help='Preview only (default for --create-aliases)')
    
    args = parser.parse_args()
    
    if args.create_aliases:
        create_aliases(dry_run=args.dry_run if args.dry_run else True)
    else:
        analyze_duplicates()
