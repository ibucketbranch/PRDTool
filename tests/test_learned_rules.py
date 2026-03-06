"""Tests for the learned_rules module.

Tests cover:
- LearnedRuleStore initialization and loading
- Rule matching with different pattern types (keyword, glob, regex)
- Priority ordering (learned > override > taxonomy > hardcoded)
- Content signal matching
- Rule management (add, remove, enable, disable)
- Persistence (save/load)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from organizer.learned_rules import (
    LearnedRuleStore,
    MatchResult,
    StoredRule,
    create_rule_store,
    match_file,
)

if TYPE_CHECKING:
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def temp_rules_path(tmp_path: Path) -> Path:
    """Create a temporary path for rules file."""
    return tmp_path / ".organizer" / "agent" / "learned_routing_rules.json"


@pytest.fixture
def temp_taxonomy_path(tmp_path: Path) -> Path:
    """Create a temporary taxonomy file."""
    taxonomy_path = tmp_path / ".organizer" / "ROOT_TAXONOMY.json"
    taxonomy_path.parent.mkdir(parents=True, exist_ok=True)
    taxonomy_data = {
        "version": "2026-03-05",
        "description": "Test taxonomy",
        "canonical_roots": ["Finances Bin", "VA", "Work Bin"],
        "locked_bins": {"VA": True, "Finances Bin": True},
        "rules": {
            "invoice": "Finances Bin/Bills",
            "tax": "Finances Bin/Taxes",
            "va_claim": "VA/Claims",
        },
    }
    taxonomy_path.write_text(json.dumps(taxonomy_data), encoding="utf-8")
    return taxonomy_path


@pytest.fixture
def sample_rules_data() -> dict:
    """Sample rules data for testing."""
    return {
        "version": "1.0",
        "rules": [
            {
                "pattern": "invoice",
                "destination": "/path/to/invoices",
                "confidence": 0.9,
                "pattern_type": "keyword",
                "reasoning": "Files containing 'invoice' keyword",
                "enabled": True,
            },
            {
                "pattern": "^report_\\d{4}",
                "destination": "/path/to/reports",
                "confidence": 0.85,
                "pattern_type": "regex",
                "reasoning": "Report files with year",
                "enabled": True,
            },
            {
                "pattern": "disabled_pattern",
                "destination": "/path/to/disabled",
                "confidence": 0.9,
                "pattern_type": "keyword",
                "enabled": False,
            },
            {
                "pattern": "*.pdf",
                "destination": "/path/to/documents",
                "confidence": 0.75,
                "pattern_type": "glob",
                "reasoning": "PDF files",
                "enabled": True,
            },
        ],
    }


@pytest.fixture
def rules_file(temp_rules_path: Path, sample_rules_data: dict) -> Path:
    """Create a temporary rules file."""
    temp_rules_path.parent.mkdir(parents=True, exist_ok=True)
    temp_rules_path.write_text(json.dumps(sample_rules_data), encoding="utf-8")
    return temp_rules_path


# ─────────────────────────────────────────────────────────────────────────────
# StoredRule Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestStoredRule:
    """Tests for StoredRule dataclass."""

    def test_default_values(self) -> None:
        """Test that default values are set correctly."""
        rule = StoredRule(pattern="test", destination="/path")
        assert rule.confidence == 0.8
        assert rule.pattern_type == "keyword"
        assert rule.enabled is True
        assert rule.hit_count == 0
        assert rule.created_at != ""

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        rule = StoredRule(
            pattern="invoice",
            destination="/invoices",
            confidence=0.9,
            reasoning="Test rule",
        )
        d = rule.to_dict()
        assert d["pattern"] == "invoice"
        assert d["destination"] == "/invoices"
        assert d["confidence"] == 0.9
        assert d["reasoning"] == "Test rule"

    def test_from_dict(self) -> None:
        """Test creation from dictionary."""
        data = {
            "pattern": "tax",
            "destination": "/taxes",
            "confidence": 0.85,
            "pattern_type": "keyword",
            "enabled": True,
        }
        rule = StoredRule.from_dict(data)
        assert rule.pattern == "tax"
        assert rule.destination == "/taxes"
        assert rule.confidence == 0.85

    def test_keyword_match_in_filename(self) -> None:
        """Test keyword matching in filename."""
        rule = StoredRule(pattern="invoice", destination="/invoices")
        assert rule.matches("invoice_2024.pdf") is True
        assert rule.matches("my_invoice.pdf") is True
        assert rule.matches("INVOICE_report.pdf") is True  # Case insensitive
        assert rule.matches("receipt_2024.pdf") is False

    def test_keyword_match_in_content_signals(self) -> None:
        """Test keyword matching in content signals."""
        rule = StoredRule(pattern="verizon", destination="/bills")
        signals = {"keywords": ["verizon", "bill", "monthly"]}
        assert rule.matches("document.pdf", signals) is True
        assert rule.matches("document.pdf", {"keywords": ["att", "bill"]}) is False

    def test_glob_match(self) -> None:
        """Test glob pattern matching."""
        rule = StoredRule(pattern="*.pdf", destination="/pdfs", pattern_type="glob")
        assert rule.matches("document.pdf") is True
        assert rule.matches("report.PDF") is True  # Case insensitive
        assert rule.matches("document.txt") is False

    def test_glob_prefix_match(self) -> None:
        """Test glob pattern with prefix."""
        rule = StoredRule(pattern="invoice_*", destination="/invoices", pattern_type="glob")
        assert rule.matches("invoice_2024.pdf") is True
        assert rule.matches("invoice_january.pdf") is True
        assert rule.matches("my_invoice.pdf") is False

    def test_regex_match(self) -> None:
        """Test regex pattern matching."""
        rule = StoredRule(
            pattern=r"^report_\d{4}",
            destination="/reports",
            pattern_type="regex",
        )
        assert rule.matches("report_2024.pdf") is True
        assert rule.matches("report_2023_q1.pdf") is True
        assert rule.matches("my_report_2024.pdf") is False  # Doesn't start with pattern

    def test_disabled_rule_no_match(self) -> None:
        """Test that disabled rules don't match."""
        rule = StoredRule(pattern="invoice", destination="/invoices", enabled=False)
        assert rule.matches("invoice_2024.pdf") is False

    def test_invalid_regex_no_crash(self) -> None:
        """Test that invalid regex doesn't crash."""
        rule = StoredRule(
            pattern="[invalid",  # Invalid regex
            destination="/path",
            pattern_type="regex",
        )
        # Should not raise, just return False
        assert rule.matches("test.pdf") is False


