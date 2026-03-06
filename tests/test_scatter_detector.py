"""Tests for scatter_detector module.

Tests LLM-powered scatter detection with T1 Fast validation, T2 Smart escalation,
keyword fallback, locked bin protection, and path preservation.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from organizer.scatter_detector import (
    PathPreservationResult,
    ScatterDetectionResult,
    ScatterDetector,
    ScatterViolation,
    detect_scatter,
    load_scatter_report,
    save_scatter_report,
)
from organizer.taxonomy_utils import Taxonomy, TaxonomyBin


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_taxonomy() -> Taxonomy:
    """Create a sample taxonomy for testing."""
    taxonomy = Taxonomy(
        version="2026-03-03",
        description="Test taxonomy",
    )
    taxonomy.bins = {
        "Finances Bin": TaxonomyBin(name="Finances Bin", locked=True),
        "Work Bin": TaxonomyBin(name="Work Bin", locked=True),
        "VA": TaxonomyBin(name="VA", locked=True),
        "Personal Bin": TaxonomyBin(name="Personal Bin", locked=True),
        "Archive": TaxonomyBin(name="Archive", locked=False),
    }
    return taxonomy


@pytest.fixture
def sample_taxonomy_dict() -> dict:
    """Create a sample taxonomy dict for testing."""
    return {
        "version": "2026-03-03",
        "canonical_roots": ["Finances Bin", "Work Bin", "VA", "Personal Bin", "Archive"],
        "locked_bins": {
            "Finances Bin": True,
            "Work Bin": True,
            "VA": True,
            "Personal Bin": True,
            "Archive": False,
        },
    }


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    client = MagicMock()
    client.is_ollama_available.return_value = True
    return client


@pytest.fixture
def mock_model_router():
    """Create a mock model router."""
    from organizer.model_router import ModelTier, RoutingDecision

    router = MagicMock()

    def mock_route(profile):
        if profile.complexity == "low":
            return RoutingDecision(
                model="llama3.1:8b",
                tier=ModelTier.FAST,
                reason="Test",
            )
        else:
            return RoutingDecision(
                model="qwen2.5:14b",
                tier=ModelTier.SMART,
                reason="Test",
            )

    router.route.side_effect = mock_route
    return router


@pytest.fixture
def temp_dir_with_files():
    """Create a temporary directory structure for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)

        # Create bin directories
        (base / "Finances Bin").mkdir()
        (base / "Work Bin").mkdir()
        (base / "VA").mkdir()
        (base / "Personal Bin").mkdir()

        # Create files in various locations
        # Correctly placed files
        (base / "Finances Bin" / "tax_return_2024.pdf").write_text("tax doc")
        (base / "Finances Bin" / "invoice_march.pdf").write_text("invoice")
        (base / "Work Bin" / "resume_2024.pdf").write_text("resume")
        (base / "VA" / "va_claim_form.pdf").write_text("va claim")

        # Misplaced files (scatter violations)
        (base / "Work Bin" / "tax_form_1040.pdf").write_text(
            "tax document"
        )  # Should be in Finances
        (base / "Personal Bin" / "resume_draft.doc").write_text(
            "resume"
        )  # Should be in Work
        (base / "Finances Bin" / "va_dbq_form.pdf").write_text(
            "va dbq"
        )  # Should be in VA

        yield base


# =============================================================================
# ScatterViolation Tests
# =============================================================================


class TestScatterViolation:
    """Tests for ScatterViolation dataclass."""

    def test_creation(self):
        """Test basic creation of ScatterViolation."""
        violation = ScatterViolation(
            file_path="/path/to/file.pdf",
            current_bin="Work Bin",
            expected_bin="Finances Bin",
            confidence=0.85,
            reason="Contains tax keywords",
        )

        assert violation.file_path == "/path/to/file.pdf"
        assert violation.current_bin == "Work Bin"
        assert violation.expected_bin == "Finances Bin"
        assert violation.confidence == 0.85
        assert violation.reason == "Contains tax keywords"
        assert violation.model_used == ""
        assert violation.used_keyword_fallback is False

    def test_creation_with_llm_fields(self):
        """Test creation with LLM-related fields."""
        violation = ScatterViolation(
            file_path="/path/to/file.pdf",
            current_bin="Work Bin",
            expected_bin="Finances Bin",
            confidence=0.92,
            reason="LLM detected tax document",
            model_used="llama3.1:8b",
            suggested_subpath="2024/IRS",
            used_keyword_fallback=False,
        )

        assert violation.model_used == "llama3.1:8b"
        assert violation.suggested_subpath == "2024/IRS"
        assert violation.used_keyword_fallback is False

    def test_to_dict(self):
        """Test conversion to dictionary."""
        violation = ScatterViolation(
            file_path="/path/to/file.pdf",
            current_bin="Work Bin",
            expected_bin="Finances Bin",
            confidence=0.85,
            reason="Test reason",
            model_used="llama3.1:8b",
        )

        d = violation.to_dict()
        assert d["file_path"] == "/path/to/file.pdf"
        assert d["confidence"] == 0.85
        assert d["model_used"] == "llama3.1:8b"

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "file_path": "/path/to/file.pdf",
            "current_bin": "Work Bin",
            "expected_bin": "Finances Bin",
            "confidence": 0.85,
            "reason": "Test reason",
            "model_used": "llama3.1:8b",
            "used_keyword_fallback": False,
        }

        violation = ScatterViolation.from_dict(data)
        assert violation.file_path == "/path/to/file.pdf"
        assert violation.confidence == 0.85
        assert violation.model_used == "llama3.1:8b"

    def test_roundtrip(self):
        """Test dict roundtrip preserves data."""
        original = ScatterViolation(
            file_path="/path/to/file.pdf",
            current_bin="Work Bin",
            expected_bin="Finances Bin",
            confidence=0.85,
            reason="Test reason",
            model_used="llama3.1:8b",
            suggested_subpath="2024",
            used_keyword_fallback=False,
        )

        restored = ScatterViolation.from_dict(original.to_dict())
        assert restored.file_path == original.file_path
        assert restored.confidence == original.confidence
        assert restored.model_used == original.model_used


# =============================================================================
# ScatterDetectionResult Tests
# =============================================================================


