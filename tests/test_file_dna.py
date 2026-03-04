"""Tests for file_dna module - FileDNA, DNARegistry, and tag extraction.

Covers:
- FileDNA dataclass creation and serialization
- compute_file_hash() for SHA-256 hashing
- get_content_preview() for text extraction
- extract_tags() with LLM (mock) and keyword fallback
- DNARegistry load/save/register/lookup operations
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from organizer.file_dna import (
    DNARegistry,
    FileDNA,
    TagExtractionResult,
    compute_file_hash,
    extract_tags,
    get_content_preview,
)


class TestFileDNA:
    """Tests for FileDNA dataclass."""

    def test_create_file_dna(self) -> None:
        """Should create FileDNA with required fields."""
        dna = FileDNA(
            file_path="/path/to/file.pdf",
            sha256_hash="abc123def456",
        )
        assert dna.file_path == "/path/to/file.pdf"
        assert dna.sha256_hash == "abc123def456"
        assert dna.content_summary == ""
        assert dna.auto_tags == []
        assert dna.origin == ""
        assert dna.routed_to == ""
        assert dna.duplicate_of == ""
        assert dna.model_used == ""
        # first_seen_at should be auto-set
        assert dna.first_seen_at != ""

    def test_create_file_dna_with_all_fields(self) -> None:
        """Should create FileDNA with all optional fields."""
        dna = FileDNA(
            file_path="/path/to/file.pdf",
            sha256_hash="abc123",
            content_summary="This is a tax document...",
            auto_tags=["tax_doc", "2024", "IRS"],
            origin="inbox",
            first_seen_at="2024-01-15T10:30:00",
            routed_to="/Finances Bin/Taxes/2024",
            duplicate_of="/original/path.pdf",
            model_used="llama3.1:8b",
        )
        assert dna.content_summary == "This is a tax document..."
        assert dna.auto_tags == ["tax_doc", "2024", "IRS"]
        assert dna.origin == "inbox"
        assert dna.first_seen_at == "2024-01-15T10:30:00"
        assert dna.routed_to == "/Finances Bin/Taxes/2024"
        assert dna.duplicate_of == "/original/path.pdf"
        assert dna.model_used == "llama3.1:8b"

    def test_to_dict(self) -> None:
        """Should convert FileDNA to dictionary."""
        dna = FileDNA(
            file_path="/path/to/file.pdf",
            sha256_hash="abc123",
            auto_tags=["tax", "2024"],
            origin="scan",
        )
        d = dna.to_dict()
        assert d["file_path"] == "/path/to/file.pdf"
        assert d["sha256_hash"] == "abc123"
        assert d["auto_tags"] == ["tax", "2024"]
        assert d["origin"] == "scan"

    def test_from_dict(self) -> None:
        """Should create FileDNA from dictionary."""
        data = {
            "file_path": "/path/to/file.pdf",
            "sha256_hash": "xyz789",
            "content_summary": "Content preview",
            "auto_tags": ["invoice"],
            "origin": "import",
            "first_seen_at": "2024-02-01T12:00:00",
            "routed_to": "/destination",
            "duplicate_of": "",
            "model_used": "qwen2.5:14b",
        }
        dna = FileDNA.from_dict(data)
        assert dna.file_path == "/path/to/file.pdf"
        assert dna.sha256_hash == "xyz789"
        assert dna.content_summary == "Content preview"
        assert dna.auto_tags == ["invoice"]
        assert dna.origin == "import"
        assert dna.model_used == "qwen2.5:14b"

    def test_from_dict_missing_fields(self) -> None:
        """Should handle missing fields with defaults."""
        data = {"file_path": "/path.pdf"}
        dna = FileDNA.from_dict(data)
        assert dna.file_path == "/path.pdf"
        assert dna.sha256_hash == ""
        assert dna.auto_tags == []

    def test_roundtrip(self) -> None:
        """Should roundtrip through to_dict/from_dict."""
        original = FileDNA(
            file_path="/test/path.pdf",
            sha256_hash="hash123",
            auto_tags=["tag1", "tag2"],
            origin="inbox",
        )
        restored = FileDNA.from_dict(original.to_dict())
        assert restored.file_path == original.file_path
        assert restored.sha256_hash == original.sha256_hash
        assert restored.auto_tags == original.auto_tags
        assert restored.origin == original.origin


class TestTagExtractionResult:
    """Tests for TagExtractionResult dataclass."""

    def test_create_result(self) -> None:
        """Should create TagExtractionResult."""
        result = TagExtractionResult(
            document_type="tax_return",
            year="2024",
            organizations=["IRS"],
            people=["John Doe"],
            topics=["federal taxes"],
            suggested_tags=["tax_return", "2024", "IRS"],
        )
        assert result.document_type == "tax_return"
        assert result.year == "2024"
        assert result.organizations == ["IRS"]
        assert result.used_keyword_fallback is False
        assert result.confidence == 0.5

    def test_to_tags_list(self) -> None:
        """Should combine all fields into flat tag list."""
        result = TagExtractionResult(
            document_type="invoice",
            year="2023",
            organizations=["Amazon", "Verizon"],
            suggested_tags=["purchase", "electronics"],
        )
        tags = result.to_tags_list()
        assert "invoice" in tags
        assert "2023" in tags
        assert "Amazon" in tags
        assert "Verizon" in tags
        assert "purchase" in tags

    def test_to_tags_list_no_duplicates(self) -> None:
        """Should not duplicate tags that already exist in suggested_tags."""
        result = TagExtractionResult(
            document_type="invoice",
            year="2023",
            suggested_tags=["invoice", "2023", "receipt"],
        )
        tags = result.to_tags_list()
        # Count occurrences
        assert tags.count("invoice") == 1
        assert tags.count("2023") == 1


class TestComputeFileHash:
    """Tests for compute_file_hash() function."""

    def test_hash_small_file(self) -> None:
        """Should compute SHA-256 hash of small file."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"Hello, world!")
            f.flush()
            path = f.name

        try:
            hash_value = compute_file_hash(path)
            # SHA-256 of "Hello, world!" is known
            assert hash_value == "315f5bdb76d078c43b8ac0064e4a0164612b1fce77c869345bfc94c75894edd3"
        finally:
            Path(path).unlink()

    def test_hash_empty_file(self) -> None:
        """Should compute SHA-256 hash of empty file."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            path = f.name

        try:
            hash_value = compute_file_hash(path)
            # SHA-256 of empty content
            assert hash_value == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        finally:
            Path(path).unlink()

    def test_hash_large_file(self) -> None:
        """Should handle files larger than chunk size (8KB)."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
            # Write 20KB of data (larger than 8KB chunk)
            f.write(b"X" * 20480)
            f.flush()
            path = f.name

        try:
            hash_value = compute_file_hash(path)
            assert len(hash_value) == 64  # SHA-256 hex is 64 chars
        finally:
            Path(path).unlink()

    def test_hash_nonexistent_file(self) -> None:
        """Should raise FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            compute_file_hash("/nonexistent/file.pdf")

    def test_hash_directory(self) -> None:
        """Should raise IsADirectoryError for directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(IsADirectoryError):
                compute_file_hash(tmpdir)

    def test_hash_consistent(self) -> None:
        """Should produce consistent hash for same content."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"Consistent content")
            f.flush()
            path = f.name

        try:
            hash1 = compute_file_hash(path)
            hash2 = compute_file_hash(path)
            assert hash1 == hash2
        finally:
            Path(path).unlink()


class TestGetContentPreview:
    """Tests for get_content_preview() function."""

    def test_preview_text_file(self) -> None:
        """Should extract text content preview."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w") as f:
            f.write("This is a test document with some content.")
            f.flush()
            path = f.name

        try:
            preview = get_content_preview(path)
            assert "This is a test document" in preview
        finally:
            Path(path).unlink()

    def test_preview_max_chars(self) -> None:
        """Should respect max_chars limit."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w") as f:
            f.write("A" * 1000)
            f.flush()
            path = f.name

        try:
            preview = get_content_preview(path, max_chars=100)
            assert len(preview) <= 100
        finally:
            Path(path).unlink()

    def test_preview_binary_extension(self) -> None:
        """Should return binary indicator for known binary extensions."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
            f.write(b"PDF content")
            f.flush()
            path = f.name

        try:
            preview = get_content_preview(path)
            assert "[Binary file: .pdf]" in preview
        finally:
            Path(path).unlink()

    def test_preview_image_extension(self) -> None:
        """Should return binary indicator for image files."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f:
            f.write(b"\xff\xd8\xff\xe0")  # JPEG magic bytes
            f.flush()
            path = f.name

        try:
            preview = get_content_preview(path)
            assert "[Binary file: .jpg]" in preview
        finally:
            Path(path).unlink()

    def test_preview_whitespace_normalized(self) -> None:
        """Should normalize excessive whitespace."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w") as f:
            f.write("Line one\n\n\n   Line two   \t\t Line three")
            f.flush()
            path = f.name

        try:
            preview = get_content_preview(path)
            # Multiple spaces/newlines should be collapsed
            assert "  " not in preview or "\n" not in preview
        finally:
            Path(path).unlink()

    def test_preview_nonexistent_file(self) -> None:
        """Should return empty string for nonexistent file."""
        preview = get_content_preview("/nonexistent/file.txt")
        assert preview == ""


