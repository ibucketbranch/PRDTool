import os
from supabase import create_client

url = "http://127.0.0.1:54421"
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

supabase = create_client(url, key)

# Check if table exists and has data
try:
    res = supabase.table('documents').select('count', count='exact').limit(1).execute()
    print(f"Table 'documents' exists. Count: {res.count}")
except Exception as e:
    print(f"Error accessing table: {e}")
