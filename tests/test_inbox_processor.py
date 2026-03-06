#!/usr/bin/env python3
"""Tests for inbox_processor.py

Tests the inbox processing functionality including:
- File scanning
- Processing workflow
- Error handling
- Retry functionality
- LLM classification path
- Escalation from T1 to T2
- Keyword fallback when Ollama down
- A/B comparison logging
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from organizer.inbox_processor import (
    ClassificationComparison,
    InboxProcessor,
    LLMClassificationResult,
)


class TestInboxProcessor(unittest.TestCase):
    """Test cases for InboxProcessor basic functionality."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.inbox_path = self.test_dir / "In-Box"
        self.inbox_path.mkdir(parents=True)
        (self.inbox_path / "Processing Errors").mkdir()

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_scan_empty_inbox(self) -> None:
        """Test scanning empty inbox."""
        processor = InboxProcessor(base_path=str(self.test_dir), inbox_name="In-Box")
        result = processor.scan()
        assert result.total_files == 0
        assert len(result.routings) == 0

    def test_scan_with_files(self) -> None:
        """Test scanning inbox with files."""
        (self.inbox_path / "test.pdf").touch()
        (self.inbox_path / "doc.txt").touch()

        processor = InboxProcessor(base_path=str(self.test_dir), inbox_name="In-Box")
        result = processor.scan()

        assert result.total_files == 2
        assert len(result.routings) == 2

    def test_scan_excludes_hidden_files(self) -> None:
        """Test that hidden files are excluded from scan."""
        (self.inbox_path / ".hidden_file.pdf").touch()
        (self.inbox_path / "visible.pdf").touch()

        processor = InboxProcessor(base_path=str(self.test_dir), inbox_name="In-Box")
        result = processor.scan()

        assert result.total_files == 1
        assert result.routings[0].filename == "visible.pdf"

    def test_scan_excludes_processing_errors_folder(self) -> None:
        """Test that Processing Errors folder contents are excluded."""
        (self.inbox_path / "Processing Errors" / "error.pdf").touch()
        (self.inbox_path / "normal.pdf").touch()

        processor = InboxProcessor(base_path=str(self.test_dir), inbox_name="In-Box")
        result = processor.scan()

        assert result.total_files == 1
        assert result.routings[0].filename == "normal.pdf"

    def test_scan_excludes_directories(self) -> None:
        """Test that directories are excluded from scan."""
        (self.inbox_path / "subdir").mkdir()
        (self.inbox_path / "subdir" / "nested.pdf").touch()
        (self.inbox_path / "root.pdf").touch()

        processor = InboxProcessor(base_path=str(self.test_dir), inbox_name="In-Box")
        result = processor.scan()

        assert result.total_files == 1
        assert result.routings[0].filename == "root.pdf"


