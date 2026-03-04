import os
import subprocess
from pathlib import Path
from collections import defaultdict

def get_image_info():
    # Target Google Drive path to EXCLUDE from search
    gdrive_base = "/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive"
    
    print(f"🔍 Scanning for images outside of Google Drive...")
    
    # Use mdfind for speed
    try:
        cmd = ["mdfind", "kMDItemContentTypeTree == 'public.image'", "-onlyin", "/Users/michaelvalderrama"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        paths = result.stdout.splitlines()
    except Exception as e:
        print(f"Error running mdfind: {e}")
        return []

    # Exclude system folders and already in GDrive
    excluded_patterns = [
        "/Library/",
        "/Applications/",
        "/.git/",
        "/.cursor/",
        "/.Trash/",
        "/node_modules/",
        gdrive_base
    ]

    folders = defaultdict(list)
    total_size = 0
    total_count = 0

    for path in paths:
        if any(pattern in path for pattern in excluded_patterns):
            continue
        
        try:
            stat = os.stat(path)
            size = stat.st_size
            parent = os.path.dirname(path)
            folders[parent].append({"path": path, "size": size})
            total_size += size
            total_count += 1
        except:
            continue

    # Sort folders by count
    sorted_folders = sorted(folders.items(), key=lambda x: len(x[1]), reverse=True)

    print("\n" + "="*80)
    print("📸 IMAGE DISCOVERY REPORT")
    print("="*80)
    print(f"Total images found: {total_count}")
    print(f"Total size:         {total_size / (1024*1024*1024):.2f} GB")
    print("="*80)
    
    print("\nTop Folders containing images:")
    for folder, files in sorted_folders[:20]:
        folder_size = sum(f['size'] for f in files)
        print(f" - {len(files):>5} images | {folder_size / (1024*1024):>8.2f} MB | {folder}")

    # Save full report
    with open('/tmp/image_discovery_report.json', 'w') as f:
        import json
        json.dump({
            "total_count": total_count,
            "total_size_gb": total_size / (1024*1024*1024),
            "folders": {k: {"count": len(v), "size_mb": sum(f['size'] for f in v) / (1024*1024)} for k, v in folders.items()}
        }, f, indent=2)

    print(f"\nFull discovery data saved to: /tmp/image_discovery_report.json")

if __name__ == "__main__":
    get_image_info()
