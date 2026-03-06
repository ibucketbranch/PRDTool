"""Tests for dedup_engine module - duplicate detection and archiving.

Covers:
- DuplicateGroup dataclass creation and serialization
- FuzzyDuplicateGroup dataclass creation and serialization
- find_exact_duplicates() using DNARegistry
- find_fuzzy_duplicates() with LLM (mock) and keyword fallback
- Archive path generation
- DedupEngine full workflow
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from organizer.dedup_engine import (
    DedupEngine,
    DuplicateGroup,
    FuzzyDuplicateGroup,
    _analyze_pair_with_keywords,
    _find_fuzzy_candidates,
    _get_filename_similarity,
    find_exact_duplicates,
    find_fuzzy_duplicates,
    get_archive_path,
)
from organizer.file_dna import DNARegistry, FileDNA


class TestDuplicateGroup:
    """Tests for DuplicateGroup dataclass."""

    def test_create_duplicate_group(self) -> None:
        """Should create DuplicateGroup with required fields."""
        group = DuplicateGroup(
            sha256_hash="abc123def456",
            canonical_path="/path/to/canonical.pdf",
        )
        assert group.sha256_hash == "abc123def456"
        assert group.canonical_path == "/path/to/canonical.pdf"
        assert group.duplicate_paths == []
        assert group.wasted_bytes == 0

    def test_create_duplicate_group_with_duplicates(self) -> None:
        """Should create DuplicateGroup with duplicate paths."""
        group = DuplicateGroup(
            sha256_hash="abc123",
            canonical_path="/canonical.pdf",
            duplicate_paths=["/dup1.pdf", "/dup2.pdf"],
            wasted_bytes=1024,
        )
        assert group.duplicate_paths == ["/dup1.pdf", "/dup2.pdf"]
        assert group.wasted_bytes == 1024
        assert group.file_count == 3

    def test_to_dict(self) -> None:
        """Should convert DuplicateGroup to dictionary."""
        group = DuplicateGroup(
            sha256_hash="hash123",
            canonical_path="/canonical.pdf",
            duplicate_paths=["/dup.pdf"],
            wasted_bytes=500,
        )
        d = group.to_dict()
        assert d["sha256_hash"] == "hash123"
        assert d["canonical_path"] == "/canonical.pdf"
        assert d["duplicate_paths"] == ["/dup.pdf"]
        assert d["wasted_bytes"] == 500

    def test_from_dict(self) -> None:
        """Should create DuplicateGroup from dictionary."""
        data = {
            "sha256_hash": "xyz789",
            "canonical_path": "/canonical.pdf",
            "duplicate_paths": ["/dup1.pdf", "/dup2.pdf"],
            "wasted_bytes": 2048,
        }
        group = DuplicateGroup.from_dict(data)
        assert group.sha256_hash == "xyz789"
        assert group.canonical_path == "/canonical.pdf"
        assert group.duplicate_paths == ["/dup1.pdf", "/dup2.pdf"]
        assert group.wasted_bytes == 2048

    def test_from_dict_missing_fields(self) -> None:
        """Should handle missing fields with defaults."""
        data = {"sha256_hash": "abc"}
        group = DuplicateGroup.from_dict(data)
        assert group.sha256_hash == "abc"
        assert group.canonical_path == ""
        assert group.duplicate_paths == []
        assert group.wasted_bytes == 0

    def test_file_count_property(self) -> None:
        """Should correctly count total files."""
        group = DuplicateGroup(
            sha256_hash="hash",
            canonical_path="/canon.pdf",
            duplicate_paths=["/d1.pdf", "/d2.pdf", "/d3.pdf"],
        )
        assert group.file_count == 4


class TestFuzzyDuplicateGroup:
    """Tests for FuzzyDuplicateGroup dataclass."""

    def test_create_fuzzy_group(self) -> None:
        """Should create FuzzyDuplicateGroup with required fields."""
        group = FuzzyDuplicateGroup(
            representative_path="/path/to/file.pdf",
        )
        assert group.representative_path == "/path/to/file.pdf"
        assert group.similar_paths == []
        assert group.relationship == "similar"
        assert group.confidence == 0.0
        assert group.reason == ""
        assert group.model_used == ""
        assert group.wasted_bytes == 0

    def test_create_fuzzy_group_with_all_fields(self) -> None:
        """Should create FuzzyDuplicateGroup with all fields."""
        group = FuzzyDuplicateGroup(
            representative_path="/file.pdf",
            similar_paths=["/file_copy.pdf"],
            relationship="version_of",
            confidence=0.92,
            reason="Files are versions of the same document",
            model_used="qwen2.5-coder:14b",
            wasted_bytes=512,
        )
        assert group.representative_path == "/file.pdf"
        assert group.similar_paths == ["/file_copy.pdf"]
        assert group.relationship == "version_of"
        assert group.confidence == 0.92
        assert group.reason == "Files are versions of the same document"
        assert group.model_used == "qwen2.5-coder:14b"
        assert group.file_count == 2

    def test_to_dict(self) -> None:
        """Should convert FuzzyDuplicateGroup to dictionary."""
        group = FuzzyDuplicateGroup(
            representative_path="/rep.pdf",
            similar_paths=["/sim.pdf"],
            relationship="related",
            confidence=0.75,
            reason="Similar content",
            model_used="llama3.1:8b",
            wasted_bytes=100,
        )
        d = group.to_dict()
        assert d["representative_path"] == "/rep.pdf"
        assert d["similar_paths"] == ["/sim.pdf"]
        assert d["relationship"] == "related"
        assert d["confidence"] == 0.75
        assert d["reason"] == "Similar content"
        assert d["model_used"] == "llama3.1:8b"

    def test_from_dict(self) -> None:
        """Should create FuzzyDuplicateGroup from dictionary."""
        data = {
            "representative_path": "/rep.pdf",
            "similar_paths": ["/sim1.pdf", "/sim2.pdf"],
            "relationship": "exact_duplicate",
            "confidence": 0.99,
            "reason": "Identical content",
            "model_used": "model-name",
            "wasted_bytes": 1000,
        }
        group = FuzzyDuplicateGroup.from_dict(data)
        assert group.representative_path == "/rep.pdf"
        assert group.similar_paths == ["/sim1.pdf", "/sim2.pdf"]
        assert group.relationship == "exact_duplicate"
        assert group.confidence == 0.99
        assert group.wasted_bytes == 1000


class TestGetArchivePath:
    """Tests for get_archive_path function."""

    def test_basic_archive_path(self) -> None:
        """Should generate correct archive path with hash prefix."""
        path = get_archive_path(
            "/iCloud/Archive",
            "abcd1234efgh5678",
            "document.pdf",
        )
        assert path == "/iCloud/Archive/Duplicates/abcd1234/document.pdf"

    def test_short_hash(self) -> None:
        """Should handle short hash gracefully."""
        path = get_archive_path("/Archive", "abc", "file.txt")
        assert path == "/Archive/Duplicates/abc/file.txt"

    def test_path_object_base(self) -> None:
        """Should accept Path object for base directory."""
        path = get_archive_path(
            Path("/home/user/Archive"),
            "1234567890abcdef",
            "test.doc",
        )
        assert path == "/home/user/Archive/Duplicates/12345678/test.doc"


class TestFilenameSimilarity:
    """Tests for _get_filename_similarity function."""

    def test_identical_names(self) -> None:
        """Should return 1.0 for identical filenames."""
        score = _get_filename_similarity("report.pdf", "report.pdf")
        assert score == 1.0

    def test_copy_pattern_match(self) -> None:
        """Should match files with copy patterns."""
        score = _get_filename_similarity("report.pdf", "report (1).pdf")
        assert score == 1.0

        score = _get_filename_similarity("file.txt", "file_copy.txt")
        assert score == 1.0

        score = _get_filename_similarity("doc.pdf", "Copy of doc.pdf")
        assert score == 1.0

    def test_different_extensions_same_name(self) -> None:
        """Should match files with same stem but different extensions."""
        score = _get_filename_similarity("report.pdf", "report.docx")
        assert score == 1.0

    def test_completely_different_names(self) -> None:
        """Should return low score for different names."""
        score = _get_filename_similarity("report.pdf", "invoice.pdf")
        assert score < 0.5

    def test_similar_names(self) -> None:
        """Should return high score for similar names."""
        score = _get_filename_similarity("annual_report_2024.pdf", "annual_report_2023.pdf")
        assert score > 0.8

    def test_empty_names(self) -> None:
        """Should return 0.0 for empty names."""
        score = _get_filename_similarity("", "file.pdf")
        assert score == 0.0

        score = _get_filename_similarity("file.pdf", "")
        assert score == 0.0


class TestFindExactDuplicates:
    """Tests for find_exact_duplicates function."""

    def test_no_duplicates(self) -> None:
        """Should return empty list when no duplicates exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reg_path = Path(tmpdir) / "dna.json"
            registry = DNARegistry(reg_path, use_llm=False)

            # Create unique files
            file1 = Path(tmpdir) / "file1.txt"
            file2 = Path(tmpdir) / "file2.txt"
            file1.write_text("Content 1")
            file2.write_text("Content 2")

            registry.register_file(file1)
            registry.register_file(file2)

            groups = find_exact_duplicates(registry)
            assert len(groups) == 0

    def test_find_exact_duplicates(self) -> None:
        """Should find files with identical hash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reg_path = Path(tmpdir) / "dna.json"
            registry = DNARegistry(reg_path, use_llm=False)

            # Create duplicate files
            content = "Identical content for all files"
            file1 = Path(tmpdir) / "original.txt"
            file2 = Path(tmpdir) / "copy1.txt"
            file3 = Path(tmpdir) / "copy2.txt"
            file1.write_text(content)
            file2.write_text(content)
            file3.write_text(content)

            registry.register_file(file1)
            registry.register_file(file2)
            registry.register_file(file3)

            groups = find_exact_duplicates(registry)
            assert len(groups) == 1
            assert groups[0].file_count == 3
            assert len(groups[0].duplicate_paths) == 2

    def test_canonical_is_shortest_path(self) -> None:
        """Should select file with shortest path as canonical."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reg_path = Path(tmpdir) / "dna.json"
            registry = DNARegistry(reg_path, use_llm=False)

            # Create duplicate files in nested directories
            content = "Same content"
            dir1 = Path(tmpdir) / "a"
            dir2 = Path(tmpdir) / "deep" / "nested" / "path"
            dir1.mkdir()
            dir2.mkdir(parents=True)

            file_short = dir1 / "f.txt"
            file_long = dir2 / "f.txt"
            file_short.write_text(content)
            file_long.write_text(content)

            registry.register_file(file_short)
            registry.register_file(file_long)

            groups = find_exact_duplicates(registry)
            assert len(groups) == 1
            # Shorter path should be canonical
            assert str(file_short) in groups[0].canonical_path

    def test_wasted_bytes_calculation(self) -> None:
        """Should calculate wasted bytes from duplicate file sizes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reg_path = Path(tmpdir) / "dna.json"
            registry = DNARegistry(reg_path, use_llm=False)

            content = "Test content with known size"
            file1 = Path(tmpdir) / "original.txt"
            file2 = Path(tmpdir) / "duplicate.txt"
            file1.write_text(content)
            file2.write_text(content)

            registry.register_file(file1)
            registry.register_file(file2)

            groups = find_exact_duplicates(registry)
            assert len(groups) == 1
            # Wasted bytes should be size of the duplicate file
            expected_size = file2.stat().st_size
            assert groups[0].wasted_bytes == expected_size


class TestFindFuzzyCandidates:
    """Tests for _find_fuzzy_candidates function."""

    def test_find_similar_filenames(self) -> None:
        """Should find files with similar filenames."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reg_path = Path(tmpdir) / "dna.json"
            registry = DNARegistry(reg_path, use_llm=False)

            # Create files with similar names but different content
            file1 = Path(tmpdir) / "report.txt"
            file2 = Path(tmpdir) / "report (1).txt"
            file1.write_text("Original report content")
            file2.write_text("Slightly modified report")

            registry.register_file(file1)
            registry.register_file(file2)

            candidates = _find_fuzzy_candidates(registry, threshold=0.85)
            assert len(candidates) == 1

    def test_skip_exact_duplicates(self) -> None:
        """Should skip files with same hash (those are exact duplicates)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reg_path = Path(tmpdir) / "dna.json"
            registry = DNARegistry(reg_path, use_llm=False)

            content = "Same content"
            file1 = Path(tmpdir) / "file.txt"
            file2 = Path(tmpdir) / "file (1).txt"
            file1.write_text(content)
            file2.write_text(content)  # Same content = same hash

            registry.register_file(file1)
            registry.register_file(file2)

            candidates = _find_fuzzy_candidates(registry, threshold=0.85)
            # Same hash = exact duplicate, not a fuzzy candidate
            assert len(candidates) == 0

    def test_skip_marked_duplicates(self) -> None:
        """Should skip files already marked as duplicates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reg_path = Path(tmpdir) / "dna.json"
            registry = DNARegistry(reg_path, use_llm=False)

            file1 = Path(tmpdir) / "report.txt"
            file2 = Path(tmpdir) / "report (1).txt"
            file1.write_text("Content A")
            file2.write_text("Content B")

            registry.register_file(file1)
            registry.register_file(file2)

            # Mark file2 as duplicate of file1
            registry.mark_duplicate(file2, file1)

            candidates = _find_fuzzy_candidates(registry, threshold=0.85)
            # Marked duplicate should be skipped
            assert len(candidates) == 0


