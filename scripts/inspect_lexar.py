import os
from supabase import create_client
import json

url = "http://127.0.0.1:54421"
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

supabase = create_client(url, key)

# Inspect the suspicious Lexar file
filename = "TurboTaxReturn.pdf"
print(f"🕵️  Inspecting: {filename}")

response = supabase.table('documents').select('ai_summary, entities, extracted_text').eq('file_name', filename).execute()

if response.data:
    doc = response.data[0]
    print("\n--- AI Summary ---")
    print(doc.get('ai_summary', 'No summary'))
    
    print("\n--- Entities ---")
    print(json.dumps(doc.get('entities', {}), indent=2))
    
    print("\n--- Text Preview ---")
    print(doc.get('extracted_text', '')[:500])
else:
    print("File not found in DB.")
