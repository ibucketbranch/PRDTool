#!/usr/bin/env python3
"""
Folder Structure Importer
Scans existing folder structure (like iCloud Drive bins) and catalogs all PDFs.
"""

import sys
import os
from pathlib import Path
from typing import Dict, List, Optional
import json
from datetime import datetime

try:
    from document_processor import DocumentProcessor
except ImportError:
    print("Error: document_processor.py not found")
    sys.exit(1)

try:
    from supabase import create_client, Client
except ImportError:
    print("supabase not installed. Install with: pip install supabase")
    sys.exit(1)


class FolderStructureImporter:
    """Import and catalog existing folder structures."""
    
    def __init__(self):
        self.processor = DocumentProcessor()
        self.supabase: Client = create_client(
            "http://127.0.0.1:54321",
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0"
        )
        self.stats = {
            'total_files': 0,
            'processed': 0,
            'skipped': 0,
            'failed': 0,
            'bins_found': {},
            'categories_found': {}
        }
    
    def scan_directory(self, root_path: str, recursive: bool = True, 
                      dry_run: bool = False) -> Dict:
        """
        Scan a directory and process all PDFs.
        
        Args:
            root_path: Root directory to scan
            recursive: Scan subdirectories
            dry_run: If True, only report what would be done, don't process files
        """
        
        print(f"\n{'='*80}")
        print(f"📁 FOLDER STRUCTURE IMPORT")
        print(f"{'='*80}")
        print(f"Root Path: {root_path}")
        print(f"Recursive: {recursive}")
        print(f"Dry Run: {dry_run}")
        print(f"{'='*80}\n")
        
        if not os.path.exists(root_path):
            print(f"❌ Error: Path not found: {root_path}")
            return {'error': 'path_not_found'}
        
        # Find all PDF files
        print("🔍 Scanning for PDF files...")
        pattern = "**/*.pdf" if recursive else "*.pdf"
        pdf_files = list(Path(root_path).glob(pattern))
        
        self.stats['total_files'] = len(pdf_files)
        print(f"✓ Found {len(pdf_files)} PDF files\n")
        
        if dry_run:
            return self._dry_run_report(pdf_files)
        
        # Process each file
        print(f"{'='*80}")
        print(f"🚀 PROCESSING FILES")
        print(f"{'='*80}\n")
        
        for i, pdf_path in enumerate(pdf_files, 1):
            print(f"\n{'─'*80}")
            print(f"[{i}/{len(pdf_files)}] {pdf_path.name}")
            print(f"{'─'*80}")
            
            try:
                result = self.processor.process_document(str(pdf_path), skip_if_exists=True)
                
                if result.get('status') == 'success':
                    self.stats['processed'] += 1
                    
                    # Track bin
                    context_bin = result.get('context_bin', 'Unknown')
                    self.stats['bins_found'][context_bin] = self.stats['bins_found'].get(context_bin, 0) + 1
                    
                    # Track category
                    category = result.get('category', 'unknown')
                    self.stats['categories_found'][category] = self.stats['categories_found'].get(category, 0) + 1
                    
                elif result.get('status') == 'skipped':
                    self.stats['skipped'] += 1
                    print(f"⏭️  Skipped (already processed)")
                else:
                    self.stats['failed'] += 1
                    print(f"❌ Failed: {result.get('reason', 'Unknown error')}")
                    
            except Exception as e:
                self.stats['failed'] += 1
                print(f"❌ Error: {e}")
            
            # Progress update every 10 files
            if i % 10 == 0:
                self._print_progress()
        
        # Final report
        self._print_final_report()
        
        return self.stats
    
    def _dry_run_report(self, pdf_files: List[Path]) -> Dict:
        """Generate a dry-run report without processing files."""
        
        print(f"\n{'='*80}")
        print(f"📊 DRY RUN REPORT")
        print(f"{'='*80}\n")
        
        bins_preview = {}
        total_size = 0
        
        for pdf_path in pdf_files:
            # Detect potential bin
            context_bin = self.processor.detect_context_bin(str(pdf_path))
            if context_bin:
                bins_preview[context_bin] = bins_preview.get(context_bin, 0) + 1
            else:
                bins_preview['Unknown'] = bins_preview.get('Unknown', 0) + 1
            
            # Get file size
            try:
                total_size += pdf_path.stat().st_size
            except:
                pass
        
        print(f"📄 Total PDFs found: {len(pdf_files)}")
        print(f"💾 Total size: {total_size / 1024 / 1024:.2f} MB")
        print(f"\n📂 Documents by Bin:")
        for bin_name, count in sorted(bins_preview.items(), key=lambda x: x[1], reverse=True):
            print(f"   • {bin_name}: {count} files")
        
        print(f"\n📁 Sample paths:")
        for pdf_path in list(pdf_files)[:10]:
            print(f"   • {pdf_path}")
        
        if len(pdf_files) > 10:
            print(f"   ... and {len(pdf_files) - 10} more")
        
        print(f"\n{'='*80}")
        print(f"💡 To process these files, run without --dry-run flag")
        print(f"{'='*80}\n")
        
        return {
            'total_files': len(pdf_files),
            'total_size_mb': total_size / 1024 / 1024,
            'bins_preview': bins_preview,
            'dry_run': True
        }
    
    def _print_progress(self):
        """Print progress update."""
        processed = self.stats['processed']
        skipped = self.stats['skipped']
        failed = self.stats['failed']
        total = self.stats['total_files']
        completed = processed + skipped + failed
        
        print(f"\n{'─'*80}")
        print(f"📊 Progress: {completed}/{total} ({completed/total*100:.1f}%)")
        print(f"   ✅ Processed: {processed} | ⏭️  Skipped: {skipped} | ❌ Failed: {failed}")
        print(f"{'─'*80}\n")
    
    def _print_final_report(self):
        """Print final import report."""
        print(f"\n{'='*80}")
        print(f"✅ IMPORT COMPLETE")
        print(f"{'='*80}\n")
        
        print(f"📊 Summary:")
        print(f"   Total Files: {self.stats['total_files']}")
        print(f"   ✅ Processed: {self.stats['processed']}")
        print(f"   ⏭️  Skipped: {self.stats['skipped']} (already in database)")
        print(f"   ❌ Failed: {self.stats['failed']}")
        
        print(f"\n📂 Documents by Bin:")
        for bin_name, count in sorted(self.stats['bins_found'].items(), key=lambda x: x[1], reverse=True):
            print(f"   • {bin_name}: {count} documents")
        
        print(f"\n🏷️  Documents by Category:")
        for category, count in sorted(self.stats['categories_found'].items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"   • {category}: {count} documents")
        
        print(f"\n{'='*80}\n")
        
        # Save report to file
        report_file = f"import_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(self.stats, f, indent=2)
        print(f"📝 Full report saved to: {report_file}\n")
    
    def scan_bin(self, bin_path: str, bin_name: Optional[str] = None) -> Dict:
        """
        Scan a specific bin directory.
        
        Args:
            bin_path: Path to bin directory
            bin_name: Override bin name detection
        """
        
        if not os.path.exists(bin_path):
            print(f"❌ Error: Bin path not found: {bin_path}")
            return {'error': 'path_not_found'}
        
        # Detect bin name from path if not provided
        if not bin_name:
            bin_name = self.processor.detect_context_bin(bin_path) or Path(bin_path).name
        
        print(f"\n{'='*80}")
        print(f"📂 SCANNING BIN: {bin_name}")
        print(f"{'='*80}")
        print(f"Path: {bin_path}")
        print(f"{'='*80}\n")
        
        return self.scan_directory(bin_path, recursive=True, dry_run=False)
    
    def get_bin_statistics(self) -> Dict:
        """Get statistics on bins currently in database."""
        try:
            result = self.supabase.table('bin_statistics').select('*').execute()
            
            if result.data:
                print(f"\n{'='*80}")
                print(f"📊 CURRENT BIN STATISTICS")
                print(f"{'='*80}\n")
                
                for bin_stat in result.data:
                    print(f"📂 {bin_stat['context_bin']}")
                    print(f"   Documents: {bin_stat['document_count']}")
                    print(f"   Categories: {bin_stat['category_count']}")
                    print(f"   Avg Confidence: {bin_stat['avg_confidence']:.2%}")
                    print(f"   Avg Importance: {bin_stat['avg_importance']:.1f}/10")
                    print(f"   Last Added: {bin_stat['last_added']}")
                    print()
                
                print(f"{'='*80}\n")
            
            return result.data if result.data else []
            
        except Exception as e:
            print(f"❌ Error fetching bin statistics: {e}")
            return []


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Import existing folder structure and catalog PDFs',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run (preview only)
  python folder_structure_importer.py ~/Library/Mobile\\ Documents/com~apple~CloudDocs --dry-run
  
  # Import all PDFs from iCloud Drive
  python folder_structure_importer.py ~/Library/Mobile\\ Documents/com~apple~CloudDocs
  
  # Import a specific bin
  python folder_structure_importer.py ~/Library/Mobile\\ Documents/com~apple~CloudDocs/Personal\\ Bin
  
  # Non-recursive import
  python folder_structure_importer.py ~/Documents --no-recursive
  
  # Show current bin statistics
  python folder_structure_importer.py --stats
        """
    )
    
    parser.add_argument('path', nargs='?', help='Path to directory to scan')
    parser.add_argument('--dry-run', action='store_true', help='Preview without processing')
    parser.add_argument('--no-recursive', action='store_true', help='Don\'t scan subdirectories')
    parser.add_argument('--bin-name', help='Override bin name detection')
    parser.add_argument('--stats', action='store_true', help='Show current bin statistics')
    
    args = parser.parse_args()
    
    importer = FolderStructureImporter()
    
    if args.stats:
        importer.get_bin_statistics()
        sys.exit(0)
    
    if not args.path:
        parser.print_help()
        sys.exit(1)
    
    # Run import
    if args.bin_name:
        importer.scan_bin(args.path, args.bin_name)
    else:
        importer.scan_directory(
            args.path, 
            recursive=not args.no_recursive,
            dry_run=args.dry_run
        )


if __name__ == "__main__":
    main()
