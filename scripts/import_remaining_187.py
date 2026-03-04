#!/usr/bin/env python3
"""
Collect and prepare the 187 remaining missing files for import into Photos.
"""
import os
import json
import shutil
import subprocess

base_folder = "/Users/michaelvalderrama/Documents/Google Pictures"
staging_folder = "/Users/michaelvalderrama/Documents/Google Pictures/To_Import_Remaining_187"

print("="*80)
print("📋 COLLECTING 187 MISSING FILES FOR IMPORT")
print("="*80)

# First, get Photos filenames to identify what's missing
print(f"\n📸 Fetching Photos library filenames...")
photos_filenames = set()
try:
    script = '''tell application "Photos"
        set photoNames to filename of media items
        return photoNames
    end tell'''
    result = subprocess.run(['osascript', '-e', script], 
                          capture_output=True, text=True, timeout=90)
    if result.returncode == 0:
        photos_filenames = set([n.strip() for n in result.stdout.split(',') if n.strip()])
        print(f"✅ Found {len(photos_filenames)} files in Photos library")
except Exception as e:
    print(f"❌ Error: {e}")
    exit(1)

# Collect all files and identify missing ones
print(f"\n📂 Scanning {base_folder} for missing files...")
missing_files = []

for root, dirs, files in os.walk(base_folder):
    # Skip staging folders
    if 'To_Import' in root:
        continue
    
    for f in files:
        if not f.startswith('.') and f.lower().endswith(('.jpg', '.jpeg', '.png', '.heic', '.tiff', '.gif', '.webp', '.bmp')):
            if f not in photos_filenames:
                full_path = os.path.join(root, f)
                missing_files.append((f, full_path))

print(f"✅ Found {len(missing_files)} missing files")

# Create staging folder
if os.path.exists(staging_folder):
    print(f"\n⚠️  Staging folder exists, clearing it...")
    shutil.rmtree(staging_folder)

os.makedirs(staging_folder, exist_ok=True)

# Copy files to staging
print(f"\n📁 Copying files to staging folder...")
copied = 0
failed = 0

for i, (filename, file_path) in enumerate(missing_files, 1):
    try:
        if os.path.exists(file_path):
            dest = os.path.join(staging_folder, filename)
            
            # Handle name collisions
            if os.path.exists(dest):
                base, ext = os.path.splitext(filename)
                counter = 1
                while os.path.exists(dest):
                    dest = os.path.join(staging_folder, f"{base}_{counter}{ext}")
                    counter += 1
            
            shutil.copy2(file_path, dest)
            copied += 1
            
            if i % 20 == 0:
                print(f"  Copied {i}/{len(missing_files)} files...")
        else:
            print(f"  ⚠️  Source not found: {file_path}")
            failed += 1
    except Exception as e:
        print(f"  ❌ Error copying {filename}: {e}")
        failed += 1

print(f"\n{'='*80}")
print(f"✅ PREPARATION COMPLETE")
print(f"{'='*80}")
print(f"  Total missing files: {len(missing_files)}")
print(f"  Copied to staging: {copied}")
print(f"  Failed: {failed}")
print(f"  Staging folder: {staging_folder}")
print(f"\n📝 NEXT STEPS:")
print(f"  1. The staging folder is now open in Finder")
print(f"  2. Select all files (Cmd+A)")
print(f"  3. Drag and drop into Photos app")
print(f"  4. Click 'Import All' when prompted")
print(f"{'='*80}")

# Open folder in Finder
os.system(f'open "{staging_folder}"')
print(f"\n✅ Opened staging folder in Finder")
