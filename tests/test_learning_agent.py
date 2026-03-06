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