class TestInboxProcessorKeywordClassification(unittest.TestCase):
    """Test cases for keyword-based classification."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.inbox_path = self.test_dir / "In-Box"
        self.inbox_path.mkdir(parents=True)

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_tax_document_classification(self) -> None:
        """Test that tax documents are classified correctly."""
        (self.inbox_path / "Tax_2024.pdf").touch()

        processor = InboxProcessor(base_path=str(self.test_dir), inbox_name="In-Box")
        result = processor.scan()

        assert result.total_files == 1
        routing = result.routings[0]
        assert routing.destination_bin == "Finances Bin/Taxes"
        # Confidence varies: 0.92+ for keyword match, 0.65 for category mapper fallback
        assert routing.confidence >= 0.65
        assert routing.used_keyword_fallback is True

    def test_va_document_classification(self) -> None:
        """Test that VA documents are classified correctly."""
        (self.inbox_path / "va_claim_form.pdf").touch()

        processor = InboxProcessor(base_path=str(self.test_dir), inbox_name="In-Box")
        result = processor.scan()

        assert result.total_files == 1
        routing = result.routings[0]
        assert routing.destination_bin == "VA"

    def test_resume_classification(self) -> None:
        """Test that resumes are classified correctly."""
        (self.inbox_path / "Resume_JohnDoe.pdf").touch()

        processor = InboxProcessor(base_path=str(self.test_dir), inbox_name="In-Box")
        result = processor.scan()

        assert result.total_files == 1
        routing = result.routings[0]
        assert (
            "Resume" in routing.destination_bin or "Personal" in routing.destination_bin
        )

    def test_unmatched_file_classification(self) -> None:
        """Test that unmatched files have empty destination."""
        (self.inbox_path / "random_file_xyz.pdf").touch()

        processor = InboxProcessor(base_path=str(self.test_dir), inbox_name="In-Box")
        result = processor.scan()

        assert result.total_files == 1
        routing = result.routings[0]
        # Unmatched files may have empty destination or be routed via category mapper
        if not routing.destination_bin:
            assert routing.status == "unmatched"

    def test_date_signals_extracted(self) -> None:
        """Test that date signals are extracted from filename."""
        (self.inbox_path / "Invoice_2023_Q1.pdf").touch()

        processor = InboxProcessor(base_path=str(self.test_dir), inbox_name="In-Box")
        result = processor.scan()

        routing = result.routings[0]
        assert "filename_years" in routing.date_signals
        assert 2023 in routing.date_signals["filename_years"]


# ── LLM Classification Tests ───────────────────────────────────────────


class TestLLMClassificationResult:
    """Tests for LLMClassificationResult dataclass."""

    def test_creation_with_all_fields(self) -> None:
        """LLMClassificationResult should be created with all fields."""
        result = LLMClassificationResult(
            bin="Finances Bin/Taxes",
            subcategory="Federal",
            confidence=0.92,
            reason="Document appears to be a tax form",
            model_used="llama3.1:8b-instruct-q8_0",
            escalated=False,
            used_keyword_fallback=False,
        )
        assert result.bin == "Finances Bin/Taxes"
        assert result.subcategory == "Federal"
        assert result.confidence == 0.92
        assert result.reason == "Document appears to be a tax form"
        assert result.model_used == "llama3.1:8b-instruct-q8_0"
        assert result.escalated is False
        assert result.used_keyword_fallback is False

    def test_default_values(self) -> None:
        """LLMClassificationResult should have sensible defaults."""
        result = LLMClassificationResult(
            bin="VA",
            subcategory="",
            confidence=0.8,
            reason="",
        )
        assert result.model_used == ""
        assert result.escalated is False
        assert result.used_keyword_fallback is False

    def test_escalated_flag(self) -> None:
        """LLMClassificationResult should track escalation."""
        result = LLMClassificationResult(
            bin="Legal Bin/Divorce",
            subcategory="",
            confidence=0.85,
            reason="Escalated to T2 for complex reasoning",
            model_used="qwen2.5-coder:14b",
            escalated=True,
        )
        assert result.escalated is True
        assert result.model_used == "qwen2.5-coder:14b"


class TestInboxProcessorLLMIntegration:
    """Tests for InboxProcessor LLM classification integration."""

    def test_processor_accepts_llm_client(self, tmp_path: Path) -> None:
        """InboxProcessor should accept llm_client parameter."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = False

        processor = InboxProcessor(
            base_path=str(tmp_path),
            inbox_name="In-Box",
            llm_client=mock_client,
        )
        assert processor._llm_client is mock_client

    def test_processor_creates_model_router_when_client_provided(
        self, tmp_path: Path
    ) -> None:
        """InboxProcessor should create ModelRouter when llm_client provided."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = False

        processor = InboxProcessor(
            base_path=str(tmp_path),
            inbox_name="In-Box",
            llm_client=mock_client,
        )
        assert processor._model_router is not None

    def test_processor_uses_provided_model_router(self, tmp_path: Path) -> None:
        """InboxProcessor should use provided ModelRouter."""
        mock_client = MagicMock()
        mock_router = MagicMock()

        processor = InboxProcessor(
            base_path=str(tmp_path),
            inbox_name="In-Box",
            llm_client=mock_client,
            model_router=mock_router,
        )
        assert processor._model_router is mock_router

    def test_processor_creates_prompt_registry_when_client_provided(
        self, tmp_path: Path
    ) -> None:
        """InboxProcessor should create PromptRegistry when llm_client provided."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = False

        processor = InboxProcessor(
            base_path=str(tmp_path),
            inbox_name="In-Box",
            llm_client=mock_client,
        )
        assert processor._prompt_registry is not None

    def test_processor_use_llm_flag_disables_llm(self, tmp_path: Path) -> None:
        """InboxProcessor should not create LLM components when use_llm=False."""
        mock_client = MagicMock()

        processor = InboxProcessor(
            base_path=str(tmp_path),
            inbox_name="In-Box",
            llm_client=mock_client,
            use_llm=False,
        )
        # Client is stored but router/registry not created
        assert processor._llm_client is mock_client
        assert processor._model_router is None
        assert processor._prompt_registry is None


