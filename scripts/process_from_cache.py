#!/usr/bin/env python3
"""
Process from Cache - Process PDFs from discovered cache
Processes MOST RECENTLY USED files first!
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

# Set API key
# Use env: export GROQ_API_KEY="your_key"

from document_processor import DocumentProcessor

def load_progress():
    """Load processing progress."""
    progress_file = Path.home() / '.document_system' / 'batch_progress.json'
    if progress_file.exists():
        with open(progress_file, 'r') as f:
            return json.load(f)
    return {'processed_files': [], 'total_processed': 0}

def save_progress(progress):
    """Save processing progress."""
    progress_file = Path.home() / '.document_system' / 'batch_progress.json'
    progress_file.parent.mkdir(parents=True, exist_ok=True)
    with open(progress_file, 'w') as f:
        json.dump(progress, f, indent=2)

def process_from_cache(batch_size: int = 10, dry_run: bool = False):
    """Process PDFs from cache (most recently used first)."""
    
    # Load cache
    cache_file = Path.home() / '.document_system' / 'pdf_cache.json'
    
    if not cache_file.exists():
        print("❌ No cache found!")
        print("   Run: python3 discover_pdfs.py <folder_path>")
        return
    
    with open(cache_file, 'r') as f:
        cache_data = json.load(f)
    
    all_pdfs = cache_data['pdfs']
    
    print(f"\n{'='*80}")
    print(f"📦 BATCH PROCESSOR (Most Recently Used First)")
    if dry_run:
        print(f"⚠️  DRY-RUN MODE")
    print(f"{'='*80}\n")
    
    # Load progress
    progress = load_progress()
    processed_paths = set(progress['processed_files'])
    
    # Filter out already processed
    remaining_pdfs = [p for p in all_pdfs if p['path'] not in processed_paths]
    
    print(f"📊 Status:")
    print(f"   Total PDFs discovered: {len(all_pdfs)}")
    print(f"   Already processed: {len(processed_paths)}")
    print(f"   Remaining: {len(remaining_pdfs)}")
    print(f"   This batch: {min(batch_size, len(remaining_pdfs))}")
    print()
    
    if not remaining_pdfs:
        print("✅ All PDFs processed!")
        return
    
    # Get next batch
    batch = remaining_pdfs[:batch_size]
    
    print(f"📋 Next {len(batch)} files (most recently used):\n")
    
    for i, pdf in enumerate(batch, 1):
        accessed = datetime.fromtimestamp(pdf['accessed']).strftime('%Y-%m-%d %H:%M')
        print(f"[{i}] {pdf['name']}")
        print(f"    📁 {Path(pdf['folder']).name}/")
        print(f"    📅 Last accessed: {accessed}")
        print(f"    📏 Size: {pdf['size'] / 1024:.1f} KB")
        print()
    
    if dry_run:
        print(f"{'='*80}")
        print("⚠️  DRY-RUN - No files processed")
        print(f"{'='*80}\n")
        return
    
    # Process batch
    print(f"{'='*80}")
    print(f"🚀 PROCESSING BATCH")
    print(f"{'='*80}\n")
    
    processor = DocumentProcessor()
    stats = {'processed': 0, 'errors': 0}
    
    for i, pdf in enumerate(batch, 1):
        print(f"[{i}/{len(batch)}] Processing: {pdf['name']}")
        
        try:
            result = processor.process_document(Path(pdf['path']))
            
            if result:
                stats['processed'] += 1
                progress['processed_files'].append(pdf['path'])
                progress['total_processed'] += 1
                print(f"   ✅ Success!\n")
            else:
                stats['errors'] += 1
                print(f"   ⚠️  Returned None\n")
        
        except Exception as e:
            stats['errors'] += 1
            print(f"   ❌ Error: {e}\n")
    
    # Save progress
    save_progress(progress)
    
    # Summary
    remaining_after = len(remaining_pdfs) - len(batch)
    
    print(f"\n{'='*80}")
    print(f"📊 BATCH COMPLETE")
    print(f"{'='*80}")
    print(f"   ✅ Processed: {stats['processed']}")
    print(f"   ❌ Errors: {stats['errors']}")
    print(f"   📋 Remaining: {remaining_after}")
    print(f"   📈 Total processed (all time): {progress['total_processed']}")
    print(f"{'='*80}\n")
    
    if remaining_after > 0:
        print(f"💡 Run again to process next batch:")
        print(f"   python3 process_from_cache.py --batch-size {batch_size}")
        print()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Process PDFs from cache (most recently used first)'
    )
    parser.add_argument('--batch-size', type=int, default=10,
                       help='Number of files to process (default: 10)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Preview only, do not process')
    
    args = parser.parse_args()
    
    process_from_cache(args.batch_size, args.dry_run)