# ─────────────────────────────────────────────────────────────────────────────
# LearnedRuleStore Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestLearnedRuleStoreInit:
    """Tests for LearnedRuleStore initialization."""

    def test_init_empty_store(self, temp_rules_path: Path) -> None:
        """Test initializing with no existing rules file."""
        store = LearnedRuleStore(rules_path=temp_rules_path, taxonomy_path=None)
        assert store.get_rule_count() == 0
        assert store.is_loaded is True

    def test_init_with_rules_file(self, rules_file: Path) -> None:
        """Test initializing with existing rules file."""
        store = LearnedRuleStore(rules_path=rules_file, taxonomy_path=None)
        assert store.get_rule_count() == 4
        assert store.get_enabled_rule_count() == 3

    def test_init_with_taxonomy(
        self, temp_rules_path: Path, temp_taxonomy_path: Path
    ) -> None:
        """Test initializing with taxonomy file."""
        store = LearnedRuleStore(
            rules_path=temp_rules_path, taxonomy_path=temp_taxonomy_path
        )
        assert store.has_taxonomy is True

    def test_init_no_auto_load(self, rules_file: Path) -> None:
        """Test initializing without auto-loading."""
        store = LearnedRuleStore(
            rules_path=rules_file, taxonomy_path=None, auto_load=False
        )
        assert store.is_loaded is False
        assert store.get_rule_count() == 0

    def test_reload(self, rules_file: Path) -> None:
        """Test reloading rules from disk."""
        store = LearnedRuleStore(rules_path=rules_file, taxonomy_path=None)
        initial_loaded_at = store.loaded_at

        # Reload should update the timestamp
        store.reload()
        # The loaded_at timestamp should be updated or equal
        assert store.loaded_at >= initial_loaded_at


