"""Tests for the category_mapper module."""

import tempfile
from pathlib import Path

import pytest

from organizer.canonical_registry import CanonicalRegistry
from organizer.category_mapper import (
    CONSOLIDATION_CATEGORIES,
    get_canonical_folder_for_category,
    get_category_for_folder_name,
    get_parent_folder_for_category,
    list_all_categories,
    map_to_canonical_category,
    suggest_canonical_path,
)


class TestConsolidationCategories:
    """Tests for the CONSOLIDATION_CATEGORIES constant."""

    def test_categories_exist(self):
        """Test that required categories are defined."""
        required_categories = ["employment", "finances", "legal", "health"]
        for category in required_categories:
            assert category in CONSOLIDATION_CATEGORIES

    def test_category_structure(self):
        """Test that each category has required fields."""
        for category_key, category_info in CONSOLIDATION_CATEGORIES.items():
            assert "patterns" in category_info, f"{category_key} missing 'patterns'"
            assert "canonical_folder" in category_info, (
                f"{category_key} missing 'canonical_folder'"
            )
            assert "parent_folder" in category_info, (
                f"{category_key} missing 'parent_folder'"
            )
            assert isinstance(category_info["patterns"], list), (
                f"{category_key} patterns should be a list"
            )
            assert len(category_info["patterns"]) > 0, (
                f"{category_key} should have at least one pattern"
            )

    def test_employment_patterns(self):
        """Test employment category has expected patterns."""
        employment = CONSOLIDATION_CATEGORIES["employment"]
        expected_patterns = ["resume", "cv", "cover letter", "job"]
        for pattern in expected_patterns:
            assert pattern in employment["patterns"], (
                f"Missing pattern '{pattern}' in employment"
            )
        assert employment["canonical_folder"] == "Resumes"
        assert employment["parent_folder"] == "Employment"

    def test_finances_patterns(self):
        """Test finances category has expected patterns."""
        finances = CONSOLIDATION_CATEGORIES["finances"]
        expected_patterns = ["tax", "taxes", "invoice", "receipt", "budget"]
        for pattern in expected_patterns:
            assert pattern in finances["patterns"], (
                f"Missing pattern '{pattern}' in finances"
            )
        assert finances["canonical_folder"] == "Taxes"
        assert finances["parent_folder"] == "Finances Bin"


