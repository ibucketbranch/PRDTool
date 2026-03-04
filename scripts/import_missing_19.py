import os
import subprocess
import json

def get_iphoto_filenames():
    script = 'tell application "Photos" to get filename of media items'
    try:
        cmd = ["osascript", "-e", script]
        process = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        raw_names = process.stdout.strip()
        if raw_names:
            return set([n.strip() for n in raw_names.split(",")])
        return set()
    except Exception:
        return set()

def main():
    staging_root = "/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs/Documents/Google Pictures/Import_to_Apple_Photos"
    image_extensions = {'.jpg', '.jpeg', '.png', '.heic', '.tiff', '.webp', '.bmp', '.gif'}
    
    staged_items = []
    for root, dirs, files in os.walk(staging_root):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in image_extensions:
                staged_items.append({"name": file, "path": os.path.join(root, file)})

    iphoto_names = get_iphoto_filenames()
    missing_paths = [item['path'] for item in staged_items if item['name'] not in iphoto_names]

    if not missing_paths:
        print("✅ No missing files found!")
        return

    print(f"🚀 Attempting to import {len(missing_paths)} missing files...")
    
    for path in missing_paths:
        print(f"  📥 Importing: {os.path.basename(path)}")
        script = f'tell application "Photos" to import (POSIX file "{path}")'
        try:
            subprocess.run(['osascript', '-e', script], check=True)
        except Exception as e:
            print(f"  ❌ Failed to import {os.path.basename(path)}: {e}")

    print("\n✅ Targeted import attempt complete.")

if __name__ == "__main__":
    main()
