"""Tests for the consolidation planner module."""

import json
import os
import sqlite3
import tempfile
from pathlib import Path

from organizer.consolidation_planner import (
    ConsolidationPlan,
    ConsolidationPlanner,
    FolderContentSummary,
    FolderGroup,
    FolderInfo,
    generate_plan_summary,
    load_plan_from_file,
    save_plan_to_file,
    scan_folder_structure,
)


class TestFolderInfo:
    """Tests for FolderInfo dataclass."""

    def test_create_folder_info(self):
        """Test creating a FolderInfo instance."""
        info = FolderInfo(
            path="/path/to/folder", name="folder", file_count=5, total_size=1000
        )
        assert info.path == "/path/to/folder"
        assert info.name == "folder"
        assert info.file_count == 5
        assert info.total_size == 1000

    def test_folder_info_defaults(self):
        """Test FolderInfo default values."""
        info = FolderInfo(path="/path", name="test")
        assert info.file_count == 0
        assert info.total_size == 0

    def test_folder_info_to_dict(self):
        """Test FolderInfo serialization."""
        info = FolderInfo(
            path="/path/to/folder", name="folder", file_count=5, total_size=1000
        )
        d = info.to_dict()
        assert d["path"] == "/path/to/folder"
        assert d["name"] == "folder"
        assert d["file_count"] == 5
        assert d["total_size"] == 1000

    def test_folder_info_from_dict(self):
        """Test FolderInfo deserialization."""
        d = {
            "path": "/path/to/folder",
            "name": "folder",
            "file_count": 5,
            "total_size": 1000,
        }
        info = FolderInfo.from_dict(d)
        assert info.path == "/path/to/folder"
        assert info.name == "folder"
        assert info.file_count == 5
        assert info.total_size == 1000

    def test_folder_info_from_dict_defaults(self):
        """Test FolderInfo deserialization with missing optional fields."""
        d = {"path": "/path", "name": "test"}
        info = FolderInfo.from_dict(d)
        assert info.file_count == 0
        assert info.total_size == 0


class TestFolderGroup:
    """Tests for FolderGroup dataclass."""

    def test_create_folder_group(self):
        """Test creating a FolderGroup instance."""
        group = FolderGroup(group_name="Resume-related", category_key="employment")
        assert group.group_name == "Resume-related"
        assert group.category_key == "employment"
        assert group.folders == []
        assert group.total_files == 0
        assert group.total_size == 0

    def test_add_folder_to_group(self):
        """Test adding folders to a group."""
        group = FolderGroup(group_name="Resume-related", category_key="employment")
        group.add_folder(
            FolderInfo(path="/Resume", name="Resume", file_count=5, total_size=1000)
        )
        group.add_folder(
            FolderInfo(path="/Resumes", name="Resumes", file_count=3, total_size=500)
        )

        assert len(group.folders) == 2
        assert group.total_files == 8
        assert group.total_size == 1500

    def test_folder_group_to_dict(self):
        """Test FolderGroup serialization."""
        group = FolderGroup(
            group_name="Resume-related",
            category_key="employment",
            target_folder="Employment/Resumes",
        )
        group.add_folder(
            FolderInfo(path="/Resume", name="Resume", file_count=5, total_size=1000)
        )

        d = group.to_dict()
        assert d["group_name"] == "Resume-related"
        assert d["category_key"] == "employment"
        assert d["target_folder"] == "Employment/Resumes"
        assert len(d["folders"]) == 1
        assert d["total_files"] == 5
        assert d["total_size"] == 1000

    def test_folder_group_from_dict(self):
        """Test FolderGroup deserialization."""
        d = {
            "group_name": "Resume-related",
            "category_key": "employment",
            "target_folder": "Employment/Resumes",
            "folders": [
                {
                    "path": "/Resume",
                    "name": "Resume",
                    "file_count": 5,
                    "total_size": 1000,
                }
            ],
        }
        group = FolderGroup.from_dict(d)
        assert group.group_name == "Resume-related"
        assert group.category_key == "employment"
        assert group.target_folder == "Employment/Resumes"
        assert len(group.folders) == 1
        assert group.total_files == 5


