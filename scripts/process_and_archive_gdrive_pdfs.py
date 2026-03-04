#!/usr/bin/env python3
"""
Process and Archive Google Drive PDFs
Processes new PDFs from Google Drive, then moves them to archive folder after successful processing.
"""

import os
import sys
import shutil
from pathlib import Path
from typing import Dict, List

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from supabase import create_client, Client
except ImportError:
    print("Error: supabase not installed. Install with: pip install supabase")
    sys.exit(1)

try:
    from document_processor import DocumentProcessor
except ImportError:
    print("Error: document_processor not found")
    sys.exit(1)

# Import the checker to reuse discovery logic
import importlib.util
spec = importlib.util.spec_from_file_location(
    "check_and_process_gdrive_pdfs",
    Path(__file__).parent / "check_and_process_gdrive_pdfs.py"
)
check_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_module)
GoogleDrivePDFChecker = check_module.GoogleDrivePDFChecker


class ProcessAndArchiveGDrivePDFs:
    """
    Process new Google Drive PDFs and archive them after successful processing.
    """
    
    def __init__(self, 
                 gdrive_path: str = "/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive",
                 archive_folder: str = "Archived_PDFs_Processed",
                 supabase_url: str = "http://127.0.0.1:54421",
                 supabase_key: str = None):
        """Initialize processor."""
        self.gdrive_path = Path(gdrive_path)
        self.archive_path = self.gdrive_path / archive_folder
        supabase_key = supabase_key or os.getenv('SUPABASE_SERVICE_ROLE_KEY')
        self.supabase: Client = create_client(supabase_url, supabase_key)
        self.doc_processor = DocumentProcessor()
        self.checker = GoogleDrivePDFChecker(gdrive_path=gdrive_path)
        
        print("🚀 Process and Archive Google Drive PDFs")
        print(f"   Google Drive path: {self.gdrive_path}")
        print(f"   Archive folder: {self.archive_path}")
        print()
    
    def process_and_archive(self, dry_run: bool = False) -> Dict:
        """
        Process new PDFs and archive them after successful processing.
        
        Args:
            dry_run: If True, only show what would be done without actually processing/archiving
        
        Returns:
            Report dictionary with statistics
        """
        print("=" * 80)
        if dry_run:
            print("🔍 DRY RUN - Process and Archive Preview")
        else:
            print("📦 PROCESS AND ARCHIVE NEW GOOGLE DRIVE PDFs")
        print("=" * 80)
        print()
        
        # Step 1: Discover PDFs
        pdfs = self.checker.discover_pdfs()
        
        if not pdfs:
            print("❌ No PDFs found in Google Drive")
            return {'processed': [], 'archived': [], 'failed': []}
        
        # Step 2: Identify PDFs not in database
        print("🔍 Identifying PDFs not in database...")
        print()
        
        not_in_db = []
        for pdf_path in pdfs:
            # Skip files already in archive
            if 'Archived_PDFs_Processed' in str(pdf_path):
                continue
            
            # Calculate hash and check database
            file_hash = self.checker.calculate_file_hash(pdf_path)
            if not file_hash:
                continue
            
            existing_doc = self.checker.check_if_exists_in_db(file_hash)
            if not existing_doc:
                not_in_db.append(pdf_path)
        
        print(f"✅ Found {len(not_in_db)} PDFs not in database")
        print()
        
        if not not_in_db:
            print("✅ All PDFs already processed!")
            return {'processed': [], 'archived': [], 'failed': []}
        
        # Step 3: Process PDFs
        print("=" * 80)
        print("📄 STEP 1: PROCESSING PDFs")
        print("=" * 80)
        print()
        
        report = {
            'total': len(not_in_db),
            'processed': [],
            'failed': [],
            'archived': [],
            'archive_failed': []
        }
        
        for i, pdf_path in enumerate(not_in_db, 1):
            print(f"\n[{i}/{len(not_in_db)}] Processing: {pdf_path.name}")
            print(f"   📍 Google Drive path: {pdf_path}")
            
            if dry_run:
                report['processed'].append({
                    'path': str(pdf_path),
                    'name': pdf_path.name,
                    'status': 'would_process'
                })
                print(f"   ✅ Would process")
                continue
            
            try:
                result = self.doc_processor.process_document(str(pdf_path), skip_if_exists=False)
                
                if result and result.get('status') == 'success':
                    document_id = result.get('document_id')
                    
                    # Ensure Google Drive path is recorded with notes
                    try:
                        loc_check = self.supabase.table('document_locations')\
                            .select('id')\
                            .eq('document_id', document_id)\
                            .eq('location_type', 'original')\
                            .execute()
                        
                        if loc_check.data:
                            self.supabase.table('document_locations')\
                                .update({
                                    'notes': f'Original Google Drive location - Source: Google Drive processing. File: {pdf_path.name}'
                                })\
                                .eq('id', loc_check.data[0]['id'])\
                                .execute()
                            print(f"   ✅ Google Drive path recorded with source notes")
                    except Exception as loc_err:
                        print(f"   ⚠️  Note: Could not update location notes: {loc_err}")
                    
                    report['processed'].append({
                        'path': str(pdf_path),
                        'name': pdf_path.name,
                        'document_id': document_id,
                        'status': 'processed'
                    })
                    print(f"   ✅ Successfully processed (ID: {document_id})")
                else:
                    error_msg = result.get('error', 'Unknown error') if result else 'No result'
                    report['failed'].append({
                        'path': str(pdf_path),
                        'name': pdf_path.name,
                        'error': error_msg
                    })
                    print(f"   ❌ Failed: {error_msg}")
                    
            except Exception as e:
                report['failed'].append({
                    'path': str(pdf_path),
                    'name': pdf_path.name,
                    'error': str(e)
                })
                print(f"   ❌ Exception: {e}")
        
        print(f"\n✅ Processing complete!")
        print(f"   Processed: {len(report['processed'])}")
        print(f"   Failed: {len(report['failed'])}")
        print()
        
        # Step 4: Archive successfully processed PDFs
        if report['processed']:
            print("=" * 80)
            print("📦 STEP 2: ARCHIVING PROCESSED PDFs")
            print("=" * 80)
            print()
            
            # Create archive folder
            if not dry_run:
                self.archive_path.mkdir(parents=True, exist_ok=True)
                print(f"✅ Archive folder ready: {self.archive_path}")
            else:
                print(f"📁 Archive folder would be: {self.archive_path}")
            print()
            
            print(f"Archiving {len(report['processed'])} successfully processed PDFs...")
            print()
            
            for i, item in enumerate(report['processed'], 1):
                pdf_path = Path(item['path'])
                
                if i % 10 == 0:
                    print(f"   Progress: {i}/{len(report['processed'])}...", end='\r')
                
                try:
                    # Determine destination path (preserve relative structure)
                    relative_path = pdf_path.relative_to(self.gdrive_path)
                    archive_dest = self.archive_path / relative_path
                    
                    # Create parent directories
                    archive_dest.parent.mkdir(parents=True, exist_ok=True)
                    
                    if dry_run:
                        report['archived'].append({
                            'source': str(pdf_path),
                            'destination': str(archive_dest),
                            'status': 'would_archive'
                        })
                    else:
                        # Move file to archive
                        shutil.move(str(pdf_path), str(archive_dest))
                        report['archived'].append({
                            'source': str(pdf_path),
                            'destination': str(archive_dest),
                            'status': 'archived'
                        })
                
                except Exception as e:
                    report['archive_failed'].append({
                        'path': str(pdf_path),
                        'error': str(e)
                    })
                    print(f"\n   ⚠️  Error archiving {pdf_path.name}: {e}")
            
            print(f"\n   ✅ Archive complete!")
            print()
        
        # Print final report
        self._print_report(report, dry_run)
        
        return report
    
    def _print_report(self, report: Dict, dry_run: bool = False):
        """Print formatted report."""
        print("=" * 80)
        if dry_run:
            print("🔍 DRY RUN REPORT")
        else:
            print("📊 FINAL REPORT")
        print("=" * 80)
        print()
        print(f"Total PDFs found:         {report['total']}")
        if dry_run:
            print(f"Would process:            {len(report['processed'])}")
            print(f"Would archive:            {len(report['archived'])}")
        else:
            print(f"✅ Processed:              {len(report['processed'])}")
            print(f"✅ Archived:               {len(report['archived'])}")
        print(f"❌ Processing failed:      {len(report['failed'])}")
        print(f"❌ Archiving failed:       {len(report['archive_failed'])}")
        print()
        print("=" * 80)
        
        if report['processed']:
            print(f"\n{'Would process' if dry_run else 'Processed'} ({len(report['processed'])}):")
            print("-" * 80)
            for item in report['processed'][:10]:
                print(f"  ✅ {item['name']}")
                if 'document_id' in item:
                    print(f"     ID: {item['document_id']}")
                print(f"     Path: {item['path']}")
                print()
            if len(report['processed']) > 10:
                print(f"     ... and {len(report['processed']) - 10} more")
                print()
        
        if report['archived']:
            print(f"\n{'Would archive' if dry_run else 'Archived'} ({len(report['archived'])}):")
            print("-" * 80)
            for item in report['archived'][:10]:
                print(f"  ✅ {Path(item['source']).name}")
                print(f"     From: {item['source']}")
                print(f"     To:   {item['destination']}")
                print()
            if len(report['archived']) > 10:
                print(f"     ... and {len(report['archived']) - 10} more")
                print()
        
        if report['failed']:
            print(f"\n❌ Processing Failed ({len(report['failed'])}):")
            print("-" * 80)
            for item in report['failed'][:10]:
                print(f"  ❌ {item['name']}")
                print(f"     Error: {item['error']}")
                print()
            if len(report['failed']) > 10:
                print(f"     ... and {len(report['failed']) - 10} more")
                print()
        
        if report['archive_failed']:
            print(f"\n❌ Archiving Failed ({len(report['archive_failed'])}):")
            print("-" * 80)
            for item in report['archive_failed'][:10]:
                print(f"  ❌ {Path(item['path']).name}")
                print(f"     Error: {item['error']}")
                print()
            if len(report['archive_failed']) > 10:
                print(f"     ... and {len(report['archive_failed']) - 10} more")
                print()
        
        print("=" * 80)
        print()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Process new Google Drive PDFs and archive them after successful processing'
    )
    parser.add_argument(
        '--gdrive-path',
        type=str,
        default="/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive",
        help='Path to Google Drive root (default: standard macOS path)'
    )
    parser.add_argument(
        '--archive-folder',
        type=str,
        default="Archived_PDFs_Processed",
        help='Name of archive folder (default: Archived_PDFs_Processed)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview what would be processed and archived without actually doing it'
    )
    parser.add_argument(
        '--yes',
        action='store_true',
        help='Skip confirmation prompt and proceed'
    )
    
    args = parser.parse_args()
    
    # Create processor
    processor = ProcessAndArchiveGDrivePDFs(
        gdrive_path=args.gdrive_path,
        archive_folder=args.archive_folder
    )
    
    # Confirm action
    if not args.dry_run and not args.yes:
        print("=" * 80)
        print("⚠️  WARNING: This will process PDFs and move them to archive")
        print("=" * 80)
        print("   This will:")
        print("   1. Process new PDFs (extract text, AI analysis, database storage)")
        print("   2. Move successfully processed PDFs to archive folder")
        print()
        response = input("   Continue? (yes/no): ").strip().lower()
        if response != 'yes':
            print("   Cancelled.")
            return
        print()
    elif args.yes and not args.dry_run:
        print("=" * 80)
        print("⚠️  Processing and archiving (--yes flag used)")
        print("=" * 80)
        print()
    
    # Process and archive
    report = processor.process_and_archive(dry_run=args.dry_run)
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)
    print(f"Total found:         {report['total']}")
    if args.dry_run:
        print(f"Would process:        {len(report['processed'])}")
        print(f"Would archive:        {len(report['archived'])}")
    else:
        print(f"Processed:            {len(report['processed'])}")
        print(f"Archived:             {len(report['archived'])}")
    print(f"Processing failed:    {len(report['failed'])}")
    print(f"Archiving failed:     {len(report['archive_failed'])}")
    print("=" * 80)
    print()


if __name__ == "__main__":
    main()
