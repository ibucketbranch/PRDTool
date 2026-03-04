import os
import json
import shutil
from pathlib import Path
from collections import defaultdict

def plan_gdrive_internal_consolidation():
    # Source & Consolidation Root: Google Drive
    gdrive_root = "/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive"
    
    # Target Consolidation Folder within Google Drive
    target_folder_name = "Google Photos"
    target_root = os.path.join(gdrive_root, target_folder_name)
    
    print(f"🔍 Planning INTERNAL consolidation of images within Google Drive...")
    print(f"Source: {gdrive_root}")
    print(f"Target: {target_root}")
    
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.tiff', '.webp', '.heic', '.bmp'}
    
    # Standard junk to skip
    excluded_patterns = [
        "/node_modules/", "/.git/", "/build/", "/dist/", "/public/images/",
        "/assets/", "/icons/", "/.cursor/", "/.Trash/", "/.sync/", "/.temp/"
    ]

    move_plan = []
    skipped_already_in_target = 0
    skipped_noise = 0
    total_size = 0

    for root, dirs, files in os.walk(gdrive_root):
        # SKIP anything already in the target "Google Photos" folder
        if root.startswith(target_root):
            skipped_already_in_target += len(files)
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

                    # Determine destination path within "Google Photos"
                    # We preserve the original relative path structure
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
    print("📸 INTERNAL CONSOLIDATION PLAN: GOOGLE DRIVE")
    print("="*80)
    print(f"Images to Consolidate:   {len(move_plan)}")
    print(f"Total Data Size:         {total_size / (1024*1024):.2f} MB")
    print(f"Already in target:       {skipped_already_in_target}")
    print(f"Filtered (Noise):        {skipped_noise}")
    print("="*80)

    # Save plan
    output_path = '/tmp/gdrive_internal_consolidation_plan.json'
    with open(output_path, 'w') as f:
        json.dump(move_plan, f, indent=2)

    print(f"\nConsolidation plan saved to: {output_path}")

if __name__ == "__main__":
    plan_gdrive_internal_consolidation()
