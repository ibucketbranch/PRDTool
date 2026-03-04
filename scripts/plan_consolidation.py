#!/usr/bin/env python3
"""
Duplicate Consolidation Tool
Finds duplicates and creates an action plan to consolidate them with aliases
"""
import json
import hashlib
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
        print(f"Error hashing {filepath}: {e}")
        return None

def choose_master_file(files):
    """Choose which file to keep as master (newest in best location)"""
    # Priority: Main folder > Backup > Old > Archive
    def score_path(path):
        path_lower = path.lower()
        score = 0
        
        # Penalties for backup/old/archive folders
        if 'backup' in path_lower:
            score -= 100
        if 'old' in path_lower:
            score -= 50
        if 'archive' in path_lower:
            score -= 30
        if 'copy' in path_lower:
            score -= 20
            
        # Bonus for being in main bin
        if 'work bin' in path_lower or 'personal bin' in path_lower:
            score += 50
            
        # Bonus for shorter path (likely more organized)
        score -= len(Path(path).parts) * 5
        
        # Most recent modification time
        try:
            mtime = Path(path).stat().st_mtime
            score += mtime / 1000000  # Add timestamp component
        except:
            pass
            
        return score
    
    # Sort by score (highest first)
    sorted_files = sorted(files, key=score_path, reverse=True)
    return sorted_files[0]

def main():
    print("\n" + "="*80)
    print("🗜️  DUPLICATE CONSOLIDATION PLANNER")
    print("="*80 + "\n")
    
    # Load cache
    cache_file = Path.home() / '.document_system' / 'pdf_cache.json'
    progress_file = Path.home() / '.document_system' / 'batch_progress.json'
    
    with open(cache_file) as f:
        cache = json.load(f)
    with open(progress_file) as f:
        progress = json.load(f)
    
    processed_paths = set(progress.get('processed_files', []))
    all_pdfs = [pdf for pdf in cache.get('pdfs', []) if pdf['path'] in processed_paths]
    
    print(f"📊 Analyzing {len(all_pdfs)} processed files...\n")
    
    # Group by size first (fast pre-filter)
    by_size = defaultdict(list)
    for pdf in all_pdfs:
        by_size[pdf['size']].append(pdf)
    
    # Find actual duplicates by hash
    print("🔍 Computing hashes for potential duplicates...")
    duplicates = []
    total_checked = 0
    
    for size, pdfs in by_size.items():
        if len(pdfs) > 1:
            # Multiple files same size - check hashes
            by_hash = defaultdict(list)
            for pdf in pdfs:
                if Path(pdf['path']).exists():
                    file_hash = get_hash(pdf['path'])
                    if file_hash:
                        by_hash[file_hash].append(pdf['path'])
                    total_checked += 1
                    if total_checked % 100 == 0:
                        print(f"   Checked {total_checked} files...")
            
            # Find groups with multiple files (duplicates)
            for file_hash, paths in by_hash.items():
                if len(paths) > 1:
                    duplicates.append({
                        'hash': file_hash,
                        'paths': paths,
                        'size': size
                    })
    
    print(f"\n✅ Found {len(duplicates)} sets of duplicate files\n")
    
    # Create consolidation plan
    plan = []
    total_space_saved = 0
    total_files_to_replace = 0
    
    for dup_group in duplicates:
        paths = dup_group['paths']
        size = dup_group['size']
        
        # Choose master file
        master = choose_master_file(paths)
        duplicates_to_replace = [p for p in paths if p != master]
        
        space_saved = size * len(duplicates_to_replace)
        total_space_saved += space_saved
        total_files_to_replace += len(duplicates_to_replace)
        
        plan.append({
            'master': master,
            'duplicates': duplicates_to_replace,
            'size': size,
            'space_saved': space_saved
        })
    
    # Sort by space savings (biggest first)
    plan.sort(key=lambda x: x['space_saved'], reverse=True)
    
    # Show summary
    print("="*80)
    print("📋 CONSOLIDATION PLAN")
    print("="*80 + "\n")
    
    print(f"💾 Total space to save: {total_space_saved / (1024*1024*1024):.2f} GB")
    print(f"🗑️  Files to replace with aliases: {total_files_to_replace}")
    print(f"✅ Master copies to keep: {len(plan)}\n")
    
    # Show top 20 biggest savings
    print("🔥 TOP 20 BIGGEST SPACE SAVERS:\n")
    
    for i, item in enumerate(plan[:20], 1):
        master_name = Path(item['master']).name
        num_dups = len(item['duplicates'])
        space_mb = item['space_saved'] / (1024*1024)
        
        print(f"{i}. {master_name}")
        print(f"   Duplicates: {num_dups} copies")
        print(f"   Space saved: {space_mb:.1f} MB")
        print(f"   Master: {item['master']}")
        print(f"   Will replace:")
        for dup in item['duplicates'][:3]:  # Show first 3
            print(f"      → {dup}")
        if len(item['duplicates']) > 3:
            print(f"      → ... and {len(item['duplicates']) - 3} more")
        print()
    
    # Save plan to file
    plan_file = Path.home() / '.document_system' / 'consolidation_plan.json'
    with open(plan_file, 'w') as f:
        json.dump({
            'created': datetime.now().isoformat(),
            'total_space_saved': total_space_saved,
            'total_files_to_replace': total_files_to_replace,
            'total_masters': len(plan),
            'plan': plan
        }, f, indent=2)
    
    print("="*80)
    print(f"💾 Plan saved to: {plan_file}")
    print("="*80 + "\n")
    
    print("📝 NEXT STEPS:")
    print("   1. Review the plan above")
    print("   2. Run consolidation tool to execute (with dry-run first!)")
    print("   3. Space will be freed, all locations will still work via aliases")
    print()

if __name__ == '__main__':
    main()
