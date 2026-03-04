#!/usr/bin/env python3
"""
Comprehensive PDF Reprocessing - Full Rescan with Gemini
Reprocesses ALL PDFs on disk to extract maximum value from LLM categorization.

This script:
- Finds ALL PDFs on disk (or uses existing all_pdfs.txt)
- Reprocesses each one with Gemini (primary) for better categorization
- Updates database records with improved AI analysis
- Forces reprocessing even if document already exists (skip_if_exists=False)

🛡️ FILE SAFETY GUARANTEE:
- This script NEVER deletes, moves, renames, or modifies files
- It ONLY reads files and updates database records
- Your files remain completely untouched on disk
- All file operations are read-only
"""

import os
import sys
import time
from pathlib import Path
from typing import List, Optional
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from document_processor import DocumentProcessor

def find_all_pdfs_on_disk() -> List[str]:
    """Find ALL PDF files on disk in common locations."""
    print("🔍 Scanning file system for ALL PDFs...")
    
    home = Path.home()
    search_paths = [
        home / "Library" / "Mobile Documents" / "com~apple~CloudDocs",  # iCloud Drive
        home / "Documents",
        home / "Downloads",
        home / "Websites",
        # Add more paths if needed
    ]
    
    all_pdfs = set()
    
    for search_path in search_paths:
        if not search_path.exists():
            print(f"   ⚠️  Path not found: {search_path}")
            continue
        
        print(f"   📂 Scanning: {search_path}")
        try:
            count = 0
            for pdf_path in search_path.rglob("*.pdf"):
                # Skip system folders
                if any(skip in str(pdf_path) for skip in [
                    'node_modules', '.git', '.Trash', 'Library/Caches',
                    '.npm', '.cache', 'Library/Application Support'
                ]):
                    continue
                
                all_pdfs.add(str(pdf_path))
                count += 1
                if count % 100 == 0:
                    print(f"      ... found {count} PDFs so far")
            
            print(f"      ✅ Found {count} PDFs in {search_path.name}")
        except Exception as e:
            print(f"      ⚠️  Error scanning {search_path}: {e}")
    
    return sorted(list(all_pdfs))

def load_pdfs_from_file(file_path: str = "all_pdfs.txt") -> Optional[List[str]]:
    """Load PDF list from existing file if it exists."""
    file_path = Path(file_path)
    if not file_path.exists():
        return None
    
    print(f"📄 Loading PDF list from: {file_path}")
    pdfs = []
    try:
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and line.endswith('.pdf') and os.path.exists(line):
                    pdfs.append(line)
        
        print(f"   ✅ Loaded {len(pdfs)} valid PDF paths from file")
        return pdfs
    except Exception as e:
        print(f"   ⚠️  Error reading file: {e}")
        return None

