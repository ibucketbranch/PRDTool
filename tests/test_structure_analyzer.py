"""Tests for structure_analyzer module - tree walking, metadata extraction, patterns.

Covers:
- FolderNode dataclass creation and serialization
- StructureSnapshot creation, serialization, and loading
- StructureAnalyzer tree walking with depth limiting
- Ignore patterns (system folders, custom patterns)
- Naming pattern detection (YYYY_*, YYYY-MM-DD_*, prefix_*, version suffix)
- Date structure detection (year folders, month folders)
- LLM narration (mock) and keyword fallback
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from organizer.structure_analyzer import (
    DEFAULT_IGNORE_PATTERNS,
    SYSTEM_FOLDERS,
    FolderNode,
    StructureAnalyzer,
    StructureSnapshot,
    analyze_structure,
    load_structure,
)


class TestFolderNode:
    """Tests for FolderNode dataclass."""

    def test_create_folder_node(self) -> None:
        """Should create FolderNode with required fields."""
        node = FolderNode(
            path="/path/to/folder",
            name="folder",
            depth=2,
        )
        assert node.path == "/path/to/folder"
        assert node.name == "folder"
        assert node.depth == 2
        assert node.file_count == 0
        assert node.subfolder_count == 0
        assert node.total_size_bytes == 0
        assert node.file_types == {}
        assert node.sample_filenames == []
        assert node.naming_patterns == []
        assert node.has_date_structure is False
        # scanned_at should be auto-set
        assert node.scanned_at != ""

    def test_create_folder_node_with_all_fields(self) -> None:
        """Should create FolderNode with all optional fields."""
        node = FolderNode(
            path="/path/to/folder",
            name="folder",
            depth=1,
            file_count=10,
            subfolder_count=3,
            total_size_bytes=1024000,
            file_types={".pdf": 5, ".txt": 3, ".doc": 2},
            sample_filenames=["doc1.pdf", "doc2.pdf", "notes.txt"],
            naming_patterns=["YYYY_*", "prefix_*"],
            has_date_structure=True,
            scanned_at="2024-01-15T10:30:00",
        )
        assert node.file_count == 10
        assert node.subfolder_count == 3
        assert node.total_size_bytes == 1024000
        assert node.file_types == {".pdf": 5, ".txt": 3, ".doc": 2}
        assert node.sample_filenames == ["doc1.pdf", "doc2.pdf", "notes.txt"]
        assert node.naming_patterns == ["YYYY_*", "prefix_*"]
        assert node.has_date_structure is True
        assert node.scanned_at == "2024-01-15T10:30:00"

    def test_to_dict(self) -> None:
        """Should convert FolderNode to dictionary."""
        node = FolderNode(
            path="/test/folder",
            name="folder",
            depth=0,
            file_count=5,
            file_types={".pdf": 3, ".txt": 2},
        )
        d = node.to_dict()
        assert d["path"] == "/test/folder"
        assert d["name"] == "folder"
        assert d["depth"] == 0
        assert d["file_count"] == 5
        assert d["file_types"] == {".pdf": 3, ".txt": 2}

    def test_from_dict(self) -> None:
        """Should create FolderNode from dictionary."""
        data = {
            "path": "/path/to/folder",
            "name": "folder",
            "depth": 2,
            "file_count": 10,
            "subfolder_count": 2,
            "total_size_bytes": 5000,
            "file_types": {".pdf": 8, ".doc": 2},
            "sample_filenames": ["file1.pdf", "file2.doc"],
            "naming_patterns": ["YYYY_*"],
            "has_date_structure": True,
            "scanned_at": "2024-02-01T12:00:00",
        }
        node = FolderNode.from_dict(data)
        assert node.path == "/path/to/folder"
        assert node.name == "folder"
        assert node.depth == 2
        assert node.file_count == 10
        assert node.file_types == {".pdf": 8, ".doc": 2}
        assert node.has_date_structure is True

    def test_from_dict_missing_fields(self) -> None:
        """Should handle missing fields with defaults."""
        data = {"path": "/test", "name": "test", "depth": 0}
        node = FolderNode.from_dict(data)
        assert node.path == "/test"
        assert node.file_count == 0
        assert node.file_types == {}
        assert node.naming_patterns == []
        assert node.has_date_structure is False

    def test_roundtrip(self) -> None:
        """Should roundtrip through to_dict/from_dict."""
        original = FolderNode(
            path="/test/path",
            name="path",
            depth=1,
            file_count=5,
            file_types={".pdf": 5},
            naming_patterns=["invoice_*"],
            has_date_structure=False,
        )
        restored = FolderNode.from_dict(original.to_dict())
        assert restored.path == original.path
        assert restored.name == original.name
        assert restored.depth == original.depth
        assert restored.file_count == original.file_count
        assert restored.file_types == original.file_types
        assert restored.naming_patterns == original.naming_patterns


class TestStructureSnapshot:
    """Tests for StructureSnapshot dataclass."""

    def test_create_snapshot(self) -> None:
        """Should create StructureSnapshot with required fields."""
        snapshot = StructureSnapshot(
            root_path="/path/to/root",
            max_depth=4,
        )
        assert snapshot.root_path == "/path/to/root"
        assert snapshot.max_depth == 4
        assert snapshot.total_folders == 0
        assert snapshot.total_files == 0
        assert snapshot.total_size_bytes == 0
        assert snapshot.folders == []
        assert snapshot.strategy_description == ""
        assert snapshot.model_used == ""
        # analyzed_at should be auto-set
        assert snapshot.analyzed_at != ""

    def test_create_snapshot_with_folders(self) -> None:
        """Should create StructureSnapshot with folder nodes."""
        folders = [
            FolderNode(path="/root", name="root", depth=0, file_count=3),
            FolderNode(path="/root/docs", name="docs", depth=1, file_count=10),
        ]
        snapshot = StructureSnapshot(
            root_path="/root",
            max_depth=4,
            total_folders=2,
            total_files=13,
            folders=folders,
        )
        assert len(snapshot.folders) == 2
        assert snapshot.total_folders == 2
        assert snapshot.total_files == 13

    def test_to_dict(self) -> None:
        """Should convert StructureSnapshot to dictionary."""
        folders = [FolderNode(path="/root", name="root", depth=0)]
        snapshot = StructureSnapshot(
            root_path="/root",
            max_depth=4,
            total_folders=1,
            folders=folders,
            strategy_description="Test description",
        )
        d = snapshot.to_dict()
        assert d["version"] == "1.0"
        assert d["root_path"] == "/root"
        assert d["max_depth"] == 4
        assert d["total_folders"] == 1
        assert len(d["folders"]) == 1
        assert d["strategy_description"] == "Test description"

    def test_from_dict(self) -> None:
        """Should create StructureSnapshot from dictionary."""
        data = {
            "version": "1.0",
            "root_path": "/test/root",
            "max_depth": 3,
            "total_folders": 5,
            "total_files": 100,
            "total_size_bytes": 50000,
            "folders": [
                {"path": "/test/root", "name": "root", "depth": 0},
                {"path": "/test/root/sub", "name": "sub", "depth": 1},
            ],
            "strategy_description": "Category-based organization",
            "model_used": "qwen2.5:14b",
            "analyzed_at": "2024-01-15T10:30:00",
        }
        snapshot = StructureSnapshot.from_dict(data)
        assert snapshot.root_path == "/test/root"
        assert snapshot.max_depth == 3
        assert snapshot.total_folders == 5
        assert len(snapshot.folders) == 2
        assert snapshot.strategy_description == "Category-based organization"
        assert snapshot.model_used == "qwen2.5:14b"

    def test_save_and_load(self) -> None:
        """Should save snapshot to file and load it back."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "structure.json"

            folders = [
                FolderNode(path="/root", name="root", depth=0, file_count=5),
                FolderNode(path="/root/docs", name="docs", depth=1, file_count=10),
            ]
            original = StructureSnapshot(
                root_path="/root",
                max_depth=4,
                total_folders=2,
                total_files=15,
                folders=folders,
                strategy_description="Test strategy",
            )
            original.save(output_path)

            # Verify file was created
            assert output_path.exists()

            # Load and verify
            loaded = StructureSnapshot.load(output_path)
            assert loaded.root_path == original.root_path
            assert loaded.max_depth == original.max_depth
            assert loaded.total_folders == original.total_folders
            assert loaded.total_files == original.total_files
            assert len(loaded.folders) == 2
            assert loaded.strategy_description == "Test strategy"

    def test_get_folders_at_depth(self) -> None:
        """Should filter folders by depth."""
        folders = [
            FolderNode(path="/root", name="root", depth=0),
            FolderNode(path="/root/a", name="a", depth=1),
            FolderNode(path="/root/b", name="b", depth=1),
            FolderNode(path="/root/a/c", name="c", depth=2),
        ]
        snapshot = StructureSnapshot(
            root_path="/root",
            max_depth=4,
            folders=folders,
        )

        depth_0 = snapshot.get_folders_at_depth(0)
        assert len(depth_0) == 1
        assert depth_0[0].name == "root"

        depth_1 = snapshot.get_folders_at_depth(1)
        assert len(depth_1) == 2
        assert {f.name for f in depth_1} == {"a", "b"}

        depth_2 = snapshot.get_folders_at_depth(2)
        assert len(depth_2) == 1
        assert depth_2[0].name == "c"

    def test_get_top_file_types(self) -> None:
        """Should aggregate and return top file types."""
        folders = [
            FolderNode(
                path="/root",
                name="root",
                depth=0,
                file_types={".pdf": 10, ".txt": 5},
            ),
            FolderNode(
                path="/root/sub",
                name="sub",
                depth=1,
                file_types={".pdf": 5, ".doc": 8, ".txt": 2},
            ),
        ]
        snapshot = StructureSnapshot(
            root_path="/root",
            max_depth=4,
            folders=folders,
        )

        top_types = snapshot.get_top_file_types(3)
        assert len(top_types) == 3
        # .pdf should be first (15 total)
        assert top_types[0] == (".pdf", 15)
        # .doc second (8 total)
        assert top_types[1] == (".doc", 8)
        # .txt third (7 total)
        assert top_types[2] == (".txt", 7)


