#!/usr/bin/env python3
"""
Enhanced Resume/AI Monitor: See PDFs scanned, unique resumes, Gemini/Groq stats, last processed files, errors.
"""
import os
import time
from supabase import create_client
from datetime import datetime

supabase_url = "http://127.0.0.1:54421"
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(supabase_url, supabase_key)

def get_totals():
    pdfs = supabase.table('documents').select('id').execute()
    resumes = supabase.table('documents').select(
        'id,file_name,file_hash,suggested_folder_structure,updated_at'
    ).eq('ai_category','employment').execute()
    resume_hashes = set()
    recent_resumes = []
    for doc in resumes.data:
        fh = doc.get('file_hash')
        if fh and fh not in resume_hashes:
            resume_hashes.add(fh)
            recent_resumes.append(doc)
    return len(pdfs.data), len(resume_hashes), recent_resumes[:5]

def get_log_stats(log_path="/tmp/resume_processing_full_ai.log"):
    total_gemini = 0
    total_groq = 0
    error_lines = []
    processed_lines = []
    try:
        with open(log_path, 'r') as f:
            for line in f:
                if "Gemini" in line:
                    total_gemini += 1
                if "Groq" in line:
                    total_groq += 1
                if "error" in line.lower() or "fail" in line.lower():
                    error_lines.append(line.strip())
                if "Processing:" in line:
                    processed_lines.append(line.strip())
        last10 = processed_lines[-10:]
        errors = error_lines[-5:]
        return total_gemini, total_groq, last10, errors
    except Exception:
        return 0, 0, [], []

def display_status():
    pdfs_scanned, unique_resumes, recent_docs = get_totals()
    gemini_ct, groq_ct, last10, errors = get_log_stats()
    print("\033[2J\033[H", end="")
    print("="*80)
    print(f"Total PDFs scanned: {pdfs_scanned}")
    print(f"Unique resumes identified by AI: {unique_resumes}")
    print(f"Gemini LLM calls: {gemini_ct} | Groq LLM calls: {groq_ct}")
    print("")
    print("Most recent resumes w/ AI folder proposal:")
    for d in recent_docs:
        name = d.get('file_name','??')[:40]
        struct = d.get('suggested_folder_structure','N/A')
        time_ = d.get('updated_at','')[:19]
        print(f" - {name}")
        print(f"   \U0001F4C1 {struct}")
        print(f"   ⏰ {time_}")
    print("")
    print("Last 10 processed files:")
    for l in last10:
        print("  " + l)
    if errors:
        print("\nErrors/warnings (last 5):")
        for e in errors:
            print("  " + e)
    print("")
    print(f"🕐 Last update: {datetime.now().strftime('%H:%M:%S')}")
    print("="*80)

def main():
    try:
        while True:
            display_status()
            time.sleep(6)
    except KeyboardInterrupt:
        print("\nEnded monitor.")

if __name__ == "__main__":
    main()