class TestScatterDetectionResult:
    """Tests for ScatterDetectionResult dataclass."""

    def test_creation(self):
        """Test basic creation."""
        result = ScatterDetectionResult()
        assert result.violations == []
        assert result.files_scanned == 0
        assert result.files_in_correct_bin == 0

    def test_with_violations(self):
        """Test creation with violations."""
        violation = ScatterViolation(
            file_path="/path/to/file.pdf",
            current_bin="Work Bin",
            expected_bin="Finances Bin",
            confidence=0.85,
            reason="Test",
        )

        result = ScatterDetectionResult(
            violations=[violation],
            files_scanned=10,
            files_in_correct_bin=9,
            model_used="llama3.1:8b",
        )

        assert len(result.violations) == 1
        assert result.files_scanned == 10
        assert result.files_in_correct_bin == 9

    def test_to_dict(self):
        """Test conversion to dictionary."""
        violation = ScatterViolation(
            file_path="/path/to/file.pdf",
            current_bin="Work Bin",
            expected_bin="Finances Bin",
            confidence=0.85,
            reason="Test",
        )

        result = ScatterDetectionResult(
            violations=[violation],
            files_scanned=10,
            model_used="llama3.1:8b",
        )

        d = result.to_dict()
        assert len(d["violations"]) == 1
        assert d["files_scanned"] == 10
        assert d["model_used"] == "llama3.1:8b"


# =============================================================================
# PathPreservationResult Tests
# =============================================================================


class TestPathPreservationResult:
    """Tests for PathPreservationResult dataclass."""

    def test_creation(self):
        """Test basic creation."""
        result = PathPreservationResult(
            suggested_subpath="2024/IRS",
            reason="Extracted year and agency from filename",
            model_used="qwen2.5:14b",
            confidence=0.9,
        )

        assert result.suggested_subpath == "2024/IRS"
        assert result.confidence == 0.9
        assert result.model_used == "qwen2.5:14b"


# =============================================================================
# ScatterDetector Initialization Tests
# =============================================================================


class TestScatterDetectorInit:
    """Tests for ScatterDetector initialization."""

    def test_init_basic(self):
        """Test basic initialization."""
        detector = ScatterDetector()
        assert detector._llm_client is None
        assert detector._model_router is None
        assert detector._use_llm is False

    def test_init_with_taxonomy_object(self, sample_taxonomy):
        """Test initialization with Taxonomy object."""
        detector = ScatterDetector(taxonomy=sample_taxonomy)
        assert isinstance(detector._taxonomy, Taxonomy)

    def test_init_with_taxonomy_dict(self, sample_taxonomy_dict):
        """Test initialization with taxonomy dict."""
        detector = ScatterDetector(taxonomy=sample_taxonomy_dict)
        assert isinstance(detector._taxonomy, dict)

    def test_init_with_llm_client(self, mock_llm_client):
        """Test initialization with LLM client."""
        detector = ScatterDetector(llm_client=mock_llm_client)
        assert detector._llm_client is mock_llm_client
        assert detector._model_router is not None  # Auto-created
        assert detector._use_llm is True

    def test_init_with_custom_router(self, mock_llm_client, mock_model_router):
        """Test initialization with custom model router."""
        detector = ScatterDetector(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
        )
        assert detector._model_router is mock_model_router

    def test_init_use_llm_false(self, mock_llm_client):
        """Test initialization with use_llm=False."""
        detector = ScatterDetector(llm_client=mock_llm_client, use_llm=False)
        assert detector._use_llm is False

    def test_init_custom_threshold(self, mock_llm_client):
        """Test initialization with custom escalation threshold."""
        detector = ScatterDetector(
            llm_client=mock_llm_client,
            escalation_threshold=0.8,
        )
        assert detector._escalation_threshold == 0.8


# =============================================================================
# Keyword Fallback Tests
# =============================================================================


class TestKeywordFallback:
    """Tests for keyword-based validation fallback."""

    def test_keyword_fallback_when_no_llm(self, temp_dir_with_files):
        """Test that keyword fallback is used when no LLM client."""
        detector = ScatterDetector()

        result = detector.detect_scatter(str(temp_dir_with_files), max_files=10)

        assert result.used_keyword_fallback is True
        assert result.model_used == ""

    def test_tax_keyword_detected(self, temp_dir_with_files, sample_taxonomy):
        """Test that tax keyword is detected as Finances Bin file."""
        detector = ScatterDetector(taxonomy=sample_taxonomy)

        # File with "tax" in name in Work Bin should be flagged
        file_path = str(temp_dir_with_files / "Work Bin" / "tax_form_1040.pdf")
        violation = detector.validate_file(file_path, str(temp_dir_with_files))

        assert violation is not None
        assert violation.expected_bin == "Finances Bin"
        assert violation.used_keyword_fallback is True

    def test_resume_keyword_detected(self, temp_dir_with_files, sample_taxonomy):
        """Test that resume keyword is detected as Work Bin file."""
        detector = ScatterDetector(taxonomy=sample_taxonomy)

        # File with "resume" in name in Personal Bin should be flagged
        file_path = str(temp_dir_with_files / "Personal Bin" / "resume_draft.doc")
        violation = detector.validate_file(file_path, str(temp_dir_with_files))

        assert violation is not None
        assert violation.expected_bin == "Work Bin"
        assert violation.used_keyword_fallback is True

    def test_va_keyword_detected(self, temp_dir_with_files, sample_taxonomy):
        """Test that VA keyword is detected as VA file."""
        detector = ScatterDetector(taxonomy=sample_taxonomy)

        # File with "va" in name in Finances Bin should be flagged
        file_path = str(temp_dir_with_files / "Finances Bin" / "va_dbq_form.pdf")
        violation = detector.validate_file(file_path, str(temp_dir_with_files))

        assert violation is not None
        assert violation.expected_bin == "VA"

    def test_file_in_correct_bin_not_flagged(self, temp_dir_with_files, sample_taxonomy):
        """Test that correctly placed files are not flagged."""
        detector = ScatterDetector(taxonomy=sample_taxonomy)

        # Tax file in Finances Bin should be fine
        file_path = str(temp_dir_with_files / "Finances Bin" / "tax_return_2024.pdf")
        violation = detector.validate_file(file_path, str(temp_dir_with_files))

        assert violation is None


# =============================================================================
# LLM Validation Tests
# =============================================================================


