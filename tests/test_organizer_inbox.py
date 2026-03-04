"""Tests for organizer.inbox_processor (LLM-native classifier with keyword fallback)."""

import json
from pathlib import Path
from unittest.mock import MagicMock

from organizer.inbox_processor import (
    InboxProcessor,
    InboxRouting,
    LLMClassificationResult,
    ClassificationComparison,
)


def test_date_signals_extracted_from_filename(tmp_path: Path) -> None:
    """Date signals should include years parsed from filename."""
    inbox = tmp_path / "In-Box"
    inbox.mkdir(parents=True)
    (inbox / "Tax_2024.pdf").write_text("", encoding="utf-8")

    processor = InboxProcessor(base_path=str(tmp_path), inbox_name="In-Box")
    result = processor.scan()

    assert result.total_files == 1
    r = result.routings[0]
    assert r.destination_bin == "Finances Bin/Taxes"
    assert "filename_years" in r.date_signals
    assert 2024 in r.date_signals["filename_years"]


def test_date_signals_include_mtime(tmp_path: Path) -> None:
    """Date signals should include mtime from file metadata."""
    inbox = tmp_path / "In-Box"
    inbox.mkdir(parents=True)
    (inbox / "resume.pdf").write_text("", encoding="utf-8")

    processor = InboxProcessor(base_path=str(tmp_path), inbox_name="In-Box")
    result = processor.scan()

    assert result.total_files == 1
    r = result.routings[0]
    assert "mtime_year" in r.date_signals
    assert "mtime_iso" in r.date_signals


def test_tax_with_year_gets_confidence_boost(tmp_path: Path) -> None:
    """Tax documents with year in filename get classified to Finances Bin/Taxes."""
    inbox = tmp_path / "In-Box"
    inbox.mkdir(parents=True)
    (inbox / "Tax_Return_2023.pdf").write_text("", encoding="utf-8")

    processor = InboxProcessor(base_path=str(tmp_path), inbox_name="In-Box")
    result = processor.scan()

    assert result.total_files == 1
    r = result.routings[0]
    assert r.destination_bin == "Finances Bin/Taxes"
    assert r.confidence >= 0.65


def test_category_mapper_fallback_for_suggestive_names(tmp_path: Path) -> None:
    """Files with names matching CategoryMapper get taxonomy-aligned destination."""
    inbox = tmp_path / "In-Box"
    inbox.mkdir(parents=True)
    (inbox / "Resume_JohnDoe.pdf").write_text("", encoding="utf-8")

    processor = InboxProcessor(base_path=str(tmp_path), inbox_name="In-Box")
    result = processor.scan()

    assert result.total_files == 1
    r = result.routings[0]
    assert r.destination_bin
    assert "Resume" in r.destination_bin or "Employment" in r.destination_bin or "category:" in str(r.matched_keywords)


# ── LLM Classification Tests ───────────────────────────────────────────


class TestLLMClassificationResult:
    """Tests for LLMClassificationResult dataclass."""

    def test_llm_classification_result_creation(self) -> None:
        """LLMClassificationResult should be created with all fields."""
        result = LLMClassificationResult(
            bin="Finances Bin/Taxes",
            subcategory="2024",
            confidence=0.92,
            reason="Document appears to be a tax form",
            model_used="llama3.1:8b",
            escalated=False,
            used_keyword_fallback=False,
        )
        assert result.bin == "Finances Bin/Taxes"
        assert result.subcategory == "2024"
        assert result.confidence == 0.92
        assert result.reason == "Document appears to be a tax form"
        assert result.model_used == "llama3.1:8b"
        assert result.escalated is False
        assert result.used_keyword_fallback is False

    def test_llm_classification_result_defaults(self) -> None:
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


