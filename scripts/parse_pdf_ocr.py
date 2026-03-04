#!/usr/bin/env python3
"""
OCR-based PDF Parser for conversation text
This handles PDFs where text extraction doesn't work.
"""

import sys
import os
import json
from typing import List, Dict
from pathlib import Path

try:
    from pdf2image import convert_from_path
    import pytesseract
    from PIL import Image
except ImportError:
    print("Required packages not installed. Install with:")
    print("pip install pdf2image pytesseract pillow")
    print("Also need: brew install poppler tesseract")
    sys.exit(1)


def ocr_pdf_page(pdf_path: str, page_num: int) -> str:
    """OCR a single page from PDF."""
    print(f"Processing page {page_num}...", end=' ', flush=True)
    
    try:
        # Convert page to image
        images = convert_from_path(
            pdf_path, 
            first_page=page_num, 
            last_page=page_num,
            dpi=150  # Lower DPI for speed
        )
        
        if images:
            # OCR the image
            text = pytesseract.image_to_string(images[0])
            print(f"✓ ({len(text)} chars)")
            return text
        else:
            print("✗ No image")
            return ""
    except Exception as e:
        print(f"✗ Error: {e}")
        return ""


def ocr_pdf_batch(pdf_path: str, start_page: int, end_page: int, progress_file: str) -> List[str]:
    """OCR a batch of pages."""
    texts = []
    
    # Load existing progress if available
    if os.path.exists(progress_file):
        with open(progress_file, 'r') as f:
            data = json.load(f)
            texts = data.get('pages', [])
            start_page = len(texts) + 1
            print(f"Resuming from page {start_page}")
    
    for page_num in range(start_page, end_page + 1):
        text = ocr_pdf_page(pdf_path, page_num)
        texts.append(text)
        
        # Save progress every 10 pages
        if page_num % 10 == 0:
            with open(progress_file, 'w') as f:
                json.dump({'pages': texts, 'last_page': page_num}, f)
            print(f"Progress saved (page {page_num})")
    
    # Final save
    with open(progress_file, 'w') as f:
        json.dump({'pages': texts, 'last_page': end_page}, f)
    
    return texts


def parse_ocr_text(pages: List[str]) -> List[Dict]:
    """Parse OCR'd text into messages."""
    all_text = '\n\n'.join(pages)
    
    # Save raw OCR output for inspection
    with open('ocr_raw_text.txt', 'w', encoding='utf-8') as f:
        f.write(all_text)
    print(f"\nRaw OCR text saved to: ocr_raw_text.txt ({len(all_text)} chars)")
    
    # Try to parse messages - this is text message format specific
    # Common patterns in exported text messages
    messages = []
    
    lines = all_text.split('\n')
    current_msg = {}
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Look for common message patterns
        # Pattern: "Date Time - Name: Message"
        # Pattern: "Name (Date Time): Message"
        # etc.
        
        # For now, collect all non-empty lines as potential messages
        # User can refine the parser based on the actual format
        if line:
            messages.append({
                'text': line,
                'sender': 'Unknown',
                'date': None
            })
    
    return messages


def main():
    if len(sys.argv) < 2:
        print("Usage: python parse_pdf_ocr.py <pdf_path> [start_page] [end_page]")
        print("\nNote: OCR is slow. Process a few pages first to test:")
        print("  python parse_pdf_ocr.py conversation.pdf 1 5")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    
    # Get PDF info
    try:
        from pdf2image import pdfinfo_from_path
        info = pdfinfo_from_path(pdf_path)
        total_pages = info.get('Pages', 0)
        print(f"PDF has {total_pages} pages")
    except:
        total_pages = 137  # Default from earlier check
    
    # Parse page range
    start_page = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    end_page = int(sys.argv[3]) if len(sys.argv) > 3 else min(10, total_pages)  # Default: first 10 pages
    
    print(f"\nProcessing pages {start_page} to {end_page}")
    print(f"Total pages in PDF: {total_pages}")
    
    if end_page > 10:
        response = input(f"\nWarning: Processing {end_page - start_page + 1} pages will take a long time. Continue? (y/n): ")
        if response.lower() != 'y':
            print("Cancelled.")
            sys.exit(0)
    
    progress_file = 'ocr_progress.json'
    
    print("\nStarting OCR...")
    pages = ocr_pdf_batch(pdf_path, start_page, end_page, progress_file)
    
    print(f"\nOCR complete! Processed {len(pages)} pages")
    print(f"Total text extracted: {sum(len(p) for p in pages)} characters")
    
    # Parse messages
    print("\nParsing messages...")
    messages = parse_ocr_text(pages)
    
    print(f"Found {len(messages)} text segments")
    print("\nNext steps:")
    print("1. Review ocr_raw_text.txt to see the extracted text format")
    print("2. If the format looks good, process all pages:")
    print(f"   python parse_pdf_ocr.py '{pdf_path}' 1 {total_pages}")
    print("3. Then refine the message parsing based on the actual format")


if __name__ == "__main__":
    main()