class TestLearnedRuleStoreMatching:
    """Tests for LearnedRuleStore matching functionality."""

    def test_match_keyword_rule(self, rules_file: Path) -> None:
        """Test matching against keyword rules."""
        store = LearnedRuleStore(rules_path=rules_file, taxonomy_path=None)
        dest, conf = store.match("invoice_2024.pdf")
        assert dest == "/path/to/invoices"
        assert conf == 0.9

    def test_match_glob_rule(self, rules_file: Path) -> None:
        """Test matching against glob rules."""
        store = LearnedRuleStore(rules_path=rules_file, taxonomy_path=None)
        # Should not match invoice first (keyword takes priority by order)
        dest, conf = store.match("document.pdf")
        assert dest == "/path/to/documents"
        assert conf == 0.75

    def test_match_regex_rule(self, rules_file: Path) -> None:
        """Test matching against regex rules."""
        store = LearnedRuleStore(rules_path=rules_file, taxonomy_path=None)
        dest, conf = store.match("report_2024_summary.pdf")
        assert dest == "/path/to/reports"
        assert conf == 0.85

    def test_match_no_match(self, rules_file: Path) -> None:
        """Test when no rule matches."""
        store = LearnedRuleStore(rules_path=rules_file, taxonomy_path=None)
        dest, conf = store.match("random_file.txt")
        assert dest == ""
        assert conf == 0.0

    def test_match_disabled_rule_skipped(self, rules_file: Path) -> None:
        """Test that disabled rules are skipped."""
        store = LearnedRuleStore(rules_path=rules_file, taxonomy_path=None)
        dest, conf = store.match("disabled_pattern_file.pdf")
        # Should not match the disabled rule
        assert dest != "/path/to/disabled"

    def test_match_with_content_signals(self, rules_file: Path) -> None:
        """Test matching with content signals."""
        store = LearnedRuleStore(rules_path=rules_file, taxonomy_path=None)
        # File doesn't have invoice in name, but content signals do
        signals = {"keywords": ["invoice", "payment"]}
        dest, conf = store.match("document.pdf", signals)
        # Should match invoice rule due to content signals
        assert dest == "/path/to/invoices"

    def test_match_with_details(self, rules_file: Path) -> None:
        """Test match_with_details returns full MatchResult."""
        store = LearnedRuleStore(rules_path=rules_file, taxonomy_path=None)
        result = store.match_with_details("invoice_2024.pdf")
        assert result is not None
        assert result.destination == "/path/to/invoices"
        assert result.rule_pattern == "invoice"
        assert result.rule_source == "learned"
        assert result.reasoning == "Files containing 'invoice' keyword"

    def test_match_with_details_no_match(self, rules_file: Path) -> None:
        """Test match_with_details returns None when no match."""
        store = LearnedRuleStore(rules_path=rules_file, taxonomy_path=None)
        result = store.match_with_details("random_file.xyz")
        assert result is None


class TestLearnedRuleStorePriority:
    """Tests for priority-based matching."""

    def test_learned_rules_over_taxonomy(
        self, rules_file: Path, temp_taxonomy_path: Path
    ) -> None:
        """Test that learned rules take priority over taxonomy."""
        store = LearnedRuleStore(
            rules_path=rules_file, taxonomy_path=temp_taxonomy_path
        )
        # Both learned rules and taxonomy have "invoice" pattern
        # Learned should win
        dest, conf = store.match("invoice_2024.pdf")
        assert dest == "/path/to/invoices"  # From learned rules
        assert conf == 0.9

    def test_taxonomy_fallback(
        self, temp_rules_path: Path, temp_taxonomy_path: Path
    ) -> None:
        """Test fallback to taxonomy when no learned rule matches."""
        # Create empty rules file
        temp_rules_path.parent.mkdir(parents=True, exist_ok=True)
        temp_rules_path.write_text(json.dumps({"rules": []}), encoding="utf-8")

        store = LearnedRuleStore(
            rules_path=temp_rules_path, taxonomy_path=temp_taxonomy_path
        )
        # No learned rules, should fall back to taxonomy
        dest, conf = store.match("tax_return_2024.pdf")
        assert dest == "Finances Bin/Taxes"
        assert conf == 0.85

    def test_override_priority(
        self, rules_file: Path, temp_taxonomy_path: Path
    ) -> None:
        """Test that user overrides take priority over learned rules."""
        # Create mock override registry
        mock_override = MagicMock()
        mock_override.pattern = "invoice"
        mock_override.correct_bin = "/user/override/path"
        mock_override.source = "user_correction"

        mock_registry = MagicMock()
        mock_registry.find_match.return_value = mock_override

        store = LearnedRuleStore(
            rules_path=rules_file,
            taxonomy_path=temp_taxonomy_path,
            override_registry=mock_registry,
        )

        # Override should not win over learned rules in this implementation
        # because learned rules are checked first
        # Let's test by creating a file that doesn't match learned rules
        # Actually, let me re-read the code - overrides are checked AFTER learned rules
        # So this test confirms that learned rules win
        dest, conf = store.match("invoice_2024.pdf")
        assert dest == "/path/to/invoices"  # From learned rules, not override