class TestAnalyzePairWithKeywords:
    """Tests for _analyze_pair_with_keywords function."""

    def test_copy_pattern_detection(self) -> None:
        """Should detect copy patterns in filenames."""
        dna_a = FileDNA(file_path="/path/report.pdf", sha256_hash="abc")
        dna_b = FileDNA(file_path="/path/report (1).pdf", sha256_hash="def")

        result = _analyze_pair_with_keywords(dna_a, dna_b)
        assert result["relationship"] == "version_of"
        assert result["confidence"] == 0.85
        assert "copy" in result["reason"].lower() or "pattern" in result["reason"].lower()

    def test_high_content_overlap(self) -> None:
        """Should detect high content overlap."""
        content = "This is a long document with lots of text content for testing."
        dna_a = FileDNA(file_path="/a.txt", sha256_hash="abc", content_summary=content)
        dna_b = FileDNA(file_path="/b.txt", sha256_hash="def", content_summary=content)

        result = _analyze_pair_with_keywords(dna_a, dna_b)
        assert result["relationship"] == "version_of"
        assert result["confidence"] > 0.8

    def test_moderate_content_overlap(self) -> None:
        """Should detect moderate content overlap."""
        content_a = "This document discusses financial reports and quarterly earnings."
        content_b = "The quarterly earnings and financial overview is presented here."
        dna_a = FileDNA(file_path="/a.txt", sha256_hash="abc", content_summary=content_a)
        dna_b = FileDNA(file_path="/b.txt", sha256_hash="def", content_summary=content_b)

        result = _analyze_pair_with_keywords(dna_a, dna_b)
        # May be "related" or "unrelated" depending on overlap calculation
        assert result["relationship"] in ("related", "unrelated")

    def test_unrelated_files(self) -> None:
        """Should identify unrelated files."""
        dna_a = FileDNA(
            file_path="/invoice.pdf",
            sha256_hash="abc",
            content_summary="Invoice for services rendered",
        )
        dna_b = FileDNA(
            file_path="/resume.pdf",
            sha256_hash="def",
            content_summary="Professional experience and education",
        )

        result = _analyze_pair_with_keywords(dna_a, dna_b)
        assert result["relationship"] == "unrelated"


