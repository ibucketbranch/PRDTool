import os
import shutil
import json
from pathlib import Path

def main():
    list_file = '/tmp/gdrive_all_remaining_images.txt'
    gdrive_root = "/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive"
    master_folder = "Google Pictures"
    master_path_gdrive = os.path.join(gdrive_root, master_folder)
    
    # Target in iCloud
    target_root = "/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs/Documents/Google Pictures"
    
    if not os.path.exists(list_file):
        print("Error: Remaining images list not found.")
        return

    with open(list_file, 'r') as f:
        paths = [line.strip() for line in f if line.strip()]

    print(f"🚀 Evacuating {len(paths)} remaining images from Google Drive to iCloud...")

    moved_count = 0
    skipped_count = 0
    total_size = 0
    
    for source_path in paths:
        if not os.path.exists(source_path):
            skipped_count += 1
            continue
            
        file_name = os.path.basename(source_path)
        # Preserve relative path from Google Pictures root
        # e.g. '2014/04/photo-1.jpeg'
        rel_path = os.path.relpath(source_path, master_path_gdrive)
        dest_path = os.path.join(target_root, rel_path)
        
        # Ensure destination directory exists
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        
        # Handle collision (though unlikely if structure is preserved)
        final_dest = dest_path
        if os.path.exists(final_dest):
            # Check if it's the same file (could use hash, but size is a good proxy here for speed)
            if os.path.getsize(source_path) == os.path.getsize(final_dest):
                # Duplicate already there, just remove from GDrive to clean up
                os.remove(source_path)
                moved_count += 1
                if moved_count % 500 == 0:
                    print(f" ✅ Cleaned up {moved_count} duplicates/moves...")
                continue
            else:
                # Same name, different size - rename
                ext = os.path.splitext(file_name)[1].lower()
                name_stem = Path(file_name).stem
                counter = 1
                while os.path.exists(final_dest):
                    final_dest = os.path.join(os.path.dirname(dest_path), f"{name_stem}__{counter}{ext}")
                    counter += 1
        
        try:
            # Execute move
            shutil.move(source_path, final_dest)
            moved_count += 1
            if moved_count % 500 == 0:
                print(f" ✅ Moved {moved_count}/{len(paths)} images...")
        except Exception as e:
            # print(f" ❌ Error moving {file_name}: {e}")
            pass

    print("\n" + "="*80)
    print("✨ FINAL EVACUATION COMPLETE")
    print("="*80)
    print(f"Total images processed: {moved_count}")
    print(f"Skipped:                {skipped_count}")
    print(f"Destination:            {target_root}")
    print("="*80)

if __name__ == "__main__":
    main()
