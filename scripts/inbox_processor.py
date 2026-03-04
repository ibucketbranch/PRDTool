#!/usr/bin/env python3
"""
Inbox Processor - SAFE MODE
Processes PDFs from In-Box folder with multiple safety checks.

SAFETY FEATURES:
- Dry-run mode (preview only)
- Atomic file operations (copy -> verify -> delete)
- Transaction logging
- Error isolation (Processing Errors folder)
- Hash verification
- Rollback capability
"""

import os
import sys
import shutil
import hashlib
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import re

try:
    from document_processor import DocumentProcessor
except ImportError:
    print("Error: document_processor.py not found")
    sys.exit(1)

try:
    from notification_service import (
        notify_new_files, notify_processing_complete, notify_processing_error,
        notify_staged_files_ready, notify_duplicate_detected
    )
except ImportError:
    print("Warning: notification_service.py not found - notifications disabled")
    # Create dummy functions if not available
    def notify_new_files(*args, **kwargs): pass
    def notify_processing_complete(*args, **kwargs): pass
    def notify_processing_error(*args, **kwargs): pass
    def notify_staged_files_ready(*args, **kwargs): pass
    def notify_duplicate_detected(*args, **kwargs): pass

try:
    from supabase import create_client, Client
except ImportError:
    print("supabase not installed")
    sys.exit(1)

try:
    from groq import Groq
except ImportError:
    Groq = None
    print("Warning: groq not installed - Groq fallback disabled")


