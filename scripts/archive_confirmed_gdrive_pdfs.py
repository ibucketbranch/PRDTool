#!/usr/bin/env python3
"""
Archive Confirmed Google Drive PDFs
Moves PDFs that are confirmed to exist in database (by hash) into an archive folder.
"""

import os
import sys
import hashlib
import shutil
from pathlib import Path
from typing import Dict, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from supabase import create_client, Client
except ImportError:
    print("Error: supabase not installed. Install with: pip install supabase")
    sys.exit(1)


class GoogleDrivePDFArchiver:
    """
    Archive confirmed PDFs in Google Drive.
    """
    
    def __init__(self, 
                 gdrive_path: str = "/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive",
                 archive_folder: str = "Archived_PDFs_Processed",
                 supabase_url: str = "http://127.0.0.1:54421",
                 supabase_key: Optional[str] = None):
        """Initialize archiver."""
        self.gdrive_path = Path(gdrive_path)
        self.archive_path = self.gdrive_path / archive_folder
        supabase_key = supabase_key or os.getenv('SUPABASE_SERVICE_ROLE_KEY')
        self.supabase: Client = create_client(supabase_url, supabase_key)
        
        print("🚀 Google Drive PDF Archiver initialized")
        print(f"   Google Drive path: {self.gdrive_path}")
        print(f"   Archive folder: {self.archive_path}")
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
                .select('id,file_name,current_path,file_hash')\
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
                # Skip system folders and archive folder itself
                if any(skip in str(pdf_path) for skip in skip_patterns):
                    continue
                
                # Skip files already in archive folder
                if 'Archived_PDFs_Processed' in str(pdf_path):
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
    
    def identify_confirmed_pdfs(self, pdfs: List[Path]) -> List[Path]:
        """Identify PDFs that are confirmed to exist in database by hash."""
        print("🔍 Identifying confirmed PDFs (matching database hashes)...")
        print()
        
        confirmed = []
        
        for i, pdf_path in enumerate(pdfs, 1):
            if i % 50 == 0:
                print(f"   Checking {i}/{len(pdfs)}...", end='\r')
            
            try:
                # Calculate hash
                file_hash = self.calculate_file_hash(pdf_path)
                if not file_hash:
                    continue
                
                # Check database
                existing_doc = self.check_if_exists_in_db(file_hash)
                
                if existing_doc:
                    # Verify hash matches
                    db_hash = existing_doc.get('file_hash', '')
                    if db_hash == file_hash:
                        confirmed.append(pdf_path)
            
            except Exception as e:
                print(f"   ⚠️  Error checking {pdf_path.name}: {e}")
        
        print(f"\n   ✅ Found {len(confirmed)} confirmed PDFs")
        print()
        
        return confirmed
    
    def archive_pdfs(self, pdfs: List[Path], dry_run: bool = False) -> Dict:
        """
        Move confirmed PDFs to archive folder.
        
        Args:
            pdfs: List of PDF paths to archive
            dry_run: If True, only show what would be moved without actually moving
        
        Returns:
            Report dictionary with statistics
        """
        print("=" * 80)
        if dry_run:
            print("🔍 DRY RUN - Archive Preview (no files will be moved)")
        else:
            print("📦 ARCHIVING CONFIRMED PDFs")
        print("=" * 80)
        print()
        
        # Create archive folder
        if not dry_run:
            self.archive_path.mkdir(parents=True, exist_ok=True)
            print(f"✅ Archive folder ready: {self.archive_path}")
        else:
            print(f"📁 Archive folder would be: {self.archive_path}")
        print()
        
        report = {
            'total': len(pdfs),
            'moved': [],
            'failed': [],
            'skipped': []
        }
        
        print(f"Archiving {len(pdfs)} PDFs...")
        print()
        
        for i, pdf_path in enumerate(pdfs, 1):
            if i % 10 == 0:
                print(f"   Progress: {i}/{len(pdfs)}...", end='\r')
            
            try:
                # Determine destination path
                # Preserve relative path structure within archive
                relative_path = pdf_path.relative_to(self.gdrive_path)
                archive_dest = self.archive_path / relative_path
                
                # Create parent directories
                archive_dest.parent.mkdir(parents=True, exist_ok=True)
                
                if dry_run:
                    report['moved'].append({
                        'source': str(pdf_path),
                        'destination': str(archive_dest),
                        'status': 'would_move'
                    })
                else:
                    # Move file
                    shutil.move(str(pdf_path), str(archive_dest))
                    report['moved'].append({
                        'source': str(pdf_path),
                        'destination': str(archive_dest),
                        'status': 'moved'
                    })
            
            except Exception as e:
                report['failed'].append({
                    'path': str(pdf_path),
                    'error': str(e)
                })
                print(f"\n   ⚠️  Error archiving {pdf_path.name}: {e}")
        
        print(f"\n   ✅ Archive complete!")
        print()
        
        # Print report
        self._print_report(report, dry_run)
        
        return report
    
    def _print_report(self, report: Dict, dry_run: bool = False):
        """Print formatted archive report."""
        print("=" * 80)
        if dry_run:
            print("🔍 DRY RUN REPORT")
        else:
            print("📦 ARCHIVE REPORT")
        print("=" * 80)
        print()
        print(f"Total PDFs:              {report['total']}")
        if dry_run:
            print(f"Would move:              {len(report['moved'])}")
        else:
            print(f"✅ Successfully moved:   {len(report['moved'])}")
        print(f"❌ Failed:               {len(report['failed'])}")
        print()
        print("=" * 80)
        
        if report['moved']:
            print(f"\n{'Would move' if dry_run else 'Moved'} ({len(report['moved'])}):")
            print("-" * 80)
            for item in report['moved'][:20]:
                print(f"  ✅ {Path(item['source']).name}")
                print(f"     From: {item['source']}")
                print(f"     To:   {item['destination']}")
                print()
            if len(report['moved']) > 20:
                print(f"     ... and {len(report['moved']) - 20} more")
                print()
        
        if report['failed']:
            print(f"\n❌ Failed ({len(report['failed'])}):")
            print("-" * 80)
            for item in report['failed'][:10]:
                print(f"  ❌ {Path(item['path']).name}")
                print(f"     Error: {item['error']}")
                print()
            if len(report['failed']) > 10:
                print(f"     ... and {len(report['failed']) - 10} more")
                print()
        
        print("=" * 80)
        print()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Archive confirmed Google Drive PDFs (that exist in database)'
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
        help='Preview what would be archived without actually moving files'
    )
    parser.add_argument(
        '--yes',
        action='store_true',
        help='Skip confirmation prompt and proceed with archiving'
    )
    
    args = parser.parse_args()
    
    # Create archiver
    archiver = GoogleDrivePDFArchiver(
        gdrive_path=args.gdrive_path,
        archive_folder=args.archive_folder
    )
    
    # Discover PDFs
    pdfs = archiver.discover_pdfs()
    
    if not pdfs:
        print("❌ No PDFs found in Google Drive")
        return
    
    # Identify confirmed PDFs
    confirmed_pdfs = archiver.identify_confirmed_pdfs(pdfs)
    
    if not confirmed_pdfs:
        print("❌ No confirmed PDFs found (none match database hashes)")
        return
    
    # Confirm action
    if not args.dry_run and not args.yes:
        print("=" * 80)
        print("⚠️  WARNING: This will MOVE files to archive folder")
        print("=" * 80)
        print(f"   Will move {len(confirmed_pdfs)} PDFs to:")
        print(f"   {archiver.archive_path}")
        print()
        response = input("   Continue? (yes/no): ").strip().lower()
        if response != 'yes':
            print("   Cancelled.")
            return
        print()
    elif args.yes and not args.dry_run:
        print("=" * 80)
        print("⚠️  Archiving confirmed PDFs (--yes flag used)")
        print("=" * 80)
        print(f"   Moving {len(confirmed_pdfs)} PDFs to:")
        print(f"   {archiver.archive_path}")
        print()
    
    # Archive PDFs
    report = archiver.archive_pdfs(confirmed_pdfs, dry_run=args.dry_run)
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)
    print(f"Total confirmed:     {report['total']}")
    if args.dry_run:
        print(f"Would move:          {len(report['moved'])}")
    else:
        print(f"Moved:               {len(report['moved'])}")
    print(f"Failed:              {len(report['failed'])}")
    print("=" * 80)
    print()


if __name__ == "__main__":
    main()
