#!/usr/bin/env python3
"""
Import photos from Camera Uploads into Apple Photos.
Skips files already present in Photos by filename.
"""
import os
import sys
import subprocess
import time
from collections import defaultdict

CAMERA_UPLOADS_PATH = "/Users/michaelvalderrama/Mikevalderrama Dropbox/Mike Valderrama/Camera Uploads"

IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", ".heic", ".heif",
    ".webp"
}


def get_photos_filenames():
    """Get all filenames from Photos app."""
    print("📸 Checking Photos app...")
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
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=120
        )
        if result.returncode == 0:
            filenames = []
            for line in result.stdout.strip().split("\n"):
                line = line.strip()
                if line and not line.startswith("{") and not line.startswith("}"):
                    filename = line.replace('"', "").replace(",", "").strip()
                    if filename:
                        filenames.append(filename)
            print(f"   Found {len(filenames)} items in Photos")
            return set(filenames)
    except Exception as e:
        print(f"   ⚠️  Error checking Photos: {e}")

    return set()


def find_image_files():
    """Find all image files in Camera Uploads."""
    print(f"\n🔍 Scanning: {CAMERA_UPLOADS_PATH}")
    image_files = []
    by_type = defaultdict(list)

    for root, dirs, files in os.walk(CAMERA_UPLOADS_PATH):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for file in files:
            if file.startswith("."):
                continue
            ext = os.path.splitext(file)[1].lower()
            if ext in IMAGE_EXTENSIONS:
                file_path = os.path.join(root, file)
                try:
                    file_size = os.path.getsize(file_path)
                except Exception:
                    file_size = 0
                image_files.append({
                    "path": file_path,
                    "name": file,
                    "ext": ext,
                    "size": file_size
                })
                by_type[ext].append(file)

    print(f"   Found {len(image_files):,} images")
    if image_files:
        print("\n   By type:")
        for ext, files in sorted(by_type.items(), key=lambda x: len(x[1]), reverse=True):
            print(f"      {ext}: {len(files):,} files")
    return image_files


def import_to_photos(file_path: str) -> bool:
    """Import a single file into Photos."""
    script = f'''tell application "Photos"
        try
            import POSIX file "{file_path}" without prompting skipDuplicates true
            return "SUCCESS"
        on error errMsg
            return "ERROR|" & errMsg
        end try
    end tell'''

    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=45
        )
        output = (result.stdout or "").strip()
        if "ERROR" in output:
            error_msg = output.split("|", 1)[1] if "|" in output else output
            if "timeout" in error_msg.lower():
                return True
            return False
        return result.returncode == 0 and "SUCCESS" in output
    except subprocess.TimeoutExpired:
        return True
    except Exception as e:
        print(f"      ⚠️  Import error: {e}")
        return False


def main():
    print("=" * 80)
    print("📸 IMPORT CAMERA UPLOADS TO PHOTOS")
    print("=" * 80)

    photos_filenames = get_photos_filenames()
    image_files = find_image_files()

    if not image_files:
        print("\n✅ No images found in Camera Uploads")
        return

    to_import = []
    already_in_photos = []

    for item in image_files:
        if item["name"] in photos_filenames:
            already_in_photos.append(item)
        else:
            to_import.append(item)

    print(f"\n📊 Status:")
    print(f"   Already in Photos: {len(already_in_photos):,}")
    print(f"   Need to import: {len(to_import):,}")

    if not to_import:
        print("\n✅ All images are already in Photos!")
        return

    if "--execute" not in sys.argv and "--yes" not in sys.argv:
        print(f"\n⚠️  This will import {len(to_import):,} images to Photos")
        print("\n   To proceed, run:")
        print(f"   python3 {sys.argv[0]} --execute")
        return

    print(f"\n{'=' * 80}")
    print("📥 IMPORTING IMAGES")
    print(f"{'=' * 80}")

    imported = 0
    failed = 0

    for i, item in enumerate(to_import, 1):
        filename = item["name"]
        file_path = item["path"]
        print(f"\n[{i}/{len(to_import)}] Importing: {filename}")
        print(f"      Size: {item['size'] / (1024**2):.1f} MB")

        if import_to_photos(file_path):
            imported += 1
            print("      ✅ Imported")
        else:
            failed += 1
            print("      ❌ Failed")

        if i < len(to_import):
            time.sleep(0.5)

        if i % 50 == 0:
            print(f"\n   Progress: {i}/{len(to_import)} ({i/len(to_import)*100:.1f}%)")
            print(f"   Imported: {imported}, Failed: {failed}")

    print(f"\n{'=' * 80}")
    print("📊 IMPORT SUMMARY")
    print(f"{'=' * 80}")
    print(f"  Total images: {len(to_import):,}")
    print(f"  ✅ Imported: {imported:,}")
    print(f"  ❌ Failed: {failed:,}")
    print(f"  Already in Photos: {len(already_in_photos):,}")
    print(f"\n{'=' * 80}")

    if imported > 0:
        print(f"\n✅ Successfully imported {imported:,} images to Photos")


if __name__ == "__main__":
    main()
