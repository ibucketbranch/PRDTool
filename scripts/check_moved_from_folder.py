#!/usr/bin/env python3
"""
Check if files were moved from a specific folder and where they went.
"""
import os
import sys
from supabase import create_client

supabase_url = "http://127.0.0.1:54421"
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(supabase_url, supabase_key)

def check_folder(folder_path):
    """Check if files were moved from this folder."""
    print("="*80)
    print(f"🔍 CHECKING FOLDER: {folder_path}")
    print("="*80)
    
    # Check if folder exists
    if not os.path.exists(folder_path):
        print(f"❌ Folder does not exist")
        return
    
    # Check if folder is empty
    try:
        items = os.listdir(folder_path)
        if len(items) == 0:
            print(f"📁 Folder is EMPTY")
        else:
            print(f"📁 Folder contains {len(items)} items:")
            for item in items[:10]:
                print(f"   - {item}")
            if len(items) > 10:
                print(f"   ... and {len(items) - 10} more")
    except Exception as e:
        print(f"⚠️  Error reading folder: {e}")
        return
    
    # Search database for files that were in this folder
    print(f"\n🔍 Searching database for files from this folder...")
    
    try:
        # Check document_locations for original paths
        result = supabase.table('document_locations')\
            .select('document_id,location_path,location_type,notes')\
            .ilike('location_path', f'%{folder_path}%')\
            .execute()
        
        if result.data:
            print(f"\n📋 Found {len(result.data)} location records:")
            
            # Get document details
            doc_ids = list(set([loc['document_id'] for loc in result.data]))
            
            docs_result = supabase.table('documents')\
                .select('id,file_name,current_path')\
                .in_('id', doc_ids)\
                .execute()
            
            docs_by_id = {doc['id']: doc for doc in docs_result.data}
            
            for loc in result.data:
                doc = docs_by_id.get(loc['document_id'], {})
                print(f"\n   📄 {doc.get('file_name', 'Unknown')}")
                print(f"      Original location: {loc['location_path']}")
                print(f"      Current location: {doc.get('current_path', 'Unknown')}")
                print(f"      Location type: {loc['location_type']}")
                if loc.get('notes'):
                    print(f"      Notes: {loc['notes']}")
        else:
            print(f"   No location records found for this folder")
        
        # Also check current_path in case files are still there
        result2 = supabase.table('documents')\
            .select('id,file_name,current_path')\
            .ilike('current_path', f'%{folder_path}%')\
            .execute()
        
        if result2.data:
            print(f"\n📋 Found {len(result2.data)} documents still in this folder:")
            for doc in result2.data:
                print(f"   - {doc['file_name']}")
        else:
            print(f"\n   No documents currently in this folder (according to database)")
            
    except Exception as e:
        print(f"❌ Error querying database: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\n{'='*80}")

if __name__ == "__main__":
    folder = sys.argv[1] if len(sys.argv) > 1 else "/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs/Personal Bin/VA Docs and Apps/2024-2025 Activities/Original AD Medical Records"
    check_folder(folder)