class TestStructureAnalyzerTreeWalking:
    """Tests for StructureAnalyzer tree walking functionality."""

    def test_analyze_simple_structure(self) -> None:
        """Should analyze a simple folder structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()

            # Create structure
            (root / "docs").mkdir()
            (root / "images").mkdir()
            (root / "docs" / "test.pdf").touch()
            (root / "docs" / "readme.txt").touch()
            (root / "images" / "photo.jpg").touch()

            analyzer = StructureAnalyzer(use_llm=False)
            result = analyzer.analyze(root, max_depth=4)

            assert result.root_path == str(root)
            assert result.total_folders >= 3  # root, docs, images
            assert result.total_files >= 3

    def test_analyze_with_depth_limit(self) -> None:
        """Should respect max_depth limit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            # Create deep structure
            (root / "level1" / "level2" / "level3" / "level4").mkdir(parents=True)
            (root / "level1" / "file1.txt").touch()
            (root / "level1" / "level2" / "file2.txt").touch()
            (root / "level1" / "level2" / "level3" / "file3.txt").touch()
            (root / "level1" / "level2" / "level3" / "level4" / "file4.txt").touch()

            # Analyze with max_depth=2
            analyzer = StructureAnalyzer(use_llm=False)
            result = analyzer.analyze(root, max_depth=2)

            # Should only have folders up to depth 2
            depths = [f.depth for f in result.folders]
            assert max(depths) <= 2

            # Depth 3 folder should not be included
            folder_names = [f.name for f in result.folders]
            assert "level3" not in folder_names
            assert "level4" not in folder_names

    def test_analyze_skips_system_folders(self) -> None:
        """Should skip system folders like .git, __pycache__, node_modules."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            # Create system folders
            (root / ".git").mkdir()
            (root / "__pycache__").mkdir()
            (root / "node_modules").mkdir()
            (root / "docs").mkdir()  # Regular folder

            # Add files to system folders
            (root / ".git" / "config").touch()
            (root / "__pycache__" / "module.pyc").touch()
            (root / "docs" / "readme.txt").touch()

            analyzer = StructureAnalyzer(use_llm=False)
            result = analyzer.analyze(root, max_depth=4)

            folder_names = [f.name for f in result.folders]
            assert ".git" not in folder_names
            assert "__pycache__" not in folder_names
            assert "node_modules" not in folder_names
            assert "docs" in folder_names

    def test_analyze_skips_hidden_folders(self) -> None:
        """Should skip hidden folders (starting with .)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            # Create hidden and visible folders
            (root / ".hidden").mkdir()
            (root / ".cache").mkdir()
            (root / "visible").mkdir()

            analyzer = StructureAnalyzer(use_llm=False)
            result = analyzer.analyze(root, max_depth=4)

            folder_names = [f.name for f in result.folders]
            assert ".hidden" not in folder_names
            assert ".cache" not in folder_names
            assert "visible" in folder_names

    def test_analyze_with_custom_ignore_patterns(self) -> None:
        """Should respect custom ignore patterns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            # Create folders
            (root / "backup").mkdir()
            (root / "temp").mkdir()
            (root / "docs").mkdir()

            custom_patterns = ["*/backup", "*/temp"]
            analyzer = StructureAnalyzer(
                use_llm=False,
                ignore_patterns=custom_patterns,
            )
            result = analyzer.analyze(root, max_depth=4)

            folder_names = [f.name for f in result.folders]
            assert "backup" not in folder_names
            assert "temp" not in folder_names
            assert "docs" in folder_names

    def test_analyze_nonexistent_path(self) -> None:
        """Should raise FileNotFoundError for nonexistent path."""
        analyzer = StructureAnalyzer(use_llm=False)
        with pytest.raises(FileNotFoundError):
            analyzer.analyze("/nonexistent/path/that/does/not/exist")

    def test_analyze_file_not_directory(self) -> None:
        """Should raise NotADirectoryError when given a file."""
        with tempfile.NamedTemporaryFile() as f:
            analyzer = StructureAnalyzer(use_llm=False)
            with pytest.raises(NotADirectoryError):
                analyzer.analyze(f.name)


class TestStructureAnalyzerMetadataExtraction:
    """Tests for metadata extraction functionality."""

    def test_extract_file_count_and_types(self) -> None:
        """Should count files and extract file types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            # Create files with different extensions
            (root / "doc1.pdf").touch()
            (root / "doc2.pdf").touch()
            (root / "doc3.pdf").touch()
            (root / "notes.txt").touch()
            (root / "data.json").touch()

            analyzer = StructureAnalyzer(use_llm=False)
            result = analyzer.analyze(root, max_depth=4)

            # Find root folder
            root_folder = next(f for f in result.folders if f.depth == 0)

            assert root_folder.file_count == 5
            assert root_folder.file_types.get(".pdf") == 3
            assert root_folder.file_types.get(".txt") == 1
            assert root_folder.file_types.get(".json") == 1

    def test_extract_sample_filenames(self) -> None:
        """Should collect sample filenames (up to 10)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            # Create many files
            for i in range(15):
                (root / f"file_{i:02d}.txt").touch()

            analyzer = StructureAnalyzer(use_llm=False)
            result = analyzer.analyze(root, max_depth=4)

            root_folder = next(f for f in result.folders if f.depth == 0)

            # Should have at most 10 samples
            assert len(root_folder.sample_filenames) <= 10
            assert len(root_folder.sample_filenames) > 0

    def test_extract_subfolder_count(self) -> None:
        """Should count immediate subfolders."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            # Create subfolders
            (root / "sub1").mkdir()
            (root / "sub2").mkdir()
            (root / "sub3").mkdir()
            # Create a file (should not be counted as subfolder)
            (root / "file.txt").touch()

            analyzer = StructureAnalyzer(use_llm=False)
            result = analyzer.analyze(root, max_depth=4)

            root_folder = next(f for f in result.folders if f.depth == 0)

            assert root_folder.subfolder_count == 3

    def test_skip_hidden_files_in_count(self) -> None:
        """Should not count hidden files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            # Create visible and hidden files
            (root / "visible.txt").touch()
            (root / ".hidden.txt").touch()
            (root / ".DS_Store").touch()

            analyzer = StructureAnalyzer(use_llm=False)
            result = analyzer.analyze(root, max_depth=4)

            root_folder = next(f for f in result.folders if f.depth == 0)

            # Only visible.txt should be counted
            assert root_folder.file_count == 1


class TestNamingPatternDetection:
    """Tests for naming pattern detection."""

    def test_detect_year_prefix_pattern(self) -> None:
        """Should detect YYYY_* pattern in filenames."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            # Create files with year prefix
            (root / "2020_report.pdf").touch()
            (root / "2021_report.pdf").touch()
            (root / "2022_report.pdf").touch()
            (root / "2023_report.pdf").touch()

            analyzer = StructureAnalyzer(use_llm=False)
            result = analyzer.analyze(root, max_depth=4)

            root_folder = next(f for f in result.folders if f.depth == 0)
            assert "YYYY_*" in root_folder.naming_patterns

    def test_detect_date_prefix_pattern(self) -> None:
        """Should detect YYYY-MM-DD_* pattern in filenames."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            # Create files with date prefix
            (root / "2024-01-15_meeting_notes.txt").touch()
            (root / "2024-02-20_project_update.txt").touch()
            (root / "2024-03-01_review.txt").touch()

            analyzer = StructureAnalyzer(use_llm=False)
            result = analyzer.analyze(root, max_depth=4)

            root_folder = next(f for f in result.folders if f.depth == 0)
            assert "YYYY-MM-DD_*" in root_folder.naming_patterns

    def test_detect_common_prefix_pattern(self) -> None:
        """Should detect common prefix in filenames."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            # Create files with common prefix
            (root / "invoice_001.pdf").touch()
            (root / "invoice_002.pdf").touch()
            (root / "invoice_003.pdf").touch()

            analyzer = StructureAnalyzer(use_llm=False)
            result = analyzer.analyze(root, max_depth=4)

            root_folder = next(f for f in result.folders if f.depth == 0)
            # Should detect "invoice_*" pattern
            assert any("invoice" in p for p in root_folder.naming_patterns)

    def test_detect_version_suffix_pattern(self) -> None:
        """Should detect *_vN version suffix pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            # Create files with version suffix
            (root / "document_v1.pdf").touch()
            (root / "document_v2.pdf").touch()
            (root / "report_final.pdf").touch()

            analyzer = StructureAnalyzer(use_llm=False)
            result = analyzer.analyze(root, max_depth=4)

            root_folder = next(f for f in result.folders if f.depth == 0)
            assert "*_vN" in root_folder.naming_patterns

    def test_no_pattern_for_few_files(self) -> None:
        """Should not detect patterns with insufficient files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            # Create only one file with year prefix
            (root / "2024_single.pdf").touch()

            analyzer = StructureAnalyzer(use_llm=False)
            result = analyzer.analyze(root, max_depth=4)

            root_folder = next(f for f in result.folders if f.depth == 0)
            # YYYY_* should not be detected with only one file
            assert "YYYY_*" not in root_folder.naming_patterns