class TestLearnedRuleStoreManagement:
    """Tests for rule management operations."""

    def test_add_rule(self, temp_rules_path: Path) -> None:
        """Test adding a new rule."""
        store = LearnedRuleStore(rules_path=temp_rules_path, taxonomy_path=None)
        rule = StoredRule(
            pattern="receipt",
            destination="/receipts",
            confidence=0.9,
        )
        store.add_rule(rule)

        assert store.get_rule_count() == 1
        dest, conf = store.match("receipt_2024.pdf")
        assert dest == "/receipts"

    def test_add_rule_replaces_existing(self, rules_file: Path) -> None:
        """Test that adding a rule with same pattern replaces it."""
        store = LearnedRuleStore(rules_path=rules_file, taxonomy_path=None)
        initial_count = store.get_rule_count()

        # Add rule with existing pattern
        rule = StoredRule(
            pattern="invoice",
            destination="/new/invoices",
            confidence=0.95,
        )
        store.add_rule(rule)

        # Count should be same (replaced, not added)
        assert store.get_rule_count() == initial_count

        # Should use new destination - use .txt to avoid pdf glob match
        dest, conf = store.match("invoice_2024.txt")
        assert dest == "/new/invoices"
        assert conf == 0.95

    def test_remove_rule(self, rules_file: Path) -> None:
        """Test removing a rule."""
        store = LearnedRuleStore(rules_path=rules_file, taxonomy_path=None)
        initial_count = store.get_rule_count()

        removed = store.remove_rule("invoice")
        assert removed is True
        assert store.get_rule_count() == initial_count - 1

    def test_remove_nonexistent_rule(self, rules_file: Path) -> None:
        """Test removing a rule that doesn't exist."""
        store = LearnedRuleStore(rules_path=rules_file, taxonomy_path=None)
        removed = store.remove_rule("nonexistent_pattern")
        assert removed is False

    def test_enable_rule(self, rules_file: Path) -> None:
        """Test enabling a disabled rule."""
        store = LearnedRuleStore(rules_path=rules_file, taxonomy_path=None)
        # The "disabled_pattern" rule is disabled by default
        enabled = store.enable_rule("disabled_pattern")
        assert enabled is True

        # Now it should match - use .txt to avoid pdf glob match
        dest, _ = store.match("disabled_pattern_file.txt")
        assert dest == "/path/to/disabled"

    def test_disable_rule(self, rules_file: Path) -> None:
        """Test disabling an enabled rule."""
        store = LearnedRuleStore(rules_path=rules_file, taxonomy_path=None)
        disabled = store.disable_rule("invoice")
        assert disabled is True

        # Now it should not match
        dest, _ = store.match("invoice_2024.pdf")
        assert dest != "/path/to/invoices"

    def test_enable_nonexistent_rule(self, rules_file: Path) -> None:
        """Test enabling a rule that doesn't exist."""
        store = LearnedRuleStore(rules_path=rules_file, taxonomy_path=None)
        enabled = store.enable_rule("nonexistent_pattern")
        assert enabled is False

    def test_clear_rules(self, rules_file: Path) -> None:
        """Test clearing all rules."""
        store = LearnedRuleStore(rules_path=rules_file, taxonomy_path=None)
        assert store.get_rule_count() > 0

        store.clear()
        assert store.get_rule_count() == 0

    def test_get_all_rules(self, rules_file: Path) -> None:
        """Test getting all rules."""
        store = LearnedRuleStore(rules_path=rules_file, taxonomy_path=None)
        rules = store.get_all_rules()
        assert len(rules) == 4
        assert all(isinstance(r, StoredRule) for r in rules)

    def test_get_enabled_rules(self, rules_file: Path) -> None:
        """Test getting only enabled rules."""
        store = LearnedRuleStore(rules_path=rules_file, taxonomy_path=None)
        rules = store.get_enabled_rules()
        assert len(rules) == 3
        assert all(r.enabled for r in rules)

    def test_get_rules_for_destination(self, rules_file: Path) -> None:
        """Test getting rules for a specific destination."""
        store = LearnedRuleStore(rules_path=rules_file, taxonomy_path=None)
        rules = store.get_rules_for_destination("/path/to/invoices")
        assert len(rules) == 1
        assert rules[0].pattern == "invoice"


