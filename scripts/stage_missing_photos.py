import os
import shutil
import json
from pathlib import Path

def main():
    json_path = '/tmp/missing_from_iphoto_current.json'
    target_base = "/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs/Documents/Google Pictures/Import_to_Apple_Photos"
    
    if not os.path.exists(json_path):
        print("Error: Missing photos list not found.")
        return

    with open(json_path, 'r') as f:
        missing_items = json.load(f)

    print(f"🚀 Starting move of {len(missing_items)} missing photos to iCloud staging area...")
    
    moved_count = 0
    total_size = 0
    
    for item in missing_items:
        src = item['path']
        rel_path = item['rel_path']
        dest = os.path.join(target_base, rel_path)
        
        # Ensure destination directory exists
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        
        try:
            if os.path.exists(src):
                # Using shutil.move for physical move
                shutil.move(src, dest)
                moved_count += 1
                if moved_count % 500 == 0:
                    print(f" ✅ Moved {moved_count}/{len(missing_items)}...")
            else:
                print(f" ⚠️  Source missing: {src}")
        except Exception as e:
            print(f" ❌ Error moving {os.path.basename(src)}: {e}")

    print("\n" + "="*80)
    print("✨ STAGING COMPLETE")
    print("="*80)
    print(f"Total photos moved to staging: {moved_count}")
    print(f"Staging area: {target_base}")
    print("="*80)

if __name__ == "__main__":
    main()