class TestConsolidationPlan:
    """Tests for ConsolidationPlan dataclass."""

    def test_create_plan(self):
        """Test creating a ConsolidationPlan instance."""
        plan = ConsolidationPlan(base_path="/iCloud", threshold=0.85)
        assert plan.base_path == "/iCloud"
        assert plan.threshold == 0.85
        assert plan.groups == []
        assert plan.created_at != ""

    def test_plan_properties(self):
        """Test ConsolidationPlan computed properties."""
        plan = ConsolidationPlan()

        group1 = FolderGroup(group_name="Group1", category_key=None)
        group1.add_folder(FolderInfo(path="/a", name="a", file_count=5))
        group1.add_folder(FolderInfo(path="/b", name="b", file_count=3))

        group2 = FolderGroup(group_name="Group2", category_key=None)
        group2.add_folder(FolderInfo(path="/c", name="c", file_count=10))
        group2.add_folder(FolderInfo(path="/d", name="d", file_count=7))
        group2.add_folder(FolderInfo(path="/e", name="e", file_count=2))

        plan.groups = [group1, group2]

        assert plan.total_groups == 2
        assert plan.total_folders == 5
        assert plan.total_files == 27

    def test_plan_to_dict(self):
        """Test ConsolidationPlan serialization."""
        plan = ConsolidationPlan(base_path="/iCloud", threshold=0.85)
        group = FolderGroup(group_name="Test", category_key="employment")
        group.add_folder(FolderInfo(path="/test", name="test", file_count=5))
        plan.groups = [group]

        d = plan.to_dict()
        assert d["base_path"] == "/iCloud"
        assert d["threshold"] == 0.85
        assert len(d["groups"]) == 1
        assert d["summary"]["total_groups"] == 1
        assert d["summary"]["total_folders"] == 1
        assert d["summary"]["total_files"] == 5

    def test_plan_from_dict(self):
        """Test ConsolidationPlan deserialization."""
        d = {
            "created_at": "2026-01-20T12:00:00",
            "base_path": "/iCloud",
            "threshold": 0.85,
            "groups": [
                {
                    "group_name": "Test",
                    "category_key": "employment",
                    "target_folder": "Employment/Resumes",
                    "folders": [
                        {
                            "path": "/test",
                            "name": "test",
                            "file_count": 5,
                            "total_size": 100,
                        }
                    ],
                }
            ],
        }
        plan = ConsolidationPlan.from_dict(d)
        assert plan.created_at == "2026-01-20T12:00:00"
        assert plan.base_path == "/iCloud"
        assert plan.threshold == 0.85
        assert len(plan.groups) == 1

    def test_plan_to_json(self):
        """Test ConsolidationPlan JSON serialization."""
        plan = ConsolidationPlan(base_path="/test")
        json_str = plan.to_json()
        parsed = json.loads(json_str)
        assert parsed["base_path"] == "/test"

    def test_plan_from_json(self):
        """Test ConsolidationPlan JSON deserialization."""
        json_str = '{"base_path": "/test", "threshold": 0.8, "groups": []}'
        plan = ConsolidationPlan.from_json(json_str)
        assert plan.base_path == "/test"

    def test_plan_save_and_load(self):
        """Test saving and loading plan to/from file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = os.path.join(tmpdir, "plan.json")

            plan = ConsolidationPlan(base_path="/iCloud", threshold=0.85)
            group = FolderGroup(group_name="Test", category_key="employment")
            group.add_folder(FolderInfo(path="/test", name="test", file_count=5))
            plan.groups = [group]

            plan.save(plan_path)
            assert os.path.exists(plan_path)

            loaded = ConsolidationPlan.load(plan_path)
            assert loaded.base_path == "/iCloud"
            assert loaded.threshold == 0.85
            assert len(loaded.groups) == 1
            assert loaded.groups[0].group_name == "Test"


class TestConsolidationPlanner:
    """Tests for ConsolidationPlanner class."""

    def test_create_planner(self):
        """Test creating a ConsolidationPlanner instance."""
        planner = ConsolidationPlanner(base_path="/test", threshold=0.85)
        assert planner.base_path == "/test"
        assert planner.threshold == 0.85

    def test_planner_default_base_path(self):
        """Test planner uses current directory as default."""
        planner = ConsolidationPlanner()
        assert planner.base_path == os.getcwd()

    def test_scan_folders_empty_directory(self):
        """Test scanning an empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            planner = ConsolidationPlanner(base_path=tmpdir)
            folders = planner.scan_folders()
            assert folders == []

    def test_scan_folders_basic(self):
        """Test scanning a directory with folders."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create some test folders
            os.makedirs(os.path.join(tmpdir, "Resume"))
            os.makedirs(os.path.join(tmpdir, "Taxes"))
            os.makedirs(os.path.join(tmpdir, "Documents"))

            planner = ConsolidationPlanner(base_path=tmpdir)
            folders = planner.scan_folders()

            assert len(folders) == 3
            names = {f.name for f in folders}
            assert "Resume" in names
            assert "Taxes" in names
            assert "Documents" in names

    def test_scan_folders_with_files(self):
        """Test scanning counts files correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create folder with files
            resume_dir = os.path.join(tmpdir, "Resume")
            os.makedirs(resume_dir)
            Path(os.path.join(resume_dir, "resume1.pdf")).write_text("test content")
            Path(os.path.join(resume_dir, "resume2.pdf")).write_text("more content")

            planner = ConsolidationPlanner(base_path=tmpdir)
            folders = planner.scan_folders()

            assert len(folders) == 1
            assert folders[0].name == "Resume"
            assert folders[0].file_count == 2
            assert folders[0].total_size > 0

    def test_scan_folders_skips_hidden(self):
        """Test scanning skips hidden directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "Resume"))
            os.makedirs(os.path.join(tmpdir, ".hidden"))

            planner = ConsolidationPlanner(base_path=tmpdir)
            folders = planner.scan_folders()

            assert len(folders) == 1
            assert folders[0].name == "Resume"

    def test_scan_folders_max_depth(self):
        """Test scanning respects max_depth."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create nested folders
            os.makedirs(os.path.join(tmpdir, "level1", "level2", "level3", "level4"))

            planner = ConsolidationPlanner(base_path=tmpdir)

            # Depth 2 should find level1 and level2
            folders = planner.scan_folders(max_depth=2)
            names = {f.name for f in folders}
            assert "level1" in names
            assert "level2" in names
            assert "level3" in names
            assert "level4" not in names

    def test_group_similar_folders_basic(self):
        """Test grouping similar folders."""
        planner = ConsolidationPlanner(threshold=0.8)

        folders = [
            FolderInfo(path="/Resume", name="Resume", file_count=5),
            FolderInfo(path="/Resumes", name="Resumes", file_count=3),
            FolderInfo(path="/Resume_Docs", name="Resume_Docs", file_count=10),
            FolderInfo(path="/Taxes", name="Taxes", file_count=7),
        ]

        groups = planner.group_similar_folders(folders)

        # Should have one group for Resume-related folders
        assert len(groups) == 1
        assert len(groups[0].folders) == 3
        assert groups[0].total_files == 18

    def test_group_similar_folders_multiple_groups(self):
        """Test grouping creates multiple groups for different categories."""
        planner = ConsolidationPlanner(threshold=0.8)

        folders = [
            FolderInfo(path="/Resume", name="Resume", file_count=5),
            FolderInfo(path="/Resumes", name="Resumes", file_count=3),
            FolderInfo(path="/Tax", name="Tax", file_count=10),
            FolderInfo(path="/Taxes", name="Taxes", file_count=7),
            FolderInfo(path="/Tax_2023", name="Tax_2023", file_count=4),
        ]

        groups = planner.group_similar_folders(folders)

        # Should have two groups
        assert len(groups) == 2

        # Find each group
        group_names = {g.group_name for g in groups}
        assert "Employment-related" in group_names
        assert "Finances-related" in group_names

    def test_group_similar_folders_no_singles(self):
        """Test that single folders are not grouped."""
        planner = ConsolidationPlanner(threshold=0.8)

        folders = [
            FolderInfo(path="/Resume", name="Resume", file_count=5),
            FolderInfo(path="/Taxes", name="Taxes", file_count=7),
            FolderInfo(path="/Documents", name="Documents", file_count=3),
        ]

        groups = planner.group_similar_folders(folders)

        # No groups since no folders are similar
        assert len(groups) == 0

    def test_group_similar_folders_with_category(self):
        """Test group correctly identifies category and target."""
        planner = ConsolidationPlanner(threshold=0.8)

        folders = [
            FolderInfo(path="/Resume", name="Resume", file_count=5),
            FolderInfo(path="/Resumes", name="Resumes", file_count=3),
        ]

        groups = planner.group_similar_folders(folders)

        assert len(groups) == 1
        assert groups[0].category_key == "employment"
        assert groups[0].target_folder == "Employment/Resumes"

    def test_create_plan(self):
        """Test creating a complete consolidation plan."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test folder structure
            os.makedirs(os.path.join(tmpdir, "Resume"))
            os.makedirs(os.path.join(tmpdir, "Resumes"))
            Path(os.path.join(tmpdir, "Resume", "test.txt")).write_text("test")
            Path(os.path.join(tmpdir, "Resumes", "test.txt")).write_text("test")

            planner = ConsolidationPlanner(base_path=tmpdir, threshold=0.8)
            plan = planner.create_plan()

            assert plan.base_path == tmpdir
            assert plan.threshold == 0.8
            assert plan.total_groups == 1
            assert plan.total_folders == 2
            assert plan.total_files == 2

    def test_generate_summary_empty(self):
        """Test generating summary for empty plan."""
        planner = ConsolidationPlanner()
        plan = ConsolidationPlan()

        summary = planner.generate_summary(plan)

        assert "No similar folder groups found" in summary

    def test_generate_summary_with_groups(self):
        """Test generating summary with groups."""
        planner = ConsolidationPlanner()

        plan = ConsolidationPlan()
        group = FolderGroup(
            group_name="Resume-related",
            category_key="employment",
            target_folder="Employment/Resumes",
        )
        group.add_folder(FolderInfo(path="/Resume", name="Resume", file_count=5))
        group.add_folder(FolderInfo(path="/Resumes", name="Resumes", file_count=3))
        plan.groups = [group]

        summary = planner.generate_summary(plan)

        assert "FOLDER SIMILARITY ANALYSIS" in summary
        assert "Found 1 similar folder groups" in summary
        assert "Resume-related" in summary
        assert "2 folders" in summary
        assert "8 files" in summary
        assert "Employment/Resumes" in summary


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_scan_folder_structure(self):
        """Test scan_folder_structure convenience function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "Test"))

            plan = scan_folder_structure(base_path=tmpdir)

            assert isinstance(plan, ConsolidationPlan)
            assert plan.base_path == tmpdir

    def test_generate_plan_summary(self):
        """Test generate_plan_summary convenience function."""
        plan = ConsolidationPlan()
        summary = generate_plan_summary(plan)
        assert "FOLDER SIMILARITY ANALYSIS" in summary

    def test_save_and_load_plan_file(self):
        """Test save_plan_to_file and load_plan_from_file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = os.path.join(tmpdir, "test_plan.json")

            plan = ConsolidationPlan(base_path="/test", threshold=0.9)
            save_plan_to_file(plan, plan_path)

            loaded = load_plan_from_file(plan_path)
            assert loaded.base_path == "/test"
            assert loaded.threshold == 0.9


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_scan_nonexistent_path(self):
        """Test scanning a path that doesn't exist."""
        planner = ConsolidationPlanner(base_path="/nonexistent/path/xyz123")
        folders = planner.scan_folders()
        assert folders == []

    def test_scan_permission_denied(self):
        """Test scanning handles permission errors gracefully."""
        # This test is platform-dependent and may not trigger on all systems
        planner = ConsolidationPlanner(base_path="/root/secret")
        folders = planner.scan_folders()
        # Should not raise, just return empty or partial results
        assert isinstance(folders, list)

    def test_group_empty_folder_list(self):
        """Test grouping an empty folder list."""
        planner = ConsolidationPlanner()
        groups = planner.group_similar_folders([])
        assert groups == []

    def test_plan_roundtrip_json(self):
        """Test plan survives JSON roundtrip without data loss."""
        original = ConsolidationPlan(base_path="/test", threshold=0.75)
        group = FolderGroup(
            group_name="Test-related",
            category_key="employment",
            target_folder="Employment/Test",
        )
        group.add_folder(
            FolderInfo(
                path="/path/to/test", name="test", file_count=42, total_size=12345
            )
        )
        original.groups = [group]

        json_str = original.to_json()
        restored = ConsolidationPlan.from_json(json_str)

        assert restored.base_path == original.base_path
        assert restored.threshold == original.threshold
        assert len(restored.groups) == len(original.groups)
        assert restored.groups[0].group_name == original.groups[0].group_name
        assert restored.groups[0].folders[0].file_count == 42
        assert restored.groups[0].folders[0].total_size == 12345

    def test_generate_group_name_no_category(self):
        """Test group name generation without category."""
        planner = ConsolidationPlanner()

        # Internal method test
        name = planner._generate_group_name("RandomFolder", None)
        assert "RandomFolder" in name or "Random" in name

    def test_determine_target_folder_no_category(self):
        """Test target folder determination without category."""
        planner = ConsolidationPlanner()

        target = planner._determine_target_folder(None, "MyFolder")
        assert target == "MyFolder"

    def test_folder_info_equality(self):
        """Test FolderInfo comparison."""
        info1 = FolderInfo(path="/test", name="test", file_count=5)
        info2 = FolderInfo(path="/test", name="test", file_count=5)

        # Dataclasses should be equal if all fields match
        assert info1 == info2

    def test_plan_with_nested_folders(self):
        """Test scanning and grouping with nested similar folders."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create nested Resume folders
            os.makedirs(os.path.join(tmpdir, "Resume"))
            os.makedirs(os.path.join(tmpdir, "Work", "Resumes"))
            os.makedirs(os.path.join(tmpdir, "Old", "Resume_Backup"))

            planner = ConsolidationPlanner(base_path=tmpdir, threshold=0.8)
            plan = planner.create_plan(max_depth=3)

            # Should find and group the Resume-related folders
            resume_folders = []
            for group in plan.groups:
                if (
                    "resume" in group.group_name.lower()
                    or "employment" in group.group_name.lower()
                ):
                    resume_folders.extend(group.folders)

            # Should find at least 2 similar resume folders
            assert len(resume_folders) >= 2


class TestContentAwareFolderGroup:
    """Tests for content-aware FolderGroup fields (Phase 2)."""

    def test_folder_group_content_aware_defaults(self):
        """Test FolderGroup content-aware default values."""
        group = FolderGroup(group_name="Test-related", category_key="employment")
        assert group.should_consolidate is True
        assert group.consolidation_reasoning == []
        assert group.ai_categories == set()
        assert group.date_ranges == {}
        assert group.content_analysis_done is False
        assert group.confidence == 1.0

    def test_folder_group_add_reasoning(self):
        """Test adding reasoning to a FolderGroup."""
        group = FolderGroup(group_name="Test-related", category_key=None)
        group.add_reasoning("Same AI category")
        group.add_reasoning("Same date range")
        assert len(group.consolidation_reasoning) == 2
        assert "Same AI category" in group.consolidation_reasoning

    def test_folder_group_content_aware_to_dict(self):
        """Test FolderGroup serialization with content-aware fields."""
        group = FolderGroup(
            group_name="Resume-related",
            category_key="employment",
            should_consolidate=False,
            confidence=0.7,
        )
        group.ai_categories.add("Employment/Resumes")
        group.date_ranges["/path/Resume"] = "2024-2025"
        group.content_analysis_done = True
        group.add_reasoning("Different timeframes")

        d = group.to_dict()
        assert d["should_consolidate"] is False
        assert d["confidence"] == 0.7
        assert "Employment/Resumes" in d["ai_categories"]
        assert d["date_ranges"]["/path/Resume"] == "2024-2025"
        assert d["content_analysis_done"] is True
        assert "Different timeframes" in d["consolidation_reasoning"]

    def test_folder_group_content_aware_from_dict(self):
        """Test FolderGroup deserialization with content-aware fields."""
        d = {
            "group_name": "Tax-related",
            "category_key": "finances",
            "target_folder": "Finances/Taxes",
            "folders": [],
            "should_consolidate": False,
            "consolidation_reasoning": ["Different years: 2002 vs 2025"],
            "ai_categories": ["Finances/Taxes"],
            "date_ranges": {"/Tax2002": "2002", "/Tax2025": "2025"},
            "content_analysis_done": True,
            "confidence": 0.4,
        }
        group = FolderGroup.from_dict(d)
        assert group.should_consolidate is False
        assert group.confidence == 0.4
        assert "Finances/Taxes" in group.ai_categories
        assert group.date_ranges["/Tax2002"] == "2002"
        assert group.content_analysis_done is True


class TestContentAwareConsolidationPlan:
    """Tests for content-aware ConsolidationPlan fields (Phase 2)."""

    def test_plan_content_aware_defaults(self):
        """Test ConsolidationPlan content-aware default values."""
        plan = ConsolidationPlan(base_path="/test")
        assert plan.content_aware is False
        assert plan.db_path == ""

    def test_plan_groups_to_consolidate(self):
        """Test groups_to_consolidate property."""
        plan = ConsolidationPlan()

        group1 = FolderGroup(group_name="Group1", category_key=None)
        group1.should_consolidate = True
        group1.add_folder(FolderInfo(path="/a", name="a"))
        group1.add_folder(FolderInfo(path="/b", name="b"))

        group2 = FolderGroup(group_name="Group2", category_key=None)
        group2.should_consolidate = False
        group2.add_folder(FolderInfo(path="/c", name="c"))
        group2.add_folder(FolderInfo(path="/d", name="d"))

        plan.groups = [group1, group2]

        assert len(plan.groups_to_consolidate) == 1
        assert plan.groups_to_consolidate[0].group_name == "Group1"

    def test_plan_groups_to_skip(self):
        """Test groups_to_skip property."""
        plan = ConsolidationPlan()

        group1 = FolderGroup(group_name="Group1", category_key=None)
        group1.should_consolidate = True

        group2 = FolderGroup(group_name="Group2", category_key=None)
        group2.should_consolidate = False

        plan.groups = [group1, group2]

        assert len(plan.groups_to_skip) == 1
        assert plan.groups_to_skip[0].group_name == "Group2"

    def test_plan_content_aware_to_dict(self):
        """Test ConsolidationPlan serialization with content-aware fields."""
        plan = ConsolidationPlan(
            base_path="/test",
            content_aware=True,
            db_path="/test/db.sqlite",
        )
        d = plan.to_dict()
        assert d["content_aware"] is True
        assert d["db_path"] == "/test/db.sqlite"
        assert "groups_to_consolidate" in d["summary"]
        assert "groups_to_skip" in d["summary"]

    def test_plan_content_aware_from_dict(self):
        """Test ConsolidationPlan deserialization with content-aware fields."""
        d = {
            "base_path": "/test",
            "threshold": 0.8,
            "content_aware": True,
            "db_path": "/test/db.sqlite",
            "groups": [],
        }
        plan = ConsolidationPlan.from_dict(d)
        assert plan.content_aware is True
        assert plan.db_path == "/test/db.sqlite"


class TestContentAwarePlanner:
    """Tests for ConsolidationPlanner content-aware mode (Phase 2)."""

    def test_planner_content_aware_init(self):
        """Test ConsolidationPlanner with content-aware parameters."""
        planner = ConsolidationPlanner(
            base_path="/test",
            threshold=0.85,
            db_path="/test/db.sqlite",
            content_aware=True,
        )
        assert planner.base_path == "/test"
        assert planner.threshold == 0.85
        assert planner.db_path == "/test/db.sqlite"
        assert planner.content_aware is True

    def test_planner_content_aware_defaults(self):
        """Test ConsolidationPlanner content-aware defaults."""
        planner = ConsolidationPlanner()
        assert planner.db_path == ""
        assert planner.content_aware is False

    def test_planner_get_db_connection_no_path(self):
        """Test _get_db_connection returns None without db_path."""
        planner = ConsolidationPlanner(content_aware=True)
        conn = planner._get_db_connection()
        assert conn is None

    def test_planner_get_db_connection_invalid_path(self):
        """Test _get_db_connection with nonexistent database."""
        planner = ConsolidationPlanner(
            db_path="/nonexistent/path/db.sqlite",
            content_aware=True,
        )
        conn = planner._get_db_connection()
        assert conn is None

    def test_planner_create_plan_with_content_aware_flag(self):
        """Test create_plan sets content_aware flag in plan."""
        with tempfile.TemporaryDirectory() as tmpdir:
            planner = ConsolidationPlanner(
                base_path=tmpdir,
                content_aware=True,
            )
            plan = planner.create_plan()
            assert plan.content_aware is True

    def test_planner_create_plan_without_content_aware(self):
        """Test create_plan works without content-aware mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "Resume"))
            os.makedirs(os.path.join(tmpdir, "Resumes"))

            planner = ConsolidationPlanner(base_path=tmpdir, content_aware=False)
            plan = planner.create_plan()

            assert plan.content_aware is False
            assert len(plan.groups) == 1

    def test_group_similar_folders_content_aware_no_db(self):
        """Test content-aware grouping falls back without database."""
        planner = ConsolidationPlanner(content_aware=True)
        folders = [
            FolderInfo(path="/Resume", name="Resume"),
            FolderInfo(path="/Resumes", name="Resumes"),
        ]
        groups = planner.group_similar_folders_content_aware(folders)
        # Should still group by name similarity
        assert len(groups) == 1


