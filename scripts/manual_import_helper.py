#!/usr/bin/env python3
"""
Helper script to prepare files for manual import into Photos.
Since automated import is failing, this creates a folder with all missing files.
"""
import os
import json
import shutil
from pathlib import Path

def main():
    # Load missing files list
    list_file = "/tmp/missing_files_from_unsorted.json"
    if not os.path.exists(list_file):
        print("❌ Missing files list not found. Run the scan first.")
        return
    
    with open(list_file, 'r') as f:
        missing = json.load(f)
    
    print("="*80)
    print("📋 PREPARING FILES FOR MANUAL IMPORT")
    print("="*80)
    print(f"\nFound {len(missing)} missing files")
    
    # Create a staging folder for manual import
    staging_folder = "/Users/michaelvalderrama/Documents/Google Pictures/To_Import_Into_Photos"
    
    if os.path.exists(staging_folder):
        print(f"\n⚠️  Staging folder already exists: {staging_folder}")
        response = input("Delete and recreate? (y/n): ").strip().lower()
        if response == 'y':
            shutil.rmtree(staging_folder)
        else:
            print("Using existing folder...")
    else:
        os.makedirs(staging_folder, exist_ok=True)
    
    print(f"\n📁 Copying files to: {staging_folder}")
    
    copied = 0
    failed = 0
    
    for i, item in enumerate(missing, 1):
        source = item['path']
        filename = item['filename']
        dest = os.path.join(staging_folder, filename)
        
        try:
            if os.path.exists(source):
                # Handle name collisions
                if os.path.exists(dest):
                    base, ext = os.path.splitext(filename)
                    counter = 1
                    while os.path.exists(dest):
                        dest = os.path.join(staging_folder, f"{base}_{counter}{ext}")
                        counter += 1
                
                shutil.copy2(source, dest)
                copied += 1
                
                if i % 10 == 0:
                    print(f"  Copied {i}/{len(missing)} files...")
            else:
                print(f"  ⚠️  Source not found: {source}")
                failed += 1
        except Exception as e:
            print(f"  ❌ Error copying {filename}: {e}")
            failed += 1
    
    print(f"\n{'='*80}")
    print(f"✅ COPY COMPLETE")
    print(f"{'='*80}")
    print(f"  Copied: {copied}/{len(missing)}")
    print(f"  Failed: {failed}/{len(missing)}")
    print(f"  Staging folder: {staging_folder}")
    print(f"\n📝 NEXT STEPS:")
    print(f"  1. Open Photos app")
    print(f"  2. Go to File → Import...")
    print(f"  3. Navigate to: {staging_folder}")
    print(f"  4. Select all files and click 'Review for Import'")
    print(f"  5. Click 'Import All'")
    print(f"{'='*80}")
    
    # Open the folder in Finder
    os.system(f'open "{staging_folder}"')
    print(f"\n✅ Opened staging folder in Finder")

if __name__ == "__main__":
    main()
