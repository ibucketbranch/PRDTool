import os
import hashlib
import json
from collections import defaultdict
from pathlib import Path

def get_file_hash(path):
    """Calculate SHA256 hash of a file."""
    hasher = hashlib.sha256()
    try:
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return None

def find_internal_gdrive_duplicates():
    gdrive_root = "/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive"
    print(f"🔍 Auditing Google Drive for internal duplicates...")
    print(f"Target: {gdrive_root}")
    
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.tiff', '.webp', '.heic', '.bmp'}
    
    # Junk patterns to skip
    excluded_patterns = [
        "/node_modules/", "/.git/", "/build/", "/dist/", 
        "/public/images/", "/assets/", "/icons/", "/.cursor/", 
        "/.Trash/", "/.sync/", "/.temp/"
    ]

    hash_map = defaultdict(list)
    total_scanned = 0
    skipped_junk = 0
    
    # Discovery phase
    print("🚀 Scanning files and calculating hashes...")
    for root, dirs, files in os.walk(gdrive_root):
        if any(p in root for p in excluded_patterns):
            skipped_junk += len(files)
            continue
            
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in image_extensions:
                file_path = os.path.join(root, file)
                
                # Check for filename noise
                if any(x in file.lower() for x in ['icon', 'favicon', 'logo-', 'avatar', 'sprite']):
                    skipped_junk += 1
                    continue
                
                f_hash = get_file_hash(file_path)
                if f_hash:
                    hash_map[f_hash].append({
                        "path": file_path,
                        "name": file,
                        "size": os.path.getsize(file_path)
                    })
                    total_scanned += 1
                    if total_scanned % 500 == 0:
                        print(f"  Processed {total_scanned} images...")

    # Analysis phase
    duplicates = {h: items for h, items in hash_map.items() if len(items) > 1}
    
    total_dups_count = sum(len(items) - 1 for items in duplicates.values())
    wasted_space = sum(items[0]['size'] * (len(items) - 1) for items in duplicates.values())

    print("\n" + "="*80)
    print("📊 INTERNAL GOOGLE DRIVE DUPLICATE REPORT")
    print("="*80)
    print(f"Total Unique Images:      {len(hash_map)}")
    print(f"Total Images Scanned:     {total_scanned}")
    print(f"Duplicate Files Found:    {total_dups_count}")
    print(f"Redundant Space Used:     {wasted_space / (1024*1024):.2f} MB")
    print("="*80)

    # Prepare detailed report
    detailed_report = []
    for h, items in duplicates.items():
        detailed_report.append({
            "hash": h,
            "count": len(items),
            "size_per_file": items[0]['size'],
            "files": items
        })

    # Sort by wasted space (size * (count-1))
    detailed_report.sort(key=lambda x: x['size_per_file'] * (x['count']-1), reverse=True)

    print("\nTop 15 Duplicate Sets (by space wasted):")
    for entry in detailed_report[:15]:
        waste = (entry['size_per_file'] * (entry['count'] - 1)) / (1024*1024)
        print(f" - {entry['count']} copies | Waste: {waste:>8.2f} MB | {entry['files'][0]['name']}")
        for f in entry['files']:
            # Show path relative to GDrive root
            rel = os.path.relpath(f['path'], gdrive_root)
            print(f"    📍 {rel}")

    # Save to file
    output_path = '/tmp/gdrive_internal_dupes.json'
    with open(output_path, 'w') as f:
        json.dump(detailed_report, f, indent=2)

    print(f"\nFull duplicate audit saved to: {output_path}")

if __name__ == "__main__":
    find_internal_gdrive_duplicates()
