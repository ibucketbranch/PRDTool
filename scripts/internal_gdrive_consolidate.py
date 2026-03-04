import os
import shutil
from pathlib import Path

def main():
    gdrive_root = "/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive"
    master_folder_name = "Google Pictures"
    master_path = os.path.join(gdrive_root, master_folder_name)
    old_master_name = "Google Photos"
    old_master_path = os.path.join(gdrive_root, old_master_name)

    print(f"🚀 Starting Internal Google Drive Consolidation...")

    # 1. Rename existing 'Google Photos' to 'Google Pictures' if it exists
    if os.path.exists(old_master_path) and not os.path.exists(master_path):
        print(f"📦 Renaming '{old_master_name}' to '{master_folder_name}'...")
        os.rename(old_master_path, master_path)
    elif not os.path.exists(master_path):
        print(f"📁 Creating master folder '{master_folder_name}'...")
        os.makedirs(master_path, exist_ok=True)

    # 2. Identify images outside of the new master folder
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.tiff', '.webp', '.heic', '.bmp'}
    excluded_patterns = ["/node_modules/", "/.git/", "/.cursor/", "/.Trash/", master_path]

    moved_count = 0
    
    print(f"🔍 Finding images outside of '{master_folder_name}'...")
    
    for root, dirs, files in os.walk(gdrive_root):
        # Skip the master folder itself
        if root.startswith(master_path):
            continue
            
        # Skip common junk folders
        if any(p in root for p in excluded_patterns):
            continue
            
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in image_extensions:
                source_path = os.path.join(root, file)
                
                # Filter out obvious icons/noise
                if any(x in file.lower() for x in ['icon', 'favicon', 'logo-']):
                    continue

                try:
                    # Calculate destination path preserving relative structure
                    # We want to move 'Folder/sub/img.jpg' to 'Google Pictures/Folder/sub/img.jpg'
                    rel_path = os.path.relpath(source_path, gdrive_root)
                    dest_path = os.path.join(master_path, rel_path)
                    
                    # Create destination directory if needed
                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                    
                    # Handle name collisions
                    final_dest = dest_path
                    counter = 1
                    while os.path.exists(final_dest):
                        name_stem = Path(file).stem
                        final_dest = os.path.join(os.path.dirname(dest_path), f"{name_stem}__{counter}{ext}")
                        counter += 1
                    
                    # Physically move the file
                    shutil.move(source_path, final_dest)
                    moved_count += 1
                    if moved_count % 50 == 0:
                        print(f" ✅ Moved {moved_count} images...")
                except Exception as e:
                    print(f" ❌ Error moving {file}: {e}")

    print("\n" + "="*80)
    print("✨ INTERNAL CONSOLIDATION COMPLETE")
    print("="*80)
    print(f"Total images moved into '{master_folder_name}': {moved_count}")
    print(f"Final location: {master_path}")
    print("="*80)

if __name__ == "__main__":
    main()
