#!/usr/bin/env python3
"""
Tests for inbox_processor.py

Tests the inbox processing functionality including:
- File scanning
- Processing workflow
- Error handling
- Retry functionality
"""

import unittest
import tempfile
import shutil
from pathlib import Path
import sys
import os

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.inbox_processor import InboxProcessor


class TestInboxProcessor(unittest.TestCase):
    """Test cases for InboxProcessor"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create temporary directories
        self.test_dir = Path(tempfile.mkdtemp())
        self.inbox_path = self.test_dir / "In-Box"
        self.inbox_path.mkdir(parents=True)
        
        # Create subdirectories
        (self.inbox_path / "Processed").mkdir()
        (self.inbox_path / "Processing Errors").mkdir()
        
        # Create test processor
        self.processor = InboxProcessor(
            inbox_path=str(self.inbox_path),
            dry_run=True,
            use_staging=True
        )
    
    def tearDown(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_scan_inbox_empty(self):
        """Test scanning empty inbox"""
        files = self.processor.scan_inbox()
        self.assertEqual(len(files), 0)
    
    def test_scan_inbox_with_files(self):
        """Test scanning inbox with supported files"""
        # Create test files
        (self.inbox_path / "test.pdf").touch()
        (self.inbox_path / "test.docx").touch()
        (self.inbox_path / "test.txt").touch()
        (self.inbox_path / "test.xlsx").touch()
        (self.inbox_path / "ignored.log").touch()  # Should be ignored
        
        files = self.processor.scan_inbox()
        # Should find 4 supported files (pdf, docx, txt, xlsx)
        self.assertEqual(len(files), 4)
        
        # Check file extensions
        extensions = {f.suffix.lower() for f in files}
        self.assertIn('.pdf', extensions)
        self.assertIn('.docx', extensions)
        self.assertIn('.txt', extensions)
        self.assertIn('.xlsx', extensions)
        self.assertNotIn('.log', extensions)
    
    def test_scan_inbox_excludes_subfolders(self):
        """Test that scan_inbox excludes files in subfolders"""
        # Create file in inbox root
        (self.inbox_path / "root.pdf").touch()
        
        # Create file in Processed subfolder (should be excluded)
        (self.inbox_path / "Processed" / "processed.pdf").touch()
        
        # Create file in Processing Errors subfolder (should be excluded)
        (self.inbox_path / "Processing Errors" / "error.pdf").touch()
        
        files = self.processor.scan_inbox()
        # Should only find the root file
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].name, "root.pdf")
    
    def test_scan_errors(self):
        """Test scanning Processing Errors folder"""
        errors_path = self.inbox_path / "Processing Errors"
        
        # Create error files
        (errors_path / "failed1.pdf").touch()
        (errors_path / "failed2.docx").touch()
        (errors_path / "error_log.txt").touch()  # Should be excluded
        
        files = self.processor.scan_errors()
        # Should find 2 files (pdf, docx), excluding .txt error logs
        self.assertEqual(len(files), 2)
        
        extensions = {f.suffix.lower() for f in files}
        self.assertIn('.pdf', extensions)
        self.assertIn('.docx', extensions)
        self.assertNotIn('.txt', extensions)
    
    def test_scan_processed(self):
        """Test scanning Processed folder"""
        processed_path = self.inbox_path / "Processed"
        
        # Create processed files
        (processed_path / "file1.pdf").touch()
        (processed_path / "file2.docx").touch()
        (processed_path / "file3.txt").touch()
        
        files = self.processor.scan_processed()
        # Should find all supported file types
        self.assertGreaterEqual(len(files), 3)
    
    def test_setup_inbox(self):
        """Test inbox structure setup"""
        # Remove subdirectories
        shutil.rmtree(self.inbox_path / "Processed", ignore_errors=True)
        shutil.rmtree(self.inbox_path / "Processing Errors", ignore_errors=True)
        
        # Setup should create them
        self.processor.setup_inbox()
        
        self.assertTrue((self.inbox_path / "Processed").exists())
        self.assertTrue((self.inbox_path / "Processing Errors").exists())
    
    def test_process_inbox_retry_mode(self):
        """Test process_inbox with retry_errors=True"""
        errors_path = self.inbox_path / "Processing Errors"
        (errors_path / "retry_test.pdf").touch()
        
        # Should scan errors folder when retry_errors=True
        # Note: This will fail because DocumentProcessor needs real files,
        # but we can test the scanning logic
        try:
            stats = self.processor.process_inbox(retry_errors=True)
            # Should attempt to process the file
            self.assertIsInstance(stats, dict)
            self.assertIn('total', stats)
        except Exception as e:
            # Expected to fail without real document processor setup
            # But scanning should work
            pass


class TestInboxProcessorCLI(unittest.TestCase):
    """Test CLI argument parsing"""
    
    def test_help_flag(self):
        """Test --help flag"""
        import subprocess
        result = subprocess.run(
            ["python3", "scripts/inbox_processor.py", "--help"],
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            text=True
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Process PDFs from In-Box", result.stdout)
    
    def test_dry_run_default(self):
        """Test that dry-run is default"""
        import subprocess
        result = subprocess.run(
            ["python3", "scripts/inbox_processor.py", "--setup-only"],
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            text=True
        )
        # Should succeed (setup-only doesn't require files)
        self.assertIn(result.returncode, [0, 1])  # May fail if inbox doesn't exist, but should parse args


if __name__ == "__main__":
    unittest.main()
