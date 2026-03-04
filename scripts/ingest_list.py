#!/usr/bin/env python3
"""
Ingest PDF List
Reads a list of PDF paths (from fast_discover.sh) and creates the JSON cache.
"""

import os
import json
import sys
from pathlib import Path
from datetime import datetime

def ingest_list(list_file: str, cache_file: str = None):
    if cache_file is None:
        cache_file = Path.home() / '.document_system' / 'pdf_cache.json'
    else:
        cache_file = Path(cache_file)
        
    print(f"📖 Reading list from: {list_file}")
    
    with open(list_file, 'r') as f:
        paths = [line.strip() for line in f if line.strip()]
    
    print(f"   Processing {len(paths)} paths...")
    
    pdfs = []
    total_size = 0
    
    for i, path_str in enumerate(paths, 1):
        try:
            path = Path(path_str)
            if not path.exists():
                continue
                
            stat = path.stat()
            pdfs.append({
                'path': str(path),
                'name': path.name,
                'size': stat.st_size,
                'modified': stat.st_mtime,
                'accessed': stat.st_atime,
                'folder': str(path.parent)
            })
            total_size += stat.st_size
            
            if i % 100 == 0:
                print(f"   Processed {i} files...", end='\r')
                
        except Exception:
            pass # Skip inaccessible files
            
    print(f"   Processed {len(paths)} files. Done.")
    
    # Sort by MOST RECENTLY ACCESSED
    pdfs.sort(key=lambda x: x['accessed'], reverse=True)
    
    cache_data = {
        'discovered_at': datetime.now().isoformat(),
        'method': 'fast_discover',
        'total_pdfs': len(pdfs),
        'total_size_bytes': total_size,
        'pdfs': pdfs
    }
    
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_file, 'w') as f:
        json.dump(cache_data, f, indent=2)
        
    print(f"\n✅ Cache saved to: {cache_file}")
    print(f"   Total PDFs: {len(pdfs)}")
    print(f"   Total size: {total_size / 1024 / 1024:.1f} MB")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        list_file = "all_pdfs.txt"
    else:
        list_file = sys.argv[1]
        
    if not os.path.exists(list_file):
        print(f"❌ List file not found: {list_file}")
        sys.exit(1)
        
    ingest_list(list_file)