class TestExtractTagsWithKeywords:
    """Tests for extract_tags() with keyword fallback (no LLM)."""

    def test_extract_year_from_filename(self) -> None:
        """Should extract year from filename."""
        result = extract_tags("tax_return_2024.pdf", "", use_llm=False)
        assert result.year == "2024"
        assert "2024" in result.suggested_tags

    def test_extract_document_type_tax(self) -> None:
        """Should detect tax document type."""
        result = extract_tags("IRS_1040_form.pdf", "Income tax return", use_llm=False)
        assert result.document_type == "tax_doc"
        assert "tax_doc" in result.suggested_tags

    def test_extract_document_type_invoice(self) -> None:
        """Should detect invoice document type."""
        result = extract_tags("Amazon_Invoice_123.pdf", "Invoice for order", use_llm=False)
        assert result.document_type == "invoice"

    def test_extract_document_type_resume(self) -> None:
        """Should detect resume document type."""
        result = extract_tags("John_Doe_Resume.pdf", "", use_llm=False)
        assert result.document_type == "resume"

    def test_extract_organizations_irs(self) -> None:
        """Should detect IRS organization."""
        result = extract_tags("1040_form.pdf", "IRS Form 1040", use_llm=False)
        assert "IRS" in result.organizations

    def test_extract_organizations_bank(self) -> None:
        """Should detect bank organizations."""
        result = extract_tags("statement.pdf", "Chase Bank statement", use_llm=False)
        assert "Chase" in result.organizations

    def test_extract_multiple_orgs(self) -> None:
        """Should detect multiple organizations."""
        result = extract_tags("bills.pdf", "Verizon AT&T combined bill", use_llm=False)
        assert "Verizon" in result.organizations
        assert "AT&T" in result.organizations

    def test_keyword_fallback_flag(self) -> None:
        """Should set used_keyword_fallback when no LLM."""
        result = extract_tags("test.pdf", "", use_llm=False)
        assert result.used_keyword_fallback is True
        assert result.model_used == ""

    def test_confidence_with_tags(self) -> None:
        """Should have higher confidence when tags found."""
        result = extract_tags("tax_2024.pdf", "IRS form", use_llm=False)
        assert result.confidence >= 0.7  # Has matches

    def test_confidence_no_tags(self) -> None:
        """Should have lower confidence when no tags found."""
        result = extract_tags("random_file.xyz", "", use_llm=False)
        assert result.confidence <= 0.5  # No matches