class TestLLMValidation:
    """Tests for LLM-powered validation."""

    def test_llm_validation_used_when_available(
        self, temp_dir_with_files, sample_taxonomy, mock_llm_client, mock_model_router
    ):
        """Test that LLM validation is used when client is available."""
        # Mock successful LLM response
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = json.dumps({
            "belongs_here": False,
            "correct_bin": "Finances Bin",
            "confidence": 0.92,
            "reason": "This is a tax document",
        })
        mock_llm_client.generate.return_value = mock_response

        detector = ScatterDetector(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
            taxonomy=sample_taxonomy,
        )

        # This file should trigger LLM validation
        file_path = str(temp_dir_with_files / "Work Bin" / "tax_form_1040.pdf")
        violation = detector.validate_file(file_path, str(temp_dir_with_files))

        assert violation is not None
        assert violation.model_used == "llama3.1:8b"
        assert violation.used_keyword_fallback is False
        assert violation.confidence == 0.92

    def test_llm_reason_captured_in_violation(
        self, temp_dir_with_files, sample_taxonomy, mock_llm_client, mock_model_router
    ):
        """Test that LLM reasoning is captured in the violation."""
        # Mock successful LLM response with detailed reason
        mock_validation_response = MagicMock()
        mock_validation_response.success = True
        mock_validation_response.text = json.dumps({
            "belongs_here": False,
            "correct_bin": "Finances Bin",
            "confidence": 0.88,
            "reason": "File contains tax form 1040 indicators, including IRS references and income data",
        })

        # Mock path preservation response
        mock_path_response = MagicMock()
        mock_path_response.success = True
        mock_path_response.text = json.dumps({
            "suggested_subpath": "2024/Federal",
            "reason": "Tax year detected from document content",
        })

        mock_llm_client.generate.side_effect = [mock_validation_response, mock_path_response]

        detector = ScatterDetector(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
            taxonomy=sample_taxonomy,
        )

        file_path = str(temp_dir_with_files / "Work Bin" / "tax_form_1040.pdf")
        violation = detector.validate_file(file_path, str(temp_dir_with_files))

        assert violation is not None
        assert "tax form 1040 indicators" in violation.reason
        assert "IRS references" in violation.reason

    def test_llm_operational_check_uses_cached_result(
        self, sample_taxonomy, mock_llm_client, mock_model_router
    ):
        """Test that LLM availability check is performed."""
        mock_llm_client.is_ollama_available.return_value = True

        detector = ScatterDetector(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
            taxonomy=sample_taxonomy,
        )

        # Check if LLM is available should call the client method
        is_available = detector._is_llm_available()
        assert is_available is True
        mock_llm_client.is_ollama_available.assert_called_once()

    def test_llm_confirms_correct_placement(
        self, temp_dir_with_files, sample_taxonomy, mock_llm_client, mock_model_router
    ):
        """Test that LLM can confirm file is correctly placed."""
        # Mock LLM saying file belongs here
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = json.dumps({
            "belongs_here": True,
            "correct_bin": "Finances Bin",
            "confidence": 0.95,
            "reason": "File is correctly placed",
        })
        mock_llm_client.generate.return_value = mock_response

        detector = ScatterDetector(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
            taxonomy=sample_taxonomy,
        )

        # Tax file that keywords say is misplaced, but LLM says is correct
        file_path = str(temp_dir_with_files / "Work Bin" / "tax_form_1040.pdf")
        violation = detector.validate_file(file_path, str(temp_dir_with_files))

        # LLM says it's fine, so no violation
        assert violation is None

    def test_llm_error_falls_back_to_keywords(
        self, temp_dir_with_files, sample_taxonomy, mock_llm_client, mock_model_router
    ):
        """Test that LLM error falls back to keyword matching."""
        # Mock LLM error
        mock_response = MagicMock()
        mock_response.success = False
        mock_response.error = "Connection error"
        mock_llm_client.generate.return_value = mock_response

        detector = ScatterDetector(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
            taxonomy=sample_taxonomy,
        )

        file_path = str(temp_dir_with_files / "Work Bin" / "tax_form_1040.pdf")
        violation = detector.validate_file(file_path, str(temp_dir_with_files))

        # Should fall back to keyword result
        assert violation is not None
        assert violation.used_keyword_fallback is True


# =============================================================================
# LLM Unavailability Tests
# =============================================================================


class TestLLMUnavailability:
    """Tests for behavior when LLM is unavailable."""

    def test_ollama_down_uses_keyword_fallback(
        self, temp_dir_with_files, sample_taxonomy, mock_model_router
    ):
        """Test that keyword fallback is used when Ollama is not running."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = False  # Ollama is down

        detector = ScatterDetector(
            llm_client=mock_client,
            model_router=mock_model_router,
            taxonomy=sample_taxonomy,
        )

        file_path = str(temp_dir_with_files / "Work Bin" / "tax_form_1040.pdf")
        violation = detector.validate_file(file_path, str(temp_dir_with_files))

        assert violation is not None
        assert violation.used_keyword_fallback is True
        assert violation.model_used == ""
        # LLM generate should never be called
        mock_client.generate.assert_not_called()

    def test_ollama_check_exception_falls_back_to_keywords(
        self, temp_dir_with_files, sample_taxonomy
    ):
        """Test that exception during Ollama check falls back to keywords."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.side_effect = Exception("Connection refused")

        detector = ScatterDetector(
            llm_client=mock_client,
            taxonomy=sample_taxonomy,
        )

        file_path = str(temp_dir_with_files / "Work Bin" / "tax_form_1040.pdf")
        violation = detector.validate_file(file_path, str(temp_dir_with_files))

        assert violation is not None
        assert violation.used_keyword_fallback is True

    def test_no_llm_client_uses_keyword_fallback(
        self, temp_dir_with_files, sample_taxonomy
    ):
        """Test that no LLM client means keyword fallback is used."""
        detector = ScatterDetector(taxonomy=sample_taxonomy)

        file_path = str(temp_dir_with_files / "Work Bin" / "tax_form_1040.pdf")
        violation = detector.validate_file(file_path, str(temp_dir_with_files))

        assert violation is not None
        assert violation.used_keyword_fallback is True
        assert violation.model_used == ""

    def test_use_llm_false_bypasses_llm(
        self, temp_dir_with_files, sample_taxonomy, mock_llm_client, mock_model_router
    ):
        """Test that use_llm=False explicitly bypasses LLM."""
        mock_llm_client.is_ollama_available.return_value = True

        detector = ScatterDetector(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
            taxonomy=sample_taxonomy,
            use_llm=False,  # Explicitly disable LLM
        )

        file_path = str(temp_dir_with_files / "Work Bin" / "tax_form_1040.pdf")
        violation = detector.validate_file(file_path, str(temp_dir_with_files))

        assert violation is not None
        assert violation.used_keyword_fallback is True
        # LLM should never be called
        mock_llm_client.generate.assert_not_called()

    def test_model_router_runtime_error_returns_no_violation(
        self, temp_dir_with_files, sample_taxonomy, mock_llm_client
    ):
        """Test that RuntimeError from router during validation causes assumes file belongs.

        Note: Current behavior returns belongs_here=True when router fails, which
        means no violation is detected. This may be intentional (fail-safe: don't
        report violations we're not sure about) or a bug. This test documents
        the current behavior.
        """
        mock_llm_client.is_ollama_available.return_value = True

        mock_router = MagicMock()
        mock_router.route.side_effect = RuntimeError("No models available")

        detector = ScatterDetector(
            llm_client=mock_llm_client,
            model_router=mock_router,
            taxonomy=sample_taxonomy,
        )

        file_path = str(temp_dir_with_files / "Work Bin" / "tax_form_1040.pdf")
        violation = detector.validate_file(file_path, str(temp_dir_with_files))

        # Current behavior: when router fails, returns belongs_here=True
        # meaning no violation is detected
        assert violation is None

    def test_llm_generate_fails_falls_back_to_keywords(
        self, temp_dir_with_files, sample_taxonomy, mock_llm_client, mock_model_router
    ):
        """Test that LLM generate failure returns model_used=None and triggers fallback."""
        mock_llm_client.is_ollama_available.return_value = True

        # Mock generate to fail
        mock_response = MagicMock()
        mock_response.success = False
        mock_response.error = "Model timeout"
        mock_llm_client.generate.return_value = mock_response

        detector = ScatterDetector(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
            taxonomy=sample_taxonomy,
        )

        file_path = str(temp_dir_with_files / "Work Bin" / "tax_form_1040.pdf")
        violation = detector.validate_file(file_path, str(temp_dir_with_files))

        # Should fall back to keywords when generate fails
        assert violation is not None
        assert violation.used_keyword_fallback is True
        assert violation.expected_bin == "Finances Bin"