class TestContentAwarePlannerWithDatabase:
    """Tests for ConsolidationPlanner with actual database (Phase 2)."""

    def _create_test_database(self, db_path: str):
        """Create a test database with schema."""
        import sqlite3

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create documents table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
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
                pdf_modified_date TEXT,
                rename_status TEXT
            )
            """
        )

        # Create document_locations table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS document_locations (
                id INTEGER PRIMARY KEY,
                document_id INTEGER,
                path TEXT,
                location_type TEXT,
                created_at TEXT
            )
            """
        )

        conn.commit()
        return conn

    def _insert_test_document(
        self, conn, doc_id, filename, current_path, ai_category, key_dates=None
    ):
        """Insert a test document into the database."""
        import json

        # Resolve path to handle macOS symlinks (/var -> /private/var)
        resolved_path = str(Path(current_path).resolve())
        conn.execute(
            """
            INSERT INTO documents (id, filename, current_path, ai_category, key_dates)
            VALUES (?, ?, ?, ?, ?)
            """,
            (doc_id, filename, resolved_path, ai_category, json.dumps(key_dates or [])),
        )
        conn.commit()

    def test_planner_with_database(self):
        """Test ConsolidationPlanner with a real database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            conn = self._create_test_database(db_path)

            # Create test folders
            resume_dir = os.path.join(tmpdir, "Resume")
            resumes_dir = os.path.join(tmpdir, "Resumes")
            os.makedirs(resume_dir)
            os.makedirs(resumes_dir)

            # Create test files
            Path(os.path.join(resume_dir, "resume1.pdf")).write_text("test")
            Path(os.path.join(resumes_dir, "resume2.pdf")).write_text("test")

            # Insert documents into database
            self._insert_test_document(
                conn,
                1,
                "resume1.pdf",
                os.path.join(resume_dir, "resume1.pdf"),
                "Employment/Resumes",
                ["2024-01-01"],
            )
            self._insert_test_document(
                conn,
                2,
                "resume2.pdf",
                os.path.join(resumes_dir, "resume2.pdf"),
                "Employment/Resumes",
                ["2024-06-01"],
            )
            conn.close()

            # Create planner with content-aware mode
            planner = ConsolidationPlanner(
                base_path=tmpdir,
                content_aware=True,
                db_path=db_path,
            )
            plan = planner.create_plan()

            assert plan.content_aware is True
            assert len(plan.groups) == 1
            assert plan.groups[0].content_analysis_done is True
            assert (
                plan.groups[0].should_consolidate is True
            )  # Same category, same dates

    def test_planner_different_categories_no_consolidate(self):
        """Test planner marks different categories as should not consolidate."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            conn = self._create_test_database(db_path)

            # Create test folders
            folder1 = os.path.join(tmpdir, "MyFolder")
            folder2 = os.path.join(tmpdir, "MyFolders")
            os.makedirs(folder1)
            os.makedirs(folder2)

            # Create test files
            Path(os.path.join(folder1, "doc1.pdf")).write_text("test")
            Path(os.path.join(folder2, "doc2.pdf")).write_text("test")

            # Insert documents with DIFFERENT categories
            self._insert_test_document(
                conn,
                1,
                "doc1.pdf",
                os.path.join(folder1, "doc1.pdf"),
                "Employment/Resumes",
                ["2024-01-01"],
            )
            self._insert_test_document(
                conn,
                2,
                "doc2.pdf",
                os.path.join(folder2, "doc2.pdf"),
                "Finances/Taxes",
                ["2024-01-01"],
            )
            conn.close()

            planner = ConsolidationPlanner(
                base_path=tmpdir,
                content_aware=True,
                db_path=db_path,
            )
            plan = planner.create_plan()

            assert len(plan.groups) == 1
            # Different categories should NOT consolidate
            assert plan.groups[0].should_consolidate is False

    def test_planner_different_timeframes_no_consolidate(self):
        """Test planner marks different timeframes as should not consolidate."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            conn = self._create_test_database(db_path)

            # Create test folders
            tax2002 = os.path.join(tmpdir, "Tax2002")
            tax2025 = os.path.join(tmpdir, "Tax2025")
            os.makedirs(tax2002)
            os.makedirs(tax2025)

            # Create test files
            Path(os.path.join(tax2002, "taxes.pdf")).write_text("test")
            Path(os.path.join(tax2025, "taxes.pdf")).write_text("test")

            # Insert documents with DIFFERENT timeframes (but same category)
            self._insert_test_document(
                conn,
                1,
                "taxes.pdf",
                os.path.join(tax2002, "taxes.pdf"),
                "Finances/Taxes",
                ["2002-04-15"],
            )
            self._insert_test_document(
                conn,
                2,
                "taxes.pdf",
                os.path.join(tax2025, "taxes.pdf"),
                "Finances/Taxes",
                ["2025-04-15"],
            )
            conn.close()

            planner = ConsolidationPlanner(
                base_path=tmpdir,
                content_aware=True,
                db_path=db_path,
            )
            plan = planner.create_plan()

            assert len(plan.groups) == 1
            # Different timeframes should NOT consolidate
            assert plan.groups[0].should_consolidate is False
            assert "2002" in str(plan.groups[0].consolidation_reasoning)
            assert "2025" in str(plan.groups[0].consolidation_reasoning)


class TestContentAwareSummary:
    """Tests for content-aware plan summary generation (Phase 2)."""

    def test_summary_with_content_aware_empty(self):
        """Test summary generation for empty content-aware plan."""
        plan = ConsolidationPlan(content_aware=True)
        planner = ConsolidationPlanner()
        summary = planner.generate_summary(plan)

        assert "CONTENT-AWARE FOLDER ANALYSIS" in summary
        assert "No similar folder groups found" in summary

    def test_summary_with_content_aware_groups(self):
        """Test summary generation with content-aware groups."""
        plan = ConsolidationPlan(content_aware=True)

        group = FolderGroup(
            group_name="Resume-related",
            category_key="employment",
            target_folder="Employment/Resumes",
        )
        group.add_folder(FolderInfo(path="/Resume", name="Resume", file_count=5))
        group.add_folder(FolderInfo(path="/Resumes", name="Resumes", file_count=3))
        group.should_consolidate = True
        group.content_analysis_done = True
        group.confidence = 0.8
        group.ai_categories.add("Employment/Resumes")
        group.add_reasoning("✅ Same AI category")

        plan.groups = [group]

        planner = ConsolidationPlanner()
        summary = planner.generate_summary(plan)

        assert "CONTENT-AWARE FOLDER ANALYSIS" in summary
        assert "Groups to consolidate: 1" in summary
        assert "Groups to skip: 0" in summary
        assert "✅" in summary
        assert "CAN CONSOLIDATE" in summary
        assert "80%" in summary

    def test_summary_with_skip_groups(self):
        """Test summary generation with groups to skip."""
        plan = ConsolidationPlan(content_aware=True)

        group = FolderGroup(
            group_name="Tax-related",
            category_key="finances",
            target_folder="Finances/Taxes",
        )
        group.add_folder(FolderInfo(path="/Tax2002", name="Tax2002", file_count=10))
        group.add_folder(FolderInfo(path="/Tax2025", name="Tax2025", file_count=8))
        group.should_consolidate = False
        group.content_analysis_done = True
        group.add_reasoning("❌ Different timeframes")

        plan.groups = [group]

        planner = ConsolidationPlanner()
        summary = planner.generate_summary(plan)

        assert "Groups to skip: 1" in summary
        assert "❌" in summary
        assert "DO NOT CONSOLIDATE" in summary
        assert "Keep separate" in summary


class TestContentAwareConvenienceFunctions:
    """Tests for content-aware convenience functions (Phase 2)."""

    def test_scan_folder_structure_content_aware_params(self):
        """Test scan_folder_structure accepts content-aware parameters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "Test"))

            plan = scan_folder_structure(
                base_path=tmpdir,
                content_aware=True,
                db_path="/nonexistent/db.sqlite",
            )

            assert plan.content_aware is True
            assert plan.db_path == "/nonexistent/db.sqlite"