class InboxProcessor:
    """
    Safe inbox processing with atomic operations and error handling.
    """
    
    def __init__(self, inbox_path: str = None, dry_run: bool = True, use_staging: bool = True):
        """
        Initialize inbox processor.
        
        Args:
            inbox_path: Path to In-Box folder (defaults to iCloud)
            dry_run: If True, only preview operations (DEFAULT: True for safety)
            use_staging: If True, move to Processed/ folder first (DEFAULT: True, always used)
        """
        # Default inbox location
        if inbox_path is None:
            inbox_path = str(Path.home() / 'Library' / 'Mobile Documents' / 
                           'com~apple~CloudDocs' / 'In-Box')
        
        self.inbox_path = Path(inbox_path)
        self.errors_path = self.inbox_path / 'Processing Errors'
        self.processed_path = self.inbox_path / 'Processed'  # NEW: Staging area
        self.dry_run = dry_run
        self.use_staging = use_staging  # NEW: Whether to use staging
        
        self.processor = DocumentProcessor()
        groq_key = os.getenv('GROQ_API_KEY')
        self.groq_client = None
        if Groq and groq_key:
            try:
                self.groq_client = Groq(api_key=groq_key)
            except Exception as exc:
                print(f"Warning: Could not initialize Groq client: {exc}")
        elif not groq_key:
            print("Info: GROQ_API_KEY not set; filename descriptions will use basic fallback.")
        self.supabase: Client = create_client(
            "http://127.0.0.1:54321",
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0"
        )
        
        # Transaction log
        self.transaction_log = []
        self.log_file = Path.home() / '.inbox_processor.log'
        
        # Category short codes for filenames
        self.category_codes = {
            'vehicle_registration': 'VehicleReg',
            'vehicle_insurance': 'VehicleIns',
            'vehicle_maintenance': 'VehicleMaint',
            'tax_document': 'TaxDoc',
            'invoice': 'Invoice',
            'receipt': 'Receipt',
            'bank_statement': 'BankStmt',
            'contract': 'Contract',
            'medical_record': 'MedicalRec',
            'medical_insurance': 'MedicalIns',
            'insurance_policy': 'InsPolicy',
            'legal': 'LegalDoc',
            'correspondence': 'Correspondence',
            'other': 'Document'
        }
    
    def setup_inbox(self):
        """Create inbox folder structure if it doesn't exist."""
        print(f"\n🔧 Setting up inbox structure...")
        
        # Create In-Box
        if not self.inbox_path.exists():
            print(f"   Creating: {self.inbox_path}")
            if not self.dry_run:
                self.inbox_path.mkdir(parents=True, exist_ok=True)
            print(f"   ✅ In-Box created")
        else:
            print(f"   ✓ In-Box exists: {self.inbox_path}")
        
        # Create Processed subfolder (staging area)
        if not self.processed_path.exists():
            print(f"   Creating: {self.processed_path}")
            if not self.dry_run:
                self.processed_path.mkdir(parents=True, exist_ok=True)
            print(f"   ✅ Processed (staging) created")
        else:
            print(f"   ✓ Processed exists: {self.processed_path}")
        
        # Create Processing Errors subfolder
        if not self.errors_path.exists():
            print(f"   Creating: {self.errors_path}")
            if not self.dry_run:
                self.errors_path.mkdir(parents=True, exist_ok=True)
            print(f"   ✅ Processing Errors created")
        else:
            print(f"   ✓ Processing Errors exists: {self.errors_path}")
        
        print(f"   ✅ Inbox setup complete\n")
    
    def _log(self, message: str, level: str = "INFO"):
        """Log message to file and console."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] [{level}] {message}"
        
        print(f"   {message}")
        
        try:
            with open(self.log_file, 'a') as f:
                f.write(log_entry + '\n')
        except:
            pass
    
    def _calculate_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def scan_inbox(self) -> List[Path]:
        """Scan inbox for supported file types (PDF, TXT, DOCX, XLSX, PPTX, RTF) excluding subfolders."""
        if not self.inbox_path.exists():
            self._log(f"Inbox not found: {self.inbox_path}", "ERROR")
            return []
        
        # Supported file extensions
        supported_extensions = ['.pdf', '.txt', '.docx', '.xlsx', '.pptx', '.rtf']
        
        files_to_process = []
        for ext in supported_extensions:
            for file_path in self.inbox_path.glob(f'*{ext}'):
                # Skip if in subfolders (Processing Errors or Processed)
                if file_path.parent != self.inbox_path:
                    continue
                files_to_process.append(file_path)
        
        return files_to_process
    
    def scan_errors(self) -> List[Path]:
        """Scan Processing Errors folder for files to retry."""
        if not self.errors_path.exists():
            return []
        
        # Supported file extensions (exclude .txt error logs)
        supported_extensions = ['.pdf', '.docx', '.xlsx', '.pptx', '.rtf']
        error_files = []
        for ext in supported_extensions:
            for file_path in self.errors_path.glob(f'*{ext}'):
                error_files.append(file_path)
        
        return error_files
    
    def scan_processed(self) -> List[Path]:
        """Scan Processed folder for verified files ready to finalize."""
        if not self.processed_path.exists():
            return []
        
        # Scan for all supported file types
        supported_extensions = ['.pdf', '.txt', '.docx', '.xlsx', '.pptx', '.rtf']
        processed_files = []
        for ext in supported_extensions:
            processed_files.extend(self.processed_path.glob(f'*{ext}'))
        
        return processed_files
    
    def generate_smart_filename(self, doc_info: Dict) -> str:
        """
        Generate smart filename using AI.
        
        Format: [Category]_[Description]_[Date]_[Version].[ext]
        Example: VehicleReg_Tesla_Model3_20240315_v1.pdf
        Example: BankStatement_BofA_Checking_20240315_v1.txt
        """
        
        # Get category code
        category = doc_info.get('ai_category', 'other')
        category_code = self.category_codes.get(category, 'Document')
        
        # Extract description using Groq
        description = self._generate_description(doc_info)
        
        # Extract date from entities or use current
        doc_date = self._extract_document_date(doc_info)
        
        # Version (always v1 for new files)
        version = 'v1'
        
        # Part (always COMPLETE unless multi-part)
        part = 'COMPLETE'
        
        # Build filename
        components = [
            category_code,
            description,
            doc_date,
            version,
            part
        ]
        
        filename = "_".join(filter(None, components)) + ".pdf"
        
        # Sanitize
        filename = self._sanitize_filename(filename)
        
        # Note: File extension will be preserved by caller based on original file type
        return filename
    
    def _generate_description(self, doc_info: Dict) -> str:
        """Use Groq (if available) to generate 2-4 word description."""
        
        if not self.groq_client:
            return self._basic_description(doc_info)
        
        summary = doc_info.get('ai_summary', '')
        entities = doc_info.get('entities', {})
        category = doc_info.get('ai_category', '')
        
        prompt = f"""Generate a 2-4 word filename description for this document.

Summary: {summary[:500]}
Category: {category}
Entities: {json.dumps(entities)}

