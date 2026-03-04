import os
import subprocess
import csv
import json
import hashlib
from datetime import datetime

def get_gdrive_data():
    gdrive_root = "/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive/Google Photos"
    print(f"📦 Extracting metadata from Google Photos ({gdrive_root})...")
    
    image_extensions = {'.jpg', '.jpeg', '.png', '.heic', '.tiff', '.webp'}
    gdrive_data = []
    
    for root, dirs, files in os.walk(gdrive_root):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in image_extensions:
                file_path = os.path.join(root, file)
                try:
                    stat = os.stat(file_path)
                    # We'll use size + name as a proxy for now, 
                    # but we can add hash later if needed
                    gdrive_data.append({
                        "name": file,
                        "size": stat.st_size,
                        "path": file_path
                    })
                except:
                    continue
    return gdrive_data

def get_iphoto_data():
    print("🍎 Querying Apple Photos metadata (this may take a moment)...")
    # This AppleScript gets filename and date for all media items
    script = '''
    tell application "Photos"
        set output to ""
        set all_items to media items
        repeat with i from 1 to count of all_items
            set item_ref to item i of all_items
            set item_name to filename of item_ref
            set item_date to (creation date of item_ref) as string
            set output to output & item_name & "|" & item_date & "\n"
        end repeat
        return output
    end tell
    '''
    try:
        # We'll run a faster version first just to get counts/samples if the full list is too slow
        # but for 26k it might take 30-60 seconds.
        process = subprocess.run(['osascript', '-e', script], capture_output=True, text=True, timeout=300)
        lines = process.stdout.strip().split('\n')
        iphoto_items = []
        for line in lines:
            if "|" in line:
                parts = line.split("|")
                iphoto_items.append({"name": parts[0], "date": parts[1]})
        return iphoto_items
    except Exception as e:
        print(f"Error querying Apple Photos: {e}")
        return []

def main():
    # To be extremely fast and robust for 26k+ items, we'll start with 
    # a summary and then offer the deep dive.
    
    gdrive_items = get_gdrive_data()
    print(f"✅ Found {len(gdrive_items)} images in Google Drive.")
    
    # Due to AppleScript speed limitations for 26k items, 
    # I'll perform a "fast reconciliation" based on the counts we already have
    # and then offer to run the detailed one.
    
    print("\n" + "="*80)
    print("📊 PRELIMINARY RECONCILIATION SUMMARY")
    print("="*80)
    print(f"Apple Photos items:    26,560")
    print(f"Google Photos files:   {len(gdrive_items)}")
    print(f"Estimated Difference:  {abs(26560 - len(gdrive_items))} items")
    print("="*80)
    
    # Save the GDrive list for comparison
    with open('/tmp/gdrive_photo_list.json', 'w') as f:
        json.dump(gdrive_items, f, indent=2)
        
    print("\nNext Step:")
    print("I can run a background script to match every single file by name and date.")
    print("This will tell us exactly which photos are ONLY in Google Drive.")

if __name__ == "__main__":
    main()
