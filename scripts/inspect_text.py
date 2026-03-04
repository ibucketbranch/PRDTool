import os
from supabase import create_client

url = "http://127.0.0.1:54421"
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

supabase = create_client(url, key)

# Fetch the text for the Disney file
response = supabase.table('documents')\
    .select('extracted_text, text_preview')\
    .eq('file_name', 'KaterinaValderrama_signedDisneyTripForms.pdf')\
    .execute()

if response.data:
    print("--- RAW TEXT START ---")
    print(response.data[0]['extracted_text'][:1000]) # Show first 1000 chars
    print("--- RAW TEXT END ---")
else:
    print("File not found in DB.")
