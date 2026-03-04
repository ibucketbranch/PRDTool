#!/usr/bin/env python3
"""
Reprocess documents by priority category order.
Processes: Resumes → Bank Statements → Tax Docs → Legal → etc.
Uses new intelligent categorization that prioritizes filename and content over messy paths.

🛡️ FILE SAFETY GUARANTEE:
- This script NEVER deletes, moves, renames, or modifies files
- It ONLY reads files and updates database records
- Your files remain completely untouched on disk
- All file operations are read-only
"""

import os
import sys
from pathlib import Path
from typing import List, Dict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from document_processor import DocumentProcessor

# Priority order for reprocessing
PRIORITY_CATEGORIES = [
    {
        'name': 'Resumes',
        'keywords': ['resume', 'cv', 'curriculum vitae'],
        'category_match': 'employment',
        'description': 'Resumes and CVs'
    },
    {
        'name': 'Bank Statements',
        'keywords': ['bank statement', 'bofa', 'bank of america', 'chase', 'wells fargo', 
                     'account activity', 'account details', 'savings account', 'checking account'],
        'category_match': 'bank_statement',
        'description': 'Bank statements and account activity'
    },
    {
        'name': 'Financial Statements',
        'keywords': ['financial statement', 'balance sheet', 'income statement', 
                    'fidelity', 'investment', 'portfolio'],
        'category_match': 'bank_statement',  # Similar category
        'description': 'Financial and investment statements'
    },
    {
        'name': 'Tax Documents',
        'keywords': ['w2', '1099', '1040', 'tax return', 'irs', 'form 1040', 'w-2', '1099-'],
        'category_match': 'tax_document',
        'description': 'Tax forms and returns'
    },
    {
        'name': 'Legal Documents',
        'keywords': ['legal', 'court', 'divorce', 'lawsuit', 'attorney', 'lawyer', 
                     'settlement', 'order', 'judgment'],
        'category_match': 'legal_document',
        'description': 'Legal and court documents'
    },
    {
        'name': 'Vehicle Documents',
        'keywords': ['vehicle', 'registration', 'dmv', 'insurance', 'auto', 'car'],
        'category_match': ['vehicle_registration', 'vehicle_insurance', 'vehicle_maintenance'],
        'description': 'Vehicle-related documents'
    },
    {
        'name': 'Medical Records',
        'keywords': ['medical', 'health', 'prescription', 'doctor', 'hospital', 'clinic'],
        'category_match': 'medical_record',
        'description': 'Medical and health records'
    },
    {
        'name': 'Property Documents',
        'keywords': ['property', 'real estate', 'mortgage', 'deed', 'title'],
        'category_match': 'property_document',
        'description': 'Property and real estate documents'
    },
]

