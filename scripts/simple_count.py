import os
from supabase import create_client

url = "http://127.0.0.1:54421"
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

supabase = create_client(url, key)

# Simple, reliable count
count = supabase.table('documents').select('id', count='exact').execute().count

print(f"📄 FILES PROCESSED: {count}")
print(f"📊 PROGRESS: {count} / 6224 ({(count/6224)*100:.1f}%)")
