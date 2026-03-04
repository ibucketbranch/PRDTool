import os
import subprocess
import json

def get_iphoto_filenames():
    print("🍎 Fetching all filenames from Apple Photos...")
    script = 'tell application "Photos" to get filename of media items'
    try:
        cmd = ["osascript", "-e", script]
        process = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        raw_names = process.stdout.strip()
        if raw_names:
            # AppleScript returns a comma-separated list
            names = [n.strip() for n in raw_names.split(",")]
            return set(names)
        return set()
    except Exception as e:
        print(f"Error fetching from Apple Photos: {e}")
        return set()

def get_gdrive_filenames():
    gdrive_root = "/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive/Google Pictures"
    print(f"📦 Scanning Google Pictures ({gdrive_root})...")
    
    image_extensions = {'.jpg', '.jpeg', '.png', '.heic', '.tiff', '.webp', '.bmp', '.gif'}
    filenames = []
    
    for root, dirs, files in os.walk(gdrive_root):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in image_extensions:
                filenames.append(file)
    return filenames

def main():
    gdrive_files = get_gdrive_filenames()
    total_gdrive = len(gdrive_files)
    print(f"✅ Found {total_gdrive} images in Google Pictures.")

    iphoto_names = get_iphoto_filenames()
    total_iphoto = len(iphoto_names)
    print(f"✅ Found {total_iphoto} items in Apple Photos.")

    matches = 0
    missing = 0
    
    # We check each file in GDrive to see if it's in iPhotos
    for name in gdrive_files:
        if name in iphoto_names:
            matches += 1
        else:
            missing += 1

    percent_missing = (missing / total_gdrive) * 100 if total_gdrive > 0 else 0

    print("\n" + "="*80)
    print("📸 UPDATED RECONCILIATION REPORT")
    print("="*80)
    print(f"Total in Google Pictures:   {total_gdrive}")
    print(f"Found in Apple Photos:      {matches}")
    print(f"MISSING from Apple Photos:  {missing}")
    print(f"\nPercentage NOT in Apple Photos: {percent_missing:.1f}%")
    print("="*80)

if __name__ == "__main__":
    main()