class TestDateStructureDetection:
    """Tests for date-based folder structure detection."""

    def test_detect_year_folders(self) -> None:
        """Should detect year-based folder structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            # Create year folders
            (root / "2019").mkdir()
            (root / "2020").mkdir()
            (root / "2021").mkdir()
            (root / "2022").mkdir()

            analyzer = StructureAnalyzer(use_llm=False)
            result = analyzer.analyze(root, max_depth=4)

            root_folder = next(f for f in result.folders if f.depth == 0)
            assert root_folder.has_date_structure is True

    def test_detect_month_folders_numeric(self) -> None:
        """Should detect numeric month folders (01-12)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            # Create month folders
            (root / "01").mkdir()
            (root / "02").mkdir()
            (root / "03").mkdir()
            (root / "04").mkdir()

            analyzer = StructureAnalyzer(use_llm=False)
            result = analyzer.analyze(root, max_depth=4)

            root_folder = next(f for f in result.folders if f.depth == 0)
            assert root_folder.has_date_structure is True

    def test_detect_month_folders_named(self) -> None:
        """Should detect named month folders (Jan, Feb, etc.)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            # Create month folders
            (root / "January").mkdir()
            (root / "February").mkdir()
            (root / "March").mkdir()

            analyzer = StructureAnalyzer(use_llm=False)
            result = analyzer.analyze(root, max_depth=4)

            root_folder = next(f for f in result.folders if f.depth == 0)
            assert root_folder.has_date_structure is True

    def test_no_date_structure_for_non_dates(self) -> None:
        """Should not detect date structure for non-date folders."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            # Create non-date folders
            (root / "Documents").mkdir()
            (root / "Images").mkdir()
            (root / "Projects").mkdir()

            analyzer = StructureAnalyzer(use_llm=False)
            result = analyzer.analyze(root, max_depth=4)

            root_folder = next(f for f in result.folders if f.depth == 0)
            assert root_folder.has_date_structure is False