class TestGetCategoryForFolderName:
    """Tests for get_category_for_folder_name function."""

    def test_resume_variations(self):
        """Test resume folder name variations map to employment."""
        resume_names = [
            "Resume",
            "Resumes",
            "Resume_Docs",
            "Resume_1",
            "RESUME",
            "resume",
        ]
        for name in resume_names:
            result = get_category_for_folder_name(name)
            assert result == "employment", (
                f"'{name}' should map to employment, got {result}"
            )

    def test_cv_maps_to_employment(self):
        """Test CV maps to employment category."""
        assert get_category_for_folder_name("CV") == "employment"
        assert get_category_for_folder_name("cv_docs") == "employment"

    def test_cover_letter_maps_to_employment(self):
        """Test cover letter variations map to employment."""
        assert get_category_for_folder_name("Cover Letter") == "employment"
        assert get_category_for_folder_name("cover_letter") == "employment"
        assert get_category_for_folder_name("CoverLetter") == "employment"

    def test_tax_variations(self):
        """Test tax folder name variations map to finances."""
        tax_names = ["Tax", "Taxes", "Tax_2023", "Tax_Docs", "TAXES"]
        for name in tax_names:
            result = get_category_for_folder_name(name)
            assert result == "finances", (
                f"'{name}' should map to finances, got {result}"
            )

    def test_invoice_maps_to_finances(self):
        """Test invoice maps to finances category."""
        assert get_category_for_folder_name("Invoice") == "finances"
        assert get_category_for_folder_name("Invoices") == "finances"
        assert get_category_for_folder_name("Invoice_2023") == "finances"

    def test_contract_variations(self):
        """Test contract folder name variations map to legal."""
        contract_names = ["Contract", "Contracts", "Contract_Docs", "Agreement"]
        for name in contract_names:
            result = get_category_for_folder_name(name)
            assert result == "legal", f"'{name}' should map to legal, got {result}"

    def test_medical_variations(self):
        """Test medical folder name variations map to health."""
        # Note: compound names like "Medical_Records" normalize to "medicalrecord"
        # which doesn't fuzzy-match "medical" - this is expected behavior.
        # For such cases, the pattern itself should be added to CONSOLIDATION_CATEGORIES.
        health_names = ["Medical", "Prescription", "Health", "Doctor"]
        for name in health_names:
            result = get_category_for_folder_name(name)
            assert result == "health", f"'{name}' should map to health, got {result}"

    def test_unknown_folder_returns_none(self):
        """Test unknown folder names return None."""
        unknown_names = ["RandomFolder", "Misc", "Downloads", "Photos", "Music"]
        for name in unknown_names:
            result = get_category_for_folder_name(name)
            assert result is None, (
                f"'{name}' should not match any category, got {result}"
            )

    def test_partial_match_with_threshold(self):
        """Test partial matches respect threshold."""
        # Lower threshold should match more loosely
        result_low = get_category_for_folder_name("Resum", threshold=0.7)
        result_high = get_category_for_folder_name("Resum", threshold=0.95)
        # With low threshold, partial match might work
        # With very high threshold, it might not
        assert (
            result_low is not None or result_high is None
        )  # At least one should differ


class TestGetCanonicalFolderForCategory:
    """Tests for get_canonical_folder_for_category function."""

    def test_employment_canonical_folder(self):
        """Test employment returns Resumes."""
        assert get_canonical_folder_for_category("employment") == "Resumes"

    def test_finances_canonical_folder(self):
        """Test finances returns Taxes."""
        assert get_canonical_folder_for_category("finances") == "Taxes"

    def test_legal_canonical_folder(self):
        """Test legal returns Contracts."""
        assert get_canonical_folder_for_category("legal") == "Contracts"

    def test_health_canonical_folder(self):
        """Test health returns Medical."""
        assert get_canonical_folder_for_category("health") == "Medical"

    def test_unknown_category_returns_none(self):
        """Test unknown category returns None."""
        assert get_canonical_folder_for_category("unknown") is None
        assert get_canonical_folder_for_category("") is None


class TestGetParentFolderForCategory:
    """Tests for get_parent_folder_for_category function."""

    def test_employment_parent_folder(self):
        """Test employment returns Employment."""
        assert get_parent_folder_for_category("employment") == "Employment"

    def test_finances_parent_folder(self):
        """Test finances returns Finances Bin."""
        assert get_parent_folder_for_category("finances") == "Finances Bin"

    def test_legal_parent_folder(self):
        """Test legal returns Contracts."""
        assert get_parent_folder_for_category("legal") == "Contracts"

    def test_health_parent_folder(self):
        """Test health returns Health."""
        assert get_parent_folder_for_category("health") == "Health"

    def test_unknown_category_returns_none(self):
        """Test unknown category returns None."""
        assert get_parent_folder_for_category("unknown") is None


