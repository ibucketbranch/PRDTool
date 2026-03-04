#!/usr/bin/env python3
"""
Backfill script to populate file_modified_at for existing documents.
Reads the actual filesystem modification time (st_mtime) from each file
and updates the database.
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add parent directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

try:
    from supabase import create_client, Client
except ImportError:
    print("supabase not installed. Install with: pip install supabase")
    sys.exit(1)

# Default service role key for local Supabase
DEFAULT_SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

def get_supabase_client() -> Client:
    """Initialize Supabase client."""
    supabase_url = os.getenv('SUPABASE_URL', 'http://127.0.0.1:54421')
    supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY', DEFAULT_SUPABASE_KEY)
    return create_client(supabase_url, supabase_key)

def backfill_file_modified_at(dry_run: bool = True, batch_size: int = 100):
    """
    Backfill file_modified_at for all documents that don't have it.
    
    Args:
        dry_run: If True, only show what would be updated without making changes
        batch_size: Number of documents to process per batch
    """
    supabase = get_supabase_client()
    
    print("🔍 Fetching documents without file_modified_at...")
    
    # Fetch documents where file_modified_at is NULL
    offset = 0
    total_updated = 0
    total_skipped = 0
    total_errors = 0
    
    while True:
        # Fetch batch of documents
        response = supabase.table('documents')\
            .select('id, current_path, file_name, file_modified_at')\
            .is_('file_modified_at', 'null')\
            .range(offset, offset + batch_size - 1)\
            .execute()
        
        if not response.data:
            break
        
        print(f"\n📦 Processing batch {offset // batch_size + 1} ({len(response.data)} documents)...")
        
        for doc in response.data:
            doc_id = doc['id']
            current_path = doc['current_path']
            file_name = doc.get('file_name', 'unknown')
            
            # Check if file exists
            if not os.path.exists(current_path):
                print(f"  ⚠️  File not found: {file_name} ({current_path})")
                total_skipped += 1
                continue
            
            try:
                # Get filesystem modification time
                file_stat = os.stat(current_path)
                file_modified_at = datetime.fromtimestamp(file_stat.st_mtime).isoformat()
                
                if dry_run:
                    print(f"  ✓ Would update: {file_name}")
                    print(f"    Modified: {file_modified_at}")
                    total_updated += 1
                else:
                    # Update the database
                    supabase.table('documents')\
                        .update({'file_modified_at': file_modified_at})\
                        .eq('id', doc_id)\
                        .execute()
                    print(f"  ✓ Updated: {file_name} → {file_modified_at}")
                    total_updated += 1
                    
            except Exception as e:
                print(f"  ❌ Error processing {file_name}: {e}")
                total_errors += 1
        
        offset += batch_size
        
        if len(response.data) < batch_size:
            break
    
    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"  ✓ Updated: {total_updated}")
    print(f"  ⚠️  Skipped (file not found): {total_skipped}")
    print(f"  ❌ Errors: {total_errors}")
    
    if dry_run:
        print(f"\n⚠️  DRY RUN - No changes made. Run with --execute to apply changes.")
    else:
        print(f"\n✅ Backfill complete!")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Backfill file_modified_at for existing documents"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually update the database (default is dry-run)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of documents to process per batch (default: 100)"
    )
    
    args = parser.parse_args()
    
    dry_run = not args.execute
    
    if dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")
        print("   Run with --execute to apply updates\n")
    else:
        print("⚠️  EXECUTE MODE - Database will be updated\n")
        response = input("Are you sure? (yes/no): ")
        if response.lower() != 'yes':
            print("Cancelled.")
            sys.exit(0)
    
    backfill_file_modified_at(dry_run=dry_run, batch_size=args.batch_size)