class TestNarrationWithMockLLM:
    """Tests for LLM-powered narration with mock client."""

    def test_narration_with_llm(self) -> None:
        """Should generate narration using LLM."""
        # Create mock LLM client
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = "This folder uses category-based organization with separate areas for documents, images, and projects."
        mock_response.model_used = "qwen2.5-coder:14b"

        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = True
        mock_client.generate.return_value = mock_response

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "documents").mkdir()
            (root / "images").mkdir()
            (root / "projects").mkdir()

            analyzer = StructureAnalyzer(
                llm_client=mock_client,
                use_llm=True,
            )
            result = analyzer.analyze(root, max_depth=4, generate_narration=True)

            assert "category-based" in result.strategy_description
            assert result.model_used == "qwen2.5-coder:14b"
            mock_client.generate.assert_called_once()

    def test_narration_fallback_when_llm_unavailable(self) -> None:
        """Should fall back to keyword narration when LLM unavailable."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = False

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "documents").mkdir()
            (root / "images").mkdir()

            analyzer = StructureAnalyzer(
                llm_client=mock_client,
                use_llm=True,
            )
            result = analyzer.analyze(root, max_depth=4, generate_narration=True)

            # Should have a keyword-based description
            assert result.strategy_description != ""
            assert result.model_used == ""  # No LLM used
            mock_client.generate.assert_not_called()

    def test_narration_fallback_when_llm_fails(self) -> None:
        """Should fall back when LLM returns unsuccessful response."""
        mock_response = MagicMock()
        mock_response.success = False

        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = True
        mock_client.generate.return_value = mock_response

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "folder1").mkdir()

            analyzer = StructureAnalyzer(
                llm_client=mock_client,
                use_llm=True,
            )
            result = analyzer.analyze(root, max_depth=4, generate_narration=True)

            assert result.strategy_description != ""
            assert result.model_used == ""

    def test_narration_disabled(self) -> None:
        """Should not generate narration when disabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "folder1").mkdir()

            analyzer = StructureAnalyzer(use_llm=False)
            result = analyzer.analyze(root, max_depth=4, generate_narration=False)

            assert result.strategy_description == ""
            assert result.model_used == ""


