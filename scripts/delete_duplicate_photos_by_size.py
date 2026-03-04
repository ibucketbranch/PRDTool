#!/usr/bin/env python3
"""
Delete duplicate photos/videos in Photos app, keeping only the largest version.
For each duplicate group, keeps the file with the largest size and deletes the rest.
"""

import subprocess
import time
from collections import defaultdict
from typing import Dict, List, Tuple

def get_all_media_items():
    """Get all media items from Photos with their filenames and sizes."""
    print("📸 Fetching all media items from Photos...")
    print("   (This may take a while for large libraries...)")
    
    # First get total count
    count_script = 'tell application "Photos" to get count of media items'
    try:
        count_result = subprocess.run(['osascript', '-e', count_script], capture_output=True, text=True, timeout=60)
        total_count = int(count_result.stdout.strip())
        print(f"   Total items in Photos: {total_count}")
    except:
        print("⚠️  Could not get total count, proceeding anyway...")
        total_count = None
    
    # Process items one at a time (simpler, more reliable)
    items = []
    processed = 0
    
    for i in range(1, total_count + 1):
        script = f'''tell application "Photos"
            try
                set aItem to item {i} of media items
                set fileName to filename of aItem
                set fileSize to size of aItem
                set itemId to id of aItem
                return fileName & "|||" & (fileSize as string) & "|||" & itemId
            on error
                return ""
            end try
        end tell'''
        
        try:
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0 and result.stdout.strip():
                output = result.stdout.strip()
                if '|||' in output:
                    parts = output.split('|||')
                    if len(parts) >= 3:
                        try:
                            filename = parts[0].strip()
                            size = int(parts[1].strip())
                            item_id = parts[2].strip()
                            items.append({
                                'filename': filename,
                                'size': size,
                                'id': item_id
                            })
                            processed += 1
                        except (ValueError, IndexError):
                            pass
            
            # Progress update every 1000 items
            if i % 1000 == 0:
                print(f"   Processed {i}/{total_count} items ({len(items)} parsed)...")
                
        except subprocess.TimeoutExpired:
            print(f"⚠️  Timeout at item {i}")
            continue
        except Exception as e:
            if i % 1000 == 0:  # Only print errors occasionally
                print(f"⚠️  Error at item {i}: {e}")
            continue
    
    print(f"✅ Found {len(items)} media items")
    return items

def find_duplicates(media_items: List[Dict]) -> Dict[str, List[Dict]]:
    """Group media items by filename to find duplicates."""
    print("\n🔍 Finding duplicates...")
    
    # Group by filename
    by_filename = defaultdict(list)
    for item in media_items:
        by_filename[item['filename']].append(item)
    
    # Find files with duplicates
    duplicates = {}
    for filename, items in by_filename.items():
        if len(items) > 1:
            duplicates[filename] = items
    
    print(f"✅ Found {len(duplicates)} files with duplicates")
    total_duplicates = sum(len(items) - 1 for items in duplicates.values())
    print(f"   Total duplicate items to potentially delete: {total_duplicates}")
    
    return duplicates

