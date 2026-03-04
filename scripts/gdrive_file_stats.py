import os
import json
from pathlib import Path
from collections import defaultdict

def format_size(size):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024

def scan_gdrive_stats():
    gdrive_root = "/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive"
    print(f"🔍 Analyzing file types and sizes in: {gdrive_root}...")
    
    categories = {
        "Images": [".jpg", ".jpeg", ".png", ".heic", ".tiff", ".webp", ".bmp", ".gif", ".cr2"],
        "Documents": [".pdf", ".doc", ".docx", ".rtf", ".txt", ".pages", ".gdoc"],
        "Spreadsheets": [".xls", ".xlsx", ".csv", ".numbers", ".gsheet"],
        "Presentations": [".ppt", ".pptx", ".key", ".gslides"],
        "Videos": [".mov", ".mp4", ".m4v", ".avi", ".mkv", ".mpg", ".mpeg"],
        "Audio": [".mp3", ".m4a", ".wav", ".aif", ".aiff", ".flac"],
        "Code/Development": [".m", ".h", ".cs", ".py", ".js", ".html", ".htm", ".css", ".xml", ".json", ".plist", ".xib", ".pbxproj", ".pbxbtree", ".pch", ".sample"],
        "Email/Contacts": [".emlx", ".abcdp", ".vcf", ".vcard"],
        "Archives": [".zip", ".tar", ".gz", ".7z", ".rar"]
    }
    
    # Reverse mapping for fast lookup
    ext_to_cat = {}
    for cat, exts in categories.items():
        for ext in exts:
            ext_to_cat[ext] = cat

    stats = defaultdict(lambda: {"count": 0, "size": 0})
    ext_stats = defaultdict(lambda: {"count": 0, "size": 0})
    odd_names = []

    for root, dirs, files in os.walk(gdrive_root):
        for file in files:
            file_path = os.path.join(root, file)
            ext = os.path.splitext(file)[1].lower()
            
            try:
                size = os.path.getsize(file_path)
                cat = ext_to_cat.get(ext, "Other")
                
                stats[cat]["count"] += 1
                stats[cat]["size"] += size
                
                ext_stats[ext]["count"] += 1
                ext_stats[ext]["size"] += size
                
                # Check for "long and odd names"
                # Criteria: length > 100 or contains weird characters or just looks like junk
                if len(file) > 100 or any(c in file for c in ['%', '$', '{', '}', '[', ']']):
                    if len(odd_names) < 50:
                        odd_names.append({"name": file, "path": os.path.relpath(file_path, gdrive_root), "size": size})
            except:
                continue

    # Sorting
    sorted_cats = sorted(stats.items(), key=lambda x: x[1]["size"], reverse=True)
    sorted_exts = sorted(ext_stats.items(), key=lambda x: x[1]["count"], reverse=True)

    print("\n" + "="*80)
    print("📊 GOOGLE DRIVE FILE TYPE REPORT")
    print("="*80)
    print(f"{'Category':<20} | {'Count':>10} | {'Total Size':>15}")
    print("-" * 50)
    for cat, data in sorted_cats:
        print(f"{cat:<20} | {data['count']:>10,} | {format_size(data['size']):>15}")
    
    print("\n" + "="*80)
    print("📈 TOP EXTENSIONS BY COUNT")
    print("="*80)
    print(f"{'Extension':<15} | {'Count':>10} | {'Total Size':>15}")
    print("-" * 45)
    for ext, data in sorted_exts[:30]:
        display_ext = ext if ext else "[no-ext]"
        print(f"{display_ext:<15} | {data['count']:>10,} | {format_size(data['size']):>15}")

    if odd_names:
        print("\n" + "="*80)
        print("🕵️ EXAMPLES OF ODD OR LONG FILENAMES (Potential Junk)")
        print("="*80)
        for item in odd_names[:15]:
            print(f" - {item['name'][:80]}...")
            print(f"   📁 {item['path'][:80]}...")
            print(f"   ⚖️ {format_size(item['size'])}")
            print("-" * 40)

if __name__ == "__main__":
    scan_gdrive_stats()