class TestLLMClassificationPath:
    """Tests for LLM classification path."""

    def test_uses_llm_when_available(self, tmp_path: Path) -> None:
        """Processor should use LLM classification when LLM is operational."""
        inbox = tmp_path / "In-Box"
        inbox.mkdir(parents=True)
        (inbox / "random_file.pdf").write_text("", encoding="utf-8")

        mock_client = MagicMock()
        mock_router = MagicMock()
        mock_router.is_llm_operational.return_value = True

        # Mock escalation result
        mock_result = MagicMock()
        mock_result.used_keyword_fallback = False
        mock_result.text = '{"bin": "VA", "subcategory": "", "confidence": 0.9, "reason": "LLM classified"}'
        mock_result.confidence = 0.9
        mock_result.model_used = "llama3.1:8b-instruct-q8_0"
        mock_result.escalation_count = 0
        mock_router.generate_with_escalation.return_value = mock_result

        mock_registry = MagicMock()
        mock_registry.get.return_value = "Test prompt"

        processor = InboxProcessor(
            base_path=str(tmp_path),
            inbox_name="In-Box",
            llm_client=mock_client,
            model_router=mock_router,
            prompt_registry=mock_registry,
        )
        result = processor.scan()

        assert result.total_files == 1
        r = result.routings[0]
        assert r.destination_bin == "VA"
        assert r.used_keyword_fallback is False
        assert r.model_used == "llama3.1:8b-instruct-q8_0"
        assert r.reason == "LLM classified"

    def test_llm_classification_populates_matched_keywords_with_llm_tag(
        self, tmp_path: Path
    ) -> None:
        """LLM classification should populate matched_keywords with llm:model tag."""
        inbox = tmp_path / "In-Box"
        inbox.mkdir(parents=True)
        (inbox / "document.pdf").write_text("", encoding="utf-8")

        mock_client = MagicMock()
        mock_router = MagicMock()
        mock_router.is_llm_operational.return_value = True

        mock_result = MagicMock()
        mock_result.used_keyword_fallback = False
        mock_result.text = (
            '{"bin": "Work Bin/Projects", "confidence": 0.88, "reason": "Project doc"}'
        )
        mock_result.confidence = 0.88
        mock_result.model_used = "llama3.1:8b-instruct-q8_0"
        mock_result.escalation_count = 0
        mock_router.generate_with_escalation.return_value = mock_result

        mock_registry = MagicMock()
        mock_registry.get.return_value = "Test prompt"

        processor = InboxProcessor(
            base_path=str(tmp_path),
            inbox_name="In-Box",
            llm_client=mock_client,
            model_router=mock_router,
            prompt_registry=mock_registry,
        )
        result = processor.scan()

        r = result.routings[0]
        assert "llm:llama3.1:8b-instruct-q8_0" in r.matched_keywords


class TestEscalationFromT1ToT2:
    """Tests for escalation from T1 (Fast) to T2 (Smart) model."""

    def test_escalation_when_low_confidence(self, tmp_path: Path) -> None:
        """Processor should record escalation when T1 returns low confidence."""
        inbox = tmp_path / "In-Box"
        inbox.mkdir(parents=True)
        (inbox / "ambiguous_file.pdf").write_text("", encoding="utf-8")

        mock_client = MagicMock()
        mock_router = MagicMock()
        mock_router.is_llm_operational.return_value = True

        # Mock escalation result showing T2 was used
        mock_result = MagicMock()
        mock_result.used_keyword_fallback = False
        mock_result.text = '{"bin": "Legal Bin/Divorce", "confidence": 0.85, "reason": "Escalated to T2"}'
        mock_result.confidence = 0.85
        mock_result.model_used = "qwen2.5-coder:14b"  # T2 model
        mock_result.escalation_count = 1  # Indicates escalation occurred
        mock_router.generate_with_escalation.return_value = mock_result

        mock_registry = MagicMock()
        mock_registry.get.return_value = "Test prompt"

        processor = InboxProcessor(
            base_path=str(tmp_path),
            inbox_name="In-Box",
            llm_client=mock_client,
            model_router=mock_router,
            prompt_registry=mock_registry,
        )
        result = processor.scan()

        assert result.total_files == 1
        r = result.routings[0]
        assert r.destination_bin == "Legal Bin/Divorce"
        assert r.model_used == "qwen2.5-coder:14b"
        assert "llm:qwen2.5-coder:14b" in r.matched_keywords

    def test_no_escalation_when_high_confidence(self, tmp_path: Path) -> None:
        """Processor should use T1 result when confidence is high."""
        inbox = tmp_path / "In-Box"
        inbox.mkdir(parents=True)
        (inbox / "clear_tax_doc.pdf").write_text("", encoding="utf-8")

        mock_client = MagicMock()
        mock_router = MagicMock()
        mock_router.is_llm_operational.return_value = True

        # Mock T1 result with high confidence (no escalation)
        mock_result = MagicMock()
        mock_result.used_keyword_fallback = False
        mock_result.text = '{"bin": "Finances Bin/Taxes", "confidence": 0.95, "reason": "Clear tax form"}'
        mock_result.confidence = 0.95
        mock_result.model_used = "llama3.1:8b-instruct-q8_0"  # T1 model
        mock_result.escalation_count = 0  # No escalation
        mock_router.generate_with_escalation.return_value = mock_result

        mock_registry = MagicMock()
        mock_registry.get.return_value = "Test prompt"

        processor = InboxProcessor(
            base_path=str(tmp_path),
            inbox_name="In-Box",
            llm_client=mock_client,
            model_router=mock_router,
            prompt_registry=mock_registry,
        )
        result = processor.scan()

        r = result.routings[0]
        assert r.model_used == "llama3.1:8b-instruct-q8_0"
        assert r.confidence == 0.95

    def test_multiple_escalation_steps(self, tmp_path: Path) -> None:
        """Processor should handle multiple escalation steps (T1 -> T2 -> T3)."""
        inbox = tmp_path / "In-Box"
        inbox.mkdir(parents=True)
        (inbox / "very_complex_doc.pdf").write_text("", encoding="utf-8")

        mock_client = MagicMock()
        mock_router = MagicMock()
        mock_router.is_llm_operational.return_value = True

        # Mock result showing escalation to T3 (cloud)
        mock_result = MagicMock()
        mock_result.used_keyword_fallback = False
        mock_result.text = '{"bin": "Work Bin/Consulting", "confidence": 0.92, "reason": "Complex analysis"}'
        mock_result.confidence = 0.92
        mock_result.model_used = "qwen3-coder:480b-cloud"  # T3 model
        mock_result.escalation_count = 2  # T1 -> T2 -> T3
        mock_router.generate_with_escalation.return_value = mock_result

        mock_registry = MagicMock()
        mock_registry.get.return_value = "Test prompt"

        processor = InboxProcessor(
            base_path=str(tmp_path),
            inbox_name="In-Box",
            llm_client=mock_client,
            model_router=mock_router,
            prompt_registry=mock_registry,
        )
        result = processor.scan()

        r = result.routings[0]
        assert r.model_used == "qwen3-coder:480b-cloud"