class TestInboxRoutingLLMFields:
    """Tests for LLM-related fields in InboxRouting."""

    def test_inbox_routing_llm_fields_present(self) -> None:
        """InboxRouting should have LLM-related fields."""
        routing = InboxRouting(
            filename="tax_2024.pdf",
            source_path="/path/to/tax_2024.pdf",
            destination_bin="Finances Bin/Taxes",
            confidence=0.92,
            reason="Tax document detected",
            model_used="llama3.1:8b",
            used_keyword_fallback=False,
        )
        assert routing.reason == "Tax document detected"
        assert routing.model_used == "llama3.1:8b"
        assert routing.used_keyword_fallback is False

    def test_inbox_routing_llm_fields_defaults(self) -> None:
        """InboxRouting LLM fields should default to empty/False."""
        routing = InboxRouting(
            filename="file.pdf",
            source_path="/path/to/file.pdf",
            destination_bin="VA",
            confidence=0.8,
        )
        assert routing.reason == ""
        assert routing.model_used == ""
        assert routing.used_keyword_fallback is False


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

    def test_processor_creates_model_router_when_client_provided(self, tmp_path: Path) -> None:
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

    def test_processor_creates_prompt_registry_when_client_provided(self, tmp_path: Path) -> None:
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


class TestInboxProcessorKeywordFallback:
    """Tests for keyword fallback when LLM is unavailable."""

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

    def test_falls_back_to_keywords_when_llm_unavailable(self, tmp_path: Path) -> None:
        """Processor should use keyword matching when LLM is down."""
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
        )
        result = processor.scan()

        assert result.total_files == 1
        r = result.routings[0]
        assert r.destination_bin == "Finances Bin/Taxes"
        assert r.used_keyword_fallback is True

    def test_falls_back_to_keywords_when_llm_fails(self, tmp_path: Path) -> None:
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


class TestInboxProcessorLLMClassification:
    """Tests for LLM-based classification."""

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
        mock_result.model_used = "llama3.1:8b"
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
        assert r.model_used == "llama3.1:8b"
        assert r.reason == "LLM classified"

    def test_llm_classification_with_escalation(self, tmp_path: Path) -> None:
        """Processor should record escalation when it occurs."""
        inbox = tmp_path / "In-Box"
        inbox.mkdir(parents=True)
        (inbox / "ambiguous_file.pdf").write_text("", encoding="utf-8")

        mock_client = MagicMock()
        mock_router = MagicMock()
        mock_router.is_llm_operational.return_value = True

        # Mock escalation result with escalation
        mock_result = MagicMock()
        mock_result.used_keyword_fallback = False
        mock_result.text = '{"bin": "Legal Bin/Divorce", "subcategory": "", "confidence": 0.85, "reason": "Escalated to T2"}'
        mock_result.confidence = 0.85
        mock_result.model_used = "qwen2.5-coder:14b"
        mock_result.escalation_count = 1
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
        assert "llm:" in str(r.matched_keywords)


class TestInboxProcessorJSONParsing:
    """Tests for LLM JSON response parsing."""

    def test_parse_llm_json_response_clean(self, tmp_path: Path) -> None:
        """Should parse clean JSON response."""
        processor = InboxProcessor(base_path=str(tmp_path))
        result = processor._parse_llm_json_response(
            '{"bin": "VA", "confidence": 0.9}'
        )
        assert result == {"bin": "VA", "confidence": 0.9}

    def test_parse_llm_json_response_with_markdown(self, tmp_path: Path) -> None:
        """Should parse JSON wrapped in markdown code block."""
        processor = InboxProcessor(base_path=str(tmp_path))
        result = processor._parse_llm_json_response(
            '```json\n{"bin": "VA", "confidence": 0.9}\n```'
        )
        assert result == {"bin": "VA", "confidence": 0.9}

    def test_parse_llm_json_response_with_text_before(self, tmp_path: Path) -> None:
        """Should extract JSON from text with extra content."""
        processor = InboxProcessor(base_path=str(tmp_path))
        result = processor._parse_llm_json_response(
            'Here is my response: {"bin": "VA", "confidence": 0.9}'
        )
        assert result == {"bin": "VA", "confidence": 0.9}

    def test_parse_llm_json_response_invalid(self, tmp_path: Path) -> None:
        """Should return empty dict for invalid JSON."""
        processor = InboxProcessor(base_path=str(tmp_path))
        result = processor._parse_llm_json_response("not json at all")
        assert result == {}

    def test_extract_confidence_from_response(self, tmp_path: Path) -> None:
        """Should extract confidence score from JSON response."""
        processor = InboxProcessor(base_path=str(tmp_path))
        confidence = processor._extract_confidence(
            '{"bin": "VA", "confidence": 0.85}'
        )
        assert confidence == 0.85

    def test_extract_confidence_returns_none_if_missing(self, tmp_path: Path) -> None:
        """Should return None if confidence not in response."""
        processor = InboxProcessor(base_path=str(tmp_path))
        confidence = processor._extract_confidence('{"bin": "VA"}')
        assert confidence is None