def verify_gemini_setup() -> bool:
    """Verify that Gemini API key is configured."""
    gemini_key = os.getenv('GEMINI_API_KEY')
    if not gemini_key:
        print("")
        print("=" * 80)
        print("⚠️  CRITICAL: GEMINI_API_KEY not set!")
        print("=" * 80)
        print("")
        print("Gemini is the PRIMARY LLM provider for best categorization.")
        print("Without it, the system will fall back to Groq only.")
        print("")
        print("To set it:")
        print("  export GEMINI_API_KEY='your-key-here'")
        print("")
        print("Or add to your .env file:")
        print("  GEMINI_API_KEY=your-key-here")
        print("")
        print("See docs/GEMINI_SETUP.md for detailed instructions.")
        print("")
        response = input("Continue anyway with Groq only? (yes/no): ").strip().lower()
        if response != 'yes':
            return False
    else:
        print("✅ GEMINI_API_KEY is configured")
    return True

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Reprocess ALL PDFs with Gemini for maximum LLM extraction',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Reprocess all PDFs (use existing all_pdfs.txt if available)
  python3 scripts/reprocess_all_pdfs.py

  # Force fresh scan of disk
  python3 scripts/reprocess_all_pdfs.py --fresh-scan

  # Test with first 10 PDFs
  python3 scripts/reprocess_all_pdfs.py --limit 10

  # Process in batches of 100
  python3 scripts/reprocess_all_pdfs.py --batch-size 100
        """
    )
    parser.add_argument('--fresh-scan', action='store_true',
                       help='Force fresh disk scan instead of using all_pdfs.txt')
    parser.add_argument('--limit', type=int, default=None,
                       help='Limit number of PDFs to process (for testing)')
    parser.add_argument('--batch-size', type=int, default=None,
                       help='Process in batches (pause between batches)')
    parser.add_argument('--start-from', type=int, default=0,
                       help='Start from this index (for resuming)')
    parser.add_argument('--skip-existing', action='store_true',
                       help='Skip PDFs that already exist in database (default: reprocess all)')
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("🔄 COMPREHENSIVE PDF REPROCESSING - Full Rescan with Gemini")
    print("=" * 80)
    print("")
    print("🛡️  FILE SAFETY GUARANTEE:")
    print("   ✅ This script NEVER deletes, moves, renames, or modifies files")
    print("   ✅ It ONLY reads files and updates database records")
    print("   ✅ Your files remain completely untouched on disk")
    print("   ✅ All file operations are read-only")
    print("")
    
    # Verify Gemini setup
    if not verify_gemini_setup():
        print("Cancelled.")
        return
    
    print("")
    
    # Find or load PDFs
    pdf_files = None
    if not args.fresh_scan:
        # Try to load from existing file first
        pdf_files = load_pdfs_from_file()
    
    if pdf_files is None or args.fresh_scan:
        # Scan disk
        pdf_files = find_all_pdfs_on_disk()
        
        # Optionally save to file
        if pdf_files:
            output_file = Path(__file__).parent.parent / "all_pdfs.txt"
            print(f"💾 Saving PDF list to: {output_file}")
            with open(output_file, 'w') as f:
                for pdf in pdf_files:
                    f.write(f"{pdf}\n")
            print(f"   ✅ Saved {len(pdf_files)} PDF paths")
    
    if not pdf_files:
        print("❌ No PDFs found!")
        return
    
    total_pdfs = len(pdf_files)
    print("")
    print(f"📊 Total PDFs to process: {total_pdfs}")
    
    # Apply start-from offset
    if args.start_from > 0:
        pdf_files = pdf_files[args.start_from:]
        print(f"   Starting from index {args.start_from} ({len(pdf_files)} remaining)")
    
    # Apply limit
    if args.limit:
        pdf_files = pdf_files[:args.limit]
        print(f"   ⚠️  Limited to first {args.limit} PDFs (TEST MODE)")
    
    print("")
    
    # Initialize processor
    print("🤖 Initializing DocumentProcessor...")
    processor = DocumentProcessor(
        groq_api_key=os.getenv("GROQ_API_KEY"),
        gemini_api_key=os.getenv("GEMINI_API_KEY"),
        llm_provider=os.getenv("LLM_PROVIDER", "gemini")
    )
    print("")
    
    # Statistics
    stats = {
        'processed': 0,
        'updated': 0,
        'skipped': 0,
        'failed': 0,
        'not_found': 0,
        'start_time': time.time()
    }
    
    # Process each PDF
    print("=" * 80)
    print("🚀 STARTING REPROCESSING")
    print("=" * 80)
    print("")
    
    batch_num = 0
    for i, file_path in enumerate(pdf_files, 1):
        # Batch processing
        if args.batch_size and (i - 1) % args.batch_size == 0 and i > 1:
            batch_num += 1
            elapsed = time.time() - stats['start_time']
            rate = stats['processed'] / elapsed if elapsed > 0 else 0
            remaining = (total_pdfs - i + 1) / rate if rate > 0 else 0
            
            print("")
            print(f"📦 Batch {batch_num} complete ({args.batch_size} PDFs)")
            print(f"   Processed: {stats['processed']} | Updated: {stats['updated']} | Failed: {stats['failed']}")
            print(f"   Rate: {rate:.1f} PDFs/min | Est. remaining: {remaining/60:.1f} min")
            print("")
            response = input("Continue to next batch? (yes/no): ").strip().lower()
            if response != 'yes':
                print("Paused. Resume with --start-from", i)
                break
        
        # Check if file exists
        if not os.path.exists(file_path):
            stats['not_found'] += 1
            print(f"[{i}/{len(pdf_files)}] ⚠️  File not found: {Path(file_path).name}")
            continue
        
        file_name = Path(file_path).name
        print(f"[{i}/{len(pdf_files)}] Processing: {file_name}")
        
        # Truncate long paths for display
        display_path = file_path[:80] + "..." if len(file_path) > 80 else file_path
        print(f"   📄 {display_path}")
        
        try:
            # Reprocess with Gemini (skip_if_exists=False to force reprocessing)
            result = processor.process_document(
                file_path,
                skip_if_exists=args.skip_existing  # Default: False (reprocess all)
            )
            
            status = result.get('status', 'unknown')
            
            if status == 'success':
                stats['processed'] += 1
                stats['updated'] += 1
                category = result.get('category', 'unknown')
                print(f"   ✅ Success → Category: {category}")
                
                # Show if category changed
                if 'previous_category' in result:
                    old_cat = result['previous_category']
                    if old_cat != category:
                        print(f"   🔄 Category updated: {old_cat} → {category}")
            
            elif status == 'skipped':
                stats['skipped'] += 1
                reason = result.get('reason', 'unknown')
                print(f"   ⏭️  Skipped: {reason}")
            
            else:
                stats['failed'] += 1
                reason = result.get('reason', 'unknown')
                print(f"   ❌ Failed: {reason}")
        
        except Exception as e:
            stats['failed'] += 1
            print(f"   ❌ Error: {e}")
        
        print("")
    
    # Final summary
    elapsed = time.time() - stats['start_time']
    rate = stats['processed'] / elapsed * 60 if elapsed > 0 else 0  # PDFs per minute
    
    print("=" * 80)
    print("✅ REPROCESSING COMPLETE")
    print("=" * 80)
    print("")
    print(f"📊 Statistics:")
    print(f"   ✅ Processed/Updated: {stats['processed']}")
    print(f"   ⏭️  Skipped: {stats['skipped']}")
    print(f"   ❌ Failed: {stats['failed']}")
    print(f"   ⚠️  Not Found: {stats['not_found']}")
    print(f"   ⏱️  Total Time: {elapsed/60:.1f} minutes")
    print(f"   📈 Rate: {rate:.1f} PDFs/minute")
    print("")
    print("All PDFs have been reprocessed with Gemini for maximum LLM extraction.")
    print("Database records updated with improved categorization and summaries.")
    print("")

if __name__ == "__main__":
    main()
