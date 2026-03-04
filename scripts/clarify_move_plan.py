#!/usr/bin/env python3
"""
Clarify what files we're moving and why.
"""
import os
from supabase import create_client

supabase = create_client('http://127.0.0.1:54421', os.getenv('SUPABASE_SERVICE_ROLE_KEY'))
google_drive_path = '/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive'

print("="*80)
print("📋 CLARIFYING WHAT WE'RE MOVING")
print("="*80)

print("""
🎯 WHAT WE'RE MOVING:

The 890 files are:
- ✅ Files that are CURRENTLY in Google Drive (physical location)
- ✅ Files that have been PROCESSED (extracted, categorized, AI analyzed)
- ✅ Files that have AI-suggested folder structures
- ✅ Files ready to be organized in iCloud

These are NOT "new" files - they're EXISTING files that:
1. Are currently stored in Google Drive
2. Have been analyzed and categorized by AI
3. Need to be physically moved to iCloud
4. Will be organized by their AI-suggested folder structures

📦 THE MOVE PROCESS:

1. Find files in Google Drive that are processed
2. Use their AI-suggested folder structure (e.g., "Work Bin/Employment/Resumes")
3. Physically move them from Google Drive → iCloud
4. Update database with new location
5. Preserve original Google Drive path in history

💡 EXAMPLE:

File: "MichaelValderrama-v20911wyse.docx"
Current location: Google Drive (somewhere)
AI suggests: "Work Bin/Employment/Resumes/Michael Valderrama"
New location: iCloud/Documents/Work Bin/Employment/Resumes/Michael Valderrama/

This is a PHYSICAL MOVE, not just copying metadata.
""")

# Show actual example
print("\n" + "="*80)
print("📊 ACTUAL FILES TO MOVE")
print("="*80)

result = supabase.table('documents')\
    .select('file_name,current_path,suggested_folder_structure')\
    .ilike('current_path', f'%{google_drive_path}%')\
    .limit(5)\
    .execute()

if result.data:
    print("\nExample files that will be moved:")
    for i, doc in enumerate(result.data, 1):
        print(f"\n{i}. {doc.get('file_name')}")
        print(f"   From: {doc.get('current_path', '')[:80]}...")
        suggested = doc.get('suggested_folder_structure', '')
        if suggested:
            print(f"   To:   iCloud/Documents/{suggested}/")
        else:
            print(f"   To:   (will use context bin or category)")

print("\n" + "="*80)
print("✅ SUMMARY")
print("="*80)
print("""
We're moving 890 EXISTING, PROCESSED files from Google Drive to iCloud.
They're not "new" - they're files that:
- Already exist in Google Drive
- Have been analyzed by AI
- Need to be physically moved and organized in iCloud

This is part of the Google Drive → iCloud migration.
""")
print("="*80)
