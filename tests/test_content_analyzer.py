"""Tests for the content_analyzer module."""

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from organizer.content_analyzer import (
    ConsolidationDecision,
    DefaultDocumentProcessor,
    DocumentInfo,
    FileInfo,
    FolderAnalysis,
    FolderScanResult,
    SUPPORTED_EXTENSIONS,
    _check_date_range_overlap,
    _check_path_compatibility,
    _compute_year_clusters,
    _extract_context_bin,
    _extract_year_from_date,
    _parse_array_field,
    _parse_json_field,
    analyze_folder_content,
    analyze_folder_content_from_path,
    analyze_folder_with_processing,
    analyze_folder_with_processing_from_path,
    check_files_in_database,
    create_document_processor,
    get_folder_metadata,
    is_supported_file,
    process_unanalyzed_files,
    scan_folder_for_files,
    scan_folder_with_database,
    scan_folder_with_database_from_path,
    should_consolidate_folders,
    should_consolidate_folders_from_path,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database with test schema."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY,
            filename TEXT,
            current_path TEXT,
            ai_category TEXT,
            ai_subcategories TEXT,
            ai_summary TEXT,
            entities TEXT,
            key_dates TEXT,
            folder_hierarchy TEXT,
            pdf_created_date TEXT,
            pdf_modified_date TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE document_locations (
            id INTEGER PRIMARY KEY,
            document_id INTEGER,
            path TEXT,
            location_type TEXT,
            created_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()

    yield db_path

    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def db_with_documents(temp_db):
    """Create a database with test documents."""
    conn = sqlite3.connect(temp_db)

    # Add documents in folder1 (Resume folder)
    conn.execute(
        """
        INSERT INTO documents (id, filename, current_path, ai_category, ai_subcategories,
            ai_summary, entities, key_dates, folder_hierarchy, pdf_created_date, pdf_modified_date)
        VALUES (1, 'resume_2024.pdf', '/test/Resume/resume_2024.pdf', 'Employment/Resumes',
            '["Employment"]', 'My professional resume', '{"people": ["John Doe"]}',
            '["2024-01-15"]', '["Personal", "Documents"]', '2024-01-15', '2024-02-01')
        """
    )
    conn.execute(
        """
        INSERT INTO documents (id, filename, current_path, ai_category, ai_subcategories,
            ai_summary, entities, key_dates, folder_hierarchy, pdf_created_date, pdf_modified_date)
        VALUES (2, 'cover_letter.pdf', '/test/Resume/cover_letter.pdf', 'Employment/Resumes',
            '["Employment"]', 'Cover letter for job', '{"people": ["John Doe"], "organizations": ["ACME Corp"]}',
            '["2024-03-01"]', '["Personal", "Documents"]', '2024-03-01', '2024-03-05')
        """
    )

    # Add document_locations
    conn.execute(
        """
        INSERT INTO document_locations (document_id, path, location_type, created_at)
        VALUES (1, '/original/Desktop/resume_2024.pdf', 'original', '2024-01-15')
        """
    )
    conn.execute(
        """
        INSERT INTO document_locations (document_id, path, location_type, created_at)
        VALUES (2, '/original/Desktop/cover_letter.pdf', 'original', '2024-03-01')
        """
    )

    # Add documents in folder2 (Resumes folder - similar content)
    conn.execute(
        """
        INSERT INTO documents (id, filename, current_path, ai_category, ai_subcategories,
            ai_summary, entities, key_dates, folder_hierarchy, pdf_created_date, pdf_modified_date)
        VALUES (3, 'cv.pdf', '/test/Resumes/cv.pdf', 'Employment/Resumes',
            '["Employment"]', 'Curriculum Vitae', '{"people": ["John Doe"]}',
            '["2024-06-01"]', '["Personal", "Documents"]', '2024-06-01', '2024-06-15')
        """
    )
    conn.execute(
        """
        INSERT INTO document_locations (document_id, path, location_type, created_at)
        VALUES (3, '/original/Desktop/cv.pdf', 'original', '2024-06-01')
        """
    )

    # Add documents in folder3 (Tax folder - different content)
    conn.execute(
        """
        INSERT INTO documents (id, filename, current_path, ai_category, ai_subcategories,
            ai_summary, entities, key_dates, folder_hierarchy, pdf_created_date, pdf_modified_date)
        VALUES (4, 'tax_2024.pdf', '/test/Taxes/tax_2024.pdf', 'Finances/Taxes',
            '["Finances"]', 'Tax return 2024', '{"organizations": ["IRS"]}',
            '["2024-04-15"]', '["Personal", "Documents"]', '2024-04-01', '2024-04-15')
        """
    )

    # Add documents in folder4 (Old tax folder - different timeframe)
    conn.execute(
        """
        INSERT INTO documents (id, filename, current_path, ai_category, ai_subcategories,
            ai_summary, entities, key_dates, folder_hierarchy, pdf_created_date, pdf_modified_date)
        VALUES (5, 'tax_2002.pdf', '/test/Tax_2002/tax_2002.pdf', 'Finances/Taxes',
            '["Finances"]', 'Tax return 2002', '{"organizations": ["IRS"]}',
            '["2002-04-15"]', '["Personal", "Documents"]', '2002-04-01', '2002-04-15')
        """
    )

    conn.commit()
    conn.close()

    return temp_db


# =============================================================================
# Test DocumentInfo
# =============================================================================


class TestDocumentInfo:
    """Tests for DocumentInfo dataclass."""

    def test_document_info_creation(self):
        """Test creating a DocumentInfo instance."""
        doc = DocumentInfo(
            id=1,
            filename="test.pdf",
            current_path="/path/to/test.pdf",
        )
        assert doc.id == 1
        assert doc.filename == "test.pdf"
        assert doc.current_path == "/path/to/test.pdf"
        assert doc.ai_category == ""
        assert doc.ai_subcategories == []
        assert doc.entities == {}

    def test_document_info_with_all_fields(self):
        """Test creating a DocumentInfo with all fields."""
        doc = DocumentInfo(
            id=1,
            filename="test.pdf",
            current_path="/path/to/test.pdf",
            ai_category="Employment/Resumes",
            ai_subcategories=["Employment"],
            ai_summary="Test summary",
            entities={"people": ["John"]},
            key_dates=["2024-01-01"],
            original_path="/original/path",
            folder_hierarchy=["Personal", "Documents"],
            pdf_created_date="2024-01-01",
            pdf_modified_date="2024-01-02",
        )
        assert doc.ai_category == "Employment/Resumes"
        assert doc.entities == {"people": ["John"]}

    def test_document_info_to_dict(self):
        """Test DocumentInfo.to_dict() serialization."""
        doc = DocumentInfo(
            id=1,
            filename="test.pdf",
            current_path="/path/to/test.pdf",
            ai_category="Test",
        )
        result = doc.to_dict()
        assert result["id"] == 1
        assert result["filename"] == "test.pdf"
        assert result["ai_category"] == "Test"


# =============================================================================
# Test FolderAnalysis
# =============================================================================


class TestFolderAnalysis:
    """Tests for FolderAnalysis dataclass."""

    def test_folder_analysis_creation(self):
        """Test creating a FolderAnalysis instance."""
        analysis = FolderAnalysis(folder_path="/test/folder")
        assert analysis.folder_path == "/test/folder"
        assert analysis.document_count == 0
        assert analysis.documents == []
        assert analysis.ai_categories == set()
        assert analysis.analyzed_at != ""

    def test_folder_analysis_with_data(self):
        """Test creating a FolderAnalysis with data."""
        analysis = FolderAnalysis(
            folder_path="/test/folder",
            document_count=5,
            ai_categories={"Employment/Resumes"},
            date_range=("2024", "2025"),
            year_clusters=["2024-2025"],
        )
        assert analysis.document_count == 5
        assert "Employment/Resumes" in analysis.ai_categories
        assert analysis.date_range == ("2024", "2025")

    def test_folder_analysis_to_dict(self):
        """Test FolderAnalysis.to_dict() serialization."""
        analysis = FolderAnalysis(
            folder_path="/test/folder",
            document_count=2,
            ai_categories={"Test"},
            entities={"people": {"John", "Jane"}},
        )
        result = analysis.to_dict()
        assert result["folder_path"] == "/test/folder"
        assert result["document_count"] == 2
        assert "Test" in result["ai_categories"]
        assert set(result["entities"]["people"]) == {"John", "Jane"}


# =============================================================================
# Test ConsolidationDecision
# =============================================================================


class TestConsolidationDecision:
    """Tests for ConsolidationDecision dataclass."""

    def test_consolidation_decision_creation(self):
        """Test creating a ConsolidationDecision instance."""
        decision = ConsolidationDecision(
            folder1_path="/folder1",
            folder2_path="/folder2",
            should_consolidate=True,
            confidence=0.8,
        )
        assert decision.should_consolidate is True
        assert decision.confidence == 0.8
        assert decision.reasoning == []

    def test_consolidation_decision_to_dict(self):
        """Test ConsolidationDecision.to_dict() serialization."""
        decision = ConsolidationDecision(
            folder1_path="/folder1",
            folder2_path="/folder2",
            should_consolidate=True,
            confidence=0.8,
            reasoning=["Test reason"],
            matching_categories=True,
        )
        result = decision.to_dict()
        assert result["should_consolidate"] is True
        assert result["confidence"] == 0.8
        assert result["matching_categories"] is True


# =============================================================================
# Test Helper Functions
# =============================================================================


class TestParseJsonField:
    """Tests for _parse_json_field helper."""

    def test_parse_none(self):
        """Test parsing None returns empty dict."""
        assert _parse_json_field(None) == {}

    def test_parse_valid_json(self):
        """Test parsing valid JSON string."""
        assert _parse_json_field('{"key": "value"}') == {"key": "value"}

    def test_parse_dict_passthrough(self):
        """Test that dict is passed through."""
        data = {"key": "value"}
        assert _parse_json_field(data) == data

    def test_parse_invalid_json(self):
        """Test parsing invalid JSON returns empty dict."""
        assert _parse_json_field("not json") == {}


class TestParseArrayField:
    """Tests for _parse_array_field helper."""

    def test_parse_none(self):
        """Test parsing None returns empty list."""
        assert _parse_array_field(None) == []

    def test_parse_valid_array(self):
        """Test parsing valid JSON array."""
        assert _parse_array_field('["a", "b"]') == ["a", "b"]

    def test_parse_list_passthrough(self):
        """Test that list is passed through."""
        data = ["a", "b"]
        assert _parse_array_field(data) == data

    def test_parse_invalid_json(self):
        """Test parsing invalid JSON returns empty list."""
        assert _parse_array_field("not json") == []


class TestExtractYearFromDate:
    """Tests for _extract_year_from_date helper."""

    def test_iso_format(self):
        """Test extracting year from ISO format."""
        assert _extract_year_from_date("2024-01-15") == 2024

    def test_slash_format(self):
        """Test extracting year from slash format."""
        assert _extract_year_from_date("2024/01/15") == 2024

    def test_us_format(self):
        """Test extracting year from US date format."""
        assert _extract_year_from_date("01/15/2024") == 2024

    def test_year_only(self):
        """Test extracting year from year-only string."""
        assert _extract_year_from_date("2024") == 2024

    def test_iso_with_time(self):
        """Test extracting year from ISO format with time."""
        assert _extract_year_from_date("2024-01-15T10:30:00") == 2024

    def test_embedded_year(self):
        """Test extracting year embedded in text."""
        assert _extract_year_from_date("Tax year 2024") == 2024

    def test_empty_string(self):
        """Test empty string returns None."""
        assert _extract_year_from_date("") is None

    def test_no_year(self):
        """Test string without year returns None."""
        assert _extract_year_from_date("no year here") is None


class TestComputeYearClusters:
    """Tests for _compute_year_clusters helper."""

    def test_single_year(self):
        """Test single year produces single cluster."""
        assert _compute_year_clusters(["2024-01-01"]) == ["2024"]

    def test_consecutive_years(self):
        """Test consecutive years produce range cluster."""
        dates = ["2024-01-01", "2025-06-15"]
        assert _compute_year_clusters(dates) == ["2024-2025"]

    def test_separate_clusters(self):
        """Test non-consecutive years produce separate clusters."""
        dates = ["2002-01-01", "2003-06-15", "2024-01-01", "2025-06-15"]
        clusters = _compute_year_clusters(dates)
        assert "2002-2003" in clusters
        assert "2024-2025" in clusters

    def test_empty_list(self):
        """Test empty list returns empty clusters."""
        assert _compute_year_clusters([]) == []

    def test_invalid_dates(self):
        """Test invalid dates are ignored."""
        dates = ["not a date", "also not"]
        assert _compute_year_clusters(dates) == []


class TestExtractContextBin:
    """Tests for _extract_context_bin helper."""

    def test_desktop_context(self):
        """Test Desktop path extraction."""
        assert _extract_context_bin("/Users/john/Desktop/file.pdf") == "Desktop"

    def test_documents_context(self):
        """Test Documents path extraction."""
        assert _extract_context_bin("/Users/john/Documents/file.pdf") == "Documents"

    def test_icloud_context(self):
        """Test iCloud path extraction."""
        assert _extract_context_bin("/Users/john/iCloud/file.pdf") == "iCloud"

    def test_dropbox_context(self):
        """Test Dropbox path extraction."""
        assert _extract_context_bin("/Users/john/Dropbox/file.pdf") == "Dropbox"

    def test_unknown_context(self):
        """Test unknown path returns Unknown."""
        assert _extract_context_bin("/some/random/path") == "Unknown"


class TestCheckPathCompatibility:
    """Tests for _check_path_compatibility helper."""

    def test_empty_paths(self):
        """Test empty path sets are compatible."""
        compatible, reason = _check_path_compatibility(set(), set())
        assert compatible is True

    def test_same_context(self):
        """Test same context is compatible."""
        paths1 = {"/Users/john/Desktop/file1.pdf"}
        paths2 = {"/Users/john/Desktop/file2.pdf"}
        compatible, reason = _check_path_compatibility(paths1, paths2)
        assert compatible is True

    def test_different_context_compatible(self):
        """Test different contexts are still compatible by default."""
        paths1 = {"/Users/john/Desktop/file1.pdf"}
        paths2 = {"/Users/john/Documents/file2.pdf"}
        compatible, reason = _check_path_compatibility(paths1, paths2)
        assert compatible is True

    def test_microsoft_vs_macos_desktop(self):
        """Test Microsoft Desktop vs macOS Desktop is incompatible."""
        paths1 = {"/microsoft/Desktop/file1.pdf"}
        paths2 = {"/macos/Desktop/file2.pdf"}
        compatible, reason = _check_path_compatibility(paths1, paths2)
        assert compatible is False
        assert "macOS" in reason or "Microsoft" in reason


class TestCheckDateRangeOverlap:
    """Tests for _check_date_range_overlap helper."""

    def test_none_ranges(self):
        """Test None ranges are compatible."""
        compatible, reason = _check_date_range_overlap(None, None)
        assert compatible is True

    def test_overlapping_ranges(self):
        """Test overlapping ranges are compatible."""
        compatible, reason = _check_date_range_overlap(
            ("2024", "2025"), ("2024", "2026")
        )
        assert compatible is True

    def test_adjacent_ranges(self):
        """Test adjacent ranges are compatible."""
        compatible, reason = _check_date_range_overlap(
            ("2022", "2023"), ("2024", "2025")
        )
        assert compatible is True

    def test_separate_ranges(self):
        """Test separate ranges with gap are incompatible."""
        compatible, reason = _check_date_range_overlap(
            ("2002", "2003"), ("2024", "2025")
        )
        assert compatible is False
        assert "Different timeframes" in reason


# =============================================================================
# Test Database Functions
# =============================================================================


class TestGetFolderMetadata:
    """Tests for get_folder_metadata function."""

    def test_get_metadata_empty_folder(self, temp_db):
        """Test getting metadata for folder with no documents."""
        conn = sqlite3.connect(temp_db)
        docs = get_folder_metadata(conn, "/nonexistent/folder")
        conn.close()
        assert docs == []

    def test_get_metadata_with_documents(self, db_with_documents):
        """Test getting metadata for folder with documents."""
        conn = sqlite3.connect(db_with_documents)
        docs = get_folder_metadata(conn, "/test/Resume")
        conn.close()

        assert len(docs) == 2
        assert docs[0].ai_category == "Employment/Resumes"
        assert docs[0].original_path == "/original/Desktop/resume_2024.pdf"

    def test_get_metadata_trailing_slash(self, db_with_documents):
        """Test folder path with trailing slash."""
        conn = sqlite3.connect(db_with_documents)
        docs = get_folder_metadata(conn, "/test/Resume/")
        conn.close()

        assert len(docs) == 2


class TestAnalyzeFolderContent:
    """Tests for analyze_folder_content function."""

    def test_analyze_empty_folder(self, temp_db):
        """Test analyzing folder with no documents."""
        conn = sqlite3.connect(temp_db)
        analysis = analyze_folder_content(conn, "/empty/folder")
        conn.close()

        assert analysis.document_count == 0
        assert analysis.ai_categories == set()
        assert analysis.date_range is None

    def test_analyze_folder_with_documents(self, db_with_documents):
        """Test analyzing folder with documents."""
        conn = sqlite3.connect(db_with_documents)
        analysis = analyze_folder_content(conn, "/test/Resume")
        conn.close()

        assert analysis.document_count == 2
        assert "Employment/Resumes" in analysis.ai_categories
        assert analysis.date_range is not None
        assert "2024" in analysis.date_range[0] or "2024" in analysis.date_range[1]

    def test_analyze_folder_entities(self, db_with_documents):
        """Test entity extraction from folder analysis."""
        conn = sqlite3.connect(db_with_documents)
        analysis = analyze_folder_content(conn, "/test/Resume")
        conn.close()

        assert "people" in analysis.entities
        assert "John Doe" in analysis.entities["people"]

    def test_analyze_folder_original_paths(self, db_with_documents):
        """Test original path extraction from folder analysis."""
        conn = sqlite3.connect(db_with_documents)
        analysis = analyze_folder_content(conn, "/test/Resume")
        conn.close()

        assert len(analysis.original_paths) > 0


class TestAnalyzeFolderContentFromPath:
    """Tests for analyze_folder_content_from_path function."""

    def test_analyze_from_path(self, db_with_documents):
        """Test analyzing folder using database path."""
        analysis = analyze_folder_content_from_path(db_with_documents, "/test/Resume")
        assert analysis.document_count == 2

    def test_analyze_from_path_nonexistent_db(self):
        """Test analyzing with nonexistent database raises error."""
        with pytest.raises(FileNotFoundError):
            analyze_folder_content_from_path("/nonexistent/db.sqlite", "/test/folder")


# =============================================================================
# Test Consolidation Decision Functions
# =============================================================================


class TestShouldConsolidateFolders:
    """Tests for should_consolidate_folders function."""

    def test_similar_folders_should_consolidate(self, db_with_documents):
        """Test that similar folders (Resume and Resumes) should consolidate."""
        conn = sqlite3.connect(db_with_documents)
        decision = should_consolidate_folders(conn, "/test/Resume", "/test/Resumes")
        conn.close()

        assert decision.should_consolidate is True
        assert decision.matching_categories is True
        assert decision.confidence > 0.5

    def test_different_categories_should_not_consolidate(self, db_with_documents):
        """Test that folders with different categories should not consolidate."""
        conn = sqlite3.connect(db_with_documents)
        decision = should_consolidate_folders(conn, "/test/Resume", "/test/Taxes")
        conn.close()

        assert decision.should_consolidate is False
        assert decision.matching_categories is False

    def test_different_timeframes_should_not_consolidate(self, db_with_documents):
        """Test that folders with different timeframes should not consolidate."""
        conn = sqlite3.connect(db_with_documents)
        decision = should_consolidate_folders(conn, "/test/Taxes", "/test/Tax_2002")
        conn.close()

        assert decision.should_consolidate is False
        assert decision.matching_date_range is False
        assert any("timeframe" in r.lower() for r in decision.reasoning)

    def test_empty_folder_low_confidence(self, db_with_documents):
        """Test that empty folders have low confidence."""
        conn = sqlite3.connect(db_with_documents)
        decision = should_consolidate_folders(conn, "/test/Resume", "/empty/folder")
        conn.close()

        assert decision.confidence == 0.0
        assert "Insufficient data" in decision.reasoning[0]

    def test_decision_includes_reasoning(self, db_with_documents):
        """Test that decision includes detailed reasoning."""
        conn = sqlite3.connect(db_with_documents)
        decision = should_consolidate_folders(conn, "/test/Resume", "/test/Resumes")
        conn.close()

        assert len(decision.reasoning) > 0
        # Check for category-related reasoning (may be "category" or "categories")
        assert any("categor" in r.lower() for r in decision.reasoning)


class TestShouldConsolidateFoldersFromPath:
    """Tests for should_consolidate_folders_from_path function."""

    def test_consolidate_from_path(self, db_with_documents):
        """Test consolidation check using database path."""
        decision = should_consolidate_folders_from_path(
            db_with_documents, "/test/Resume", "/test/Resumes"
        )
        assert decision.should_consolidate is True

    def test_consolidate_from_path_nonexistent_db(self):
        """Test consolidation check with nonexistent database raises error."""
        with pytest.raises(FileNotFoundError):
            should_consolidate_folders_from_path(
                "/nonexistent/db.sqlite", "/folder1", "/folder2"
            )

    def test_consolidate_from_path_with_threshold(self, db_with_documents):
        """Test consolidation check with custom similarity threshold."""
        # With default threshold (0.6), these should consolidate
        decision = should_consolidate_folders_from_path(
            db_with_documents, "/test/Resume", "/test/Resumes"
        )
        assert decision.should_consolidate is True

        # With very high threshold (0.99), even good matches may fail
        decision = should_consolidate_folders_from_path(
            db_with_documents,
            "/test/Resume",
            "/test/Resumes",
            similarity_threshold=0.99,
        )
        # Confidence is typically < 1.0 so this should fail
        if decision.confidence < 0.99:
            assert decision.should_consolidate is False


class TestSimilarityThreshold:
    """Tests for configurable content similarity threshold."""

    def test_default_threshold_is_60_percent(self, db_with_documents):
        """Test that default threshold is 0.6 (60%)."""
        conn = sqlite3.connect(db_with_documents)
        # With the default threshold, similar folders should consolidate
        decision = should_consolidate_folders(conn, "/test/Resume", "/test/Resumes")
        conn.close()

        # Default behavior should allow consolidation at 60% confidence
        assert decision.should_consolidate is True

    def test_high_threshold_blocks_consolidation(self, db_with_documents):
        """Test that a high threshold blocks lower-confidence consolidations."""
        conn = sqlite3.connect(db_with_documents)
        # With a very high threshold (95%), even matching folders may not consolidate
        decision = should_consolidate_folders(
            conn, "/test/Resume", "/test/Resumes", similarity_threshold=0.95
        )
        conn.close()

        # If confidence is less than threshold, should not consolidate
        if decision.confidence < 0.95:
            assert decision.should_consolidate is False
            assert "below threshold" in " ".join(decision.reasoning).lower()

    def test_low_threshold_allows_more_consolidations(self, db_with_documents):
        """Test that a low threshold allows more consolidations."""
        conn = sqlite3.connect(db_with_documents)
        # With a very low threshold (20%), most folders should consolidate
        decision = should_consolidate_folders(
            conn, "/test/Resume", "/test/Resumes", similarity_threshold=0.2
        )
        conn.close()

        # With low threshold and matching content, should consolidate
        assert decision.should_consolidate is True

    def test_threshold_zero_always_consolidates(self, db_with_documents):
        """Test that threshold 0.0 always allows consolidation (if rules pass)."""
        conn = sqlite3.connect(db_with_documents)
        decision = should_consolidate_folders(
            conn, "/test/Resume", "/test/Resumes", similarity_threshold=0.0
        )
        conn.close()

        # With 0% threshold, any confidence should pass
        assert decision.should_consolidate is True

    def test_threshold_one_requires_perfect_match(self, db_with_documents):
        """Test that threshold 1.0 requires 100% confidence."""
        conn = sqlite3.connect(db_with_documents)
        decision = should_consolidate_folders(
            conn, "/test/Resume", "/test/Resumes", similarity_threshold=1.0
        )
        conn.close()

        # 100% confidence is very difficult to achieve
        if decision.confidence < 1.0:
            assert decision.should_consolidate is False

    def test_threshold_message_in_reasoning(self, db_with_documents):
        """Test that threshold value appears in reasoning when blocked."""
        conn = sqlite3.connect(db_with_documents)
        # Use a threshold that will likely block
        decision = should_consolidate_folders(
            conn, "/test/Resume", "/test/Resumes", similarity_threshold=0.99
        )
        conn.close()

        if not decision.should_consolidate:
            # Should mention both confidence and threshold in reasoning
            reasoning_text = " ".join(decision.reasoning).lower()
            assert "threshold" in reasoning_text or "99%" in reasoning_text

    def test_different_categories_still_blocked(self, db_with_documents):
        """Test that different categories block consolidation regardless of threshold."""
        conn = sqlite3.connect(db_with_documents)
        # Even with threshold 0, different categories should not consolidate
        decision = should_consolidate_folders(
            conn, "/test/Resume", "/test/Taxes", similarity_threshold=0.0
        )
        conn.close()

        # Different categories override threshold
        assert decision.should_consolidate is False

    def test_different_timeframes_still_blocked(self, db_with_documents):
        """Test that different timeframes block consolidation regardless of threshold."""
        conn = sqlite3.connect(db_with_documents)
        # Even with threshold 0, different timeframes should not consolidate
        decision = should_consolidate_folders(
            conn, "/test/Taxes", "/test/Tax_2002", similarity_threshold=0.0
        )
        conn.close()

        # Different timeframes override threshold
        assert decision.should_consolidate is False


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for content analyzer."""

    def test_full_analysis_workflow(self, db_with_documents):
        """Test complete analysis workflow."""
        conn = sqlite3.connect(db_with_documents)

        # Analyze both folders
        analysis1 = analyze_folder_content(conn, "/test/Resume")
        analysis2 = analyze_folder_content(conn, "/test/Resumes")

        # Check consolidation
        decision = should_consolidate_folders(conn, "/test/Resume", "/test/Resumes")

        conn.close()

        # Both should have documents
        assert analysis1.document_count > 0
        assert analysis2.document_count > 0

        # Should have same category
        assert analysis1.ai_categories == analysis2.ai_categories

        # Should consolidate
        assert decision.should_consolidate is True
        assert decision.confidence >= 0.6

    def test_prd_example_resume_consolidation(self, db_with_documents):
        """Test PRD example: Resume folders should consolidate."""
        conn = sqlite3.connect(db_with_documents)
        decision = should_consolidate_folders(conn, "/test/Resume", "/test/Resumes")
        conn.close()

        # Per PRD: "Resume" + "Resumes" + "Resume_Docs" (same content) → CAN consolidate
        assert decision.should_consolidate is True

    def test_prd_example_different_timeframes(self, db_with_documents):
        """Test PRD example: Different timeframes should NOT consolidate."""
        conn = sqlite3.connect(db_with_documents)
        decision = should_consolidate_folders(conn, "/test/Taxes", "/test/Tax_2002")
        conn.close()

        # Per PRD: Tax 2002 ≠ Tax 2025 (different timeframes) → DO NOT consolidate
        assert decision.should_consolidate is False

    def test_prd_example_different_categories(self, db_with_documents):
        """Test PRD example: Different categories should NOT consolidate."""
        conn = sqlite3.connect(db_with_documents)
        decision = should_consolidate_folders(conn, "/test/Resume", "/test/Taxes")
        conn.close()

        # Per PRD: Different content → DON'T consolidate
        assert decision.should_consolidate is False

    def test_decision_to_dict_roundtrip(self, db_with_documents):
        """Test that decision can be serialized to dict."""
        conn = sqlite3.connect(db_with_documents)
        decision = should_consolidate_folders(conn, "/test/Resume", "/test/Resumes")
        conn.close()

        result = decision.to_dict()

        assert isinstance(result, dict)
        assert result["should_consolidate"] == decision.should_consolidate
        assert result["confidence"] == decision.confidence
        assert result["reasoning"] == decision.reasoning

        # Should be JSON serializable
        json_str = json.dumps(result)
        assert isinstance(json_str, str)


# =============================================================================
# Test FileInfo and FolderScanResult
# =============================================================================


class TestFileInfo:
    """Tests for FileInfo dataclass."""

    def test_file_info_creation(self):
        """Test creating a FileInfo instance."""
        info = FileInfo(
            path="/test/file.pdf",
            filename="file.pdf",
            extension=".pdf",
            size_bytes=1024,
            modified_time="2024-01-01T10:00:00",
        )
        assert info.path == "/test/file.pdf"
        assert info.filename == "file.pdf"
        assert info.extension == ".pdf"
        assert info.size_bytes == 1024
        assert info.in_database is False

    def test_file_info_to_dict(self):
        """Test FileInfo.to_dict() serialization."""
        info = FileInfo(
            path="/test/file.pdf",
            filename="file.pdf",
            extension=".pdf",
            size_bytes=1024,
            modified_time="2024-01-01T10:00:00",
            in_database=True,
        )
        result = info.to_dict()
        assert result["path"] == "/test/file.pdf"
        assert result["in_database"] is True


class TestFolderScanResult:
    """Tests for FolderScanResult dataclass."""

    def test_folder_scan_result_creation(self):
        """Test creating a FolderScanResult instance."""
        result = FolderScanResult(folder_path="/test/folder")
        assert result.folder_path == "/test/folder"
        assert result.total_files == 0
        assert result.files_in_database == 0
        assert result.files_not_in_database == 0
        assert result.scanned_at != ""

    def test_folder_scan_result_with_files(self):
        """Test creating a FolderScanResult with files."""
        file1 = FileInfo(
            path="/test/file1.pdf",
            filename="file1.pdf",
            extension=".pdf",
            size_bytes=1024,
            modified_time="2024-01-01",
            in_database=True,
        )
        file2 = FileInfo(
            path="/test/file2.pdf",
            filename="file2.pdf",
            extension=".pdf",
            size_bytes=2048,
            modified_time="2024-01-02",
            in_database=False,
        )
        result = FolderScanResult(
            folder_path="/test/folder",
            total_files=2,
            files_in_database=1,
            files_not_in_database=1,
            files=[file1, file2],
            unanalyzed_files=[file2],
        )
        assert result.total_files == 2
        assert result.files_in_database == 1
        assert len(result.unanalyzed_files) == 1

    def test_folder_scan_result_to_dict(self):
        """Test FolderScanResult.to_dict() serialization."""
        result = FolderScanResult(
            folder_path="/test/folder",
            total_files=5,
            files_in_database=3,
            files_not_in_database=2,
        )
        d = result.to_dict()
        assert d["folder_path"] == "/test/folder"
        assert d["total_files"] == 5
        assert d["files_in_database"] == 3
        assert d["files_not_in_database"] == 2


# =============================================================================
# Test DocumentProcessor Integration Functions
# =============================================================================


class TestIsSupportedFile:
    """Tests for is_supported_file function."""

    def test_pdf_is_supported(self):
        """Test that PDF files are supported."""
        assert is_supported_file("/test/file.pdf") is True

    def test_doc_is_supported(self):
        """Test that DOC files are supported."""
        assert is_supported_file("/test/file.doc") is True

    def test_docx_is_supported(self):
        """Test that DOCX files are supported."""
        assert is_supported_file("/test/file.docx") is True

    def test_txt_is_supported(self):
        """Test that TXT files are supported."""
        assert is_supported_file("/test/file.txt") is True

    def test_xlsx_is_supported(self):
        """Test that XLSX files are supported."""
        assert is_supported_file("/test/file.xlsx") is True

    def test_image_is_supported(self):
        """Test that image files are supported."""
        assert is_supported_file("/test/image.png") is True
        assert is_supported_file("/test/image.jpg") is True
        assert is_supported_file("/test/image.jpeg") is True

    def test_unsupported_extension(self):
        """Test that unsupported extensions return False."""
        assert is_supported_file("/test/file.xyz") is False
        assert is_supported_file("/test/file.exe") is False

    def test_custom_extensions(self):
        """Test with custom extension set."""
        custom = {".custom", ".xyz"}
        assert is_supported_file("/test/file.custom", custom) is True
        assert is_supported_file("/test/file.pdf", custom) is False

    def test_case_insensitive(self):
        """Test that extension matching is case-insensitive."""
        assert is_supported_file("/test/file.PDF") is True
        assert is_supported_file("/test/file.Pdf") is True


class TestScanFolderForFiles:
    """Tests for scan_folder_for_files function."""

    def test_scan_empty_folder(self, tmp_path):
        """Test scanning an empty folder."""
        files = scan_folder_for_files(str(tmp_path))
        assert files == []

    def test_scan_folder_with_files(self, tmp_path):
        """Test scanning a folder with files."""
        # Create test files
        (tmp_path / "file1.pdf").write_text("content1")
        (tmp_path / "file2.txt").write_text("content2")

        files = scan_folder_for_files(str(tmp_path))
        assert len(files) == 2
        filenames = {f.filename for f in files}
        assert "file1.pdf" in filenames
        assert "file2.txt" in filenames

    def test_scan_with_extension_filter(self, tmp_path):
        """Test scanning with extension filter."""
        (tmp_path / "file1.pdf").write_text("content1")
        (tmp_path / "file2.txt").write_text("content2")
        (tmp_path / "file3.exe").write_text("content3")

        files = scan_folder_for_files(str(tmp_path), extensions={".pdf"})
        assert len(files) == 1
        assert files[0].filename == "file1.pdf"

    def test_scan_recursive(self, tmp_path):
        """Test recursive scanning."""
        # Create nested structure
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (tmp_path / "file1.pdf").write_text("content1")
        (subdir / "file2.pdf").write_text("content2")

        files = scan_folder_for_files(str(tmp_path), recursive=True)
        assert len(files) == 2

    def test_scan_non_recursive(self, tmp_path):
        """Test non-recursive scanning."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (tmp_path / "file1.pdf").write_text("content1")
        (subdir / "file2.pdf").write_text("content2")

        files = scan_folder_for_files(str(tmp_path), recursive=False)
        assert len(files) == 1
        assert files[0].filename == "file1.pdf"

    def test_scan_nonexistent_folder(self):
        """Test scanning a nonexistent folder."""
        files = scan_folder_for_files("/nonexistent/folder")
        assert files == []

    def test_file_info_populated(self, tmp_path):
        """Test that FileInfo fields are properly populated."""
        (tmp_path / "test.pdf").write_text("test content")

        files = scan_folder_for_files(str(tmp_path))
        assert len(files) == 1

        f = files[0]
        assert f.filename == "test.pdf"
        assert f.extension == ".pdf"
        assert f.size_bytes > 0
        assert f.modified_time != ""
        assert f.in_database is False


class TestCheckFilesInDatabase:
    """Tests for check_files_in_database function."""

    def test_files_not_in_database(self, temp_db):
        """Test checking files that are not in database."""
        conn = sqlite3.connect(temp_db)
        files = [
            FileInfo(
                path="/test/file.pdf",
                filename="file.pdf",
                extension=".pdf",
                size_bytes=1024,
                modified_time="2024-01-01",
            )
        ]
        result = check_files_in_database(conn, files)
        conn.close()

        assert len(result) == 1
        assert result[0].in_database is False

    def test_files_in_database(self, db_with_documents):
        """Test checking files that are in database."""
        conn = sqlite3.connect(db_with_documents)
        files = [
            FileInfo(
                path="/test/Resume/resume_2024.pdf",
                filename="resume_2024.pdf",
                extension=".pdf",
                size_bytes=1024,
                modified_time="2024-01-01",
            )
        ]
        result = check_files_in_database(conn, files)
        conn.close()

        assert len(result) == 1
        assert result[0].in_database is True

    def test_mixed_files(self, db_with_documents):
        """Test checking a mix of files in and not in database."""
        conn = sqlite3.connect(db_with_documents)
        files = [
            FileInfo(
                path="/test/Resume/resume_2024.pdf",
                filename="resume_2024.pdf",
                extension=".pdf",
                size_bytes=1024,
                modified_time="2024-01-01",
            ),
            FileInfo(
                path="/test/new_file.pdf",
                filename="new_file.pdf",
                extension=".pdf",
                size_bytes=2048,
                modified_time="2024-01-02",
            ),
        ]
        result = check_files_in_database(conn, files)
        conn.close()

        in_db = [f for f in result if f.in_database]
        not_in_db = [f for f in result if not f.in_database]

        assert len(in_db) == 1
        assert len(not_in_db) == 1


class TestScanFolderWithDatabase:
    """Tests for scan_folder_with_database function."""

    def test_scan_empty_folder(self, temp_db, tmp_path):
        """Test scanning empty folder with database."""
        conn = sqlite3.connect(temp_db)
        result = scan_folder_with_database(conn, str(tmp_path))
        conn.close()

        assert result.total_files == 0
        assert result.files_in_database == 0
        assert result.files_not_in_database == 0

    def test_scan_folder_with_unanalyzed_files(self, temp_db, tmp_path):
        """Test scanning folder with files not in database."""
        # Create test files
        (tmp_path / "file1.pdf").write_text("content1")
        (tmp_path / "file2.txt").write_text("content2")

        conn = sqlite3.connect(temp_db)
        result = scan_folder_with_database(conn, str(tmp_path))
        conn.close()

        assert result.total_files == 2
        assert result.files_in_database == 0
        assert result.files_not_in_database == 2
        assert len(result.unanalyzed_files) == 2


class TestScanFolderWithDatabaseFromPath:
    """Tests for scan_folder_with_database_from_path function."""

    def test_scan_from_path(self, temp_db, tmp_path):
        """Test scanning using database path."""
        (tmp_path / "test.pdf").write_text("content")

        result = scan_folder_with_database_from_path(temp_db, str(tmp_path))

        assert result.total_files == 1
        assert result.files_not_in_database == 1

    def test_scan_from_path_nonexistent_db(self, tmp_path):
        """Test scanning with nonexistent database raises error."""
        with pytest.raises(FileNotFoundError):
            scan_folder_with_database_from_path("/nonexistent/db.sqlite", str(tmp_path))


# =============================================================================
# Test DefaultDocumentProcessor
# =============================================================================


class TestDefaultDocumentProcessor:
    """Tests for DefaultDocumentProcessor class."""

    def test_create_processor(self):
        """Test creating a DefaultDocumentProcessor."""
        processor = DefaultDocumentProcessor()
        assert processor.extensions == SUPPORTED_EXTENSIONS

    def test_create_processor_custom_extensions(self):
        """Test creating processor with custom extensions."""
        custom = {".custom"}
        processor = DefaultDocumentProcessor(extensions=custom)
        assert processor.extensions == custom

    def test_is_processable_supported(self):
        """Test is_processable for supported files."""
        processor = DefaultDocumentProcessor()
        assert processor.is_processable("/test/file.pdf") is True
        assert processor.is_processable("/test/file.docx") is True

    def test_is_processable_unsupported(self):
        """Test is_processable for unsupported files."""
        processor = DefaultDocumentProcessor()
        assert processor.is_processable("/test/file.exe") is False
        assert processor.is_processable("/test/file.xyz") is False

    def test_find_files(self, tmp_path):
        """Test finding files in a folder."""
        (tmp_path / "file1.pdf").write_text("content1")
        (tmp_path / "file2.txt").write_text("content2")
        (tmp_path / "file3.exe").write_text("content3")

        processor = DefaultDocumentProcessor()
        files = processor.find_files(str(tmp_path))

        # Should find pdf and txt but not exe
        assert len(files) == 2
        extensions = {Path(f).suffix for f in files}
        assert ".pdf" in extensions
        assert ".txt" in extensions
        assert ".exe" not in extensions

    def test_process_file_success(self, tmp_path):
        """Test processing an existing file."""
        test_file = tmp_path / "test.pdf"
        test_file.write_text("test content")

        processor = DefaultDocumentProcessor()
        result = processor.process_file(str(test_file))

        assert result["success"] is True
        assert result["filename"] == "test.pdf"
        assert result["extension"] == ".pdf"
        assert result["size_bytes"] > 0

    def test_process_file_not_found(self):
        """Test processing a nonexistent file."""
        processor = DefaultDocumentProcessor()
        result = processor.process_file("/nonexistent/file.pdf")

        assert result["success"] is False
        assert "error" in result

    def test_create_document_processor_factory(self):
        """Test the factory function creates a processor."""
        processor = create_document_processor()
        assert isinstance(processor, DefaultDocumentProcessor)

    def test_create_document_processor_with_extensions(self):
        """Test factory with custom extensions."""
        processor = create_document_processor(extensions={".custom"})
        assert processor.extensions == {".custom"}


class TestProcessUnanalyzedFiles:
    """Tests for process_unanalyzed_files function."""

    def test_process_files(self, tmp_path):
        """Test processing a list of files."""
        test_file = tmp_path / "test.pdf"
        test_file.write_text("content")

        files = [
            FileInfo(
                path=str(test_file),
                filename="test.pdf",
                extension=".pdf",
                size_bytes=7,
                modified_time="2024-01-01",
            )
        ]

        processor = DefaultDocumentProcessor()
        results = process_unanalyzed_files(processor, files)

        assert len(results) == 1
        assert results[0]["success"] is True

    def test_process_with_progress_callback(self, tmp_path):
        """Test processing with progress callback."""
        test_file = tmp_path / "test.pdf"
        test_file.write_text("content")

        files = [
            FileInfo(
                path=str(test_file),
                filename="test.pdf",
                extension=".pdf",
                size_bytes=7,
                modified_time="2024-01-01",
            )
        ]

        progress_calls = []

        def callback(current, total, filename):
            progress_calls.append((current, total, filename))

        processor = DefaultDocumentProcessor()
        process_unanalyzed_files(processor, files, progress_callback=callback)

        assert len(progress_calls) == 1
        assert progress_calls[0] == (1, 1, "test.pdf")

    def test_process_skips_unsupported(self, tmp_path):
        """Test that unsupported files are skipped."""
        test_file = tmp_path / "test.exe"
        test_file.write_text("content")

        files = [
            FileInfo(
                path=str(test_file),
                filename="test.exe",
                extension=".exe",
                size_bytes=7,
                modified_time="2024-01-01",
            )
        ]

        processor = DefaultDocumentProcessor()
        results = process_unanalyzed_files(processor, files)

        # Should be empty since .exe is not processable
        assert len(results) == 0


# =============================================================================
# Test analyze_folder_with_processing
# =============================================================================


class TestAnalyzeFolderWithProcessing:
    """Tests for analyze_folder_with_processing function."""

    def test_analyze_without_processor(self, db_with_documents):
        """Test analyzing folder without processor."""
        conn = sqlite3.connect(db_with_documents)
        analysis = analyze_folder_with_processing(conn, "/test/Resume")
        conn.close()

        assert analysis.document_count == 2
        assert "Employment/Resumes" in analysis.ai_categories

    def test_analyze_with_processor_no_analyze_missing(self, db_with_documents):
        """Test analyzing with processor but analyze_missing=False."""
        conn = sqlite3.connect(db_with_documents)
        processor = DefaultDocumentProcessor()
        analysis = analyze_folder_with_processing(
            conn, "/test/Resume", processor=processor, analyze_missing=False
        )
        conn.close()

        # Should still work normally
        assert analysis.document_count == 2


class TestAnalyzeFolderWithProcessingFromPath:
    """Tests for analyze_folder_with_processing_from_path function."""

    def test_analyze_from_path(self, db_with_documents):
        """Test analyzing folder using database path."""
        analysis = analyze_folder_with_processing_from_path(
            db_with_documents, "/test/Resume"
        )
        assert analysis.document_count == 2

    def test_analyze_from_path_nonexistent_db(self):
        """Test analyzing with nonexistent database raises error."""
        with pytest.raises(FileNotFoundError):
            analyze_folder_with_processing_from_path(
                "/nonexistent/db.sqlite", "/test/folder"
            )


# =============================================================================
# Test SUPPORTED_EXTENSIONS constant
# =============================================================================


class TestSupportedExtensions:
    """Tests for SUPPORTED_EXTENSIONS constant."""

    def test_common_document_types(self):
        """Test that common document types are supported."""
        assert ".pdf" in SUPPORTED_EXTENSIONS
        assert ".doc" in SUPPORTED_EXTENSIONS
        assert ".docx" in SUPPORTED_EXTENSIONS
        assert ".txt" in SUPPORTED_EXTENSIONS

    def test_spreadsheet_types(self):
        """Test that spreadsheet types are supported."""
        assert ".xls" in SUPPORTED_EXTENSIONS
        assert ".xlsx" in SUPPORTED_EXTENSIONS
        assert ".csv" in SUPPORTED_EXTENSIONS

    def test_image_types(self):
        """Test that image types are supported."""
        assert ".png" in SUPPORTED_EXTENSIONS
        assert ".jpg" in SUPPORTED_EXTENSIONS
        assert ".jpeg" in SUPPORTED_EXTENSIONS

    def test_presentation_types(self):
        """Test that presentation types are supported."""
        assert ".ppt" in SUPPORTED_EXTENSIONS
        assert ".pptx" in SUPPORTED_EXTENSIONS