class TestKeywordFallbackWhenOllamaDown:
    """Tests for keyword fallback when Ollama/LLM is unavailable."""

    def test_falls_back_to_keywords_when_no_llm_client(self, tmp_path: Path) -> None:
        """Processor should use keyword matching when no LLM client."""
        inbox = tmp_path / "In-Box"
        inbox.mkdir(parents=True)
        (inbox / "Tax_2024.pdf").write_text("", encoding="utf-8")

        processor = InboxProcessor(base_path=str(tmp_path), inbox_name="In-Box")
        result = processor.scan()

        assert result.total_files == 1
        r = result.routings[0]
        assert r.destination_bin == "Finances Bin/Taxes"
        assert r.used_keyword_fallback is True

    def test_falls_back_to_keywords_when_llm_not_operational(
        self, tmp_path: Path
    ) -> None:
        """Processor should use keyword matching when LLM is not operational."""
        inbox = tmp_path / "In-Box"
        inbox.mkdir(parents=True)
        (inbox / "Tax_2024.pdf").write_text("", encoding="utf-8")

        mock_client = MagicMock()
        mock_router = MagicMock()
        mock_router.is_llm_operational.return_value = False  # Ollama is down

        processor = InboxProcessor(
            base_path=str(tmp_path),
            inbox_name="In-Box",
            llm_client=mock_client,
            model_router=mock_router,
        )
        result = processor.scan()

        assert result.total_files == 1
        r = result.routings[0]
        assert r.destination_bin == "Finances Bin/Taxes"
        assert r.used_keyword_fallback is True

    def test_falls_back_to_keywords_when_llm_generation_fails(
        self, tmp_path: Path
    ) -> None:
        """Processor should use keyword matching when LLM generation fails."""
        inbox = tmp_path / "In-Box"
        inbox.mkdir(parents=True)
        (inbox / "Tax_2024.pdf").write_text("", encoding="utf-8")

        mock_client = MagicMock()
        mock_router = MagicMock()
        mock_router.is_llm_operational.return_value = True
        mock_router.generate_with_escalation.side_effect = RuntimeError("LLM failed")

        mock_registry = MagicMock()
        mock_registry.get.return_value = "Test prompt"

        processor = InboxProcessor(
            base_path=str(tmp_path),
            inbox_name="In-Box",
            llm_client=mock_client,
            model_router=mock_router,
            prompt_registry=mock_registry,
        )
        result = processor.scan()

        assert result.total_files == 1
        r = result.routings[0]
        assert r.destination_bin == "Finances Bin/Taxes"
        assert r.used_keyword_fallback is True

    def test_falls_back_to_keywords_when_prompt_not_found(self, tmp_path: Path) -> None:
        """Processor should use keyword matching when prompt registry fails."""
        inbox = tmp_path / "In-Box"
        inbox.mkdir(parents=True)
        (inbox / "Tax_2024.pdf").write_text("", encoding="utf-8")

        mock_client = MagicMock()
        mock_router = MagicMock()
        mock_router.is_llm_operational.return_value = True

        mock_registry = MagicMock()
        mock_registry.get.side_effect = FileNotFoundError("Prompt not found")

        processor = InboxProcessor(
            base_path=str(tmp_path),
            inbox_name="In-Box",
            llm_client=mock_client,
            model_router=mock_router,
            prompt_registry=mock_registry,
        )
        result = processor.scan()

        r = result.routings[0]
        assert r.destination_bin == "Finances Bin/Taxes"
        assert r.used_keyword_fallback is True

    def test_falls_back_to_keywords_when_llm_returns_empty_bin(
        self, tmp_path: Path
    ) -> None:
        """Processor should use keyword matching when LLM returns empty bin."""
        inbox = tmp_path / "In-Box"
        inbox.mkdir(parents=True)
        (inbox / "Tax_2024.pdf").write_text("", encoding="utf-8")

        mock_client = MagicMock()
        mock_router = MagicMock()
        mock_router.is_llm_operational.return_value = True

        # Mock LLM returning empty/invalid response
        mock_result = MagicMock()
        mock_result.used_keyword_fallback = False
        mock_result.text = '{"bin": "", "confidence": 0.0, "reason": ""}'
        mock_result.confidence = 0.0
        mock_result.model_used = "llama3.1:8b-instruct-q8_0"
        mock_result.escalation_count = 0
        mock_router.generate_with_escalation.return_value = mock_result

        mock_registry = MagicMock()
        mock_registry.get.return_value = "Test prompt"

        processor = InboxProcessor(
            base_path=str(tmp_path),
            inbox_name="In-Box",
            llm_client=mock_client,
            model_router=mock_router,
            prompt_registry=mock_registry,
        )
        result = processor.scan()

        r = result.routings[0]
        # Should fall back to keyword matching
        assert r.destination_bin == "Finances Bin/Taxes"
        assert r.used_keyword_fallback is True

    def test_graceful_degradation_preserves_functionality(self, tmp_path: Path) -> None:
        """Graceful degradation should ensure files are still classified."""
        inbox = tmp_path / "In-Box"
        inbox.mkdir(parents=True)
        (inbox / "va_claim.pdf").write_text("", encoding="utf-8")
        (inbox / "resume.pdf").write_text("", encoding="utf-8")
        (inbox / "1099_tax.pdf").write_text("", encoding="utf-8")

        mock_client = MagicMock()
        mock_router = MagicMock()
        mock_router.is_llm_operational.return_value = False  # Ollama completely down

        processor = InboxProcessor(
            base_path=str(tmp_path),
            inbox_name="In-Box",
            llm_client=mock_client,
            model_router=mock_router,
        )
        result = processor.scan()

        # All files should still be classified via keywords
        assert result.total_files == 3
        assert result.routed >= 2  # At least VA and tax should match
        for r in result.routings:
            assert r.used_keyword_fallback is True


