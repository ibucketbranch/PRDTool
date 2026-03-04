#!/usr/bin/env python3
"""
Check and Process Google Drive PDFs
Discovers PDFs in Google Drive, checks against database, reports findings, and processes new ones.
"""

import os
import sys
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

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


class GoogleDrivePDFChecker:
    """
    Check Google Drive PDFs against database and process new ones.
    """
    
    def __init__(self, 
                 gdrive_path: str = "/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive",
                 supabase_url: str = "http://127.0.0.1:54421",
                 supabase_key: Optional[str] = None):
        """Initialize checker."""
        self.gdrive_path = Path(gdrive_path)
        supabase_key = supabase_key or os.getenv('SUPABASE_SERVICE_ROLE_KEY')
        self.supabase: Client = create_client(supabase_url, supabase_key)
        self.doc_processor = DocumentProcessor()
        
        print("🚀 Google Drive PDF Checker initialized")
        print(f"   Google Drive path: {self.gdrive_path}")
        print()
    
    def calculate_file_hash(self, file_path: Path) -> Optional[str]:
        """Calculate SHA256 hash of file."""
        sha256_hash = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception as e:
            print(f"   ⚠️  Hash error for {file_path}: {e}")
            return None
    
    def check_if_exists_in_db(self, file_hash: str) -> Optional[Dict]:
        """Check if document with this hash already exists in database."""
        try:
            resp = self.supabase.table('documents')\
                .select('id,file_name,current_path,file_hash,created_at')\
                .eq('file_hash', file_hash)\
                .limit(1)\
                .execute()
            if resp.data and len(resp.data) > 0:
                return resp.data[0]
            return None
        except Exception as e:
            print(f"   ⚠️  DB check error: {e}")
            return None
    
    def discover_pdfs(self) -> List[Path]:
        """Discover all PDFs in Google Drive."""
        print("🔍 Discovering PDFs in Google Drive...")
        print(f"   Scanning: {self.gdrive_path}")
        print()
        
        pdfs = []
        skip_patterns = [
            'node_modules', '.git', '.Trash', 'Library/Caches',
            '.npm', '.cache', 'Library/Application Support',
            '.pkg', '.dmg', '.app/Contents', 'Library/Logs'
        ]
        
        count = 0
        try:
            for pdf_path in self.gdrive_path.rglob("*.pdf"):
                # Skip system folders
                if any(skip in str(pdf_path) for skip in skip_patterns):
                    continue
                
                pdfs.append(pdf_path)
                count += 1
                if count % 100 == 0:
                    print(f"   ... found {count} PDFs so far", end='\r')
            
            print(f"   ✅ Found {count} PDFs total")
            print()
        except Exception as e:
            print(f"   ⚠️  Error scanning: {e}")
        
        return sorted(pdfs)
    
    def verify_hashes(self, pdfs: List[Path]) -> Dict:
        """
        Verify hashes of PDFs marked as existing in database.
        Re-calculates hash and compares with database hash.
        
        Returns:
            Verification report dictionary
        """
        print("=" * 80)
        print("🔍 HASH VERIFICATION - Confirming PDFs in Database")
        print("=" * 80)
        print()
        
        verification_report = {
            'total_checked': 0,
            'hash_matches': [],
            'hash_mismatches': [],
            'not_found_in_db': [],
            'errors': []
        }
        
        print(f"Verifying hashes for {len(pdfs)} PDFs...")
        print()
        
        for i, pdf_path in enumerate(pdfs, 1):
            if i % 50 == 0:
                print(f"   Progress: {i}/{len(pdfs)}...", end='\r')
            
            try:
                # Calculate hash
                file_hash = self.calculate_file_hash(pdf_path)
                if not file_hash:
                    verification_report['errors'].append({
                        'path': str(pdf_path),
                        'error': 'Could not calculate hash'
                    })
                    continue
                
                # Check database
                existing_doc = self.check_if_exists_in_db(file_hash)
                
                if existing_doc:
                    verification_report['total_checked'] += 1
                    db_hash = existing_doc.get('file_hash', '')
                    
                    # Verify hash matches
                    if db_hash == file_hash:
                        verification_report['hash_matches'].append({
                            'path': str(pdf_path),
                            'hash': file_hash[:16] + '...',
                            'db_id': existing_doc['id'],
                            'db_name': existing_doc['file_name'],
                            'db_path': existing_doc['current_path']
                        })
                    else:
                        verification_report['hash_mismatches'].append({
                            'path': str(pdf_path),
                            'calculated_hash': file_hash,
                            'db_hash': db_hash,
                            'db_id': existing_doc['id'],
                            'db_name': existing_doc['file_name'],
                            'error': 'Hash mismatch - file may have changed'
                        })
                else:
                    verification_report['not_found_in_db'].append({
                        'path': str(pdf_path),
                        'hash': file_hash[:16] + '...',
                        'name': pdf_path.name
                    })
            
            except Exception as e:
                verification_report['errors'].append({
                    'path': str(pdf_path),
                    'error': str(e)
                })
        
        print(f"\n   ✅ Verification complete!")
        print()
        
        # Print verification report
        self._print_verification_report(verification_report)
        
        return verification_report
    
    def check_and_report(self, pdfs: List[Path], process_new: bool = False) -> Dict:
        """
        Check each PDF against database and generate report.
        
        Args:
            pdfs: List of PDF paths to check
            process_new: If True, process PDFs that don't exist in DB
        
        Returns:
            Report dictionary with statistics
        """
        print("=" * 80)
        print("📊 GOOGLE DRIVE PDF CHECK REPORT")
        print("=" * 80)
        print()
        
        report = {
            'total_found': len(pdfs),
            'exists_in_db': [],
            'not_in_db': [],
            'errors': [],
            'processed': [],
            'failed': []
        }
        
        print(f"Checking {len(pdfs)} PDFs against database...")
        print()
        
        for i, pdf_path in enumerate(pdfs, 1):
            if i % 50 == 0:
                print(f"   Progress: {i}/{len(pdfs)}...", end='\r')
            
            try:
                # Calculate hash
                file_hash = self.calculate_file_hash(pdf_path)
                if not file_hash:
                    report['errors'].append({
                        'path': str(pdf_path),
                        'error': 'Could not calculate hash'
                    })
                    continue
                
                # Check database
                existing_doc = self.check_if_exists_in_db(file_hash)
                
                if existing_doc:
                    report['exists_in_db'].append({
                        'path': str(pdf_path),
                        'hash': file_hash[:16] + '...',
                        'db_hash': existing_doc.get('file_hash', '')[:16] + '...' if existing_doc.get('file_hash') else 'N/A',
                        'db_id': existing_doc['id'],
                        'db_name': existing_doc['file_name'],
                        'db_path': existing_doc['current_path']
                    })
                else:
                    report['not_in_db'].append({
                        'path': str(pdf_path),
                        'hash': file_hash[:16] + '...',
                        'name': pdf_path.name
                    })
                    
                    # Process if requested
                    if process_new:
                        print(f"\n   [{i}/{len(pdfs)}] Processing: {pdf_path.name}")
                        print(f"      📍 Google Drive path: {pdf_path}")
                        try:
                            result = self.doc_processor.process_document(str(pdf_path), skip_if_exists=False)
                            if result and result.get('status') == 'success':
                                document_id = result.get('document_id')
                                
                                # Ensure Google Drive path is recorded with notes
                                try:
                                    # Check if original location was recorded
                                    loc_check = self.supabase.table('document_locations')\
                                        .select('id')\
                                        .eq('document_id', document_id)\
                                        .eq('location_type', 'original')\
                                        .execute()
                                    
                                    if loc_check.data:
                                        # Update the notes to indicate Google Drive source
                                        self.supabase.table('document_locations')\
                                            .update({
                                                'notes': f'Original Google Drive location - Source: Google Drive processing. File: {pdf_path.name}'
                                            })\
                                            .eq('id', loc_check.data[0]['id'])\
                                            .execute()
                                        print(f"      ✅ Google Drive path recorded with source notes")
                                    
                                except Exception as loc_err:
                                    print(f"      ⚠️  Note: Could not update location notes: {loc_err}")
                                
                                report['processed'].append({
                                    'path': str(pdf_path),
                                    'document_id': document_id,
                                    'name': pdf_path.name
                                })
                            else:
                                report['failed'].append({
                                    'path': str(pdf_path),
                                    'error': result.get('error', 'Unknown error') if result else 'No result'
                                })
                        except Exception as e:
                            report['failed'].append({
                                'path': str(pdf_path),
                                'error': str(e)
                            })
            
            except Exception as e:
                report['errors'].append({
                    'path': str(pdf_path),
                    'error': str(e)
                })
        
        print(f"\n   ✅ Check complete!")
        print()
        
        # Print report
        self._print_report(report)
        
        return report
    
    def _print_report(self, report: Dict):
        """Print formatted terminal report."""
        print("=" * 80)
        print("📊 FINAL REPORT")
        print("=" * 80)
        print()
        print(f"Total PDFs found:              {report['total_found']}")
        print(f"✅ Already in database:        {len(report['exists_in_db'])}")
        print(f"🆕 Not in database:            {len(report['not_in_db'])}")
        print(f"❌ Errors:                     {len(report['errors'])}")
        
        if report.get('processed'):
            print(f"✅ Processed:                  {len(report['processed'])}")
        if report.get('failed'):
            print(f"❌ Failed to process:          {len(report['failed'])}")
        
        print()
        print("=" * 80)
        
        # Show samples
        if report['exists_in_db']:
            print("\n📋 Sample PDFs ALREADY IN DATABASE (showing first 10):")
            print("-" * 80)
            for item in report['exists_in_db'][:10]:
                print(f"  ✅ {Path(item['path']).name}")
                print(f"     Path: {item['path']}")
                print(f"     DB ID: {item['db_id']}")
                print(f"     DB Name: {item['db_name']}")
                print(f"     DB Path: {item['db_path']}")
                print()
        
        if report['not_in_db']:
            print(f"\n🆕 PDFs NOT IN DATABASE (showing first 20):")
            print("-" * 80)
            for item in report['not_in_db'][:20]:
                print(f"  🆕 {item['name']}")
                print(f"     Path: {item['path']}")
                print(f"     Hash: {item['hash']}")
                print()
            
            if len(report['not_in_db']) > 20:
                print(f"     ... and {len(report['not_in_db']) - 20} more")
                print()
        
        if report.get('processed'):
            print(f"\n✅ Successfully Processed ({len(report['processed'])}):")
            print("-" * 80)
            for item in report['processed'][:10]:
                print(f"  ✅ {item.get('name', Path(item['path']).name)} (ID: {item['document_id']})")
                print(f"     📍 Google Drive: {item['path']}")
                print(f"     💾 Original path & name tracked in database")
            if len(report['processed']) > 10:
                print(f"     ... and {len(report['processed']) - 10} more")
            print()
        
        if report.get('failed'):
            print(f"\n❌ Failed to Process ({len(report['failed'])}):")
            print("-" * 80)
            for item in report['failed'][:10]:
                print(f"  ❌ {Path(item['path']).name}")
                print(f"     Error: {item['error']}")
            if len(report['failed']) > 10:
                print(f"     ... and {len(report['failed']) - 10} more")
            print()
        
        if report['errors']:
            print(f"\n⚠️  Errors ({len(report['errors'])}):")
            print("-" * 80)
            for item in report['errors'][:10]:
                print(f"  ⚠️  {Path(item['path']).name}")
                print(f"     Error: {item['error']}")
            if len(report['errors']) > 10:
                print(f"     ... and {len(report['errors']) - 10} more")
            print()
        
        print("=" * 80)
        print()
    
    def _print_verification_report(self, report: Dict):
        """Print formatted hash verification report."""
        print("=" * 80)
        print("🔍 HASH VERIFICATION REPORT")
        print("=" * 80)
        print()
        print(f"Total PDFs checked:         {report['total_checked']}")
        print(f"✅ Hash matches:            {len(report['hash_matches'])}")
        print(f"⚠️  Hash mismatches:         {len(report['hash_mismatches'])}")
        print(f"🆕 Not found in DB:          {len(report['not_found_in_db'])}")
        print(f"❌ Errors:                   {len(report['errors'])}")
        print()
        print("=" * 80)
        
        if report['hash_matches']:
            print(f"\n✅ CONFIRMED - Hash Matches ({len(report['hash_matches'])}):")
            print("-" * 80)
            for item in report['hash_matches'][:10]:
                print(f"  ✅ {Path(item['path']).name}")
                print(f"     Path: {item['path']}")
                print(f"     Hash: {item['hash']} ✓")
                print(f"     DB ID: {item['db_id']}")
                print()
            if len(report['hash_matches']) > 10:
                print(f"     ... and {len(report['hash_matches']) - 10} more confirmed")
                print()
        
        if report['hash_mismatches']:
            print(f"\n⚠️  HASH MISMATCHES ({len(report['hash_mismatches'])}):")
            print("-" * 80)
            for item in report['hash_mismatches']:
                print(f"  ⚠️  {Path(item['path']).name}")
                print(f"     Path: {item['path']}")
                print(f"     Calculated Hash: {item['calculated_hash'][:32]}...")
                print(f"     DB Hash:         {item['db_hash'][:32]}...")
                print(f"     DB ID: {item['db_id']}")
                print(f"     Error: {item['error']}")
                print()
        
        if report['not_found_in_db']:
            print(f"\n🆕 NOT FOUND IN DATABASE ({len(report['not_found_in_db'])}):")
            print("-" * 80)
            for item in report['not_found_in_db'][:10]:
                print(f"  🆕 {item['name']}")
                print(f"     Path: {item['path']}")
                print(f"     Hash: {item['hash']}")
                print()
            if len(report['not_found_in_db']) > 10:
                print(f"     ... and {len(report['not_found_in_db']) - 10} more")
                print()
        
        if report['errors']:
            print(f"\n❌ ERRORS ({len(report['errors'])}):")
            print("-" * 80)
            for item in report['errors'][:10]:
                print(f"  ❌ {Path(item['path']).name}")
                print(f"     Error: {item['error']}")
                print()
            if len(report['errors']) > 10:
                print(f"     ... and {len(report['errors']) - 10} more")
                print()
        
        print("=" * 80)
        print()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Check Google Drive PDFs against database and optionally process new ones'
    )
    parser.add_argument(
        '--gdrive-path',
        type=str,
        default="/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive",
        help='Path to Google Drive root (default: standard macOS path)'
    )
    parser.add_argument(
        '--process',
        action='store_true',
        help='Process PDFs that are not in database (same workflow as iCloud/localhost)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Only check and report, do not process (default behavior)'
    )
    parser.add_argument(
        '--verify-hashes',
        action='store_true',
        help='Verify hashes of PDFs marked as existing in database'
    )
    
    args = parser.parse_args()
    
    # Create checker
    checker = GoogleDrivePDFChecker(gdrive_path=args.gdrive_path)
    
    # Discover PDFs
    pdfs = checker.discover_pdfs()
    
    if not pdfs:
        print("❌ No PDFs found in Google Drive")
        return
    
    # Hash verification mode
    if args.verify_hashes:
        print("🔍 Hash Verification Mode")
        print("   Verifying hashes of PDFs marked as existing in database")
        print()
        verification_report = checker.verify_hashes(pdfs)
        
        print("\n" + "=" * 80)
        print("📊 VERIFICATION SUMMARY")
        print("=" * 80)
        print(f"Total checked:        {verification_report['total_checked']}")
        print(f"✅ Hash matches:       {len(verification_report['hash_matches'])}")
        print(f"⚠️  Hash mismatches:    {len(verification_report['hash_mismatches'])}")
        print(f"🆕 Not found in DB:     {len(verification_report['not_found_in_db'])}")
        print("=" * 80)
        print()
        return
    
    # Check and report
    process_new = args.process and not args.dry_run
    if process_new:
        print("⚠️  Processing mode: Will process PDFs not in database")
        print()
    else:
        print("ℹ️  Report mode: Only checking, not processing")
        print("   Use --process to process new PDFs")
        print("   Use --verify-hashes to verify hashes of existing PDFs")
        print()
    
    report = checker.check_and_report(pdfs, process_new=process_new)
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)
    print(f"Total found:        {report['total_found']}")
    print(f"In database:        {len(report['exists_in_db'])}")
    print(f"Not in database:    {len(report['not_in_db'])}")
    if process_new:
        print(f"Processed:          {len(report.get('processed', []))}")
        print(f"Failed:             {len(report.get('failed', []))}")
    print("=" * 80)
    print()


if __name__ == "__main__":
    main()
