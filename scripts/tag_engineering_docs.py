#!/usr/bin/env python3
"""
Tag Engineering Docs - Find and tag all Apple/Engineering reference documents
"""

from supabase import create_client

def tag_engineering_docs():
    """Find and tag all engineering/Apple reference documents."""
    
    # Connect to DB
    client = create_client('http://127.0.0.1:54421', os.getenv('SUPABASE_SERVICE_ROLE_KEY'))
    
    # Engineering path indicators
    engineering_paths = [
        'library/frameworks',
        'library/developer',
        'commandlinetools',
        'library/documentation',
        'releasebundle',
        'bezelservices',
        'application support/apple',
        '/library/application support',
        '/system/library',
        '/usr/share/doc',
        '/usr/local/share/doc'
    ]
    
    print("🔍 Searching for engineering/Apple reference documents...\n")
    
    # Get all documents
    resp = client.table('documents').select('id,file_name,current_path,ai_category,tags').execute()
    
    updated_count = 0
    already_tagged = 0
    
    for doc in resp.data:
        path = doc.get('current_path', '').lower()
        
        # Check if it's engineering/apple reference content
        is_engineering = any(term in path for term in engineering_paths)
        
        if is_engineering:
            # Check if already properly tagged
            existing_tags = doc.get('tags') or []
            current_category = doc.get('ai_category')
            
            needs_update = False
            
            if current_category != 'engineering':
                needs_update = True
            
            if 'Engineering Docs' not in existing_tags:
                needs_update = True
                if 'Engineering Docs' not in existing_tags:
                    existing_tags.append('Engineering Docs')
            
            if 'Apple Reference' not in existing_tags and 'apple' in path:
                needs_update = True
                existing_tags.append('Apple Reference')
            
            if needs_update:
                update_data = {
                    'ai_category': 'engineering',
                    'tags': existing_tags,
                    'ai_subcategories': ['technical_reference', 'system_documentation']
                }
                
                client.table('documents').update(update_data).eq('id', doc['id']).execute()
                updated_count += 1
                print(f"✅ Tagged: {doc['file_name']}")
            else:
                already_tagged += 1
    
    print(f"\n{'='*70}")
    print(f"✅ Updated: {updated_count} documents")
    print(f"✓  Already tagged: {already_tagged} documents")
    print(f"📊 Total engineering docs: {updated_count + already_tagged}")
    print(f"{'='*70}")

if __name__ == "__main__":
    tag_engineering_docs()
