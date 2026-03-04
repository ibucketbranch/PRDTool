#!/usr/bin/env python3
"""
Fast PDF Discovery - Find all PDFs and cache the list
Scans specified user directories and iCloud, ignoring system files.
"""

import os
import json
import argparse
from pathlib import Path
from datetime import datetime

# Directories to ignore to avoid system files and churn
IGNORE_DIRS = {
    'Library', 'Applications', 'System', 'bin', 'sbin', 'usr', 'var', 'tmp', 
    '.git', '.vscode', '.cursor', 'node_modules', 'venv', '.env', '__pycache__',
    'Music', 'Pictures', 'Movies', 'Public' # Typically media, not docs
}

# Allow-list for Library (specifically for iCloud)
ALLOW_LIBRARY_PATHS = [
    'Mobile Documents/com~apple~CloudDocs'
]

def is_ignored(path_part: str) -> bool:
    return path_part in IGNORE_DIRS or path_part.startswith('.')

def discover_pdfs(root_paths: list[str], cache_file: str = None):
    """
    Quickly discover all PDFs in multiple paths and cache them.
    Sorts by NEWEST/MOST RECENTLY ACCESSED first.
    """
    
    if cache_file is None:
        cache_file = Path.home() / '.document_system' / 'pdf_cache.json'
    else:
        cache_file = Path(cache_file)
    
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    
    pdfs = []
    total_size = 0
    seen_paths = set()

    for root_path in root_paths:
        root = Path(root_path).expanduser()
        print(f"🔍 Discovering PDFs in: {root}")
        
        for root_dir, dirs, files in os.walk(root):
            # Smart filtering of directories
            # 1. Remove hidden dirs
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            # NOTE: User explicitly requested to NOT exclude Library/Applications
            # "all data is good data"
            
            for file in files:
                if file.startswith('.'):
                    continue
                
                if file.lower().endswith('.pdf'):
                    pdf_path = Path(root_dir) / file
                    
                    # Avoid duplicates if roots overlap
                    if str(pdf_path) in seen_paths:
                        continue
                    seen_paths.add(str(pdf_path))
                    
                    try:
                        stat = pdf_path.stat()
                        pdfs.append({
                            'path': str(pdf_path),
                            'name': file,
                            'size': stat.st_size,
                            'modified': stat.st_mtime,
                            'accessed': stat.st_atime,
                            'folder': str(pdf_path.parent)
                        })
                        total_size += stat.st_size
                        
                        if len(pdfs) % 100 == 0:
                            print(f"   Found {len(pdfs)} PDFs...", end='\r')
                    except Exception as e:
                        # Permission errors etc.
                        pass
    
    # Sort by MOST RECENTLY ACCESSED
    pdfs.sort(key=lambda x: x['accessed'], reverse=True)
    
    print(f"\n✅ Discovery complete!")
    print(f"   Total PDFs: {len(pdfs)}")
    print(f"   Total size: {total_size / 1024 / 1024:.1f} MB")
    print()
    
    if len(pdfs) > 0:
        print("📊 Top 10 Most Recently Used:")
        for i, pdf in enumerate(pdfs[:10], 1):
            accessed = datetime.fromtimestamp(pdf['accessed']).strftime('%Y-%m-%d %H:%M')
            print(f"   {i}. {pdf['name']}")
            print(f"      📁 {Path(pdf['folder']).name}")
            print(f"      📅 Last accessed: {accessed}")
    print()
    
    cache_data = {
        'discovered_at': datetime.now().isoformat(),
        'roots': root_paths,
        'total_pdfs': len(pdfs),
        'total_size_bytes': total_size,
        'pdfs': pdfs
    }
    
    with open(cache_file, 'w') as f:
        json.dump(cache_data, f, indent=2)
    
    print(f"💾 Cache saved to: {cache_file}")
    print()
    
    return pdfs


def load_cached_pdfs(cache_file: str = None):
    if cache_file is None:
        cache_file = Path.home() / '.document_system' / 'pdf_cache.json'
    else:
        cache_file = Path(cache_file)
    
    if not cache_file.exists():
        return None
    
    with open(cache_file, 'r') as f:
        cache_data = json.load(f)
    return cache_data['pdfs']


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Discover PDFs in specified directories.')
    parser.add_argument('paths', metavar='path', type=str, nargs='*',
                        help='Paths to scan (default: Home and iCloud)')
    parser.add_argument('--load', action='store_true', help='Load cached list')
    
    args = parser.parse_args()
    
    if args.load:
        pdfs = load_cached_pdfs()
        if pdfs:
            print(f"✅ {len(pdfs)} PDFs in cache")
        else:
            print("❌ No cache found")
    else:
        roots = args.paths
        if not roots:
            # Default to Home (carefully filtered) and iCloud
            roots = [
                '/Users/michaelvalderrama',
                '/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs'
            ]
        
        discover_pdfs(roots)