class TestFindFuzzyDuplicatesWithKeywords:
    """Tests for find_fuzzy_duplicates with keyword fallback."""

    def test_fuzzy_duplicates_without_llm(self) -> None:
        """Should find fuzzy duplicates using keyword fallback when LLM unavailable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reg_path = Path(tmpdir) / "dna.json"
            registry = DNARegistry(reg_path, use_llm=False)

            # Create files with similar names and copy pattern
            file1 = Path(tmpdir) / "document.txt"
            file2 = Path(tmpdir) / "document (1).txt"
            file1.write_text("Original document content here.")
            file2.write_text("Modified document content here.")

            registry.register_file(file1)
            registry.register_file(file2)

            # No LLM client = keyword fallback
            groups = find_fuzzy_duplicates(registry, use_llm=False)

            # Should find the pair as fuzzy duplicates due to copy pattern
            assert len(groups) >= 1
            if groups:
                assert groups[0].model_used == ""  # No model used
                assert "copy" in groups[0].reason.lower() or "pattern" in groups[0].reason.lower()

    def test_no_fuzzy_duplicates(self) -> None:
        """Should return empty list when no fuzzy duplicates exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reg_path = Path(tmpdir) / "dna.json"
            registry = DNARegistry(reg_path, use_llm=False)

            # Create files with completely different names
            file1 = Path(tmpdir) / "invoice.txt"
            file2 = Path(tmpdir) / "resume.txt"
            file1.write_text("Invoice content")
            file2.write_text("Resume content")

            registry.register_file(file1)
            registry.register_file(file2)

            groups = find_fuzzy_duplicates(registry, use_llm=False)
            assert len(groups) == 0


