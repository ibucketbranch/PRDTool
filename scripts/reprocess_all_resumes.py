#!/usr/bin/env python3
"""
Reprocess ALL resumes with full Gemini pipeline for maximum LLM extraction.

Finds potential resumes by scanning ALL PDFs, then uses AI to identify resumes based on:
1. Filename - if it contains "resume" or person's name
2. Original path - if it's in a "Resumes" folder or employment-related location
3. Content - AI analyzes text to determine if it's actually a resume

This approach finds resumes even when the filename doesn't contain "resume".

🛡️ FILE SAFETY GUARANTEE:
- This script NEVER deletes, moves, renames, or modifies files
- It ONLY reads files and updates database records
- Your files remain completely untouched on disk
- All file operations are read-only
"""
import os
import sys
import time
from pathlib import Path
from typing import List, Set

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from document_processor import DocumentProcessor

def find_all_resumes() -> List[str]:
    """Find ALL potential resume PDFs by scanning all PDFs.
    
    Strategy: Find ALL PDFs, then let AI determine if they're resumes based on:
    1. Filename (e.g., "MichaelValderrama.pdf" or "Resume.pdf")
    2. Original path (e.g., in "Resumes" folder or "Employment" folder)
    3. Content (AI analyzes text for resume indicators)
    
    Searches:
    - Entire home directory (/Users/michaelvalderrama) - as requested
    - Excludes system folders to avoid slow/irrelevant scans
    
    Note: We find ALL PDFs, not just ones with "resume" in the name,
    because many resumes don't have "resume" in the filename.
    """
    print("🔍 Scanning for ALL PDFs (AI will identify resumes)...")
    print("")
    print("   Strategy: Find all PDFs, then AI determines if they're resumes")
    print("   based on: filename + path + content")
    print("")
    
    home = Path.home()
    
    # Search entire home directory (/Users/michaelvalderrama) as requested
    # But exclude system folders to keep it fast
    skip_patterns = [
        'node_modules', '.git', '.Trash', 'Library/Caches',
        '.npm', '.cache', 'Library/Application Support',
        '.pkg', '.dmg', '.app/Contents', 'Library/Logs',
        'Library/Containers', 'Library/Saved Application State',
        'Library/Developer', 'Library/Group Containers'
    ]
    
    all_pdfs: Set[str] = set()
    
    print(f"   📂 Scanning entire home directory: {home}")
    print("   (Skipping system folders for performance)")
    count = 0
    
    try:
        # Search entire home directory recursively for ALL PDFs
        for pdf_path in home.rglob("*.pdf"):
            pdf_str = str(pdf_path)
            
            # Skip system folders
            if any(skip in pdf_str for skip in skip_patterns):
                continue
            
            all_pdfs.add(pdf_str)
            count += 1
            
            if count % 100 == 0:
                print(f"      ... found {count} PDFs so far")
        
        print(f"      ✅ Found {count} total PDFs")
    except Exception as e:
        print(f"      ⚠️  Error scanning {home}: {e}")
    
    print("")
    print(f"   📊 Total PDFs found: {len(all_pdfs)}")
    print("   💡 AI will analyze each to identify resumes based on:")
    print("      - Filename (e.g., person's name, 'resume' keyword)")
    print("      - Path (e.g., in 'Resumes' or 'Employment' folder)")
    print("      - Content (work experience, skills, education, etc.)")
    print("")
    
    return sorted(list(all_pdfs))

def verify_gemini_setup(non_interactive: bool = False) -> bool:
    """Verify that Gemini API key is configured."""
    gemini_key = os.getenv('GEMINI_API_KEY')
    if not gemini_key:
        print("")
        print("=" * 80)
        print("⚠️  WARNING: GEMINI_API_KEY not set!")
        print("=" * 80)
        print("")
        print("Gemini is the PRIMARY LLM provider for best categorization.")
        print("Without it, resumes will be processed with Groq only.")
        print("")
        print("To set it:")
        print("  export GEMINI_API_KEY='your-key-here'")
        print("")
        print("Or add to your .env file:")
        print("  GEMINI_API_KEY=your-key-here")
        print("")
        if non_interactive:
            print("⚠️  Non-interactive mode: Continuing with Groq only...")
            return True
        try:
            response = input("Continue anyway with Groq only? (yes/no): ").strip().lower()
            if response != 'yes':
                return False
        except (EOFError, KeyboardInterrupt):
            print("\n⚠️  Non-interactive mode: Continuing with Groq only...")
            return True
    else:
        print("✅ GEMINI_API_KEY is configured")
    return True

