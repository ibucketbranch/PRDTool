#!/usr/bin/env python3
"""
Selective Duplicate Consolidation Tool
Focus on worst offenders: 6+ copies, backup folders, excessive duplication
"""
import json
import hashlib
import os
from pathlib import Path
from collections import defaultdict
from datetime import datetime

def get_hash(filepath):
    """Calculate SHA256 hash"""
    try:
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except Exception as e:
        return None

def choose_master_file(files):
    """Choose which file to keep as master"""
    def score_path(path):
        path_lower = path.lower()
        score = 0
        
        # Heavy penalties for backup/old/archive
        if 'backup' in path_lower:
            score -= 100
        if 'old' in path_lower:
            score -= 50
        if 'archive' in path_lower:
            score -= 30
        if 'copy' in path_lower:
            score -= 20
            
        # Bonus for main bins
        if 'work bin' in path_lower or 'personal bin' in path_lower or 'projects bin' in path_lower:
            score += 50
            
        # Shorter path = better organized
        score -= len(Path(path).parts) * 5
        
        # Most recent file
        try:
            mtime = Path(path).stat().st_mtime
            score += mtime / 1000000
        except:
            pass
            
        return score
    
    sorted_files = sorted(files, key=score_path, reverse=True)
    return sorted_files[0]

def is_backup_folder(path):
    """Check if file is in a backup/old/archive folder"""
    path_lower = path.lower()
    return any(x in path_lower for x in ['backup', '-old', 'archive', '-copy', 'temp'])

def create_alias(master_path, alias_path, dry_run=True):
    """Create a symbolic link (alias) to the master file"""
    if dry_run:
        return True
    
    try:
        # Remove the duplicate file
        os.remove(alias_path)
        # Create symbolic link
        os.symlink(master_path, alias_path)
        return True
    except Exception as e:
        print(f"Error creating alias: {e}")
        return False