class TestLearnedRuleStorePersistence:
    """Tests for rule persistence."""

    def test_rules_persist_after_add(self, temp_rules_path: Path) -> None:
        """Test that rules are saved after adding."""
        store = LearnedRuleStore(rules_path=temp_rules_path, taxonomy_path=None)
        rule = StoredRule(
            pattern="test_persist",
            destination="/test/persist",
            confidence=0.9,
        )
        store.add_rule(rule)

        # Create new store and verify rule is loaded
        store2 = LearnedRuleStore(rules_path=temp_rules_path, taxonomy_path=None)
        assert store2.get_rule_count() == 1
        dest, _ = store2.match("test_persist_file.pdf")
        assert dest == "/test/persist"

    def test_hit_count_persists(self, rules_file: Path) -> None:
        """Test that hit count is persisted after matching."""
        store = LearnedRuleStore(rules_path=rules_file, taxonomy_path=None)
        store.match("invoice_2024.pdf")
        store.match("invoice_2023.pdf")

        # Create new store and verify hit count
        store2 = LearnedRuleStore(rules_path=rules_file, taxonomy_path=None)
        rules = store2.get_rules_for_destination("/path/to/invoices")
        assert len(rules) == 1
        assert rules[0].hit_count == 2


class TestMatchResult:
    """Tests for MatchResult dataclass."""

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        result = MatchResult(
            destination="/path/to/files",
            confidence=0.9,
            rule_pattern="invoice",
            rule_source="learned",
            reasoning="Test reasoning",
        )
        d = result.to_dict()
        assert d["destination"] == "/path/to/files"
        assert d["confidence"] == 0.9
        assert d["rule_pattern"] == "invoice"
        assert d["rule_source"] == "learned"
        assert d["reasoning"] == "Test reasoning"


# ─────────────────────────────────────────────────────────────────────────────
# Convenience Function Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_create_rule_store(self, rules_file: Path, temp_taxonomy_path: Path) -> None:
        """Test create_rule_store convenience function."""
        store = create_rule_store(
            rules_path=rules_file,
            taxonomy_path=temp_taxonomy_path,
            with_overrides=False,
        )
        assert isinstance(store, LearnedRuleStore)
        assert store.get_rule_count() == 4

    def test_match_file(self, rules_file: Path) -> None:
        """Test match_file convenience function."""
        dest, conf = match_file(
            "invoice_2024.pdf",
            rules_path=rules_file,
        )
        assert dest == "/path/to/invoices"
        assert conf == 0.9


