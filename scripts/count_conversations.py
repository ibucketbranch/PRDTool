import os
from supabase import create_client

url = "http://127.0.0.1:54421"
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

supabase = create_client(url, key)

# Count conversation documents
# 1. By 'conversation' category
# 2. By 'is_conversation' flag
# 3. By filename patterns (chat..., +1...)

print("💬 Analyzing Conversation Documents...")

# Check DB categories
cat_count = supabase.table('document_categories').select('document_id', count='exact')\
    .eq('category_id', \
        supabase.table('categories').select('id').eq('category_name', 'conversation').execute().data[0]['id']\
    ).execute().count

print(f"   Categorized as 'conversation': {cat_count}")

# Check DB flag
flag_count = supabase.table('documents').select('id', count='exact').eq('is_conversation', True).execute().count
print(f"   Flagged as is_conversation: {flag_count}")

# Check Filename Patterns in DB
chat_pattern = supabase.table('documents').select('id', count='exact').ilike('file_name', 'chat%').execute().count
phone_pattern = supabase.table('documents').select('id', count='exact').ilike('file_name', '+%').execute().count
print(f"   Files starting with 'chat...': {chat_pattern}")
print(f"   Files starting with '+...': {phone_pattern}")

print(f"   Total likely conversations: {max(cat_count, flag_count, chat_pattern + phone_pattern)}")
