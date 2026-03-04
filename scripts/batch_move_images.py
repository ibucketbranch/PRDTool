import os
import shutil
import json
from pathlib import Path

def main():
    list_file = '/tmp/gdrive_outside_images.txt'
    target_root = "/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs/Documents/Google Pictures/From_GDrive_Unsorted"
    
    if not os.path.exists(list_file):
        print("Error: List file not found.")
        return

    with open(list_file, 'r') as f:
        paths = [line.strip() for line in f if line.strip()]

    print(f"🚀 Moving {len(paths)} images from Google Drive list to iCloud...")

    moved_count = 0
    total_size = 0
    
    for source_path in paths:
        if not os.path.exists(source_path):
            continue
            
        file_name = os.path.basename(source_path)
        ext = os.path.splitext(file_name)[1].lower()
        
        try:
            stat = os.stat(source_path)
            if stat.st_size == 0:
                continue
                
            dest_name = file_name
            dest_path = os.path.join(target_root, dest_name)
            
            # Handle name collisions
            counter = 1
            while os.path.exists(dest_path):
                name_stem = Path(file_name).stem
                dest_path = os.path.join(target_root, f"{name_stem}_{counter}{ext}")
                counter += 1
            
            # Execute move
            shutil.move(source_path, dest_path)
            moved_count += 1
            total_size += stat.st_size
            
            if moved_count % 100 == 0:
                print(f" ✅ Moved {moved_count}/{len(paths)} images...")
        except Exception as e:
            # We skip errors silently to keep moving
            pass

    print("\n" + "="*80)
    print("✨ BATCH MOVE COMPLETE")
    print("="*80)
    print(f"Total images moved to iCloud: {moved_count}")
    print(f"Total size:                   {total_size / (1024*1024):.2f} MB")
    print(f"Destination:                  {target_root}")
    print("="*80)

if __name__ == "__main__":
    main()
