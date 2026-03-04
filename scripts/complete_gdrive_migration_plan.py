#!/usr/bin/env python3
"""
Complete Google Drive Migration Plan:
1. Process remaining unprocessed files
2. Move all processed files to iCloud based on AI-suggested structures
"""
import os
import sys
from pathlib import Path

print("="*80)
print("📋 COMPLETE GOOGLE DRIVE MIGRATION PLAN")
print("="*80)

print(f"""
🎯 MIGRATION STEPS:

Step 1: Process Remaining Files
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Found: 876 unprocessed files (by hash check)
  
  Run: python3 scripts/process_all_gdrive_documents.py
  
  This will:
  - Process all remaining .pdf, .docx, .xlsx, .pptx, .txt, .rtf files
  - Extract text and metadata
  - AI categorize and suggest folder structures
  - Save to database with original paths preserved

Step 2: Verify All Files Processed
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Run: python3 scripts/final_gdrive_report.py
  
  Verify: >95% processed before proceeding to move

Step 3: Move Files to iCloud
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Run: python3 scripts/move_gdrive_to_icloud.py --execute
  
  This will:
  - Move files from Google Drive to iCloud
  - Organize by AI-suggested folder structures
  - Update database with new paths
  - Preserve original Google Drive paths in document_locations

Step 4: Clean Up Empty Folders
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Run: python3 scripts/cleanup_empty_folders.py --execute --force-empty
  
  This will:
  - Delete empty folders after files are moved
  - Only delete folders where files were moved (verified in database)

Step 5: Final Safety Check
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Run: python3 scripts/quick_safety_check_gdrive.py
  
  Verify: >95% accounted for before deleting Google Drive

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 RECOMMENDED EXECUTION ORDER:

1. python3 scripts/process_all_gdrive_documents.py
   (Wait for completion)

2. python3 scripts/final_gdrive_report.py
   (Verify >95% processed)

3. python3 scripts/move_gdrive_to_icloud.py
   (Dry run first to review)

4. python3 scripts/move_gdrive_to_icloud.py --execute
   (Execute moves)

5. python3 scripts/cleanup_empty_folders.py --execute --force-empty
   (Clean up empty folders)

6. python3 scripts/quick_safety_check_gdrive.py
   (Final verification)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")

print("✅ Plan ready. Execute steps in order.")
print("="*80)