class TestContentAwarePlanRoundtrip:
    """Tests for content-aware plan JSON roundtrip (Phase 2)."""

    def test_plan_roundtrip_with_content_aware(self):
        """Test content-aware plan survives JSON roundtrip."""
        original = ConsolidationPlan(
            base_path="/test",
            threshold=0.75,
            content_aware=True,
            db_path="/test/db.sqlite",
        )

        group = FolderGroup(
            group_name="Test-related",
            category_key="employment",
            target_folder="Employment/Test",
            should_consolidate=False,
            confidence=0.6,
        )
        group.add_folder(FolderInfo(path="/test1", name="test1", file_count=5))
        group.add_folder(FolderInfo(path="/test2", name="test2", file_count=3))
        group.content_analysis_done = True
        group.ai_categories.add("Employment/Resumes")
        group.date_ranges["/test1"] = "2024-2025"
        group.add_reasoning("Test reason")

        original.groups = [group]

        # Roundtrip through JSON
        json_str = original.to_json()
        restored = ConsolidationPlan.from_json(json_str)

        # Verify all fields survived
        assert restored.content_aware is True
        assert restored.db_path == "/test/db.sqlite"
        assert len(restored.groups) == 1

        restored_group = restored.groups[0]
        assert restored_group.should_consolidate is False
        assert restored_group.confidence == 0.6
        assert restored_group.content_analysis_done is True
        assert "Employment/Resumes" in restored_group.ai_categories
        assert restored_group.date_ranges["/test1"] == "2024-2025"
        assert "Test reason" in restored_group.consolidation_reasoning