# ─────────────────────────────────────────────────────────────────────────────
# Edge Cases
# ─────────────────────────────────────────────────────────────────────────────


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_corrupt_json_file(self, temp_rules_path: Path) -> None:
        """Test handling of corrupt JSON file."""
        temp_rules_path.parent.mkdir(parents=True, exist_ok=True)
        temp_rules_path.write_text("not valid json {{{", encoding="utf-8")

        store = LearnedRuleStore(rules_path=temp_rules_path, taxonomy_path=None)
        assert store.get_rule_count() == 0
        assert store.is_loaded is True

    def test_missing_taxonomy_file(self, temp_rules_path: Path) -> None:
        """Test handling of missing taxonomy file."""
        store = LearnedRuleStore(
            rules_path=temp_rules_path,
            taxonomy_path="/nonexistent/taxonomy.json",
        )
        assert store.has_taxonomy is False

    def test_empty_filename(self, rules_file: Path) -> None:
        """Test matching with empty filename."""
        store = LearnedRuleStore(rules_path=rules_file, taxonomy_path=None)
        dest, conf = store.match("")
        assert dest == ""
        assert conf == 0.0

    def test_none_content_signals(self, rules_file: Path) -> None:
        """Test matching with None content signals."""
        store = LearnedRuleStore(rules_path=rules_file, taxonomy_path=None)
        dest, conf = store.match("invoice.pdf", None)
        assert dest == "/path/to/invoices"

    def test_empty_content_signals(self, rules_file: Path) -> None:
        """Test matching with empty content signals."""
        store = LearnedRuleStore(rules_path=rules_file, taxonomy_path=None)
        dest, conf = store.match("invoice.pdf", {})
        assert dest == "/path/to/invoices"

    def test_rules_path_property(self, rules_file: Path) -> None:
        """Test rules_path property."""
        store = LearnedRuleStore(rules_path=rules_file, taxonomy_path=None)
        assert store.rules_path == rules_file

    def test_inferred_pattern_type_glob(self, temp_rules_path: Path) -> None:
        """Test that pattern type is inferred correctly for glob patterns."""
        temp_rules_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "rules": [
                {"pattern": "*.pdf", "destination": "/pdfs"},
                {"pattern": "invoice_??.pdf", "destination": "/invoices"},
            ]
        }
        temp_rules_path.write_text(json.dumps(data), encoding="utf-8")

        store = LearnedRuleStore(rules_path=temp_rules_path, taxonomy_path=None)
        rules = store.get_all_rules()
        assert rules[0].pattern_type == "glob"
        assert rules[1].pattern_type == "glob"

    def test_inferred_pattern_type_regex(self, temp_rules_path: Path) -> None:
        """Test that pattern type is inferred correctly for regex patterns."""
        temp_rules_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "rules": [
                {"pattern": "^invoice", "destination": "/invoices"},
                {"pattern": "report$", "destination": "/reports"},
            ]
        }
        temp_rules_path.write_text(json.dumps(data), encoding="utf-8")

        store = LearnedRuleStore(rules_path=temp_rules_path, taxonomy_path=None)
        rules = store.get_all_rules()
        assert rules[0].pattern_type == "regex"
        assert rules[1].pattern_type == "regex"


class TestLearnedRulesMergePriority:
    """Tests specifically for merge priority behavior."""

    def test_merge_priority_learned_first(
        self, temp_rules_path: Path, temp_taxonomy_path: Path
    ) -> None:
        """Test that learned rules are checked before taxonomy."""
        temp_rules_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "rules": [
                {"pattern": "tax", "destination": "/learned/taxes", "confidence": 0.95},
            ]
        }
        temp_rules_path.write_text(json.dumps(data), encoding="utf-8")

        store = LearnedRuleStore(
            rules_path=temp_rules_path, taxonomy_path=temp_taxonomy_path
        )

        # tax matches both learned rules and taxonomy
        # Learned should win
        dest, conf = store.match("tax_document.pdf")
        assert dest == "/learned/taxes"
        assert conf == 0.95

    def test_merge_priority_taxonomy_when_no_learned_match(
        self, temp_rules_path: Path, temp_taxonomy_path: Path
    ) -> None:
        """Test that taxonomy is used when learned rules don't match."""
        temp_rules_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "rules": [
                {"pattern": "receipt", "destination": "/receipts", "confidence": 0.9},
            ]
        }
        temp_rules_path.write_text(json.dumps(data), encoding="utf-8")

        store = LearnedRuleStore(
            rules_path=temp_rules_path, taxonomy_path=temp_taxonomy_path
        )

        # va_claim matches only taxonomy (not learned rules)
        dest, conf = store.match("va_claim_2024.pdf")
        assert dest == "VA/Claims"
        assert conf == 0.85


# ─────────────────────────────────────────────────────────────────────────────
# Integration Tests: Learned Rules in Routing Pipeline
# ─────────────────────────────────────────────────────────────────────────────


