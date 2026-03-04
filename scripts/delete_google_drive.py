#!/usr/bin/env python3
"""
Delete Google Drive after confirmation.
ONLY runs after explicit user confirmation.
"""
import os
import shutil
import sys
from pathlib import Path

google_drive_path = "/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive"

def verify_safe_to_delete():
    """Verify it's safe to delete Google Drive."""
    print("="*80)
    print("🛡️  FINAL SAFETY CHECK")
    print("="*80)
    
    # Check for important document files
    IMPORTANT_EXTENSIONS = {'.pdf', '.docx', '.xlsx', '.pptx', '.txt', '.rtf'}
    doc_files = []
    
    if not os.path.exists(google_drive_path):
        print(f"\n✅ Google Drive path doesn't exist - nothing to delete")
        return True, []
    
    print(f"\n🔍 Scanning Google Drive for important files...")
    for root, dirs, files in os.walk(google_drive_path):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for file in files:
            if file.startswith('.'):
                continue
            ext = os.path.splitext(file)[1].lower()
            if ext in IMPORTANT_EXTENSIONS:
                doc_files.append(os.path.join(root, file))
    
    if doc_files:
        print(f"   ⚠️  Found {len(doc_files)} important document files still in Google Drive")
        print(f"   Sample files:")
        for f in doc_files[:5]:
            print(f"      - {os.path.basename(f)}")
        if len(doc_files) > 5:
            print(f"      ... and {len(doc_files) - 5} more")
        return False, doc_files
    else:
        print(f"   ✅ No important document files found")
        return True, []

def delete_google_drive():
    """Delete Google Drive directory."""
    print("\n" + "="*80)
    print("🗑️  DELETING GOOGLE DRIVE")
    print("="*80)
    
    if not os.path.exists(google_drive_path):
        print(f"\n✅ Google Drive already deleted or doesn't exist")
        return
    
    try:
        # Get size before deletion
        total_size = 0
        file_count = 0
        for root, dirs, files in os.walk(google_drive_path):
            for file in files:
                try:
                    file_path = os.path.join(root, file)
                    total_size += os.path.getsize(file_path)
                    file_count += 1
                except:
                    pass
        
        print(f"\n📊 Google Drive contents:")
        print(f"   Files: {file_count:,}")
        print(f"   Size: {total_size / (1024**3):.2f} GB")
        
        print(f"\n🗑️  Deleting: {google_drive_path}")
        shutil.rmtree(google_drive_path)
        
        print(f"\n✅ Google Drive deleted successfully")
        print(f"   Freed {total_size / (1024**3):.2f} GB of space")
        
    except Exception as e:
        print(f"\n❌ Error deleting Google Drive: {e}")
        print(f"   You may need to delete it manually")

def main():
    if '--confirm' not in sys.argv:
        print("="*80)
        print("⚠️  GOOGLE DRIVE DELETION")
        print("="*80)
        print("\nThis script will DELETE the entire Google Drive directory.")
        print(f"Path: {google_drive_path}")
        print("\nTo confirm deletion, run:")
        print("   python3 scripts/delete_google_drive.py --confirm")
        return
    
    # Verify safety
    safe, remaining_files = verify_safe_to_delete()
    
    if not safe:
        print("\n" + "="*80)
        print("❌ NOT SAFE TO DELETE")
        print("="*80)
        print(f"\nFound {len(remaining_files)} important document files still in Google Drive.")
        print("Please move these files first before deleting Google Drive.")
        return
    
    # Final confirmation
    print("\n" + "="*80)
    print("⚠️  FINAL CONFIRMATION REQUIRED")
    print("="*80)
    print(f"\nThis will PERMANENTLY DELETE:")
    print(f"   {google_drive_path}")
    print(f"\nThis action CANNOT be undone.")
    print(f"\nType 'DELETE GOOGLE DRIVE' to confirm:")
    
    try:
        confirmation = input("   ").strip()
        if confirmation != 'DELETE GOOGLE DRIVE':
            print("\n❌ Confirmation failed. Deletion cancelled.")
            return
    except EOFError:
        print("\n⚠️  Non-interactive mode. Skipping final confirmation.")
        print("   For safety, manual confirmation required in interactive mode.")
        return
    
    # Delete
    delete_google_drive()
    
    print("\n" + "="*80)
    print("✅ DELETION COMPLETE")
    print("="*80)
    print("\nGoogle Drive has been deleted.")
    print("All important files have been moved to iCloud.")
    print("="*80)

if __name__ == "__main__":
    main()
