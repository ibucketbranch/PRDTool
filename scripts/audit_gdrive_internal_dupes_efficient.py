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

def find_internal_gdrive_duplicates_efficient():
    gdrive_root = "/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive"
    print(f"🔍 Efficient Audit of Google Drive for internal duplicates...")
    print(f"Target: {gdrive_root}")
    
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.tiff', '.webp', '.heic', '.bmp'}
    
    # Junk patterns to skip
    excluded_patterns = [
        "/node_modules/", "/.git/", "/build/", "/dist/", 
        "/public/images/", "/assets/", "/icons/", "/.cursor/", 
        "/.Trash/", "/.sync/", "/.temp/"
    ]

    # Step 1: Group by (name, size) to find candidates
    print("🚀 Phase 1: Identifying duplicate candidates by name and size...")
    candidates_map = defaultdict(list)
    total_found = 0
    
    for root, dirs, files in os.walk(gdrive_root):
        if any(p in root for p in excluded_patterns):
            continue
            
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in image_extensions:
                file_path = os.path.join(root, file)
                
                # Check for filename noise
                if any(x in file.lower() for x in ['icon', 'favicon', 'logo-', 'avatar', 'sprite']):
                    continue
                
                try:
                    size = os.path.getsize(file_path)
                    if size == 0: continue
                    
                    candidates_map[(file, size)].append(file_path)
                    total_found += 1
                    if total_found % 5000 == 0:
                        print(f"  Scanned {total_found} images...")
                except:
                    continue

    # Step 2: Only hash files that share (name, size) with at least one other file
    print("🚀 Phase 2: Verifying candidates with deep hashing...")
    
    duplicate_sets = []
    hash_to_files = defaultdict(list)
    
    potential_dup_files = []
    for key, paths in candidates_map.items():
        if len(paths) > 1:
            potential_dup_files.extend(paths)
            
    print(f"  Found {len(potential_dup_files)} candidate files to hash (out of {total_found} total).")
    
    for i, path in enumerate(potential_dup_files, 1):
        f_hash = get_file_hash(path)
        if f_hash:
            hash_to_files[f_hash].append(path)
        if i % 100 == 0:
            print(f"  Hashed {i}/{len(potential_dup_files)} files...")

    # Step 3: Identify confirmed duplicates
    final_duplicates = {h: paths for h, paths in hash_to_files.items() if len(paths) > 1}
    
    total_dups_count = sum(len(paths) - 1 for paths in final_duplicates.values())
    wasted_space = sum(os.path.getsize(paths[0]) * (len(paths) - 1) for paths in final_duplicates.values())

    print("\n" + "="*80)
    print("📊 INTERNAL GOOGLE DRIVE DUPLICATE REPORT (EFFICIENT)")
    print("="*80)
    print(f"Total Images Scanned:     {total_found}")
    print(f"Duplicate Files Found:    {total_dups_count}")
    print(f"Redundant Space Used:     {wasted_space / (1024*1024):.2f} MB")
    print("="*80)

    # Prepare detailed report
    detailed_report = []
    for h, paths in final_duplicates.items():
        size = os.path.getsize(paths[0])
        detailed_report.append({
            "hash": h,
            "count": len(paths),
            "size_per_file": size,
            "files": [{"path": p, "name": os.path.basename(p), "size": size} for p in paths]
        })

    # Sort by wasted space
    detailed_report.sort(key=lambda x: x['size_per_file'] * (x['count']-1), reverse=True)

    print("\nTop 15 Duplicate Sets (by space wasted):")
    for entry in detailed_report[:15]:
        waste = (entry['size_per_file'] * (entry['count'] - 1)) / (1024*1024)
        print(f" - {entry['count']} copies | Waste: {waste:>8.2f} MB | {entry['files'][0]['name']}")
        for f in entry['files']:
            rel = os.path.relpath(f['path'], gdrive_root)
            print(f"    📍 {rel}")

    # Save to file
    output_path = '/tmp/gdrive_internal_dupes_efficient.json'
    with open(output_path, 'w') as f:
        json.dump(detailed_report, f, indent=2)

    print(f"\nFull duplicate audit saved to: {output_path}")

if __name__ == "__main__":
    find_internal_gdrive_duplicates_efficient()
