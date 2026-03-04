"""Tests for taxonomy_utils module.

Tests locked bin functionality as specified in Phase 12 of the PRD:
- Locked bins cannot be renamed, moved, or merged by the agent
- New subcategories can still be created under locked bins
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from organizer.taxonomy_utils import (
    Taxonomy,
    TaxonomyBin,
    load_taxonomy,
    save_taxonomy,
    is_bin_locked,
    get_locked_bins,
    validate_bin_operation,
    is_path_under_locked_bin,
    create_default_taxonomy,
)


class TestTaxonomyBin:
    """Tests for TaxonomyBin dataclass."""

    def test_create_bin_with_defaults(self) -> None:
        """Test creating a bin with default values."""
        bin_obj = TaxonomyBin(name="Test Bin")
        assert bin_obj.name == "Test Bin"
        assert bin_obj.locked is False
        assert bin_obj.subcategories == {}

    def test_create_locked_bin(self) -> None:
        """Test creating a locked bin."""
        bin_obj = TaxonomyBin(name="VA", locked=True)
        assert bin_obj.name == "VA"
        assert bin_obj.locked is True

    def test_bin_with_subcategories(self) -> None:
        """Test creating a bin with subcategories."""
        bin_obj = TaxonomyBin(
            name="Finances Bin",
            locked=True,
            subcategories={"taxes": "Finances Bin/Taxes"},
        )
        assert "taxes" in bin_obj.subcategories
        assert bin_obj.subcategories["taxes"] == "Finances Bin/Taxes"

    def test_bin_to_dict(self) -> None:
        """Test converting bin to dictionary."""
        bin_obj = TaxonomyBin(
            name="VA",
            locked=True,
            subcategories={"claims": "VA/Claims"},
        )
        result = bin_obj.to_dict()
        assert result["name"] == "VA"
        assert result["locked"] is True
        assert result["subcategories"]["claims"] == "VA/Claims"

    def test_bin_from_dict(self) -> None:
        """Test creating bin from dictionary."""
        data = {
            "name": "Work Bin",
            "locked": True,
            "subcategories": {"projects": "Work Bin/Projects"},
        }
        bin_obj = TaxonomyBin.from_dict(data)
        assert bin_obj.name == "Work Bin"
        assert bin_obj.locked is True
        assert bin_obj.subcategories["projects"] == "Work Bin/Projects"

    def test_bin_from_dict_with_defaults(self) -> None:
        """Test creating bin from incomplete dictionary."""
        data = {"name": "Test"}
        bin_obj = TaxonomyBin.from_dict(data)
        assert bin_obj.name == "Test"
        assert bin_obj.locked is False
        assert bin_obj.subcategories == {}


class TestTaxonomy:
    """Tests for Taxonomy dataclass."""

    def test_create_empty_taxonomy(self) -> None:
        """Test creating an empty taxonomy."""
        taxonomy = Taxonomy()
        assert taxonomy.version == ""
        assert taxonomy.description == ""
        assert taxonomy.bins == {}
        assert taxonomy.rules == {}

    def test_create_taxonomy_with_bins(self) -> None:
        """Test creating taxonomy with bins."""
        taxonomy = Taxonomy(
            version="2026-03-03",
            description="Test taxonomy",
        )
        taxonomy.bins["VA"] = TaxonomyBin(name="VA", locked=True)
        taxonomy.bins["Archive"] = TaxonomyBin(name="Archive", locked=False)

        assert len(taxonomy.bins) == 2
        assert taxonomy.bins["VA"].locked is True
        assert taxonomy.bins["Archive"].locked is False

    def test_get_locked_bins(self) -> None:
        """Test getting list of locked bins."""
        taxonomy = Taxonomy()
        taxonomy.bins["VA"] = TaxonomyBin(name="VA", locked=True)
        taxonomy.bins["Finances Bin"] = TaxonomyBin(name="Finances Bin", locked=True)
        taxonomy.bins["Temp"] = TaxonomyBin(name="Temp", locked=False)

        locked = taxonomy.get_locked_bins()
        assert len(locked) == 2
        assert "VA" in locked
        assert "Finances Bin" in locked
        assert "Temp" not in locked

    def test_is_bin_locked_true(self) -> None:
        """Test checking if locked bin is locked."""
        taxonomy = Taxonomy()
        taxonomy.bins["VA"] = TaxonomyBin(name="VA", locked=True)

        assert taxonomy.is_bin_locked("VA") is True

    def test_is_bin_locked_false(self) -> None:
        """Test checking if unlocked bin is locked."""
        taxonomy = Taxonomy()
        taxonomy.bins["Temp"] = TaxonomyBin(name="Temp", locked=False)

        assert taxonomy.is_bin_locked("Temp") is False

    def test_is_bin_locked_nonexistent(self) -> None:
        """Test checking if nonexistent bin is locked."""
        taxonomy = Taxonomy()
        assert taxonomy.is_bin_locked("DoesNotExist") is False

    def test_get_bin_names(self) -> None:
        """Test getting all bin names."""
        taxonomy = Taxonomy()
        taxonomy.bins["VA"] = TaxonomyBin(name="VA")
        taxonomy.bins["Work Bin"] = TaxonomyBin(name="Work Bin")

        names = taxonomy.get_bin_names()
        assert len(names) == 2
        assert "VA" in names
        assert "Work Bin" in names

    def test_taxonomy_to_dict(self) -> None:
        """Test converting taxonomy to dictionary."""
        taxonomy = Taxonomy(version="1.0", description="Test")
        taxonomy.bins["VA"] = TaxonomyBin(name="VA", locked=True)
        taxonomy.rules["va_claims"] = "VA"

        result = taxonomy.to_dict()
        assert result["version"] == "1.0"
        assert result["description"] == "Test"
        assert "VA" in result["canonical_roots"]
        assert result["locked_bins"]["VA"] is True


class TestLoadTaxonomy:
    """Tests for loading taxonomy from file."""

    def test_load_taxonomy_with_locked_bins(self) -> None:
        """Test loading taxonomy with locked_bins field."""
        data = {
            "version": "2026-03-03",
            "description": "Test taxonomy",
            "canonical_roots": ["VA", "Finances Bin", "Work Bin"],
            "locked_bins": {
                "VA": True,
                "Finances Bin": True,
                "Work Bin": False,
            },
            "rules": {"va": "VA"},
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(data, f)
            temp_path = f.name

        try:
            taxonomy = load_taxonomy(temp_path)
            assert taxonomy.version == "2026-03-03"
            assert taxonomy.is_bin_locked("VA") is True
            assert taxonomy.is_bin_locked("Finances Bin") is True
            assert taxonomy.is_bin_locked("Work Bin") is False
            assert len(taxonomy.get_locked_bins()) == 2
        finally:
            Path(temp_path).unlink()

    def test_load_taxonomy_without_locked_bins(self) -> None:
        """Test loading taxonomy without locked_bins field (all unlocked)."""
        data = {
            "version": "1.0",
            "canonical_roots": ["VA", "Archive"],
            "rules": {},
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(data, f)
            temp_path = f.name

        try:
            taxonomy = load_taxonomy(temp_path)
            assert taxonomy.is_bin_locked("VA") is False
            assert taxonomy.is_bin_locked("Archive") is False
        finally:
            Path(temp_path).unlink()

    def test_load_taxonomy_with_subcategories(self) -> None:
        """Test loading taxonomy with subcategories."""
        data = {
            "version": "1.0",
            "canonical_roots": ["Family Bin", "Finances Bin"],
            "locked_bins": {"Family Bin": True, "Finances Bin": True},
            "family_members": {
                "camila": "Family Bin/Camila",
                "hudson": "Family Bin/Hudson",
            },
            "finance_subcategories": {
                "taxes": "Finances Bin/Taxes",
            },
            "rules": {},
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(data, f)
            temp_path = f.name

        try:
            taxonomy = load_taxonomy(temp_path)
            assert "camila" in taxonomy.bins["Family Bin"].subcategories
            assert "taxes" in taxonomy.bins["Finances Bin"].subcategories
        finally:
            Path(temp_path).unlink()

    def test_load_taxonomy_file_not_found(self) -> None:
        """Test loading taxonomy from nonexistent file."""
        with pytest.raises(FileNotFoundError):
            load_taxonomy("/nonexistent/path/taxonomy.json")


class TestSaveTaxonomy:
    """Tests for saving taxonomy to file."""

    def test_save_and_load_taxonomy(self) -> None:
        """Test saving and reloading taxonomy preserves data."""
        taxonomy = Taxonomy(version="2.0", description="Round trip test")
        taxonomy.bins["VA"] = TaxonomyBin(name="VA", locked=True)
        taxonomy.bins["Archive"] = TaxonomyBin(name="Archive", locked=False)
        taxonomy.rules["va"] = "VA"

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            temp_path = f.name

        try:
            save_taxonomy(taxonomy, temp_path)
            loaded = load_taxonomy(temp_path)

            assert loaded.version == "2.0"
            assert loaded.is_bin_locked("VA") is True
            assert loaded.is_bin_locked("Archive") is False
        finally:
            Path(temp_path).unlink()


class TestIsBinLocked:
    """Tests for is_bin_locked helper function."""

    def test_with_taxonomy_object_locked(self) -> None:
        """Test is_bin_locked with Taxonomy object (locked bin)."""
        taxonomy = Taxonomy()
        taxonomy.bins["VA"] = TaxonomyBin(name="VA", locked=True)

        assert is_bin_locked(taxonomy, "VA") is True

    def test_with_taxonomy_object_unlocked(self) -> None:
        """Test is_bin_locked with Taxonomy object (unlocked bin)."""
        taxonomy = Taxonomy()
        taxonomy.bins["Temp"] = TaxonomyBin(name="Temp", locked=False)

        assert is_bin_locked(taxonomy, "Temp") is False

    def test_with_raw_dict_locked(self) -> None:
        """Test is_bin_locked with raw dict (locked bin)."""
        data = {"locked_bins": {"VA": True, "Finances Bin": True}}

        assert is_bin_locked(data, "VA") is True
        assert is_bin_locked(data, "Finances Bin") is True

    def test_with_raw_dict_unlocked(self) -> None:
        """Test is_bin_locked with raw dict (unlocked bin)."""
        data = {"locked_bins": {"VA": True, "Temp": False}}

        assert is_bin_locked(data, "Temp") is False

    def test_with_raw_dict_missing(self) -> None:
        """Test is_bin_locked with raw dict (missing bin)."""
        data = {"locked_bins": {"VA": True}}

        assert is_bin_locked(data, "NotThere") is False

    def test_with_no_locked_bins_field(self) -> None:
        """Test is_bin_locked when locked_bins field is missing."""
        data = {"canonical_roots": ["VA", "Archive"]}

        assert is_bin_locked(data, "VA") is False


class TestGetLockedBins:
    """Tests for get_locked_bins helper function."""

    def test_with_taxonomy_object(self) -> None:
        """Test get_locked_bins with Taxonomy object."""
        taxonomy = Taxonomy()
        taxonomy.bins["VA"] = TaxonomyBin(name="VA", locked=True)
        taxonomy.bins["Archive"] = TaxonomyBin(name="Archive", locked=True)
        taxonomy.bins["Temp"] = TaxonomyBin(name="Temp", locked=False)

        locked = get_locked_bins(taxonomy)
        assert len(locked) == 2
        assert "VA" in locked
        assert "Archive" in locked

    def test_with_raw_dict(self) -> None:
        """Test get_locked_bins with raw dict."""
        data = {
            "locked_bins": {
                "VA": True,
                "Finances Bin": True,
                "Temp": False,
            }
        }

        locked = get_locked_bins(data)
        assert len(locked) == 2
        assert "VA" in locked
        assert "Finances Bin" in locked

    def test_with_no_locked_bins(self) -> None:
        """Test get_locked_bins when no bins are locked."""
        data = {"locked_bins": {"VA": False, "Archive": False}}

        locked = get_locked_bins(data)
        assert len(locked) == 0


class TestValidateBinOperation:
    """Tests for validate_bin_operation function."""

    def test_rename_locked_bin_disallowed(self) -> None:
        """Test renaming a locked bin is disallowed."""
        taxonomy = Taxonomy()
        taxonomy.bins["VA"] = TaxonomyBin(name="VA", locked=True)

        allowed, reason = validate_bin_operation(taxonomy, "VA", "rename")
        assert allowed is False
        assert "locked" in reason.lower()
        assert "rename" in reason.lower()

    def test_move_locked_bin_disallowed(self) -> None:
        """Test moving a locked bin is disallowed."""
        taxonomy = Taxonomy()
        taxonomy.bins["Finances Bin"] = TaxonomyBin(name="Finances Bin", locked=True)

        allowed, reason = validate_bin_operation(taxonomy, "Finances Bin", "move")
        assert allowed is False
        assert "locked" in reason.lower()

    def test_merge_locked_bin_disallowed(self) -> None:
        """Test merging a locked bin is disallowed."""
        taxonomy = Taxonomy()
        taxonomy.bins["Work Bin"] = TaxonomyBin(name="Work Bin", locked=True)

        allowed, reason = validate_bin_operation(taxonomy, "Work Bin", "merge")
        assert allowed is False
        assert "locked" in reason.lower()

    def test_create_subcategory_allowed_on_locked(self) -> None:
        """Test creating subcategory on locked bin is allowed."""
        taxonomy = Taxonomy()
        taxonomy.bins["VA"] = TaxonomyBin(name="VA", locked=True)

        allowed, reason = validate_bin_operation(taxonomy, "VA", "create_subcategory")
        assert allowed is True

    def test_rename_unlocked_bin_allowed(self) -> None:
        """Test renaming an unlocked bin is allowed."""
        taxonomy = Taxonomy()
        taxonomy.bins["Temp"] = TaxonomyBin(name="Temp", locked=False)

        allowed, reason = validate_bin_operation(taxonomy, "Temp", "rename")
        assert allowed is True

    def test_unknown_operation_disallowed(self) -> None:
        """Test unknown operations are disallowed."""
        taxonomy = Taxonomy()
        taxonomy.bins["VA"] = TaxonomyBin(name="VA", locked=True)

        allowed, reason = validate_bin_operation(taxonomy, "VA", "delete")
        assert allowed is False
        assert "unknown" in reason.lower()

    def test_with_raw_dict(self) -> None:
        """Test validate_bin_operation with raw dict."""
        data = {"locked_bins": {"VA": True}}

        allowed, reason = validate_bin_operation(data, "VA", "rename")
        assert allowed is False

        allowed, reason = validate_bin_operation(data, "VA", "create_subcategory")
        assert allowed is True


class TestIsPathUnderLockedBin:
    """Tests for is_path_under_locked_bin function."""

    def test_path_under_locked_bin(self) -> None:
        """Test path under a locked bin."""
        taxonomy = Taxonomy()
        taxonomy.bins["VA"] = TaxonomyBin(name="VA", locked=True)

        is_locked, bin_name = is_path_under_locked_bin(taxonomy, "VA/Claims/2024")
        assert is_locked is True
        assert bin_name == "VA"

    def test_path_under_unlocked_bin(self) -> None:
        """Test path under an unlocked bin."""
        taxonomy = Taxonomy()
        taxonomy.bins["Temp"] = TaxonomyBin(name="Temp", locked=False)

        is_locked, bin_name = is_path_under_locked_bin(taxonomy, "Temp/Projects")
        assert is_locked is False
        assert bin_name == ""

    def test_root_path_locked(self) -> None:
        """Test root path that is a locked bin."""
        taxonomy = Taxonomy()
        taxonomy.bins["VA"] = TaxonomyBin(name="VA", locked=True)

        is_locked, bin_name = is_path_under_locked_bin(taxonomy, "VA")
        assert is_locked is True
        assert bin_name == "VA"

    def test_empty_path(self) -> None:
        """Test empty path."""
        taxonomy = Taxonomy()
        taxonomy.bins["VA"] = TaxonomyBin(name="VA", locked=True)

        is_locked, bin_name = is_path_under_locked_bin(taxonomy, "")
        assert is_locked is False
        assert bin_name == ""

    def test_windows_path_separator(self) -> None:
        """Test path with Windows separator."""
        taxonomy = Taxonomy()
        taxonomy.bins["VA"] = TaxonomyBin(name="VA", locked=True)

        is_locked, bin_name = is_path_under_locked_bin(taxonomy, "VA\\Claims\\2024")
        assert is_locked is True
        assert bin_name == "VA"

    def test_with_raw_dict(self) -> None:
        """Test is_path_under_locked_bin with raw dict."""
        data = {"locked_bins": {"Finances Bin": True}}

        is_locked, bin_name = is_path_under_locked_bin(
            data, "Finances Bin/Taxes/2024"
        )
        assert is_locked is True
        assert bin_name == "Finances Bin"


class TestCreateDefaultTaxonomy:
    """Tests for create_default_taxonomy function."""

    def test_creates_standard_bins(self) -> None:
        """Test default taxonomy has standard bins."""
        taxonomy = create_default_taxonomy()

        expected_bins = [
            "Family Bin",
            "Finances Bin",
            "Legal Bin",
            "Personal Bin",
            "Work Bin",
            "VA",
            "Archive",
            "Needs-Review",
        ]

        for bin_name in expected_bins:
            assert bin_name in taxonomy.bins

    def test_all_bins_locked_by_default(self) -> None:
        """Test all default bins are locked."""
        taxonomy = create_default_taxonomy()

        for bin_obj in taxonomy.bins.values():
            assert bin_obj.locked is True

    def test_has_version(self) -> None:
        """Test default taxonomy has version."""
        taxonomy = create_default_taxonomy()
        assert taxonomy.version != ""

    def test_has_description(self) -> None:
        """Test default taxonomy has description."""
        taxonomy = create_default_taxonomy()
        assert "locked" in taxonomy.description.lower()


class TestIntegrationWithRealTaxonomy:
    """Integration tests with realistic taxonomy structure."""

    def test_full_taxonomy_workflow(self) -> None:
        """Test creating, saving, loading, and validating taxonomy."""
        # Create taxonomy
        taxonomy = Taxonomy(
            version="2026-03-03",
            description="Full workflow test",
        )

        # Add locked root bins
        root_bins = ["VA", "Finances Bin", "Work Bin", "Archive"]
        for name in root_bins:
            taxonomy.bins[name] = TaxonomyBin(name=name, locked=True)

        # Add one unlocked bin
        taxonomy.bins["Temp"] = TaxonomyBin(name="Temp", locked=False)

        # Save and reload
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            temp_path = f.name

        try:
            save_taxonomy(taxonomy, temp_path)
            loaded = load_taxonomy(temp_path)

            # Verify locked status
            assert loaded.is_bin_locked("VA") is True
            assert loaded.is_bin_locked("Finances Bin") is True
            assert loaded.is_bin_locked("Temp") is False

            # Verify operations
            allowed, _ = validate_bin_operation(loaded, "VA", "rename")
            assert allowed is False

            allowed, _ = validate_bin_operation(loaded, "VA", "create_subcategory")
            assert allowed is True

            allowed, _ = validate_bin_operation(loaded, "Temp", "rename")
            assert allowed is True

            # Verify path checking
            is_locked, bin_name = is_path_under_locked_bin(
                loaded, "VA/Claims/PTSD/2024"
            )
            assert is_locked is True
            assert bin_name == "VA"

        finally:
            Path(temp_path).unlink()

    def test_agent_cannot_modify_locked_bins(self) -> None:
        """Test that locked bins cannot be modified by agent operations.

        This represents the core requirement from Phase 12:
        'Locked bins cannot be renamed, moved, or merged by the agent'
        """
        taxonomy = create_default_taxonomy()

        # All standard bins should be locked
        for bin_name in ["VA", "Finances Bin", "Work Bin", "Legal Bin"]:
            # Cannot rename
            allowed, _ = validate_bin_operation(taxonomy, bin_name, "rename")
            assert allowed is False, f"{bin_name} should not allow rename"

            # Cannot move
            allowed, _ = validate_bin_operation(taxonomy, bin_name, "move")
            assert allowed is False, f"{bin_name} should not allow move"

            # Cannot merge
            allowed, _ = validate_bin_operation(taxonomy, bin_name, "merge")
            assert allowed is False, f"{bin_name} should not allow merge"

            # Can create subcategory
            allowed, _ = validate_bin_operation(
                taxonomy, bin_name, "create_subcategory"
            )
            assert allowed is True, f"{bin_name} should allow create_subcategory"
