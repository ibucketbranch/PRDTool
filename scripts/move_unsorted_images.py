import os
import shutil
import json
from pathlib import Path

def main():
    gdrive_root = "/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive"
    target_root = "/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs/Documents/Google Pictures/From_GDrive_Unsorted"
    
    # Exclusion: The main photo collection we want to handle separately
    gdrive_photos_folder = os.path.join(gdrive_root, "Google Photos")
    
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.tiff', '.webp', '.heic', '.bmp'}
    
    # Standard junk to skip
    excluded_patterns = [
        "/node_modules/", "/.git/", "/build/", "/dist/", "/public/images/",
        "/assets/", "/icons/", "/.cursor/", "/.Trash/", "/.sync/", "/.temp/"
    ]

    moved_count = 0
    total_size = 0
    
    print(f"🚀 Moving images OUTSIDE of 'Google Photos' into iCloud...")

    for root, dirs, files in os.walk(gdrive_root):
        # SKIP the main photos folder
        if root.startswith(gdrive_photos_folder):
            continue
            
        # Skip junk folders
        if any(p in root for p in excluded_patterns):
            continue
            
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in image_extensions:
                source_path = os.path.join(root, file)
                try:
                    stat = os.stat(source_path)
                    if stat.st_size == 0:
                        continue
                        
                    # Target path: Flatten into the unsorted folder but preserve filename
                    # We'll use a unique name check to be safe
                    dest_name = file
                    dest_path = os.path.join(target_root, dest_name)
                    
                    # Handle name collisions
                    counter = 1
                    while os.path.exists(dest_path):
                        name_stem = Path(file).stem
                        dest_path = os.path.join(target_root, f"{name_stem}_{counter}{ext}")
                        counter += 1
                    
                    # Execute move
                    shutil.move(source_path, dest_path)
                    moved_count += 1
                    total_size += stat.st_size
                    
                    if moved_count % 100 == 0:
                        print(f" ✅ Moved {moved_count} images...")
                except Exception as e:
                    print(f" ❌ Error moving {file}: {e}")

    print("\n" + "="*80)
    print("✨ MOVE COMPLETE")
    print("="*80)
    print(f"Total images moved to iCloud: {moved_count}")
    print(f"Total size:                   {total_size / (1024*1024):.2f} MB")
    print(f"Destination:                  {target_root}")
    print("="*80)

if __name__ == "__main__":
    main()