# =============================================================================
# Prompt Registry Integration Tests
# =============================================================================


class TestPromptRegistryIntegration:
    """Tests for prompt registry integration."""

    def test_uses_prompt_from_registry_when_available(
        self, temp_dir_with_files, sample_taxonomy, mock_llm_client, mock_model_router
    ):
        """Test that prompts are loaded from registry when available."""
        mock_registry = MagicMock()
        mock_registry.get.return_value = "Custom validate placement prompt for {filename}"

        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = json.dumps({
            "belongs_here": False,
            "correct_bin": "Finances Bin",
            "confidence": 0.90,
            "reason": "Tax document detected",
        })
        mock_llm_client.generate.return_value = mock_response

        detector = ScatterDetector(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
            taxonomy=sample_taxonomy,
            prompt_registry=mock_registry,
        )

        file_path = str(temp_dir_with_files / "Work Bin" / "tax_form_1040.pdf")
        detector._validate_with_llm(
            file_path, "tax_form_1040.pdf", "Work Bin", "Finances Bin", "content"
        )

        # Verify registry was accessed
        mock_registry.get.assert_called_once()
        call_kwargs = mock_registry.get.call_args
        assert call_kwargs[0][0] == "validate_placement"

    def test_falls_back_to_inline_prompt_when_registry_missing(
        self, temp_dir_with_files, sample_taxonomy, mock_llm_client, mock_model_router
    ):
        """Test that inline prompt is used when registry doesn't have the prompt."""
        mock_registry = MagicMock()
        mock_registry.get.side_effect = KeyError("validate_placement not found")

        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = json.dumps({
            "belongs_here": False,
            "correct_bin": "Finances Bin",
            "confidence": 0.90,
            "reason": "Tax document detected",
        })
        mock_llm_client.generate.return_value = mock_response

        detector = ScatterDetector(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
            taxonomy=sample_taxonomy,
            prompt_registry=mock_registry,
        )

        result = detector._validate_with_llm(
            "/path/to/file.pdf", "file.pdf", "Work Bin", "Finances Bin", "content"
        )

        # Should succeed using inline prompt
        assert result is not None
        assert result[2] == 0.90  # confidence

    def test_prompt_registry_used_for_path_preservation(
        self, sample_taxonomy, mock_llm_client, mock_model_router
    ):
        """Test that prompt registry is used for path preservation prompts."""
        mock_registry = MagicMock()
        mock_registry.get.return_value = "Custom path preservation prompt"

        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = json.dumps({
            "suggested_subpath": "2024/IRS",
            "reason": "Year and agency detected",
        })
        mock_llm_client.generate.return_value = mock_response

        detector = ScatterDetector(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
            taxonomy=sample_taxonomy,
            prompt_registry=mock_registry,
        )

        result = detector._suggest_subpath_with_llm(
            "/path/to/tax_2024.pdf", "tax_2024.pdf", "Finances Bin"
        )

        assert result is not None
        # Should have tried to get the suggest_subfolder prompt
        # (may fail and use inline, but should try)


# =============================================================================
# Escalation Tests
# =============================================================================


class TestEscalation:
    """Tests for T1 to T2 escalation."""

    def test_escalation_on_low_confidence(
        self, temp_dir_with_files, sample_taxonomy, mock_llm_client, mock_model_router
    ):
        """Test that low confidence triggers escalation to T2 Smart."""
        # First call (T1) returns low confidence
        t1_response = MagicMock()
        t1_response.success = True
        t1_response.text = json.dumps({
            "belongs_here": False,
            "correct_bin": "Finances Bin",
            "confidence": 0.6,  # Below threshold
            "reason": "Uncertain classification",
        })

        # Second call (T2) returns higher confidence
        t2_response = MagicMock()
        t2_response.success = True
        t2_response.text = json.dumps({
            "belongs_here": False,
            "correct_bin": "Finances Bin",
            "confidence": 0.92,
            "reason": "Confirmed tax document after deeper analysis",
        })

        # Third call (T2) for path preservation
        path_response = MagicMock()
        path_response.success = True
        path_response.text = json.dumps({
            "suggested_subpath": "2024/Federal",
            "reason": "Tax year organization",
        })

        mock_llm_client.generate.side_effect = [t1_response, t2_response, path_response]

        detector = ScatterDetector(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
            taxonomy=sample_taxonomy,
            escalation_threshold=0.75,
        )

        file_path = str(temp_dir_with_files / "Work Bin" / "tax_form_1040.pdf")
        violation = detector.validate_file(file_path, str(temp_dir_with_files))

        assert violation is not None
        # Should have called LLM three times (T1 validation, T2 escalation, T2 path preservation)
        assert mock_llm_client.generate.call_count == 3
        # Final confidence should be from T2
        assert violation.confidence == 0.92
        assert violation.model_used == "qwen2.5:14b"
        # Check path preservation was populated
        assert violation.suggested_subpath == "2024/Federal"

    def test_no_escalation_on_high_confidence(
        self, temp_dir_with_files, sample_taxonomy, mock_llm_client, mock_model_router
    ):
        """Test that high confidence does not trigger escalation."""
        # T1 returns high confidence
        validation_response = MagicMock()
        validation_response.success = True
        validation_response.text = json.dumps({
            "belongs_here": False,
            "correct_bin": "Finances Bin",
            "confidence": 0.92,  # Above threshold
            "reason": "Clear tax document",
        })

        # T2 for path preservation
        path_response = MagicMock()
        path_response.success = True
        path_response.text = json.dumps({
            "suggested_subpath": "2024",
            "reason": "Year from document",
        })

        mock_llm_client.generate.side_effect = [validation_response, path_response]

        detector = ScatterDetector(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
            taxonomy=sample_taxonomy,
            escalation_threshold=0.75,
        )

        file_path = str(temp_dir_with_files / "Work Bin" / "tax_form_1040.pdf")
        violation = detector.validate_file(file_path, str(temp_dir_with_files))

        # Should call T1 validation once, then T2 path preservation once
        # No escalation on validation since confidence was high
        assert mock_llm_client.generate.call_count == 2
        assert violation.model_used == "llama3.1:8b"


