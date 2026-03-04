#!/usr/bin/env python3
"""
Process from Cache - OLDEST FOLDERS FIRST (Safe Strategy)
Processes PDFs from oldest-modified folders to minimize risk
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime

# Setup logging
log_file = Path.home() / '.document_system' / 'processing.log'
log_file.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

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

def process_oldest_first(batch_size: int = 10, dry_run: bool = False):
    """Process PDFs from OLDEST folders first (safe strategy)."""
    
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
    print(f"📦 BATCH PROCESSOR (OLDEST FOLDERS FIRST - Safe Strategy)")
    if dry_run:
        print(f"⚠️  DRY-RUN MODE")
    print(f"{'='*80}\n")
    
    # Load progress
    progress = load_progress()
    processed_paths = set(progress['processed_files'])
    
    # Filter out already processed
    remaining_pdfs = [p for p in all_pdfs if p['path'] not in processed_paths]
    
    # Sort by FILE modification time (NEWEST files first for recent documents!)
    remaining_pdfs.sort(key=lambda x: x['modified'], reverse=True)
    
    print(f"📊 Status:")
    print(f"   Total PDFs discovered: {len(all_pdfs)}")
    print(f"   Already processed: {len(processed_paths)}")
    print(f"   Remaining: {len(remaining_pdfs)}")
    print(f"   This batch: {min(batch_size, len(remaining_pdfs))}")
    print()
    
    if not remaining_pdfs:
        print("✅ All PDFs processed!")
        return
    
    # Get next batch from OLDEST folders
    batch = remaining_pdfs[:batch_size]
    
    print(f"📋 Next {len(batch)} files (from OLDEST folders):\n")
    
    for i, pdf in enumerate(batch, 1):
        file_modified = datetime.fromtimestamp(pdf['modified']).strftime('%Y-%m-%d')
        print(f"[{i}] {pdf['name']}")
        print(f"    📁 {Path(pdf['folder']).name}/")
        print(f"    📅 File modified: {file_modified}")
        print(f"    📏 Size: {pdf['size'] / 1024:.1f} KB")
        print()
    
    if dry_run:
        print(f"{'='*80}")
        print("⚠️  DRY-RUN - No files processed")
        print(f"{'='*80}\n")
        return
    
    # Process batch
    print(f"{'='*80}")
    print(f"🚀 PROCESSING BATCH (OLDEST FOLDERS FIRST)")
    print(f"{'='*80}\n")
    
    processor = DocumentProcessor()
    stats = {'processed': 0, 'errors': 0, 'error_details': []}
    
    for i, pdf in enumerate(batch, 1):
        print(f"[{i}/{len(batch)}] Processing: {pdf['name']}")
        print(f"   📁 {Path(pdf['folder']).name}/")
        
        try:
            result = processor.process_document(Path(pdf['path']))
            
            if result:
                stats['processed'] += 1
                progress['processed_files'].append(pdf['path'])
                progress['total_processed'] += 1
                print(f"   ✅ Success!\n")
            else:
                stats['errors'] += 1
                stats['error_details'].append({
                    'file': pdf['name'],
                    'error': 'Processing returned None'
                })
                print(f"   ⚠️  Returned None\n")
        
        except Exception as e:
            stats['errors'] += 1
            stats['error_details'].append({
                'file': pdf['name'],
                'error': str(e)
            })
            logger.error(f"Error processing {pdf['name']}: {e}", exc_info=True)
            print(f"   ❌ Error: {e}\n")
    
    # Save progress
    save_progress(progress)
    logger.info(f"Batch complete: {stats['processed']} processed, {stats['errors']} errors")
    
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
    
    if stats['error_details']:
        print(f"⚠️  Errors:")
        for error in stats['error_details']:
            print(f"   • {error['file']}: {error['error']}")
        print()
    
    if remaining_after > 0:
        print(f"💡 Run again to process next batch:")
        print(f"   python3 process_oldest_first.py --batch-size {batch_size}")
        print()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Process PDFs from OLDEST folders first (safe strategy)'
    )
    parser.add_argument('--batch-size', type=int, default=10,
                       help='Number of files to process (default: 10)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Preview only, do not process')
    
    args = parser.parse_args()
    
    process_oldest_first(args.batch_size, args.dry_run)