class TestInboxProcessorAvailableBins:
    """Tests for bin list generation."""

    def test_get_available_bins_returns_sorted_list(self, tmp_path: Path) -> None:
        """Should return sorted list of unique bins."""
        processor = InboxProcessor(base_path=str(tmp_path))
        bins = processor._get_available_bins()

        # Should be a string with newline-separated bins
        assert isinstance(bins, str)
        bin_list = bins.split("\n")
        assert len(bin_list) > 0
        # Should be sorted
        assert bin_list == sorted(bin_list)
        # Should contain known bins
        assert "Finances Bin/Taxes" in bin_list
        assert "VA" in bin_list
        assert "Personal Bin/Resumes" in bin_list


# ── A/B Comparison Tests ───────────────────────────────────────────


class TestClassificationComparison:
    """Tests for ClassificationComparison dataclass."""

    def test_classification_comparison_creation(self) -> None:
        """ClassificationComparison should be created with all fields."""
        comparison = ClassificationComparison(
            filename="tax_2024.pdf",
            llm_result={
                "bin": "Finances Bin/Taxes",
                "confidence": 0.92,
                "reason": "Tax document",
                "model_used": "llama3.1:8b",
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
        assert comparison.timestamp != ""  # Auto-generated

    def test_classification_comparison_without_llm(self) -> None:
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

    def test_classification_comparison_auto_timestamp(self) -> None:
        """ClassificationComparison should auto-generate timestamp if not provided."""
        comparison = ClassificationComparison(
            filename="file.pdf",
            llm_result=None,
            keyword_result={"bin": "VA", "confidence": 0.8, "matched_keywords": []},
            agreed=False,
            winner="keyword",
        )
        assert comparison.timestamp != ""
        # Should be ISO format
        assert "T" in comparison.timestamp


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

    def test_processor_ab_comparison_disabled_by_default(self, tmp_path: Path) -> None:
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

        # Mock LLM result
        mock_result = MagicMock()
        mock_result.used_keyword_fallback = False
        mock_result.text = '{"bin": "Finances Bin/Taxes", "confidence": 0.95, "reason": "LLM detected tax"}'
        mock_result.confidence = 0.95
        mock_result.model_used = "llama3.1:8b"
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

        # Should have comparison logged
        comparisons = processor.get_current_comparisons()
        assert len(comparisons) == 1
        comparison = comparisons[0]
        assert comparison.filename == "Tax_2024.pdf"
        assert comparison.llm_result is not None
        assert comparison.keyword_result is not None
        # Both should agree on Taxes
        assert comparison.agreed is True
        assert comparison.winner == "llm"

    def test_ab_comparison_detects_disagreement(self, tmp_path: Path) -> None:
        """A/B mode should detect when LLM and keyword disagree."""
        inbox = tmp_path / "In-Box"
        inbox.mkdir(parents=True)
        # File that keyword would route to VA but LLM routes elsewhere
        (inbox / "random_file.pdf").write_text("", encoding="utf-8")

        mock_client = MagicMock()
        mock_router = MagicMock()
        mock_router.is_llm_operational.return_value = True

        # Mock LLM result that disagrees with keyword
        mock_result = MagicMock()
        mock_result.used_keyword_fallback = False
        mock_result.text = '{"bin": "Legal Bin/Divorce", "confidence": 0.85, "reason": "LLM thinks legal"}'
        mock_result.confidence = 0.85
        mock_result.model_used = "llama3.1:8b"
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
        # LLM says Legal, keyword says unmatched (empty bin)
        assert comparison.agreed is False

    def test_ab_comparison_keyword_fallback_when_llm_down(self, tmp_path: Path) -> None:
        """A/B mode should record keyword-only when LLM unavailable."""
        inbox = tmp_path / "In-Box"
        inbox.mkdir(parents=True)
        (inbox / "Tax_2024.pdf").write_text("", encoding="utf-8")

        mock_client = MagicMock()
        mock_router = MagicMock()
        mock_router.is_llm_operational.return_value = False  # LLM is down

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

        # Log file should exist
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

        # Log directory should not be created
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

        # Should have summary
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

        # Should have comparisons list
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
        mock_result.model_used = "llama3.1:8b"
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

        # Summary should show LLM was available
        assert log_data["summary"]["llm_available"] == 1
        assert log_data["summary"]["keyword_only"] == 0

        # Comparison should have LLM result
        comp = log_data["comparisons"][0]
        assert comp["llm_result"] is not None
        assert comp["llm_result"]["model_used"] == "llama3.1:8b"
        assert comp["winner"] == "llm"

    def test_agreement_rate_calculation(self, tmp_path: Path) -> None:
        """Agreement rate should be calculated correctly."""
        inbox = tmp_path / "In-Box"
        inbox.mkdir(parents=True)
        logs_dir = tmp_path / "logs"

        # Create files where we can control the outcomes
        (inbox / "Tax_2024.pdf").write_text("", encoding="utf-8")  # Will match both
        (inbox / "resume.pdf").write_text("", encoding="utf-8")  # Will match both

        mock_client = MagicMock()
        mock_router = MagicMock()
        mock_router.is_llm_operational.return_value = True

        # Mock LLM to agree with keyword for Tax, disagree for resume
        def mock_generate(prompt, profile, confidence_extractor, **kwargs):
            mock_result = MagicMock()
            mock_result.used_keyword_fallback = False
            mock_result.escalation_count = 0
            mock_result.model_used = "llama3.1:8b"
            if "Tax_2024" in prompt:
                mock_result.text = '{"bin": "Finances Bin/Taxes", "confidence": 0.95, "reason": ""}'
                mock_result.confidence = 0.95
            else:
                mock_result.text = '{"bin": "Personal Bin/Resumes", "confidence": 0.9, "reason": ""}'
                mock_result.confidence = 0.9
            return mock_result

        mock_router.generate_with_escalation.side_effect = mock_generate

        mock_registry = MagicMock()
        mock_registry.get.side_effect = lambda name, **kwargs: f"Prompt for {kwargs.get('filename', 'file')}"

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

        # Both should have been processed with LLM
        assert log_data["summary"]["llm_available"] == 2
        # Both LLM and keyword should agree (both route to correct bins)
        assert log_data["summary"]["agreed"] == 2
        assert log_data["summary"]["agreement_rate"] == 1.0


class TestGetCurrentComparisons:
    """Tests for get_current_comparisons method."""

    def test_get_current_comparisons_returns_list(self, tmp_path: Path) -> None:
        """get_current_comparisons should return list of comparisons."""
        processor = InboxProcessor(
            base_path=str(tmp_path),
            ab_comparison_enabled=True,
        )
        comparisons = processor.get_current_comparisons()
        assert isinstance(comparisons, list)
        assert len(comparisons) == 0

    def test_get_current_comparisons_after_scan(self, tmp_path: Path) -> None:
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

        # First scan
        processor.scan()
        assert len(processor.get_current_comparisons()) == 1

        # Remove file and scan again
        (inbox / "Tax_2024.pdf").unlink()
        processor.scan()
        assert len(processor.get_current_comparisons()) == 0