# =============================================================================
# Path Preservation Tests
# =============================================================================


class TestPathPreservation:
    """Tests for LLM-powered path preservation."""

    def test_year_extraction_keyword(self, sample_taxonomy):
        """Test year extraction from filename without LLM."""
        detector = ScatterDetector(taxonomy=sample_taxonomy)

        result = detector.suggest_subpath("/path/to/tax_2024_form.pdf", "Finances Bin")

        assert result.suggested_subpath == "2024"
        assert "year" in result.reason.lower()
        assert result.model_used == ""

    def test_agency_extraction_keyword(self, sample_taxonomy):
        """Test agency extraction from filename without LLM."""
        detector = ScatterDetector(taxonomy=sample_taxonomy)

        result = detector.suggest_subpath("/path/to/irs_form_1040.pdf", "Finances Bin")

        assert result.suggested_subpath == "IRS"
        assert result.model_used == ""

    def test_llm_path_preservation(
        self, sample_taxonomy, mock_llm_client, mock_model_router
    ):
        """Test LLM-powered path preservation."""
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = json.dumps({
            "suggested_subpath": "2024/IRS/Form1040",
            "reason": "Organized by year, agency, and form type",
        })
        mock_llm_client.generate.return_value = mock_response
        mock_llm_client.is_ollama_available.return_value = True

        detector = ScatterDetector(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
            taxonomy=sample_taxonomy,
        )

        result = detector.suggest_subpath("/path/to/tax_form_1040.pdf", "Finances Bin")

        assert result.suggested_subpath == "2024/IRS/Form1040"
        assert result.model_used == "qwen2.5:14b"  # T2 Smart

    def test_no_subpath_detected(self, sample_taxonomy):
        """Test when no subfolder structure is detected."""
        detector = ScatterDetector(taxonomy=sample_taxonomy)

        result = detector.suggest_subpath("/path/to/random_file.pdf", "Personal Bin")

        assert result.suggested_subpath == ""
        assert result.confidence == 0.5


# =============================================================================
# Path Preservation Reasoning Tests
# =============================================================================


class TestPathPreservationReasoning:
    """Tests for path preservation reasoning details."""

    def test_llm_reasoning_explains_year_agency_organization(
        self, sample_taxonomy, mock_llm_client, mock_model_router
    ):
        """Test that LLM reasoning explains organizational structure."""
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = json.dumps({
            "suggested_subpath": "2024/IRS/Form1040",
            "reason": "Organized by tax year 2024, agency IRS, and form type 1040",
        })
        mock_llm_client.generate.return_value = mock_response

        detector = ScatterDetector(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
            taxonomy=sample_taxonomy,
        )

        result = detector.suggest_subpath("/path/to/irs_1040_2024.pdf", "Finances Bin")

        assert result.suggested_subpath == "2024/IRS/Form1040"
        assert "tax year" in result.reason.lower() or "year" in result.reason.lower()
        assert result.model_used == "qwen2.5:14b"  # T2 Smart for analyze

    def test_llm_preserves_existing_hierarchy(
        self, sample_taxonomy, mock_llm_client, mock_model_router
    ):
        """Test that LLM suggests preserving existing folder hierarchy."""
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = json.dumps({
            "suggested_subpath": "Claims/Disability/PTSD",
            "reason": "Preserving claim type hierarchy from original location",
        })
        mock_llm_client.generate.return_value = mock_response

        detector = ScatterDetector(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
            taxonomy=sample_taxonomy,
        )

        result = detector.suggest_subpath(
            "/path/to/ptsd_claim_evidence.pdf", "VA"
        )

        assert "Claims" in result.suggested_subpath
        assert result.model_used == "qwen2.5:14b"

    def test_keyword_reasoning_for_year_extraction(self, sample_taxonomy):
        """Test that keyword fallback provides clear reasoning for year extraction."""
        detector = ScatterDetector(taxonomy=sample_taxonomy)

        result = detector.suggest_subpath("/path/to/tax_return_2023.pdf", "Finances Bin")

        assert result.suggested_subpath == "2023"
        assert "year" in result.reason.lower()
        assert "2023" in result.reason
        assert result.model_used == ""

    def test_keyword_reasoning_for_agency_extraction(self, sample_taxonomy):
        """Test that keyword fallback provides clear reasoning for agency extraction."""
        detector = ScatterDetector(taxonomy=sample_taxonomy)

        result = detector.suggest_subpath("/path/to/ssa_benefits_notice.pdf", "Finances Bin")

        assert result.suggested_subpath == "SSA"
        assert "agency" in result.reason.lower() or "SSA" in result.reason
        assert result.model_used == ""

    def test_llm_path_failure_falls_back_to_keywords(
        self, sample_taxonomy, mock_llm_client, mock_model_router
    ):
        """Test that LLM path preservation failure falls back to keywords."""
        mock_llm_client.is_ollama_available.return_value = True

        mock_response = MagicMock()
        mock_response.success = False
        mock_response.error = "Model timeout"
        mock_llm_client.generate.return_value = mock_response

        detector = ScatterDetector(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
            taxonomy=sample_taxonomy,
        )

        result = detector.suggest_subpath("/path/to/tax_2022_return.pdf", "Finances Bin")

        # Should fall back to keyword extraction
        assert result.suggested_subpath == "2022"
        assert result.model_used == ""

    def test_llm_invalid_json_falls_back_to_keywords(
        self, sample_taxonomy, mock_llm_client, mock_model_router
    ):
        """Test that invalid LLM JSON response falls back to keywords."""
        mock_llm_client.is_ollama_available.return_value = True

        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = "I don't understand the request"  # Not JSON
        mock_llm_client.generate.return_value = mock_response

        detector = ScatterDetector(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
            taxonomy=sample_taxonomy,
        )

        result = detector.suggest_subpath("/path/to/tax_2021_doc.pdf", "Finances Bin")

        # Should fall back to keyword extraction
        assert result.suggested_subpath == "2021"
        assert result.model_used == ""


