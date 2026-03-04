import os
import hashlib
import json
from pathlib import Path
from supabase import create_client
from datetime import datetime

# Supabase configuration
supabase_url = "http://127.0.0.1:54421"
supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
supabase = create_client(supabase_url, supabase_key)

def get_file_hash(path):
    """Calculate SHA256 hash of a file."""
    hasher = hashlib.sha256()
    try:
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception as e:
        return None

def main():
    gdrive_path = "/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive"
    mdfind_file = '/tmp/gdrive_pdfs_mdfind.txt'
    
    print(f"--- Google Drive Deep Analysis ---")
    
    # 1. Fetch DB records
    print("Fetching existing records from DB...")
    db_records = []
    try:
        # Fetch in pages to ensure we get all records
        page_size = 1000
        start = 0
        while True:
            res = supabase.table('documents').select('file_name,file_hash,current_path').range(start, start + page_size - 1).execute()
            if not res.data:
                break
            db_records.extend(res.data)
            if len(res.data) < page_size:
                break
            start += page_size
        print(f"Loaded {len(db_records)} records from database.")
    except Exception as e:
        print(f"Error: {e}")
        return

    db_hashes = {r['file_hash']: r for r in db_records if r.get('file_hash')}
    db_names = {r['file_name']: r for r in db_records if r.get('file_name')}

    # 2. Load Google Drive paths
    if not os.path.exists(mdfind_file):
        print("Error: mdfind file not found. Run discovery first.")
        return

    with open(mdfind_file, 'r') as f:
        paths = [line.strip() for line in f if line.strip()]

    print(f"Analyzing {len(paths)} files from Google Drive...")
    
    report = {
        "exact_match": [],      # Same Name + Same Hash
        "content_dup": [],      # Same Hash, Different Name
        "name_match_new": [],   # Same Name, Different Hash (Potential new version or different file)
        "truly_new": [],        # New Hash + New Name
        "errors": []
    }

    processed = 0
    total = len(paths)
    
    for path in paths:
        processed += 1
        if processed % 100 == 0:
            print(f" Progress: {processed}/{total}...")
            
        file_name = os.path.basename(path)
        file_hash = get_file_hash(path)
        
        if not file_hash:
            report["errors"].append(path)
            continue
            
        match_by_hash = db_hashes.get(file_hash)
        match_by_name = db_names.get(file_name)
        
        if match_by_hash and match_by_name and match_by_name['file_hash'] == file_hash:
            report["exact_match"].append({"path": path, "db_path": match_by_hash['current_path']})
        elif match_by_hash:
            report["content_dup"].append({"path": path, "db_name": match_by_hash['file_name'], "db_path": match_by_hash['current_path']})
        elif match_by_name:
            report["name_match_new"].append({"path": path, "db_hash": match_by_name['file_hash']})
        else:
            report["truly_new"].append(path)

    # 3. Generate Report
    print("\n" + "="*80)
    print("📊 GOOGLE DRIVE DEEP COMPARISON REPORT (Name + Hash + Path)")
    print("="*80)
    print(f"Total PDFs found:          {total}")
    print(f"Exact Matches (Name+Hash): {len(report['exact_match'])}")
    print(f"Content Dups (New Name):   {len(report['content_dup'])}")
    print(f"Name Match (New Content):  {len(report['name_match_new'])}")
    print(f"TRULY NEW FILES:           {len(report['truly_new'])}")
    print(f"Errors (Unreadable):       {len(report['errors'])}")
    print("="*80)

    if report['truly_new']:
        print("\nSample Truly New Files (Top 10):")
        for f in sorted(report['truly_new'])[:10]:
            print(f"  - {os.path.basename(f)}")

    # Save details
    with open('/tmp/gdrive_deep_analysis.json', 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\nDetailed analysis saved to: /tmp/gdrive_deep_analysis.json")

if __name__ == "__main__":
    main()
