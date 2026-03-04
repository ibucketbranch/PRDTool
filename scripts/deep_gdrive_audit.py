import os
import json
from pathlib import Path
from collections import defaultdict

def format_size(size):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024

def deep_gdrive_audit():
    gdrive_root = "/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive"
    print(f"🔍 Starting DEEP AUDIT of Google Drive: {gdrive_root}")
    
    stats = defaultdict(lambda: {"count": 0, "size": 0})
    folder_stats = defaultdict(lambda: {"count": 0, "size": 0})
    
    total_files = 0
    
    # We'll use os.walk for a truly deep recursion
    for root, dirs, files in os.walk(gdrive_root):
        rel_dir = os.path.relpath(root, gdrive_root)
        
        for file in files:
            file_path = os.path.join(root, file)
            ext = os.path.splitext(file)[1].lower()
            if not ext:
                ext = "[no-extension]"
            
            try:
                # Use os.stat to get size without triggering full file download if possible
                f_stat = os.stat(file_path)
                size = f_stat.st_size
                
                stats[ext]["count"] += 1
                stats[ext]["size"] += size
                
                # Track folder density
                top_level = rel_dir.split(os.sep)[0] if rel_dir != "." else "Root"
                folder_stats[top_level]["count"] += 1
                folder_stats[top_level]["size"] += size
                
                total_files += 1
                if total_files % 10000 == 0:
                    print(f"  Scanned {total_files} files...")
            except:
                continue

    # 1. Extension Report
    sorted_exts = sorted(stats.items(), key=lambda x: x[1]["size"], reverse=True)
    
    # 2. Folder Report
    sorted_folders = sorted(folder_stats.items(), key=lambda x: x[1]["size"], reverse=True)

    print("\n" + "="*80)
    print("📋 DEEP GOOGLE DRIVE AUDIT REPORT")
    print("="*80)
    print(f"Total Files Scanned: {total_files:,}")
    print("-" * 80)
    
    print("\n💾 TOP FILE TYPES BY SIZE:")
    print(f"{'Extension':<15} | {'Count':>10} | {'Total Size':>15}")
    print("-" * 45)
    for ext, data in sorted_exts[:40]:
        print(f"{ext:<15} | {data['count']:>10,} | {format_size(data['size']):>15}")

    print("\n📁 TOP DIRECTORIES BY SIZE (Top Level):")
    print(f"{'Directory':<30} | {'Count':>10} | {'Total Size':>15}")
    print("-" * 60)
    for folder, data in sorted_folders[:20]:
        print(f"{folder[:30]:<30} | {data['count']:>10,} | {format_size(data['size']):>15}")

    # Save full details to a JSON for further analysis if needed
    report_data = {
        "summary": {
            "total_files": total_files,
            "scan_date": str(Path().stat().st_mtime)
        },
        "extensions": stats,
        "folders": folder_stats
    }
    
    with open('/tmp/deep_gdrive_audit.json', 'w') as f:
        json.dump(report_data, f, indent=2)
    
    print("\n" + "="*80)
    print(f"Full audit details saved to: /tmp/deep_gdrive_audit.json")
    print("="*80)

if __name__ == "__main__":
    deep_gdrive_audit()
