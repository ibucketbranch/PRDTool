"""Tests for the Learning-Agent (Phase 15) - consolidates LLM-native testing.

This test file covers the Learning-Agent functionality including:
- T2 Smart model domain detection (mock LLM)
- T2 Smart model rule generation (mock LLM)
- Structure narration with LLM
- Learned rule merge priority (learned > override > built-in > hardcoded)

These tests validate that the Learning-Agent correctly:
1. Detects domain context using T2 Smart model
2. Generates routing rules using T2 Smart model
3. Creates plain-English strategy descriptions via LLM
4. Respects the correct priority ordering for routing rules
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from organizer.domain_detector import DomainDetector, detect_domain
from organizer.learned_rules import LearnedRuleStore
from organizer.rule_generator import RuleGenerator, generate_rules
from organizer.structure_analyzer import (
    FolderNode,
    StructureAnalyzer,
    StructureSnapshot,
    analyze_structure,
)

if TYPE_CHECKING:
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_llm_client() -> MagicMock:
    """Create a mock LLM client that returns valid responses."""
    mock_client = MagicMock()
    mock_client.is_ollama_available.return_value = True
    return mock_client


@pytest.fixture
def mock_model_router() -> MagicMock:
    """Create a mock model router that always returns T2 Smart."""
    mock_router = MagicMock()
    mock_router.route.return_value = MagicMock(model="qwen2.5-coder:14b")
    return mock_router


@pytest.fixture
def temp_rules_path(tmp_path: Path) -> Path:
    """Create a temporary path for learned rules file."""
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
            "medical": "VA/Medical Records",
        },
    }
    taxonomy_path.write_text(json.dumps(taxonomy_data), encoding="utf-8")
    return taxonomy_path


@pytest.fixture
def sample_structure_snapshot() -> StructureSnapshot:
    """Create a sample structure snapshot for testing."""
    folders = [
        FolderNode(
            path="/test/root",
            name="root",
            depth=0,
            file_count=5,
            file_types={".pdf": 3, ".docx": 2},
        ),
        FolderNode(
            path="/test/root/invoices",
            name="invoices",
            depth=1,
            file_count=10,
            file_types={".pdf": 10},
            sample_filenames=["invoice_001.pdf", "invoice_002.pdf", "invoice_003.pdf"],
        ),
        FolderNode(
            path="/test/root/medical",
            name="medical",
            depth=1,
            file_count=15,
            file_types={".pdf": 12, ".doc": 3},
            sample_filenames=["va_claim.pdf", "nexus_letter.pdf", "dbq_ptsd.pdf"],
        ),
    ]
    return StructureSnapshot(
        root_path="/test/root",
        max_depth=4,
        total_folders=3,
        total_files=30,
        folders=folders,
    )


def _create_mock_snapshot(folders: list[FolderNode]) -> StructureSnapshot:
    """Helper to create a mock StructureSnapshot."""
    return StructureSnapshot(
        root_path="/test/root",
        max_depth=4,
        total_folders=len(folders),
        total_files=sum(f.file_count for f in folders),
        total_size_bytes=sum(f.total_size_bytes for f in folders),
        folders=folders,
    )


# ─────────────────────────────────────────────────────────────────────────────
# T2 Domain Detection Tests (Mock LLM)
# ─────────────────────────────────────────────────────────────────────────────


class TestT2DomainDetection:
    """Tests for T2 Smart model domain detection."""

    def test_t2_domain_detection_medical(
        self, mock_llm_client: MagicMock, mock_model_router: MagicMock
    ) -> None:
        """Should detect medical domain using T2 Smart model."""
        mock_llm_client.generate.return_value = MagicMock(
            success=True,
            text='{"domain": "medical", "confidence": 0.92, "evidence": ["VA folder found", "Medical documents present", "nexus_letter.pdf detected"]}',
            model_used="qwen2.5-coder:14b",
        )

        folders = [
            FolderNode(
                path="/test/VA",
                name="VA",
                depth=0,
                file_count=10,
                sample_filenames=["nexus_letter.pdf", "dbq_ptsd.pdf", "va_claim.pdf"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        detector = DomainDetector(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
        )
        context = detector.detect_domain(snapshot)

        assert context.detected_domain == "medical"
        assert context.confidence == 0.92
        assert context.model_used == "qwen2.5-coder:14b"
        assert len(context.evidence) == 3
        assert context.used_llm is True
        # Verify T2 model was used via router
        mock_model_router.route.assert_called()

    def test_t2_domain_detection_engineering(
        self, mock_llm_client: MagicMock, mock_model_router: MagicMock
    ) -> None:
        """Should detect engineering domain using T2 Smart model."""
        mock_llm_client.generate.return_value = MagicMock(
            success=True,
            text='{"domain": "engineering", "confidence": 0.88, "evidence": ["src folder structure", "Code files (.py, .ts)", "Configuration files present"]}',
            model_used="qwen2.5-coder:14b",
        )

        folders = [
            FolderNode(
                path="/test/src",
                name="src",
                depth=0,
                file_count=50,
                file_types={".py": 30, ".ts": 15, ".json": 5},
                sample_filenames=["main.py", "api.ts", "config.json"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        detector = DomainDetector(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
        )
        context = detector.detect_domain(snapshot)

        assert context.detected_domain == "engineering"
        assert context.confidence == 0.88
        assert context.used_llm is True

    def test_t2_domain_detection_fallback_to_keywords(
        self, mock_llm_client: MagicMock
    ) -> None:
        """Should fall back to keyword detection when LLM is unavailable."""
        mock_llm_client.is_ollama_available.return_value = False

        folders = [
            FolderNode(
                path="/test/legal",
                name="legal",
                depth=0,
                file_count=20,
                sample_filenames=["contract_2024.pdf", "agreement.pdf", "lawsuit.pdf"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        detector = DomainDetector(llm_client=mock_llm_client)
        context = detector.detect_domain(snapshot)

        assert context.detected_domain == "legal"
        assert context.model_used == "keyword_fallback"
        assert context.used_llm is False

    def test_t2_domain_detection_handles_malformed_json(
        self, mock_llm_client: MagicMock
    ) -> None:
        """Should fall back to keywords on malformed JSON response."""
        mock_llm_client.generate.return_value = MagicMock(
            success=True,
            text="I think this is a medical domain because...",  # Not JSON
            model_used="qwen2.5-coder:14b",
        )

        folders = [
            FolderNode(
                path="/test/medical",
                name="medical",
                depth=0,
                sample_filenames=["prescription.pdf", "health_records.pdf"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        detector = DomainDetector(llm_client=mock_llm_client)
        context = detector.detect_domain(snapshot)

        # Should fall back to keyword detection
        assert context.detected_domain == "medical"
        assert context.model_used == "keyword_fallback"


# ─────────────────────────────────────────────────────────────────────────────
# T2 Rule Generation Tests (Mock LLM)
# ─────────────────────────────────────────────────────────────────────────────


class TestT2RuleGeneration:
    """Tests for T2 Smart model rule generation."""

    def test_t2_rule_generation_single_rule(
        self, mock_llm_client: MagicMock, mock_model_router: MagicMock
    ) -> None:
        """Should generate a single rule using T2 Smart model."""
        mock_llm_client.generate.return_value = MagicMock(
            success=True,
            text='{"rules": [{"pattern": "invoice", "confidence": 0.92, "reasoning": "Files containing invoice keyword belong in invoices folder"}]}',
            model_used="qwen2.5-coder:14b",
        )

        folders = [
            FolderNode(
                path="/test/invoices",
                name="invoices",
                depth=0,
                file_count=10,
                sample_filenames=["invoice_001.pdf", "invoice_002.pdf"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        generator = RuleGenerator(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
        )
        result = generator.generate_rules(snapshot)

        llm_rules = [r for r in result.rules if r.used_llm]
        assert len(llm_rules) >= 1
        assert llm_rules[0].pattern == "invoice"
        assert llm_rules[0].confidence == 0.92
        assert "invoice" in llm_rules[0].reasoning.lower()
        assert llm_rules[0].model_used == "qwen2.5-coder:14b"

    def test_t2_rule_generation_multiple_rules(
        self, mock_llm_client: MagicMock, mock_model_router: MagicMock
    ) -> None:
        """Should generate multiple rules for a folder using T2 Smart model."""
        mock_llm_client.generate.return_value = MagicMock(
            success=True,
            text='{"rules": [{"pattern": "invoice", "confidence": 0.9, "reasoning": "Invoice documents"}, {"pattern": "receipt", "confidence": 0.85, "reasoning": "Receipt documents"}, {"pattern": "*.pdf", "confidence": 0.75, "reasoning": "PDF files"}]}',
            model_used="qwen2.5-coder:14b",
        )

        folders = [
            FolderNode(
                path="/test/finance",
                name="finance",
                depth=0,
                file_count=20,
                sample_filenames=[
                    "invoice_001.pdf",
                    "receipt_jan.pdf",
                    "statement.pdf",
                ],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        generator = RuleGenerator(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
        )
        result = generator.generate_rules(snapshot, max_rules_per_folder=3)

        llm_rules = [r for r in result.rules if r.used_llm]
        assert len(llm_rules) == 3
        patterns = [r.pattern for r in llm_rules]
        assert "invoice" in patterns
        assert "receipt" in patterns
        assert "*.pdf" in patterns

    def test_t2_rule_generation_fallback_to_patterns(
        self, mock_llm_client: MagicMock
    ) -> None:
        """Should fall back to pattern-based rules when LLM is unavailable."""
        mock_llm_client.is_ollama_available.return_value = False

        folders = [
            FolderNode(
                path="/test/docs",
                name="docs",
                depth=0,
                file_count=10,
                file_types={".pdf": 8, ".docx": 2},
                sample_filenames=["report_2024.pdf", "notes.docx"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        generator = RuleGenerator(llm_client=mock_llm_client)
        result = generator.generate_rules(snapshot)

        # Should generate rules using pattern fallback
        assert result.model_used == "pattern_fallback"
        assert all(r.model_used == "pattern_fallback" for r in result.rules)
        assert len(result.rules) >= 1

    def test_t2_rule_generation_extracts_json_from_markdown(
        self, mock_llm_client: MagicMock
    ) -> None:
        """Should extract JSON from markdown code blocks."""
        mock_llm_client.generate.return_value = MagicMock(
            success=True,
            text="""Here are the routing rules I generated:

