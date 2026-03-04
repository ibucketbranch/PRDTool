#!/usr/bin/env python3
"""
Filing Manager: Checks existing folders before creating new ones.
Prevents duplicate folder creation by matching documents to existing folder structures.
"""
import os
import re
from pathlib import Path
from collections import defaultdict

icloud_base = "/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs"

SKIP_PATTERNS = [
    'node_modules', '.git', '__pycache__', '.xcodeproj', '.xcworkspace',
    'build/', 'dist/', 'lib/', 'src/', 'test/', 'tests/',
    'ProjectGatita', 'XcodeProjects', 'PhoneGapLib'
]

class FilingManager:
    """Manages folder structure by checking existing folders before creating new ones."""
    
    def __init__(self, base_path=None):
        self.base_path = base_path or icloud_base
        self.folder_index = None
        self._build_index()
    
    def normalize_name(self, name):
        """Normalize name for matching."""
        name = os.path.splitext(name)[0].lower()
        name = re.sub(r'\d{4}', '', name)  # Remove years
        name = re.sub(r'\d+', '', name)  # Remove numbers
        name = re.sub(r'\s*(v\d+|version\d+|rev\d+|copy|backup).*$', '', name, flags=re.IGNORECASE)
        name = re.sub(r'[^a-z]', '', name)
        return name.strip()
    
    def _build_index(self):
        """Build index of existing folders."""
        print("🗂️  Building folder index...")
        self.folder_index = defaultdict(list)
        
        for root, dirs, files in os.walk(self.base_path):
            dirs[:] = [d for d in dirs if not any(pattern in d for pattern in SKIP_PATTERNS)]
            if any(pattern in root for pattern in SKIP_PATTERNS):
                continue
            
            for d in dirs:
                folder_path = os.path.join(root, d)
                relative = os.path.relpath(folder_path, self.base_path)
                normalized = self.normalize_name(d)
                
                if normalized and len(normalized) >= 3:
                    self.folder_index[normalized].append({
                        'name': d,
                        'path': folder_path,
                        'relative': relative,
                        'normalized': normalized
                    })
        
        print(f"   Indexed {len(self.folder_index)} folder patterns")
    
    def find_existing_folder(self, suggested_structure, ai_category=None, context_bin=None):
        """
        Find existing folder that matches the suggested structure.
        Returns the best matching existing folder path, or None if no match.
        """
        if not suggested_structure:
            return None
        
        # Extract key folder names from suggested structure
        parts = [p.strip() for p in suggested_structure.split('/') if p.strip()]
        if not parts:
            return None
        
        # Try to match the last/most specific folder name
        target_folder_name = parts[-1]
        normalized_target = self.normalize_name(target_folder_name)
        
        if normalized_target in self.folder_index:
            candidates = self.folder_index[normalized_target]
            
            # Score candidates based on:
            # 1. Location in logical bins (Employment, Work Bin, etc.)
            # 2. Path similarity to suggested structure
            # 3. Context bin match
            
            best_match = None
            best_score = -1
            
            for candidate in candidates:
                score = 0
                relative = candidate['relative'].lower()
                
                # Prefer folders in logical locations
                if context_bin and context_bin.lower() in relative:
                    score += 100
                
                # Prefer folders matching suggested structure parts
                for part in parts:
                    if part.lower() in relative:
                        score += 10
                
                # Prefer shorter paths (less nested)
                score -= len(relative.split('/')) * 2
                
                if score > best_score:
                    best_score = score
                    best_match = candidate
            
            if best_match and best_score > 0:
                return best_match['path']
        
        return None
    
    def get_target_folder(self, suggested_structure, ai_category=None, context_bin=None, file_name=None):
        """
        Get target folder for a document, using existing folder if available.
        Returns: (target_folder_path, should_create_new)
        """
        # First, try to find existing matching folder
        existing = self.find_existing_folder(suggested_structure, ai_category, context_bin)
        
        if existing:
            # Use existing folder
            return existing, False
        
        # No existing folder found, create new one based on suggested structure
        if suggested_structure:
            target = os.path.join(self.base_path, suggested_structure)
            return target, True
        
        # Fallback: use context bin + category
        if context_bin:
            category = ai_category.replace('_', ' ').title() if ai_category else 'Other'
            target = os.path.join(self.base_path, context_bin, category)
            return target, True
        
        # Final fallback
        target = os.path.join(self.base_path, 'Documents', 'Uncategorized')
        return target, True

def test_filing_manager():
    """Test the filing manager."""
    print("="*80)
    print("🧪 TESTING FILING MANAGER")
    print("="*80)
    
    fm = FilingManager()
    
    # Test cases
    test_cases = [
        {
            'suggested': 'Work Bin/Employment/Resumes/Michael Valderrama',
            'category': 'employment',
            'context_bin': 'Work Bin',
            'file_name': 'Resume_Intel_2024.pdf'
        },
        {
            'suggested': 'Finances Bin/Statements/2024/Bank of America',
            'category': 'bank_statement',
            'context_bin': 'Finances Bin',
            'file_name': 'eStmt_2024-08.pdf'
        },
        {
            'suggested': 'Legal Bin/Contracts/Product Development',
            'category': 'contract',
            'context_bin': 'Legal Bin',
            'file_name': 'GoPro_Contract_2024.docx'
        }
    ]
    
    print("\n📋 Test Results:")
    for i, test in enumerate(test_cases, 1):
        print(f"\n{i}. File: {test['file_name']}")
        print(f"   Suggested: {test['suggested']}")
        
        target, is_new = fm.get_target_folder(
            test['suggested'],
            test['category'],
            test['context_bin'],
            test['file_name']
        )
        
        relative = os.path.relpath(target, icloud_base)
        if is_new:
            print(f"   → Will create: {relative}")
        else:
            print(f"   → Use existing: {relative}")

if __name__ == "__main__":
    test_filing_manager()