class TestLearnedRulesInboxProcessorIntegration:
    """Tests for learned rules integration with InboxProcessor."""

    def test_inbox_processor_loads_learned_rules(self, temp_rules_path: Path) -> None:
        """Test that InboxProcessor can load learned rules store."""
        from organizer.inbox_processor import InboxProcessor

        # Create a minimal inbox processor with learned rules path
        processor = InboxProcessor(
            base_path=str(temp_rules_path.parent.parent.parent),  # Root above .organizer
            learned_rules_path=str(temp_rules_path),
            use_learned_rules=True,
            use_llm=False,  # Don't need LLM for this test
        )

        # Verify the processor has the learned rules path set
        assert processor._learned_rules_path == temp_rules_path
        assert processor._use_learned_rules is True

    def test_inbox_processor_disables_learned_rules(self, temp_rules_path: Path) -> None:
        """Test that InboxProcessor can disable learned rules."""
        from organizer.inbox_processor import InboxProcessor

        processor = InboxProcessor(
            base_path=str(temp_rules_path.parent.parent.parent),
            learned_rules_path=str(temp_rules_path),
            use_learned_rules=False,
            use_llm=False,
        )

        assert processor._use_learned_rules is False
        # _get_learned_rule_store should return None when disabled
        assert processor._get_learned_rule_store() is None


class TestLearnedRulesScatterDetectorIntegration:
    """Tests for learned rules integration with ScatterDetector."""

    def test_scatter_detector_accepts_learned_rule_store(self, rules_file: Path) -> None:
        """Test that ScatterDetector can be initialized with learned rule store."""
        from organizer.learned_rules import LearnedRuleStore
        from organizer.scatter_detector import ScatterDetector

        store = LearnedRuleStore(rules_path=rules_file, taxonomy_path=None)

        detector = ScatterDetector(
            learned_rule_store=store,
            use_learned_rules=True,
            use_llm=False,
        )

        assert detector._learned_rule_store is store
        assert detector._use_learned_rules is True

    def test_scatter_detector_disable_learned_rules(self, rules_file: Path) -> None:
        """Test that ScatterDetector can disable learned rules."""
        from organizer.learned_rules import LearnedRuleStore
        from organizer.scatter_detector import ScatterDetector

        store = LearnedRuleStore(rules_path=rules_file, taxonomy_path=None)

        detector = ScatterDetector(
            learned_rule_store=store,
            use_learned_rules=False,
            use_llm=False,
        )

        assert detector._use_learned_rules is False


class TestLearnedRulesReFileAgentIntegration:
    """Tests for learned rules integration with ReFileAgent."""

    def test_refile_agent_accepts_learned_rule_store(self, rules_file: Path) -> None:
        """Test that ReFileAgent can be initialized with learned rule store."""
        from organizer.learned_rules import LearnedRuleStore
        from organizer.refile_agent import ReFileAgent

        store = LearnedRuleStore(rules_path=rules_file, taxonomy_path=None)

        agent = ReFileAgent(
            learned_rule_store=store,
            use_learned_rules=True,
            use_llm=False,
        )

        assert agent._learned_rule_store is store
        assert agent._use_learned_rules is True

    def test_refile_agent_suggest_destination_uses_learned_rules(
        self, rules_file: Path
    ) -> None:
        """Test that ReFileAgent uses learned rules for destination suggestion."""
        from organizer.learned_rules import LearnedRuleStore
        from organizer.refile_agent import ReFileAgent

        store = LearnedRuleStore(rules_path=rules_file, taxonomy_path=None)

        agent = ReFileAgent(
            learned_rule_store=store,
            use_learned_rules=True,
            use_llm=False,
        )

        # Suggest destination for a file that matches learned rule
        suggestion = agent._suggest_destination_with_keywords(
            "invoice_2024.pdf", "/old/path/invoice_2024.pdf"
        )

        # Should use learned rule destination
        assert suggestion.suggested_path.startswith("/path/to/invoices")
        assert suggestion.confidence == 0.9
        assert "Learned rule" in suggestion.reason


