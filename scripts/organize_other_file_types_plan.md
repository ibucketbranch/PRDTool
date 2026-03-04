# Plan: Organizing Other File Types from Google Drive

## Current Status
- ✅ PDFs: Supported (162 unique PDFs need processing)
- ❌ .doc/.docx: 2,022 files - NOT supported yet
- ❌ .xls/.xlsx: 499 files - NOT supported yet  
- ❌ .ppt/.pptx: 463 files - NOT supported yet
- ❌ .txt: 190 files - Easy to add
- ❌ .rtf: 56 files - Easy to add

## Solution: Extend Document Processor

### Step 1: Add Text Extraction Libraries
```bash
pip install python-docx openpyxl python-pptx
```

### Step 2: Modify document_processor.py
- Add `extract_text_from_docx()` method
- Add `extract_text_from_xlsx()` method  
- Add `extract_text_from_pptx()` method
- Modify `extract_text_and_metadata()` to detect file type and route accordingly

### Step 3: Organization Strategy (Same as PDFs)

**The system will automatically organize based on:**
1. **Filename** - Primary signal (e.g., "Resume", "Bank Statement", "W2")
2. **Content** - What the document actually contains
3. **Original Path** - Where it was stored (shows user's intent)

**Organization into Bins:**
- **Work Bin** - Resumes, employment docs, work projects
- **Finances Bin** - Bank statements, tax docs, invoices, receipts
- **Legal Bin** - Contracts, court documents, legal correspondence
- **Personal Bin** - Medical records, identity docs, personal correspondence
- **Projects Bin** - Project files, presentations, technical docs

**Hierarchical Structure Examples:**
- Resume: `Work Bin/Employment/Resumes/Michael Valderrama`
- Bank Statement: `Finances Bin/Statements/2024/Bank of America`
- Tax Doc: `Finances Bin/Taxes/2024`
- Legal Contract: `Legal Bin/Contracts/2024`
- Medical Record: `Personal Bin/Medical/Records`

## Implementation Priority

### Phase 1: Easy Wins (Text-based)
1. ✅ .txt files - Just read file
2. ✅ .rtf files - Use striprtf library

### Phase 2: Office Documents  
3. ✅ .docx files - python-docx
4. ✅ .xlsx files - openpyxl (extract text from cells)
5. ✅ .pptx files - python-pptx (extract text from slides)

### Phase 3: Legacy Formats
6. ⚠️ .doc files - Requires antiword or LibreOffice conversion
7. ⚠️ .xls files - Requires xlrd (legacy) or conversion
8. ⚠️ .ppt files - Requires conversion to pptx

## Recommendation

**For Google Drive cleanup:**
1. Process all PDFs first (162 files) - already supported
2. Add support for .docx, .xlsx, .pptx (most common modern formats)
3. Process those files (1,784 files)
4. For legacy .doc, .xls, .ppt - convert to modern formats or skip if low priority

**Total to process:**
- PDFs: 162 files
- Modern Office: 1,784 files (.docx, .xlsx, .pptx)
- Legacy Office: 1,250 files (.doc, .xls, .ppt) - lower priority
- Text files: 246 files (.txt, .rtf)

**Total important documents: ~3,442 files**
