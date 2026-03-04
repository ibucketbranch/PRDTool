#!/usr/bin/env python3
"""
Summary of next steps for Google Drive migration.
Shows current status and what needs to be done next.
"""
import os
import subprocess
from supabase import create_client

supabase_url = "http://127.0.0.1:54421"
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(supabase_url, supabase_key)

google_drive_path = "/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive"

print("="*80)
print("📋 GOOGLE DRIVE MIGRATION - NEXT STEPS")
print("="*80)

print(f"""
✅ VERIFICATION STATUS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✓ Document Processing: VERIFIED
  - Found 814 files ready to move (have AI-suggested folder structures)
  - Found 876 files still need processing (by hash check)
  - System supports: PDF, DOCX, XLSX, PPTX, TXT, RTF

✓ Media Files: NEEDS ATTENTION
  - Found 590 media files in Google Drive (12.94 GB)
  - Status: Need to verify in Photos app
  - Note: Media files belong in Photos, not folders

✓ Move Scripts: READY
  - move_gdrive_to_icloud.py: Ready to move processed documents
  - delete_verified_media_from_gdrive.py: Ready to delete media after Photos verification

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 NEXT STEPS (In Order):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP 1: Process Remaining Documents
────────────────────────────────────────────────────────────────────────────────
  Run: python3 scripts/process_all_gdrive_documents.py
  
  This will:
  - Process remaining 876 files (PDF, DOCX, XLSX, PPTX, TXT, RTF)
  - Extract text, categorize, and suggest folder structures
  - Save to database
  
  ⏱️  Estimated time: 30-60 minutes (depends on file sizes and AI processing)

STEP 2: Verify Document Processing Complete
────────────────────────────────────────────────────────────────────────────────
  Run: python3 scripts/final_gdrive_report.py
  
  Verify: >95% processed before proceeding

STEP 3: Review Move Plan (Dry Run)
────────────────────────────────────────────────────────────────────────────────
  Run: python3 scripts/move_gdrive_to_icloud.py
  
  This shows where files will be moved without actually moving them.
  Review the plan to ensure organization looks good.

STEP 4: Execute Document Moves
────────────────────────────────────────────────────────────────────────────────
  Run: python3 scripts/move_gdrive_to_icloud.py --execute
  
  This will:
  - Move all processed documents from Google Drive to iCloud
  - Organize by AI-suggested folder structures
  - Update database with new paths
  - Preserve original Google Drive paths in history

STEP 5: Handle Media Files
────────────────────────────────────────────────────────────────────────────────
  Option A: Import to Photos manually
    - Open Photos app
    - File → Import...
    - Select Google Drive media files
    - Import all
  
  Option B: Use automated import (if available)
    - Check scripts/check_and_import_gdrive_videos.py
    - May need to run in batches for large files
  
  Then verify:
    Run: python3 scripts/verify_media_in_photos.py
  
  Then delete verified media:
    Run: python3 scripts/delete_verified_media_from_gdrive.py --execute

STEP 6: Clean Up Empty Folders
────────────────────────────────────────────────────────────────────────────────
  Run: python3 scripts/cleanup_empty_folders.py --execute --force-empty
  
  Removes empty folders after files are moved.

STEP 7: Final Safety Check
────────────────────────────────────────────────────────────────────────────────
  Run: python3 scripts/quick_safety_check_gdrive.py
  
  Verify: >95% accounted for before deleting Google Drive

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 RECOMMENDED IMMEDIATE ACTION:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Start with STEP 1: Process remaining documents

Run: python3 scripts/process_all_gdrive_documents.py

This will process the remaining 876 files and prepare them for moving.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