class TestKeywordNarration:
    """Tests for keyword-based narration fallback."""

    def test_narration_with_date_structure(self) -> None:
        """Should mention date-based organization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "2020").mkdir()
            (root / "2021").mkdir()
            (root / "2022").mkdir()

            analyzer = StructureAnalyzer(use_llm=False)
            result = analyzer.analyze(root, max_depth=4)

            assert "date" in result.strategy_description.lower()

    def test_narration_with_category_structure(self) -> None:
        """Should mention number of main categories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "Documents").mkdir()
            (root / "Images").mkdir()
            (root / "Projects").mkdir()
            (root / "Archive").mkdir()

            analyzer = StructureAnalyzer(use_llm=False)
            result = analyzer.analyze(root, max_depth=4)

            # Should mention categories
            assert "categories" in result.strategy_description.lower() or \
                   "4 main" in result.strategy_description.lower()

    def test_narration_with_file_types(self) -> None:
        """Should mention dominant file types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            for i in range(5):
                (root / f"doc{i}.pdf").touch()

            analyzer = StructureAnalyzer(use_llm=False)
            result = analyzer.analyze(root, max_depth=4)

            assert ".pdf" in result.strategy_description.lower()


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_analyze_structure_function(self) -> None:
        """Should analyze and return snapshot."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "docs").mkdir()
            (root / "docs" / "file.txt").touch()

            result = analyze_structure(root, max_depth=4, use_llm=False)

            assert result.root_path == str(Path(root).resolve())
            assert result.total_folders >= 2
            assert result.total_files >= 1

    def test_analyze_structure_with_output(self) -> None:
        """Should save snapshot when output_path provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            output = Path(tmpdir) / "output.json"
            (root / "folder").mkdir()

            analyze_structure(
                root,
                max_depth=4,
                output_path=output,
                use_llm=False,
            )

            assert output.exists()
            # Verify saved content
            data = json.loads(output.read_text())
            assert data["root_path"] == str(Path(root).resolve())

    def test_load_structure_function(self) -> None:
        """Should load saved snapshot."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "structure.json"

            # Create and save snapshot
            snapshot = StructureSnapshot(
                root_path="/test/root",
                max_depth=4,
                total_folders=5,
                total_files=10,
            )
            snapshot.save(output)

            # Load it back
            loaded = load_structure(output)
            assert loaded.root_path == "/test/root"
            assert loaded.total_folders == 5
            assert loaded.total_files == 10


class TestSystemFoldersConstant:
    """Tests for SYSTEM_FOLDERS constant."""

    def test_system_folders_contains_common_folders(self) -> None:
        """Should contain common system folders."""
        assert ".git" in SYSTEM_FOLDERS
        assert "__pycache__" in SYSTEM_FOLDERS
        assert "node_modules" in SYSTEM_FOLDERS
        assert ".Trash" in SYSTEM_FOLDERS
        assert "Library" in SYSTEM_FOLDERS

    def test_default_ignore_patterns(self) -> None:
        """Should have sensible default ignore patterns."""
        assert any(".git" in p for p in DEFAULT_IGNORE_PATTERNS)
        assert any("__pycache__" in p for p in DEFAULT_IGNORE_PATTERNS)
        assert any(".*" in p for p in DEFAULT_IGNORE_PATTERNS)
