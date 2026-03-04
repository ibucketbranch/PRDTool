import os
import subprocess
import json

def get_iphoto_filenames():
    print("🍎 Fetching all filenames from Apple Photos...")
    # This AppleScript is optimized to just get the filename property
    script = 'tell application "Photos" to get filename of media items'
    try:
        # For 26k items, this might return a VERY large string.
        # We'll use a slightly different approach to avoid shell command length limits.
        cmd = ["osascript", "-e", script]
        process = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        # AppleScript returns a comma-separated list like "img1.jpg, img2.jpg"
        raw_names = process.stdout.strip()
        if raw_names:
            # Clean and split
            names = [n.strip() for n in raw_names.split(",")]
            return set(names)
        return set()
    except Exception as e:
        print(f"Error: {e}")
        return set()

def main():
    gdrive_list_path = '/tmp/gdrive_photo_list.json'
    if not os.path.exists(gdrive_list_path):
        print("Error: GDrive list not found.")
        return

    with open(gdrive_list_path, 'r') as f:
        gdrive_items = json.load(f)

    iphoto_names = get_iphoto_filenames()
    print(f"✅ Loaded {len(iphoto_names)} names from Apple Photos.")

    only_in_gdrive = []
    matches = 0

    for item in gdrive_items:
        if item['name'] in iphoto_names:
            matches += 1
        else:
            only_in_gdrive.append(item)

    print("\n" + "="*80)
    print("📊 PHOTO RECONCILIATION REPORT")
    print("="*80)
    print(f"Total in Google Drive:  {len(gdrive_items)}")
    print(f"Matches in iPhotos:     {matches}")
    print(f"Only in Google Drive:   {len(only_in_gdrive)}")
    print("="*80)

    if only_in_gdrive:
        print("\nSample of photos ONLY in Google Drive (not found by name in iPhotos):")
        # Sort by date/name for better view
        for item in sorted(only_in_gdrive, key=lambda x: x['name'])[:20]:
            print(f"  - {item['name']} (Path: {os.path.relpath(item['path'], '/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive')})")

    # Save the list of missing photos
    with open('/tmp/missing_from_iphoto.json', 'w') as f:
        json.dump(only_in_gdrive, f, indent=2)
    
    print(f"\nFull list of {len(only_in_gdrive)} missing photos saved to: /tmp/missing_from_iphoto.json")

if __name__ == "__main__":
    main()