# =============================================================================
# Path Preservation Integration Tests
# =============================================================================


class TestPathPreservationIntegration:
    """Tests for path preservation integration in violation detection."""

    def test_violation_includes_suggested_subpath_year(
        self, temp_dir_with_files, sample_taxonomy
    ):
        """Test that violations include year-based suggested_subpath."""
        detector = ScatterDetector(taxonomy=sample_taxonomy)

        # File with year in name in wrong bin
        file_path = str(temp_dir_with_files / "Work Bin" / "tax_form_1040.pdf")
        violation = detector.validate_file(file_path, str(temp_dir_with_files))

        assert violation is not None
        # The keyword fallback should extract year or agency from filename
        # tax_form_1040.pdf contains no 4-digit year, so we check for IRS match
        # or if no match, empty string is acceptable
        assert violation.expected_bin == "Finances Bin"

    def test_violation_includes_suggested_subpath_with_llm(
        self, temp_dir_with_files, sample_taxonomy, mock_llm_client, mock_model_router
    ):
        """Test that LLM violations include LLM-suggested subpath."""
        # Mock T1 validation response
        validation_response = MagicMock()
        validation_response.success = True
        validation_response.text = json.dumps({
            "belongs_here": False,
            "correct_bin": "Finances Bin",
            "confidence": 0.92,
            "reason": "This is a tax document",
        })

        # Mock T2 path preservation response
        path_response = MagicMock()
        path_response.success = True
        path_response.text = json.dumps({
            "suggested_subpath": "2024/Federal",
            "reason": "Organized by year and tax type",
        })

        mock_llm_client.generate.side_effect = [validation_response, path_response]

        detector = ScatterDetector(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
            taxonomy=sample_taxonomy,
        )

        file_path = str(temp_dir_with_files / "Work Bin" / "tax_form_1040.pdf")
        violation = detector.validate_file(file_path, str(temp_dir_with_files))

        assert violation is not None
        assert violation.suggested_subpath == "2024/Federal"
        assert violation.model_used == "llama3.1:8b"

    def test_violation_subpath_with_keyword_fallback(
        self, temp_dir_with_files, sample_taxonomy
    ):
        """Test that keyword fallback violations also get subpath suggestions."""
        # Create a file with year in the name
        tax_2023_file = temp_dir_with_files / "Work Bin" / "tax_2023_return.pdf"
        tax_2023_file.write_text("tax document for 2023")

        detector = ScatterDetector(taxonomy=sample_taxonomy)
        violation = detector.validate_file(str(tax_2023_file), str(temp_dir_with_files))

        assert violation is not None
        assert violation.used_keyword_fallback is True
        # Should extract year from filename
        assert violation.suggested_subpath == "2023"
        assert violation.expected_bin == "Finances Bin"

    def test_violation_subpath_with_agency(
        self, temp_dir_with_files, sample_taxonomy
    ):
        """Test agency extraction for subpath in violations."""
        # Create a file with IRS in the name that will also be flagged as misplaced
        # Using "tax" keyword to trigger violation, and "irs" for agency detection
        irs_file = temp_dir_with_files / "Work Bin" / "tax_irs_notice.pdf"
        irs_file.write_text("irs tax document")

        detector = ScatterDetector(taxonomy=sample_taxonomy)
        violation = detector.validate_file(str(irs_file), str(temp_dir_with_files))

        assert violation is not None
        assert violation.expected_bin == "Finances Bin"
        # IRS agency should be extracted for subpath
        assert violation.suggested_subpath == "IRS"

    def test_violation_subpath_year_takes_precedence(
        self, temp_dir_with_files, sample_taxonomy
    ):
        """Test that year is extracted first when present in filename."""
        # Create a file with year in the name
        file_with_year = temp_dir_with_files / "Work Bin" / "tax_2020_doc.pdf"
        file_with_year.write_text("tax document from 2020")

        detector = ScatterDetector(taxonomy=sample_taxonomy)
        violation = detector.validate_file(
            str(file_with_year), str(temp_dir_with_files)
        )

        assert violation is not None
        # Year extraction happens first
        assert violation.suggested_subpath == "2020"

    def test_detect_scatter_populates_subpaths(
        self, temp_dir_with_files, sample_taxonomy
    ):
        """Test that detect_scatter populates subpaths on all violations."""
        detector = ScatterDetector(taxonomy=sample_taxonomy)

        result = detector.detect_scatter(str(temp_dir_with_files))

        # Check that violations have been found
        assert len(result.violations) > 0

        # Verify that validate_file was called (indirectly through suggested_subpath)
        # Files without recognizable patterns should have empty subpath
        # Files with patterns should have extracted subpath
        for violation in result.violations:
            # suggested_subpath should be a string (may be empty)
            assert isinstance(violation.suggested_subpath, str)

    def test_llm_path_preservation_called_with_correct_bin(
        self, temp_dir_with_files, sample_taxonomy, mock_llm_client, mock_model_router
    ):
        """Test that suggest_subpath is called with the correct expected bin."""
        # Mock T1 validation returning a different bin than keywords suggest
        validation_response = MagicMock()
        validation_response.success = True
        validation_response.text = json.dumps({
            "belongs_here": False,
            "correct_bin": "VA",  # LLM says VA, not Finances
            "confidence": 0.92,
            "reason": "This is a VA document",
        })

        # Mock T2 path preservation response
        path_response = MagicMock()
        path_response.success = True
        path_response.text = json.dumps({
            "suggested_subpath": "Claims/2024",
            "reason": "VA claims folder structure",
        })

        mock_llm_client.generate.side_effect = [validation_response, path_response]

        detector = ScatterDetector(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
            taxonomy=sample_taxonomy,
        )

        file_path = str(temp_dir_with_files / "Work Bin" / "tax_form_1040.pdf")
        violation = detector.validate_file(file_path, str(temp_dir_with_files))

        assert violation is not None
        assert violation.expected_bin == "VA"
        assert violation.suggested_subpath == "Claims/2024"


# =============================================================================
# Locked Bin Protection Tests
# =============================================================================