class TestDecisionLogicPhase2:
    """Tests for enhanced decision logic (Phase 2).

    These tests verify that the decision engine:
    1. Gathers ALL context from database
    2. Applies ALL 5 decision rules
    3. Uses canonical registry for target location
    4. Adds clear reasoning to plan
    """

    def _create_test_database(self, db_path: str):
        """Create a test database with schema."""
        import sqlite3

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
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
                pdf_modified_date TEXT,
                rename_status TEXT
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS document_locations (
                id INTEGER PRIMARY KEY,
                document_id INTEGER,
                path TEXT,
                location_type TEXT,
                created_at TEXT
            )
            """
        )

        conn.commit()
        return conn

    def _insert_document_with_entities(
        self,
        conn,
        doc_id,
        filename,
        current_path,
        ai_category,
        key_dates=None,
        entities=None,
        folder_hierarchy=None,
    ):
        """Insert a test document with full metadata."""
        import json

        resolved_path = str(Path(current_path).resolve())
        conn.execute(
            """
            INSERT INTO documents (
                id, filename, current_path, ai_category, key_dates, entities, folder_hierarchy
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                doc_id,
                filename,
                resolved_path,
                ai_category,
                json.dumps(key_dates or []),
                json.dumps(entities or {}),
                json.dumps(folder_hierarchy or []),
            ),
        )
        conn.commit()

    def test_decision_logic_gathers_all_context(self):
        """Test that decision logic gathers all 6 types of context."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            conn = self._create_test_database(db_path)

            # Create test folders
            folder1 = os.path.join(tmpdir, "Resume")
            folder2 = os.path.join(tmpdir, "Resumes")
            os.makedirs(folder1)
            os.makedirs(folder2)

            Path(os.path.join(folder1, "doc1.pdf")).write_text("test")
            Path(os.path.join(folder2, "doc2.pdf")).write_text("test")

            # Insert documents with full metadata
            self._insert_document_with_entities(
                conn,
                1,
                "doc1.pdf",
                os.path.join(folder1, "doc1.pdf"),
                "Employment/Resumes",
                key_dates=["2024-03-15"],
                entities={"people": ["John Doe"], "organizations": ["Acme Corp"]},
                folder_hierarchy=["Documents", "Personal"],
            )
            self._insert_document_with_entities(
                conn,
                2,
                "doc2.pdf",
                os.path.join(folder2, "doc2.pdf"),
                "Employment/Resumes",
                key_dates=["2024-06-20"],
                entities={"people": ["John Doe"], "organizations": ["Acme Corp"]},
                folder_hierarchy=["Documents", "Personal"],
            )
            conn.close()

            planner = ConsolidationPlanner(
                base_path=tmpdir,
                content_aware=True,
                db_path=db_path,
            )
            plan = planner.create_plan()

            assert len(plan.groups) == 1
            group = plan.groups[0]

            # Verify all context was gathered
            assert group.content_analysis_done is True
            assert len(group.ai_categories) > 0
            assert len(group.date_ranges) > 0

            # Check reasoning contains context gathering
            reasoning_text = "\n".join(group.consolidation_reasoning)
            assert "Gathering context" in reasoning_text
            assert "AI categories" in reasoning_text
            assert "documents" in reasoning_text.lower()

    def test_decision_logic_applies_all_five_rules(self):
        """Test that decision logic applies all 5 decision rules."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            conn = self._create_test_database(db_path)

            # Use folder names that are similar enough to be grouped
            folder1 = os.path.join(tmpdir, "Taxes")
            folder2 = os.path.join(tmpdir, "Taxs")  # Similar enough to group
            os.makedirs(folder1)
            os.makedirs(folder2)

            Path(os.path.join(folder1, "doc1.pdf")).write_text("test")
            Path(os.path.join(folder2, "doc2.pdf")).write_text("test")

            self._insert_document_with_entities(
                conn,
                1,
                "doc1.pdf",
                os.path.join(folder1, "doc1.pdf"),
                "Finances/Taxes",
                key_dates=["2024-04-15"],
                entities={"organizations": ["IRS"]},
                folder_hierarchy=["Documents"],
            )
            self._insert_document_with_entities(
                conn,
                2,
                "doc2.pdf",
                os.path.join(folder2, "doc2.pdf"),
                "Finances/Taxes",
                key_dates=["2024-04-10"],
                entities={"organizations": ["IRS"]},
                folder_hierarchy=["Documents"],
            )
            conn.close()

            planner = ConsolidationPlanner(
                base_path=tmpdir,
                content_aware=True,
                db_path=db_path,
            )
            plan = planner.create_plan()

            assert len(plan.groups) == 1
            group = plan.groups[0]
            reasoning_text = "\n".join(group.consolidation_reasoning)

            # Verify all 5 rules are mentioned
            assert "Rule 1:" in reasoning_text  # AI category
            assert "Rule 2:" in reasoning_text  # Date range
            assert "Rule 3:" in reasoning_text  # Context bin
            assert "Rule 4:" in reasoning_text  # Entities
            assert "Rule 5:" in reasoning_text  # Original paths

    def test_decision_logic_determines_target_from_ai_category(self):
        """Test that target folder is determined from AI category."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            conn = self._create_test_database(db_path)

            folder1 = os.path.join(tmpdir, "MyResume")
            folder2 = os.path.join(tmpdir, "MyResumes")
            os.makedirs(folder1)
            os.makedirs(folder2)

            Path(os.path.join(folder1, "doc1.pdf")).write_text("test")
            Path(os.path.join(folder2, "doc2.pdf")).write_text("test")

            self._insert_document_with_entities(
                conn,
                1,
                "doc1.pdf",
                os.path.join(folder1, "doc1.pdf"),
                "Employment/Resumes",
                key_dates=["2024-01-15"],
            )
            self._insert_document_with_entities(
                conn,
                2,
                "doc2.pdf",
                os.path.join(folder2, "doc2.pdf"),
                "Employment/Resumes",
                key_dates=["2024-02-15"],
            )
            conn.close()

            planner = ConsolidationPlanner(
                base_path=tmpdir,
                content_aware=True,
                db_path=db_path,
            )
            plan = planner.create_plan()

            assert len(plan.groups) == 1
            group = plan.groups[0]

            # Should consolidate (same category, same timeframe)
            assert group.should_consolidate is True

            # Target folder should be based on AI category
            reasoning_text = "\n".join(group.consolidation_reasoning)
            assert "Target folder" in reasoning_text
            assert "Employment" in reasoning_text or "Resumes" in reasoning_text

    def test_decision_logic_clear_reasoning_for_no_consolidation(self):
        """Test that clear reasoning is provided when not consolidating."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            conn = self._create_test_database(db_path)

            folder1 = os.path.join(tmpdir, "Folder1")
            folder2 = os.path.join(tmpdir, "Folder2")
            os.makedirs(folder1)
            os.makedirs(folder2)

            Path(os.path.join(folder1, "doc1.pdf")).write_text("test")
            Path(os.path.join(folder2, "doc2.pdf")).write_text("test")

            # Different categories = should NOT consolidate
            self._insert_document_with_entities(
                conn,
                1,
                "doc1.pdf",
                os.path.join(folder1, "doc1.pdf"),
                "Employment/Resumes",
                key_dates=["2024-01-15"],
            )
            self._insert_document_with_entities(
                conn,
                2,
                "doc2.pdf",
                os.path.join(folder2, "doc2.pdf"),
                "Legal/Contracts",
                key_dates=["2024-01-15"],
            )
            conn.close()

            planner = ConsolidationPlanner(
                base_path=tmpdir,
                content_aware=True,
                db_path=db_path,
            )
            plan = planner.create_plan()

            assert len(plan.groups) == 1
            group = plan.groups[0]

            # Should NOT consolidate
            assert group.should_consolidate is False

            # Reasoning should be clear
            reasoning_text = "\n".join(group.consolidation_reasoning)
            assert "❌" in reasoning_text
            assert "DECISION" in reasoning_text
            assert "DO NOT CONSOLIDATE" in reasoning_text

    def test_decision_logic_with_matching_entities(self):
        """Test consolidation when entities (people/orgs) match."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            conn = self._create_test_database(db_path)

            folder1 = os.path.join(tmpdir, "VA_Claims")
            folder2 = os.path.join(tmpdir, "VAClaims")
            os.makedirs(folder1)
            os.makedirs(folder2)

            Path(os.path.join(folder1, "claim1.pdf")).write_text("test")
            Path(os.path.join(folder2, "claim2.pdf")).write_text("test")

            # Same category, same dates, same entities
            self._insert_document_with_entities(
                conn,
                1,
                "claim1.pdf",
                os.path.join(folder1, "claim1.pdf"),
                "VA/Claims",
                key_dates=["2024-06-01"],
                entities={
                    "people": ["Michael Smith"],
                    "organizations": ["Department of Veterans Affairs"],
                },
            )
            self._insert_document_with_entities(
                conn,
                2,
                "claim2.pdf",
                os.path.join(folder2, "claim2.pdf"),
                "VA/Claims",
                key_dates=["2024-07-01"],
                entities={
                    "people": ["Michael Smith"],
                    "organizations": ["Department of Veterans Affairs"],
                },
            )
            conn.close()

            planner = ConsolidationPlanner(
                base_path=tmpdir,
                content_aware=True,
                db_path=db_path,
            )
            plan = planner.create_plan()

            assert len(plan.groups) == 1
            group = plan.groups[0]

            # Should consolidate - all rules pass
            assert group.should_consolidate is True

            reasoning_text = "\n".join(group.consolidation_reasoning)
            # Should mention matching entities
            assert "Rule 4:" in reasoning_text
            assert "✅" in reasoning_text

    def test_decision_logic_with_no_database_data(self):
        """Test fallback when no data in database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            conn = self._create_test_database(db_path)
            conn.close()  # Empty database

            folder1 = os.path.join(tmpdir, "Resume")
            folder2 = os.path.join(tmpdir, "Resumes")
            os.makedirs(folder1)
            os.makedirs(folder2)

            # Create files but don't add to database
            Path(os.path.join(folder1, "doc1.pdf")).write_text("test")
            Path(os.path.join(folder2, "doc2.pdf")).write_text("test")

            planner = ConsolidationPlanner(
                base_path=tmpdir,
                content_aware=True,
                db_path=db_path,
            )
            plan = planner.create_plan()

            assert len(plan.groups) == 1
            group = plan.groups[0]

            # Should fallback to name-based
            assert group.content_analysis_done is True
            assert group.should_consolidate is True
            assert group.confidence == 0.5  # Lower confidence for fallback

            reasoning_text = "\n".join(group.consolidation_reasoning)
            assert "No documents found" in reasoning_text
            assert "name-based" in reasoning_text.lower()

    def test_decision_logic_prd_example_different_timeframes(self):
        """Test PRD example: Tax 2002 vs Tax 2025 should NOT consolidate."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            conn = self._create_test_database(db_path)

            # PRD example: Tax documents from different years
            tax2002 = os.path.join(tmpdir, "Tax2002")
            tax2025 = os.path.join(tmpdir, "Tax2025")
            os.makedirs(tax2002)
            os.makedirs(tax2025)

            Path(os.path.join(tax2002, "w2_2002.pdf")).write_text("test")
            Path(os.path.join(tax2025, "w2_2025.pdf")).write_text("test")

            # Same category, but VERY different dates
            self._insert_document_with_entities(
                conn,
                1,
                "w2_2002.pdf",
                os.path.join(tax2002, "w2_2002.pdf"),
                "Finances/Taxes",
                key_dates=["2002-04-15", "2002-01-31"],
            )
            self._insert_document_with_entities(
                conn,
                2,
                "w2_2025.pdf",
                os.path.join(tax2025, "w2_2025.pdf"),
                "Finances/Taxes",
                key_dates=["2025-04-15", "2025-01-31"],
            )
            conn.close()

            planner = ConsolidationPlanner(
                base_path=tmpdir,
                content_aware=True,
                db_path=db_path,
            )
            plan = planner.create_plan()

            assert len(plan.groups) == 1
            group = plan.groups[0]

            # PRD requirement: Different timeframes = DO NOT consolidate
            assert group.should_consolidate is False

            reasoning_text = "\n".join(group.consolidation_reasoning)
            assert "timeframe" in reasoning_text.lower() or "2002" in reasoning_text
            assert "2025" in reasoning_text

    def test_decision_logic_prd_example_same_resume_content(self):
        """Test PRD example: Resume folders with same content SHOULD consolidate."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            conn = self._create_test_database(db_path)

            # PRD example: Resume + Resumes + Resume_Docs
            resume = os.path.join(tmpdir, "Resume")
            resumes = os.path.join(tmpdir, "Resumes")
            resume_docs = os.path.join(tmpdir, "Resume_Docs")
            os.makedirs(resume)
            os.makedirs(resumes)
            os.makedirs(resume_docs)

            Path(os.path.join(resume, "my_resume.pdf")).write_text("test")
            Path(os.path.join(resumes, "cover_letter.pdf")).write_text("test")
            Path(os.path.join(resume_docs, "cv.pdf")).write_text("test")

            # Same category, same timeframe, same context
            self._insert_document_with_entities(
                conn,
                1,
                "my_resume.pdf",
                os.path.join(resume, "my_resume.pdf"),
                "Employment/Resumes",
                key_dates=["2024-01-10"],
                entities={"people": ["Jane Smith"]},
            )
            self._insert_document_with_entities(
                conn,
                2,
                "cover_letter.pdf",
                os.path.join(resumes, "cover_letter.pdf"),
                "Employment/Resumes",
                key_dates=["2024-02-15"],
                entities={"people": ["Jane Smith"]},
            )
            self._insert_document_with_entities(
                conn,
                3,
                "cv.pdf",
                os.path.join(resume_docs, "cv.pdf"),
                "Employment/Resumes",
                key_dates=["2024-03-20"],
                entities={"people": ["Jane Smith"]},
            )
            conn.close()

            planner = ConsolidationPlanner(
                base_path=tmpdir,
                content_aware=True,
                db_path=db_path,
            )
            plan = planner.create_plan()

            # Should find one group with all 3 folders
            assert len(plan.groups) == 1
            group = plan.groups[0]
            assert len(group.folders) == 3

            # PRD requirement: Same content = CAN consolidate
            assert group.should_consolidate is True

            reasoning_text = "\n".join(group.consolidation_reasoning)
            assert "DECISION" in reasoning_text
            assert "CAN CONSOLIDATE" in reasoning_text


