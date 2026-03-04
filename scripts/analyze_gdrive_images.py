import os
import json
from pathlib import Path
from collections import defaultdict

def scan_gdrive_images():
    gdrive_root = "/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive"
    print(f"🔍 Scanning Google Drive for 'real' images (filtering noise)...")
    
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.tiff', '.webp', '.heic', '.bmp'}
    
    # Junk patterns to skip
    excluded_patterns = [
        "/node_modules/",
        "/.git/",
        "/build/",
        "/dist/",
        "/public/images/",
        "/assets/",
        "/icons/",
        "/.cursor/",
        "/.Trash/",
        "/.sync/",
        "/.temp/"
    ]

    folders = defaultdict(list)
    total_size = 0
    total_count = 0
    skipped_junk = 0
    skipped_0byte = 0

    for root, dirs, files in os.walk(gdrive_root):
        # Skip directories matching excluded patterns early
        if any(pattern in root for pattern in excluded_patterns):
            skipped_junk += len(files)
            continue
            
        for file in files:
            file_path = os.path.join(root, file)
            ext = os.path.splitext(file)[1].lower()
            
            if ext in image_extensions:
                try:
                    stat = os.stat(file_path)
                    size = stat.st_size
                    
                    if size == 0:
                        skipped_0byte += 1
                        continue
                        
                    # Final check for filename noise (e.g. tiny thumb or icon)
                    # Often "icon", "logo", "bg", "avatar" are junk
                    name_lower = file.lower()
                    if any(x in name_lower for x in ['icon', 'favicon', 'logo-', 'avatar', 'sprite']):
                        skipped_junk += 1
                        continue

                    folders[root].append({
                        "path": file_path,
                        "size": size,
                        "name": file
                    })
                    total_size += size
                    total_count += 1
                except:
                    continue

    # Sort folders by count
    sorted_folders = sorted(folders.items(), key=lambda x: len(x[1]), reverse=True)

    print("\n" + "="*80)
    print("📊 GOOGLE DRIVE IMAGE ANALYSIS REPORT")
    print("="*80)
    print(f"Total 'Real' Images Found: {total_count}")
    print(f"Total Size:               {total_size / (1024*1024):.2f} MB")
    print(f"Filtered (Noise/Junk):    {skipped_junk}")
    print(f"Filtered (Empty Files):   {skipped_0byte}")
    print("="*80)
    
    print("\nTop Image Locations in Google Drive:")
    for folder, files in sorted_folders[:25]:
        folder_size = sum(f['size'] for f in files)
        # Show relative path from GDrive root for readability
        rel_folder = os.path.relpath(folder, gdrive_root)
        print(f" - {len(files):>5} images | {folder_size / (1024*1024):>8.2f} MB | {rel_folder}")

    # Save finalized list for next step
    all_images = []
    for folder, files in folders.items():
        all_images.extend(files)

    output_path = '/tmp/gdrive_images_clean.json'
    with open(output_path, 'w') as f:
        json.dump(all_images, f, indent=2)

    print(f"\nFinal list of {len(all_images)} clean image paths saved to: {output_path}")

if __name__ == "__main__":
    scan_gdrive_images()