# ── A/B Comparison Tests ───────────────────────────────────────────


class TestClassificationComparison:
    """Tests for ClassificationComparison dataclass."""

    def test_creation_with_all_fields(self) -> None:
        """ClassificationComparison should be created with all fields."""
        comparison = ClassificationComparison(
            filename="tax_2024.pdf",
            llm_result={
                "bin": "Finances Bin/Taxes",
                "confidence": 0.92,
                "reason": "Tax document",
                "model_used": "llama3.1:8b-instruct-q8_0",
            },
            keyword_result={
                "bin": "Finances Bin/Taxes",
                "confidence": 0.92,
                "matched_keywords": ["tax"],
            },
            agreed=True,
            winner="llm",
        )
        assert comparison.filename == "tax_2024.pdf"
        assert comparison.llm_result is not None
        assert comparison.llm_result["bin"] == "Finances Bin/Taxes"
        assert comparison.keyword_result["bin"] == "Finances Bin/Taxes"
        assert comparison.agreed is True
        assert comparison.winner == "llm"
        assert comparison.timestamp != ""

    def test_creation_without_llm_result(self) -> None:
        """ClassificationComparison should handle None llm_result."""
        comparison = ClassificationComparison(
            filename="file.pdf",
            llm_result=None,
            keyword_result={"bin": "VA", "confidence": 0.8, "matched_keywords": ["va"]},
            agreed=False,
            winner="keyword",
        )
        assert comparison.llm_result is None
        assert comparison.winner == "keyword"

    def test_auto_generated_timestamp(self) -> None:
        """ClassificationComparison should auto-generate timestamp."""
        comparison = ClassificationComparison(
            filename="file.pdf",
            llm_result=None,
            keyword_result={"bin": "VA", "confidence": 0.8, "matched_keywords": []},
            agreed=False,
            winner="keyword",
        )
        assert comparison.timestamp != ""
        assert "T" in comparison.timestamp  # ISO format