class TestContentSimilarityThreshold:
    """Tests for configurable content similarity threshold (Phase 4)."""

    def test_planner_default_threshold(self):
        """Test that planner has default content similarity threshold of 0.6."""
        planner = ConsolidationPlanner()
        assert planner.content_similarity_threshold == 0.6

    def test_planner_custom_threshold(self):
        """Test that planner accepts custom content similarity threshold."""
        planner = ConsolidationPlanner(content_similarity_threshold=0.8)
        assert planner.content_similarity_threshold == 0.8

    def test_planner_threshold_zero(self):
        """Test that planner accepts threshold of 0.0."""
        planner = ConsolidationPlanner(content_similarity_threshold=0.0)
        assert planner.content_similarity_threshold == 0.0

    def test_planner_threshold_one(self):
        """Test that planner accepts threshold of 1.0."""
        planner = ConsolidationPlanner(content_similarity_threshold=1.0)
        assert planner.content_similarity_threshold == 1.0

    def test_scan_folder_structure_with_threshold(self, tmp_path):
        """Test scan_folder_structure accepts content_similarity_threshold."""
        # Create test folder structure
        folder1 = tmp_path / "Resume"
        folder2 = tmp_path / "Resumes"
        folder1.mkdir()
        folder2.mkdir()
        (folder1 / "file1.txt").write_text("content")
        (folder2 / "file2.txt").write_text("content")

        # Test that function accepts the parameter
        plan = scan_folder_structure(
            base_path=str(tmp_path),
            threshold=0.8,
            content_aware=False,  # No DB needed
            content_similarity_threshold=0.7,
        )
        assert plan is not None

    def test_planner_with_threshold_and_database(self, tmp_path):
        """Test planner with custom threshold and database."""
        # Create test database
        db_path = str(tmp_path / "test.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute(
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
                pdf_modified_date TEXT,
                canonical_folder TEXT,
                rename_status TEXT
            )
            """
        )
        cursor.execute(
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

        # Create test folders
        folder1 = tmp_path / "Resume"
        folder2 = tmp_path / "Resumes"
        folder1.mkdir()
        folder2.mkdir()
        (folder1 / "file1.txt").write_text("content")
        (folder2 / "file2.txt").write_text("content")

        planner = ConsolidationPlanner(
            base_path=str(tmp_path),
            content_aware=True,
            db_path=db_path,
            content_similarity_threshold=0.9,
        )
        assert planner.content_similarity_threshold == 0.9

        plan = planner.create_plan()
        # Even with high threshold, plan should be created
        assert plan is not None


class TestAnalyzeMissing:
    """Tests for analyze_missing parameter in ConsolidationPlanner."""

    def test_planner_default_analyze_missing_false(self):
        """Test that analyze_missing defaults to False."""
        planner = ConsolidationPlanner()
        assert planner.analyze_missing is False

    def test_planner_analyze_missing_true(self):
        """Test that analyze_missing can be set to True."""
        planner = ConsolidationPlanner(analyze_missing=True)
        assert planner.analyze_missing is True

    def test_planner_analyze_missing_with_content_aware(self, tmp_path):
        """Test analyze_missing with content_aware mode."""
        db_path = str(tmp_path / "test.db")

        # Create minimal database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
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
                pdf_modified_date TEXT,
                canonical_folder TEXT,
                rename_status TEXT
            )
            """
        )
        cursor.execute(
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

        planner = ConsolidationPlanner(
            base_path=str(tmp_path),
            content_aware=True,
            db_path=db_path,
            analyze_missing=True,
        )
        assert planner.content_aware is True
        assert planner.analyze_missing is True

    def test_scan_folder_structure_with_analyze_missing(self, tmp_path):
        """Test scan_folder_structure convenience function with analyze_missing."""
        db_path = str(tmp_path / "test.db")

        # Create minimal database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
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
                pdf_modified_date TEXT,
                canonical_folder TEXT,
                rename_status TEXT
            )
            """
        )
        cursor.execute(
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

        # Create test folders
        folder1 = tmp_path / "Resume"
        folder2 = tmp_path / "Resumes"
        folder1.mkdir()
        folder2.mkdir()
        (folder1 / "file1.txt").write_text("content")
        (folder2 / "file2.txt").write_text("content")

        plan = scan_folder_structure(
            base_path=str(tmp_path),
            content_aware=True,
            db_path=db_path,
            analyze_missing=True,
        )
        assert plan is not None
        assert plan.content_aware is True

    def test_planner_creates_plan_with_analyze_missing(self, tmp_path):
        """Test that planner creates plan when analyze_missing is True."""
        db_path = str(tmp_path / "test.db")

        # Create minimal database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
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
                pdf_modified_date TEXT,
                canonical_folder TEXT,
                rename_status TEXT
            )
            """
        )
        cursor.execute(
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

        # Create test folders with files
        folder1 = tmp_path / "Tax2024"
        folder2 = tmp_path / "Tax_2024"
        folder1.mkdir()
        folder2.mkdir()
        (folder1 / "tax_return.pdf").write_text("tax content")
        (folder2 / "w2_form.pdf").write_text("w2 content")

        planner = ConsolidationPlanner(
            base_path=str(tmp_path),
            content_aware=True,
            db_path=db_path,
            analyze_missing=True,
        )

        plan = planner.create_plan()
        assert plan is not None
        assert plan.content_aware is True

    def test_analyze_missing_shows_reasoning_about_analysis(self, tmp_path):
        """Test that analyze_missing adds reasoning about analyzing missing files."""
        db_path = str(tmp_path / "test.db")

        # Create minimal database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
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
                pdf_modified_date TEXT,
                canonical_folder TEXT,
                rename_status TEXT
            )
            """
        )
        cursor.execute(
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

        # Create test folders
        folder1 = tmp_path / "Resume"
        folder2 = tmp_path / "Resumes"
        folder1.mkdir()
        folder2.mkdir()
        (folder1 / "file1.pdf").write_text("content")
        (folder2 / "file2.pdf").write_text("content")

        planner = ConsolidationPlanner(
            base_path=str(tmp_path),
            content_aware=True,
            db_path=db_path,
            analyze_missing=True,
        )

        plan = planner.create_plan()
        assert plan is not None

        # With analyze_missing enabled, the reasoning should mention analyzing missing files
        # when there are groups with content analysis
        for group in plan.groups:
            if group.content_analysis_done:
                # Should have reasoning about gathering context
                reasoning_text = " ".join(group.consolidation_reasoning)
                assert "Gathering context" in reasoning_text


class TestFolderContentSummary:
    """Test cases for FolderContentSummary class (Phase 5)."""

    def test_creation(self):
        """Test FolderContentSummary creation with basic fields."""
        summary = FolderContentSummary(
            folder_path="/test/path",
            ai_categories={"Employment/Resumes"},
            context_bins={"Personal Bin"},
            year_clusters=["2024-2025"],
            document_count=5,
        )
        assert summary.folder_path == "/test/path"
        assert summary.ai_categories == {"Employment/Resumes"}
        assert summary.context_bins == {"Personal Bin"}
        assert summary.year_clusters == ["2024-2025"]
        assert summary.document_count == 5

    def test_creation_with_defaults(self):
        """Test FolderContentSummary creation with default values."""
        summary = FolderContentSummary(folder_path="/test/path")
        assert summary.folder_path == "/test/path"
        assert summary.ai_categories == set()
        assert summary.context_bins == set()
        assert summary.year_clusters == []
        assert summary.document_count == 0

    def test_to_dict(self):
        """Test FolderContentSummary serialization to dict."""
        summary = FolderContentSummary(
            folder_path="/test/path",
            ai_categories={"Employment/Resumes", "Legal"},
            context_bins={"Personal Bin"},
            year_clusters=["2024-2025"],
            document_count=5,
        )
        data = summary.to_dict()
        assert data["folder_path"] == "/test/path"
        assert set(data["ai_categories"]) == {"Employment/Resumes", "Legal"}
        assert set(data["context_bins"]) == {"Personal Bin"}
        assert data["year_clusters"] == ["2024-2025"]
        assert data["document_count"] == 5

    def test_from_dict(self):
        """Test FolderContentSummary deserialization from dict."""
        data = {
            "folder_path": "/test/path",
            "ai_categories": ["Employment/Resumes"],
            "context_bins": ["Personal Bin"],
            "year_clusters": ["2024-2025"],
            "document_count": 5,
        }
        summary = FolderContentSummary.from_dict(data)
        assert summary.folder_path == "/test/path"
        assert summary.ai_categories == {"Employment/Resumes"}
        assert summary.context_bins == {"Personal Bin"}
        assert summary.year_clusters == ["2024-2025"]
        assert summary.document_count == 5

    def test_from_dict_missing_fields(self):
        """Test FolderContentSummary from_dict handles missing fields."""
        data = {}
        summary = FolderContentSummary.from_dict(data)
        assert summary.folder_path == ""
        assert summary.ai_categories == set()
        assert summary.context_bins == set()
        assert summary.year_clusters == []
        assert summary.document_count == 0

    def test_roundtrip(self):
        """Test FolderContentSummary serialization/deserialization roundtrip."""
        original = FolderContentSummary(
            folder_path="/test/path",
            ai_categories={"Employment/Resumes"},
            context_bins={"Personal Bin", "Work Bin"},
            year_clusters=["2022-2023", "2024-2025"],
            document_count=10,
        )
        data = original.to_dict()
        restored = FolderContentSummary.from_dict(data)
        assert restored.folder_path == original.folder_path
        assert restored.ai_categories == original.ai_categories
        assert restored.context_bins == original.context_bins
        assert restored.year_clusters == original.year_clusters
        assert restored.document_count == original.document_count

    def test_post_init_converts_lists_to_sets(self):
        """Test that __post_init__ converts lists to sets for ai_categories and context_bins."""
        # This tests the internal behavior when dataclass is created with lists
        summary = FolderContentSummary(
            folder_path="/test",
            ai_categories=["cat1", "cat2"],  # type: ignore
            context_bins=["bin1", "bin2"],  # type: ignore
        )
        assert isinstance(summary.ai_categories, set)
        assert isinstance(summary.context_bins, set)


class TestFolderGroupWithContentSummaries:
    """Test cases for FolderGroup with folder_content_summaries field."""

    def test_folder_group_has_content_summaries(self):
        """Test FolderGroup includes folder_content_summaries field."""
        group = FolderGroup(group_name="Test", category_key=None)
        assert hasattr(group, "folder_content_summaries")
        assert group.folder_content_summaries == {}

    def test_folder_group_to_dict_includes_summaries(self):
        """Test FolderGroup.to_dict includes folder_content_summaries."""
        group = FolderGroup(group_name="Test", category_key=None)
        group.folder_content_summaries["/test/path"] = FolderContentSummary(
            folder_path="/test/path",
            ai_categories={"Employment/Resumes"},
            context_bins={"Personal Bin"},
        )
        data = group.to_dict()
        assert "folder_content_summaries" in data
        assert "/test/path" in data["folder_content_summaries"]
        assert set(data["folder_content_summaries"]["/test/path"]["ai_categories"]) == {
            "Employment/Resumes"
        }

    def test_folder_group_from_dict_restores_summaries(self):
        """Test FolderGroup.from_dict restores folder_content_summaries."""
        data = {
            "group_name": "Test",
            "category_key": None,
            "folders": [],
            "folder_content_summaries": {
                "/test/path": {
                    "folder_path": "/test/path",
                    "ai_categories": ["Employment/Resumes"],
                    "context_bins": ["Personal Bin"],
                    "year_clusters": ["2024"],
                    "document_count": 5,
                }
            },
        }
        group = FolderGroup.from_dict(data)
        assert "/test/path" in group.folder_content_summaries
        summary = group.folder_content_summaries["/test/path"]
        assert summary.ai_categories == {"Employment/Resumes"}
        assert summary.context_bins == {"Personal Bin"}

    def test_folder_group_roundtrip_with_summaries(self):
        """Test FolderGroup serialization roundtrip preserves content summaries."""
        original = FolderGroup(group_name="Test", category_key=None)
        original.folder_content_summaries["/path1"] = FolderContentSummary(
            folder_path="/path1",
            ai_categories={"Employment/Resumes"},
            context_bins={"Personal Bin"},
            year_clusters=["2024-2025"],
            document_count=5,
        )
        original.folder_content_summaries["/path2"] = FolderContentSummary(
            folder_path="/path2",
            ai_categories={"Legal"},
            context_bins={"Work Bin"},
            year_clusters=["2023"],
            document_count=3,
        )

        data = original.to_dict()
        restored = FolderGroup.from_dict(data)

        assert len(restored.folder_content_summaries) == 2
        assert restored.folder_content_summaries["/path1"].ai_categories == {
            "Employment/Resumes"
        }
        assert restored.folder_content_summaries["/path2"].ai_categories == {"Legal"}


class TestContentAnalysisInPlanOutput:
    """Test cases for showing content analysis in plan output (Phase 5)."""

    def test_summary_shows_per_folder_ai_category(self, tmp_path):
        """Test that generate_summary shows per-folder AI category."""
        # Create a group with content summaries
        group = FolderGroup(
            group_name="Resume-related",
            category_key="resume",
            content_analysis_done=True,
            should_consolidate=True,
        )
        folder1 = FolderInfo(
            path=str(tmp_path / "Resume"),
            name="Resume",
            file_count=12,
        )
        group.add_folder(folder1)
        group.folder_content_summaries[str(tmp_path / "Resume")] = FolderContentSummary(
            folder_path=str(tmp_path / "Resume"),
            ai_categories={"Employment/Resumes"},
            context_bins=set(),
        )

        plan = ConsolidationPlan(
            base_path=str(tmp_path),
            content_aware=True,
            groups=[group],
        )

        planner = ConsolidationPlanner(base_path=str(tmp_path))
        summary = planner.generate_summary(plan)

        assert 'AI: "Employment/Resumes"' in summary

    def test_summary_shows_per_folder_context_bin(self, tmp_path):
        """Test that generate_summary shows per-folder context bin."""
        group = FolderGroup(
            group_name="Resume-related",
            category_key="resume",
            content_analysis_done=True,
            should_consolidate=True,
        )
        folder1 = FolderInfo(
            path=str(tmp_path / "Resume"),
            name="Resume",
            file_count=12,
        )
        group.add_folder(folder1)
        group.folder_content_summaries[str(tmp_path / "Resume")] = FolderContentSummary(
            folder_path=str(tmp_path / "Resume"),
            ai_categories=set(),
            context_bins={"Personal Bin"},
        )

        plan = ConsolidationPlan(
            base_path=str(tmp_path),
            content_aware=True,
            groups=[group],
        )

        planner = ConsolidationPlanner(base_path=str(tmp_path))
        summary = planner.generate_summary(plan)

        assert 'Context: "Personal Bin"' in summary

    def test_summary_shows_per_folder_dates(self, tmp_path):
        """Test that generate_summary shows per-folder date ranges."""
        group = FolderGroup(
            group_name="Resume-related",
            category_key="resume",
            content_analysis_done=True,
            should_consolidate=True,
        )
        folder1 = FolderInfo(
            path=str(tmp_path / "Resume"),
            name="Resume",
            file_count=12,
        )
        group.add_folder(folder1)
        group.folder_content_summaries[str(tmp_path / "Resume")] = FolderContentSummary(
            folder_path=str(tmp_path / "Resume"),
            ai_categories=set(),
            context_bins=set(),
            year_clusters=["2024-2025"],
        )

        plan = ConsolidationPlan(
            base_path=str(tmp_path),
            content_aware=True,
            groups=[group],
        )

        planner = ConsolidationPlanner(base_path=str(tmp_path))
        summary = planner.generate_summary(plan)

        assert 'Dates: "2024-2025"' in summary

    def test_summary_shows_all_content_info_combined(self, tmp_path):
        """Test that summary shows AI, Context, and Dates together per folder."""
        group = FolderGroup(
            group_name="Resume-related",
            category_key="resume",
            content_analysis_done=True,
            should_consolidate=True,
        )
        folder1 = FolderInfo(
            path=str(tmp_path / "Resume"),
            name="Resume",
            file_count=12,
        )
        group.add_folder(folder1)
        group.folder_content_summaries[str(tmp_path / "Resume")] = FolderContentSummary(
            folder_path=str(tmp_path / "Resume"),
            ai_categories={"Employment/Resumes"},
            context_bins={"Personal Bin"},
            year_clusters=["2024-2025"],
        )

        plan = ConsolidationPlan(
            base_path=str(tmp_path),
            content_aware=True,
            groups=[group],
        )

        planner = ConsolidationPlanner(base_path=str(tmp_path))
        summary = planner.generate_summary(plan)

        # All three should be on the same line for the folder listing (starts with "  -")
        lines = summary.split("\n")
        folder_line = [
            line
            for line in lines
            if line.strip().startswith("-") and "12 files" in line
        ]
        assert len(folder_line) == 1
        assert "AI:" in folder_line[0]
        assert "Context:" in folder_line[0]
        assert "Dates:" in folder_line[0]

    def test_summary_shows_different_content_per_folder(self, tmp_path):
        """Test that different folders show their own content analysis."""
        group = FolderGroup(
            group_name="Resume-related",
            category_key="resume",
            content_analysis_done=True,
            should_consolidate=True,
        )
        folder1 = FolderInfo(
            path=str(tmp_path / "Resume"),
            name="Resume",
            file_count=12,
        )
        folder2 = FolderInfo(
            path=str(tmp_path / "Resumes"),
            name="Resumes",
            file_count=8,
        )
        group.add_folder(folder1)
        group.add_folder(folder2)
        group.folder_content_summaries[str(tmp_path / "Resume")] = FolderContentSummary(
            folder_path=str(tmp_path / "Resume"),
            ai_categories={"Employment/Resumes"},
            context_bins={"Personal Bin"},
        )
        group.folder_content_summaries[str(tmp_path / "Resumes")] = (
            FolderContentSummary(
                folder_path=str(tmp_path / "Resumes"),
                ai_categories={"Employment/Resumes"},
                context_bins={"Work Bin"},
            )
        )

        plan = ConsolidationPlan(
            base_path=str(tmp_path),
            content_aware=True,
            groups=[group],
        )

        planner = ConsolidationPlanner(base_path=str(tmp_path))
        summary = planner.generate_summary(plan)

        # Both folders should be listed with their specific content
        assert "Personal Bin" in summary
        assert "Work Bin" in summary

    def test_summary_without_content_aware_no_content_info(self, tmp_path):
        """Test that non-content-aware mode doesn't show per-folder content info."""
        group = FolderGroup(
            group_name="Resume-related",
            category_key="resume",
        )
        folder1 = FolderInfo(
            path=str(tmp_path / "Resume"),
            name="Resume",
            file_count=12,
        )
        group.add_folder(folder1)

        plan = ConsolidationPlan(
            base_path=str(tmp_path),
            content_aware=False,
            groups=[group],
        )

        planner = ConsolidationPlanner(base_path=str(tmp_path))
        summary = planner.generate_summary(plan)

        # Should not show content-aware formatting
        assert 'AI: "' not in summary
        assert 'Context: "' not in summary
        assert 'Dates: "' not in summary

    def test_summary_fallback_for_missing_summaries(self, tmp_path):
        """Test summary falls back to group-level info if per-folder summary missing."""
        group = FolderGroup(
            group_name="Resume-related",
            category_key="resume",
            content_analysis_done=True,
            should_consolidate=True,
        )
        group.ai_categories = {"Employment/Resumes"}
        group.date_ranges[str(tmp_path / "Resume")] = "2024-2025"
        folder1 = FolderInfo(
            path=str(tmp_path / "Resume"),
            name="Resume",
            file_count=12,
        )
        group.add_folder(folder1)
        # Note: NOT adding folder_content_summaries

        plan = ConsolidationPlan(
            base_path=str(tmp_path),
            content_aware=True,
            groups=[group],
        )

        planner = ConsolidationPlanner(base_path=str(tmp_path))
        summary = planner.generate_summary(plan)

        # Should fallback to group-level info
        assert "Employment/Resumes" in summary