class TestExtractTagsWithLLM:
    """Tests for extract_tags() with mocked LLM."""

    def test_llm_extraction_success(self) -> None:
        """Should extract tags using LLM when available."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = True
        mock_client.generate.return_value = MagicMock(
            success=True,
            text=json.dumps({
                "document_type": "tax_return",
                "year": "2024",
                "organizations": ["IRS"],
                "people": [],
                "topics": ["federal income tax"],
                "suggested_tags": ["tax_return", "2024", "IRS", "federal"],
                "confidence": 0.92,
            }),
            model_used="llama3.1:8b-instruct-q8_0",
        )

        result = extract_tags(
            "Form_1040_2024.pdf",
            "U.S. Individual Income Tax Return",
            llm_client=mock_client,
            use_llm=True,
        )

        assert result.document_type == "tax_return"
        assert result.year == "2024"
        assert "IRS" in result.organizations
        assert result.model_used == "llama3.1:8b-instruct-q8_0"
        assert result.used_keyword_fallback is False
        assert result.confidence == 0.92

    def test_llm_unavailable_falls_back(self) -> None:
        """Should fall back to keywords when LLM unavailable."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = False

        result = extract_tags(
            "tax_2024.pdf",
            "IRS form content",
            llm_client=mock_client,
            use_llm=True,
        )

        assert result.used_keyword_fallback is True
        # Should still extract from keywords
        assert "2024" in result.suggested_tags or result.year == "2024"

    def test_llm_failure_falls_back(self) -> None:
        """Should fall back to keywords when LLM fails."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = True
        mock_client.generate.return_value = MagicMock(
            success=False,
            text="",
            error="Connection error",
        )

        result = extract_tags(
            "invoice_amazon.pdf",
            "Amazon purchase",
            llm_client=mock_client,
            use_llm=True,
        )

        assert result.used_keyword_fallback is True
        assert "Amazon" in result.organizations or "invoice" in result.document_type

    def test_llm_invalid_json_falls_back(self) -> None:
        """Should fall back to keywords when LLM returns invalid JSON."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = True
        mock_client.generate.return_value = MagicMock(
            success=True,
            text="This is not JSON at all",
            model_used="llama3.1:8b",
        )

        result = extract_tags(
            "bank_statement.pdf",
            "Chase checking account",
            llm_client=mock_client,
            use_llm=True,
        )

        assert result.used_keyword_fallback is True

    def test_llm_json_in_code_block(self) -> None:
        """Should parse JSON wrapped in markdown code block."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = True
        mock_client.generate.return_value = MagicMock(
            success=True,
            text='```json\n{"document_type": "invoice", "year": "2023", "organizations": [], "people": [], "topics": [], "suggested_tags": ["invoice"], "confidence": 0.85}\n```',
            model_used="llama3.1:8b",
        )

        result = extract_tags(
            "invoice.pdf",
            "Invoice content",
            llm_client=mock_client,
            use_llm=True,
        )

        assert result.document_type == "invoice"
        assert result.used_keyword_fallback is False


class TestDNARegistry:
    """Tests for DNARegistry class."""

    def test_init_creates_empty_registry(self) -> None:
        """Should initialize with empty registry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry_path = Path(tmpdir) / "file_dna.json"
            registry = DNARegistry(registry_path, use_llm=False)
            assert registry.get_count() == 0

    def test_init_loads_existing_registry(self) -> None:
        """Should load existing registry from disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry_path = Path(tmpdir) / "file_dna.json"

            # Create a registry file
            data = {
                "version": "1.0",
                "entries": [
                    {
                        "file_path": "/test/file1.pdf",
                        "sha256_hash": "hash1",
                        "auto_tags": ["tax"],
                    },
                    {
                        "file_path": "/test/file2.pdf",
                        "sha256_hash": "hash2",
                        "auto_tags": ["invoice"],
                    },
                ],
            }
            with open(registry_path, "w") as f:
                json.dump(data, f)

            registry = DNARegistry(registry_path, use_llm=False)
            assert registry.get_count() == 2

    def test_register_file(self) -> None:
        """Should register a file and compute its DNA."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test file
            test_file = Path(tmpdir) / "test_2024.txt"
            test_file.write_text("This is a tax document for 2024")

            registry_path = Path(tmpdir) / "registry.json"
            registry = DNARegistry(registry_path, use_llm=False)

            dna = registry.register_file(test_file, origin="inbox")

            assert dna.sha256_hash != ""
            assert len(dna.sha256_hash) == 64
            assert "tax" in dna.content_summary.lower() or "2024" in str(dna.auto_tags)
            assert dna.origin == "inbox"
            assert registry.get_count() == 1

    def test_register_file_persists(self) -> None:
        """Should persist registration to disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "document.txt"
            test_file.write_text("Test content")

            registry_path = Path(tmpdir) / "registry.json"
            registry = DNARegistry(registry_path, use_llm=False)
            registry.register_file(test_file, origin="scan")

            # Create new registry instance and check data persists
            registry2 = DNARegistry(registry_path, use_llm=False)
            assert registry2.get_count() == 1
            dna = registry2.get_by_path(test_file)
            assert dna is not None
            assert dna.origin == "scan"

    def test_get_by_path(self) -> None:
        """Should retrieve DNA by file path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "file.txt"
            test_file.write_text("Content")

            registry_path = Path(tmpdir) / "registry.json"
            registry = DNARegistry(registry_path, use_llm=False)
            original_dna = registry.register_file(test_file)

            retrieved_dna = registry.get_by_path(test_file)
            assert retrieved_dna is not None
            assert retrieved_dna.sha256_hash == original_dna.sha256_hash

    def test_get_by_path_not_found(self) -> None:
        """Should return None for unregistered path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry_path = Path(tmpdir) / "registry.json"
            registry = DNARegistry(registry_path, use_llm=False)

            dna = registry.get_by_path("/nonexistent/file.pdf")
            assert dna is None

    def test_find_by_hash(self) -> None:
        """Should find files by hash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "file.txt"
            test_file.write_text("Unique content")

            registry_path = Path(tmpdir) / "registry.json"
            registry = DNARegistry(registry_path, use_llm=False)
            dna = registry.register_file(test_file)

            results = registry.find_by_hash(dna.sha256_hash)
            assert len(results) == 1
            assert results[0].file_path == dna.file_path

    def test_find_by_hash_multiple(self) -> None:
        """Should find multiple files with same hash (duplicates)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create two files with same content
            content = "Duplicate content"
            file1 = Path(tmpdir) / "file1.txt"
            file2 = Path(tmpdir) / "file2.txt"
            file1.write_text(content)
            file2.write_text(content)

            registry_path = Path(tmpdir) / "registry.json"
            registry = DNARegistry(registry_path, use_llm=False)
            dna1 = registry.register_file(file1)
            dna2 = registry.register_file(file2)

            assert dna1.sha256_hash == dna2.sha256_hash
            results = registry.find_by_hash(dna1.sha256_hash)
            assert len(results) == 2

    def test_update_routed_to(self) -> None:
        """Should update routed_to field."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "file.txt"
            test_file.write_text("Content")

            registry_path = Path(tmpdir) / "registry.json"
            registry = DNARegistry(registry_path, use_llm=False)
            registry.register_file(test_file)

            success = registry.update_routed_to(test_file, "/Finances Bin/Taxes")
            assert success is True

            dna = registry.get_by_path(test_file)
            assert dna is not None
            assert dna.routed_to == "/Finances Bin/Taxes"

    def test_update_routed_to_not_found(self) -> None:
        """Should return False for unregistered file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry_path = Path(tmpdir) / "registry.json"
            registry = DNARegistry(registry_path, use_llm=False)

            success = registry.update_routed_to("/nonexistent.pdf", "/destination")
            assert success is False

    def test_mark_duplicate(self) -> None:
        """Should mark file as duplicate."""
        with tempfile.TemporaryDirectory() as tmpdir:
            content = "Same content"
            canonical = Path(tmpdir) / "canonical.txt"
            duplicate = Path(tmpdir) / "duplicate.txt"
            canonical.write_text(content)
            duplicate.write_text(content)

            registry_path = Path(tmpdir) / "registry.json"
            registry = DNARegistry(registry_path, use_llm=False)
            registry.register_file(canonical)
            registry.register_file(duplicate)

            success = registry.mark_duplicate(duplicate, canonical)
            assert success is True

            dna = registry.get_by_path(duplicate)
            assert dna is not None
            assert str(canonical.resolve()) in dna.duplicate_of

    def test_find_duplicates(self) -> None:
        """Should find all duplicate groups."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create unique and duplicate files
            unique = Path(tmpdir) / "unique.txt"
            dup1 = Path(tmpdir) / "dup1.txt"
            dup2 = Path(tmpdir) / "dup2.txt"
            unique.write_text("Unique content")
            dup1.write_text("Duplicate content")
            dup2.write_text("Duplicate content")

            registry_path = Path(tmpdir) / "registry.json"
            registry = DNARegistry(registry_path, use_llm=False)
            registry.register_file(unique)
            registry.register_file(dup1)
            registry.register_file(dup2)

            duplicates = registry.find_duplicates()
            # Should have one group (the duplicates)
            assert len(duplicates) == 1
            # The group should have 2 files
            for hash_val, files in duplicates.items():
                assert len(files) == 2

    def test_search_by_tag(self) -> None:
        """Should search files by tag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create files with different content
            tax_file = Path(tmpdir) / "tax_2024.txt"
            invoice_file = Path(tmpdir) / "invoice.txt"
            tax_file.write_text("IRS tax return 2024")
            invoice_file.write_text("Amazon purchase receipt")

            registry_path = Path(tmpdir) / "registry.json"
            registry = DNARegistry(registry_path, use_llm=False)
            registry.register_file(tax_file)
            registry.register_file(invoice_file)

            # Search for tax-related files
            results = registry.search_by_tag("2024")
            # Should find at least the tax file (has 2024 in name/content)
            paths = [r.file_path for r in results]
            assert any("tax_2024" in p for p in paths)

    def test_search_by_keyword(self) -> None:
        """Should search files by keyword in path, content, or tags."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "verizon_bill.txt"
            test_file.write_text("Verizon wireless bill for March 2024")

            registry_path = Path(tmpdir) / "registry.json"
            registry = DNARegistry(registry_path, use_llm=False)
            registry.register_file(test_file)

            # Search by content keyword
            results = registry.search_by_keyword("wireless")
            assert len(results) >= 1

            # Search by filename keyword
            results = registry.search_by_keyword("verizon")
            assert len(results) >= 1

    def test_remove(self) -> None:
        """Should remove file from registry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "file.txt"
            test_file.write_text("Content")

            registry_path = Path(tmpdir) / "registry.json"
            registry = DNARegistry(registry_path, use_llm=False)
            dna = registry.register_file(test_file)

            assert registry.get_count() == 1
            success = registry.remove(test_file)
            assert success is True
            assert registry.get_count() == 0
            assert registry.get_by_path(test_file) is None
            # Hash index should also be updated
            assert len(registry.find_by_hash(dna.sha256_hash)) == 0

    def test_remove_not_found(self) -> None:
        """Should return False when removing unregistered file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry_path = Path(tmpdir) / "registry.json"
            registry = DNARegistry(registry_path, use_llm=False)

            success = registry.remove("/nonexistent/file.pdf")
            assert success is False

    def test_clear(self) -> None:
        """Should clear all entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = Path(tmpdir) / "file1.txt"
            file2 = Path(tmpdir) / "file2.txt"
            file1.write_text("Content 1")
            file2.write_text("Content 2")

            registry_path = Path(tmpdir) / "registry.json"
            registry = DNARegistry(registry_path, use_llm=False)
            registry.register_file(file1)
            registry.register_file(file2)

            assert registry.get_count() == 2
            registry.clear()
            assert registry.get_count() == 0

    def test_get_all(self) -> None:
        """Should return all DNA records."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = Path(tmpdir) / "file1.txt"
            file2 = Path(tmpdir) / "file2.txt"
            file1.write_text("Content 1")
            file2.write_text("Content 2")

            registry_path = Path(tmpdir) / "registry.json"
            registry = DNARegistry(registry_path, use_llm=False)
            registry.register_file(file1)
            registry.register_file(file2)

            all_dna = registry.get_all()
            assert len(all_dna) == 2

    def test_register_updates_existing(self) -> None:
        """Should update existing record when re-registering."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "file.txt"
            test_file.write_text("Original content")

            registry_path = Path(tmpdir) / "registry.json"
            registry = DNARegistry(registry_path, use_llm=False)
            dna1 = registry.register_file(test_file, origin="inbox")
            original_hash = dna1.sha256_hash

            # Modify file and re-register
            test_file.write_text("Modified content")
            dna2 = registry.register_file(test_file, origin="scan")

            assert registry.get_count() == 1  # Still one entry
            assert dna2.sha256_hash != original_hash  # Hash changed
            assert dna2.origin == "inbox"  # Origin preserved from first registration


class TestDNARegistryWithLLM:
    """Tests for DNARegistry with mocked LLM."""

    def test_register_with_llm_tags(self) -> None:
        """Should use LLM for tag extraction when available."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "1040_2024.txt"
            test_file.write_text("IRS Form 1040 Individual Income Tax Return")

            mock_client = MagicMock()
            mock_client.is_ollama_available.return_value = True
            mock_client.generate.return_value = MagicMock(
                success=True,
                text=json.dumps({
                    "document_type": "tax_return",
                    "year": "2024",
                    "organizations": ["IRS"],
                    "people": [],
                    "topics": ["income tax"],
                    "suggested_tags": ["tax_return", "2024", "IRS", "1040"],
                    "confidence": 0.95,
                }),
                model_used="llama3.1:8b",
            )

            registry_path = Path(tmpdir) / "registry.json"
            registry = DNARegistry(
                registry_path,
                llm_client=mock_client,
                use_llm=True,
            )

            dna = registry.register_file(test_file, origin="inbox")

            assert dna.model_used == "llama3.1:8b"
            assert "tax_return" in dna.auto_tags
            assert "2024" in dna.auto_tags
            mock_client.generate.assert_called_once()

    def test_register_with_model_router(self) -> None:
        """Should use model router for model selection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "document.txt"
            test_file.write_text("Some content")

            mock_client = MagicMock()
            mock_client.is_ollama_available.return_value = True
            mock_client.generate.return_value = MagicMock(
                success=True,
                text=json.dumps({
                    "document_type": "document",
                    "year": "",
                    "organizations": [],
                    "people": [],
                    "topics": [],
                    "suggested_tags": ["document"],
                    "confidence": 0.8,
                }),
                model_used="qwen2.5-coder:14b",
            )

            mock_router = MagicMock()
            mock_router.route.return_value = MagicMock(model="qwen2.5-coder:14b")

            registry_path = Path(tmpdir) / "registry.json"
            registry = DNARegistry(
                registry_path,
                llm_client=mock_client,
                model_router=mock_router,
                use_llm=True,
            )

            dna = registry.register_file(test_file)

            mock_router.route.assert_called_once()
            assert dna.model_used == "qwen2.5-coder:14b"
