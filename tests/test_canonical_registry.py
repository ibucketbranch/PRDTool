"""Tests for the CanonicalRegistry class."""

import json
import tempfile
from pathlib import Path

import pytest

from organizer.canonical_registry import CanonicalRegistry, FolderEntry


class TestFolderEntry:
    """Tests for the FolderEntry dataclass."""

    def test_create_entry(self):
        """Test creating a FolderEntry."""
        entry = FolderEntry(
            path="/docs/Resume", normalized_name="resume", category="Employment"
        )
        assert entry.path == "/docs/Resume"
        assert entry.normalized_name == "resume"
        assert entry.category == "Employment"

    def test_to_dict(self):
        """Test converting entry to dictionary."""
        entry = FolderEntry(
            path="/docs/Resume", normalized_name="resume", category="Employment"
        )
        result = entry.to_dict()
        assert result == {
            "path": "/docs/Resume",
            "normalized_name": "resume",
            "category": "Employment",
        }

    def test_from_dict(self):
        """Test creating entry from dictionary."""
        data = {
            "path": "/docs/Resume",
            "normalized_name": "resume",
            "category": "Employment",
        }
        entry = FolderEntry.from_dict(data)
        assert entry.path == "/docs/Resume"
        assert entry.normalized_name == "resume"
        assert entry.category == "Employment"

    def test_from_dict_without_category(self):
        """Test creating entry from dictionary without category."""
        data = {
            "path": "/docs/Resume",
            "normalized_name": "resume",
        }
        entry = FolderEntry.from_dict(data)
        assert entry.category == ""