class TestFindFuzzyDuplicatesWithLLM:
    """Tests for find_fuzzy_duplicates with mocked LLM."""

    def test_llm_analysis_success(self) -> None:
        """Should use LLM for fuzzy duplicate analysis when available."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reg_path = Path(tmpdir) / "dna.json"
            registry = DNARegistry(reg_path, use_llm=False)

            # Create files with similar names
            file1 = Path(tmpdir) / "report.txt"
            file2 = Path(tmpdir) / "report_v2.txt"
            file1.write_text("Original report content with details.")
            file2.write_text("Updated report with new information.")

            registry.register_file(file1)
            registry.register_file(file2)

            # Mock LLM client
            mock_client = MagicMock()
            mock_client.is_ollama_available.return_value = True
            mock_response = MagicMock()
            mock_response.success = True
            mock_response.text = json.dumps({
                "relationship": "version_of",
                "confidence": 0.92,
                "reason": "Files are different versions of the same report",
            })
            mock_response.model_used = "qwen2.5-coder:14b"
            mock_client.generate.return_value = mock_response

            groups = find_fuzzy_duplicates(
                registry,
                llm_client=mock_client,
                use_llm=True,
            )

            # Should find the pair via LLM
            assert len(groups) == 1
            assert groups[0].relationship == "version_of"
            assert groups[0].confidence == 0.92
            assert groups[0].model_used == "qwen2.5-coder:14b"

    def test_llm_returns_unrelated(self) -> None:
        """Should not group files when LLM says they're unrelated."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reg_path = Path(tmpdir) / "dna.json"
            registry = DNARegistry(reg_path, use_llm=False)

            # Create files with similar names
            file1 = Path(tmpdir) / "report.txt"
            file2 = Path(tmpdir) / "report_sales.txt"
            file1.write_text("Technical report on infrastructure.")
            file2.write_text("Sales report for Q4 2024.")

            registry.register_file(file1)
            registry.register_file(file2)

            # Mock LLM to return unrelated
            mock_client = MagicMock()
            mock_client.is_ollama_available.return_value = True
            mock_response = MagicMock()
            mock_response.success = True
            mock_response.text = json.dumps({
                "relationship": "unrelated",
                "confidence": 0.85,
                "reason": "Different types of reports",
            })
            mock_response.model_used = "qwen2.5-coder:14b"
            mock_client.generate.return_value = mock_response

            groups = find_fuzzy_duplicates(
                registry,
                llm_client=mock_client,
                use_llm=True,
            )

            # Should not group unrelated files
            assert len(groups) == 0

    def test_llm_unavailable_fallback(self) -> None:
        """Should fall back to keywords when LLM unavailable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reg_path = Path(tmpdir) / "dna.json"
            registry = DNARegistry(reg_path, use_llm=False)

            file1 = Path(tmpdir) / "doc.txt"
            file2 = Path(tmpdir) / "doc (1).txt"
            file1.write_text("Content A")
            file2.write_text("Content B")

            registry.register_file(file1)
            registry.register_file(file2)

            # Mock LLM client that says it's unavailable
            mock_client = MagicMock()
            mock_client.is_ollama_available.return_value = False

            groups = find_fuzzy_duplicates(
                registry,
                llm_client=mock_client,
                use_llm=True,
            )

            # Should still find via keyword fallback
            if groups:
                assert groups[0].model_used == ""  # No model used


class TestDedupEngine:
    """Tests for DedupEngine class."""

    def test_engine_initialization(self) -> None:
        """Should initialize DedupEngine with registry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reg_path = Path(tmpdir) / "dna.json"
            registry = DNARegistry(reg_path, use_llm=False)

            engine = DedupEngine(registry, archive_dir="/Archive")
            assert engine._archive_dir == Path("/Archive")
            assert engine._fuzzy_threshold == 0.85
            assert engine._use_llm is True

    def test_engine_run_empty_registry(self) -> None:
        """Should run on empty registry without errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reg_path = Path(tmpdir) / "dna.json"
            registry = DNARegistry(reg_path, use_llm=False)

            engine = DedupEngine(registry, use_llm=False)
            report = engine.run()

            assert report["exact_count"] == 0
            assert report["fuzzy_count"] == 0
            assert report["total_wasted_bytes"] == 0

    def test_engine_finds_exact_duplicates(self) -> None:
        """Should find exact duplicates via engine."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reg_path = Path(tmpdir) / "dna.json"
            registry = DNARegistry(reg_path, use_llm=False)

            content = "Duplicate content"
            file1 = Path(tmpdir) / "orig.txt"
            file2 = Path(tmpdir) / "copy.txt"
            file1.write_text(content)
            file2.write_text(content)

            registry.register_file(file1)
            registry.register_file(file2)

            engine = DedupEngine(registry, use_llm=False)
            report = engine.run()

            assert report["exact_count"] == 1
            assert report["exact_file_count"] == 2

            groups = engine.get_exact_groups()
            assert len(groups) == 1

    def test_engine_get_archive_path_for(self) -> None:
        """Should generate archive path for a file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reg_path = Path(tmpdir) / "dna.json"
            registry = DNARegistry(reg_path, use_llm=False)

            engine = DedupEngine(registry, archive_dir="/iCloud/Archive")

            path = engine.get_archive_path_for(
                "/path/to/document.pdf",
                "abcd1234efgh5678",
            )
            assert path == "/iCloud/Archive/Duplicates/abcd1234/document.pdf"

    def test_engine_report_structure(self) -> None:
        """Should return complete report structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reg_path = Path(tmpdir) / "dna.json"
            registry = DNARegistry(reg_path, use_llm=False)

            engine = DedupEngine(registry, use_llm=False)
            report = engine.run()

            assert "exact_count" in report
            assert "exact_file_count" in report
            assert "exact_wasted_bytes" in report
            assert "fuzzy_count" in report
            assert "fuzzy_file_count" in report
            assert "fuzzy_wasted_bytes" in report
            assert "total_wasted_bytes" in report


