import os
from supabase import create_client

url = "http://127.0.0.1:54421"
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

supabase = create_client(url, key)

print("🔍 Analyzing current records...")

# 1. Count Total
total = supabase.table('documents').select('id', count='exact').execute().count
print(f"Total Documents: {total}")

# 2. Count "Good" (Has Text AND Category != Other/Unreadable)
# We consider it "Good" if it has > 50 chars of text OR if it has a specific category
# Actually, simpler: Let's find the "Empty Text" ones.
empty_text = supabase.table('documents').select('id', count='exact').lt('file_size_bytes', 1000).execute().count 
# Note: file_size_bytes isn't text length. We can't query text length easily in supabase REST without a function.

# Let's use a simpler heuristic for "Bad":
# - processing_status = 'failed' (if we stored that? we store it in JSON return, but maybe not column?)
# - ai_category = 'other' AND confidence < 0.6 (likely junk)
# - ai_summary contains "limited visible content"

print("🗑️  Identifying records to purge (Reprocess with Vision)...")

# Fetch all and filter in python (safer for complex logic)
all_docs = supabase.table('documents').select('id, file_name, extracted_text, ai_summary').execute()

to_purge = []
for doc in all_docs.data:
    text_len = len(doc.get('extracted_text') or "")
    summary = doc.get('ai_summary') or ""
    
    # CRITERIA FOR RE-PROCESSING (VISION CANDIDATES):
    # 1. Almost no text extracted (< 50 chars)
    # 2. Summary says "limited visible content"
    if text_len < 50 or "limited visible content" in summary or "unable to provide" in summary.lower():
        to_purge.append(doc['id'])

print(f"found {len(to_purge)} 'Empty/Ghost' records out of {total}.")

if len(to_purge) > 0:
    print(f"Deleting {len(to_purge)} records to force re-processing...")
    # Delete in batches
    batch_size = 100
    for i in range(0, len(to_purge), batch_size):
        batch = to_purge[i:i+batch_size]
        supabase.table('documents').delete().in_('id', batch).execute()
        print(f"   Deleted batch {i}-{i+len(batch)}")

print("✅ Cleanup complete. Restarting processor will now catch these.")