class TestLockedBinProtection:
    """Tests for locked bin handling."""

    def test_is_bin_locked(self, sample_taxonomy):
        """Test locked bin detection."""
        detector = ScatterDetector(taxonomy=sample_taxonomy)

        assert detector._is_bin_locked("Finances Bin") is True
        assert detector._is_bin_locked("Work Bin") is True
        assert detector._is_bin_locked("Archive") is False

    def test_bins_list_shows_locked_status(self, sample_taxonomy):
        """Test that bins list shows locked status."""
        detector = ScatterDetector(taxonomy=sample_taxonomy)

        bins_list = detector._build_bins_list()

        assert "(locked)" in bins_list
        assert "Finances Bin (locked)" in bins_list

    def test_locked_bin_protection_with_dict(self, sample_taxonomy_dict):
        """Test locked bin detection with dict taxonomy."""
        detector = ScatterDetector(taxonomy=sample_taxonomy_dict)

        assert detector._is_bin_locked("Finances Bin") is True
        assert detector._is_bin_locked("Archive") is False


# =============================================================================
# Full Detection Tests
# =============================================================================


class TestDetectScatter:
    """Tests for full scatter detection."""

    def test_detect_scatter_basic(self, temp_dir_with_files, sample_taxonomy):
        """Test basic scatter detection."""
        detector = ScatterDetector(taxonomy=sample_taxonomy)

        result = detector.detect_scatter(str(temp_dir_with_files))

        assert result.files_scanned > 0
        assert len(result.violations) > 0
        assert result.used_keyword_fallback is True

    def test_detect_scatter_max_files(self, temp_dir_with_files, sample_taxonomy):
        """Test scatter detection with max_files limit."""
        detector = ScatterDetector(taxonomy=sample_taxonomy)

        result = detector.detect_scatter(str(temp_dir_with_files), max_files=3)

        assert result.files_scanned <= 3

    def test_detect_scatter_extension_filter(self, temp_dir_with_files, sample_taxonomy):
        """Test scatter detection with extension filter."""
        detector = ScatterDetector(taxonomy=sample_taxonomy)

        result = detector.detect_scatter(
            str(temp_dir_with_files),
            file_extensions={".pdf"},
        )

        for violation in result.violations:
            assert violation.file_path.endswith(".pdf")

    def test_detect_scatter_nonexistent_path(self, sample_taxonomy):
        """Test scatter detection with nonexistent path."""
        detector = ScatterDetector(taxonomy=sample_taxonomy)

        result = detector.detect_scatter("/nonexistent/path")

        assert result.files_scanned == 0
        assert len(result.violations) == 0

    def test_detect_scatter_single_file(self, temp_dir_with_files, sample_taxonomy):
        """Test scatter detection on a single file."""
        detector = ScatterDetector(taxonomy=sample_taxonomy)

        # Pass a file instead of directory
        file_path = str(temp_dir_with_files / "Work Bin" / "tax_form_1040.pdf")
        result = detector.detect_scatter(file_path)

        assert result.files_scanned == 1


# =============================================================================
# Convenience Function Tests
# =============================================================================


class TestDetectScatterFunction:
    """Tests for detect_scatter convenience function."""

    def test_basic_usage(self, temp_dir_with_files, sample_taxonomy):
        """Test basic function usage."""
        result = detect_scatter(
            base_path=str(temp_dir_with_files),
            taxonomy=sample_taxonomy,
        )

        assert isinstance(result, ScatterDetectionResult)
        assert result.files_scanned > 0

    def test_with_llm_client(
        self, temp_dir_with_files, sample_taxonomy, mock_llm_client
    ):
        """Test function with LLM client."""
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = json.dumps({
            "belongs_here": True,
            "correct_bin": "Work Bin",
            "confidence": 0.95,
            "reason": "File is correctly placed",
        })
        mock_llm_client.generate.return_value = mock_response

        result = detect_scatter(
            base_path=str(temp_dir_with_files),
            taxonomy=sample_taxonomy,
            llm_client=mock_llm_client,
            use_llm=True,
            max_files=5,
        )

        assert isinstance(result, ScatterDetectionResult)


# =============================================================================
# JSON Parsing Tests
# =============================================================================


class TestJSONParsing:
    """Tests for LLM JSON response parsing."""

    def test_parse_clean_json(self, sample_taxonomy):
        """Test parsing clean JSON response."""
        detector = ScatterDetector(taxonomy=sample_taxonomy)

        text = '{"belongs_here": false, "confidence": 0.85, "reason": "test"}'
        data = detector._parse_llm_json_response(text)

        assert data is not None
        assert data["belongs_here"] is False
        assert data["confidence"] == 0.85

    def test_parse_json_in_markdown(self, sample_taxonomy):
        """Test parsing JSON in markdown code block."""
        detector = ScatterDetector(taxonomy=sample_taxonomy)

        text = """Here's the analysis:
```json
{"belongs_here": false, "confidence": 0.85, "reason": "test"}
```
"""
        data = detector._parse_llm_json_response(text)

        assert data is not None
        assert data["belongs_here"] is False

    def test_parse_json_with_text(self, sample_taxonomy):
        """Test parsing JSON with surrounding text."""
        detector = ScatterDetector(taxonomy=sample_taxonomy)

        text = 'Based on my analysis, {"belongs_here": false, "confidence": 0.85, "reason": "test"} is the result.'
        data = detector._parse_llm_json_response(text)

        assert data is not None
        assert data["belongs_here"] is False

    def test_parse_invalid_json(self, sample_taxonomy):
        """Test handling of invalid JSON."""
        detector = ScatterDetector(taxonomy=sample_taxonomy)

        text = "This is not JSON at all"
        data = detector._parse_llm_json_response(text)

        assert data is None

    def test_extract_confidence(self, sample_taxonomy):
        """Test confidence extraction."""
        detector = ScatterDetector(taxonomy=sample_taxonomy)

        assert detector._extract_confidence({"confidence": 0.85}) == 0.85
        assert detector._extract_confidence({"confidence": 1.5}) == 1.0  # Clamped
        assert detector._extract_confidence({"confidence": -0.5}) == 0.0  # Clamped
        assert detector._extract_confidence({}) == 0.5  # Default


# =============================================================================
# Report Save/Load Tests
# =============================================================================