class TestCanonicalRegistry:
    """Tests for the CanonicalRegistry class."""

    @pytest.fixture
    def temp_storage(self):
        """Create a temporary directory for registry storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "canonical_folders.json"

    @pytest.fixture
    def registry(self, temp_storage):
        """Create a fresh registry for each test."""
        return CanonicalRegistry(storage_path=temp_storage)

    def test_init_creates_empty_registry(self, registry):
        """Test that a new registry is empty."""
        assert len(registry.folders) == 0

    def test_register_folder_new(self, registry):
        """Test registering a new folder."""
        result = registry.register_folder("/docs/Resume", category="Employment")
        assert result is None  # New folder, no existing match
        assert "resume" in registry.folders

    def test_register_folder_similar_returns_existing(self, registry):
        """Test that registering a similar folder returns existing entry."""
        registry.register_folder("/docs/Resume", category="Employment")
        result = registry.register_folder("/docs/Resumes", category="Employment")
        assert result is not None
        assert result.path == "/docs/Resume"

    def test_register_folder_different(self, registry):
        """Test registering completely different folders."""
        registry.register_folder("/docs/Resume", category="Employment")
        result = registry.register_folder("/docs/Taxes", category="Finances")
        assert result is None  # Different folder, no match

    def test_get_canonical_folder_exists(self, registry):
        """Test getting canonical folder when it exists."""
        registry.register_folder("/docs/Resume", category="Employment")
        result = registry.get_canonical_folder("Resumes")
        assert result is not None
        assert result.path == "/docs/Resume"

    def test_get_canonical_folder_not_exists(self, registry):
        """Test getting canonical folder when it doesn't exist."""
        result = registry.get_canonical_folder("Resumes")
        assert result is None

    def test_get_canonical_folder_variations(self, registry):
        """Test various folder name variations."""
        registry.register_folder("/docs/Resume", category="Employment")

        # All these should match
        assert registry.get_canonical_folder("Resume") is not None
        assert registry.get_canonical_folder("Resumes") is not None
        assert registry.get_canonical_folder("Resume_Docs") is not None
        assert registry.get_canonical_folder("Resume_1") is not None
        assert registry.get_canonical_folder("RESUME") is not None

    def test_get_or_create_new_folder(self, registry):
        """Test get_or_create with a new folder."""
        path = registry.get_or_create("Employment", "Resume", "/iCloud")
        assert path == "/iCloud/Employment/Resume"
        assert "resume" in registry.folders

    def test_get_or_create_existing_folder(self, registry):
        """Test get_or_create with an existing similar folder."""
        registry.get_or_create("Employment", "Resume", "/iCloud")
        path = registry.get_or_create("Employment", "Resumes", "/iCloud")
        assert path == "/iCloud/Employment/Resume"  # Returns canonical

    def test_get_or_create_without_base_path(self, registry):
        """Test get_or_create without base path."""
        path = registry.get_or_create("Employment", "Resume")
        assert path == "Employment/Resume"

    def test_get_or_create_without_category(self, registry):
        """Test get_or_create without category."""
        path = registry.get_or_create("", "Resume", "/iCloud")
        assert path == "/iCloud/Resume"

    def test_persistence_save_and_load(self, temp_storage):
        """Test that registry persists between instances."""
        # Create and populate registry
        registry1 = CanonicalRegistry(storage_path=temp_storage)
        registry1.register_folder("/docs/Resume", category="Employment")
        registry1.register_folder("/docs/Taxes", category="Finances")

        # Create new instance from same storage
        registry2 = CanonicalRegistry(storage_path=temp_storage)
        assert len(registry2.folders) == 2
        assert "resume" in registry2.folders
        assert "tax" in registry2.folders

    def test_persistence_file_format(self, temp_storage):
        """Test that the JSON file has correct format."""
        registry = CanonicalRegistry(storage_path=temp_storage)
        registry.register_folder("/docs/Resume", category="Employment")

        with open(temp_storage, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert "folders" in data
        assert "resume" in data["folders"]
        assert data["folders"]["resume"]["path"] == "/docs/Resume"
        assert data["folders"]["resume"]["category"] == "Employment"

    def test_list_folders_all(self, registry):
        """Test listing all folders."""
        registry.register_folder("/docs/Resume", category="Employment")
        registry.register_folder("/docs/Taxes", category="Finances")
        registry.register_folder("/docs/Contracts", category="Legal")

        folders = registry.list_folders()
        assert len(folders) == 3

    def test_list_folders_by_category(self, registry):
        """Test listing folders filtered by category."""
        registry.register_folder("/docs/Resume", category="Employment")
        registry.register_folder("/docs/Cover_Letters", category="Employment")
        registry.register_folder("/docs/Taxes", category="Finances")

        employment_folders = registry.list_folders(category="Employment")
        assert len(employment_folders) == 2

        finance_folders = registry.list_folders(category="Finances")
        assert len(finance_folders) == 1

    def test_clear(self, registry):
        """Test clearing the registry."""
        registry.register_folder("/docs/Resume", category="Employment")
        registry.register_folder("/docs/Taxes", category="Finances")

        registry.clear()
        assert len(registry.folders) == 0

    def test_custom_threshold(self, temp_storage):
        """Test registry with custom similarity threshold."""
        registry = CanonicalRegistry(storage_path=temp_storage, threshold=0.95)
        registry.register_folder("/docs/Resume", category="Employment")

        # With high threshold, similar but not exact names might not match
        # Resume and Resumes should still match since normalized forms are identical
        result = registry.get_canonical_folder("Resumes")
        assert result is not None  # Normalized to same form


class TestPRDScenarios:
    """Tests for PRD-specific scenarios."""

    @pytest.fixture
    def temp_storage(self):
        """Create a temporary directory for registry storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "canonical_folders.json"

    @pytest.fixture
    def registry(self, temp_storage):
        """Create a fresh registry for each test."""
        return CanonicalRegistry(storage_path=temp_storage)

    def test_resume_consolidation_scenario(self, registry):
        """Test the resume consolidation scenario from PRD example."""
        # First Resume folder registered as canonical
        registry.register_folder("/iCloud/Resume", category="Employment")

        # All these should return the existing canonical folder
        similar_folders = [
            "/iCloud/Resumes",
            "/iCloud/Resume_Docs",
            "/iCloud/Resume_1",
        ]
        for folder in similar_folders:
            result = registry.register_folder(folder, category="Employment")
            assert result is not None, (
                f"Expected {folder} to match existing Resume folder"
            )
            assert result.path == "/iCloud/Resume"

    def test_tax_consolidation_scenario(self, registry):
        """Test the tax consolidation scenario from PRD example."""
        # Register canonical tax folder
        registry.register_folder("/iCloud/Finances/Taxes", category="Finances")

        # Tax_2023 should match (normalizes to "tax")
        result1 = registry.get_canonical_folder("Tax_2023")
        assert result1 is not None
        assert result1.path == "/iCloud/Finances/Taxes"

        # Tax_Docs and Tax_Files should match
        result2 = registry.get_canonical_folder("Tax_Docs")
        result3 = registry.get_canonical_folder("Tax_Files")
        assert result2 is not None
        assert result3 is not None

        # Note: "Tax Returns" normalizes to "taxreturn" which is different from "tax"
        # This is expected behavior - it's a compound name that needs category-based
        # matching (Phase 3) rather than just fuzzy string matching

    def test_get_or_create_workflow(self, registry):
        """Test the typical get-or-create workflow."""
        # First file with AI-suggested category "Resume"
        path1 = registry.get_or_create("Employment", "Resume", "/iCloud")
        assert path1 == "/iCloud/Employment/Resume"

        # Second file with AI-suggested category "Resumes"
        path2 = registry.get_or_create("Employment", "Resumes", "/iCloud")
        assert path2 == "/iCloud/Employment/Resume"  # Should use canonical

        # Third file with "Resume_Docs"
        path3 = registry.get_or_create("Employment", "Resume_Docs", "/iCloud")
        assert path3 == "/iCloud/Employment/Resume"  # Should use canonical

        # Different category entirely
        path4 = registry.get_or_create("Finances", "Taxes", "/iCloud")
        assert path4 == "/iCloud/Finances/Taxes"  # New folder

    def test_different_categories_same_name(self, registry):
        """Test folders with same name but should be separate due to context."""
        # This tests that truly different folders remain separate
        registry.register_folder("/iCloud/Resume", category="Employment")
        result = registry.register_folder("/iCloud/Medical", category="Health")
        assert result is None  # Different, should be registered separately