Rules:
- Use PascalCase (no spaces): Tesla_Model3
- 2-4 words maximum
- Focus on key identifiers (vehicle, company, person, account)
- Be specific but concise
- Professional naming

Examples:
- Vehicle registration → "Tesla_Model3"
- Insurance card → "BlueShield_Card"
- Tax return → "Federal_Return"
- Bank statement → "Chase_Checking"

Return ONLY the description, nothing else."""
        
        try:
            response = self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=50
            )
            
            description = response.choices[0].message.content.strip()
            description = description.replace(' ', '_')
            return description
            
        except Exception as e:
            self._log(f"AI description failed: {e}", "WARN")
            return self._basic_description(doc_info)

    def _basic_description(self, doc_info: Dict) -> str:
        """Fallback description generator when Groq is unavailable."""
        summary = (doc_info.get('ai_summary') or '').strip()
        if summary:
            words = re.findall(r"[A-Za-z0-9]+", summary)
            if words:
                return "_".join(words[:3])[:40] or "Document"
        return "Document"
    
    def _extract_document_date(self, doc_info: Dict) -> str:
        """Extract document date from entities or metadata."""
        entities = doc_info.get('entities', {})
        dates = entities.get('dates', [])
        
        if dates:
            # Try to parse first date
            for date_str in dates:
                # Look for YYYY format
                year_match = re.search(r'\b(20\d{2})\b', str(date_str))
                if year_match:
                    year = year_match.group(1)
                    # Look for full date
                    full_date_match = re.search(r'\b(\d{1,2})[/-](\d{1,2})[/-](20\d{2})\b', str(date_str))
                    if full_date_match:
                        month, day, year = full_date_match.groups()
                        return f"{year}{int(month):02d}{int(day):02d}"
                    return year
        
        # Fallback to current year
        return datetime.now().strftime('%Y')
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for filesystem compatibility."""
        # Remove invalid characters
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        # Replace multiple underscores
        filename = re.sub(r'_+', '_', filename)
        # Remove leading/trailing underscores
        filename = filename.strip('_')
        return filename
    
    def build_destination_path(self, doc_info: Dict, new_filename: str) -> Path:
        """
        Build destination path: context_bin/category/new_filename
        
        Example: Personal Bin/Vehicles/VehicleReg_Tesla_Model3_20240315_v1.pdf
        """
        context_bin = doc_info.get('context_bin', 'Uncategorized')
        category = doc_info.get('ai_category', 'other')
        
        # Get base iCloud path
        icloud_base = Path.home() / 'Library' / 'Mobile Documents' / 'com~apple~CloudDocs'
        
        # Build path
        dest_path = icloud_base / context_bin / category / new_filename
        
        return dest_path
    
    def safe_move_file(self, source: Path, destination: Path) -> Tuple[bool, str]:
        """
        Safely move file with verification.
        
        Steps:
        1. Calculate source hash
        2. Create destination directory
        3. Copy file to destination
        4. Verify destination hash matches
        5. Delete original only if verified
        6. Log transaction
        
        Returns:
            (success: bool, message: str)
        """
        
        if self.dry_run:
            return True, f"DRY-RUN: Would move {source.name} to {destination}"
        
        try:
            # Step 1: Calculate source hash
            source_hash = self._calculate_hash(source)
            self._log(f"Source hash: {source_hash[:16]}...")
            
            # Step 2: Create destination directory
            destination.parent.mkdir(parents=True, exist_ok=True)
            
            # Step 3: Handle conflicts
            if destination.exists():
                # Check if it's a duplicate
                existing_hash = self._calculate_hash(destination)
                if existing_hash == source_hash:
                    # True duplicate - just delete source
                    source.unlink()
                    
                    # Notify about duplicate
                    notify_duplicate_detected(source.name, "deleted (true duplicate)")
                    
                    return True, f"Duplicate detected, original removed"
                else:
                    # Name collision - add REF number
                    ref_num = self._get_next_ref_number(destination)
                    name_without_ext = destination.stem
                    destination = destination.parent / f"{name_without_ext}_REF{ref_num:03d}.pdf"
                    
                    # Notify about name collision
                    notify_duplicate_detected(source.name, f"renamed with REF{ref_num:03d}")
            
            # Step 4: Copy file
            shutil.copy2(source, destination)
            self._log(f"Copied to: {destination}")
            
            # Step 5: Verify hash
            dest_hash = self._calculate_hash(destination)
            if dest_hash != source_hash:
                # Hashes don't match - ABORT
                destination.unlink()  # Delete bad copy
                return False, "Hash verification failed - copy aborted"
            
            self._log(f"Hash verified: {dest_hash[:16]}...")
            
            # Step 6: Delete original (only after verification)
            source.unlink()
            self._log(f"Original removed: {source}")
            
            # Step 7: Log transaction
            self.transaction_log.append({
                'timestamp': datetime.now().isoformat(),
                'source': str(source),
                'destination': str(destination),
                'hash': source_hash,
                'status': 'success'
            })
            
            return True, f"Successfully moved to {destination}"
            
        except Exception as e:
            self._log(f"Error moving file: {e}", "ERROR")
            return False, str(e)
    
    def _get_next_ref_number(self, base_path: Path) -> int:
        """Get next available REF number for conflict resolution."""
        ref_num = 1
        while True:
            test_path = base_path.parent / f"{base_path.stem}_REF{ref_num:03d}.pdf"
            if not test_path.exists():
                return ref_num
            ref_num += 1
    
    def move_to_errors(self, file_path: Path, error_message: str):
        """Move problematic file to Processing Errors folder."""
        if self.dry_run:
            self._log(f"DRY-RUN: Would move {file_path.name} to errors")
            return
        
        try:
            error_dest = self.errors_path / file_path.name
            
            # Handle name collision in errors folder
            counter = 1
            original_ext = file_path.suffix
            while error_dest.exists():
                error_dest = self.errors_path / f"{file_path.stem}_{counter}{original_ext}"
                counter += 1
            
            shutil.move(str(file_path), str(error_dest))
            
            # Create error log file
            error_log = error_dest.with_suffix('.txt')
            with open(error_log, 'w') as f:
                f.write(f"Error: {error_message}\n")
                f.write(f"Original: {file_path}\n")
                f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            
            self._log(f"Moved to errors: {error_dest.name}", "WARN")
            
        except Exception as e:
            self._log(f"Failed to move to errors: {e}", "ERROR")
    
    def process_inbox(self, retry_errors: bool = False) -> Dict:
        """
        Main processing method - the prisoner intake! 😄
        
        Args:
            retry_errors: If True, process files from Processing Errors folder instead of In-Box
        
        Returns stats about processing.
        """
        
        print(f"\n{'='*80}")
        print(f"🏭 INBOX PROCESSOR")
        if retry_errors:
            print(f"🔄 RETRY MODE (Processing files from Processing Errors folder)")
        if self.dry_run:
            print(f"⚠️  DRY-RUN MODE (No files will be moved)")
        print(f"{'='*80}\n")
        
        # Setup inbox structure
        self.setup_inbox()
        
        # Scan for files
        if retry_errors:
            print(f"📁 Scanning Processing Errors folder: {self.errors_path}")
            files_to_process = self.scan_errors()
            print(f"   Found {len(files_to_process)} files to retry\n")
        else:
            print(f"📁 Scanning inbox: {self.inbox_path}")
            files_to_process = self.scan_inbox()
            print(f"   Found {len(files_to_process)} files to process\n")
        
        # Notify if new files found
        if len(files_to_process) > 0:
            notify_new_files(len(files_to_process), "Processing Errors" if retry_errors else "In-Box")
        
        if not files_to_process:
            print(f"✅ Inbox is empty!\n")
            return {'total': 0, 'processed': 0, 'failed': 0}
        
        stats = {
            'total': len(files_to_process),
            'processed': 0,
            'failed': 0,
            'errors': []
        }
        
        # Process each file
        for i, file_path in enumerate(files_to_process, 1):
            print(f"\n{'─'*80}")
            print(f"[{i}/{len(files_to_process)}] Processing: {file_path.name}")
            print(f"{'─'*80}\n")
            
            try:
                # Step 1: Process with DocumentProcessor
                self._log("Analyzing document...")
                result = self.processor.process_document(str(file_path), skip_if_exists=False)
                
                if result.get('status') != 'success':
                    raise Exception(f"Processing failed: {result.get('reason')}")
                
                # Step 2: Generate smart filename
                self._log("Generating smart filename...")
                new_filename = self.generate_smart_filename(result)
                # Preserve original file extension
                original_ext = file_path.suffix
                if not new_filename.endswith(original_ext):
                    new_filename = new_filename.rsplit('.', 1)[0] + original_ext
                print(f"   📝 New name: {new_filename}")
                
                # Step 3: Build destination path
                dest_path = self.build_destination_path(result, new_filename)
                print(f"   📂 Destination: {dest_path}")
                
                # Step 4: Move file to staging (ALWAYS use staging for safety)
                # Workflow: Inbox → Processed (staging) → Final location (via --finalize)
                # If retrying errors, move from Processing Errors to Processed
                staging_path = self.processed_path / new_filename
                self._log("Moving to staging (Processed folder)...")
                success, message = self.safe_move_file(file_path, staging_path)
                
                if success:
                    stats['processed'] += 1
                    print(f"   ✅ Staged: {message}")
                    print(f"   📋 Review in: In-Box/Processed/")
                    print(f"   💡 Run with --finalize to move to permanent location")
                else:
                    raise Exception(message)
                
            except Exception as e:
                stats['failed'] += 1
                stats['errors'].append({
                    'file': file_path.name,
                    'error': str(e)
                })
                print(f"   ❌ Error: {e}")
                self._log(f"Failed: {e}", "ERROR")
                
                # Notify about error
                notify_processing_error(file_path.name, str(e))
                
                # Move to errors folder
                self.move_to_errors(file_path, str(e))
        
        # Final summary
        print(f"\n{'='*80}")
        print(f"📊 PROCESSING COMPLETE")
        print(f"{'='*80}")
        print(f"✅ Processed: {stats['processed']}")
        print(f"❌ Failed: {stats['failed']}")
        print(f"{'='*80}\n")
        
        # Send completion notifications
        if stats['processed'] > 0:
            notify_processing_complete(stats['processed'], staged=self.use_staging)
        
        if self.use_staging and stats['processed'] > 0:
            notify_staged_files_ready(stats['processed'])
        
        # Save transaction log
        if not self.dry_run and self.transaction_log:
            log_file = Path.home() / 'Documents' / f"inbox_transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(log_file, 'w') as f:
                json.dump(self.transaction_log, f, indent=2)
            print(f"📝 Transaction log saved: {log_file}\n")
        
        return stats
    
    def finalize_processed(self) -> Dict:
        """
        Finalize processed files: Move from Processed/ staging to final location.
        
        This is Step 2 of the workflow:
        Step 1: Inbox → Processed (staging) - done by process_inbox()
        Step 2: Processed → Final location - done by finalize_processed()
        
        Returns stats about finalization.
        """
        
        print(f"\n{'='*80}")
        print(f"✅ FINALIZING PROCESSED FILES")
        if self.dry_run:
            print(f"⚠️  DRY-RUN MODE (No files will be moved)")
        print(f"{'='*80}\n")
        
        # Scan Processed folder
        print(f"📁 Scanning Processed folder: {self.processed_path}")
        processed_files = self.scan_processed()
        print(f"   Found {len(processed_files)} files ready to finalize\n")
        
        if not processed_files:
            print(f"✅ No files to finalize!\n")
            return {'total': 0, 'finalized': 0, 'failed': 0}
        
        stats = {
            'total': len(processed_files),
            'finalized': 0,
            'failed': 0,
            'errors': []
        }
        
        # Process each file
        for i, pdf_path in enumerate(processed_files, 1):
            print(f"\n{'─'*80}")
            print(f"[{i}/{len(processed_files)}] Finalizing: {pdf_path.name}")
            print(f"{'─'*80}\n")
            
            try:
                # Get document info from database
                # Files in Processed folder should have current_path pointing to Processed folder
                processed_path_str = str(self.processed_path)
                
                # Try to find by current_path (most reliable - should point to Processed folder)
                result = self.supabase.table('documents').select('*').ilike('current_path', f'%{pdf_path.name}%').execute()
                
                # Filter to find the one in Processed folder
                doc_data = None
                if result.data:
                    for doc in result.data:
                        current_path = doc.get('current_path', '')
                        if processed_path_str in current_path or 'Processed' in current_path:
                            doc_data = doc
                            break
                
                # Fallback: Try by file_hash
                if not doc_data:
                    file_hash = self._calculate_hash(pdf_path)
                    result = self.supabase.table('documents').select('*').eq('file_hash', file_hash).limit(1).execute()
                    if result.data and len(result.data) > 0:
                        doc_data = result.data[0]
                
                if not doc_data:
                    raise Exception(f"Document not found in database for {pdf_path.name}. File may not have been processed yet.")
                
                # Generate smart filename (should match what's in Processed folder)
                new_filename = self.generate_smart_filename(doc_data)
                
                # Build destination path
                dest_path = self.build_destination_path(doc_data, new_filename)
                print(f"   📂 Final destination: {dest_path}")
                
                # Move from staging to final location
                self._log("Moving to final location...")
                success, message = self.safe_move_file(pdf_path, dest_path)
                
                if success:
                    stats['finalized'] += 1
                    print(f"   ✅ {message}")
                else:
                    raise Exception(message)
                
            except Exception as e:
                stats['failed'] += 1
                stats['errors'].append({
                    'file': pdf_path.name,
                    'error': str(e)
                })
                print(f"   ❌ Error: {e}")
                self._log(f"Failed: {e}", "ERROR")
                
                # Move to errors folder
                self.move_to_errors(pdf_path, str(e))
        
        # Final summary
        print(f"\n{'='*80}")
        print(f"📊 FINALIZATION COMPLETE")
        print(f"{'='*80}")
        print(f"✅ Finalized: {stats['finalized']}")
        print(f"❌ Failed: {stats['failed']}")
        print(f"{'='*80}\n")
        
        return stats


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Process PDFs from In-Box with smart renaming and organization',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
⚠️  SAFETY FIRST: Always run with --dry-run first!