def delete_media_item(item_id: str) -> bool:
    """Delete a media item from Photos by its ID."""
    script = f'''tell application "Photos"
        try
            set itemToDelete to media item id {item_id}
            delete itemToDelete
            return "SUCCESS"
        on error errMsg
            return "ERROR|" & errMsg
        end try
    end tell'''
    
    try:
        result = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        output = result.stdout.strip()
        if "SUCCESS" in output:
            return True
        else:
            error_msg = output.split("|", 1)[1] if "|" in output else output
            print(f"      ⚠️  Delete error: {error_msg[:50]}")
            return False
    except Exception as e:
        print(f"      ⚠️  Delete error: {e}")
        return False

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Delete duplicate photos/videos, keeping only the largest version'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be deleted without actually deleting'
    )
    parser.add_argument(
        '--yes',
        action='store_true',
        help='Skip confirmation prompt'
    )
    parser.add_argument(
        '--min-size-diff',
        type=int,
        default=0,
        help='Minimum size difference (bytes) to consider as duplicate. Default: 0 (any difference)'
    )
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("🗑️  DELETE DUPLICATE PHOTOS/VIDEOS (KEEP LARGEST)")
    print("=" * 80)
    print()
    
    if args.dry_run:
        print("⚠️  DRY RUN MODE - No files will be deleted")
        print()
    
    # Get all media items
    media_items = get_all_media_items()
    
    if not media_items:
        print("❌ No media items found in Photos")
        return
    
    # Find duplicates
    duplicates = find_duplicates(media_items)
    
    if not duplicates:
        print("\n✅ No duplicates found!")
        return
    
    # For each duplicate group, find the largest and mark others for deletion
    items_to_delete = []
    items_to_keep = []
    total_size_saved = 0
    
    print("\n" + "=" * 80)
    print("📊 DUPLICATE ANALYSIS")
    print("=" * 80)
    print()
    
    for filename, items in sorted(duplicates.items()):
        # Sort by size (largest first)
        items_sorted = sorted(items, key=lambda x: x['size'], reverse=True)
        largest = items_sorted[0]
        smaller_ones = items_sorted[1:]
        
        items_to_keep.append(largest)
        
        for item in smaller_ones:
            size_diff = largest['size'] - item['size']
            if size_diff >= args.min_size_diff:
                items_to_delete.append({
                    'filename': filename,
                    'size': item['size'],
                    'id': item['id'],
                    'largest_size': largest['size'],
                    'size_diff': size_diff
                })
                total_size_saved += item['size']
    
    # Show summary
    print(f"Files with duplicates:     {len(duplicates)}")
    print(f"Items to keep (largest):     {len(items_to_keep)}")
    print(f"Items to delete (smaller):    {len(items_to_delete)}")
    print(f"Total space to free:          {total_size_saved / (1024*1024):.2f} MB ({total_size_saved / (1024*1024*1024):.2f} GB)")
    print()
    
    # Show examples
    if items_to_delete:
        print("📋 Examples of duplicates to delete (first 10):")
        print("-" * 80)
        for item in items_to_delete[:10]:
            print(f"  🗑️  {item['filename']}")
            print(f"     Size: {item['size'] / (1024*1024):.2f} MB (largest: {item['largest_size'] / (1024*1024):.2f} MB, diff: {item['size_diff'] / (1024*1024):.2f} MB)")
        if len(items_to_delete) > 10:
            print(f"     ... and {len(items_to_delete) - 10} more")
        print()
    
    if not items_to_delete:
        print("✅ No items to delete (all duplicates are same size or below minimum size difference)")
        return
    
    # Confirm deletion
    if not args.yes and not args.dry_run:
        response = input(f"⚠️  Delete {len(items_to_delete)} duplicate items? (y/n): ").strip().lower()
        if response != 'y':
            print("❌ Aborted")
            return
    
    if args.dry_run:
        print("\n✅ DRY RUN COMPLETE - No files were deleted")
        return
    
    # Delete items
    print("\n" + "=" * 80)
    print("🗑️  DELETING DUPLICATES")
    print("=" * 80)
    print()
    
    deleted = 0
    failed = 0
    
    for i, item in enumerate(items_to_delete, 1):
        print(f"[{i}/{len(items_to_delete)}] Deleting: {item['filename']} ({item['size'] / (1024*1024):.2f} MB)...", end=" ", flush=True)
        
        if delete_media_item(item['id']):
            deleted += 1
            print("✅ Deleted")
        else:
            failed += 1
            print("❌ Failed")
        
        # Small delay between deletions
        if i < len(items_to_delete):
            time.sleep(0.5)
        
        # Progress update every 50 items
        if i % 50 == 0:
            print(f"\n   Progress: {i}/{len(items_to_delete)} ({i/len(items_to_delete)*100:.1f}%) - Deleted: {deleted}, Failed: {failed}")
    
    print(f"\n{'=' * 80}")
    print("📊 DELETION SUMMARY")
    print("=" * 80)
    print(f"✅ Successfully deleted: {deleted}/{len(items_to_delete)}")
    print(f"❌ Failed:                {failed}/{len(items_to_delete)}")
    print(f"💾 Space freed:           {total_size_saved / (1024*1024):.2f} MB ({total_size_saved / (1024*1024*1024):.2f} GB)")
    print("=" * 80)

if __name__ == "__main__":
    main()
