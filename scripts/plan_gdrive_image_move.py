import os
import json
from pathlib import Path
from collections import defaultdict

def plan_gdrive_image_consolidation():
    gdrive_root = "/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive"
    target_dir_name = "Google Pictures"
    target_root = os.path.join(gdrive_root, target_dir_name)
    
    print(f"🔍 Planning consolidation of all images into: {target_root}")
    
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.tiff', '.webp', '.heic', '.bmp'}
    
    # Junk patterns to skip (same as before)
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

    # Exclude the target directory itself
    excluded_paths = [target_root]

    move_plan = []
    skipped_junk = 0
    skipped_0byte = 0
    in_target_already = 0

    for root, dirs, files in os.walk(gdrive_root):
        # Skip the target directory and junk directories
        if any(root.startswith(p) for p in excluded_paths) or any(p in root for p in excluded_patterns):
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
                        
                    name_lower = file.lower()
                    if any(x in name_lower for x in ['icon', 'favicon', 'logo-', 'avatar', 'sprite']):
                        skipped_junk += 1
                        continue

                    # Calculate relative path from GDrive root
                    rel_path = os.path.relpath(file_path, gdrive_root)
                    
                    # Target path is inside Google Pictures, preserving the relative structure
                    dest_path = os.path.join(target_root, rel_path)
                    
                    move_plan.append({
                        "source": file_path,
                        "target": dest_path,
                        "size": size,
                        "rel_folder": os.path.dirname(rel_path)
                    })
                except:
                    continue

    # Group by top-level folder for the report
    folder_stats = defaultdict(lambda: {"count": 0, "size": 0})
    for item in move_plan:
        # Get the first part of the relative folder as the "Top Level Folder"
        parts = Path(item["rel_folder"]).parts
        top_folder = parts[0] if parts else "Root"
        folder_stats[top_folder]["count"] += 1
        folder_stats[top_folder]["size"] += item["size"]

    sorted_folders = sorted(folder_stats.items(), key=lambda x: x[1]["count"], reverse=True)

    print("\n" + "="*80)
    print("📸 GOOGLE PICTURES CONSOLIDATION PLAN")
    print("="*80)
    print(f"Total Images to Move:    {len(move_plan)}")
    print(f"Total Size:              {sum(item['size'] for item in move_plan) / (1024*1024):.2f} MB")
    print(f"Filtered (Noise/Junk):   {skipped_junk}")
    print(f"Filtered (Empty):        {skipped_0byte}")
    print("="*80)
    
    print("\nSource Folders (Top Level):")
    for folder, stats in sorted_folders[:30]:
        print(f" - {stats['count']:>5} images | {stats['size'] / (1024*1024):>8.2f} MB | {folder}")

    # Save the plan
    output_path = '/tmp/gdrive_image_move_plan.json'
    with open(output_path, 'w') as f:
        json.dump(move_plan, f, indent=2)

    print(f"\nConsolidation plan saved to: {output_path}")

if __name__ == "__main__":
    plan_gdrive_image_consolidation()