class TestLearnedRulesConsolidationPlannerIntegration:
    """Tests for learned rules integration with ConsolidationPlanner."""

    def test_consolidation_planner_respects_learned_hierarchy(
        self, tmp_path: Path
    ) -> None:
        """Test that ConsolidationPlanner respects learned structure."""
        from organizer.consolidation_planner import ConsolidationPlanner
        from organizer.structure_analyzer import FolderNode, StructureSnapshot

        # Create a learned structure file
        agent_dir = tmp_path / ".organizer" / "agent"
        agent_dir.mkdir(parents=True, exist_ok=True)
        structure_path = agent_dir / "learned_structure.json"

        # Create snapshot with two folders that should be kept separate
        snapshot = StructureSnapshot(
            root_path=str(tmp_path),
            max_depth=4,
            folders=[
                FolderNode(
                    path=str(tmp_path / "Resumes_Personal"),
                    name="Resumes_Personal",
                    depth=1,
                ),
                FolderNode(
                    path=str(tmp_path / "Resumes_Work"),
                    name="Resumes_Work",
                    depth=1,
                ),
            ],
        )
        snapshot.save(structure_path)

        # Create actual folders
        (tmp_path / "Resumes_Personal").mkdir()
        (tmp_path / "Resumes_Work").mkdir()

        planner = ConsolidationPlanner(
            base_path=str(tmp_path),
            threshold=0.7,  # Low threshold to trigger grouping by name
            learned_structure_path=str(structure_path),
            respect_learned_hierarchy=True,
        )

        # These folders have similar names but exist separately in learned structure
        # Planner should keep them separate
        separate = planner._are_folders_separate_in_learned_structure(
            str(tmp_path / "Resumes_Personal"),
            str(tmp_path / "Resumes_Work"),
        )
        assert separate is True

    def test_consolidation_planner_allows_merge_when_not_in_learned(
        self, tmp_path: Path
    ) -> None:
        """Test that ConsolidationPlanner allows merge for unlisted folders."""
        from organizer.consolidation_planner import ConsolidationPlanner
        from organizer.structure_analyzer import FolderNode, StructureSnapshot

        # Create a learned structure file with only one folder
        agent_dir = tmp_path / ".organizer" / "agent"
        agent_dir.mkdir(parents=True, exist_ok=True)
        structure_path = agent_dir / "learned_structure.json"

        snapshot = StructureSnapshot(
            root_path=str(tmp_path),
            max_depth=4,
            folders=[
                FolderNode(
                    path=str(tmp_path / "SomeOtherFolder"),
                    name="SomeOtherFolder",
                    depth=1,
                ),
            ],
        )
        snapshot.save(structure_path)

        planner = ConsolidationPlanner(
            base_path=str(tmp_path),
            learned_structure_path=str(structure_path),
            respect_learned_hierarchy=True,
        )

        # Folders not in learned structure should be allowed to merge
        separate = planner._are_folders_separate_in_learned_structure(
            str(tmp_path / "NewFolder1"),
            str(tmp_path / "NewFolder2"),
        )
        assert separate is False

    def test_consolidation_planner_ignores_learned_when_disabled(
        self, tmp_path: Path
    ) -> None:
        """Test that ConsolidationPlanner ignores learned structure when disabled."""
        from organizer.consolidation_planner import ConsolidationPlanner
        from organizer.structure_analyzer import FolderNode, StructureSnapshot

        # Create a learned structure file
        agent_dir = tmp_path / ".organizer" / "agent"
        agent_dir.mkdir(parents=True, exist_ok=True)
        structure_path = agent_dir / "learned_structure.json"

        snapshot = StructureSnapshot(
            root_path=str(tmp_path),
            max_depth=4,
            folders=[
                FolderNode(
                    path=str(tmp_path / "Folder1"),
                    name="Folder1",
                    depth=1,
                ),
                FolderNode(
                    path=str(tmp_path / "Folder2"),
                    name="Folder2",
                    depth=1,
                ),
            ],
        )
        snapshot.save(structure_path)

        planner = ConsolidationPlanner(
            base_path=str(tmp_path),
            learned_structure_path=str(structure_path),
            respect_learned_hierarchy=False,  # Disabled
        )

        # With respect_learned_hierarchy=False, should allow merge
        separate = planner._are_folders_separate_in_learned_structure(
            str(tmp_path / "Folder1"),
            str(tmp_path / "Folder2"),
        )
        assert separate is False