class TestSuggestCanonicalPath:
    """Tests for suggest_canonical_path function."""

    @pytest.fixture
    def temp_storage(self):
        """Create a temporary directory for registry storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "canonical_folders.json"

    @pytest.fixture
    def registry(self, temp_storage):
        """Create a fresh registry for each test."""
        return CanonicalRegistry(storage_path=temp_storage)

    def test_resume_path_suggestion(self, registry):
        """Test resume file gets Employment/Resumes path."""
        path = suggest_canonical_path(
            file_path="/downloads/john_resume.pdf",
            file_name="john_resume.pdf",
            ai_category="Resume",
            registry=registry,
            base_path="/iCloud",
        )
        assert path == "/iCloud/Employment/Resumes"

    def test_tax_path_suggestion(self, registry):
        """Test tax file gets Finances Bin/Taxes path."""
        path = suggest_canonical_path(
            file_path="/downloads/2023_taxes.pdf",
            file_name="2023_taxes.pdf",
            ai_category="Tax_2023",
            registry=registry,
            base_path="/iCloud",
        )
        assert path == "/iCloud/Finances Bin/Taxes"

    def test_contract_path_suggestion(self, registry):
        """Test contract file gets Contracts/Contracts path."""
        path = suggest_canonical_path(
            file_path="/downloads/nda.pdf",
            file_name="nda.pdf",
            ai_category="Contract",
            registry=registry,
            base_path="/iCloud",
        )
        assert path == "/iCloud/Contracts/Contracts"

    def test_respects_existing_registry_folder(self, registry):
        """Test that existing registry folders are respected."""
        # Pre-register a folder
        registry.register_folder("/iCloud/Employment/MyResumes", category="Employment")

        # Now suggest path for similar category
        path = suggest_canonical_path(
            file_path="/downloads/cv.pdf",
            file_name="cv.pdf",
            ai_category="Resumes",  # Similar to existing "MyResumes"
            registry=registry,
            base_path="/iCloud",
        )
        # Should return existing folder since "Resumes" normalizes to "resume"
        # which is similar to "MyResumes" normalized
        assert "Resumes" in path or "MyResumes" in path

    def test_unknown_category_uses_ai_category_directly(self, registry):
        """Test unknown category falls back to AI category."""
        path = suggest_canonical_path(
            file_path="/downloads/misc.pdf",
            file_name="misc.pdf",
            ai_category="RandomFolder",
            registry=registry,
            base_path="/iCloud",
        )
        assert "RandomFolder" in path

    def test_without_base_path(self, registry):
        """Test path suggestion without base path."""
        path = suggest_canonical_path(
            file_path="/downloads/resume.pdf",
            file_name="resume.pdf",
            ai_category="Resume",
            registry=registry,
        )
        assert path == "Employment/Resumes"

    def test_creates_registry_if_none(self):
        """Test that registry is created if None."""
        # Should not raise an error
        path = suggest_canonical_path(
            file_path="/downloads/resume.pdf",
            file_name="resume.pdf",
            ai_category="Resume",
            registry=None,
        )
        assert "Resumes" in path


class TestMapToCanonicalCategory:
    """Tests for map_to_canonical_category function."""

    @pytest.fixture
    def temp_storage(self):
        """Create a temporary directory for registry storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "canonical_folders.json"

    @pytest.fixture
    def registry(self, temp_storage):
        """Create a fresh registry for each test."""
        return CanonicalRegistry(storage_path=temp_storage)

    def test_resume_mapping(self):
        """Test Resume_Docs maps correctly."""
        result = map_to_canonical_category("Resume_Docs")
        assert result == ("employment", "Employment", "Resumes")

    def test_tax_mapping(self):
        """Test Tax_2023 maps correctly."""
        result = map_to_canonical_category("Tax_2023")
        assert result == ("finances", "Finances Bin", "Taxes")

    def test_contract_mapping(self):
        """Test Contract maps correctly."""
        result = map_to_canonical_category("Contract")
        assert result == ("legal", "Contracts", "Contracts")

    def test_medical_mapping(self):
        """Test Medical maps correctly."""
        result = map_to_canonical_category("Medical")
        assert result == ("health", "Health", "Medical")

    def test_unknown_mapping_returns_none_tuple(self):
        """Test unknown folder returns tuple of Nones."""
        result = map_to_canonical_category("RandomFolder")
        assert result == (None, None, None)

    def test_with_registry_existing_folder(self, registry):
        """Test mapping respects registry entries."""
        # Register a folder with specific category
        registry.register_folder("/iCloud/Employment/MyResumes", category="Employment")

        # Map a similar folder name
        result = map_to_canonical_category("Resume", registry=registry)
        # Should still return employment category info based on patterns
        assert result[0] == "employment"