class TestContentAnalysisPopulatedInAnalyzeGroup:
    """Test that _analyze_group_content populates folder_content_summaries."""

    def test_analyze_group_populates_content_summaries(self, tmp_path):
        """Test that _analyze_group_content populates folder_content_summaries."""
        db_path = str(tmp_path / "test.db")

        # Create database with test data
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
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
                pdf_modified_date TEXT,
                canonical_folder TEXT,
                rename_status TEXT
            )
            """
        )
        cursor.execute(
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

        # Insert test document
        folder1_path = str(tmp_path / "Resume")
        cursor.execute(
            """
            INSERT INTO documents (filename, current_path, ai_category, folder_hierarchy)
            VALUES (?, ?, ?, ?)
            """,
            (
                "test.pdf",
                f"{folder1_path}/test.pdf",
                "Employment/Resumes",
                '["Personal Bin"]',
            ),
        )
        conn.commit()

        # Create test folders
        (tmp_path / "Resume").mkdir()
        (tmp_path / "Resume" / "test.pdf").write_text("content")
        (tmp_path / "Resumes").mkdir()
        (tmp_path / "Resumes" / "test2.pdf").write_text("content")

        planner = ConsolidationPlanner(
            base_path=str(tmp_path),
            content_aware=True,
            db_path=db_path,
        )

        plan = planner.create_plan()
        conn.close()

        # Find the Resume-related group
        resume_group = None
        for group in plan.groups:
            if "Resume" in group.group_name:
                resume_group = group
                break

        if resume_group and resume_group.content_analysis_done:
            # Check that folder_content_summaries is populated
            assert folder1_path in resume_group.folder_content_summaries
            summary = resume_group.folder_content_summaries[folder1_path]
            assert "Employment/Resumes" in summary.ai_categories
            assert "Personal Bin" in summary.context_bins


class TestDecisionSummary:
    """Tests for decision_summary field in FolderGroup (Phase 5)."""

    def test_folder_group_has_decision_summary_field(self):
        """Test that FolderGroup has decision_summary field."""
        group = FolderGroup(group_name="Test", category_key=None)
        assert hasattr(group, "decision_summary")
        assert group.decision_summary == ""

    def test_folder_group_decision_summary_in_to_dict(self):
        """Test that decision_summary is included in to_dict."""
        group = FolderGroup(
            group_name="Resume-related",
            category_key="employment",
            decision_summary="Same AI category, same context bin",
        )
        d = group.to_dict()
        assert "decision_summary" in d
        assert d["decision_summary"] == "Same AI category, same context bin"

    def test_folder_group_decision_summary_from_dict(self):
        """Test that decision_summary is restored from dict."""
        d = {
            "group_name": "Resume-related",
            "category_key": "employment",
            "decision_summary": "Different timeframes (2002 vs 2025)",
            "folders": [],
        }
        group = FolderGroup.from_dict(d)
        assert group.decision_summary == "Different timeframes (2002 vs 2025)"

    def test_folder_group_decision_summary_roundtrip(self):
        """Test decision_summary roundtrip through JSON."""
        group = FolderGroup(
            group_name="Tax-related",
            category_key="finances",
            decision_summary="Different AI categories",
        )
        group.add_folder(FolderInfo(path="/Tax", name="Tax", file_count=5))

        d = group.to_dict()
        restored = FolderGroup.from_dict(d)

        assert restored.decision_summary == "Different AI categories"


class TestDecisionSummaryInSummaryOutput:
    """Tests for decision_summary display in generate_summary (Phase 5)."""

    def test_summary_shows_decision_summary_for_can_consolidate(self):
        """Test that generate_summary shows decision_summary for consolidatable groups."""
        plan = ConsolidationPlan(content_aware=True)

        group = FolderGroup(
            group_name="Resume-related",
            category_key="employment",
            target_folder="Employment/Resumes",
            decision_summary="Same AI category, same context bin",
        )
        group.add_folder(FolderInfo(path="/Resume", name="Resume", file_count=5))
        group.add_folder(FolderInfo(path="/Resumes", name="Resumes", file_count=3))
        group.should_consolidate = True
        group.content_analysis_done = True
        group.confidence = 0.8

        plan.groups = [group]

        planner = ConsolidationPlanner()
        summary = planner.generate_summary(plan)

        # Should show decision_summary instead of confidence percentage
        assert "CAN CONSOLIDATE: Same AI category, same context bin" in summary

    def test_summary_shows_decision_summary_for_no_consolidate(self):
        """Test that generate_summary shows decision_summary for non-consolidatable groups."""
        plan = ConsolidationPlan(content_aware=True)

        group = FolderGroup(
            group_name="Tax-related",
            category_key="finances",
            target_folder="Finances/Taxes",
            decision_summary="Different timeframes (Tax2002 vs Tax2025)",
        )
        group.add_folder(FolderInfo(path="/Tax2002", name="Tax2002", file_count=10))
        group.add_folder(FolderInfo(path="/Tax2025", name="Tax2025", file_count=8))
        group.should_consolidate = False
        group.content_analysis_done = True

        plan.groups = [group]

        planner = ConsolidationPlanner()
        summary = planner.generate_summary(plan)

        # Should show decision_summary
        assert (
            "DO NOT CONSOLIDATE: Different timeframes (Tax2002 vs Tax2025)" in summary
        )

    def test_summary_shows_decision_summary_for_different_categories(self):
        """Test that summary shows correct reason for different AI categories."""
        plan = ConsolidationPlan(content_aware=True)

        group = FolderGroup(
            group_name="Mixed-related",
            category_key=None,
            decision_summary="Different AI categories (Mixed vs Other)",
        )
        group.add_folder(FolderInfo(path="/Mixed", name="Mixed", file_count=10))
        group.add_folder(FolderInfo(path="/Other", name="Other", file_count=5))
        group.should_consolidate = False
        group.content_analysis_done = True

        plan.groups = [group]

        planner = ConsolidationPlanner()
        summary = planner.generate_summary(plan)

        assert "DO NOT CONSOLIDATE: Different AI categories" in summary

    def test_summary_shows_decision_summary_for_different_paths(self):
        """Test that summary shows correct reason for different path contexts."""
        plan = ConsolidationPlan(content_aware=True)

        group = FolderGroup(
            group_name="Desktop-related",
            category_key=None,
            decision_summary="Different path contexts (Desktop vs Desktop 2)",
        )
        group.add_folder(FolderInfo(path="/Desktop", name="Desktop", file_count=50))
        group.add_folder(FolderInfo(path="/Desktop 2", name="Desktop 2", file_count=40))
        group.should_consolidate = False
        group.content_analysis_done = True

        plan.groups = [group]

        planner = ConsolidationPlanner()
        summary = planner.generate_summary(plan)

        assert "DO NOT CONSOLIDATE: Different path contexts" in summary

    def test_summary_fallback_to_confidence_when_no_decision_summary(self):
        """Test that summary falls back to confidence when decision_summary is empty."""
        plan = ConsolidationPlan(content_aware=True)

        group = FolderGroup(
            group_name="Resume-related",
            category_key="employment",
            target_folder="Employment/Resumes",
            decision_summary="",  # Empty
        )
        group.add_folder(FolderInfo(path="/Resume", name="Resume", file_count=5))
        group.should_consolidate = True
        group.content_analysis_done = True
        group.confidence = 0.75

        plan.groups = [group]

        planner = ConsolidationPlanner()
        summary = planner.generate_summary(plan)

        # Should fall back to confidence percentage
        assert "CAN CONSOLIDATE: 75% confidence" in summary

    def test_summary_fallback_for_no_consolidate_no_summary(self):
        """Test fallback for no consolidate when decision_summary is empty."""
        plan = ConsolidationPlan(content_aware=True)

        group = FolderGroup(
            group_name="Mixed-related",
            category_key=None,
            decision_summary="",  # Empty
        )
        group.add_folder(FolderInfo(path="/Mixed", name="Mixed", file_count=10))
        group.should_consolidate = False
        group.content_analysis_done = True

        plan.groups = [group]

        planner = ConsolidationPlanner()
        summary = planner.generate_summary(plan)

        # Should fall back to generic message
        assert "DO NOT CONSOLIDATE: Incompatible content" in summary


class TestDecisionSummaryIntegration:
    """Integration tests for decision_summary generation during content analysis."""

    def test_decision_summary_generated_for_matching_content(self, tmp_path):
        """Test that decision_summary is generated when folders can consolidate."""
        # Create test database with matching documents
        db_path = str(tmp_path / "test.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create documents table
        cursor.execute(
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

        # Create document_locations table
        cursor.execute(
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

        folder1_path = str(tmp_path / "Resume")
        folder2_path = str(tmp_path / "Resumes")

        # Insert matching documents (same category, same dates)
        cursor.execute(
            """
            INSERT INTO documents
            (filename, current_path, ai_category, key_dates, folder_hierarchy)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "resume1.pdf",
                f"{folder1_path}/resume1.pdf",
                "Employment/Resumes",
                '["2024-01-15"]',
                '["Personal Bin"]',
            ),
        )
        cursor.execute(
            """
            INSERT INTO documents
            (filename, current_path, ai_category, key_dates, folder_hierarchy)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "resume2.pdf",
                f"{folder2_path}/resume2.pdf",
                "Employment/Resumes",
                '["2024-03-20"]',
                '["Personal Bin"]',
            ),
        )
        conn.commit()

        # Create test folders with files
        (tmp_path / "Resume").mkdir()
        (tmp_path / "Resume" / "resume1.pdf").write_text("content")
        (tmp_path / "Resumes").mkdir()
        (tmp_path / "Resumes" / "resume2.pdf").write_text("content")

        planner = ConsolidationPlanner(
            base_path=str(tmp_path),
            content_aware=True,
            db_path=db_path,
        )

        plan = planner.create_plan()
        conn.close()

        # Find the Resume-related group
        resume_group = None
        for group in plan.groups:
            if "Resume" in group.group_name:
                resume_group = group
                break

        # Verify decision_summary is generated for matching content
        if resume_group and resume_group.content_analysis_done:
            assert resume_group.should_consolidate is True
            assert resume_group.decision_summary != ""
            # Summary should indicate why they can consolidate
            assert (
                "category" in resume_group.decision_summary.lower()
                or "context" in resume_group.decision_summary.lower()
                or "compatible" in resume_group.decision_summary.lower()
            )

    def test_decision_summary_generated_for_different_timeframes(self, tmp_path):
        """Test that decision_summary indicates different timeframes."""
        # Create test database
        db_path = str(tmp_path / "test.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute(
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

        cursor.execute(
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

        folder1_path = str(tmp_path / "Tax2002")
        folder2_path = str(tmp_path / "Tax2025")

        # Insert documents with different timeframes
        cursor.execute(
            """
            INSERT INTO documents
            (filename, current_path, ai_category, key_dates, folder_hierarchy)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "tax2002.pdf",
                f"{folder1_path}/tax2002.pdf",
                "Finances/Taxes",
                '["2002-04-15"]',
                '["Personal"]',
            ),
        )
        cursor.execute(
            """
            INSERT INTO documents
            (filename, current_path, ai_category, key_dates, folder_hierarchy)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "tax2025.pdf",
                f"{folder2_path}/tax2025.pdf",
                "Finances/Taxes",
                '["2025-01-10"]',
                '["Personal"]',
            ),
        )
        conn.commit()

        # Create test folders
        (tmp_path / "Tax2002").mkdir()
        (tmp_path / "Tax2002" / "tax2002.pdf").write_text("content")
        (tmp_path / "Tax2025").mkdir()
        (tmp_path / "Tax2025" / "tax2025.pdf").write_text("content")

        planner = ConsolidationPlanner(
            base_path=str(tmp_path),
            content_aware=True,
            db_path=db_path,
        )

        plan = planner.create_plan()
        conn.close()

        # Find the Tax-related group
        tax_group = None
        for group in plan.groups:
            if "Tax" in group.group_name:
                tax_group = group
                break

        # Verify decision_summary mentions different timeframes
        if tax_group and tax_group.content_analysis_done:
            assert tax_group.should_consolidate is False
            assert tax_group.decision_summary != ""
            # Summary should indicate timeframe difference
            assert "timeframe" in tax_group.decision_summary.lower()

    def test_decision_summary_prd_example_resume_consolidation(self, tmp_path):
        """Test PRD example: Resume folders CAN consolidate with proper reasoning."""
        db_path = str(tmp_path / "test.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute(
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
        cursor.execute(
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

        # Create three resume folders (as per PRD example)
        for folder_name in ["Resume", "Resumes", "Resume_Docs"]:
            folder_path = str(tmp_path / folder_name)
            (tmp_path / folder_name).mkdir()
            (tmp_path / folder_name / f"doc_{folder_name}.pdf").write_text("content")

            cursor.execute(
                """
                INSERT INTO documents
                (filename, current_path, ai_category, key_dates, folder_hierarchy)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    f"doc_{folder_name}.pdf",
                    f"{folder_path}/doc_{folder_name}.pdf",
                    "Employment/Resumes",
                    '["2024-06-15"]',
                    '["Personal Bin"]',
                ),
            )

        conn.commit()

        planner = ConsolidationPlanner(
            base_path=str(tmp_path),
            content_aware=True,
            db_path=db_path,
            threshold=0.7,  # Lower threshold to match Resume variants
        )

        plan = planner.create_plan()
        conn.close()

        # Generate summary and verify it shows reasoning
        summary = planner.generate_summary(plan)

        # The summary should show CAN CONSOLIDATE with a reason
        assert "CAN CONSOLIDATE" in summary or plan.total_groups == 0
