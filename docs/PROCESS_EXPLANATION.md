# Document Processing Flow - How It Works

## The Process (Step by Step)

### 1. **Find PDFs** (reprocess_by_priority.py)
- Scans file system: iCloud Drive, Documents, Downloads, Websites
- Matches PDFs by keywords in filename or path
- Example: Finds all PDFs with "resume" in name or path

### 2. **Process Each PDF** (document_processor.py)
For each PDF found:

#### Step 2a: Identify the File
- Calculate SHA256 hash of the file (unique fingerprint)
- Check database: "Does a document with this hash already exist?"
- **Key Point**: Same file = same hash, even if moved/renamed

#### Step 2b: Extract Content
- Extract text from PDF
- If text is low/empty → use Vision (OCR) to read images
- Extract metadata (title, author, page count, etc.)

#### Step 2c: Intelligent Categorization
- AI analyzes: **Filename + Content + Path** (in that priority)
- AI categorizes: employment, bank_statement, tax_document, etc.
- AI generates summary and tags

#### Step 2d: Update Database
**THIS IS THE CRITICAL PART:**

```python
if existing_document:
    # Document already in DB (found by hash)
    document_id = existing_document['id']
    
    # 1. DELETE old category links (clean up)
    delete old category associations
    
    # 2. UPDATE the existing record (OVERWRITE, not duplicate)
    update documents table WHERE id = document_id
    # This REPLACES all fields with new data:
    # - ai_category (new intelligent category)
    # - ai_summary (new summary)
    # - extracted_text (re-extracted)
    # - confidence_score (new confidence)
    # - current_path (updated if moved)
    
else:
    # New document - INSERT new record
    insert into documents table
```

### 3. **Link Categories**
- Delete old category links
- Create new category links based on AI categorization
- Links document to category table (many-to-many relationship)

## Database Tables Used

1. **`documents`** - Main table (ONE record per unique file)
   - Identified by `file_hash` (SHA256)
   - **UPDATED** if file already processed
   - **INSERTED** if new file

2. **`document_categories`** - Links documents to categories
   - **DELETED** then recreated on update
   - Prevents duplicate category links

3. **`categories`** - Category definitions
   - Created if doesn't exist
   - Reused if exists

## Key Points

✅ **NO DUPLICATES**: Same file (same hash) = same database record  
✅ **OVERWRITES**: Existing records are updated, not duplicated  
✅ **CLEAN**: Old category links are deleted before adding new ones  
✅ **ONE SOURCE OF TRUTH**: File hash is the unique identifier

## What Gets Updated

When reprocessing with `skip_if_exists=False`:

- ✅ `ai_category` - New intelligent category
- ✅ `ai_summary` - New summary
- ✅ `ai_subcategories` - New subcategories
- ✅ `confidence_score` - New confidence
- ✅ `extracted_text` - Re-extracted text
- ✅ `entities` - Re-extracted entities
- ✅ `current_path` - Updated if file moved
- ✅ `folder_hierarchy` - Updated folder structure
- ✅ Category links - Deleted and recreated

## Example Flow

```
1. Find: "MichaelValderramaResume.pdf"
2. Hash: abc123... (calculate SHA256)
3. Check DB: "Does hash abc123... exist?" → YES (found existing record ID: 42)
4. Process: Extract text, AI categorizes as "employment"
5. Update: UPDATE documents WHERE id=42 SET ai_category='employment', ...
6. Clean: DELETE document_categories WHERE document_id=42
7. Link: INSERT document_categories (document_id=42, category_id=employment)
```

**Result**: Same record (ID: 42) updated with new categorization. No duplicate created.
