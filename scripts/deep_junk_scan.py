import os
import json
from pathlib import Path
from collections import defaultdict

def scan_for_project_junk():
    paths_to_scan = [
        "/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive/Google Pictures",
        "/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs/Documents/Google Pictures"
    ]
    
    print(f"🔍 Deep scanning for project junk (thumbnails, shopping bags, color samples)...")
    
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif'}
    
    # Junk criteria:
    # 1. Size < 100KB (likely thumbnails)
    # 2. Filenames with junk keywords
    junk_keywords = ["bag", "shopping", "matte", "grocery", "merchandise", "coffeebag", "color", "sample", "thumb", "jim-", "pixel"]
    
    folder_junk_stats = defaultdict(lambda: {"count": 0, "size": 0})
    folder_gem_stats = defaultdict(lambda: {"count": 0, "size": 0})
    
    for base_path in paths_to_scan:
        if not os.path.exists(base_path): continue
        
        for root, dirs, files in os.walk(base_path):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in image_extensions:
                    file_path = os.path.join(root, file)
                    try:
                        size = os.path.getsize(file_path)
                        name_lower = file.lower()
                        
                        is_junk = False
                        if size < 100 * 1024: # Less than 100KB
                            is_junk = True
                        if any(kw in name_lower for kw in junk_keywords):
                            is_junk = True
                            
                        rel_dir = os.path.relpath(root, base_path)
                        if is_junk:
                            folder_junk_stats[rel_dir]["count"] += 1
                            folder_junk_stats[rel_dir]["size"] += size
                        else:
                            folder_gem_stats[rel_dir]["count"] += 1
                            folder_gem_stats[rel_dir]["size"] += size
                    except:
                        continue

    print("\n" + "="*80)
    print("📊 POTENTIAL JUNK FOLDERS (High count of small/keyword images)")
    print("="*80)
    print(f"{'Junk Count':>10} | {'Gem Count':>10} | {'Folder Path'}")
    print("-" * 80)
    
    # Sort by junk count
    sorted_folders = sorted(folder_junk_stats.items(), key=lambda x: x[1]["count"], reverse=True)
    
    for folder, stats in sorted_folders[:30]:
        gem_count = folder_gem_stats.get(folder, {}).get("count", 0)
        print(f"{stats['count']:>10,} | {gem_count:>10,} | {folder}")

if __name__ == "__main__":
    scan_for_project_junk()