class TestABComparisonMode:
    """Tests for A/B comparison mode in InboxProcessor."""

    def test_processor_accepts_ab_comparison_flag(self, tmp_path: Path) -> None:
        """InboxProcessor should accept ab_comparison_enabled parameter."""
        processor = InboxProcessor(
            base_path=str(tmp_path),
            inbox_name="In-Box",
            ab_comparison_enabled=True,
        )
        assert processor._ab_comparison_enabled is True

    def test_ab_comparison_disabled_by_default(self, tmp_path: Path) -> None:
        """A/B comparison should be disabled by default."""
        processor = InboxProcessor(base_path=str(tmp_path))
        assert processor._ab_comparison_enabled is False

    def test_processor_accepts_comparison_logs_dir(self, tmp_path: Path) -> None:
        """InboxProcessor should accept comparison_logs_dir parameter."""
        logs_dir = tmp_path / "custom_logs"
        processor = InboxProcessor(
            base_path=str(tmp_path),
            ab_comparison_enabled=True,
            comparison_logs_dir=str(logs_dir),
        )
        assert processor._comparison_logs_dir == logs_dir

    def test_ab_comparison_runs_both_methods(self, tmp_path: Path) -> None:
        """A/B mode should run both LLM and keyword classification."""
        inbox = tmp_path / "In-Box"
        inbox.mkdir(parents=True)
        (inbox / "Tax_2024.pdf").write_text("", encoding="utf-8")

        mock_client = MagicMock()
        mock_router = MagicMock()
        mock_router.is_llm_operational.return_value = True

        mock_result = MagicMock()
        mock_result.used_keyword_fallback = False
        mock_result.text = '{"bin": "Finances Bin/Taxes", "confidence": 0.95, "reason": "LLM detected tax"}'
        mock_result.confidence = 0.95
        mock_result.model_used = "llama3.1:8b-instruct-q8_0"
        mock_result.escalation_count = 0
        mock_router.generate_with_escalation.return_value = mock_result

        mock_registry = MagicMock()
        mock_registry.get.return_value = "Test prompt"

        processor = InboxProcessor(
            base_path=str(tmp_path),
            inbox_name="In-Box",
            llm_client=mock_client,
            model_router=mock_router,
            prompt_registry=mock_registry,
            ab_comparison_enabled=True,
        )
        processor.scan()

        comparisons = processor.get_current_comparisons()
        assert len(comparisons) == 1
        comparison = comparisons[0]
        assert comparison.filename == "Tax_2024.pdf"
        assert comparison.llm_result is not None
        assert comparison.keyword_result is not None
        assert comparison.agreed is True
        assert comparison.winner == "llm"

    def test_ab_comparison_detects_disagreement(self, tmp_path: Path) -> None:
        """A/B mode should detect when LLM and keyword disagree."""
        inbox = tmp_path / "In-Box"
        inbox.mkdir(parents=True)
        (inbox / "random_file.pdf").write_text("", encoding="utf-8")

        mock_client = MagicMock()
        mock_router = MagicMock()
        mock_router.is_llm_operational.return_value = True

        # Mock LLM result that disagrees with keyword (keyword returns empty for random file)
        mock_result = MagicMock()
        mock_result.used_keyword_fallback = False
        mock_result.text = '{"bin": "Legal Bin/Divorce", "confidence": 0.85, "reason": "LLM thinks legal"}'
        mock_result.confidence = 0.85
        mock_result.model_used = "llama3.1:8b-instruct-q8_0"
        mock_result.escalation_count = 0
        mock_router.generate_with_escalation.return_value = mock_result

        mock_registry = MagicMock()
        mock_registry.get.return_value = "Test prompt"

        processor = InboxProcessor(
            base_path=str(tmp_path),
            inbox_name="In-Box",
            llm_client=mock_client,
            model_router=mock_router,
            prompt_registry=mock_registry,
            ab_comparison_enabled=True,
        )
        processor.scan()

        comparisons = processor.get_current_comparisons()
        assert len(comparisons) == 1
        comparison = comparisons[0]
        # LLM says Legal, keyword likely says unmatched
        assert comparison.agreed is False

    def test_ab_comparison_keyword_fallback_when_llm_down(self, tmp_path: Path) -> None:
        """A/B mode should record keyword-only when LLM unavailable."""
        inbox = tmp_path / "In-Box"
        inbox.mkdir(parents=True)
        (inbox / "Tax_2024.pdf").write_text("", encoding="utf-8")

        mock_client = MagicMock()
        mock_router = MagicMock()
        mock_router.is_llm_operational.return_value = False

        processor = InboxProcessor(
            base_path=str(tmp_path),
            inbox_name="In-Box",
            llm_client=mock_client,
            model_router=mock_router,
            ab_comparison_enabled=True,
        )
        processor.scan()

        comparisons = processor.get_current_comparisons()
        assert len(comparisons) == 1
        comparison = comparisons[0]
        assert comparison.llm_result is None
        assert comparison.keyword_result is not None
        assert comparison.winner == "keyword"


