#!/usr/bin/env python3
"""
Copy all resumes to Employment/Resumes/
Finds resumes by filename and by content analysis
"""
import os
import shutil
import re
from pathlib import Path
from supabase import create_client

# Target location
TARGET_BASE = Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "Employment" / "Resumes"
TARGET_BASE.mkdir(parents=True, exist_ok=True)

# Supabase connection
SUPABASE_URL = "http://127.0.0.1:54421"
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def is_resume_by_content(file_path):
    """Check if file content looks like a resume"""
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(file_path)
        text = ""
        for page in reader.pages[:3]:  # Check first 3 pages
            text += page.extract_text().lower()
        
        # Resume indicators
        resume_keywords = [
            "work experience", "employment history", "professional experience",
            "education", "skills", "summary", "objective", "contact",
            "phone", "email", "years of experience", "responsibilities",
            "achievements", "qualifications", "references"
        ]
        
        matches = sum(1 for keyword in resume_keywords if keyword in text)
        return matches >= 3  # At least 3 resume indicators
    except:
        return False

def extract_person_name(file_path, entities=None):
    """Extract person name from filename or entities"""
    filename = Path(file_path).stem
    
    # Try entities first
    if entities and entities.get("people"):
        return entities["people"][0]
    
    # Try filename patterns
    # Pattern: FirstNameLastNameResume or FirstName_LastName_Resume
    name_match = re.search(r"([A-Z][a-z]+[A-Z][a-z]+)", filename)
    if name_match:
        full_name = name_match.group(1)
        # Split camelCase: "MichaelValderrama" -> "Michael Valderrama"
        person_name = re.sub(r"([a-z])([A-Z])", r"\1 \2", full_name)
        return person_name
    
    return None

print("🔍 Finding all resumes...")
print("")

# 1. Find by filename (contains "resume")
print("1. Searching by filename (contains 'resume')...")
result = supabase.table('documents').select('id,file_name,current_path,entities').or_('file_name.ilike.%resume%').execute()

resumes_found = {}
for doc in result.data:
    file_path = doc.get('current_path')
    if file_path and os.path.exists(file_path):
        person_name = extract_person_name(file_path, doc.get('entities'))
        if person_name:
            target_dir = TARGET_BASE / person_name
        else:
            target_dir = TARGET_BASE / "Other"
        
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = target_dir / Path(file_path).name
        
        # Handle duplicates
        if target_file.exists():
            stem = target_file.stem
            ext = target_file.suffix
            counter = 1
            while target_file.exists():
                target_file = target_dir / f"{stem}_{counter}{ext}"
                counter += 1
        
        resumes_found[str(file_path)] = str(target_file)

print(f"   Found {len(resumes_found)} files with 'resume' in filename")

# 2. Find by content (employment category, check content)
print("2. Checking employment documents for resume content...")
result = supabase.table('documents').select('id,file_name,current_path,entities,ai_category').eq('ai_category', 'employment').execute()

content_resumes = 0
for doc in result.data:
    file_path = doc.get('current_path')
    if not file_path or not os.path.exists(file_path):
        continue
    
    # Skip if already found by filename
    if str(file_path) in resumes_found:
        continue
    
    # Check if it's actually a resume by content
    if is_resume_by_content(file_path):
        person_name = extract_person_name(file_path, doc.get('entities'))
        if person_name:
            target_dir = TARGET_BASE / person_name
        else:
            target_dir = TARGET_BASE / "Other"
        
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = target_dir / Path(file_path).name
        
        # Handle duplicates
        if target_file.exists():
            stem = target_file.stem
            ext = target_file.suffix
            counter = 1
            while target_file.exists():
                target_file = target_dir / f"{stem}_{counter}{ext}"
                counter += 1
        
        resumes_found[str(file_path)] = str(target_file)
        content_resumes += 1

print(f"   Found {content_resumes} additional resumes by content analysis")
print("")

# Copy all files
print(f"📋 Copying {len(resumes_found)} resumes to Employment/Resumes/...")
print("")

copied = 0
for source, target in resumes_found.items():
    try:
        shutil.copy2(source, target)
        print(f"✅ Copied: {Path(source).name}")
        print(f"   To: {Path(target).parent.name}/{Path(target).name}")
        copied += 1
    except Exception as e:
        print(f"❌ Failed: {Path(source).name} - {e}")

print("")
print(f"✅ Done! Copied {copied} resumes to:")
print(f"   {TARGET_BASE}")
