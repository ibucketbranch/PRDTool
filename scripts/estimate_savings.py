import os
from supabase import create_client

url = "http://127.0.0.1:54421"
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

supabase = create_client(url, key)

print("💰 Calculating Potential Savings...")

# 1. Fetch Tax Documents
# We want to find generic templates.
# Criteria:
# - Category = 'tax_document' OR 'other'
# - AND (Path contains 'TurboTax' OR 'Application Support')
# - AND (Path does NOT contain 'My Documents' or 'Personal')

# Note: Complex AND/OR logic is hard in single Supabase call, so we'll fetch wider net and filter in Python.
response = supabase.table('documents').select('file_name, file_size_bytes, current_path').ilike('current_path', '%TurboTax%').execute()

candidates = []
total_bytes = 0

for doc in response.data:
    path = doc['current_path'].lower()
    
    # SAFETY CHECK: Skip if path looks personal
    if 'my documents' in path or 'personal' in path or 'tax archive' in path or 'returns' in path:
        continue
        
    candidates.append(doc)
    total_bytes += (doc['file_size_bytes'] or 0)

print(f"🎯 Candidates for Deletion: {len(candidates)} files")
print(f"💾 Space Reclaimed: {total_bytes / 1024 / 1024:.2f} MB")

if len(candidates) > 0:
    print("\nSample Candidates:")
    for c in candidates[:5]:
        print(f"   - {c['file_name']} ({c['current_path'][-50:]})")