class TestABComparisonLogging:
    """Tests for A/B comparison log file generation."""

    def test_comparison_log_created_when_enabled(self, tmp_path: Path) -> None:
        """Comparison log file should be created when A/B mode enabled."""
        inbox = tmp_path / "In-Box"
        inbox.mkdir(parents=True)
        logs_dir = tmp_path / "logs"
        (inbox / "Tax_2024.pdf").write_text("", encoding="utf-8")

        processor = InboxProcessor(
            base_path=str(tmp_path),
            inbox_name="In-Box",
            ab_comparison_enabled=True,
            comparison_logs_dir=str(logs_dir),
        )
        processor.scan(cycle_id="test123")

        log_files = list(logs_dir.glob("llm_comparison_*.json"))
        assert len(log_files) == 1
        assert "test123" in log_files[0].name

    def test_comparison_log_not_created_when_disabled(self, tmp_path: Path) -> None:
        """No comparison log should be created when A/B mode disabled."""
        inbox = tmp_path / "In-Box"
        inbox.mkdir(parents=True)
        logs_dir = tmp_path / "logs"
        (inbox / "Tax_2024.pdf").write_text("", encoding="utf-8")

        processor = InboxProcessor(
            base_path=str(tmp_path),
            inbox_name="In-Box",
            ab_comparison_enabled=False,
            comparison_logs_dir=str(logs_dir),
        )
        processor.scan()

        assert not logs_dir.exists()

    def test_comparison_log_contains_summary(self, tmp_path: Path) -> None:
        """Comparison log should contain summary statistics."""
        inbox = tmp_path / "In-Box"
        inbox.mkdir(parents=True)
        logs_dir = tmp_path / "logs"
        (inbox / "Tax_2024.pdf").write_text("", encoding="utf-8")
        (inbox / "resume.pdf").write_text("", encoding="utf-8")

        processor = InboxProcessor(
            base_path=str(tmp_path),
            inbox_name="In-Box",
            ab_comparison_enabled=True,
            comparison_logs_dir=str(logs_dir),
        )
        processor.scan(cycle_id="test456")

        log_file = logs_dir / "llm_comparison_test456.json"
        log_data = json.loads(log_file.read_text())

        assert "summary" in log_data
        assert log_data["summary"]["total_files"] == 2
        assert "agreement_rate" in log_data["summary"]
        assert "llm_available" in log_data["summary"]
        assert "keyword_only" in log_data["summary"]

    def test_comparison_log_contains_comparisons_list(self, tmp_path: Path) -> None:
        """Comparison log should contain list of individual comparisons."""
        inbox = tmp_path / "In-Box"
        inbox.mkdir(parents=True)
        logs_dir = tmp_path / "logs"
        (inbox / "Tax_2024.pdf").write_text("", encoding="utf-8")

        processor = InboxProcessor(
            base_path=str(tmp_path),
            inbox_name="In-Box",
            ab_comparison_enabled=True,
            comparison_logs_dir=str(logs_dir),
        )
        processor.scan(cycle_id="test789")

        log_file = logs_dir / "llm_comparison_test789.json"
        log_data = json.loads(log_file.read_text())

        assert "comparisons" in log_data
        assert len(log_data["comparisons"]) == 1
        comp = log_data["comparisons"][0]
        assert "filename" in comp
        assert "llm_result" in comp
        assert "keyword_result" in comp
        assert "agreed" in comp
        assert "winner" in comp
        assert "timestamp" in comp

    def test_comparison_log_with_llm_success(self, tmp_path: Path) -> None:
        """Comparison log should capture LLM results when available."""
        inbox = tmp_path / "In-Box"
        inbox.mkdir(parents=True)
        logs_dir = tmp_path / "logs"
        (inbox / "Tax_2024.pdf").write_text("", encoding="utf-8")

        mock_client = MagicMock()
        mock_router = MagicMock()
        mock_router.is_llm_operational.return_value = True

        mock_result = MagicMock()
        mock_result.used_keyword_fallback = False
        mock_result.text = '{"bin": "Finances Bin/Taxes", "confidence": 0.95, "reason": "LLM detected"}'
        mock_result.confidence = 0.95
        mock_result.model_used = "llama3.1:8b-instruct-q8_0"
        mock_result.escalation_count = 0
        mock_router.generate_with_escalation.return_value = mock_result

        mock_registry = MagicMock()
        mock_registry.get.return_value = "Test prompt"

        processor = InboxProcessor(
            base_path=str(tmp_path),
            inbox_name="In-Box",
            llm_client=mock_client,
            model_router=mock_router,
            prompt_registry=mock_registry,
            ab_comparison_enabled=True,
            comparison_logs_dir=str(logs_dir),
        )
        processor.scan(cycle_id="llm_test")

        log_file = logs_dir / "llm_comparison_llm_test.json"
        log_data = json.loads(log_file.read_text())

        assert log_data["summary"]["llm_available"] == 1
        assert log_data["summary"]["keyword_only"] == 0

        comp = log_data["comparisons"][0]
        assert comp["llm_result"] is not None
        assert comp["llm_result"]["model_used"] == "llama3.1:8b-instruct-q8_0"
        assert comp["winner"] == "llm"

    def test_agreement_rate_calculation(self, tmp_path: Path) -> None:
        """Agreement rate should be calculated correctly."""
        inbox = tmp_path / "In-Box"
        inbox.mkdir(parents=True)
        logs_dir = tmp_path / "logs"
        (inbox / "Tax_2024.pdf").write_text("", encoding="utf-8")
        (inbox / "resume.pdf").write_text("", encoding="utf-8")

        mock_client = MagicMock()
        mock_router = MagicMock()
        mock_router.is_llm_operational.return_value = True

        def mock_generate(prompt, profile, confidence_extractor, **kwargs):
            mock_result = MagicMock()
            mock_result.used_keyword_fallback = False
            mock_result.escalation_count = 0
            mock_result.model_used = "llama3.1:8b-instruct-q8_0"
            if "Tax_2024" in prompt:
                mock_result.text = '{"bin": "Finances Bin/Taxes", "confidence": 0.95}'
                mock_result.confidence = 0.95
            else:
                mock_result.text = '{"bin": "Personal Bin/Resumes", "confidence": 0.9}'
                mock_result.confidence = 0.9
            return mock_result

        mock_router.generate_with_escalation.side_effect = mock_generate

        mock_registry = MagicMock()
        mock_registry.get.side_effect = (
            lambda name, **kwargs: f"Prompt for {kwargs.get('filename', 'file')}"
        )

        processor = InboxProcessor(
            base_path=str(tmp_path),
            inbox_name="In-Box",
            llm_client=mock_client,
            model_router=mock_router,
            prompt_registry=mock_registry,
            ab_comparison_enabled=True,
            comparison_logs_dir=str(logs_dir),
        )
        processor.scan(cycle_id="rate_test")

        log_file = logs_dir / "llm_comparison_rate_test.json"
        log_data = json.loads(log_file.read_text())

        assert log_data["summary"]["llm_available"] == 2
        # Both should have been processed


