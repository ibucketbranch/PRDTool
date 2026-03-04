#!/usr/bin/env python3
"""
Process Discovered PDFs - Deduplicate and batch process 16K discovered PDFs
Uses existing batch_processor infrastructure for safe, incremental processing.
"""

import os
import sys
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set
from collections import defaultdict

try:
    from batch_processor import BatchFolderProcessor
    from document_processor import DocumentProcessor
except ImportError:
    print("Error: Required modules not found")
    sys.exit(1)

try:
    from notification_service import notify_system_status
except ImportError:
    def notify_system_status(*args, **kwargs): pass


class DiscoveredPDFProcessor:
    """
    Process the 16K discovered PDFs with deduplication.
    """
    
    def __init__(self, pdf_list_file: str, batch_size: int = 50):
        """
        Initialize processor.
        
        Args:
            pdf_list_file: Path to text file with PDF paths (one per line)
            batch_size: Number of files to process per batch
        """
        self.pdf_list_file = Path(pdf_list_file)
        self.batch_size = batch_size
        
        # Progress tracking
        self.progress_file = Path.home() / '.document_system' / 'discovered_pdfs_progress.json'
        self.progress_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Deduplication cache
        self.dedup_cache_file = Path.home() / '.document_system' / 'discovered_pdfs_hashes.json'
        
        # Load progress and hashes
        self.progress = self._load_progress()
        self.seen_hashes = self._load_hash_cache()
        
        # Initialize document processor
        self.doc_processor = DocumentProcessor()
        
        print("🚀 Discovered PDF Processor initialized")
        print(f"   Batch size: {batch_size}")
        print(f"   Progress file: {self.progress_file}")
        print(f"   Already processed: {len(self.progress.get('processed_files', []))}")
        print(f"   Known hashes: {len(self.seen_hashes)}")
        print()
    
    def _load_progress(self) -> Dict:
        """Load progress from file."""
        if self.progress_file.exists():
            with open(self.progress_file, 'r') as f:
                return json.load(f)
        return {
            'processed_files': [],
            'skipped_duplicates': [],
            'failed_files': [],
            'total_processed': 0,
            'total_duplicates': 0,
            'total_errors': 0,
            'started_at': datetime.now().isoformat(),
            'last_batch': None
        }
    
    def _save_progress(self):
        """Save progress to file."""
        self.progress['last_batch'] = datetime.now().isoformat()
        with open(self.progress_file, 'w') as f:
            json.dump(self.progress, f, indent=2)
    
    def _load_hash_cache(self) -> Dict[str, str]:
        """Load hash cache (hash -> first_path)."""
        if self.dedup_cache_file.exists():
            with open(self.dedup_cache_file, 'r') as f:
                return json.load(f)
        return {}
    
    def _save_hash_cache(self):
        """Save hash cache."""
        with open(self.dedup_cache_file, 'w') as f:
            json.dump(self.seen_hashes, f, indent=2)
    
    def _calculate_hash(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of file."""
        h = hashlib.sha256()
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(1024*1024), b''):
                    h.update(chunk)
            return h.hexdigest()
        except Exception as e:
            print(f"   ⚠️  Hash error for {file_path}: {e}")
            return None
    
    def load_pdf_list(self) -> List[str]:
        """Load PDF paths from text file."""
        if not self.pdf_list_file.exists():
            print(f"❌ PDF list file not found: {self.pdf_list_file}")
            sys.exit(1)
        
        with open(self.pdf_list_file, 'r', encoding='utf-8') as f:
            paths = [line.strip() for line in f if line.strip()]
        
        print(f"📋 Loaded {len(paths)} PDF paths from {self.pdf_list_file.name}")
        return paths
    
    def filter_and_deduplicate(self, pdf_paths: List[str]) -> List[str]:
        """
        Filter out already processed and duplicate files.
        
        Returns:
            List of unique PDF paths to process
        """
        print("\n🔍 Filtering and deduplicating...")
        
        processed_set = set(self.progress.get('processed_files', []))
        skipped_set = set(self.progress.get('skipped_duplicates', []))
        failed_set = set(self.progress.get('failed_files', []))
        
        to_process = []
        stats = {
            'total': len(pdf_paths),
            'already_processed': 0,
            'already_skipped': 0,
            'new_duplicates': 0,
            'to_process': 0
        }
        
        for i, path_str in enumerate(pdf_paths, 1):
            if i % 1000 == 0:
                print(f"   Checking {i}/{len(pdf_paths)}...", end='\r')
            
            path = Path(path_str)
            
            # Skip if already processed or skipped
            if path_str in processed_set:
                stats['already_processed'] += 1
                continue
            
            if path_str in skipped_set:
                stats['already_skipped'] += 1
                continue
            
            # Skip if file doesn't exist
            if not path.exists():
                continue
            
            # Calculate hash for deduplication
            file_hash = self._calculate_hash(path)
            if file_hash is None:
                continue
            
            # Check if we've seen this hash before
            if file_hash in self.seen_hashes:
                # This is a duplicate
                stats['new_duplicates'] += 1
                self.progress['skipped_duplicates'].append(path_str)
                continue
            
            # This is a unique file to process
            self.seen_hashes[file_hash] = path_str
            to_process.append(path_str)
            stats['to_process'] += 1
        
        print(f"\n✅ Filtering complete:")
        print(f"   Total PDFs: {stats['total']}")
        print(f"   Already processed: {stats['already_processed']}")
        print(f"   Already skipped: {stats['already_skipped']}")
        print(f"   New duplicates found: {stats['new_duplicates']}")
        print(f"   Unique files to process: {stats['to_process']}")
        print()
        
        # Save hash cache
        self._save_hash_cache()
        
        return to_process
    
    def process_batch(self, pdf_paths: List[str], batch_num: int) -> Dict:
        """
        Process a batch of PDFs.
        
        Returns:
            Stats dict with success/error counts
        """
        stats = {
            'success': 0,
            'errors': 0,
            'error_details': []
        }
        
        print(f"\n📦 Processing batch {batch_num} ({len(pdf_paths)} files)...")
        
        for i, path_str in enumerate(pdf_paths, 1):
            path = Path(path_str)
            
            print(f"   [{i}/{len(pdf_paths)}] {path.name}")
            
            try:
                # Process the PDF
                result = self.doc_processor.process_document(str(path))
                
                if result and result.get('success'):
                    stats['success'] += 1
                    self.progress['processed_files'].append(path_str)
                    self.progress['total_processed'] += 1
                    print(f"      ✅ Success - ID: {result.get('document_id')}")
                else:
                    stats['errors'] += 1
                    self.progress['failed_files'].append(path_str)
                    self.progress['total_errors'] += 1
                    error_msg = result.get('error', 'Unknown error') if result else 'No result'
                    stats['error_details'].append({'path': path_str, 'error': error_msg})
                    print(f"      ❌ Failed: {error_msg}")
                    
            except Exception as e:
                stats['errors'] += 1
                self.progress['failed_files'].append(path_str)
                self.progress['total_errors'] += 1
                stats['error_details'].append({'path': path_str, 'error': str(e)})
                print(f"      ❌ Exception: {e}")
        
        # Save progress after each batch
        self._save_progress()
        
        return stats
    
    def run(self, max_batches: int = None):
        """
        Run the full processing pipeline.
        
        Args:
            max_batches: Maximum number of batches to process (None = all)
        """
        print("=" * 70)
        print("DISCOVERED PDF PROCESSOR")
        print("=" * 70)
        print()
        
        # Load PDF list
        pdf_paths = self.load_pdf_list()
        
        # Filter and deduplicate
        unique_paths = self.filter_and_deduplicate(pdf_paths)
        
        if not unique_paths:
            print("✅ All PDFs already processed!")
            print()
            self._print_final_stats()
            return
        
        # Split into batches
        batches = []
        for i in range(0, len(unique_paths), self.batch_size):
            batches.append(unique_paths[i:i + self.batch_size])
        
        total_batches = len(batches)
        if max_batches:
            batches = batches[:max_batches]
        
        print(f"📊 Processing plan:")
        print(f"   Total batches: {total_batches}")
        print(f"   Batch size: {self.batch_size}")
        print(f"   Batches to process now: {len(batches)}")
        print()
        
        # Notify start
        notify_system_status(
            f"Starting batch processing of {len(unique_paths)} PDFs",
            f"{len(batches)} batches to process"
        )
        
        # Process batches
        overall_stats = {
            'total_success': 0,
            'total_errors': 0,
            'batches_completed': 0
        }
        
        for batch_num, batch_paths in enumerate(batches, 1):
            batch_stats = self.process_batch(batch_paths, batch_num)
            
            overall_stats['total_success'] += batch_stats['success']
            overall_stats['total_errors'] += batch_stats['errors']
            overall_stats['batches_completed'] += 1
            
            print(f"\n   Batch {batch_num} complete:")
            print(f"   ✅ Success: {batch_stats['success']}")
            print(f"   ❌ Errors: {batch_stats['errors']}")
            print()
            
            # Save progress
            self._save_progress()
        
        # Final summary
        print("\n" + "=" * 70)
        print("PROCESSING COMPLETE")
        print("=" * 70)
        self._print_final_stats()
        
        # Notify completion
        notify_system_status(
            f"Batch processing complete",
            f"Processed {overall_stats['total_success']} files, {overall_stats['total_errors']} errors"
        )
    
    def _print_final_stats(self):
        """Print final statistics."""
        print()
        print("📊 Final Statistics:")
        print(f"   Total processed: {self.progress['total_processed']}")
        print(f"   Total duplicates skipped: {len(self.progress.get('skipped_duplicates', []))}")
        print(f"   Total errors: {self.progress['total_errors']}")
        print(f"   Started: {self.progress.get('started_at', 'Unknown')}")
        print(f"   Last batch: {self.progress.get('last_batch', 'Unknown')}")
        print()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Process discovered PDFs with deduplication')
    parser.add_argument('pdf_list', help='Path to text file with PDF paths (one per line)')
    parser.add_argument('--batch-size', type=int, default=50, help='Number of files per batch (default: 50)')
    parser.add_argument('--max-batches', type=int, default=None, help='Maximum number of batches to process')
    parser.add_argument('--reset', action='store_true', help='Reset progress and start fresh')
    
    args = parser.parse_args()
    
    # Reset if requested
    if args.reset:
        progress_file = Path.home() / '.document_system' / 'discovered_pdfs_progress.json'
        hash_cache = Path.home() / '.document_system' / 'discovered_pdfs_hashes.json'
        if progress_file.exists():
            progress_file.unlink()
            print("✅ Progress reset")
        if hash_cache.exists():
            hash_cache.unlink()
            print("✅ Hash cache reset")
        print()
    
    # Create processor and run
    processor = DiscoveredPDFProcessor(args.pdf_list, batch_size=args.batch_size)
    processor.run(max_batches=args.max_batches)


if __name__ == "__main__":
    main()