Examples:
  # Step 1: Preview inbox processing (SAFE)
  python inbox_processor.py --dry-run
  
  # Step 1: Process inbox → Processed staging (CAREFUL!)
  python inbox_processor.py --process
  
  # Step 2: Preview finalization (SAFE)
  python inbox_processor.py --finalize --dry-run
  
  # Step 2: Finalize Processed → Final location (CAREFUL!)
  python inbox_processor.py --finalize --process
  
  # Custom inbox location
  python inbox_processor.py --inbox /path/to/inbox --dry-run
  
  # Setup inbox structure only
  python inbox_processor.py --setup-only
        """
    )
    
    parser.add_argument('--dry-run', action='store_true', default=True,
                       help='Preview only, do not move files (DEFAULT)')
    parser.add_argument('--process', action='store_true',
                       help='Actually process files (removes dry-run safety)')
    parser.add_argument('--inbox', type=str,
                       help='Custom inbox path')
    parser.add_argument('--setup-only', action='store_true',
                       help='Just create inbox structure, do not process')
    parser.add_argument('--finalize', action='store_true',
                       help='Finalize processed files: Move from Processed/ to final location (Step 2)')
    parser.add_argument('--yes', action='store_true',
                       help='Skip confirmation prompt (use for automated/API calls)')
    parser.add_argument('--retry-errors', action='store_true',
                       help='Retry processing files from Processing Errors folder')
    
    args = parser.parse_args()
    
    # Determine dry-run mode
    dry_run = not args.process  # Default is dry-run unless --process specified
    
    if not dry_run and not args.yes:
        print("\n⚠️  WARNING: You are about to move real files!")
        print("   This is NOT a dry-run.")
        response = input("\n   Type 'YES' to continue: ")
        if response != 'YES':
            print("   Aborted.")
            sys.exit(0)
    
    # Create processor
    processor = InboxProcessor(inbox_path=args.inbox, dry_run=dry_run)
    
    if args.setup_only:
        processor.setup_inbox()
        sys.exit(0)
    
    # Handle finalize mode (Step 2: Processed → Final location)
    if args.finalize:
        if not dry_run and not args.yes:
            print("\n⚠️  WARNING: You are about to move files from Processed to final locations!")
            print("   This is NOT a dry-run.")
            response = input("\n   Type 'YES' to continue: ")
            if response != 'YES':
                print("   Aborted.")
                sys.exit(0)
        
        stats = processor.finalize_processed()
        sys.exit(0 if stats['failed'] == 0 else 1)
    
    # Process inbox (Step 1: Inbox → Processed staging)
    # Or retry errors if requested
    if args.retry_errors:
        stats = processor.process_inbox(retry_errors=True)
    else:
        stats = processor.process_inbox()
    
    sys.exit(0 if stats['failed'] == 0 else 1)


if __name__ == "__main__":
    main()