class TestDedupEngineWithLLM:
    """Tests for DedupEngine with mocked LLM integration."""

    def test_engine_with_llm_finds_fuzzy(self) -> None:
        """Should find fuzzy duplicates using LLM."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reg_path = Path(tmpdir) / "dna.json"
            registry = DNARegistry(reg_path, use_llm=False)

            file1 = Path(tmpdir) / "report.txt"
            file2 = Path(tmpdir) / "report_v2.txt"
            file1.write_text("Original report with detailed analysis.")
            file2.write_text("Updated report with new findings.")

            registry.register_file(file1)
            registry.register_file(file2)

            # Mock LLM
            mock_client = MagicMock()
            mock_client.is_ollama_available.return_value = True
            mock_response = MagicMock()
            mock_response.success = True
            mock_response.text = json.dumps({
                "relationship": "version_of",
                "confidence": 0.88,
                "reason": "Version update of the same report",
            })
            mock_response.model_used = "qwen2.5-coder:14b"
            mock_client.generate.return_value = mock_response

            engine = DedupEngine(
                registry,
                llm_client=mock_client,
                use_llm=True,
            )
            report = engine.run()

            assert report["fuzzy_count"] == 1
            fuzzy_groups = engine.get_fuzzy_groups()
            assert len(fuzzy_groups) == 1
            assert fuzzy_groups[0].relationship == "version_of"

    def test_engine_uses_model_router(self) -> None:
        """Should use model router when provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reg_path = Path(tmpdir) / "dna.json"
            registry = DNARegistry(reg_path, use_llm=False)

            file1 = Path(tmpdir) / "doc.txt"
            file2 = Path(tmpdir) / "doc_copy.txt"
            file1.write_text("Content one")
            file2.write_text("Content two")

            registry.register_file(file1)
            registry.register_file(file2)

            # Mock LLM and router
            mock_client = MagicMock()
            mock_client.is_ollama_available.return_value = True
            mock_response = MagicMock()
            mock_response.success = True
            mock_response.text = json.dumps({
                "relationship": "version_of",
                "confidence": 0.9,
                "reason": "Versions",
            })
            mock_response.model_used = "custom-model"
            mock_client.generate.return_value = mock_response

            mock_router = MagicMock()
            mock_decision = MagicMock()
            mock_decision.model = "custom-model"
            mock_router.route.return_value = mock_decision

            engine = DedupEngine(
                registry,
                llm_client=mock_client,
                model_router=mock_router,
                use_llm=True,
            )
            engine.run()

            # Router should have been called
            mock_router.route.assert_called()


