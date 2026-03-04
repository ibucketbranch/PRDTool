import os
import subprocess
from pathlib import Path
from collections import defaultdict
import json

def get_image_info():
    gdrive_base = "/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive"
    
    print(f"🔍 Refining image discovery (excluding 0-byte files and junk)...")
    
    try:
        cmd = ["mdfind", "kMDItemContentTypeTree == 'public.image'", "-onlyin", "/Users/michaelvalderrama"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        paths = result.stdout.splitlines()
    except Exception as e:
        print(f"Error running mdfind: {e}")
        return

    excluded_patterns = [
        "/Library/",
        "/Applications/",
        "/.git/",
        "/.cursor/",
        "/.Trash/",
        "/node_modules/",
        "/site-packages/",
        "/venv/",
        "/build/",
        "/public/images/", # Usually website assets
        gdrive_base
    ]

    folders = defaultdict(list)
    total_size = 0
    total_count = 0
    skipped_0byte = 0

    for path in paths:
        if any(pattern in path for pattern in excluded_patterns):
            continue
        
        try:
            stat = os.stat(path)
            size = stat.st_size
            if size == 0:
                skipped_0byte += 1
                continue
                
            parent = os.path.dirname(path)
            folders[parent].append({"path": path, "size": size, "name": os.path.basename(path)})
            total_size += size
            total_count += 1
        except:
            continue

    sorted_folders = sorted(folders.items(), key=lambda x: len(x[1]), reverse=True)

    print("\n" + "="*80)
    print("📸 REFINED IMAGE DISCOVERY REPORT")
    print("="*80)
    print(f"Total images found: {total_count}")
    print(f"Total size:         {total_size / (1024*1024):.2f} MB")
    print(f"Skipped 0-byte:     {skipped_0byte}")
    print("="*80)
    
    print("\nTop Folders containing images:")
    for folder, files in sorted_folders[:20]:
        folder_size = sum(f['size'] for f in files)
        print(f" - {len(files):>5} images | {folder_size / (1024*1024):>8.2f} MB | {folder}")

    # Save finalized move list
    move_list = []
    for folder, files in folders.items():
        for f in files:
            move_list.append(f)

    with open('/tmp/images_to_move.json', 'w') as f:
        json.dump(move_list, f, indent=2)

    print(f"\nFinal list of {len(move_list)} image paths saved to: /tmp/images_to_move.json")

if __name__ == "__main__":
    get_image_info()
