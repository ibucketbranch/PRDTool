#!/usr/bin/env python3
"""
Process ALL important document types from Google Drive.
Handles: PDF, DOCX, XLSX, PPTX, TXT, RTF
Organizes them the same way as PDFs - into bins with AI categorization.
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from document_processor import DocumentProcessor

google_drive_path = "/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive"

# Important file extensions to process
IMPORTANT_EXTENSIONS = {
    '.pdf',  # Already supported
    '.docx', '.xlsx', '.pptx',  # Modern Office (need to add support)
    '.txt', '.rtf',  # Text files (easy to add)
    # Legacy formats - lower priority
    # '.doc', '.xls', '.ppt',  # Would need conversion
}

SKIP_PATTERNS = [
    '.DS_Store', '.git', 'node_modules', '__pycache__',
    '.build', '.pbxindex', '.pbxbtree', '.pbxsymbols',
    'build/', '.xcodeproj/', '.xcworkspace/',
    'My Code Projects/',  # Code projects don't need tracking
]

def find_important_files():
    """Find all important document files in Google Drive."""
    print("="*80)
    print("🔍 FINDING IMPORTANT DOCUMENTS IN GOOGLE DRIVE")
    print("="*80)
    
    files_by_type = {ext: [] for ext in IMPORTANT_EXTENSIONS}
    
    for root, dirs, files in os.walk(google_drive_path):
        dirs[:] = [d for d in dirs if not any(pattern in d for pattern in SKIP_PATTERNS)]
        
        for file in files:
            if file.startswith('.'):
                continue
            
            if any(pattern in file for pattern in SKIP_PATTERNS):
                continue
            
            ext = os.path.splitext(file)[1].lower()
            if ext in IMPORTANT_EXTENSIONS:
                file_path = os.path.join(root, file)
                files_by_type[ext].append(file_path)
    
    total = sum(len(files) for files in files_by_type.values())
    
    print(f"\n📊 Found {total} important documents:")
    for ext, files in sorted(files_by_type.items(), key=lambda x: len(x[1]), reverse=True):
        if files:
            print(f"   {ext}: {len(files)} files")
    
    return files_by_type

def process_files(files_by_type, processor):
    """Process files by type."""
    print(f"\n{'='*80}")
    print("📦 PROCESSING FILES")
    print(f"{'='*80}")
    
    processed = 0
    skipped = 0
    errors = 0
    
    # Process all supported file types
    supported_types = ['.pdf', '.docx', '.xlsx', '.pptx', '.txt', '.rtf']
    
    for ext in supported_types:
        if ext in files_by_type and files_by_type[ext]:
            files = files_by_type[ext]
            print(f"\n📄 Processing {len(files)} {ext.upper()} files...")
            
            for file_path in files:
                try:
                    result = processor.process_document(file_path, skip_if_exists=True)
                    if result.get('status') == 'success':
                        processed += 1
                    elif result.get('status') == 'skipped':
                        skipped += 1
                    else:
                        errors += 1
                        if result.get('error'):
                            print(f"   ⚠️  {os.path.basename(file_path)}: {result.get('error')}")
                except Exception as e:
                    print(f"   ❌ Error processing {os.path.basename(file_path)}: {e}")
                    errors += 1
    
    # Show unsupported types
    unsupported_types = {ext: files for ext, files in files_by_type.items() 
                        if ext not in supported_types and files}
    
    if unsupported_types:
        print(f"\n⚠️  Unsupported file types (need libraries installed):")
        for ext, files in sorted(unsupported_types.items(), key=lambda x: len(x[1]), reverse=True):
            print(f"   {ext}: {len(files)} files")
            if ext == '.doc':
                print(f"      Install: pip install python-docx (then convert .doc to .docx)")
            elif ext == '.xls':
                print(f"      Install: pip install openpyxl (then convert .xls to .xlsx)")
            elif ext == '.ppt':
                print(f"      Install: pip install python-pptx (then convert .ppt to .pptx)")
    
    print(f"\n{'='*80}")
    print("📊 SUMMARY")
    print(f"{'='*80}")
    print(f"  Processed: {processed}")
    print(f"  Skipped (already in DB): {skipped}")
    print(f"  Errors: {errors}")
    
    if unsupported_types:
        total_other = sum(len(files) for files in unsupported_types.values())
        print(f"\n  ⚠️  {total_other} files need support added for other file types")
        print(f"     See: scripts/organize_other_file_types_plan.md")
    
    return processed, skipped, errors

def main():
    print("="*80)
    print("📋 PROCESS ALL GOOGLE DRIVE DOCUMENTS")
    print("="*80)
    
    # Find files
    files_by_type = find_important_files()
    
    total = sum(len(files) for files in files_by_type.values())
    if total == 0:
        print("\n❌ No important documents found")
        return
    
    # Initialize processor
    print(f"\n🤖 Initializing document processor...")
    processor = DocumentProcessor()
    
    # Process files
    processed, skipped, errors = process_files(files_by_type, processor)
    
    print(f"\n{'='*80}")
    print("✅ Processing complete")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
