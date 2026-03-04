#!/usr/bin/env python3
"""
Quick summary of Google Drive - folder structure and file counts.
"""
import os
from collections import defaultdict

google_drive_path = "/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive"

def quick_scan():
    """Quick scan of Google Drive structure."""
    print("="*80)
    print("📋 GOOGLE DRIVE QUICK SUMMARY")
    print("="*80)
    
    if not os.path.exists(google_drive_path):
        print(f"❌ Google Drive path does not exist: {google_drive_path}")
        return
    
    print(f"\n🔍 Scanning: {google_drive_path}\n")
    
    folder_counts = defaultdict(int)
    folder_sizes = defaultdict(int)
    total_files = 0
    total_size = 0
    file_types = defaultdict(int)
    
    max_depth = 3  # Limit depth for quick scan
    max_files_per_folder = 50  # Limit files per folder
    
    for root, dirs, files in os.walk(google_drive_path):
        # Skip hidden/system folders
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        
        # Limit depth
        depth = root[len(google_drive_path):].count(os.sep)
        if depth > max_depth:
            dirs[:] = []  # Don't go deeper
        
        relative_folder = os.path.relpath(root, google_drive_path)
        if relative_folder == '.':
            relative_folder = '(root)'
        
        file_count = len([f for f in files if not f.startswith('.')])
        folder_counts[relative_folder] = file_count
        
        folder_size = 0
        for file in files[:max_files_per_folder]:  # Limit for speed
            if file.startswith('.'):
                continue
            
            file_path = os.path.join(root, file)
            try:
                file_size = os.path.getsize(file_path)
                folder_size += file_size
                total_size += file_size
                
                ext = os.path.splitext(file)[1].lower()
                file_types[ext or '(no extension)'] += 1
            except:
                pass
        
        folder_sizes[relative_folder] = folder_size
        total_files += file_count
    
    print(f"📊 OVERALL STATS:")
    print(f"   Total files: {total_files:,}")
    print(f"   Total size: {total_size / (1024**3):.2f} GB")
    print(f"   Folders: {len(folder_counts)}")
    
    print(f"\n📁 TOP FOLDERS BY FILE COUNT:")
    for folder, count in sorted(folder_counts.items(), key=lambda x: x[1], reverse=True)[:30]:
        size_mb = folder_sizes[folder] / (1024**2)
        print(f"   {folder}: {count:,} files ({size_mb:.1f} MB)")
    
    print(f"\n📄 FILE TYPES:")
    for ext, count in sorted(file_types.items(), key=lambda x: x[1], reverse=True)[:20]:
        print(f"   {ext}: {count:,} files")
    
    print(f"\n{'='*80}")
    print("✅ Quick scan complete")
    print(f"{'='*80}")
    print(f"\n💡 For detailed audit with database matching, run:")
    print(f"   python3 scripts/audit_google_drive.py")

if __name__ == "__main__":
    quick_scan()
