#!/usr/bin/env python3
"""
Process important files from Google Drive into database.
Filters out system files, build artifacts, and code projects.
"""
import os
import sys
from pathlib import Path

google_drive_path = "/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive"

# Files/folders to skip
SKIP_PATTERNS = [
    '.DS_Store', '.git', 'node_modules', '__pycache__',
    '.build', '.pbxindex', '.pbxbtree', '.pbxsymbols',
    '.o', '.a', '.dylib', '.framework',
    'build/', '.xcodeproj/', '.xcworkspace/',
    'My Code Projects/',  # Code projects don't need tracking
]

# Important file extensions to process
IMPORTANT_EXTENSIONS = {
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.txt', '.rtf', '.pages', '.numbers', '.key',
    '.zip', '.rar', '.7z'
}

def find_important_files():
    """Find important files that should be processed."""
    print("="*80)
    print("🔍 FINDING IMPORTANT FILES IN GOOGLE DRIVE")
    print("="*80)
    
    important_files = []
    skipped = 0
    
    for root, dirs, files in os.walk(google_drive_path):
        # Filter dirs to skip
        dirs[:] = [d for d in dirs if not any(pattern in d for pattern in SKIP_PATTERNS)]
        
        for file in files:
            if file.startswith('.'):
                continue
            
            # Skip system files
            if any(pattern in file for pattern in SKIP_PATTERNS):
                skipped += 1
                continue
            
            file_path = os.path.join(root, file)
            ext = os.path.splitext(file)[1].lower()
            
            # Only process important file types
            if ext in IMPORTANT_EXTENSIONS:
                important_files.append(file_path)
    
    print(f"\n📊 Results:")
    print(f"   Important files to process: {len(important_files)}")
    print(f"   Skipped (system/build files): {skipped}")
    
    return important_files

if __name__ == "__main__":
    files = find_important_files()
    print(f"\n💡 To process these files, run:")
    print(f"   python3 document_processor.py --path '{google_drive_path}' --filter-important")