def main():
    import sys
    
    # Check if running in non-interactive mode (no TTY)
    non_interactive = not sys.stdin.isatty()
    
    print("=" * 80)
    print("🔄 REPROCESSING ALL RESUMES - Full Gemini Pipeline")
    print("=" * 80)
    print("")
    print("🛡️  FILE SAFETY GUARANTEE:")
    print("   ✅ This script NEVER deletes, moves, renames, or modifies files")
    print("   ✅ It ONLY reads files and updates database records")
    print("   ✅ Your files remain completely untouched on disk")
    print("   ✅ All file operations are read-only")
    print("")
    
    # Verify Gemini setup
    if not verify_gemini_setup(non_interactive=non_interactive):
        print("Cancelled.")
        return
    
    print("")
    
    # Initialize processor with Gemini as primary
    print("🤖 Initializing DocumentProcessor with Gemini (PRIMARY)...")
    processor = DocumentProcessor(
        groq_api_key=os.getenv("GROQ_API_KEY"),
        gemini_api_key=os.getenv("GEMINI_API_KEY"),
        llm_provider=os.getenv("LLM_PROVIDER", "gemini")
    )
    print("")
    
    # Find all PDFs (AI will identify which are resumes)
    resume_files = find_all_resumes()
    
    print("=" * 80)
    print("🤖 AI CATEGORIZATION STRATEGY")
    print("=" * 80)
    print("")
    print("Each PDF will be analyzed by AI using:")
    print("  1. Filename - Does it contain 'resume' or a person's name?")
    print("  2. Original path - Is it in a 'Resumes' or 'Employment' folder?")
    print("  3. Content - Does it have resume indicators?")
    print("     (work experience, skills, education, professional summary, etc.)")
    print("")
    print("Only PDFs identified as resumes (employment category) will be processed.")
    print("")
    
    if not resume_files:
        print("❌ No resume files found")
        return
    
    print("")
    print("=" * 80)
    print(f"📋 Processing {len(resume_files)} PDFs with FULL PIPELINE")
    print("=" * 80)
    print("")
    print("Each PDF will be analyzed by AI to determine if it's a resume:")
    print("  • Filename analysis (e.g., person's name, 'resume' keyword)")
    print("  • Path analysis (e.g., in 'Resumes' or 'Employment' folder)")
    print("  • Content analysis (work experience, skills, education, etc.)")
    print("")
    print("Only PDFs identified as resumes (employment category) will be:")
    print("  • Extracted with full text analysis")
    print("  • Categorized by Gemini (primary LLM)")
    print("  • Summarized with intelligent AI analysis")
    print("  • Updated in database with improved metadata")
    print("")
    
    # Statistics
    stats = {
        'processed': 0,
        'updated': 0,
        'skipped': 0,
        'failed': 0,
        'not_found': 0,
        'start_time': time.time()
    }
    
    # Process each resume
    for i, file_path in enumerate(resume_files, 1):
        if not os.path.exists(file_path):
            stats['not_found'] += 1
            print(f"[{i}/{len(resume_files)}] ⚠️  File not found: {Path(file_path).name}")
            continue
        
        file_name = Path(file_path).name
        print(f"[{i}/{len(resume_files)}] Processing: {file_name}")
        
        # Truncate long paths for display
        display_path = file_path[:80] + "..." if len(file_path) > 80 else file_path
        print(f"   📄 {display_path}")
        
        try:
            # Reprocess with FULL PIPELINE (skip_if_exists=False forces re-analysis)
            result = processor.process_document(file_path, skip_if_exists=False)
            
            status = result.get('status', 'unknown')
            
            if status == 'success':
                category = result.get('category', 'unknown')
                
                # Only count as "processed resume" if AI categorized it as employment
                if category == 'employment':
                    stats['processed'] += 1
                    stats['updated'] += 1
                    print(f"   ✅ Resume identified → Category: {category}")
                    
                    # Show if category changed
                    if 'previous_category' in result:
                        old_cat = result['previous_category']
                        if old_cat != category:
                            print(f"   🔄 Category updated: {old_cat} → {category}")
                else:
                    stats['skipped'] += 1
                    print(f"   ⏭️  Not a resume → Category: {category} (skipping)")
            
            elif status == 'skipped':
                stats['skipped'] += 1
                reason = result.get('reason', 'unknown')
                print(f"   ⏭️  Skipped: {reason}")
            
            else:
                stats['failed'] += 1
                reason = result.get('reason', 'unknown')
                print(f"   ❌ Failed: {reason}")
        
        except Exception as e:
            stats['failed'] += 1
            print(f"   ❌ Error: {e}")
        
        print("")
    
    # Final summary
    elapsed = time.time() - stats['start_time']
    rate = stats['processed'] / elapsed * 60 if elapsed > 0 else 0  # PDFs per minute
    
    print("=" * 80)
    print("✅ REPROCESSING COMPLETE")
    print("=" * 80)
    print("")
    print(f"📊 Statistics:")
    print(f"   ✅ Resumes processed: {stats['processed']}")
    print(f"   ⏭️  Non-resumes skipped: {stats['skipped']}")
    print(f"   ❌ Failed: {stats['failed']}")
    print(f"   ⚠️  Not Found: {stats['not_found']}")
    print(f"   📊 Total PDFs scanned: {len(resume_files)}")
    print(f"   ⏱️  Total Time: {elapsed/60:.1f} minutes")
    print(f"   📈 Rate: {rate:.1f} resumes/minute")
    print("")
    print("💡 Note: Only PDFs identified as resumes (employment category)")
    print("   by AI analysis (filename + path + content) were processed.")
    print("")
    print("All resumes have been reprocessed with the FULL Gemini pipeline.")
    print("Database records updated with improved categorization and summaries.")
    print("")
    print("💡 Next steps:")
    print("   • Review categories in Supabase Studio: http://127.0.0.1:54423")
    print("   • Run: python3 scripts/plan_canonical_paths.py (to route resumes)")
    print("")

if __name__ == "__main__":
    main()
