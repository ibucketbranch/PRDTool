import os
import subprocess
import json

def get_iphoto_filenames():
    print("🍎 Fetching filenames from Apple Photos...")
    # Get filenames from Photos app
    script = 'tell application "Photos" to get filename of media items'
    try:
        cmd = ["osascript", "-e", script]
        process = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        raw_names = process.stdout.strip()
        if raw_names:
            return set([n.strip() for n in raw_names.split(",")])
        return set()
    except Exception as e:
        print(f"Error fetching from Apple Photos: {e}")
        return set()

def main():
    staging_root = "/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs/Documents/Google Pictures/Import_to_Apple_Photos"
    print(f"📦 Scanning Staging Folder: {staging_root}")
    
    image_extensions = {'.jpg', '.jpeg', '.png', '.heic', '.tiff', '.webp', '.bmp', '.gif'}
    staged_files = []
    
    for root, dirs, files in os.walk(staging_root):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in image_extensions:
                staged_files.append(file)

    total_staged = len(staged_files)
    print(f"✅ Found {total_staged} images in Staging Folder.")

    iphoto_names = get_iphoto_filenames()
    print(f"✅ Found {len(iphoto_names)} items in Apple Photos library.")

    already_imported = 0
    missing_from_photos = []
    
    for name in staged_files:
        if name in iphoto_names:
            already_imported += 1
        else:
            missing_from_photos.append(name)

    percent_complete = (already_imported / total_staged) * 100 if total_staged > 0 else 0

    print("\n" + "="*80)
    print("📸 IMPORT VERIFICATION REPORT")
    print("="*80)
    print(f"Total files in Staging Area:   {total_staged}")
    print(f"Already in Apple Photos:       {already_imported}")
    print(f"Missing from Apple Photos:     {len(missing_from_photos)}")
    print(f"\nVerification Score: {percent_complete:.1f}% imported")
    print("="*80)

    if missing_from_photos:
        print("\nSample of files NOT yet in Apple Photos:")
        for name in sorted(missing_from_photos)[:10]:
            print(f"  - {name}")

if __name__ == "__main__":
    main()