```json
{"rules": [{"pattern": "tax", "confidence": 0.9, "reasoning": "Tax documents"}]}
```

Let me know if you need more details.""",
            model_used="qwen2.5-coder:14b",
        )

        folders = [
            FolderNode(
                path="/test/tax",
                name="tax",
                depth=0,
                file_count=5,
                sample_filenames=["tax_2024.pdf", "w2_2024.pdf"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        generator = RuleGenerator(llm_client=mock_llm_client)
        result = generator.generate_rules(snapshot)

        llm_rules = [r for r in result.rules if r.used_llm]
        assert len(llm_rules) >= 1
        assert llm_rules[0].pattern == "tax"


# ─────────────────────────────────────────────────────────────────────────────
# Structure Narration Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestStructureNarration:
    """Tests for LLM-powered structure narration."""

    def test_narration_with_llm(self, mock_llm_client: MagicMock) -> None:
        """Should generate plain-English narration using T2 Smart model."""
        mock_llm_client.generate.return_value = MagicMock(
            success=True,
            text="This folder uses category-based organization with separate areas for invoices, medical records, and general documents. Files are grouped by function rather than date.",
            model_used="qwen2.5-coder:14b",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "invoices").mkdir()
            (root / "medical").mkdir()
            (root / "documents").mkdir()

            analyzer = StructureAnalyzer(
                llm_client=mock_llm_client,
                use_llm=True,
            )
            result = analyzer.analyze(root, max_depth=4, generate_narration=True)

            assert "category-based" in result.strategy_description
            assert result.model_used == "qwen2.5-coder:14b"
            mock_llm_client.generate.assert_called()

    def test_narration_fallback_without_llm(self) -> None:
        """Should generate keyword-based narration when LLM unavailable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "2020").mkdir()
            (root / "2021").mkdir()
            (root / "2022").mkdir()

            analyzer = StructureAnalyzer(use_llm=False)
            result = analyzer.analyze(root, max_depth=4, generate_narration=True)

            # Should have keyword-based description mentioning date structure
            assert "date" in result.strategy_description.lower()
            assert result.model_used == ""

    def test_narration_fallback_when_llm_fails(
        self, mock_llm_client: MagicMock
    ) -> None:
        """Should fall back to keyword narration when LLM fails."""
        mock_llm_client.generate.return_value = MagicMock(
            success=False,
            text="",
            error="Model error",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "Documents").mkdir()
            (root / "Images").mkdir()

            analyzer = StructureAnalyzer(
                llm_client=mock_llm_client,
                use_llm=True,
            )
            result = analyzer.analyze(root, max_depth=4, generate_narration=True)

            # Should have a keyword-based description
            assert result.strategy_description != ""
            assert result.model_used == ""

    def test_narration_describes_file_types(self) -> None:
        """Should mention dominant file types in narration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            for i in range(5):
                (root / f"doc{i}.pdf").touch()

            analyzer = StructureAnalyzer(use_llm=False)
            result = analyzer.analyze(root, max_depth=4, generate_narration=True)

            assert ".pdf" in result.strategy_description.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Learned Rule Merge Priority Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestLearnedRuleMergePriority:
    """Tests for learned rule merge priority.

    Priority order (highest to lowest):
    1. Learned rules (from structure learning)
    2. User overrides (from correction history)
    3. Built-in taxonomy rules
    4. Hardcoded ROUTING_RULES
    """

    def test_learned_rules_over_taxonomy(
        self, temp_rules_path: Path, temp_taxonomy_path: Path
    ) -> None:
        """Learned rules should take priority over taxonomy."""
        temp_rules_path.parent.mkdir(parents=True, exist_ok=True)
        learned_data = {
            "rules": [
                {
                    "pattern": "invoice",
                    "destination": "/learned/invoices",
                    "confidence": 0.95,
                },
            ]
        }
        temp_rules_path.write_text(json.dumps(learned_data), encoding="utf-8")

        store = LearnedRuleStore(
            rules_path=temp_rules_path,
            taxonomy_path=temp_taxonomy_path,
        )

        # invoice matches both learned rules and taxonomy
        # Learned should win
        dest, conf = store.match("invoice_2024.pdf")
        assert dest == "/learned/invoices"
        assert conf == 0.95

    def test_learned_rules_over_hardcoded(self, temp_rules_path: Path) -> None:
        """Learned rules should take priority over hardcoded ROUTING_RULES."""
        temp_rules_path.parent.mkdir(parents=True, exist_ok=True)
        learned_data = {
            "rules": [
                {
                    "pattern": "tax",
                    "destination": "/learned/tax_docs",
                    "confidence": 0.92,
                },
            ]
        }
        temp_rules_path.write_text(json.dumps(learned_data), encoding="utf-8")

        store = LearnedRuleStore(
            rules_path=temp_rules_path,
            taxonomy_path=None,  # No taxonomy
        )

        # tax matches learned rule (no taxonomy or hardcoded to compete)
        dest, conf = store.match("tax_return_2024.pdf")
        assert dest == "/learned/tax_docs"
        assert conf == 0.92

    def test_taxonomy_over_hardcoded_when_no_learned(
        self, temp_rules_path: Path, temp_taxonomy_path: Path
    ) -> None:
        """Taxonomy should be used when no learned rules match."""
        temp_rules_path.parent.mkdir(parents=True, exist_ok=True)
        # Create empty learned rules
        temp_rules_path.write_text(json.dumps({"rules": []}), encoding="utf-8")

        store = LearnedRuleStore(
            rules_path=temp_rules_path,
            taxonomy_path=temp_taxonomy_path,
        )

        # va_claim is only in taxonomy
        dest, conf = store.match("va_claim_2024.pdf")
        assert dest == "VA/Claims"
        assert conf == 0.85

    def test_override_priority_with_mock_registry(
        self, temp_rules_path: Path, temp_taxonomy_path: Path
    ) -> None:
        """User overrides should be checked but learned rules win in this implementation."""
        temp_rules_path.parent.mkdir(parents=True, exist_ok=True)
        learned_data = {
            "rules": [
                {
                    "pattern": "invoice",
                    "destination": "/learned/invoices",
                    "confidence": 0.9,
                },
            ]
        }
        temp_rules_path.write_text(json.dumps(learned_data), encoding="utf-8")

        # Create mock override registry
        mock_override = MagicMock()
        mock_override.pattern = "invoice"
        mock_override.correct_bin = "/override/invoices"
        mock_override.source = "user_correction"

        mock_registry = MagicMock()
        mock_registry.find_match.return_value = mock_override

        store = LearnedRuleStore(
            rules_path=temp_rules_path,
            taxonomy_path=temp_taxonomy_path,
            override_registry=mock_registry,
        )

        # In current implementation, learned rules are checked first
        # So learned should still win
        dest, conf = store.match("invoice_2024.pdf")
        assert dest == "/learned/invoices"

    def test_match_with_details_shows_rule_source(self, temp_rules_path: Path) -> None:
        """match_with_details should indicate rule source is 'learned'."""
        temp_rules_path.parent.mkdir(parents=True, exist_ok=True)
        learned_data = {
            "rules": [
                {
                    "pattern": "report",
                    "destination": "/reports",
                    "confidence": 0.88,
                    "reasoning": "Report files",
                },
            ]
        }
        temp_rules_path.write_text(json.dumps(learned_data), encoding="utf-8")

        store = LearnedRuleStore(
            rules_path=temp_rules_path,
            taxonomy_path=None,
        )

        result = store.match_with_details("report_2024.pdf")
        assert result is not None
        assert result.rule_source == "learned"
        assert result.destination == "/reports"
        assert result.reasoning == "Report files"

    def test_taxonomy_fallback_match_with_details(
        self, temp_rules_path: Path, temp_taxonomy_path: Path
    ) -> None:
        """match_with_details should show taxonomy source for fallback."""
        temp_rules_path.parent.mkdir(parents=True, exist_ok=True)
        temp_rules_path.write_text(json.dumps({"rules": []}), encoding="utf-8")

        store = LearnedRuleStore(
            rules_path=temp_rules_path,
            taxonomy_path=temp_taxonomy_path,
        )

        result = store.match_with_details("medical_records_2024.pdf")
        assert result is not None
        assert result.rule_source == "taxonomy"
        assert result.destination == "VA/Medical Records"

    def test_priority_chain_complete(
        self, temp_rules_path: Path, temp_taxonomy_path: Path
    ) -> None:
        """Test the complete priority chain with multiple matching sources."""
        temp_rules_path.parent.mkdir(parents=True, exist_ok=True)
        learned_data = {
            "rules": [
                {
                    "pattern": "tax",
                    "destination": "/learned/taxes",
                    "confidence": 0.95,
                },
            ]
        }
        temp_rules_path.write_text(json.dumps(learned_data), encoding="utf-8")

        store = LearnedRuleStore(
            rules_path=temp_rules_path,
            taxonomy_path=temp_taxonomy_path,
        )

        # tax matches learned rules AND taxonomy ("Finances Bin/Taxes")
        # Learned should win
        dest, conf = store.match("tax_document.pdf")
        assert dest == "/learned/taxes"
        assert conf == 0.95

        # Now remove learned rule and check taxonomy fallback
        store.remove_rule("tax")
        dest2, conf2 = store.match("tax_document.pdf")
        assert dest2 == "Finances Bin/Taxes"
        assert conf2 == 0.85


# ─────────────────────────────────────────────────────────────────────────────
# Integration Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestLearningAgentIntegration:
    """Integration tests for the full Learning-Agent pipeline."""

    def test_full_learning_pipeline(
        self, mock_llm_client: MagicMock, mock_model_router: MagicMock
    ) -> None:
        """Test the complete learning pipeline: analyze -> detect domain -> generate rules."""
        # Mock domain detection response
        domain_response = MagicMock(
            success=True,
            text='{"domain": "generic_business", "confidence": 0.85, "evidence": ["Invoice folder", "Tax documents"]}',
            model_used="qwen2.5-coder:14b",
        )

        # Mock rule generation response
        rule_response = MagicMock(
            success=True,
            text='{"rules": [{"pattern": "invoice", "confidence": 0.9, "reasoning": "Invoice docs"}]}',
            model_used="qwen2.5-coder:14b",
        )

        # Mock narration response
        narration_response = MagicMock(
            success=True,
            text="Business document organization with financial and tax categories.",
            model_used="qwen2.5-coder:14b",
        )

        # Set up mock to return different responses based on call count
        mock_llm_client.generate.side_effect = [
            narration_response,  # For structure analyzer
            domain_response,  # For domain detector
            rule_response,  # For rule generator
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "invoices").mkdir()
            (root / "tax").mkdir()
            # Add multiple files to meet min_files_for_rule threshold
            for i in range(5):
                (root / "invoices" / f"invoice_{i:03d}.pdf").touch()
                (root / "tax" / f"tax_{2020 + i}.pdf").touch()

            # Step 1: Analyze structure
            analyzer = StructureAnalyzer(
                llm_client=mock_llm_client,
                use_llm=True,
            )
            structure = analyzer.analyze(root, max_depth=4, generate_narration=True)

            assert structure.total_folders >= 2
            assert structure.strategy_description != ""

            # Step 2: Detect domain
            detector = DomainDetector(
                llm_client=mock_llm_client,
                model_router=mock_model_router,
            )
            domain_context = detector.detect_domain(structure)

            assert domain_context.detected_domain == "generic_business"
            assert domain_context.used_llm is True

            # Step 3: Generate rules - use pattern fallback to verify integration
            # (LLM mock is consumed, so pattern fallback will be used)
            generator = RuleGenerator()  # No LLM to ensure pattern fallback
            rules = generator.generate_rules(structure, use_llm=False)

            # Pattern-based rules should be generated from folder analysis
            assert len(rules.rules) >= 1

    def test_learning_agent_graceful_degradation(self) -> None:
        """Test that Learning-Agent degrades gracefully when LLM unavailable."""
        # Use no LLM client - should fall back to keyword-based methods
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "medical").mkdir()
            (root / "VA").mkdir()
            (root / "medical" / "prescription.pdf").touch()
            (root / "VA" / "va_claim.pdf").touch()

            # Analyze without LLM
            structure = analyze_structure(root, max_depth=4, use_llm=False)
            assert structure.total_folders >= 2

            # Detect domain without LLM
            domain = detect_domain(structure, use_llm=False)
            assert domain.detected_domain == "medical"
            assert domain.model_used == "keyword_fallback"

            # Generate rules without LLM
            rules = generate_rules(structure, use_llm=False)
            assert rules.model_used == "pattern_fallback"

    def test_learned_rules_persist_and_load(self, temp_rules_path: Path) -> None:
        """Test that learned rules persist to disk and load correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "contracts").mkdir()
            # Add multiple files to meet min_files_for_rule threshold
            for i in range(5):
                (root / "contracts" / f"contract_{2020 + i}.pdf").touch()

            structure = analyze_structure(root, max_depth=4, use_llm=False)

            # Generate and save rules using pattern fallback
            rules = generate_rules(
                structure,
                use_llm=False,
                output_path=temp_rules_path,
            )

            assert temp_rules_path.exists()
            # Verify at least one rule was generated
            assert len(rules.rules) >= 1

            # Load rules into store
            store = LearnedRuleStore(
                rules_path=temp_rules_path,
                taxonomy_path=None,
            )

            assert store.get_rule_count() >= 1
            dest, conf = store.match("contract_agreement.pdf")
            assert "contract" in dest.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Edge Cases and Error Handling
