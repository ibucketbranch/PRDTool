#!/usr/bin/env python3
"""
Check and Import Google Drive Videos (.mov files) to Photos
Checks if .mov files in Google Pictures folder are already in Photos, and imports missing ones.
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

def import_to_photos(file_path: str, filename: str) -> bool:
    """Import a single video file into Photos and verify it completed."""
    # First check if it's already there
    photos_filenames = get_photos_filenames()
    if filename in photos_filenames:
        return True
    
    # Import the file - Photos can be very slow with videos
    # Use a fire-and-forget approach: send import command, then verify later
    script = f'''tell application "Photos"
        try
            import POSIX file "{file_path}" without prompting
        end try
    end tell'''
    
    try:
        # Send import command without waiting for response (videos take too long)
        # We'll verify later if it worked
        subprocess.Popen(
            ['osascript', '-e', script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        # Videos need significant time to process - wait and verify
        print(f"      (Importing video - Photos may take 30-60 seconds to process...)")
        time.sleep(20)  # Initial wait for Photos to start processing
        
        # Try multiple verification attempts with increasing delays
        max_attempts = 5
        for attempt in range(max_attempts):
            photos_filenames = get_photos_filenames()
            if filename in photos_filenames:
                return True
            
            # Wait longer between attempts for videos
            if attempt < max_attempts - 1:
                wait_time = 20 + (attempt * 15)  # 20s, 35s, 50s, 65s, 80s
                print(f"      (Still processing, waiting {wait_time}s more...)")
                time.sleep(wait_time)
        
        # Final check after even longer wait
        print(f"      (Final check after extended wait...)")
        time.sleep(30)
        photos_filenames = get_photos_filenames()
        if filename in photos_filenames:
            return True
        
        # If still not found, it likely failed
        return False
        
    except Exception as e:
        print(f"   ⚠️  Import error: {e}")
        return False

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Check and import .mov video files from Google Pictures to Photos'
    )
    parser.add_argument(
        '--folder',
        type=str,
        default="/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive/Google Pictures",
        help='Path to Google Pictures folder (default: standard Google Drive path)'
    )
    parser.add_argument(
        '--import',
        dest='do_import',
        action='store_true',
        help='Import missing videos to Photos (default: only check)'
    )
    parser.add_argument(
        '--yes',
        action='store_true',
        help='Skip confirmation prompt'
    )
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("🎬 GOOGLE DRIVE VIDEOS CHECK")
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
    
    report = {
        'total': len(video_files),
        'in_photos': [],
        'missing': [],
        'imported': [],
        'failed': []
    }
    
    for video_file in video_files:
        if video_file['name'] in photos_filenames:
            report['in_photos'].append(video_file)
        else:
            report['missing'].append(video_file)
    
    # Print report
    print(f"Total video files found:   {report['total']}")
    print(f"✅ Already in Photos:       {len(report['in_photos'])}")
    print(f"🆕 Missing from Photos:     {len(report['missing'])}")
    print()
    
    if report['in_photos']:
        print("✅ Videos ALREADY IN PHOTOS (showing first 10):")
        print("-" * 80)
        for item in report['in_photos'][:10]:
            print(f"  ✅ {item['name']} ({item['size_mb']} MB, {item['extension']})")
            print(f"     Path: {item['relative_path']}")
        if len(report['in_photos']) > 10:
            print(f"     ... and {len(report['in_photos']) - 10} more")
        print()
    
    if report['missing']:
        print(f"🆕 Videos MISSING FROM PHOTOS ({len(report['missing'])}):")
        print("-" * 80)
        # Group by extension for better display
        by_ext = {}
        for item in report['missing']:
            ext = item['extension']
            if ext not in by_ext:
                by_ext[ext] = []
            by_ext[ext].append(item)
        
        for ext in sorted(by_ext.keys()):
            print(f"\n  {ext.upper()} files ({len(by_ext[ext])}):")
            for item in by_ext[ext][:10]:
                print(f"    🆕 {item['name']} ({item['size_mb']} MB)")
                print(f"       Path: {item['relative_path']}")
            if len(by_ext[ext]) > 10:
                print(f"       ... and {len(by_ext[ext]) - 10} more")
        print()
        
        # Import if requested
        if args.do_import:
            if not args.yes:
                print("=" * 80)
                print("⚠️  WARNING: This will import videos into Photos")
                print("=" * 80)
                print(f"   Will import {len(report['missing'])} videos")
                print()
                response = input("   Continue? (yes/no): ").strip().lower()
                if response != 'yes':
                    print("   Cancelled.")
                    return
                print()
            
            print("=" * 80)
            print("📥 IMPORTING VIDEOS TO PHOTOS")
            print("=" * 80)
            print()
            
            for i, item in enumerate(report['missing'], 1):
                print(f"[{i}/{len(report['missing'])}] Importing: {item['name']}...", end=" ", flush=True)
                
                if import_to_photos(item['path'], item['name']):
                    report['imported'].append(item)
                    print("✅ Imported & Verified")
                else:
                    report['failed'].append(item)
                    print("❌ FAILED or not verified")
                
                # Small delay between imports
                if i < len(report['missing']):
                    time.sleep(2)
            
            print()
            print("=" * 80)
            print("📊 IMPORT SUMMARY")
            print("=" * 80)
            print(f"✅ Successfully imported: {len(report['imported'])}")
            print(f"❌ Failed:                 {len(report['failed'])}")
            print("=" * 80)
            print()
        else:
            print("💡 To import missing videos, run with --import flag:")
            print(f"   python3 {sys.argv[0]} --folder \"{args.folder}\" --import --yes")
            print()
    else:
        print("✅ All videos are already in Photos!")
        print()
    
    print("=" * 80)


if __name__ == "__main__":
    main()
