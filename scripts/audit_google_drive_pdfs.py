#!/usr/bin/env python3
"""
Focused audit of PDFs in Google Drive - match with database.
"""
import os
from pathlib import Path
from collections import defaultdict
from supabase import create_client
import hashlib

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
    except:
        return None

def get_db_pdfs():
    """Get all PDFs from database."""
    print("📊 Loading PDFs from database...")
    
    db_pdfs = {}
    
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
                    db_pdfs[file_hash] = {
                        'id': doc['id'],
                        'file_name': doc.get('file_name'),
                        'current_path': doc.get('current_path')
                    }
        
        print(f"   Found {len(db_pdfs)} PDFs in database")
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
    
    return db_pdfs

def scan_google_drive_pdfs():
    """Scan Google Drive for PDFs."""
    print(f"\n🔍 Scanning Google Drive for PDFs...")
    
    if not os.path.exists(google_drive_path):
        print(f"   ❌ Google Drive path does not exist!")
        return {}
    
    google_pdfs = {}
    by_folder = defaultdict(list)
    
    count = 0
    for root, dirs, files in os.walk(google_drive_path):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        
        for file in files:
            if file.startswith('.'):
                continue
            
            if file.lower().endswith('.pdf'):
                file_path = os.path.join(root, file)
                count += 1
                
                try:
                    file_hash = get_file_hash(file_path)
                    relative_path = os.path.relpath(file_path, google_drive_path)
                    folder = os.path.dirname(relative_path)
                    if folder == '.':
                        folder = '(root)'
                    
                    google_pdfs[file_path] = {
                        'name': file,
                        'path': file_path,
                        'relative_path': relative_path,
                        'folder': folder,
                        'hash': file_hash
                    }
                    
                    by_folder[folder].append(file)
                    
                    if count % 50 == 0:
                        print(f"   Scanned {count} PDFs...")
                        
                except Exception as e:
                    pass
    
    print(f"   Found {len(google_pdfs)} PDFs in Google Drive")
    return google_pdfs, by_folder

def main():
    print("="*80)
    print("📋 GOOGLE DRIVE PDF AUDIT")
    print("="*80)
    
    # Load database PDFs
    db_pdfs = get_db_pdfs()
    
    # Scan Google Drive PDFs
    google_pdfs, by_folder = scan_google_drive_pdfs()
    
    # Match by hash
    matched = []
    unmatched_google = []
    
    for file_path, file_info in google_pdfs.items():
        file_hash = file_info.get('hash')
        if file_hash and file_hash in db_pdfs:
            matched.append({
                'file_path': file_path,
                'file_info': file_info,
                'db_record': db_pdfs[file_hash]
            })
        else:
            unmatched_google.append({
                'file_path': file_path,
                'file_info': file_info
            })
    
    # Report
    print(f"\n{'='*80}")
    print("📊 PDF AUDIT RESULTS")
    print(f"{'='*80}")
    print(f"  Google Drive PDFs: {len(google_pdfs)}")
    print(f"  Database PDFs: {len(db_pdfs)}")
    print(f"  ✅ Matched: {len(matched)}")
    print(f"  ⚠️  Unmatched in Google Drive: {len(unmatched_google)}")
    
    # Show matched by folder
    print(f"\n{'='*80}")
    print("✅ MATCHED PDFs BY FOLDER")
    print(f"{'='*80}")
    
    matched_by_folder = defaultdict(list)
    for match in matched:
        folder = match['file_info']['folder']
        matched_by_folder[folder].append(match)
    
    for folder, matches in sorted(matched_by_folder.items(), key=lambda x: len(x[1]), reverse=True)[:20]:
        print(f"\n  📁 {folder}: {len(matches)} PDFs matched")
        for match in matches[:5]:
            print(f"     ✅ {match['file_info']['name']}")
            print(f"        → {match['db_record']['current_path'][:80]}...")
        if len(matches) > 5:
            print(f"     ... and {len(matches) - 5} more")
    
    # Show unmatched by folder
    print(f"\n{'='*80}")
    print("⚠️  UNMATCHED PDFs IN GOOGLE DRIVE")
    print(f"{'='*80}")
    
    unmatched_by_folder = defaultdict(list)
    for item in unmatched_google:
        folder = item['file_info']['folder']
        unmatched_by_folder[folder].append(item)
    
    for folder, items in sorted(unmatched_by_folder.items(), key=lambda x: len(x[1]), reverse=True)[:20]:
        print(f"\n  📁 {folder}: {len(items)} PDFs not in database")
        for item in items[:5]:
            print(f"     ⚠️  {item['file_info']['name']}")
        if len(items) > 5:
            print(f"     ... and {len(items) - 5} more")
    
    print(f"\n{'='*80}")
    print("✅ AUDIT COMPLETE")
    print(f"{'='*80}")
    
    return {
        'matched': matched,
        'unmatched_google': unmatched_google,
        'by_folder': by_folder
    }

if __name__ == "__main__":
    results = main()