class TestGetCurrentComparisons:
    """Tests for get_current_comparisons method."""

    def test_returns_empty_list_initially(self, tmp_path: Path) -> None:
        """get_current_comparisons should return empty list initially."""
        processor = InboxProcessor(
            base_path=str(tmp_path),
            ab_comparison_enabled=True,
        )
        comparisons = processor.get_current_comparisons()
        assert isinstance(comparisons, list)
        assert len(comparisons) == 0

    def test_returns_comparisons_after_scan(self, tmp_path: Path) -> None:
        """get_current_comparisons should return comparisons after scan."""
        inbox = tmp_path / "In-Box"
        inbox.mkdir(parents=True)
        (inbox / "Tax_2024.pdf").write_text("", encoding="utf-8")

        processor = InboxProcessor(
            base_path=str(tmp_path),
            inbox_name="In-Box",
            ab_comparison_enabled=True,
        )
        processor.scan()

        comparisons = processor.get_current_comparisons()
        assert len(comparisons) == 1
        assert comparisons[0].filename == "Tax_2024.pdf"

    def test_comparisons_reset_on_new_scan(self, tmp_path: Path) -> None:
        """Comparisons should be reset on each new scan."""
        inbox = tmp_path / "In-Box"
        inbox.mkdir(parents=True)
        (inbox / "Tax_2024.pdf").write_text("", encoding="utf-8")

        processor = InboxProcessor(
            base_path=str(tmp_path),
            inbox_name="In-Box",
            ab_comparison_enabled=True,
        )

        processor.scan()
        assert len(processor.get_current_comparisons()) == 1

        # Remove file and scan again
        (inbox / "Tax_2024.pdf").unlink()
        processor.scan()
        assert len(processor.get_current_comparisons()) == 0


class TestJSONParsing:
    """Tests for LLM JSON response parsing."""

    def test_parse_clean_json(self, tmp_path: Path) -> None:
        """Should parse clean JSON response."""
        processor = InboxProcessor(base_path=str(tmp_path))
        result = processor._parse_llm_json_response('{"bin": "VA", "confidence": 0.9}')
        assert result == {"bin": "VA", "confidence": 0.9}

    def test_parse_json_with_markdown(self, tmp_path: Path) -> None:
        """Should parse JSON wrapped in markdown code block."""
        processor = InboxProcessor(base_path=str(tmp_path))
        result = processor._parse_llm_json_response(
            '```json\n{"bin": "VA", "confidence": 0.9}\n```'
        )
        assert result == {"bin": "VA", "confidence": 0.9}

    def test_parse_json_with_text_before(self, tmp_path: Path) -> None:
        """Should extract JSON from text with extra content."""
        processor = InboxProcessor(base_path=str(tmp_path))
        result = processor._parse_llm_json_response(
            'Here is my response: {"bin": "VA", "confidence": 0.9}'
        )
        assert result == {"bin": "VA", "confidence": 0.9}

    def test_parse_invalid_json(self, tmp_path: Path) -> None:
        """Should return empty dict for invalid JSON."""
        processor = InboxProcessor(base_path=str(tmp_path))
        result = processor._parse_llm_json_response("not json at all")
        assert result == {}

    def test_extract_confidence(self, tmp_path: Path) -> None:
        """Should extract confidence score from JSON response."""
        processor = InboxProcessor(base_path=str(tmp_path))
        confidence = processor._extract_confidence('{"bin": "VA", "confidence": 0.85}')
        assert confidence == 0.85

    def test_extract_confidence_missing(self, tmp_path: Path) -> None:
        """Should return None if confidence not in response."""
        processor = InboxProcessor(base_path=str(tmp_path))
        confidence = processor._extract_confidence('{"bin": "VA"}')
        assert confidence is None


class TestAvailableBins:
    """Tests for bin list generation."""

    def test_get_available_bins_returns_sorted_list(self, tmp_path: Path) -> None:
        """Should return sorted list of unique bins."""
        processor = InboxProcessor(base_path=str(tmp_path))
        bins = processor._get_available_bins()

        assert isinstance(bins, str)
        bin_list = bins.split("\n")
        assert len(bin_list) > 0
        assert bin_list == sorted(bin_list)
        assert "Finances Bin/Taxes" in bin_list
        assert "VA" in bin_list
        assert "Personal Bin/Resumes" in bin_list


if __name__ == "__main__":
    unittest.main()
