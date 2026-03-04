#!/usr/bin/env python3
"""
Simple Batch Processor - Process PDFs from a single folder (non-recursive)
Fast and simple for testing
"""

import sys
from pathlib import Path
from document_processor import DocumentProcessor

# Set API key
import os
# Use env: export GROQ_API_KEY="your_key"

def process_folder_simple(folder_path: str, batch_size: int = 5):
    """Process PDFs from a single folder (non-recursive)."""
    
    folder = Path(folder_path)
    
    if not folder.exists():
        print(f"❌ Folder not found: {folder}")
        return
    
    # Find PDFs in this folder only (not recursive)
    print(f"\n🔍 Scanning: {folder}")
    pdfs = list(folder.glob('*.pdf'))
    
    if not pdfs:
        print(f"   No PDFs found in this folder")
        return
    
    print(f"   ✅ Found {len(pdfs)} PDF(s)")
    print()
    
    # Process first N files
    batch = pdfs[:batch_size]
    
    print(f"📦 Processing {len(batch)} file(s):\n")
    
    processor = DocumentProcessor()
    
    for i, pdf_path in enumerate(batch, 1):
        print(f"[{i}/{len(batch)}] {pdf_path.name}")
        print(f"   📁 {pdf_path.parent}")
        
        try:
            result = processor.process_document(pdf_path)
            if result:
                print(f"   ✅ Success!\n")
            else:
                print(f"   ⚠️  Returned None\n")
        except Exception as e:
            print(f"   ❌ Error: {e}\n")
    
    remaining = len(pdfs) - len(batch)
    if remaining > 0:
        print(f"\n📊 {len(batch)} processed, {remaining} remaining in this folder")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 simple_batch.py <folder_path> [batch_size]")
        print("\nExample:")
        print('  python3 simple_batch.py "/Users/you/Documents" 5')
        sys.exit(1)
    
    folder_path = sys.argv[1]
    batch_size = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    
    process_folder_simple(folder_path, batch_size)
