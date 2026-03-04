#!/usr/bin/env python3
"""
Check if Google Drive PDFs are duplicates (by hash) of files already in database.
"""
import os
import hashlib
from supabase import create_client

supabase_url = "http://127.0.0.1:54421"
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(supabase_url, supabase_key)

google_drive_path = "/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive"

def get_file_hash(file_path):
    """Calculate SHA256 hash of file."""
    try:
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    except Exception as e:
        return None

def get_db_pdf_hashes():
    """Get all PDF hashes from database."""
    print("📊 Loading PDF hashes from database...")
    
    db_hashes = {}
    
    try:
        result = supabase.table('documents')\
            .select('id,file_name,current_path,file_hash')\
            .ilike('file_name', '%.pdf')\
            .limit(50000)\
            .execute()
        
        if result.data:
            for doc in result.data:
                file_hash = doc.get('file_hash')
                if file_hash:
                    db_hashes[file_hash] = {
                        'id': doc['id'],
                        'file_name': doc.get('file_name'),
                        'current_path': doc.get('current_path')
                    }
        
        print(f"   Found {len(db_hashes)} PDFs with hashes in database")
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
    
    return db_hashes

def find_gdrive_pdfs():
    """Find all PDFs in Google Drive."""
    print(f"\n🔍 Finding PDFs in Google Drive...")
    
    pdfs = []
    
    for root, dirs, files in os.walk(google_drive_path):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        
        for file in files:
            if file.startswith('.'):
                continue
            
            if file.lower().endswith('.pdf'):
                file_path = os.path.join(root, file)
                pdfs.append(file_path)
    
    print(f"   Found {len(pdfs)} PDFs in Google Drive")
    return pdfs

def check_duplicates(pdfs, db_hashes):
    """Check which PDFs are duplicates by hash."""
    print(f"\n🔗 Checking for duplicates by hash...")
    
    duplicates = []
    new_files = []
    errors = []
    
    for i, pdf_path in enumerate(pdfs, 1):
        if i % 20 == 0:
            print(f"   Checked {i}/{len(pdfs)} PDFs...")
        
        try:
            file_hash = get_file_hash(pdf_path)
            if not file_hash:
                errors.append(pdf_path)
                continue
            
            if file_hash in db_hashes:
                duplicates.append({
                    'path': pdf_path,
                    'hash': file_hash,
                    'db_record': db_hashes[file_hash]
                })
            else:
                new_files.append({
                    'path': pdf_path,
                    'hash': file_hash
                })
        except Exception as e:
            errors.append(pdf_path)
    
    print(f"   ✅ Duplicates found: {len(duplicates)}")
    print(f"   ⚠️  New files (not in DB): {len(new_files)}")
    if errors:
        print(f"   ❌ Errors: {len(errors)}")
    
    return duplicates, new_files, errors

def main():
    print("="*80)
    print("🔍 CHECKING GOOGLE DRIVE PDF DUPLICATES BY HASH")
    print("="*80)
    
    # Load database hashes
    db_hashes = get_db_pdf_hashes()
    
    # Find Google Drive PDFs
    pdfs = find_gdrive_pdfs()
    
    if not pdfs:
        print("\n❌ No PDFs found in Google Drive")
        return
    
    # Check duplicates
    duplicates, new_files, errors = check_duplicates(pdfs, db_hashes)
    
    # Report
    print(f"\n{'='*80}")
    print("📊 RESULTS")
    print(f"{'='*80}")
    print(f"  Total PDFs in Google Drive: {len(pdfs)}")
    print(f"  ✅ Duplicates (already in DB): {len(duplicates)}")
    print(f"  ⚠️  New files (not in DB): {len(new_files)}")
    
    if duplicates:
        print(f"\n{'='*80}")
        print("✅ DUPLICATE PDFs (Safe to skip)")
        print(f"{'='*80}")
        
        for dup in duplicates[:20]:
            filename = os.path.basename(dup['path'])
            db_file = dup['db_record']
            print(f"\n  📄 {filename}")
            print(f"     Google Drive: {dup['path'][:80]}...")
            print(f"     Already in DB as: {db_file['file_name']}")
            print(f"     Current location: {db_file['current_path'][:80]}...")
        
        if len(duplicates) > 20:
            print(f"\n  ... and {len(duplicates) - 20} more duplicates")
    
    if new_files:
        print(f"\n{'='*80}")
        print("⚠️  NEW PDFs (Need to process)")
        print(f"{'='*80}")
        
        by_folder = {}
        for item in new_files:
            folder = '/'.join(item['path'].replace(google_drive_path, '').split('/')[:-1])
            if not folder:
                folder = '(root)'
            if folder not in by_folder:
                by_folder[folder] = []
            by_folder[folder].append(item)
        
        for folder, items in sorted(by_folder.items(), key=lambda x: len(x[1]), reverse=True)[:20]:
            print(f"\n  📁 {folder}: {len(items)} new PDFs")
            for item in items[:3]:
                filename = os.path.basename(item['path'])
                print(f"     - {filename}")
            if len(items) > 3:
                print(f"     ... and {len(items) - 3} more")
    
    print(f"\n{'='*80}")
    print("✅ Duplicate check complete")
    print(f"{'='*80}")
    
    return duplicates, new_files

if __name__ == "__main__":
    duplicates, new_files = main()