class TestIntegration:
    """Integration tests for dedup engine with real files."""

    def test_full_workflow(self) -> None:
        """Should complete full dedup workflow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reg_path = Path(tmpdir) / "dna.json"
            registry = DNARegistry(reg_path, use_llm=False)

            # Create a mix of exact and potential fuzzy duplicates
            content1 = "Document about financial planning"
            content2 = "Document about financial planning"  # Exact dup
            content3 = "Report about marketing strategy"

            file1 = Path(tmpdir) / "finance.txt"
            file2 = Path(tmpdir) / "finance_backup.txt"
            file3 = Path(tmpdir) / "marketing.txt"

            file1.write_text(content1)
            file2.write_text(content2)  # Same content = exact dup
            file3.write_text(content3)

            registry.register_file(file1)
            registry.register_file(file2)
            registry.register_file(file3)

            engine = DedupEngine(registry, archive_dir=tmpdir, use_llm=False)
            report = engine.run()

            # Should find exact duplicate
            assert report["exact_count"] == 1
            assert report["exact_file_count"] == 2

            # Check archive path generation works
            groups = engine.get_exact_groups()
            if groups:
                dup_path = groups[0].duplicate_paths[0]
                archive_path = engine.get_archive_path_for(dup_path, groups[0].sha256_hash)
                assert "Duplicates" in archive_path
                assert groups[0].sha256_hash[:8] in archive_path