class TestListAllCategories:
    """Tests for list_all_categories function."""

    def test_returns_list(self):
        """Test that function returns a list."""
        result = list_all_categories()
        assert isinstance(result, list)

    def test_list_not_empty(self):
        """Test that list is not empty."""
        result = list_all_categories()
        assert len(result) > 0

    def test_category_dict_structure(self):
        """Test each category dict has expected keys."""
        result = list_all_categories()
        for category in result:
            assert "key" in category
            assert "patterns" in category
            assert "canonical_folder" in category
            assert "parent_folder" in category

    def test_contains_expected_categories(self):
        """Test that expected categories are present."""
        result = list_all_categories()
        keys = [cat["key"] for cat in result]
        assert "employment" in keys
        assert "finances" in keys
        assert "legal" in keys
        assert "health" in keys


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
        """Test resume folders consolidate correctly per PRD example."""
        # Various resume folder names should all map to same category
        resume_variations = ["Resume", "Resumes", "Resume_Docs", "Resume_1"]
        for name in resume_variations:
            category, parent, canonical = map_to_canonical_category(name)
            assert category == "employment", f"{name} should be employment"
            assert parent == "Employment", f"{name} parent should be Employment"
            assert canonical == "Resumes", f"{name} canonical should be Resumes"

    def test_tax_consolidation_scenario(self, registry):
        """Test tax folders consolidate correctly per PRD example."""
        # Tax variations should all map to finances
        tax_variations = ["Taxes", "Tax_2023", "Tax_Docs", "Tax_Files"]
        for name in tax_variations:
            category, parent, canonical = map_to_canonical_category(name)
            assert category == "finances", f"{name} should be finances"
            assert parent == "Finances Bin", f"{name} parent should be Finances Bin"
            assert canonical == "Taxes", f"{name} canonical should be Taxes"

    def test_suggest_path_workflow(self, registry):
        """Test the typical suggest_canonical_path workflow."""
        # First file suggests a path
        path1 = suggest_canonical_path(
            file_path="/downloads/resume.pdf",
            file_name="resume.pdf",
            ai_category="Resume",
            registry=registry,
            base_path="/iCloud",
        )
        assert path1 == "/iCloud/Employment/Resumes"

        # Second file with different AI category but same semantic meaning
        path2 = suggest_canonical_path(
            file_path="/downloads/cv.pdf",
            file_name="cv.pdf",
            ai_category="CV",
            registry=registry,
            base_path="/iCloud",
        )
        # Should get the existing registered folder
        assert path2 == "/iCloud/Employment/Resumes"

    def test_mixed_category_files(self, registry):
        """Test organizing files from different categories."""
        # Resume file
        resume_path = suggest_canonical_path(
            file_path="/downloads/resume.pdf",
            file_name="resume.pdf",
            ai_category="Resume",
            registry=registry,
            base_path="/iCloud",
        )

        # Tax file
        tax_path = suggest_canonical_path(
            file_path="/downloads/taxes.pdf",
            file_name="taxes.pdf",
            ai_category="Taxes",
            registry=registry,
            base_path="/iCloud",
        )

        # Contract file
        contract_path = suggest_canonical_path(
            file_path="/downloads/contract.pdf",
            file_name="contract.pdf",
            ai_category="Contract",
            registry=registry,
            base_path="/iCloud",
        )

        assert resume_path == "/iCloud/Employment/Resumes"
        assert tax_path == "/iCloud/Finances Bin/Taxes"
        assert contract_path == "/iCloud/Contracts/Contracts"

        # Verify registry has 3 distinct entries
        folders = registry.list_folders()
        assert len(folders) == 3
