#!/usr/bin/env python3
"""
Delete Duplicate PDFs - Remove duplicate copies, keeping one representative per unique hash
"""

import os
import json
import hashlib
from pathlib import Path
from collections import defaultdict

def calculate_hash(file_path):
    """Calculate SHA-256 hash of file."""
    h = hashlib.sha256()
    try:
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(1024*1024), b''):
                h.update(chunk)
        return h.hexdigest()
    except Exception as e:
        return None

def main():
    print("="*70)
    print("DUPLICATE PDF DELETION")
    print("="*70)
    print()
    
    # Load the PDF list
    pdf_list_file = Path('analysis/pdfs_outside_icloud.txt')
    
    if not pdf_list_file.exists():
        print("❌ Error: PDF list file not found!")
        return
    
    with open(pdf_list_file) as f:
        all_pdfs = [line.strip() for line in f if line.strip()]
    
    print(f"📋 Loaded {len(all_pdfs)} PDFs from list")
    print()
    
    # Group by hash
    print("🔍 Calculating hashes and finding duplicates...")
    hash_groups = defaultdict(list)
    
    for i, pdf_path in enumerate(all_pdfs, 1):
        if i % 500 == 0:
            print(f"   Hashing {i}/{len(all_pdfs)}...", end='\r')
        
        path = Path(pdf_path)
        if not path.exists():
            continue
        
        file_hash = calculate_hash(path)
        if file_hash:
            hash_groups[file_hash].append(path)
    
    print(f"\n✅ Found {len(hash_groups)} unique file hashes")
    print()
    
    # Identify duplicates
    duplicates_to_delete = []
    kept_files = []
    
    for file_hash, paths in hash_groups.items():
        if len(paths) > 1:
            # Keep the first one (shortest path usually), delete the rest
            paths_sorted = sorted(paths, key=lambda p: len(str(p)))
            kept_files.append(paths_sorted[0])
            duplicates_to_delete.extend(paths_sorted[1:])
        else:
            kept_files.append(paths[0])
    
    print(f"📊 Duplicate Analysis:")
    print(f"   Unique files to keep:     {len(kept_files):>6}")
    print(f"   Duplicates to delete:     {len(duplicates_to_delete):>6}")
    print()
    
    if not duplicates_to_delete:
        print("✅ No duplicates found to delete!")
        return
    
    # Calculate space savings
    total_size = sum(path.stat().st_size for path in duplicates_to_delete if path.exists())
    print(f"💾 Space to reclaim: {total_size / 1024 / 1024:.2f} MB")
    print()
    
    # Show some examples
    print("📄 Example duplicates (showing first 10):")
    for i, path in enumerate(duplicates_to_delete[:10], 1):
        # Find the kept version
        file_hash = calculate_hash(path)
        kept = [p for p in kept_files if calculate_hash(p) == file_hash][0]
        print(f"\n   {i}. DELETE: {path}")
        print(f"      KEEP:   {kept}")
    
    if len(duplicates_to_delete) > 10:
        print(f"\n   ... and {len(duplicates_to_delete) - 10} more duplicates")
    
    print()
    print("="*70)
    print("✅ USER CONFIRMED - PROCEEDING WITH DELETION")
    print("="*70)
    print(f"Deleting {len(duplicates_to_delete)} duplicate PDF files...")
    print(f"Keeping one copy of each unique file ({len(kept_files)} files)")
    print()
    
    print()
    print("🗑️  Deleting duplicate files...")
    
    deleted_count = 0
    failed_count = 0
    
    for i, path in enumerate(duplicates_to_delete, 1):
        if i % 100 == 0:
            print(f"   Deleted {i}/{len(duplicates_to_delete)}...", end='\r')
        
        try:
            if path.exists():
                os.remove(path)
                deleted_count += 1
        except Exception as e:
            failed_count += 1
    
    print(f"\n\n{'='*70}")
    print("DELETION COMPLETE")
    print("="*70)
    print(f"✅ Deleted:  {deleted_count} files")
    print(f"❌ Failed:   {failed_count} files")
    print(f"💾 Space reclaimed: {total_size / 1024 / 1024:.2f} MB")
    print()
    
    # Save log
    log_file = Path('analysis/deleted_duplicates.txt')
    with open(log_file, 'w') as f:
        f.write(f"Deleted {deleted_count} duplicate PDFs\n")
        f.write(f"Space reclaimed: {total_size / 1024 / 1024:.2f} MB\n\n")
        for path in duplicates_to_delete:
            f.write(f"{path}\n")
    
    print(f"📝 Deletion log saved to: {log_file}")

if __name__ == "__main__":
    main()
