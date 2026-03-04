import os
import json
from supabase import create_client
from pathlib import Path

# 1. Load the Cache (All discovered files)
cache_file = Path.home() / '.document_system' / 'pdf_cache.json'
with open(cache_file, 'r') as f:
    cache_data = json.load(f)

all_paths = set(p['path'] for p in cache_data['pdfs'])
print(f"Total PDFs on Disk: {len(all_paths)}")

# 2. Load the DB (All processed files)
url = "http://127.0.0.1:54421"
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(url, key)

print("Fetching DB records...")
# Fetch in chunks to avoid timeout
db_paths = set()
page = 0
page_size = 1000
while True:
    result = supabase.table('documents').select('current_path').range(page * page_size, (page + 1) * page_size - 1).execute()
    if not result.data:
        break
    for doc in result.data:
        db_paths.add(doc['current_path'])
    page += 1
    print(f"   Fetched {len(db_paths)} records...")

print(f"Total PDFs in Database: {len(db_paths)}")

# 3. Calculate Gap
missing = all_paths - db_paths
print(f"\n❌ MISSING FILES: {len(missing)}")

if len(missing) > 0:
    print("\nSample of missing files:")
    for p in list(missing)[:10]:
        print(f"   - {p}")
    
    # Save missing list
    with open('missing_files.txt', 'w') as f:
        for p in missing:
            f.write(f"{p}\n")
    print("\nFull list saved to missing_files.txt")
