"""Tests for rule_generator module - LLM-powered routing rule generation.

Covers:
- RoutingRule dataclass creation and serialization
- LearnedRulesSnapshot creation, serialization, save/load
- LLM-powered rule generation with T2 Smart (mock)
- Pattern-based rule fallback when LLM unavailable
- Graceful degradation from LLM to pattern fallback
- Confidence score calculation
- Rule filtering and enabling/disabling
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from organizer.rule_generator import (
    LearnedRulesSnapshot,
    RoutingRule,
    RuleGenerator,
    generate_rules,
    load_rules,
)
from organizer.structure_analyzer import FolderNode, StructureSnapshot


class TestRoutingRule:
    """Tests for RoutingRule dataclass."""

    def test_create_routing_rule(self) -> None:
        """Should create RoutingRule with required fields."""
        rule = RoutingRule(
            pattern="invoice",
            destination="/test/invoices",
            confidence=0.85,
        )
        assert rule.pattern == "invoice"
        assert rule.destination == "/test/invoices"
        assert rule.confidence == 0.85
        assert rule.reasoning == ""
        assert rule.source_folder == ""
        assert rule.model_used == ""
        assert rule.enabled is True
        # generated_at should be auto-set
        assert rule.generated_at != ""

    def test_create_routing_rule_with_all_fields(self) -> None:
        """Should create RoutingRule with all optional fields."""
        rule = RoutingRule(
            pattern="*.pdf",
            destination="/docs/pdfs",
            confidence=0.92,
            reasoning="All PDFs go to this folder",
            source_folder="/docs/pdfs",
            model_used="qwen2.5-coder:14b",
            generated_at="2024-01-15T10:30:00",
            enabled=False,
        )
        assert rule.pattern == "*.pdf"
        assert rule.destination == "/docs/pdfs"
        assert rule.confidence == 0.92
        assert rule.reasoning == "All PDFs go to this folder"
        assert rule.source_folder == "/docs/pdfs"
        assert rule.model_used == "qwen2.5-coder:14b"
        assert rule.generated_at == "2024-01-15T10:30:00"
        assert rule.enabled is False

    def test_to_dict(self) -> None:
        """Should convert RoutingRule to dictionary."""
        rule = RoutingRule(
            pattern="contract",
            destination="/legal/contracts",
            confidence=0.88,
            reasoning="Contract documents",
            source_folder="/legal/contracts",
            model_used="llama3.1:8b",
        )
        d = rule.to_dict()
        assert d["pattern"] == "contract"
        assert d["destination"] == "/legal/contracts"
        assert d["confidence"] == 0.88
        assert d["reasoning"] == "Contract documents"
        assert d["source_folder"] == "/legal/contracts"
        assert d["model_used"] == "llama3.1:8b"
        assert d["enabled"] is True
        assert "generated_at" in d

    def test_from_dict(self) -> None:
        """Should create RoutingRule from dictionary."""
        data = {
            "pattern": "medical",
            "destination": "/health/records",
            "confidence": 0.9,
            "reasoning": "Medical documents",
            "source_folder": "/health/records",
            "model_used": "qwen2.5-coder:14b",
            "generated_at": "2024-06-01T14:00:00",
            "enabled": True,
        }
        rule = RoutingRule.from_dict(data)
        assert rule.pattern == "medical"
        assert rule.destination == "/health/records"
        assert rule.confidence == 0.9
        assert rule.reasoning == "Medical documents"
        assert rule.model_used == "qwen2.5-coder:14b"
        assert rule.generated_at == "2024-06-01T14:00:00"
        assert rule.enabled is True

    def test_from_dict_with_defaults(self) -> None:
        """Should handle missing fields with defaults."""
        data: dict = {}
        rule = RoutingRule.from_dict(data)
        assert rule.pattern == ""
        assert rule.destination == ""
        assert rule.confidence == 0.0
        assert rule.reasoning == ""
        assert rule.model_used == ""
        assert rule.enabled is True

    def test_used_llm_property(self) -> None:
        """Should correctly identify if LLM was used."""
        rule_with_llm = RoutingRule(
            pattern="tax",
            destination="/finance/tax",
            confidence=0.9,
            model_used="qwen2.5-coder:14b",
        )
        assert rule_with_llm.used_llm is True

        rule_pattern = RoutingRule(
            pattern="tax",
            destination="/finance/tax",
            confidence=0.7,
            model_used="pattern_fallback",
        )
        assert rule_pattern.used_llm is False

        rule_no_model = RoutingRule(
            pattern="tax",
            destination="/finance/tax",
            confidence=0.5,
            model_used="",
        )
        assert rule_no_model.used_llm is False


class TestLearnedRulesSnapshot:
    """Tests for LearnedRulesSnapshot dataclass."""

    def test_create_snapshot(self) -> None:
        """Should create LearnedRulesSnapshot with defaults."""
        snapshot = LearnedRulesSnapshot(root_path="/test")
        assert snapshot.root_path == "/test"
        assert snapshot.rules == []
        assert snapshot.total_folders_analyzed == 0
        assert snapshot.model_used == ""
        assert snapshot.generated_at != ""

    def test_create_snapshot_with_rules(self) -> None:
        """Should create snapshot with rules."""
        rules = [
            RoutingRule(pattern="*.pdf", destination="/docs", confidence=0.9),
            RoutingRule(pattern="invoice", destination="/invoices", confidence=0.85),
        ]
        snapshot = LearnedRulesSnapshot(
            root_path="/test",
            rules=rules,
            total_folders_analyzed=5,
            model_used="qwen2.5-coder:14b",
        )
        assert len(snapshot.rules) == 2
        assert snapshot.total_folders_analyzed == 5
        assert snapshot.model_used == "qwen2.5-coder:14b"

    def test_to_dict(self) -> None:
        """Should convert snapshot to dictionary."""
        rules = [RoutingRule(pattern="test", destination="/test", confidence=0.8)]
        snapshot = LearnedRulesSnapshot(
            root_path="/root",
            rules=rules,
            total_folders_analyzed=3,
            model_used="llama3.1:8b",
        )
        d = snapshot.to_dict()
        assert d["version"] == "1.0"
        assert d["root_path"] == "/root"
        assert len(d["rules"]) == 1
        assert d["rules"][0]["pattern"] == "test"
        assert d["total_folders_analyzed"] == 3
        assert d["model_used"] == "llama3.1:8b"
        assert "generated_at" in d

    def test_from_dict(self) -> None:
        """Should create snapshot from dictionary."""
        data = {
            "version": "1.0",
            "root_path": "/root",
            "rules": [
                {"pattern": "*.pdf", "destination": "/docs", "confidence": 0.9},
            ],
            "total_folders_analyzed": 2,
            "model_used": "qwen2.5-coder:14b",
            "generated_at": "2024-01-01T00:00:00",
        }
        snapshot = LearnedRulesSnapshot.from_dict(data)
        assert snapshot.root_path == "/root"
        assert len(snapshot.rules) == 1
        assert snapshot.rules[0].pattern == "*.pdf"
        assert snapshot.total_folders_analyzed == 2
        assert snapshot.model_used == "qwen2.5-coder:14b"

    def test_save_and_load(self) -> None:
        """Should save and load snapshot to/from file."""
        rules = [
            RoutingRule(pattern="invoice", destination="/invoices", confidence=0.85),
            RoutingRule(pattern="contract", destination="/legal", confidence=0.9),
        ]
        snapshot = LearnedRulesSnapshot(
            root_path="/test",
            rules=rules,
            total_folders_analyzed=10,
            model_used="qwen2.5-coder:14b",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "rules.json"
            snapshot.save(path)

            # Verify file exists and is valid JSON
            assert path.exists()
            data = json.loads(path.read_text())
            assert data["root_path"] == "/test"
            assert len(data["rules"]) == 2

            # Load back
            loaded = LearnedRulesSnapshot.load(path)
            assert loaded.root_path == "/test"
            assert len(loaded.rules) == 2
            assert loaded.rules[0].pattern == "invoice"
            assert loaded.rules[1].pattern == "contract"

    def test_get_enabled_rules(self) -> None:
        """Should filter to only enabled rules."""
        rules = [
            RoutingRule(pattern="a", destination="/a", confidence=0.8, enabled=True),
            RoutingRule(pattern="b", destination="/b", confidence=0.7, enabled=False),
            RoutingRule(pattern="c", destination="/c", confidence=0.9, enabled=True),
        ]
        snapshot = LearnedRulesSnapshot(root_path="/test", rules=rules)

        enabled = snapshot.get_enabled_rules()
        assert len(enabled) == 2
        assert enabled[0].pattern == "a"
        assert enabled[1].pattern == "c"

    def test_get_rules_for_destination(self) -> None:
        """Should filter rules by destination."""
        rules = [
            RoutingRule(pattern="a", destination="/docs", confidence=0.8),
            RoutingRule(pattern="b", destination="/invoices", confidence=0.7),
            RoutingRule(pattern="c", destination="/docs", confidence=0.9),
        ]
        snapshot = LearnedRulesSnapshot(root_path="/test", rules=rules)

        docs_rules = snapshot.get_rules_for_destination("/docs")
        assert len(docs_rules) == 2
        assert docs_rules[0].pattern == "a"
        assert docs_rules[1].pattern == "c"


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


class TestPatternFallback:
    """Tests for pattern-based rule generation fallback."""

    def test_generate_extension_rule(self) -> None:
        """Should generate rule from dominant file extension."""
        folders = [
            FolderNode(
                path="/test/docs",
                name="docs",
                depth=0,
                file_count=10,
                file_types={".pdf": 8, ".txt": 2},
                sample_filenames=["doc1.pdf", "doc2.pdf", "readme.txt"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        generator = RuleGenerator()
        rules = generator.generate_rules(snapshot, use_llm=False)

        # Should have rule for .pdf extension
        pdf_rules = [r for r in rules.rules if ".pdf" in r.pattern]
        assert len(pdf_rules) >= 1
        assert pdf_rules[0].model_used == "pattern_fallback"
        assert pdf_rules[0].confidence > 0.5

    def test_generate_keyword_rule_from_folder_name(self) -> None:
        """Should generate keyword rule from folder name."""
        folders = [
            FolderNode(
                path="/test/invoices",
                name="invoices",
                depth=0,
                file_count=5,
                sample_filenames=["invoice_001.pdf", "invoice_002.pdf"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        generator = RuleGenerator()
        rules = generator.generate_rules(snapshot, use_llm=False)

        # Should have rule with "invoices" keyword
        keyword_rules = [r for r in rules.rules if "invoice" in r.pattern.lower()]
        assert len(keyword_rules) >= 1

    def test_generate_prefix_rule_from_samples(self) -> None:
        """Should generate prefix pattern rule from common filename prefix."""
        folders = [
            FolderNode(
                path="/test/reports",
                name="reports",
                depth=0,
                file_count=5,
                sample_filenames=[
                    "report_2024_q1.pdf",
                    "report_2024_q2.pdf",
                    "report_2024_q3.pdf",
                    "report_2023_annual.pdf",
                ],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        generator = RuleGenerator()
        rules = generator.generate_rules(snapshot, use_llm=False)

        # Should have rule with "report" prefix
        prefix_rules = [r for r in rules.rules if "report" in r.pattern.lower()]
        assert len(prefix_rules) >= 1

    def test_generate_year_pattern_rule(self) -> None:
        """Should generate year pattern rule from naming patterns."""
        folders = [
            FolderNode(
                path="/test/tax",
                name="tax",
                depth=0,
                file_count=5,
                naming_patterns=["YYYY_*"],
                sample_filenames=["2024_w2.pdf", "2024_1099.pdf", "2023_return.pdf"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        generator = RuleGenerator()
        rules = generator.generate_rules(snapshot, use_llm=False)

        # Should have rule with year pattern
        year_rules = [r for r in rules.rules if "20" in r.pattern]
        assert len(year_rules) >= 1

    def test_skip_folders_with_few_files(self) -> None:
        """Should skip folders with fewer files than threshold."""
        folders = [
            FolderNode(
                path="/test/small",
                name="small",
                depth=0,
                file_count=1,  # Below default threshold of 2
                sample_filenames=["lonely.txt"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        generator = RuleGenerator(min_files_for_rule=2)
        rules = generator.generate_rules(snapshot, use_llm=False)

        assert len(rules.rules) == 0
        assert rules.total_folders_analyzed == 0

    def test_max_rules_per_folder_limit(self) -> None:
        """Should respect max_rules_per_folder limit."""
        folders = [
            FolderNode(
                path="/test/mixed",
                name="mixed",
                depth=0,
                file_count=20,
                file_types={".pdf": 10, ".docx": 5, ".xlsx": 5},
                naming_patterns=["YYYY_*"],
                sample_filenames=[
                    "report_2024.pdf",
                    "report_2023.pdf",
                    "data_2024.xlsx",
                    "notes.docx",
                ],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        generator = RuleGenerator()
        rules = generator.generate_rules(snapshot, use_llm=False, max_rules_per_folder=2)

        # Should have at most 2 rules
        assert len(rules.rules) <= 2


class TestLLMGeneration:
    """Tests for LLM-powered rule generation."""

    def test_generate_with_llm_success(self) -> None:
        """Should successfully generate rules using LLM."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = True
        mock_client.generate.return_value = MagicMock(
            success=True,
            text='{"rules": [{"pattern": "invoice", "confidence": 0.92, "reasoning": "Invoice documents"}]}',
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

        generator = RuleGenerator(llm_client=mock_client)
        result = generator.generate_rules(snapshot)

        assert len(result.rules) >= 1
        llm_rules = [r for r in result.rules if r.used_llm]
        assert len(llm_rules) >= 1
        assert llm_rules[0].pattern == "invoice"
        assert llm_rules[0].confidence == 0.92
        assert llm_rules[0].model_used == "qwen2.5-coder:14b"

    def test_generate_with_llm_uses_model_router(self) -> None:
        """Should use model router to select model."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = True
        mock_client.generate.return_value = MagicMock(
            success=True,
            text='{"rules": [{"pattern": "contract", "confidence": 0.88, "reasoning": "Legal contracts"}]}',
            model_used="qwen2.5-coder:14b",
        )

        mock_router = MagicMock()
        mock_router.route.return_value = MagicMock(model="qwen2.5-coder:14b")

        folders = [
            FolderNode(
                path="/test/legal",
                name="legal",
                depth=0,
                file_count=5,
                sample_filenames=["contract.pdf", "agreement.pdf"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        generator = RuleGenerator(llm_client=mock_client, model_router=mock_router)
        result = generator.generate_rules(snapshot)

        mock_router.route.assert_called()
        assert result.model_used == "qwen2.5-coder:14b"

    def test_generate_llm_fallback_on_unavailable(self) -> None:
        """Should fall back to patterns when LLM unavailable."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = False

        folders = [
            FolderNode(
                path="/test/invoices",
                name="invoices",
                depth=0,
                file_count=5,
                file_types={".pdf": 5},
                sample_filenames=["invoice_001.pdf", "invoice_002.pdf"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        generator = RuleGenerator(llm_client=mock_client)
        result = generator.generate_rules(snapshot)

        # Should use pattern fallback
        assert result.model_used == "pattern_fallback"
        assert all(r.model_used == "pattern_fallback" for r in result.rules)

    def test_generate_llm_fallback_on_generation_failure(self) -> None:
        """Should fall back to patterns when LLM generation fails."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = True
        mock_client.generate.return_value = MagicMock(
            success=False,
            text="",
            error="Model error",
        )

        folders = [
            FolderNode(
                path="/test/docs",
                name="docs",
                depth=0,
                file_count=5,
                file_types={".pdf": 4, ".txt": 1},
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        generator = RuleGenerator(llm_client=mock_client)
        result = generator.generate_rules(snapshot)

        # Should use pattern fallback
        assert all(r.model_used == "pattern_fallback" for r in result.rules)

    def test_generate_llm_handles_malformed_json(self) -> None:
        """Should fall back to patterns on malformed JSON response."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = True
        mock_client.generate.return_value = MagicMock(
            success=True,
            text="This is not valid JSON at all",
            model_used="qwen2.5-coder:14b",
        )

        folders = [
            FolderNode(
                path="/test/reports",
                name="reports",
                depth=0,
                file_count=5,
                file_types={".pdf": 5},
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        generator = RuleGenerator(llm_client=mock_client)
        result = generator.generate_rules(snapshot)

        # Should fall back to patterns
        assert all(r.model_used == "pattern_fallback" for r in result.rules)

    def test_generate_llm_extracts_json_from_markdown(self) -> None:
        """Should extract JSON from markdown code blocks."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = True
        mock_client.generate.return_value = MagicMock(
            success=True,
            text="""Here are the rules:
```json
{"rules": [{"pattern": "tax", "confidence": 0.9, "reasoning": "Tax documents"}]}
```
Let me know if you need more.""",
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

        generator = RuleGenerator(llm_client=mock_client)
        result = generator.generate_rules(snapshot)

        llm_rules = [r for r in result.rules if r.used_llm]
        assert len(llm_rules) >= 1
        assert llm_rules[0].pattern == "tax"

    def test_generate_llm_clamps_confidence(self) -> None:
        """Should clamp confidence to valid range."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = True
        mock_client.generate.return_value = MagicMock(
            success=True,
            text='{"rules": [{"pattern": "test", "confidence": 1.5, "reasoning": "Test"}]}',
            model_used="qwen2.5-coder:14b",
        )

        folders = [
            FolderNode(
                path="/test/data",
                name="data",
                depth=0,
                file_count=5,
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        generator = RuleGenerator(llm_client=mock_client)
        result = generator.generate_rules(snapshot)

        llm_rules = [r for r in result.rules if r.used_llm]
        if llm_rules:
            assert llm_rules[0].confidence <= 1.0

    def test_generate_multiple_rules_per_folder(self) -> None:
        """Should generate multiple rules per folder from LLM."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = True
        mock_client.generate.return_value = MagicMock(
            success=True,
            text='{"rules": [{"pattern": "invoice", "confidence": 0.9, "reasoning": "Invoices"}, {"pattern": "receipt", "confidence": 0.85, "reasoning": "Receipts"}]}',
            model_used="qwen2.5-coder:14b",
        )

        folders = [
            FolderNode(
                path="/test/finance",
                name="finance",
                depth=0,
                file_count=10,
                sample_filenames=["invoice_001.pdf", "receipt_jan.pdf"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        generator = RuleGenerator(llm_client=mock_client)
        result = generator.generate_rules(snapshot, max_rules_per_folder=3)

        llm_rules = [r for r in result.rules if r.used_llm]
        assert len(llm_rules) == 2
        patterns = [r.pattern for r in llm_rules]
        assert "invoice" in patterns
        assert "receipt" in patterns


class TestConvenienceFunction:
    """Tests for generate_rules convenience function."""

    def test_generate_rules_without_llm(self) -> None:
        """Should work with pattern fallback only."""
        folders = [
            FolderNode(
                path="/test/invoices",
                name="invoices",
                depth=0,
                file_count=5,
                file_types={".pdf": 5},
                sample_filenames=["invoice_001.pdf", "invoice_002.pdf"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        result = generate_rules(snapshot, use_llm=False)

        assert result.model_used == "pattern_fallback"
        assert result.total_folders_analyzed >= 1

    def test_generate_rules_with_llm_client(self) -> None:
        """Should use provided LLM client."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = True
        mock_client.generate.return_value = MagicMock(
            success=True,
            text='{"rules": [{"pattern": "contract", "confidence": 0.9, "reasoning": "Contracts"}]}',
            model_used="qwen2.5-coder:14b",
        )

        folders = [
            FolderNode(
                path="/test/legal",
                name="legal",
                depth=0,
                file_count=5,
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        result = generate_rules(snapshot, llm_client=mock_client)

        assert result.model_used == "qwen2.5-coder:14b"

    def test_generate_rules_with_output_path(self) -> None:
        """Should save rules to output path."""
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

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "rules.json"
            result = generate_rules(snapshot, use_llm=False, output_path=output_path)

            assert output_path.exists()
            loaded = load_rules(output_path)
            assert loaded.root_path == result.root_path


class TestLoadRules:
    """Tests for load_rules function."""

    def test_load_rules_from_file(self) -> None:
        """Should load rules from existing file."""
        rules_data = {
            "version": "1.0",
            "root_path": "/test",
            "rules": [
                {"pattern": "invoice", "destination": "/invoices", "confidence": 0.9},
            ],
            "total_folders_analyzed": 1,
            "model_used": "qwen2.5-coder:14b",
            "generated_at": "2024-01-01T00:00:00",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "rules.json"
            path.write_text(json.dumps(rules_data))

            result = load_rules(path)

            assert result.root_path == "/test"
            assert len(result.rules) == 1
            assert result.rules[0].pattern == "invoice"

    def test_load_rules_file_not_found(self) -> None:
        """Should raise FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            load_rules("/nonexistent/path/rules.json")


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_snapshot(self) -> None:
        """Should handle empty snapshot gracefully."""
        snapshot = _create_mock_snapshot([])

        generator = RuleGenerator()
        result = generator.generate_rules(snapshot, use_llm=False)

        assert len(result.rules) == 0
        assert result.total_folders_analyzed == 0

    def test_llm_exception_handling(self) -> None:
        """Should handle LLM exceptions gracefully."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.side_effect = Exception("Connection error")

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

        generator = RuleGenerator(llm_client=mock_client)
        result = generator.generate_rules(snapshot)

        # Should fall back to patterns despite exception
        assert all(r.model_used == "pattern_fallback" for r in result.rules)

    def test_router_exception_handling(self) -> None:
        """Should use default model when router fails."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = True
        mock_client.generate.return_value = MagicMock(
            success=True,
            text='{"rules": [{"pattern": "test", "confidence": 0.8, "reasoning": "Test"}]}',
            model_used="qwen2.5-coder:14b",
        )

        mock_router = MagicMock()
        mock_router.route.side_effect = RuntimeError("No models available")

        folders = [
            FolderNode(
                path="/test/data",
                name="data",
                depth=0,
                file_count=5,
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        generator = RuleGenerator(llm_client=mock_client, model_router=mock_router)
        result = generator.generate_rules(snapshot)

        # Should still succeed with default model
        assert result.total_folders_analyzed >= 1

    def test_folder_with_no_file_types(self) -> None:
        """Should handle folder with empty file_types."""
        folders = [
            FolderNode(
                path="/test/empty_types",
                name="empty_types",
                depth=0,
                file_count=5,  # Has files but no types recorded
                file_types={},
                sample_filenames=["file1", "file2", "file3"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        generator = RuleGenerator()
        result = generator.generate_rules(snapshot, use_llm=False)

        # Should still generate keyword rule from folder name
        keyword_rules = [r for r in result.rules if "empty_types" in r.pattern]
        assert len(keyword_rules) >= 1

    def test_folder_with_numeric_name(self) -> None:
        """Should not generate keyword rule for numeric folder name."""
        folders = [
            FolderNode(
                path="/test/2024",
                name="2024",
                depth=0,
                file_count=5,
                file_types={".pdf": 5},
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        generator = RuleGenerator()
        result = generator.generate_rules(snapshot, use_llm=False)

        # Should not have a rule with just "2024" as keyword
        # (but may have .pdf extension rule)
        keyword_rules = [r for r in result.rules if r.pattern == "2024"]
        assert len(keyword_rules) == 0

    def test_multiple_folders_generate_rules(self) -> None:
        """Should generate rules from multiple folders."""
        folders = [
            FolderNode(
                path="/test/invoices",
                name="invoices",
                depth=0,
                file_count=5,
                file_types={".pdf": 5},
            ),
            FolderNode(
                path="/test/contracts",
                name="contracts",
                depth=0,
                file_count=5,
                file_types={".docx": 5},
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        generator = RuleGenerator()
        result = generator.generate_rules(snapshot, use_llm=False)

        # Should analyze both folders
        assert result.total_folders_analyzed == 2

        # Should have rules for both destinations
        destinations = {r.destination for r in result.rules}
        assert "/test/invoices" in destinations
        assert "/test/contracts" in destinations
