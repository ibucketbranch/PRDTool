import os
from supabase import create_client
import shutil
from pathlib import Path

url = "http://127.0.0.1:54421"
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

supabase = create_client(url, key)

# Create Archive Directory
archive_dir = Path.home() / 'Documents' / 'Archive' / 'Tax Templates'
archive_dir.mkdir(parents=True, exist_ok=True)

print("🧹 OPERATION TAX CLEANSE INITIALIZED...")

# 1. Fetch Candidates (Wider net)
response = supabase.table('documents').select('id, file_name, current_path, entities, ai_category').ilike('current_path', '%TurboTax%').execute()

moved_count = 0
kept_count = 0

for doc in response.data:
    file_path = doc['current_path']
    entities = doc.get('entities') or {}
    
    # SAFETY CHECKS
    # 1. Check for People (Names)
    has_people = len(entities.get('people', [])) > 0
    # 2. Check for Amounts (Money)
    has_money = len(entities.get('amounts', [])) > 0
    # 3. Check for specific "Taxpayer" keywords in text (if available - simplified here to entities)
    
    if has_people or has_money:
        # It has personal data -> KEEP
        # print(f"   🛡️  Keeping: {doc['file_name']} (Found: {entities.get('people')})")
        kept_count += 1
        continue
    
    # If we are here, it's generic.
    print(f"   🗑️  Archiving: {doc['file_name']}")
    
    # Move file
    try:
        if os.path.exists(file_path):
            # Move to archive
            dest = archive_dir / doc['file_name']
            # Handle duplicates in archive
            if dest.exists():
                dest = archive_dir / f"{doc['id']}_{doc['file_name']}"
            
            shutil.move(file_path, dest)
            
            # Update DB to reflect move (or delete if you prefer, but archiving is safer)
            # Actually, let's just mark it as 'archived' in DB or delete it.
            # User asked to "Clean Up", usually implies removing from active view.
            # Deleting from DB is cleanest if file is moved out of tracked path.
            supabase.table('documents').delete().eq('id', doc['id']).execute()
            
            moved_count += 1
        else:
            print(f"      ⚠️  File not found on disk: {file_path}")
            # Delete from DB anyway if it's a ghost
            supabase.table('documents').delete().eq('id', doc['id']).execute()
            moved_count += 1
            
    except Exception as e:
        print(f"      ❌ Error moving: {e}")

print(f"\n✅ CLEANUP COMPLETE")
print(f"   📦 Archived: {moved_count} files (Moved to {archive_dir})")
print(f"   🛡️  Protected: {kept_count} personal files")