def find_pdfs_by_keywords(keywords: List[str]) -> List[str]:
    """Find ALL PDF files on disk matching keywords in filename or path."""
    print("   Scanning file system for PDFs...")
    
    # Base directories to search - where your PDFs actually are
    home = Path.home()  # /Users/michaelvalderrama
    search_paths = [
        home / "Library" / "Mobile Documents" / "com~apple~CloudDocs",  # iCloud Drive (most PDFs here)
        home / "Documents",
        home / "Downloads",
        home / "Websites",  # Also check Websites folder
    ]
    
    all_pdfs = set()
    
    for search_path in search_paths:
        if not search_path.exists():
            continue
        
        print(f"   Searching: {search_path}")
        try:
            # Search for PDFs recursively
            for pdf_path in search_path.rglob("*.pdf"):
                # Skip system folders
                if any(skip in str(pdf_path) for skip in ['node_modules', '.git', '.Trash', 'Library/Caches']):
                    continue
                
                # Check if filename or path contains any keyword
                path_lower = str(pdf_path).lower()
                name_lower = pdf_path.name.lower()
                
                for keyword in keywords:
                    if keyword.lower() in name_lower or keyword.lower() in path_lower:
                        all_pdfs.add(str(pdf_path))
                        break
        except Exception as e:
            print(f"   Warning: Error searching {search_path}: {e}")
    
    return sorted(list(all_pdfs))

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Reprocess documents by priority category with intelligent categorization'
    )
    parser.add_argument('--category', type=str, choices=[c['name'].lower().replace(' ', '_') for c in PRIORITY_CATEGORIES] + ['all'],
                       default='all', help='Category to process (default: all)')
    parser.add_argument('--limit', type=int, default=None, help='Limit number of documents per category')
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("🔄 PRIORITY REPROCESSING - Intelligent Categorization")
    print("=" * 80)
    print("")
    print("🛡️  FILE SAFETY GUARANTEE:")
    print("   ✅ This script NEVER deletes, moves, renames, or modifies files")
    print("   ✅ It ONLY reads files and updates database records")
    print("   ✅ Your files remain completely untouched on disk")
    print("   ✅ All file operations are read-only")
    print("")
    print("New system prioritizes FILENAME and CONTENT over messy paths.")
    print("")
    
    # Initialize processor
    processor = DocumentProcessor(
        groq_api_key=os.getenv("GROQ_API_KEY"),
        gemini_api_key=os.getenv("GEMINI_API_KEY"),
        llm_provider=os.getenv("LLM_PROVIDER", "gemini")
    )
    
    total_processed = 0
    total_skipped = 0
    total_failed = 0
    
    # Determine which categories to process
    if args.category == 'all':
        categories_to_process = PRIORITY_CATEGORIES
        print("Processing all categories in priority order:")
        for i, cat in enumerate(PRIORITY_CATEGORIES, 1):
            print(f"  {i}. {cat['name']}")
        print("")
    else:
        # Find matching category
        category_name = args.category.replace('_', ' ').title()
        categories_to_process = [c for c in PRIORITY_CATEGORIES if c['name'].lower() == category_name.lower()]
        if not categories_to_process:
            print(f"❌ Category '{args.category}' not found")
            return
    
    # Process each priority category
    for category_info in categories_to_process:
        category_name = category_info['name']
        keywords = category_info['keywords']
        description = category_info['description']
        
        print("=" * 80)
        print(f"📁 Processing: {category_name} ({description})")
        print("=" * 80)
        print("")
        
        # Find ALL PDFs matching this category on disk
        print(f"🔍 Finding {category_name.lower()}...")
        pdf_files = find_pdfs_by_keywords(keywords)
        
        if not pdf_files:
            print(f"   ⚠️  No PDFs found for {category_name}")
            print("")
            continue
        
        print(f"   ✓ Found {len(pdf_files)} PDF files")
        
        # Apply limit if specified
        if args.limit and len(pdf_files) > args.limit:
            print(f"   ⚠️  Limiting to first {args.limit} files")
            pdf_files = pdf_files[:args.limit]
        
        print("")
        
        # Process each PDF file
        category_processed = 0
        category_skipped = 0
        category_failed = 0
        
        for i, file_path in enumerate(pdf_files, 1):
            if not os.path.exists(file_path):
                print(f"[{i}/{len(pdf_files)}] ⚠️  File not found: {Path(file_path).name}")
                category_skipped += 1
                total_skipped += 1
                continue
            
            file_name = Path(file_path).name
            print(f"[{i}/{len(pdf_files)}] Processing: {file_name}")
            print(f"   Path: {file_path[:80]}..." if len(file_path) > 80 else f"   Path: {file_path}")
            
            try:
                # Reprocess with new intelligent categorization
                result = processor.process_document(file_path, skip_if_exists=False)
                
                if result.get('status') == 'success':
                    category_processed += 1
                    total_processed += 1
                    new_category = result.get('category', 'unknown')
                    print(f"   ✅ Success → Category: {new_category}")
                elif result.get('status') == 'skipped':
                    category_skipped += 1
                    total_skipped += 1
                    print(f"   ⏭️  Skipped: {result.get('reason', 'unknown')}")
                else:
                    category_failed += 1
                    total_failed += 1
                    print(f"   ❌ Failed: {result.get('reason', 'unknown')}")
            except Exception as e:
                category_failed += 1
                total_failed += 1
                print(f"   ❌ Error: {e}")
            
            print("")
        
        # Category summary
        print(f"   📊 {category_name} Summary:")
        print(f"      ✅ Processed: {category_processed}")
        print(f"      ⏭️  Skipped: {category_skipped}")
        print(f"      ❌ Failed: {category_failed}")
        print("")
    
    # Final summary
    print("=" * 80)
    print("✅ REPROCESSING COMPLETE")
    print("=" * 80)
    print(f"   ✅ Total Processed: {total_processed}")
    print(f"   ⏭️  Total Skipped: {total_skipped}")
    print(f"   ❌ Total Failed: {total_failed}")
    print("")
    print("All documents have been reprocessed with intelligent categorization")
    print("that prioritizes filename and content over messy paths.")
    print("")

if __name__ == "__main__":
    main()
