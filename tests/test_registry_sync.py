"""Tests for registry_sync module."""

import json
import pytest

from organizer.registry_sync import (
    SyncReport,
    load_taxonomy_paths,
    load_registry_mappings,
    check_registry_against_taxonomy,
    resync_registry_with_taxonomy,
    get_valid_bins_from_taxonomy,
    get_subcategories_from_taxonomy,
    is_valid_registry_destination,
)


@pytest.fixture
def sample_taxonomy(tmp_path):
    """Create a sample taxonomy file."""
    taxonomy = {
        "version": "2026-03-03",
        "description": "Test taxonomy",
        "canonical_roots": [
            "Family Bin",
            "Finances Bin",
            "Work Bin",
            "Archive",
            "Needs-Review",
        ],
        "locked_bins": {
            "Family Bin": True,
            "Finances Bin": True,
            "Work Bin": True,
            "Archive": True,
            "Needs-Review": True,
        },
        "rules": {
            "family_members": "Family Bin",
            "taxes_banking": "Finances Bin",
            "legacy_dev": "Archive/Legacy-Dev-Tools",
        },
        "family_members": {
            "alice": "Family Bin/Alice",
            "bob": "Family Bin/Bob",
        },
        "finance_subcategories": {
            "taxes": "Finances Bin/Taxes",
            "banking": "Finances Bin/Banking",
        },
    }
    taxonomy_path = tmp_path / "ROOT_TAXONOMY.json"
    with open(taxonomy_path, "w") as f:
        json.dump(taxonomy, f)
    return taxonomy_path


@pytest.fixture
def sample_registry(tmp_path):
    """Create a sample registry file."""
    registry = {
        "_version": "test",
        "_description": "Test registry",
        "_total_mappings": 10,
        "mappings": {
            "Alice Docs": "Family Bin/Alice",
            "Bob Files": "Family Bin/Bob",
            "Tax 2024": "Finances Bin/Taxes",
            "Bank Statements": "Finances Bin/Banking",
            "Old Code": "Archive/Legacy-Dev-Tools",
            "Random": "Needs-Review",
            "Screenshots": "__KEEP_AT_ROOT__",
            # Orphaned entry - destination doesn't exist in taxonomy
            "Mystery Folder": "Invalid Bin/Mystery",
            "Another Mystery": "Nonexistent/Path",
        },
    }
    registry_path = tmp_path / "canonical_registry.json"
    with open(registry_path, "w") as f:
        json.dump(registry, f)
    return registry_path


class TestSyncReport:
    """Tests for SyncReport dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        report = SyncReport(
            orphaned_entries={"a": "b"},
            missing_entries=["c"],
            valid_entries={"d": "e"},
            special_entries={"f": "__KEEP__"},
        )
        result = report.to_dict()
        assert result["orphaned_count"] == 1
        assert result["missing_count"] == 1
        assert result["valid_count"] == 1
        assert result["special_count"] == 1
        assert "a" in result["orphaned_entries"]
        assert "c" in result["missing_entries"]

    def test_summary_basic(self):
        """Test summary generation."""
        report = SyncReport(
            valid_entries={"a": "b", "c": "d"},
            orphaned_entries={"x": "y"},
        )
        summary = report.summary()
        assert "Valid entries: 2" in summary
        assert "Orphaned entries: 1" in summary

    def test_summary_with_many_orphans(self):
        """Test summary truncation with many orphaned entries."""
        orphaned = {f"folder_{i}": f"path_{i}" for i in range(15)}
        report = SyncReport(orphaned_entries=orphaned)
        summary = report.summary()
        assert "... and 5 more" in summary


class TestLoadTaxonomyPaths:
    """Tests for load_taxonomy_paths function."""

    def test_loads_canonical_roots(self, sample_taxonomy):
        """Test that canonical roots are loaded."""
        paths = load_taxonomy_paths(sample_taxonomy)
        assert "Family Bin" in paths
        assert "Finances Bin" in paths
        assert "Work Bin" in paths
        assert "Archive" in paths
        assert "Needs-Review" in paths

    def test_loads_family_members(self, sample_taxonomy):
        """Test that family member paths are loaded."""
        paths = load_taxonomy_paths(sample_taxonomy)
        assert "Family Bin/Alice" in paths
        assert "Family Bin/Bob" in paths

    def test_loads_finance_subcategories(self, sample_taxonomy):
        """Test that finance subcategory paths are loaded."""
        paths = load_taxonomy_paths(sample_taxonomy)
        assert "Finances Bin/Taxes" in paths
        assert "Finances Bin/Banking" in paths

    def test_loads_rule_destinations(self, sample_taxonomy):
        """Test that rule destination paths are loaded."""
        paths = load_taxonomy_paths(sample_taxonomy)
        assert "Archive/Legacy-Dev-Tools" in paths

    def test_file_not_found(self, tmp_path):
        """Test FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            load_taxonomy_paths(tmp_path / "nonexistent.json")