def main(dry_run=True, min_copies=6):
    print("\n" + "="*80)
    print("🎯 SELECTIVE DUPLICATE CONSOLIDATION")
    print(f"   Focus: Files with {min_copies}+ copies & backup folders")
    if dry_run:
        print("   Mode: DRY-RUN (preview only)")
    else:
        print("   Mode: LIVE (will create aliases!)")
    print("="*80 + "\n")
    
    # Load data
    cache_file = Path.home() / '.document_system' / 'pdf_cache.json'
    progress_file = Path.home() / '.document_system' / 'batch_progress.json'
    
    with open(cache_file) as f:
        cache = json.load(f)
    with open(progress_file) as f:
        progress = json.load(f)
    
    processed_paths = set(progress.get('processed_files', []))
    all_pdfs = [pdf for pdf in cache.get('pdfs', []) if pdf['path'] in processed_paths]
    
    print(f"📊 Analyzing {len(all_pdfs)} files...\n")
    
    # Group by size and find duplicates
    by_size = defaultdict(list)
    for pdf in all_pdfs:
        by_size[pdf['size']].append(pdf)
    
    print("🔍 Finding duplicates...")
    duplicates = []
    
    for size, pdfs in by_size.items():
        if len(pdfs) > 1:
            by_hash = defaultdict(list)
            for pdf in pdfs:
                if Path(pdf['path']).exists():
                    file_hash = get_hash(pdf['path'])
                    if file_hash:
                        by_hash[file_hash].append(pdf['path'])
            
            for file_hash, paths in by_hash.items():
                if len(paths) >= min_copies:  # Only files with min_copies+ copies
                    duplicates.append({
                        'hash': file_hash,
                        'paths': paths,
                        'size': size
                    })
    
    print(f"✅ Found {len(duplicates)} duplicate sets with {min_copies}+ copies\n")
    
    if not duplicates:
        print(f"🎉 No files with {min_copies}+ copies found!")
        print(f"💡 Try lowering min_copies (current: {min_copies})")
        return
    
    # Create consolidation plan
    consolidation_plan = []
    total_space_saved = 0
    total_aliases_to_create = 0
    
    for dup_group in duplicates:
        paths = dup_group['paths']
        size = dup_group['size']
        
        # Choose master
        master = choose_master_file(paths)
        
        # Only replace files in backup folders (safer!)
        duplicates_to_replace = [
            p for p in paths 
            if p != master and is_backup_folder(p)
        ]
        
        if duplicates_to_replace:
            space_saved = size * len(duplicates_to_replace)
            total_space_saved += space_saved
            total_aliases_to_create += len(duplicates_to_replace)
            
            consolidation_plan.append({
                'master': master,
                'duplicates': duplicates_to_replace,
                'all_copies': len(paths),
                'size': size,
                'space_saved': space_saved
            })
    
    # Sort by space savings
    consolidation_plan.sort(key=lambda x: x['space_saved'], reverse=True)
    
    # Show plan
    print("="*80)
    print("📋 CONSOLIDATION PLAN - TOP OFFENDERS")
    print("="*80 + "\n")
    
    print(f"💾 Total space to save: {total_space_saved / (1024*1024):.1f} MB")
    print(f"🔗 Aliases to create: {total_aliases_to_create}")
    print(f"📁 Files to consolidate: {len(consolidation_plan)}")
    print(f"✅ Strategy: Keep master in main location, replace backup copies with aliases\n")
    
    # Show top 15
    print("🔥 FILES TO CONSOLIDATE:\n")
    
    for i, item in enumerate(consolidation_plan[:15], 1):
        master_name = Path(item['master']).name
        num_copies = item['all_copies']
        num_to_replace = len(item['duplicates'])
        space_mb = item['space_saved'] / (1024*1024)
        
        print(f"{i}. {master_name}")
        print(f"   📊 Total copies: {num_copies} | Replacing: {num_to_replace} backup copies")
        print(f"   💾 Space saved: {space_mb:.1f} MB")
        print(f"   ✅ KEEP: {item['master']}")
        print(f"   🔗 CREATE ALIASES:")
        for dup in item['duplicates'][:2]:
            print(f"      → {dup}")
        if len(item['duplicates']) > 2:
            print(f"      → ... and {len(item['duplicates']) - 2} more backup copies")
        print()
    
    if len(consolidation_plan) > 15:
        print(f"... and {len(consolidation_plan) - 15} more files\n")
    
    # Save plan
    plan_file = Path.home() / '.document_system' / 'selective_consolidation_plan.json'
    with open(plan_file, 'w') as f:
        json.dump({
            'created': datetime.now().isoformat(),
            'dry_run': dry_run,
            'min_copies': min_copies,
            'total_space_saved': total_space_saved,
            'total_aliases': total_aliases_to_create,
            'plan': consolidation_plan
        }, f, indent=2)
    
    print("="*80)
    print(f"💾 Plan saved to: {plan_file}")
    print("="*80 + "\n")
    
    if dry_run:
        print("📝 NEXT STEPS:")
        print("   1. Review the plan above")
        print("   2. Run with --execute to create aliases")
        print("   3. Or adjust --min-copies to change threshold")
        print("\n💡 Commands:")
        print("   Preview:  python3 consolidate_selective.py")
        print("   Execute:  python3 consolidate_selective.py --execute")
        print("   Adjust:   python3 consolidate_selective.py --min-copies 4")
    else:
        print("\n🚀 EXECUTING CONSOLIDATION...\n")
        
        success_count = 0
        error_count = 0
        
        for item in consolidation_plan:
            master = item['master']
            for dup_path in item['duplicates']:
                if create_alias(master, dup_path, dry_run=False):
                    print(f"✅ {Path(dup_path).name} → alias to master")
                    success_count += 1
                else:
                    print(f"❌ Failed: {dup_path}")
                    error_count += 1
        
        print(f"\n✅ Created {success_count} aliases")
        if error_count:
            print(f"❌ Errors: {error_count}")
        print(f"💾 Space freed: {total_space_saved / (1024*1024):.1f} MB")
    
    print()

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Selective duplicate consolidation')
    parser.add_argument('--execute', action='store_true', 
                       help='Execute consolidation (default is dry-run)')
    parser.add_argument('--min-copies', type=int, default=6,
                       help='Minimum number of copies to consolidate (default: 6)')
    
    args = parser.parse_args()
    
    main(dry_run=not args.execute, min_copies=args.min_copies)