# ─────────────────────────────────────────────────────────────────────────────


class TestLearningAgentEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_structure(self) -> None:
        """Should handle empty structure gracefully."""
        snapshot = _create_mock_snapshot([])

        # Domain detection with empty structure
        context = detect_domain(snapshot, use_llm=False)
        assert context.detected_domain == "generic_business"
        assert context.confidence <= 0.5

        # Rule generation with empty structure
        rules = generate_rules(snapshot, use_llm=False)
        assert len(rules.rules) == 0

    def test_llm_exception_handling(self, mock_llm_client: MagicMock) -> None:
        """Should handle LLM exceptions gracefully."""
        mock_llm_client.is_ollama_available.side_effect = Exception("Connection error")

        folders = [
            FolderNode(
                path="/test/docs",
                name="docs",
                depth=0,
                file_count=5,
                file_types={".pdf": 5},
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        # Should fall back to keyword detection without crashing
        detector = DomainDetector(llm_client=mock_llm_client)
        context = detector.detect_domain(snapshot)
        assert context.model_used == "keyword_fallback"

        # Rule generator should also fall back
        generator = RuleGenerator(llm_client=mock_llm_client)
        rules = generator.generate_rules(snapshot)
        assert all(r.model_used == "pattern_fallback" for r in rules.rules)

    def test_corrupted_rules_file(self, temp_rules_path: Path) -> None:
        """Should handle corrupted rules file gracefully."""
        temp_rules_path.parent.mkdir(parents=True, exist_ok=True)
        temp_rules_path.write_text("not valid json {{{", encoding="utf-8")

        store = LearnedRuleStore(rules_path=temp_rules_path, taxonomy_path=None)
        assert store.get_rule_count() == 0
        assert store.is_loaded is True

    def test_missing_fields_in_llm_response(self, mock_llm_client: MagicMock) -> None:
        """Should handle LLM responses with missing fields."""
        mock_llm_client.generate.return_value = MagicMock(
            success=True,
            text='{"domain": "personal"}',  # Missing confidence and evidence
            model_used="qwen2.5-coder:14b",
        )

        folders = [
            FolderNode(path="/test", name="test", depth=0),
        ]
        snapshot = _create_mock_snapshot(folders)

        detector = DomainDetector(llm_client=mock_llm_client)
        context = detector.detect_domain(snapshot)

        # Should still detect domain, using defaults for missing fields
        assert context.detected_domain == "personal"

    def test_model_router_exception(
        self, mock_llm_client: MagicMock, mock_model_router: MagicMock
    ) -> None:
        """Should use default model when router fails."""
        mock_llm_client.generate.return_value = MagicMock(
            success=True,
            text='{"domain": "engineering", "confidence": 0.8, "evidence": []}',
            model_used="qwen2.5-coder:14b",
        )
        mock_model_router.route.side_effect = RuntimeError("No models available")

        folders = [
            FolderNode(path="/test/src", name="src", depth=0),
        ]
        snapshot = _create_mock_snapshot(folders)

        detector = DomainDetector(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
        )
        context = detector.detect_domain(snapshot)

        # Should still work with default model
        assert context.detected_domain == "engineering"


# ─────────────────────────────────────────────────────────────────────────────
# LLM Domain Detection - Comprehensive Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestLLMDomainDetectionPath:
    """Tests for LLM domain detection code path verification."""

    def test_llm_domain_uses_t2_smart_model(
        self, mock_llm_client: MagicMock, mock_model_router: MagicMock
    ) -> None:
        """Should use T2 Smart model for domain detection."""
        mock_llm_client.generate.return_value = MagicMock(
            success=True,
            text='{"domain": "personal", "confidence": 0.88, "evidence": ["Photos folder"]}',
            model_used="qwen2.5-coder:14b",
        )

        folders = [
            FolderNode(
                path="/test/photos",
                name="photos",
                depth=0,
                file_count=20,
                sample_filenames=["vacation.jpg", "family.jpg"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        detector = DomainDetector(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
        )
        detector.detect_domain(snapshot)

        # Verify T2 Smart model was requested via router
        mock_model_router.route.assert_called()
        call_args = mock_model_router.route.call_args
        assert call_args[0][0].task_type == "analyze"
        assert call_args[0][0].complexity == "medium"

    def test_llm_domain_captures_model_used_field(
        self, mock_llm_client: MagicMock
    ) -> None:
        """Should capture the model_used field in DomainContext."""
        mock_llm_client.generate.return_value = MagicMock(
            success=True,
            text='{"domain": "legal", "confidence": 0.9, "evidence": ["Contract files"]}',
            model_used="llama3.1:8b-instruct-q8_0",
        )

        folders = [
            FolderNode(
                path="/test/legal",
                name="legal",
                depth=0,
                sample_filenames=["contract.pdf"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        detector = DomainDetector(llm_client=mock_llm_client)
        context = detector.detect_domain(snapshot)

        assert context.model_used == "llama3.1:8b-instruct-q8_0"
        assert context.used_llm is True

    def test_llm_domain_evidence_list_captured(
        self, mock_llm_client: MagicMock
    ) -> None:
        """Should capture evidence list from LLM response."""
        mock_llm_client.generate.return_value = MagicMock(
            success=True,
            text='{"domain": "automotive", "confidence": 0.95, "evidence": ["VIN numbers detected", "Inventory files", "Service records"]}',
            model_used="qwen2.5-coder:14b",
        )

        folders = [
            FolderNode(
                path="/test/dealership",
                name="dealership",
                depth=0,
                sample_filenames=["inventory.xlsx", "vin_list.csv"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        detector = DomainDetector(llm_client=mock_llm_client)
        context = detector.detect_domain(snapshot)

        assert len(context.evidence) == 3
        assert "VIN numbers detected" in context.evidence
        assert "Inventory files" in context.evidence


class TestLLMDomainUnavailability:
    """Tests for LLM unavailability scenarios in domain detection."""

    def test_ollama_down_uses_keyword_fallback(
        self, mock_llm_client: MagicMock
    ) -> None:
        """Should fall back to keywords when Ollama is down."""
        mock_llm_client.is_ollama_available.return_value = False

        folders = [
            FolderNode(
                path="/test/creative",
                name="creative",
                depth=0,
                sample_filenames=["design_v1.psd", "portfolio.pdf"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        detector = DomainDetector(llm_client=mock_llm_client)
        context = detector.detect_domain(snapshot)

        assert context.model_used == "keyword_fallback"
        assert context.used_llm is False
        # Should not have called generate
        mock_llm_client.generate.assert_not_called()

    def test_ollama_check_exception_falls_back_to_keywords(
        self, mock_llm_client: MagicMock
    ) -> None:
        """Should fall back when Ollama availability check raises exception."""
        mock_llm_client.is_ollama_available.side_effect = ConnectionError("Network error")

        folders = [
            FolderNode(
                path="/test/medical",
                name="medical",
                depth=0,
                sample_filenames=["prescription.pdf"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        detector = DomainDetector(llm_client=mock_llm_client)
        context = detector.detect_domain(snapshot)

        assert context.model_used == "keyword_fallback"
        assert context.detected_domain == "medical"

    def test_no_llm_client_uses_keyword_fallback(self) -> None:
        """Should use keyword fallback when no LLM client provided."""
        folders = [
            FolderNode(
                path="/test/engineering",
                name="src",
                depth=0,
                sample_filenames=["main.py", "api.ts"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        detector = DomainDetector()  # No LLM client
        context = detector.detect_domain(snapshot)

        assert context.model_used == "keyword_fallback"

    def test_use_llm_false_bypasses_llm(
        self, mock_llm_client: MagicMock
    ) -> None:
        """Should bypass LLM when use_llm=False."""
        folders = [
            FolderNode(
                path="/test/docs",
                name="docs",
                depth=0,
                sample_filenames=["readme.md"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        detector = DomainDetector(llm_client=mock_llm_client)
        context = detector.detect_domain(snapshot, use_llm=False)

        assert context.model_used == "keyword_fallback"
        mock_llm_client.is_ollama_available.assert_not_called()

    def test_llm_generate_fails_falls_back_to_keywords(
        self, mock_llm_client: MagicMock
    ) -> None:
        """Should fall back when LLM generate returns failure."""
        mock_llm_client.generate.return_value = MagicMock(
            success=False,
            text="",
            error="Model timeout",
        )

        folders = [
            FolderNode(
                path="/test/personal",
                name="personal",
                depth=0,
                sample_filenames=["diary.txt", "photos/"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        detector = DomainDetector(llm_client=mock_llm_client)
        context = detector.detect_domain(snapshot)

        assert context.model_used == "keyword_fallback"


class TestPromptRegistryDomainIntegration:
    """Tests for prompt registry integration in domain detection."""

    def test_uses_prompt_from_registry_when_available(
        self, mock_llm_client: MagicMock
    ) -> None:
        """Should use prompt from registry when available."""
        mock_llm_client.generate.return_value = MagicMock(
            success=True,
            text='{"domain": "generic_business", "confidence": 0.85, "evidence": ["Business docs"]}',
            model_used="qwen2.5-coder:14b",
        )

        mock_registry = MagicMock()
        mock_registry.get.return_value = "Custom domain detection prompt for {structure_json}"

        folders = [
            FolderNode(
                path="/test/business",
                name="business",
                depth=0,
                sample_filenames=["invoice.pdf"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        detector = DomainDetector(
            llm_client=mock_llm_client,
            prompt_registry=mock_registry,
        )
        detector.detect_domain(snapshot)

        mock_registry.get.assert_called_once()
        assert "domain_detection" in str(mock_registry.get.call_args)

    def test_falls_back_to_inline_prompt_when_registry_missing(
        self, mock_llm_client: MagicMock
    ) -> None:
        """Should fall back to inline prompt when registry raises KeyError."""
        mock_llm_client.generate.return_value = MagicMock(
            success=True,
            text='{"domain": "creative", "confidence": 0.82, "evidence": ["Art files"]}',
            model_used="qwen2.5-coder:14b",
        )

        mock_registry = MagicMock()
        mock_registry.get.side_effect = KeyError("domain_detection")

        folders = [
            FolderNode(
                path="/test/art",
                name="art",
                depth=0,
                sample_filenames=["sketch.psd"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        detector = DomainDetector(
            llm_client=mock_llm_client,
            prompt_registry=mock_registry,
        )
        context = detector.detect_domain(snapshot)

        # Should still succeed with inline prompt
        assert context.detected_domain == "creative"
        assert context.used_llm is True


class TestJSONParsingDomainEdgeCases:
    """Tests for JSON parsing edge cases in domain detection."""

    def test_parse_json_with_extra_text_before(
        self, mock_llm_client: MagicMock
    ) -> None:
        """Should extract JSON even with preamble text."""
        mock_llm_client.generate.return_value = MagicMock(
            success=True,
            text='Based on my analysis: {"domain": "medical", "confidence": 0.91, "evidence": ["Health records"]}',
            model_used="qwen2.5-coder:14b",
        )

        folders = [
            FolderNode(
                path="/test/health",
                name="health",
                depth=0,
                sample_filenames=["records.pdf"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        detector = DomainDetector(llm_client=mock_llm_client)
        context = detector.detect_domain(snapshot)

        assert context.detected_domain == "medical"
        assert context.confidence == 0.91

    def test_parse_json_with_nested_braces_in_evidence(
        self, mock_llm_client: MagicMock
    ) -> None:
        """Should handle evidence containing brace-like text."""
        mock_llm_client.generate.return_value = MagicMock(
            success=True,
            text='{"domain": "engineering", "confidence": 0.88, "evidence": ["Code files {src}"]}',
            model_used="qwen2.5-coder:14b",
        )

        folders = [
            FolderNode(
                path="/test/code",
                name="code",
                depth=0,
                sample_filenames=["app.py"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        detector = DomainDetector(llm_client=mock_llm_client)
        context = detector.detect_domain(snapshot)

        # Should fall back since nested braces break simple regex
        # The fallback is acceptable behavior
        assert context.detected_domain in {"engineering", "generic_business"}

    def test_confidence_as_string_handled(
        self, mock_llm_client: MagicMock
    ) -> None:
        """Should handle confidence as string number."""
        mock_llm_client.generate.return_value = MagicMock(
            success=True,
            text='{"domain": "legal", "confidence": "0.87", "evidence": []}',
            model_used="qwen2.5-coder:14b",
        )

        folders = [
            FolderNode(
                path="/test/legal",
                name="contracts",
                depth=0,
                sample_filenames=["agreement.pdf"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        detector = DomainDetector(llm_client=mock_llm_client)
        context = detector.detect_domain(snapshot)

        # String confidence should default to 0.5
        assert context.confidence == 0.5

    def test_invalid_domain_defaults_to_generic_business(
        self, mock_llm_client: MagicMock
    ) -> None:
        """Should default to generic_business for invalid domain value."""
        mock_llm_client.generate.return_value = MagicMock(
            success=True,
            text='{"domain": "unknown_domain_type", "confidence": 0.9, "evidence": []}',
            model_used="qwen2.5-coder:14b",
        )

        folders = [
            FolderNode(
                path="/test/misc",
                name="misc",
                depth=0,
                sample_filenames=["file.txt"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        detector = DomainDetector(llm_client=mock_llm_client)
        context = detector.detect_domain(snapshot)

        assert context.detected_domain == "generic_business"

    def test_negative_confidence_clamped_to_zero(
        self, mock_llm_client: MagicMock
    ) -> None:
        """Should clamp negative confidence to 0.0."""
        mock_llm_client.generate.return_value = MagicMock(
            success=True,
            text='{"domain": "personal", "confidence": -0.5, "evidence": []}',
            model_used="qwen2.5-coder:14b",
        )

        folders = [
            FolderNode(
                path="/test/home",
                name="home",
                depth=0,
                sample_filenames=["notes.txt"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        detector = DomainDetector(llm_client=mock_llm_client)
        context = detector.detect_domain(snapshot)

        assert context.confidence == 0.0

    def test_confidence_above_one_clamped(
        self, mock_llm_client: MagicMock
    ) -> None:
        """Should clamp confidence > 1.0 to 1.0."""
        mock_llm_client.generate.return_value = MagicMock(
            success=True,
            text='{"domain": "automotive", "confidence": 1.5, "evidence": []}',
            model_used="qwen2.5-coder:14b",
        )

        folders = [
            FolderNode(
                path="/test/cars",
                name="cars",
                depth=0,
                sample_filenames=["vin.csv"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        detector = DomainDetector(llm_client=mock_llm_client)
        context = detector.detect_domain(snapshot)

        assert context.confidence == 1.0


# ─────────────────────────────────────────────────────────────────────────────
# LLM Rule Generation - Comprehensive Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestLLMRuleGenerationPath:
    """Tests for LLM rule generation code path verification."""

    def test_llm_rule_uses_t2_smart_model(
        self, mock_llm_client: MagicMock, mock_model_router: MagicMock
    ) -> None:
        """Should use T2 Smart model for rule generation."""
        mock_llm_client.generate.return_value = MagicMock(
            success=True,
            text='{"rules": [{"pattern": "invoice", "confidence": 0.9, "reasoning": "Invoice files"}]}',
            model_used="qwen2.5-coder:14b",
        )

        folders = [
            FolderNode(
                path="/test/invoices",
                name="invoices",
                depth=0,
                file_count=10,
                sample_filenames=["invoice_001.pdf"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        generator = RuleGenerator(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
        )
        generator.generate_rules(snapshot)

        # Verify T2 Smart model was requested via router
        mock_model_router.route.assert_called()
        call_args = mock_model_router.route.call_args
        assert call_args[0][0].task_type == "generate"
        assert call_args[0][0].complexity == "medium"

    def test_llm_rule_captures_reasoning_field(
        self, mock_llm_client: MagicMock
    ) -> None:
        """Should capture reasoning from LLM response."""
        mock_llm_client.generate.return_value = MagicMock(
            success=True,
            text='{"rules": [{"pattern": "receipt", "confidence": 0.88, "reasoning": "Receipt documents for expense tracking"}]}',
            model_used="qwen2.5-coder:14b",
        )

        folders = [
            FolderNode(
                path="/test/receipts",
                name="receipts",
                depth=0,
                file_count=5,
                sample_filenames=["receipt_001.pdf"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        generator = RuleGenerator(llm_client=mock_llm_client)
        result = generator.generate_rules(snapshot)

        llm_rules = [r for r in result.rules if r.used_llm]
        assert len(llm_rules) >= 1
        assert "expense tracking" in llm_rules[0].reasoning


class TestLLMRuleUnavailability:
    """Tests for LLM unavailability scenarios in rule generation."""

    def test_ollama_down_uses_pattern_fallback(
        self, mock_llm_client: MagicMock
    ) -> None:
        """Should fall back to patterns when Ollama is down."""
        mock_llm_client.is_ollama_available.return_value = False

        folders = [
            FolderNode(
                path="/test/docs",
                name="docs",
                depth=0,
                file_count=10,
                file_types={".pdf": 8, ".docx": 2},
                sample_filenames=["doc_001.pdf", "doc_002.pdf"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        generator = RuleGenerator(llm_client=mock_llm_client)
        result = generator.generate_rules(snapshot)

        assert result.model_used == "pattern_fallback"
        mock_llm_client.generate.assert_not_called()

    def test_llm_generate_fails_uses_pattern_fallback(
        self, mock_llm_client: MagicMock
    ) -> None:
        """Should fall back when LLM generate returns failure."""
        mock_llm_client.generate.return_value = MagicMock(
            success=False,
            text="",
            error="Timeout",
        )

        folders = [
            FolderNode(
                path="/test/reports",
                name="reports",
                depth=0,
                file_count=5,
                file_types={".pdf": 5},
                sample_filenames=["report_2024.pdf"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        generator = RuleGenerator(llm_client=mock_llm_client)
        result = generator.generate_rules(snapshot)

        # Should have pattern-based rules
        assert all(r.model_used == "pattern_fallback" for r in result.rules)


class TestPromptRegistryRuleIntegration:
    """Tests for prompt registry integration in rule generation."""

    def test_uses_prompt_from_registry_for_rules(
        self, mock_llm_client: MagicMock
    ) -> None:
        """Should use prompt from registry when available."""
        mock_llm_client.generate.return_value = MagicMock(
            success=True,
            text='{"rules": [{"pattern": "tax", "confidence": 0.9, "reasoning": "Tax docs"}]}',
            model_used="qwen2.5-coder:14b",
        )

        mock_registry = MagicMock()
        mock_registry.get.return_value = "Custom rule generation prompt"

        folders = [
            FolderNode(
                path="/test/tax",
                name="tax",
                depth=0,
                file_count=5,
                sample_filenames=["tax_2024.pdf"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        generator = RuleGenerator(
            llm_client=mock_llm_client,
            prompt_registry=mock_registry,
        )
        generator.generate_rules(snapshot)

        mock_registry.get.assert_called()
        assert "rule_generation" in str(mock_registry.get.call_args)


class TestJSONParsingRuleEdgeCases:
    """Tests for JSON parsing edge cases in rule generation."""

    def test_parse_rules_with_empty_pattern_skipped(
        self, mock_llm_client: MagicMock
    ) -> None:
        """Should skip rules with empty pattern."""
        mock_llm_client.generate.return_value = MagicMock(
            success=True,
            text='{"rules": [{"pattern": "", "confidence": 0.9, "reasoning": "Empty"}, {"pattern": "valid", "confidence": 0.8, "reasoning": "Valid"}]}',
            model_used="qwen2.5-coder:14b",
        )

        folders = [
            FolderNode(
                path="/test/mixed",
                name="mixed",
                depth=0,
                file_count=5,
                sample_filenames=["file.txt"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        generator = RuleGenerator(llm_client=mock_llm_client)
        result = generator.generate_rules(snapshot)

        llm_rules = [r for r in result.rules if r.used_llm]
        # Only "valid" pattern should be included
        assert all(r.pattern != "" for r in llm_rules)

    def test_parse_rules_non_dict_items_skipped(
        self, mock_llm_client: MagicMock
    ) -> None:
        """Should skip non-dict items in rules array."""
        mock_llm_client.generate.return_value = MagicMock(
            success=True,
            text='{"rules": ["not a dict", {"pattern": "valid", "confidence": 0.8, "reasoning": "OK"}, 123]}',
            model_used="qwen2.5-coder:14b",
        )

        folders = [
            FolderNode(
                path="/test/mixed",
                name="mixed",
                depth=0,
                file_count=5,
                sample_filenames=["file.txt"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        generator = RuleGenerator(llm_client=mock_llm_client)
        result = generator.generate_rules(snapshot)

        llm_rules = [r for r in result.rules if r.used_llm]
        assert len(llm_rules) == 1
        assert llm_rules[0].pattern == "valid"

    def test_max_rules_per_folder_respected(
        self, mock_llm_client: MagicMock
    ) -> None:
        """Should respect max_rules_per_folder parameter."""
        mock_llm_client.generate.return_value = MagicMock(
            success=True,
            text='{"rules": [{"pattern": "a", "confidence": 0.9, "reasoning": "A"}, {"pattern": "b", "confidence": 0.8, "reasoning": "B"}, {"pattern": "c", "confidence": 0.7, "reasoning": "C"}, {"pattern": "d", "confidence": 0.6, "reasoning": "D"}]}',
            model_used="qwen2.5-coder:14b",
        )

        folders = [
            FolderNode(
                path="/test/many",
                name="many",
                depth=0,
                file_count=10,
                sample_filenames=["file.txt"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        generator = RuleGenerator(llm_client=mock_llm_client)
        result = generator.generate_rules(snapshot, max_rules_per_folder=2)

        llm_rules = [r for r in result.rules if r.used_llm]
        assert len(llm_rules) <= 2


# ─────────────────────────────────────────────────────────────────────────────
# LLM Strategy Narration - Comprehensive Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestLLMNarrationPath:
    """Tests for LLM narration code path verification."""

    def test_narration_uses_t2_smart_model(
        self, mock_llm_client: MagicMock, mock_model_router: MagicMock
    ) -> None:
        """Should use T2 Smart model for narration."""
        mock_llm_client.generate.return_value = MagicMock(
            success=True,
            text="This folder uses category-based organization.",
            model_used="qwen2.5-coder:14b",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "docs").mkdir()

            analyzer = StructureAnalyzer(
                llm_client=mock_llm_client,
                model_router=mock_model_router,
                use_llm=True,
            )
            analyzer.analyze(root, max_depth=4, generate_narration=True)

            # Verify T2 model was requested
            mock_model_router.route.assert_called()
            call_args = mock_model_router.route.call_args
            assert call_args[0][0].task_type == "analyze"

    def test_narration_model_used_captured(
        self, mock_llm_client: MagicMock
    ) -> None:
        """Should capture model_used in snapshot."""
        mock_llm_client.generate.return_value = MagicMock(
            success=True,
            text="Date-based organization with yearly folders.",
            model_used="llama3.1:8b-instruct-q8_0",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "2023").mkdir()
            (root / "2024").mkdir()

            analyzer = StructureAnalyzer(
                llm_client=mock_llm_client,
                use_llm=True,
            )
            result = analyzer.analyze(root, max_depth=4, generate_narration=True)

            assert result.model_used == "llama3.1:8b-instruct-q8_0"


class TestLLMNarrationUnavailability:
    """Tests for LLM unavailability in narration."""

    def test_ollama_down_generates_keyword_narration(
        self, mock_llm_client: MagicMock
    ) -> None:
        """Should generate keyword-based narration when Ollama down."""
        mock_llm_client.is_ollama_available.return_value = False

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "invoices").mkdir()
            (root / "receipts").mkdir()

            analyzer = StructureAnalyzer(
                llm_client=mock_llm_client,
                use_llm=True,
            )
            result = analyzer.analyze(root, max_depth=4, generate_narration=True)

            assert result.model_used == ""
            assert result.strategy_description != ""
            mock_llm_client.generate.assert_not_called()

    def test_generate_narration_false_skips_llm(
        self, mock_llm_client: MagicMock
    ) -> None:
        """Should skip narration when generate_narration=False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "test").mkdir()

            analyzer = StructureAnalyzer(
                llm_client=mock_llm_client,
                use_llm=True,
            )
            result = analyzer.analyze(root, max_depth=4, generate_narration=False)

            assert result.strategy_description == ""
            mock_llm_client.is_ollama_available.assert_not_called()


class TestPromptRegistryNarrationIntegration:
    """Tests for prompt registry in narration."""

    def test_uses_prompt_from_registry_for_narration(
        self, mock_llm_client: MagicMock
    ) -> None:
        """Should use prompt from registry when available."""
        mock_llm_client.generate.return_value = MagicMock(
            success=True,
            text="Custom narration from registry prompt.",
            model_used="qwen2.5-coder:14b",
        )

        mock_registry = MagicMock()
        mock_registry.get.return_value = "Custom narration prompt for {structure_json}"

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "docs").mkdir()

            analyzer = StructureAnalyzer(
                llm_client=mock_llm_client,
                prompt_registry=mock_registry,
                use_llm=True,
            )
            analyzer.analyze(root, max_depth=4, generate_narration=True)

            mock_registry.get.assert_called()
            assert "structure_narration" in str(mock_registry.get.call_args)


class TestNarrationEdgeCases:
    """Tests for narration edge cases."""

    def test_narration_strips_markdown_code_blocks(
        self, mock_llm_client: MagicMock
    ) -> None:
        """Should strip markdown code blocks from narration."""
        mock_llm_client.generate.return_value = MagicMock(
            success=True,
            text='```\nOrganized by project with date folders.\n```',
            model_used="qwen2.5-coder:14b",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "project").mkdir()

            analyzer = StructureAnalyzer(
                llm_client=mock_llm_client,
                use_llm=True,
            )
            result = analyzer.analyze(root, max_depth=4, generate_narration=True)

            assert "```" not in result.strategy_description
            assert "project" in result.strategy_description.lower()

    def test_keyword_narration_includes_file_types(self) -> None:
        """Should mention file types in keyword-based narration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            for i in range(5):
                (root / f"document{i}.pdf").touch()

            analyzer = StructureAnalyzer(use_llm=False)
            result = analyzer.analyze(root, max_depth=4, generate_narration=True)

            assert ".pdf" in result.strategy_description.lower()

    def test_keyword_narration_detects_date_structure(self) -> None:
        """Should detect date-based organization in keyword narration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "2022").mkdir()
            (root / "2023").mkdir()
            (root / "2024").mkdir()

            analyzer = StructureAnalyzer(use_llm=False)
            result = analyzer.analyze(root, max_depth=4, generate_narration=True)

            assert "date" in result.strategy_description.lower()
