import os
from supabase import create_client
import json

url = "http://127.0.0.1:54421"
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

supabase = create_client(url, key)

# Fetch last 5 documents
response = supabase.table('documents')\
    .select('file_name, ai_summary, ai_category, entities')\
    .order('indexed_at', desc=True)\
    .limit(5)\
    .execute()

print(json.dumps(response.data, indent=2))