class TestLoadRegistryMappings:
    """Tests for load_registry_mappings function."""

    def test_loads_mappings(self, sample_registry):
        """Test that mappings are loaded correctly."""
        mappings, data = load_registry_mappings(sample_registry)
        assert "Alice Docs" in mappings
        assert mappings["Alice Docs"] == "Family Bin/Alice"
        assert "Tax 2024" in mappings
        assert "Screenshots" in mappings

    def test_returns_full_data(self, sample_registry):
        """Test that full registry data is returned."""
        mappings, data = load_registry_mappings(sample_registry)
        assert "_version" in data
        assert "_description" in data
        assert "mappings" in data

    def test_file_not_found(self, tmp_path):
        """Test FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            load_registry_mappings(tmp_path / "nonexistent.json")


class TestCheckRegistryAgainstTaxonomy:
    """Tests for check_registry_against_taxonomy function."""

    def test_identifies_valid_entries(self, sample_registry, sample_taxonomy):
        """Test that valid entries are identified."""
        report = check_registry_against_taxonomy(sample_registry, sample_taxonomy)
        assert "Alice Docs" in report.valid_entries
        assert "Tax 2024" in report.valid_entries
        assert "Bank Statements" in report.valid_entries
        assert "Old Code" in report.valid_entries
        assert "Random" in report.valid_entries

    def test_identifies_orphaned_entries(self, sample_registry, sample_taxonomy):
        """Test that orphaned entries are identified."""
        report = check_registry_against_taxonomy(sample_registry, sample_taxonomy)
        assert "Mystery Folder" in report.orphaned_entries
        assert "Another Mystery" in report.orphaned_entries

    def test_identifies_special_entries(self, sample_registry, sample_taxonomy):
        """Test that special entries are identified."""
        report = check_registry_against_taxonomy(sample_registry, sample_taxonomy)
        assert "Screenshots" in report.special_entries
        assert report.special_entries["Screenshots"] == "__KEEP_AT_ROOT__"

    def test_counts_are_correct(self, sample_registry, sample_taxonomy):
        """Test that counts in report are correct."""
        report = check_registry_against_taxonomy(sample_registry, sample_taxonomy)
        # 6 valid: Alice Docs, Bob Files, Tax 2024, Bank Statements, Old Code, Random
        assert len(report.valid_entries) == 6
        # 2 orphaned: Mystery Folder, Another Mystery
        assert len(report.orphaned_entries) == 2
        # 1 special: Screenshots
        assert len(report.special_entries) == 1


class TestResyncRegistryWithTaxonomy:
    """Tests for resync_registry_with_taxonomy function."""

    def test_dry_run_does_not_modify(self, sample_registry, sample_taxonomy):
        """Test that dry run doesn't modify the registry."""
        original_content = sample_registry.read_text()
        resync_registry_with_taxonomy(
            sample_registry, sample_taxonomy, dry_run=True
        )
        assert sample_registry.read_text() == original_content

    def test_remove_orphans(self, sample_registry, sample_taxonomy):
        """Test removal of orphaned entries."""
        resync_registry_with_taxonomy(
            sample_registry,
            sample_taxonomy,
            remove_orphans=True,
            dry_run=False,
        )
        # Reload and verify orphans are gone
        mappings, _ = load_registry_mappings(sample_registry)
        assert "Mystery Folder" not in mappings
        assert "Another Mystery" not in mappings
        # Valid entries should still exist
        assert "Alice Docs" in mappings

    def test_add_missing(self, tmp_path):
        """Test adding missing taxonomy paths."""
        # Create minimal taxonomy
        taxonomy = {
            "version": "test",
            "canonical_roots": ["Bin A", "Bin B"],
            "locked_bins": {"Bin A": True, "Bin B": True},
            "rules": {},
        }
        taxonomy_path = tmp_path / "taxonomy.json"
        with open(taxonomy_path, "w") as f:
            json.dump(taxonomy, f)

        # Create registry with only one mapping
        registry = {
            "_version": "test",
            "mappings": {"Folder A": "Bin A"},
        }
        registry_path = tmp_path / "registry.json"
        with open(registry_path, "w") as f:
            json.dump(registry, f)

        # Resync with add_missing
        resync_registry_with_taxonomy(
            registry_path,
            taxonomy_path,
            add_missing=True,
            dry_run=False,
        )

        # Reload and verify
        mappings, _ = load_registry_mappings(registry_path)
        # "Bin B" should be added as missing
        assert "Bin B" in mappings

    def test_preserves_special_entries(self, sample_registry, sample_taxonomy):
        """Test that special entries are preserved during resync."""
        resync_registry_with_taxonomy(
            sample_registry,
            sample_taxonomy,
            remove_orphans=True,
            dry_run=False,
        )
        mappings, _ = load_registry_mappings(sample_registry)
        assert "Screenshots" in mappings
        assert mappings["Screenshots"] == "__KEEP_AT_ROOT__"

    def test_updates_total_count(self, sample_registry, sample_taxonomy):
        """Test that total mapping count is updated."""
        resync_registry_with_taxonomy(
            sample_registry,
            sample_taxonomy,
            remove_orphans=True,
            dry_run=False,
        )
        _, data = load_registry_mappings(sample_registry)
        # Should have 7 entries (9 original - 2 orphaned)
        assert data["_total_mappings"] == 7


