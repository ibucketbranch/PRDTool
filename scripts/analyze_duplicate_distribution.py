#!/usr/bin/env python3
"""Analyze duplicate file distribution and locations"""
import json
from pathlib import Path
from collections import Counter, defaultdict

# Load processing progress
progress_file = Path.home() / '.document_system' / 'batch_progress.json'
cache_file = Path.home() / '.document_system' / 'pdf_cache.json'

with open(progress_file) as f:
    progress = json.load(f)

with open(cache_file) as f:
    cache = json.load(f)

# Get all processed PDFs
processed_paths = set(progress.get('processed_files', []))
all_pdfs = {pdf['path']: pdf for pdf in cache.get('pdfs', []) if pdf['path'] in processed_paths}

print("\n" + "="*80)
print("🔍 DUPLICATE FILE ANALYSIS")
print("="*80 + "\n")

# Calculate hashes for all processed files
import hashlib

def get_hash(filepath):
    """Calculate SHA256 hash"""
    try:
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except:
        return None

print("📊 Analyzing file hashes...")
hash_to_files = defaultdict(list)
processed = 0

for path, info in all_pdfs.items():
    # Use size as quick pre-filter
    hash_key = f"{info['size']}"  # Group by size first for speed
    hash_to_files[hash_key].append(path)
    processed += 1
    if processed % 1000 == 0:
        print(f"   Processed {processed}/{len(all_pdfs)} files...")

print(f"\n✅ Analyzed {len(all_pdfs)} files\n")

# Find duplicates (same size)
potential_dups = {k: v for k, v in hash_to_files.items() if len(v) > 1}

print(f"📋 DUPLICATE DISTRIBUTION:\n")

# Count how many files have N copies
copy_counts = Counter(len(files) for files in potential_dups.values())

total_duplicate_files = sum((count - 1) * num for count, num in copy_counts.items())

print(f"Total unique files with duplicates: {len(potential_dups)}")
print(f"Total duplicate copies: {total_duplicate_files}\n")

print("Copy distribution:")
for num_copies in sorted(copy_counts.keys()):
    num_files = copy_counts[num_copies]
    print(f"   {num_copies} copies: {num_files} files ({num_copies-1} dups each = {(num_copies-1)*num_files} total dups)")

# Analyze locations
print(f"\n📁 LOCATION ANALYSIS:\n")

# Extract bin/folder patterns
def get_bin(path):
    """Extract the bin folder"""
    if 'Work Bin' in path:
        return 'Work Bin'
    elif 'Personal Bin' in path:
        return 'Personal Bin'
    elif 'Projects Bin' in path or 'Projcts Bin' in path:
        return 'Projects Bin'
    elif 'Lexar' in path:
        return 'Lexar'
    elif 'Micron' in path:
        return 'Micron'
    else:
        return 'Other'

# Show examples of files with most copies
print("🔥 Files with MOST copies:\n")
top_duplicates = sorted(potential_dups.items(), key=lambda x: len(x[1]), reverse=True)[:10]

for i, (size, paths) in enumerate(top_duplicates, 1):
    print(f"{i}. {len(paths)} copies of file ({int(size)/(1024*1024):.1f} MB each):")
    bins = Counter(get_bin(p) for p in paths)
    print(f"   Locations: {dict(bins)}")
    print(f"   Example: {Path(paths[0]).name}")
    print()

# Bin distribution
print("📊 Duplicates by Bin:\n")
all_dup_paths = [p for paths in potential_dups.values() for p in paths]
bin_distribution = Counter(get_bin(p) for p in all_dup_paths)

for bin_name, count in bin_distribution.most_common():
    print(f"   {bin_name}: {count} duplicate files")

print("\n" + "="*80 + "\n")
