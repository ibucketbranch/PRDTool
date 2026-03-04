import os
import json
from pathlib import Path
from collections import defaultdict

def plan_gdrive_to_icloud_evacuation():
    # Source: Google Drive
    gdrive_root = "/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive"
    
    # Target: iCloud (Organized Documents)
    icloud_base = "/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs/Documents"
    target_root = os.path.join(icloud_base, "Google Pictures")
    
    # Exclusion: Do not process files already inside 'Google Pictures' on Google Drive
    gdrive_pictures_folder = os.path.join(gdrive_root, "Google Pictures")
    
    print(f"🔍 Planning EVACUATION of images from Google Drive to iCloud...")
    print(f"Source: {gdrive_root} (excluding {gdrive_pictures_folder})")
    print(f"Target: {target_root}")
    
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.tiff', '.webp', '.heic', '.bmp'}
    
    # Standard junk to skip
    excluded_patterns = [
        "/node_modules/", "/.git/", "/build/", "/dist/", "/public/images/",
        "/assets/", "/icons/", "/.cursor/", "/.Trash/", "/.sync/", "/.temp/"
    ]

    move_plan = []
    skipped_in_pictures = 0
    skipped_noise = 0
    total_size = 0

    for root, dirs, files in os.walk(gdrive_root):
        # SKIP anything already in the GDrive "Google Pictures" folder
        if root.startswith(gdrive_pictures_folder):
            skipped_in_pictures += len(files)
            continue
            
        # Skip junk folders
        if any(p in root for p in excluded_patterns):
            skipped_noise += len(files)
            continue
            
        for file in files:
            file_path = os.path.join(root, file)
            ext = os.path.splitext(file)[1].lower()
            
            if ext in image_extensions:
                try:
                    stat = os.stat(file_path)
                    size = stat.st_size
                    
                    if size == 0:
                        continue
                        
                    # Filter filename noise
                    if any(x in file.lower() for x in ['icon', 'favicon', 'logo-', 'avatar', 'sprite']):
                        skipped_noise += 1
                        continue

                    # Determine where it belongs in iCloud
                    # We preserve the original GDrive path structure under "Google Pictures"
                    rel_path = os.path.relpath(file_path, gdrive_root)
                    dest_path = os.path.join(target_root, rel_path)
                    
                    move_plan.append({
                        "source": file_path,
                        "target": dest_path,
                        "size": size,
                        "rel_path": rel_path
                    })
                    total_size += size
                except:
                    continue

    # Summary Stats
    print("\n" + "="*80)
    print("🚀 EVACUATION PLAN: GOOGLE DRIVE -> ICLOUD")
    print("="*80)
    print(f"Images to Evacuate:      {len(move_plan)}")
    print(f"Total Transfer Size:     {total_size / (1024*1024):.2f} MB")
    print(f"Already in GDrive Pics:  {skipped_in_pictures}")
    print(f"Filtered (Noise):        {skipped_noise}")
    print("="*80)

    # Save plan
    output_path = '/tmp/gdrive_to_icloud_evacuation_plan.json'
    with open(output_path, 'w') as f:
        json.dump(move_plan, f, indent=2)

    print(f"\nEvacuation plan saved to: {output_path}")

if __name__ == "__main__":
    plan_gdrive_to_icloud_evacuation()