class TestGetValidBinsFromTaxonomy:
    """Tests for get_valid_bins_from_taxonomy function."""

    def test_returns_all_bins(self, sample_taxonomy):
        """Test that all root bins are returned."""
        bins = get_valid_bins_from_taxonomy(sample_taxonomy)
        assert "Family Bin" in bins
        assert "Finances Bin" in bins
        assert "Work Bin" in bins
        assert "Archive" in bins
        assert "Needs-Review" in bins
        assert len(bins) == 5


class TestGetSubcategoriesFromTaxonomy:
    """Tests for get_subcategories_from_taxonomy function."""

    def test_returns_family_subcategories(self, sample_taxonomy):
        """Test family member subcategories are returned."""
        subcats = get_subcategories_from_taxonomy(sample_taxonomy)
        assert "Family Bin" in subcats
        assert "Family Bin/Alice" in subcats["Family Bin"]
        assert "Family Bin/Bob" in subcats["Family Bin"]

    def test_returns_finance_subcategories(self, sample_taxonomy):
        """Test finance subcategories are returned."""
        subcats = get_subcategories_from_taxonomy(sample_taxonomy)
        assert "Finances Bin" in subcats
        assert "Finances Bin/Taxes" in subcats["Finances Bin"]
        assert "Finances Bin/Banking" in subcats["Finances Bin"]

    def test_returns_rule_subcategories(self, sample_taxonomy):
        """Test rule-based subcategories are returned."""
        subcats = get_subcategories_from_taxonomy(sample_taxonomy)
        assert "Archive" in subcats
        assert "Archive/Legacy-Dev-Tools" in subcats["Archive"]


class TestIsValidRegistryDestination:
    """Tests for is_valid_registry_destination function."""

    def test_special_entry_valid(self, sample_taxonomy):
        """Test that special entries are valid."""
        assert is_valid_registry_destination("__KEEP_AT_ROOT__", sample_taxonomy)
        assert is_valid_registry_destination("__SPECIAL__", sample_taxonomy)

    def test_exact_match_valid(self, sample_taxonomy):
        """Test that exact taxonomy paths are valid."""
        assert is_valid_registry_destination("Family Bin", sample_taxonomy)
        assert is_valid_registry_destination("Family Bin/Alice", sample_taxonomy)
        assert is_valid_registry_destination("Finances Bin/Taxes", sample_taxonomy)

    def test_under_valid_bin_valid(self, sample_taxonomy):
        """Test that paths under valid bins are valid."""
        # Even if the exact path isn't in taxonomy, being under a valid bin is OK
        assert is_valid_registry_destination("Family Bin/NewMember", sample_taxonomy)
        assert is_valid_registry_destination(
            "Archive/Legacy-Dev-Tools/SubFolder", sample_taxonomy
        )

    def test_invalid_bin_invalid(self, sample_taxonomy):
        """Test that paths under invalid bins are invalid."""
        assert not is_valid_registry_destination("Invalid Bin/Something", sample_taxonomy)
        assert not is_valid_registry_destination("Nonexistent", sample_taxonomy)


