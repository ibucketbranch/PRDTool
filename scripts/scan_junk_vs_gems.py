import os
import json
from pathlib import Path
from collections import defaultdict

def scan_and_categorize_images():
    paths_to_scan = [
        "/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive/Google Pictures",
        "/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs/Documents/Google Pictures"
    ]
    
    print(f"🔍 Deep scanning for Project Junk vs. Personal Gems...")
    
    image_extensions = {'.jpg', '.jpeg', '.png', '.heic', '.cr2', '.tiff', '.bmp', '.gif'}
    
    junk_keywords = [
        "bag", "shopping", "matte", "grocery", "merchandise", "coffeebag", 
        "bottle bag", "cookie bag", "gingham", "logo", "icon", "thumb", 
        "sample", "template", "mockup", "jim-", "ui-bg", "pixel", "banner"
    ]
    
    personal_keywords = [
        "kid", "soccer", "school", "family", "hudson", "xmas", "show", 
        "birthday", "bday", "wedding", "michael", "katerina", "camila", 
        "hudson", "jan", "trip", "vacation", "holiday", "grad", "party"
    ]
    
    camera_patterns = ["IMG_", "DSC_", "DSCN", "P101", "P102", "P103", "Video", "Movie"]

    results = {
        "Project Junk": [],
        "Potential Personal Gems": [],
        "Unclassified (Camera Names)": [],
        "Unclassified (Other)": []
    }
    
    counts = defaultdict(int)
    sizes = defaultdict(int)

    for base_path in paths_to_scan:
        if not os.path.exists(base_path):
            continue
            
        print(f"  Scanning: {base_path}...")
        for root, dirs, files in os.walk(base_path):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in image_extensions:
                    file_path = os.path.join(root, file)
                    name_lower = file.lower()
                    rel_path = os.path.relpath(file_path, base_path)
                    
                    try:
                        size = os.path.getsize(file_path)
                        if size == 0: continue
                        
                        category = "Unclassified (Other)"
                        
                        # 1. Check for Junk
                        if any(kw in name_lower for kw in junk_keywords) or "discountshoppingbags" in file_path.lower():
                            category = "Project Junk"
                        # 2. Check for Personal Keywords
                        elif any(kw in name_lower for kw in personal_keywords):
                            category = "Potential Personal Gems"
                        # 3. Check for Camera Patterns
                        elif any(pattern in file for pattern in camera_patterns):
                            category = "Unclassified (Camera Names)"
                        
                        results[category].append({
                            "name": file,
                            "path": file_path,
                            "size": size,
                            "rel_path": rel_path
                        })
                        counts[category] += 1
                        sizes[category] += size
                    except:
                        continue

    print("\n" + "="*80)
    print("📊 IMAGE CATEGORIZATION REPORT")
    print("="*80)
    for cat in results.keys():
        size_mb = sizes[cat] / (1024 * 1024)
        print(f"{cat:<30} | {counts[cat]:>6,} images | {size_mb:>10.2f} MB")
    print("="*80)

    # Show Samples
    for cat, items in results.items():
        if items:
            print(f"\nSample of {cat}:")
            for item in items[:10]:
                print(f" - {item['name']} ({item['size']/1024:.1f} KB) in {os.path.dirname(item['rel_path'])}")
            if len(items) > 10:
                print(f"   ... and {len(items)-10} more.")

    # Save details
    with open('/tmp/image_classification_details.json', 'w') as f:
        json.dump({k: [{"name": i["name"], "path": i["path"]} for i in v] for k, v in results.items()}, f, indent=2)

if __name__ == "__main__":
    scan_and_categorize_images()
