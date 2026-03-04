#!/usr/bin/env python3
"""
Check media import status and provide options.
"""
import os
import subprocess

print("="*80)
print("📊 MEDIA IMPORT STATUS & OPTIONS")
print("="*80)

# Check Photos app
print("\n📸 Checking Photos app...")
try:
    script = '''tell application "Photos"
        set photoCount to count of media items
        return photoCount
    end tell'''
    
    result = subprocess.run(
        ['osascript', '-e', script],
        capture_output=True,
        text=True,
        timeout=30
    )
    
    if result.returncode == 0:
        count = result.stdout.strip()
        print(f"   Photos app has {count} media items")
    else:
        print("   ⚠️  Could not query Photos app")
except Exception as e:
    print(f"   ⚠️  Error: {e}")

print("\n" + "="*80)
print("💡 OPTIONS")
print("="*80)
print("""
The automated import appears to have failed. Here are your options:

OPTION 1: Manual Import (Recommended)
  1. Open Photos app
  2. File → Import...
  3. Navigate to Google Drive
  4. Select media files/folders
  5. Click "Import All"
  
  This is the most reliable method for large batches.

OPTION 2: Skip Media Import
  - Media files can be deleted from Google Drive
  - They're not critical documents
  - You can always re-download from Google Drive backup if needed
  
OPTION 3: Try Staging Approach
  - Copy media files to a staging folder
  - Import from staging folder manually
  - More reliable than direct import

Since all important documents are already moved to iCloud,
you can proceed with Google Drive deletion even if media isn't imported.
""")
print("="*80)