class TestIntegration:
    """Integration tests for registry sync workflow."""

    def test_full_sync_workflow(self, tmp_path):
        """Test complete sync workflow with realistic data."""
        # Create taxonomy
        taxonomy = {
            "version": "2026-03-03",
            "description": "Integration test taxonomy",
            "canonical_roots": ["Personal", "Work", "Archive"],
            "locked_bins": {"Personal": True, "Work": True, "Archive": True},
            "rules": {"old_stuff": "Archive/Legacy"},
            "family_members": {},
            "finance_subcategories": {},
        }
        taxonomy_path = tmp_path / "taxonomy.json"
        with open(taxonomy_path, "w") as f:
            json.dump(taxonomy, f)

        # Create registry with mixed valid/invalid entries
        registry = {
            "_version": "test",
            "_total_mappings": 5,
            "mappings": {
                "My Docs": "Personal",
                "Projects": "Work",
                "Old Stuff": "Archive/Legacy",
                "Keep This": "__KEEP_AT_ROOT__",
                "Bad Entry": "NonexistentBin/Path",
            },
        }
        registry_path = tmp_path / "registry.json"
        with open(registry_path, "w") as f:
            json.dump(registry, f)

        # Step 1: Check current state
        report = check_registry_against_taxonomy(registry_path, taxonomy_path)
        assert len(report.valid_entries) == 3
        assert len(report.orphaned_entries) == 1
        assert len(report.special_entries) == 1

        # Step 2: Fix issues
        resync_registry_with_taxonomy(
            registry_path,
            taxonomy_path,
            remove_orphans=True,
            dry_run=False,
        )

        # Step 3: Verify fixed state
        report = check_registry_against_taxonomy(registry_path, taxonomy_path)
        assert len(report.orphaned_entries) == 0
        assert len(report.valid_entries) == 3
        assert len(report.special_entries) == 1

    def test_real_taxonomy_structure(self, tmp_path):
        """Test with taxonomy structure matching production."""
        taxonomy = {
            "version": "2026-03-03",
            "description": "Production-like taxonomy",
            "canonical_roots": [
                "Family Bin",
                "Finances Bin",
                "Legal Bin",
                "Personal Bin",
                "Work Bin",
                "VA",
                "Archive",
                "Needs-Review",
            ],
            "locked_bins": {
                "Family Bin": True,
                "Finances Bin": True,
                "Legal Bin": True,
                "Personal Bin": True,
                "Work Bin": True,
                "VA": True,
                "Archive": True,
                "Needs-Review": True,
            },
            "rules": {
                "family_members": "Family Bin",
                "taxes_banking": "Finances Bin",
                "va_claims": "VA",
                "legacy_dev": "Archive/Legacy-Dev-Tools",
            },
            "family_members": {
                "camila": "Family Bin/Camila",
                "hudson": "Family Bin/Hudson",
            },
            "finance_subcategories": {
                "taxes": "Finances Bin/Taxes",
                "banking": "Finances Bin/Banking",
            },
        }
        taxonomy_path = tmp_path / "ROOT_TAXONOMY.json"
        with open(taxonomy_path, "w") as f:
            json.dump(taxonomy, f)

        # Registry with production-like entries
        registry = {
            "_version": "2026-02-22-final",
            "_total_mappings": 8,
            "mappings": {
                "Camila": "Family Bin/Camila",
                "Hudson": "Family Bin/Hudson",
                "Tax 2024": "Finances Bin/Taxes",
                "VA Claims": "VA",
                "Old Code": "Archive/Legacy-Dev-Tools",
                "Unknown": "Needs-Review",
                "Screenshots": "__KEEP_AT_ROOT__",
                # Orphaned - should be removed
                "Mystery": "Fake Bin/Path",
            },
        }
        registry_path = tmp_path / "canonical_registry.json"
        with open(registry_path, "w") as f:
            json.dump(registry, f)

        # Check and fix
        report = check_registry_against_taxonomy(registry_path, taxonomy_path)
        assert "Mystery" in report.orphaned_entries
        assert "Camila" in report.valid_entries
        assert "Screenshots" in report.special_entries

        # Resync
        resync_registry_with_taxonomy(
            registry_path,
            taxonomy_path,
            remove_orphans=True,
            dry_run=False,
        )

        # Verify clean state
        final_report = check_registry_against_taxonomy(registry_path, taxonomy_path)
        assert len(final_report.orphaned_entries) == 0
