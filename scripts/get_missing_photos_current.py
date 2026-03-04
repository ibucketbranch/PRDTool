import os
import subprocess
import json

def get_iphoto_filenames():
    print("🍎 Fetching filenames from Apple Photos...")
    script = 'tell application "Photos" to get filename of media items'
    try:
        cmd = ["osascript", "-e", script]
        process = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        raw_names = process.stdout.strip()
        if raw_names:
            return set([n.strip() for n in raw_names.split(",")])
        return set()
    except Exception as e:
        print(f"Error: {e}")
        return set()

def main():
    gdrive_root = "/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive/Google Pictures"
    print(f"📦 Scanning {gdrive_root}...")
    
    image_extensions = {'.jpg', '.jpeg', '.png', '.heic', '.tiff', '.webp', '.bmp', '.gif'}
    gdrive_items = []
    
    for root, dirs, files in os.walk(gdrive_root):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in image_extensions:
                file_path = os.path.join(root, file)
                gdrive_items.append({
                    "name": file,
                    "path": file_path,
                    "rel_path": os.path.relpath(file_path, gdrive_root)
                })

    iphoto_names = get_iphoto_filenames()
    print(f"✅ Loaded {len(iphoto_names)} names from Apple Photos.")

    missing_items = [item for item in gdrive_items if item['name'] not in iphoto_names]
    
    print(f"✅ Found {len(missing_items)} missing items.")
    
    # Save current missing items with current paths
    with open('/tmp/missing_from_iphoto_current.json', 'w') as f:
        json.dump(missing_items, f, indent=2)
    
    print(f"✅ Saved to /tmp/missing_from_iphoto_current.json")

if __name__ == "__main__":
    main()