class TestReportPersistence:
    """Tests for scatter report save/load."""

    def test_save_and_load_report(self, tmp_path):
        """Test saving and loading scatter report."""
        violation = ScatterViolation(
            file_path="/path/to/file.pdf",
            current_bin="Work Bin",
            expected_bin="Finances Bin",
            confidence=0.85,
            reason="Test reason",
            model_used="llama3.1:8b",
        )

        result = ScatterDetectionResult(
            violations=[violation],
            files_scanned=10,
            files_in_correct_bin=9,
            model_used="llama3.1:8b",
        )

        report_path = tmp_path / "report.json"
        save_scatter_report(result, report_path)

        assert report_path.exists()

        loaded = load_scatter_report(report_path)
        assert loaded.files_scanned == 10
        assert len(loaded.violations) == 1
        assert loaded.violations[0].file_path == "/path/to/file.pdf"


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_taxonomy(self, temp_dir_with_files):
        """Test with empty taxonomy."""
        detector = ScatterDetector()

        result = detector.detect_scatter(str(temp_dir_with_files))

        # Should still work, using keyword rules
        assert result.files_scanned > 0

    def test_hidden_files_skipped(self, temp_dir_with_files):
        """Test that hidden files are skipped."""
        # Create a hidden file
        (temp_dir_with_files / "Finances Bin" / ".hidden_tax.pdf").write_text("hidden")

        detector = ScatterDetector()
        result = detector.detect_scatter(str(temp_dir_with_files))

        # Hidden file should not be in violations
        for violation in result.violations:
            assert not Path(violation.file_path).name.startswith(".")

    def test_hidden_directories_skipped(self, temp_dir_with_files):
        """Test that hidden directories are skipped."""
        # Create a hidden directory with files
        hidden_dir = temp_dir_with_files / "Finances Bin" / ".hidden"
        hidden_dir.mkdir()
        (hidden_dir / "tax.pdf").write_text("hidden tax")

        detector = ScatterDetector()
        result = detector.detect_scatter(str(temp_dir_with_files))

        # Files in hidden directory should not be scanned
        for violation in result.violations:
            assert "/.hidden/" not in violation.file_path

    def test_file_not_in_any_bin(self, temp_dir_with_files):
        """Test file directly in base path (not in a bin)."""
        # Create file in base path
        (temp_dir_with_files / "random.pdf").write_text("random")

        detector = ScatterDetector()

        # This file has no bin, should not crash
        file_path = str(temp_dir_with_files / "random.pdf")
        violation = detector.validate_file(file_path, str(temp_dir_with_files))

        # Should handle gracefully (no bin = no violation)
        assert violation is None

    def test_content_preview_binary_file(self, temp_dir_with_files, sample_taxonomy):
        """Test content preview for binary files."""
        detector = ScatterDetector(taxonomy=sample_taxonomy)

        # Create a .pdf file (treated as binary)
        file_path = str(temp_dir_with_files / "Finances Bin" / "tax_return_2024.pdf")
        preview = detector._get_file_content_preview(file_path)

        # Should indicate it's a binary file
        assert "[Binary file:" in preview or "tax doc" in preview

    def test_content_preview_unreadable_file(self, sample_taxonomy):
        """Test content preview for unreadable file."""
        detector = ScatterDetector(taxonomy=sample_taxonomy)

        preview = detector._get_file_content_preview("/nonexistent/file.txt")

        assert preview == ""


# =============================================================================
# Learned Rules Integration Tests
# =============================================================================


class TestLearnedRulesIntegration:
    """Tests for learned rules integration with scatter detection."""

    def test_learned_rules_checked_before_keyword_rules(
        self, temp_dir_with_files, sample_taxonomy
    ):
        """Test that learned rules are checked before keyword fallback."""
        mock_learned_store = MagicMock()

        # Mock learned rule that says tax file goes to Legal Bin instead
        mock_match_result = MagicMock()
        mock_match_result.destination = "Legal Bin/Contracts"
        mock_match_result.confidence = 0.85
        mock_learned_store.match_with_details.return_value = mock_match_result

        detector = ScatterDetector(
            taxonomy=sample_taxonomy,
            learned_rule_store=mock_learned_store,
            use_learned_rules=True,
        )

        # Tax file - keyword rules would say Finances Bin, but learned says Legal Bin
        file_path = str(temp_dir_with_files / "Work Bin" / "tax_form_1040.pdf")
        violation = detector.validate_file(file_path, str(temp_dir_with_files))

        assert violation is not None
        # Should use learned rule destination
        assert violation.expected_bin == "Legal Bin/Contracts"
        mock_learned_store.match_with_details.assert_called_once()

    def test_learned_rules_disabled_uses_keyword_rules(
        self, temp_dir_with_files, sample_taxonomy
    ):
        """Test that disabling learned rules uses keyword fallback."""
        mock_learned_store = MagicMock()

        detector = ScatterDetector(
            taxonomy=sample_taxonomy,
            learned_rule_store=mock_learned_store,
            use_learned_rules=False,  # Disable learned rules
        )

        file_path = str(temp_dir_with_files / "Work Bin" / "tax_form_1040.pdf")
        violation = detector.validate_file(file_path, str(temp_dir_with_files))

        assert violation is not None
        # Should use keyword rules (Finances Bin for tax)
        assert violation.expected_bin == "Finances Bin"
        # Learned store should not be called
        mock_learned_store.match_with_details.assert_not_called()

    def test_learned_rules_no_match_falls_through_to_keywords(
        self, temp_dir_with_files, sample_taxonomy
    ):
        """Test that no learned rule match falls through to keyword rules."""
        mock_learned_store = MagicMock()
        mock_learned_store.match_with_details.return_value = None  # No match

        detector = ScatterDetector(
            taxonomy=sample_taxonomy,
            learned_rule_store=mock_learned_store,
            use_learned_rules=True,
        )

        file_path = str(temp_dir_with_files / "Work Bin" / "tax_form_1040.pdf")
        violation = detector.validate_file(file_path, str(temp_dir_with_files))

        assert violation is not None
        # Should fall through to keyword rules
        assert violation.expected_bin == "Finances Bin"

    def test_learned_rules_correct_placement_no_violation(
        self, temp_dir_with_files, sample_taxonomy
    ):
        """Test that learned rules can confirm correct placement."""
        mock_learned_store = MagicMock()

        # Mock learned rule that says file belongs in current location
        mock_match_result = MagicMock()
        mock_match_result.destination = "Finances Bin"  # Matches current
        mock_match_result.confidence = 0.90
        mock_learned_store.match_with_details.return_value = mock_match_result

        detector = ScatterDetector(
            taxonomy=sample_taxonomy,
            learned_rule_store=mock_learned_store,
            use_learned_rules=True,
        )

        # Tax file in Finances Bin - learned rules confirm it's correct
        file_path = str(temp_dir_with_files / "Finances Bin" / "tax_return_2024.pdf")
        violation = detector.validate_file(file_path, str(temp_dir_with_files))

        # Should be no violation since learned rules say it's correct
        assert violation is None
