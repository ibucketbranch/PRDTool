#!/usr/bin/env python3
"""
Retry processing the 5 files that failed due to tsvector size limit.
These files had extracted text > 1MB which exceeded PostgreSQL's limit.
Now that we've fixed the truncation, we can retry them.
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from document_processor import DocumentProcessor

# Files that failed (from log analysis)
FAILED_FILES = [
    "/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive/Desktop Nov19/WEDDING_invites_Confirmed_Final.xlsx",
    "/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive/Desktop Nov19/Copy of Feb MSR C1 Marketing Template.xlsx",
    "/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive/Desktop Nov19/BigfootCA2.pptx",
    "/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive/Desktop Nov19/227268_Datacenterdef_by_storageServices.pptx",
]

def main():
    print("="*80)
    print("🔄 RETRYING FAILED FILES (tsvector size limit)")
    print("="*80)
    print(f"\n📋 Found {len(FAILED_FILES)} files that failed due to text size limit")
    print("   These will now be processed with text truncation fix")
    print("="*80)
    
    processor = DocumentProcessor()
    
    processed = 0
    errors = 0
    
    for i, file_path in enumerate(FAILED_FILES, 1):
        if not os.path.exists(file_path):
            print(f"\n[{i}/{len(FAILED_FILES)}] ⚠️  File not found: {os.path.basename(file_path)}")
            errors += 1
            continue
        
        print(f"\n[{i}/{len(FAILED_FILES)}] Processing: {os.path.basename(file_path)}")
        
        try:
            result = processor.process_document(file_path, skip_if_exists=False)
            if result.get('status') == 'success':
                processed += 1
                print(f"   ✅ Successfully processed")
            else:
                errors += 1
                error_msg = result.get('error', 'Unknown error')
                print(f"   ❌ Error: {error_msg}")
        except Exception as e:
            errors += 1
            print(f"   ❌ Exception: {e}")
    
    print(f"\n{'='*80}")
    print("📊 SUMMARY")
    print(f"{'='*80}")
    print(f"  Processed: {processed}")
    print(f"  Errors: {errors}")
    print(f"  Total: {len(FAILED_FILES)}")
    print(f"\n{'='*80}")

if __name__ == "__main__":
    main()
