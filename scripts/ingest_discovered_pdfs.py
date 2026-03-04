#!/usr/bin/env python3
"""
Simple PDF Ingester - Just extract text and hash, no AI processing
This will populate the database so PDFs are searchable, AI summaries can be added later.
"""

import os
import sys
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List
from collections import defaultdict

try:
    from PyPDF2 import PdfReader
except ImportError:
    print("PyPDF2 not installed. Install with: pip install PyPDF2")
    sys.exit(1)

try:
    from supabase import create_client, Client
except ImportError:
    print("supabase not installed. Install with: pip install supabase")
    sys.exit(1)


class SimplePDFIngester:
    """
    Ingest PDFs into database with basic metadata and text extraction.
    No AI processing - that can be added later.
    """
    
    def __init__(self, pdf_list_file: str, batch_size: int = 50,
                 supabase_url: str = "http://127.0.0.1:54421",
                 supabase_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY")):
        """Initialize ingester."""
        self.pdf_list_file = Path(pdf_list_file)
        self.batch_size = batch_size
        
        # Supabase client
        self.supabase: Client = create_client(supabase_url, supabase_key)
        
        # Progress tracking
        self.progress_file = Path.home() / '.document_system' / 'simple_ingest_progress.json'
        self.progress_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Deduplication cache
        self.dedup_cache_file = Path.home() / '.document_system' / 'simple_ingest_hashes.json'
        
        # Load progress and hashes
        self.progress = self._load_progress()
        self.seen_hashes = self._load_hash_cache()
        
        print("🚀 Simple PDF Ingester initialized")
        print(f"   Batch size: {batch_size}")
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
    
    def _extract_text(self, file_path: Path) -> str:
        """Extract text from PDF."""
        try:
            reader = PdfReader(str(file_path))
            text_parts = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            return "\n\n".join(text_parts)
        except Exception as e:
            print(f"   ⚠️  Text extraction error: {e}")
            return ""
    
    def _check_if_exists(self, file_hash: str) -> bool:
        """Check if document with this hash already exists in database."""
        try:
            resp = self.supabase.table('documents').select('id').eq('file_hash', file_hash).limit(1).execute()
            return len(resp.data) > 0
        except Exception as e:
            print(f"   ⚠️  DB check error: {e}")
            return False
    
    def _insert_document(self, file_path: Path, file_hash: str, extracted_text: str) -> bool:
        """Insert document into database."""
        try:
            # Get file stats
            stat = file_path.stat()
            
            # Prepare document data
            doc_data = {
                'file_name': file_path.name,
                'current_path': str(file_path),
                'file_size_bytes': stat.st_size,
                'file_hash': file_hash,
                'file_type': 'pdf',
                'document_mode': 'document',  # Required field
                'is_conversation': False,
                'extracted_text': extracted_text[:100000] if extracted_text else None,  # Limit size
                'text_preview': extracted_text[:500] if extracted_text else None,
                'processing_status': 'extracted',  # No AI processing yet
            }
            
            # Insert into database
            resp = self.supabase.table('documents').insert(doc_data).execute()
            
            if resp.data:
                return resp.data[0]['id']
            return None
            
        except Exception as e:
            print(f"   ❌ DB insert error: {e}")
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
        """Filter out already processed and duplicate files."""
        print("\n🔍 Filtering and deduplicating...")
        
        processed_set = set(self.progress.get('processed_files', []))
        skipped_set = set(self.progress.get('skipped_duplicates', []))
        
        to_process = []
        stats = {
            'total': len(pdf_paths),
            'already_processed': 0,
            'already_skipped': 0,
            'new_duplicates': 0,
            'missing_files': 0,
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
                stats['missing_files'] += 1
                continue
            
            # Calculate hash for deduplication
            file_hash = self._calculate_hash(path)
            if file_hash is None:
                continue
            
            # Check if we've seen this hash before (in our cache)
            if file_hash in self.seen_hashes:
                stats['new_duplicates'] += 1
                self.progress['skipped_duplicates'].append(path_str)
                continue
            
            # Check if already in database
            if self._check_if_exists(file_hash):
                stats['new_duplicates'] += 1
                self.seen_hashes[file_hash] = path_str
                self.progress['skipped_duplicates'].append(path_str)
                continue
            
            # This is a unique file to process
            self.seen_hashes[file_hash] = path_str
            to_process.append((path_str, file_hash))
            stats['to_process'] += 1
        
        print(f"\n✅ Filtering complete:")
        print(f"   Total PDFs: {stats['total']}")
        print(f"   Already processed: {stats['already_processed']}")
        print(f"   Already skipped: {stats['already_skipped']}")
        print(f"   Missing files: {stats['missing_files']}")
        print(f"   New duplicates found: {stats['new_duplicates']}")
        print(f"   Unique files to process: {stats['to_process']}")
        print()
        
        # Save hash cache
        self._save_hash_cache()
        
        return to_process
    
    def process_batch(self, pdf_items: List[tuple], batch_num: int) -> Dict:
        """Process a batch of PDFs."""
        stats = {
            'success': 0,
            'errors': 0,
            'error_details': []
        }
        
        print(f"\n📦 Processing batch {batch_num} ({len(pdf_items)} files)...")
        
        for i, (path_str, file_hash) in enumerate(pdf_items, 1):
            path = Path(path_str)
            
            print(f"   [{i}/{len(pdf_items)}] {path.name[:50]}...")
            
            try:
                # Extract text
                extracted_text = self._extract_text(path)
                
                # Insert into database
                doc_id = self._insert_document(path, file_hash, extracted_text)
                
                if doc_id:
                    stats['success'] += 1
                    self.progress['processed_files'].append(path_str)
                    self.progress['total_processed'] += 1
                    word_count = len(extracted_text.split()) if extracted_text else 0
                    print(f"      ✅ Success - ID: {doc_id} ({word_count} words)")
                else:
                    stats['errors'] += 1
                    self.progress['failed_files'].append(path_str)
                    self.progress['total_errors'] += 1
                    stats['error_details'].append({'path': path_str, 'error': 'Insert failed'})
                    print(f"      ❌ Failed to insert")
                    
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
        """Run the full ingestion pipeline."""
        print("=" * 70)
        print("SIMPLE PDF INGESTER")
        print("=" * 70)
        print()
        
        # Load PDF list
        pdf_paths = self.load_pdf_list()
        
        # Filter and deduplicate
        unique_items = self.filter_and_deduplicate(pdf_paths)
        
        if not unique_items:
            print("✅ All PDFs already processed!")
            print()
            self._print_final_stats()
            return
        
        # Split into batches
        batches = []
        for i in range(0, len(unique_items), self.batch_size):
            batches.append(unique_items[i:i + self.batch_size])
        
        total_batches = len(batches)
        if max_batches:
            batches = batches[:max_batches]
        
        print(f"📊 Processing plan:")
        print(f"   Total batches: {total_batches}")
        print(f"   Batch size: {self.batch_size}")
        print(f"   Batches to process now: {len(batches)}")
        print()
        
        # Process batches
        overall_stats = {
            'total_success': 0,
            'total_errors': 0,
            'batches_completed': 0
        }
        
        for batch_num, batch_items in enumerate(batches, 1):
            batch_stats = self.process_batch(batch_items, batch_num)
            
            overall_stats['total_success'] += batch_stats['success']
            overall_stats['total_errors'] += batch_stats['errors']
            overall_stats['batches_completed'] += 1
            
            print(f"\n   Batch {batch_num}/{len(batches)} complete:")
            print(f"   ✅ Success: {batch_stats['success']}")
            print(f"   ❌ Errors: {batch_stats['errors']}")
            
            if batch_num < len(batches):
                print(f"   📊 Progress: {overall_stats['total_success']}/{len(unique_items)} files")
            print()
        
        # Final summary
        print("\n" + "=" * 70)
        print("INGESTION COMPLETE")
        print("=" * 70)
        self._print_final_stats()
    
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
        print("💡 Note: AI processing (summaries, context bins) can be added later")
        print()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Simple PDF ingestion without AI processing')
    parser.add_argument('pdf_list', help='Path to text file with PDF paths (one per line)')
    parser.add_argument('--batch-size', type=int, default=50, help='Number of files per batch (default: 50)')
    parser.add_argument('--max-batches', type=int, default=None, help='Maximum number of batches to process')
    parser.add_argument('--reset', action='store_true', help='Reset progress and start fresh')
    
    args = parser.parse_args()
    
    # Reset if requested
    if args.reset:
        progress_file = Path.home() / '.document_system' / 'simple_ingest_progress.json'
        hash_cache = Path.home() / '.document_system' / 'simple_ingest_hashes.json'
        if progress_file.exists():
            progress_file.unlink()
            print("✅ Progress reset")
        if hash_cache.exists():
            hash_cache.unlink()
            print("✅ Hash cache reset")
        print()
    
    # Create ingester and run
    ingester = SimplePDFIngester(args.pdf_list, batch_size=args.batch_size)
    ingester.run(max_batches=args.max_batches)


if __name__ == "__main__":
    main()
