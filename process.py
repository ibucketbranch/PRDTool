#!/usr/bin/env python3
"""
Batch Processor - Robust Processing of PDFs
Processes files from the cache, respecting existing database entries.
"""

import os
import sys
import json
import time
import signal
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

from document_processor import DocumentProcessor

# Add scripts directory to path for lock_manager
sys.path.insert(0, str(Path(__file__).parent / 'scripts'))
from lock_manager import set_processing_active, read_lock

# Global flag for graceful shutdown
SHUTDOWN_REQUESTED = False

class ProcessingTimeoutError(Exception):
    pass

def timeout_handler(signum, frame):
    raise ProcessingTimeoutError("Processing timed out")

def signal_handler(signum, frame):
    global SHUTDOWN_REQUESTED
    print("\n⚠️  Shutdown signal received! Finishing current file...")
    SHUTDOWN_REQUESTED = True

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def load_progress():
    """Load processing progress."""
    progress_file = Path.home() / '.document_system' / 'batch_progress.json'
    if progress_file.exists():
        try:
            with open(progress_file, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass
    return {'processed_paths': [], 'failed_paths': [], 'total_processed': 0}

def save_progress(progress):
    """Save processing progress."""
    progress_file = Path.home() / '.document_system' / 'batch_progress.json'
    progress_file.parent.mkdir(parents=True, exist_ok=True)
    with open(progress_file, 'w') as f:
        json.dump(progress, f, indent=2)

def batch_process(batch_size: int = 50, dry_run: bool = False, worker_id: int = 0, total_workers: int = 1):
    """Process PDFs in batches."""
    
    # Update lock file: processing active
    if not dry_run:
        set_processing_active(True)
    
    # Load cache
    cache_file = Path.home() / '.document_system' / 'pdf_cache.json'
    
    if not cache_file.exists():
        print("❌ No cache found!")
        print("   Run: python3 discover_pdfs.py")
        return
    
    with open(cache_file, 'r') as f:
        cache_data = json.load(f)
    
    all_pdfs = cache_data['pdfs']
    
    print(f"\n{'='*80}")
    print(f"📦 BATCH PROCESSOR (Worker {worker_id}/{total_workers})")
    if dry_run:
        print(f"⚠️  DRY-RUN MODE")
    print(f"{'='*80}\n")
    
    # Load progress
    progress = load_progress()
    processed_paths = set(progress['processed_paths'])
    failed_paths = set(progress['failed_paths']) # We might want to retry these later
    
    # Filter out already processed
    remaining_pdfs = [p for p in all_pdfs if p['path'] not in processed_paths]
    
    # Sort by FILE modification time (OLDEST files first - Safe Strategy)
    remaining_pdfs.sort(key=lambda x: x['modified'], reverse=False)
    
    # Distribute work among workers using modulo
    my_pdfs = [p for i, p in enumerate(remaining_pdfs) if i % total_workers == worker_id]
    
    print(f"📊 Status:")
    print(f"   Total PDFs discovered: {len(all_pdfs)}")
    print(f"   Already processed: {len(processed_paths)}")
    print(f"   Remaining (Total): {len(remaining_pdfs)}")
    print(f"   Assigned to this worker: {len(my_pdfs)}")
    print(f"   Strategy: Oldest files first (Historical/Safe)")
    print()
    
    if not my_pdfs:
        print("✅ No PDFs assigned to this worker!")
        return
    
    # Get next batch
    batch = my_pdfs[:batch_size]
    
    if dry_run:
        print(f"📋 Next {len(batch)} files to process:")
        for i, pdf in enumerate(batch[:5], 1):
             print(f"   {i}. {pdf['name']} ({pdf['size']/1024:.1f} KB)")
        if len(batch) > 5:
            print(f"   ... and {len(batch)-5} more")
        return
    
    # Initialize processor
    try:
        processor = DocumentProcessor()
    except Exception as e:
        print(f"❌ Failed to initialize processor: {e}")
        return

    stats = {'processed': 0, 'skipped': 0, 'errors': 0}
    
    print(f"🚀 Starting batch of {len(batch)} files...\n")
    
    for i, pdf in enumerate(batch, 1):
        if SHUTDOWN_REQUESTED:
            break
            
        print(f"[{i}/{len(batch)}] {pdf['name']}")
        
        # Skip known bad filenames
        if "deleted content" in pdf['name'] or "NSKeyedArchiver" in pdf['name'] or "Document Details -" in pdf['name']:
            print(f"   ⚠️  Skipping: Corrupted/Placeholder file")
            stats['skipped'] += 1
            progress['processed_paths'].append(pdf['path'])
            continue
        
        try:
            # Set timeout watcher (60 seconds per file - SHARP WATCHER)
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(60)  # Aggressive timeout - catch hangers fast
            
            # Process document
            result = processor.process_document(Path(pdf['path']))
            
            # Disable alarm on success
            signal.alarm(0)
            
            if result['status'] == 'success':
                stats['processed'] += 1
                progress['processed_paths'].append(pdf['path'])
                progress['total_processed'] += 1
                # Remove from failed if it was there
                if pdf['path'] in failed_paths:
                    progress['failed_paths'].remove(pdf['path'])
                    
            elif result['status'] == 'skipped':
                stats['skipped'] += 1
                progress['processed_paths'].append(pdf['path']) # Mark as processed so we don't check again
                
            else:
                stats['errors'] += 1
                if pdf['path'] not in progress['failed_paths']:
                     progress['failed_paths'].append(pdf['path'])
                print(f"   ❌ Failed: {result.get('reason')} - {result.get('error')}")
        
        except ProcessingTimeoutError:
            print(f"   ⏰ TIMEOUT: Processing took > 60 seconds. Skipping immediately.")
            stats['errors'] += 1
            if pdf['path'] not in progress['failed_paths']:
                progress['failed_paths'].append(pdf['path'])
        
        except Exception as e:
            signal.alarm(0) # Ensure alarm is disabled on error
            stats['errors'] += 1
            if pdf['path'] not in progress['failed_paths']:
                progress['failed_paths'].append(pdf['path'])
            logger.error(f"Error processing {pdf['name']}: {e}", exc_info=True)
            print(f"   ❌ Error: {e}")
            
        finally:
            signal.alarm(0) # Safety net to ensure alarm is always disabled
            
        # Save progress every file to be safe
        save_progress(progress)
        
        # Minimal pause for speed (watcher will catch hangers)
        time.sleep(0.1)  # Reduced from 0.5s for faster processing
        print()
        
        # Trigger backup after every 500 documents processed
        if progress['total_processed'] > 0 and progress['total_processed'] % 500 == 0:
            print(f"💾 Triggering backup after {progress['total_processed']} documents...")
            try:
                import subprocess
                backup_script = Path(__file__).parent / 'scripts' / 'auto_backup.py'
                subprocess.run([sys.executable, str(backup_script)], timeout=300, check=False)
            except Exception as e:
                logger.warning(f"Backup trigger failed: {e}")

    # Update lock file: processing complete
    if not dry_run:
        lock = read_lock()
        set_processing_active(False, progress['total_processed'])
    
    print(f"\n{'='*80}")
    print(f"📊 BATCH COMPLETE")
    print(f"   ✅ Processed: {stats['processed']}")
    print(f"   ⏭️  Skipped:   {stats['skipped']}")
    print(f"   ❌ Errors:    {stats['errors']}")
    print(f"{'='*80}\n")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Batch process PDFs.')
    parser.add_argument('--batch-size', type=int, default=50, help='Batch size')
    parser.add_argument('--dry-run', action='store_true', help='Dry run')
    parser.add_argument('--worker-id', type=int, default=0, help='Worker ID (0-based)')
    parser.add_argument('--total-workers', type=int, default=1, help='Total number of workers')
    args = parser.parse_args()
    
    batch_process(args.batch_size, args.dry_run, args.worker_id, args.total_workers)
