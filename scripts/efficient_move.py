import os
import subprocess
import json
from pathlib import Path

def main():
    list_file = '/tmp/gdrive_outside_images.txt'
    target_root = "/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs/Documents/Google Pictures/From_GDrive_Unsorted"
    
    with open(list_file, 'r') as f:
        paths = [line.strip() for line in f if line.strip()]

    print(f"🚀 Moving {len(paths)} images using 'cp' + 'rm' for cloud efficiency...")

    moved_count = 0
    
    for source_path in paths:
        if not os.path.exists(source_path):
            continue
            
        file_name = os.path.basename(source_path)
        ext = os.path.splitext(file_name)[1].lower()
        dest_name = file_name
        dest_path = os.path.join(target_root, dest_name)
        
        # Handle collision
        counter = 1
        while os.path.exists(dest_path):
            name_stem = Path(file_name).stem
            dest_path = os.path.join(target_root, f"{name_stem}_{counter}{ext}")
            counter += 1
            
        try:
            # Use subprocess to run 'cp' which often handles cloud downloads better than python open()
            subprocess.run(['cp', source_path, dest_path], check=True, timeout=60)
            # Only remove if copy succeeded
            os.remove(source_path)
            moved_count += 1
            if moved_count % 10 == 0:
                print(f" ✅ Moved {moved_count}/{len(paths)} images...")
        except Exception as e:
            # Skip if timeout or error
            continue

    print(f"✨ DONE. Moved {moved_count} images.")

if __name__ == "__main__":
    main()
