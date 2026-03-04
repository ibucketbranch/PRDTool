#!/usr/bin/env python3
"""
Import videos from local staging folder into Photos.
This tries automated import from local storage (which should work better than cloud storage).
"""

import os
import sys
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
            return set(filenames)
    except Exception as e:
        print(f"⚠️  Error fetching Photos filenames: {e}")
    
    return set()

def import_to_photos(file_path: str, filename: str, photos_filenames: set) -> bool:
    """Import a single video file into Photos and verify it completed."""
    # First check if it's already there - skip if duplicate
    if filename in photos_filenames:
        return True
    
    # Import the file - use skipDuplicates to avoid dialog boxes
    script = f'''tell application "Photos"
        try
            import POSIX file "{file_path}" without prompting skipDuplicates true
            return "SUCCESS"
        on error errMsg
            return "ERROR|" & errMsg
        end try
    end tell'''
    
    try:
        # Try with reasonable timeout for local files
        result = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True,
            text=True,
            timeout=180  # 3 minutes for videos
        )
        output = result.stdout.strip()
        
        if "ERROR" in output:
            error_msg = output.split("|", 1)[1] if "|" in output else output
            if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                # Photos is slow but import may have started - check later
                print(f"      (Photos import may be slow, will verify later...)")
            elif "in progress" in error_msg.lower() or "another" in error_msg.lower():
                # Photos is busy - wait and retry
                time.sleep(10)
                return import_to_photos(file_path, filename)  # Retry once
            else:
                print(f"      ⚠️  Import error: {error_msg[:50]}")
                return False
        
        if result.returncode == 0 and "SUCCESS" in output:
            # Videos need time to process - wait and verify
            print(f"      (Waiting for Photos to process video...)")
            time.sleep(20)  # Initial wait
            
            # Try multiple verification attempts
            for attempt in range(3):
                current_photos = get_photos_filenames()
                if filename in current_photos:
                    return True
                if attempt < 2:
                    wait_time = 20 + (attempt * 15)  # 20s, 35s, 50s
                    print(f"      (Still processing, waiting {wait_time}s more...)")
                    time.sleep(wait_time)
            
            # Final check
            time.sleep(30)
            current_photos = get_photos_filenames()
            return filename in current_photos
        
        # If we got here, something unexpected happened
        return False
        
    except subprocess.TimeoutExpired:
        # Command timed out - Photos might still be processing
        print(f"      (Import command timed out, Photos may still be processing...)")
        # Wait and check if it appeared
        time.sleep(30)
        current_photos = get_photos_filenames()
        return filename in current_photos
    except Exception as e:
        print(f"   ⚠️  Import error: {e}")
        return False

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Import videos from local staging folder into Photos'
    )
    parser.add_argument(
        '--staging',
        type=str,
        default="/Users/michaelvalderrama/Documents/Google Pictures/To_Import_Videos_From_GDrive",
        help='Staging folder path (default: Documents/Google Pictures/To_Import_Videos_From_GDrive)'
    )
    parser.add_argument(
        '--yes',
        action='store_true',
        help='Skip confirmation prompt'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Limit number of videos to import (for testing)'
    )
    
    args = parser.parse_args()
    
    staging_path = Path(args.staging)
    
    if not staging_path.exists():
        print(f"❌ Staging folder not found: {staging_path}")
        return
    
    print("=" * 80)
    print("🎬 IMPORT VIDEOS FROM LOCAL STAGING TO PHOTOS")
    print("=" * 80)
    print(f"\n📁 Staging folder: {staging_path}")
    print()
    
    # Find all video files
    video_extensions = {'.mov', '.mp4', '.m4v', '.avi', '.mkv', '.wmv', '.flv', '.mpg', '.mpeg'}
    video_files = []
    
    for video_file in staging_path.iterdir():
        if video_file.is_file() and video_file.suffix.lower() in video_extensions:
            try:
                stat = video_file.stat()
                video_files.append({
                    'name': video_file.name,
                    'path': str(video_file),
                    'size_mb': round(stat.st_size / (1024 * 1024), 2)
                })
            except Exception as e:
                print(f"   ⚠️  Error reading {video_file.name}: {e}")
    
    if not video_files:
        print("❌ No video files found in staging folder")
        return
    
    # Apply limit if specified
    if args.limit:
        video_files = video_files[:args.limit]
        print(f"⚠️  Limited to first {args.limit} videos for testing")
    
    print(f"✅ Found {len(video_files)} video files to import")
    print()
    
    # Get Photos filenames ONCE at the start
    print("📸 Checking which videos are already in Photos...")
    photos_filenames = get_photos_filenames()
    print(f"✅ Found {len(photos_filenames)} files already in Photos")
    print()
    
    # Filter out already imported - these will be skipped
    missing_videos = [v for v in video_files if v['name'] not in photos_filenames]
    already_in_count = len(video_files) - len(missing_videos)
    
    if not missing_videos:
        print("✅ All videos are already in Photos!")
        return
    
    print(f"📊 {len(missing_videos)} videos need to be imported")
    print(f"   ({already_in_count} already in Photos - will be skipped)")
    print()
    
    if not args.yes:
        response = input(f"⚠️  Import {len(missing_videos)} videos into Photos? (y/n): ").strip().lower()
        if response != 'y':
            print("❌ Aborted")
            return
    
    print("\n" + "=" * 80)
    print("📥 IMPORTING VIDEOS")
    print("=" * 80)
    print("⚠️  Note: Photos may show duplicate dialogs. We'll skip files already in Photos.")
    print()
    
    imported = 0
    failed = 0
    skipped = 0
    
    for i, video_file in enumerate(missing_videos, 1):
        # Re-check if it's now in Photos (in case it was imported in a previous run)
        if video_file['name'] in photos_filenames:
            skipped += 1
            print(f"[{i}/{len(missing_videos)}] Skipping (already in Photos): {video_file['name']}")
            continue
        
        print(f"[{i}/{len(missing_videos)}] Importing: {video_file['name']} ({video_file['size_mb']} MB)...", end=" ", flush=True)
        
        if import_to_photos(video_file['path'], video_file['name'], photos_filenames):
            imported += 1
            # Update our cache
            photos_filenames.add(video_file['name'])
            print("✅ Imported & Verified")
        else:
            failed += 1
            print("❌ FAILED or not verified")
        
        # Small delay between imports
        if i < len(missing_videos):
            time.sleep(2)
        
        # Progress update every 10 files
        if i % 10 == 0:
            print(f"\n   Progress: {i}/{len(missing_videos)} ({i/len(missing_videos)*100:.1f}%) - Imported: {imported}, Failed: {failed}, Skipped: {skipped}")
    
    print(f"\n{'=' * 80}")
    print("📊 IMPORT SUMMARY")
    print("=" * 80)
    print(f"✅ Successfully imported: {imported}/{len(missing_videos)}")
    print(f"❌ Failed:                 {failed}/{len(missing_videos)}")
    print(f"⏭️  Skipped (duplicates):    {skipped}")
    print(f"✅ Already in Photos:       {already_in_count}")
    print("=" * 80)

if __name__ == "__main__":
    main()
