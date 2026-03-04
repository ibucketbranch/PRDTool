import os
from supabase import create_client

url = "http://127.0.0.1:54421"
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

supabase = create_client(url, key)

# Count documents that have:
# 1. Been processed (id exists)
# 2. Have AI summary (not null)
# 3. Have a category assigned (not 'other' or confident 'other')

query = supabase.table('documents').select('id', count='exact').neq('ai_summary', None)
result = query.execute()

print(f"Total AI Processed Docs: {result.count}")

# Breakdown by Category
categories = supabase.table('categories').select('category_name').execute()
print("\nTop Categories:")
cat_counts = {}
for cat in categories.data:
    # This is a bit expensive loop, but okay for ~20 categories
    c_name = cat['category_name']
    count = supabase.table('document_categories').select('document_id', count='exact').eq('category_id', cat['id']).execute().count
    if count > 0:
        cat_counts[c_name] = count

for cat, count in sorted(cat_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
    print(f"   {cat}: {count}")
