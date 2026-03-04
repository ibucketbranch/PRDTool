#!/usr/bin/env python3
"""
Simple Direct PDF Processor - Process PDFs from a list file using the existing document_processor
"""

import os
import sys
from pathlib import Path
from datetime import datetime

# Set environment variables
# Use env: export GEMINI_API_KEY="your_key"
# Use env: export GROQ_API_KEY="your_key"
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
os.environ['LLM_PROVIDER'] = 'gemini'

from document_processor import DocumentProcessor

def main():
    if len(sys.argv) < 2:
        print("Usage: python simple_direct_processor.py <pdf_list_file> [max_files]")
        sys.exit(1)
    
    pdf_list_file = Path(sys.argv[1])
    max_files = int(sys.argv[2]) if len(sys.argv) > 2 else None
    
    # Load PDF list
    with open(pdf_list_file) as f:
        pdf_paths = [line.strip() for line in f if line.strip()]
    
    print(f"📋 Loaded {len(pdf_paths)} PDFs from {pdf_list_file.name}")
    
    if max_files:
        pdf_paths = pdf_paths[:max_files]
        print(f"   Processing first {max_files} files")
    
    # Initialize processor
    print("\n🚀 Initializing document processor...")
    processor = DocumentProcessor()
    
    # Process each PDF
    stats = {'success': 0, 'errors': 0, 'skipped': 0}
    
    print(f"\n📦 Processing {len(pdf_paths)} PDFs...\n")
    
    for i, pdf_path in enumerate(pdf_paths, 1):
        path = Path(pdf_path)
        
        if not path.exists():
            print(f"[{i}/{len(pdf_paths)}] ⏭️  SKIP: {path.name} (not found)")
            stats['skipped'] += 1
            continue
        
        print(f"[{i}/{len(pdf_paths)}] 🔄 {path.name[:60]}...")
        
        try:
            result = processor.process_document(str(path))
            
            if result and result.get('success'):
                stats['success'] += 1
                doc_id = result.get('document_id', 'unknown')
                category = result.get('category', 'unknown')
                print(f"   ✅ Success - ID: {doc_id[:8]}... | Category: {category}")
            elif result and result.get('document_id'):
                # Document was saved even if success flag not set
                stats['success'] += 1
                doc_id = result.get('document_id', 'unknown')
                category = result.get('category', 'unknown')
                print(f"   ✅ Success - ID: {doc_id[:8]}... | Category: {category}")
            else:
                stats['errors'] += 1
                error = result.get('error', 'No document_id returned') if result else 'No result returned'
                print(f"   ❌ Failed: {error}")
        
        except Exception as e:
            stats['errors'] += 1
            print(f"   ❌ Exception: {e}")
        
        # Progress update every 10 files
        if i % 10 == 0:
            print(f"\n📊 Progress: {stats['success']} success, {stats['errors']} errors, {stats['skipped']} skipped\n")
    
    # Final stats
    print("\n" + "="*70)
    print("PROCESSING COMPLETE")
    print("="*70)
    print(f"✅ Successful: {stats['success']}")
    print(f"❌ Errors: {stats['errors']}")
    print(f"⏭️  Skipped: {stats['skipped']}")
    print(f"📊 Total: {len(pdf_paths)}")
    print()

if __name__ == "__main__":
    main()
