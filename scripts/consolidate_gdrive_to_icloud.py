import os
import json
import shutil
from pathlib import Path
from datetime import datetime

def main():
    analysis_file = '/tmp/gdrive_deep_analysis.json'
    if not os.path.exists(analysis_file):
        print("Error: Analysis file not found. Run deep comparison first.")
        return

    with open(analysis_file, 'r') as f:
        data = json.load(f)

    # Combine exact matches and content dups
    candidates = []
    for item in data.get('exact_match', []):
        candidates.append({"source": item['path'], "target": item['db_path'], "type": "Exact Match"})
    for item in data.get('content_dup', []):
        candidates.append({"source": item['path'], "target": item['db_path'], "type": "Content Duplicate"})

    print(f"--- Consolidating {len(candidates)} Google Drive files to organized iCloud structure ---")
    
    log_file = '/tmp/gdrive_to_icloud_move_log.jsonl'
    results = {
        "moved": 0,
        "skipped_exists": 0,
        "errors": 0
    }

    # For safety, default to dry run unless --execute is passed
    import sys
    execute = "--execute" in sys.argv
    if not execute:
        print("\n🛈 DRY RUN MODE (Use --execute to perform actual moves)\n")

    with open(log_file, 'a') as log:
        for item in candidates:
            source = item['source']
            target = item['target']
            
            if not os.path.exists(source):
                print(f"❌ Source missing: {source}")
                results["errors"] += 1
                continue

            # Ensure target directory exists
            target_dir = os.path.dirname(target)
            
            if execute:
                try:
                    os.makedirs(target_dir, exist_ok=True)
                    
                    # If target exists, check if it's the same file
                    if os.path.exists(target):
                        # Since these are confirmed by hash, we can skip or overwrite
                        # Skipping is safer as we already have the file there
                        print(f"⏭️  Already in iCloud: {os.path.basename(target)}")
                        results["skipped_exists"] += 1
                    else:
                        shutil.copy2(source, target)
                        print(f"✅ COPIED: {os.path.basename(source)} -> organized iCloud")
                        results["moved"] += 1
                        
                    # Log the action
                    log.write(json.dumps({
                        "timestamp": datetime.now().isoformat(),
                        "source": source,
                        "target": target,
                        "type": item['type'],
                        "status": "success" if not os.path.exists(target) else "skipped_exists"
                    }) + "\n")
                except Exception as e:
                    print(f"❌ ERROR moving {os.path.basename(source)}: {e}")
                    results["errors"] += 1
            else:
                # Dry run
                if os.path.exists(target):
                    print(f"🛈 WOULD SKIP (already exists): {os.path.basename(source)}")
                    results["skipped_exists"] += 1
                else:
                    print(f"🛈 WOULD COPY: {os.path.basename(source)} -> {target}")
                    results["moved"] += 1

    print("\n" + "="*80)
    print(f"SUMMARY ({'LIVE' if execute else 'DRY RUN'})")
    print("="*80)
    print(f"Files to organize: {len(candidates)}")
    print(f"New copies:        {results['moved']}")
    print(f"Already present:   {results['skipped_exists']}")
    print(f"Errors:            {results['errors']}")
    print("="*80)
    print(f"Log: {log_file}")

if __name__ == "__main__":
    main()
