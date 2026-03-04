#!/usr/bin/env python3
"""
Stage Google Drive videos for manual import into Photos.
Since automated import is failing, this copies videos to a staging folder
where they can be manually imported via Photos app.
"""

import os
import sys
import shutil
import subprocess
import time
from pathlib import Path
from typing import List, Dict

def get_photos_filenames():
    """Get all filenames from Photos library (including videos)."""
    print("📸 Fetching Photos library filenames...")
    script = '''tell application "Photos"
        set photoNames to {}
        set allItems to media items
        repeat with item in allItems
            try
                set end of photoNames to filename of item
            end try
        end repeat
        return photoNames
    end tell'''
    
    try:
        result = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True,
            text=True,
            timeout=90
        )
        
        if result.returncode == 0:
            # Parse the AppleScript list output
            filenames = []
            for line in result.stdout.strip().split('\n'):
                line = line.strip()
                if line and not line.startswith('{') and not line.startswith('}'):
                    # Remove quotes and commas
                    filename = line.replace('"', '').replace(',', '').strip()
                    if filename:
                        filenames.append(filename)
            print(f"✅ Found {len(filenames)} files in Photos library")
            return set(filenames)
    except Exception as e:
        print(f"⚠️  Error fetching Photos filenames: {e}")
    
    return set()

def find_video_files(folder_path: str) -> List[Dict]:
    """Find all video files (.mov, .mp4, .m4v, .avi, etc.) in the folder."""
    print(f"\n🔍 Scanning for video files in: {folder_path}")
    print()
    
    video_extensions = {'.mov', '.mp4', '.m4v', '.avi', '.mkv', '.wmv', '.flv', '.mpg', '.mpeg'}
    video_files = []
    folder = Path(folder_path)
    
    if not folder.exists():
        print(f"❌ Folder not found: {folder_path}")
        return []
    
    for video_file in folder.rglob("*"):
        if video_file.is_file() and video_file.suffix.lower() in video_extensions:
            try:
                stat = video_file.stat()
                video_files.append({
                    'name': video_file.name,
                    'path': str(video_file),
                    'size_mb': round(stat.st_size / (1024 * 1024), 2),
                    'extension': video_file.suffix.lower(),
                    'relative_path': str(video_file.relative_to(folder))
                })
            except Exception as e:
                print(f"   ⚠️  Error reading {video_file.name}: {e}")
    
    print(f"✅ Found {len(video_files)} video files")
    return video_files

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Stage Google Drive videos for manual import into Photos'
    )
    parser.add_argument(
        '--folder',
        type=str,
        default="/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive/Google Pictures",
        help='Path to Google Pictures folder (default: standard Google Drive path)'
    )
    parser.add_argument(
        '--staging',
        type=str,
        default=None,
        help='Staging folder for videos (default: auto-select based on --location)'
    )
    parser.add_argument(
        '--location',
        type=str,
        choices=['local', 'icloud'],
        default='local',
        help='Where to stage videos: local (Documents) or icloud (iCloud Drive). Default: local (more reliable for import)'
    )
    parser.add_argument(
        '--yes',
        action='store_true',
        help='Skip confirmation prompt'
    )
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("🎬 STAGE GOOGLE DRIVE VIDEOS FOR IMPORT")
    print("=" * 80)
    print()
    
    # Find all video files
    video_files = find_video_files(args.folder)
    
    if not video_files:
        print("✅ No video files found in this folder")
        return
    
    # Get Photos filenames
    photos_filenames = get_photos_filenames()
    
    # Check which ones are missing
    print("\n" + "=" * 80)
    print("📊 CHECKING AGAINST PHOTOS LIBRARY")
    print("=" * 80)
    print()
    
    missing_videos = []
    for video_file in video_files:
        if video_file['name'] not in photos_filenames:
            missing_videos.append(video_file)
    
    print(f"Total video files found:   {len(video_files)}")
    print(f"✅ Already in Photos:       {len(video_files) - len(missing_videos)}")
    print(f"🆕 Missing from Photos:     {len(missing_videos)}")
    print()
    
    if not missing_videos:
        print("✅ All videos are already in Photos!")
        return
    
    # Determine staging folder location
    if args.staging:
        staging_path = Path(args.staging)
    else:
        if args.location == 'icloud':
            staging_path = Path("/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs/Documents/Google Pictures/To_Import_Videos_From_GDrive")
        else:  # local
            staging_path = Path("/Users/michaelvalderrama/Documents/Google Pictures/To_Import_Videos_From_GDrive")
    
    print(f"\n📁 Staging location: {args.location.upper()}")
    print(f"   Path: {staging_path}")
    
    # Create staging folder
    if staging_path.exists():
        if not args.yes:
            response = input(f"\n⚠️  Staging folder exists: {staging_path}\nDelete and recreate? (y/n): ").strip().lower()
            if response != 'y':
                print("❌ Aborted")
                return
        shutil.rmtree(staging_path)
        print(f"🗑️  Removed existing staging folder")
    
    staging_path.mkdir(parents=True, exist_ok=True)
    print(f"📁 Created staging folder: {staging_path}")
    
    # Copy missing videos to staging
    print(f"\n📦 Copying {len(missing_videos)} videos to staging folder...")
    print("   (This may take a while for large videos...)")
    print()
    
    copied = 0
    failed = 0
    total_size_mb = 0
    
    for i, video_file in enumerate(missing_videos, 1):
        try:
            source = Path(video_file['path'])
            if not source.exists():
                print(f"  ⚠️  [{i}/{len(missing_videos)}] Source not found: {video_file['name']}")
                failed += 1
                continue
            
            # Handle name collisions
            dest = staging_path / video_file['name']
            counter = 1
            while dest.exists():
                name, ext = os.path.splitext(video_file['name'])
                dest = staging_path / f"{name}_{counter}{ext}"
                counter += 1
            
            # Copy file
            shutil.copy2(source, dest)
            copied += 1
            total_size_mb += video_file['size_mb']
            
            if i % 10 == 0:
                print(f"  📋 Progress: {i}/{len(missing_videos)} ({i/len(missing_videos)*100:.1f}%) - Copied: {copied}, Failed: {failed}")
        
        except Exception as e:
            print(f"  ❌ [{i}/{len(missing_videos)}] Error copying {video_file['name']}: {e}")
            failed += 1
    
    print(f"\n{'=' * 80}")
    print("📊 STAGING SUMMARY")
    print("=" * 80)
    print(f"✅ Successfully copied: {copied}/{len(missing_videos)}")
    print(f"❌ Failed:              {failed}/{len(missing_videos)}")
    print(f"📦 Total size:          {total_size_mb:.2f} MB ({total_size_mb/1024:.2f} GB)")
    print(f"📁 Staging folder:      {staging_path}")
    print()
    print("📝 NEXT STEPS:")
    print("   1. Open Photos app")
    print("   2. Go to File → Import...")
    print("   3. Navigate to the staging folder")
    print("   4. Select all videos and click 'Review for Import'")
    print("   5. Click 'Import All'")
    print("=" * 80)
    
    # Open staging folder in Finder
    try:
        subprocess.run(['open', str(staging_path)], check=True)
        print(f"\n✅ Opened staging folder in Finder")
    except Exception as e:
        print(f"\n⚠️  Could not open Finder: {e}")

if __name__ == "__main__":
    main()
