"""Tests for refile_agent module.

Tests LLM-powered drift detection with T1 Fast assessment, T2 Smart escalation,
keyword fallback (path-type heuristics), hash matching, and routing history
integration.
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from organizer.refile_agent import (
    DEFAULT_LOOKBACK_DAYS,
    DestinationSuggestion,
    DriftDetectionResult,
    DriftRecord,
    ReFileAgent,
    detect_drift,
    load_drift_report,
    save_drift_report,
)
from organizer.routing_history import RoutingHistory


# =============================================================================
# Test Fixtures
# =============================================================================


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
        (base / "Finances Bin" / "Taxes").mkdir(parents=True)
        (base / "Work Bin" / "Resumes").mkdir(parents=True)
        (base / "VA" / "Claims").mkdir(parents=True)
        (base / "Desktop").mkdir()
        (base / "Downloads").mkdir()
        (base / "In-Box").mkdir()

        # Create files in various locations
        (base / "Finances Bin" / "Taxes" / "tax_2024.pdf").write_text("tax doc 2024")
        (base / "Work Bin" / "Resumes" / "resume.pdf").write_text("my resume")
        (base / "VA" / "Claims" / "va_claim.pdf").write_text("va claim")

        # Drifted files
        (base / "Desktop" / "tax_2024.pdf").write_text("tax doc 2024")  # Accidental
        (base / "Finances Bin" / "Banking" / "statement.pdf").mkdir(parents=True)
        (base / "Finances Bin" / "Banking" / "statement.pdf").rmdir()
        (base / "Finances Bin" / "Banking").rmdir()
        (base / "Finances Bin" / "statement.pdf").write_text("bank statement")

        yield base


@pytest.fixture
def routing_history_with_records(tmp_path):
    """Create a routing history with test records."""
    history_path = tmp_path / ".organizer" / "agent" / "routing_history.json"
    history_path.parent.mkdir(parents=True, exist_ok=True)

    now = datetime.now()
    records = [
        {
            "filename": "tax_2024.pdf",
            "source_path": "/inbox/tax_2024.pdf",
            "destination_bin": "/tmp/test/Finances Bin/Taxes",
            "confidence": 0.95,
            "matched_keywords": ["tax"],
            "routed_at": (now - timedelta(days=5)).isoformat(),
            "status": "executed",
        },
        {
            "filename": "resume.pdf",
            "source_path": "/inbox/resume.pdf",
            "destination_bin": "/tmp/test/Work Bin/Resumes",
            "confidence": 0.92,
            "matched_keywords": ["resume"],
            "routed_at": (now - timedelta(days=10)).isoformat(),
            "status": "executed",
        },
        {
            "filename": "old_file.pdf",
            "source_path": "/inbox/old_file.pdf",
            "destination_bin": "/tmp/test/Archive",
            "confidence": 0.85,
            "matched_keywords": [],
            "routed_at": (now - timedelta(days=100)).isoformat(),  # Outside lookback
            "status": "executed",
        },
        {
            "filename": "pending.pdf",
            "source_path": "/inbox/pending.pdf",
            "destination_bin": "/tmp/test/Work Bin",
            "confidence": 0.80,
            "matched_keywords": [],
            "routed_at": now.isoformat(),
            "status": "pending",  # Not executed
        },
    ]

    data = {
        "records": records,
        "updated_at": now.isoformat(),
    }

    history_path.write_text(json.dumps(data))
    return RoutingHistory(history_path)


# =============================================================================
# DriftRecord Tests
# =============================================================================


class TestDriftRecord:
    """Tests for DriftRecord dataclass."""

    def test_creation_basic(self):
        """Test basic creation of DriftRecord."""
        record = DriftRecord(
            file_path="/path/to/file.pdf",
            original_filed_path="/original/path/file.pdf",
            current_path="/path/to/file.pdf",
        )

        assert record.file_path == "/path/to/file.pdf"
        assert record.original_filed_path == "/original/path/file.pdf"
        assert record.current_path == "/path/to/file.pdf"
        assert record.drift_assessment == ""
        assert record.detected_at != ""  # Auto-set

    def test_creation_with_assessment(self):
        """Test creation with full assessment."""
        record = DriftRecord(
            file_path="/Desktop/file.pdf",
            original_filed_path="/Finances Bin/Taxes/file.pdf",
            current_path="/Desktop/file.pdf",
            filed_by="agent",
            filed_at="2024-01-15T10:30:00",
            sha256_hash="abc123",
            drift_assessment="likely_accidental",
            reason="File moved to common accidental location",
            model_used="llama3.1:8b",
            confidence=0.85,
        )

        assert record.drift_assessment == "likely_accidental"
        assert record.confidence == 0.85
        assert record.model_used == "llama3.1:8b"

    def test_is_likely_accidental(self):
        """Test is_likely_accidental property."""
        record = DriftRecord(
            file_path="/path",
            original_filed_path="/original",
            current_path="/path",
            drift_assessment="likely_accidental",
        )

        assert record.is_likely_accidental is True
        assert record.is_likely_intentional is False

    def test_is_likely_intentional(self):
        """Test is_likely_intentional property."""
        record = DriftRecord(
            file_path="/path",
            original_filed_path="/original",
            current_path="/path",
            drift_assessment="likely_intentional",
        )

        assert record.is_likely_intentional is True
        assert record.is_likely_accidental is False

    def test_priority_high_for_accidental(self):
        """Test priority is 'high' for likely_accidental drift."""
        record = DriftRecord(
            file_path="/Desktop/file.pdf",
            original_filed_path="/Finances Bin/file.pdf",
            current_path="/Desktop/file.pdf",
            drift_assessment="likely_accidental",
        )

        assert record.priority == "high"

    def test_priority_low_for_intentional(self):
        """Test priority is 'low' for likely_intentional drift."""
        record = DriftRecord(
            file_path="/VA/Claims/file.pdf",
            original_filed_path="/Finances Bin/file.pdf",
            current_path="/VA/Claims/file.pdf",
            drift_assessment="likely_intentional",
        )

        assert record.priority == "low"

    def test_priority_normal_for_unknown(self):
        """Test priority is 'normal' for unknown assessment."""
        record = DriftRecord(
            file_path="/path",
            original_filed_path="/original",
            current_path="/path",
            drift_assessment="",  # Unknown/empty
        )

        assert record.priority == "normal"

    def test_to_dict(self):
        """Test conversion to dictionary."""
        record = DriftRecord(
            file_path="/Desktop/file.pdf",
            original_filed_path="/Finances Bin/file.pdf",
            current_path="/Desktop/file.pdf",
            drift_assessment="likely_accidental",
            confidence=0.85,
        )

        d = record.to_dict()
        assert d["file_path"] == "/Desktop/file.pdf"
        assert d["drift_assessment"] == "likely_accidental"
        assert d["confidence"] == 0.85

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "file_path": "/Desktop/file.pdf",
            "original_filed_path": "/Finances Bin/file.pdf",
            "current_path": "/Desktop/file.pdf",
            "drift_assessment": "likely_accidental",
            "confidence": 0.85,
            "model_used": "llama3.1:8b",
        }

        record = DriftRecord.from_dict(data)
        assert record.file_path == "/Desktop/file.pdf"
        assert record.drift_assessment == "likely_accidental"
        assert record.confidence == 0.85

    def test_roundtrip(self):
        """Test dict roundtrip preserves data."""
        original = DriftRecord(
            file_path="/path/file.pdf",
            original_filed_path="/original/file.pdf",
            current_path="/path/file.pdf",
            filed_by="agent",
            filed_at="2024-01-15T10:30:00",
            sha256_hash="abc123def456",
            drift_assessment="likely_accidental",
            reason="Desktop location",
            model_used="llama3.1:8b",
            confidence=0.9,
            suggested_destination="/Finances Bin/Taxes",
            original_routing_record={"key": "value"},
        )

        restored = DriftRecord.from_dict(original.to_dict())
        assert restored.file_path == original.file_path
        assert restored.drift_assessment == original.drift_assessment
        assert restored.confidence == original.confidence
        assert restored.original_routing_record == original.original_routing_record


# =============================================================================
# DriftDetectionResult Tests
# =============================================================================


class TestDriftDetectionResult:
    """Tests for DriftDetectionResult dataclass."""

    def test_creation(self):
        """Test basic creation."""
        result = DriftDetectionResult()
        assert result.drift_records == []
        assert result.files_checked == 0
        assert result.files_still_in_place == 0
        assert result.files_missing == 0

    def test_with_records(self):
        """Test creation with drift records."""
        record = DriftRecord(
            file_path="/Desktop/file.pdf",
            original_filed_path="/Finances Bin/file.pdf",
            current_path="/Desktop/file.pdf",
            drift_assessment="likely_accidental",
        )

        result = DriftDetectionResult(
            drift_records=[record],
            files_checked=10,
            files_still_in_place=8,
            files_missing=1,
            model_used="llama3.1:8b",
        )

        assert len(result.drift_records) == 1
        assert result.files_checked == 10
        assert result.files_still_in_place == 8
        assert result.files_missing == 1

    def test_get_accidental_drifts(self):
        """Test filtering for accidental drifts."""
        accidental = DriftRecord(
            file_path="/Desktop/file1.pdf",
            original_filed_path="/Finances Bin/file1.pdf",
            current_path="/Desktop/file1.pdf",
            drift_assessment="likely_accidental",
        )
        intentional = DriftRecord(
            file_path="/Work Bin/Projects/file2.pdf",
            original_filed_path="/Work Bin/file2.pdf",
            current_path="/Work Bin/Projects/file2.pdf",
            drift_assessment="likely_intentional",
        )

        result = DriftDetectionResult(drift_records=[accidental, intentional])

        accidentals = result.get_accidental_drifts()
        assert len(accidentals) == 1
        assert accidentals[0].file_path == "/Desktop/file1.pdf"

    def test_get_intentional_drifts(self):
        """Test filtering for intentional drifts."""
        accidental = DriftRecord(
            file_path="/Desktop/file1.pdf",
            original_filed_path="/Finances Bin/file1.pdf",
            current_path="/Desktop/file1.pdf",
            drift_assessment="likely_accidental",
        )
        intentional = DriftRecord(
            file_path="/Work Bin/Projects/file2.pdf",
            original_filed_path="/Work Bin/file2.pdf",
            current_path="/Work Bin/Projects/file2.pdf",
            drift_assessment="likely_intentional",
        )

        result = DriftDetectionResult(drift_records=[accidental, intentional])

        intentionals = result.get_intentional_drifts()
        assert len(intentionals) == 1
        assert intentionals[0].file_path == "/Work Bin/Projects/file2.pdf"

    def test_to_dict(self):
        """Test conversion to dictionary."""
        record = DriftRecord(
            file_path="/Desktop/file.pdf",
            original_filed_path="/Finances Bin/file.pdf",
            current_path="/Desktop/file.pdf",
            drift_assessment="likely_accidental",
        )

        result = DriftDetectionResult(
            drift_records=[record],
            files_checked=10,
            model_used="llama3.1:8b",
        )

        d = result.to_dict()
        assert len(d["drift_records"]) == 1
        assert d["files_checked"] == 10
        assert d["model_used"] == "llama3.1:8b"


# =============================================================================
# DestinationSuggestion Tests
# =============================================================================


class TestDestinationSuggestion:
    """Tests for DestinationSuggestion dataclass."""

    def test_creation(self):
        """Test basic creation."""
        suggestion = DestinationSuggestion(
            suggested_path="Finances Bin/Taxes/2024",
            confidence=0.9,
            reason="Tax document detected",
            model_used="qwen2.5:14b",
        )

        assert suggestion.suggested_path == "Finances Bin/Taxes/2024"
        assert suggestion.confidence == 0.9
        assert suggestion.model_used == "qwen2.5:14b"


# =============================================================================
# ReFileAgent Initialization Tests
# =============================================================================


class TestReFileAgentInit:
    """Tests for ReFileAgent initialization."""

    def test_init_basic(self):
        """Test basic initialization."""
        agent = ReFileAgent()
        assert agent._llm_client is None
        assert agent._model_router is None
        assert agent._use_llm is False
        assert agent._lookback_days == DEFAULT_LOOKBACK_DAYS

    def test_init_with_llm_client(self, mock_llm_client):
        """Test initialization with LLM client."""
        agent = ReFileAgent(llm_client=mock_llm_client)
        assert agent._llm_client is mock_llm_client
        assert agent._model_router is not None  # Auto-created
        assert agent._use_llm is True

    def test_init_with_custom_router(self, mock_llm_client, mock_model_router):
        """Test initialization with custom model router."""
        agent = ReFileAgent(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
        )
        assert agent._model_router is mock_model_router

    def test_init_use_llm_false(self, mock_llm_client):
        """Test initialization with use_llm=False."""
        agent = ReFileAgent(llm_client=mock_llm_client, use_llm=False)
        assert agent._use_llm is False

    def test_init_custom_threshold(self, mock_llm_client):
        """Test initialization with custom escalation threshold."""
        agent = ReFileAgent(
            llm_client=mock_llm_client,
            escalation_threshold=0.8,
        )
        assert agent._escalation_threshold == 0.8

    def test_init_custom_lookback(self):
        """Test initialization with custom lookback days."""
        agent = ReFileAgent(lookback_days=30)
        assert agent._lookback_days == 30


# =============================================================================
# Path Heuristics Tests
# =============================================================================


class TestPathHeuristics:
    """Tests for path-based heuristics."""

    def test_is_in_inbox(self):
        """Test inbox detection."""
        agent = ReFileAgent()

        assert agent._is_in_inbox("/path/to/In-Box/file.pdf") is True
        assert agent._is_in_inbox("/path/to/Inbox/file.pdf") is True
        assert agent._is_in_inbox("/path/to/inbox/file.pdf") is True
        assert agent._is_in_inbox("/path/to/in-box/file.pdf") is True
        assert agent._is_in_inbox("/path/to/Desktop/file.pdf") is False

    def test_is_taxonomy_path(self):
        """Test taxonomy path detection."""
        agent = ReFileAgent()

        assert agent._is_taxonomy_path("/path/VA/Claims/file.pdf") is True
        assert agent._is_taxonomy_path("/path/Finances Bin/Taxes/file.pdf") is True
        assert agent._is_taxonomy_path("/path/Work Bin/Projects/file.pdf") is True
        assert agent._is_taxonomy_path("/path/Desktop/file.pdf") is False

    def test_is_accidental_location(self):
        """Test accidental location detection."""
        agent = ReFileAgent()

        assert agent._is_accidental_location("/Users/test/Desktop/file.pdf") is True
        assert agent._is_accidental_location("/Users/test/Downloads/file.pdf") is True
        assert agent._is_accidental_location("/path/.Trash/file.pdf") is True
        assert agent._is_accidental_location("/path/tmp/file.pdf") is True
        assert agent._is_accidental_location("/path/Finances Bin/file.pdf") is False


# =============================================================================
# Keyword Fallback Tests
# =============================================================================


class TestKeywordFallback:
    """Tests for keyword-based drift assessment fallback."""

    def test_keyword_fallback_desktop(self):
        """Test keyword fallback for Desktop location."""
        agent = ReFileAgent()

        assessment, reason, confidence = agent._assess_drift_with_keywords(
            "tax_2024.pdf",
            "/Finances Bin/Taxes/tax_2024.pdf",
            "/Users/test/Desktop/tax_2024.pdf",
        )

        assert assessment == "likely_accidental"
        assert "Desktop" in reason or "accidental" in reason.lower()
        assert confidence >= 0.7

    def test_keyword_fallback_downloads(self):
        """Test keyword fallback for Downloads location."""
        agent = ReFileAgent()

        assessment, reason, confidence = agent._assess_drift_with_keywords(
            "resume.pdf",
            "/Work Bin/Resumes/resume.pdf",
            "/Users/test/Downloads/resume.pdf",
        )

        assert assessment == "likely_accidental"
        assert confidence >= 0.7

    def test_keyword_fallback_taxonomy(self):
        """Test keyword fallback for taxonomy location."""
        agent = ReFileAgent()

        assessment, reason, confidence = agent._assess_drift_with_keywords(
            "tax_2024.pdf",
            "/Finances Bin/Taxes/tax_2024.pdf",
            "/Finances Bin/Taxes/2024/tax_2024.pdf",
        )

        assert assessment == "likely_intentional"
        assert "taxonomy" in reason.lower() or "organized" in reason.lower()

    def test_keyword_fallback_root_level(self):
        """Test keyword fallback for near-root location."""
        agent = ReFileAgent()

        assessment, reason, confidence = agent._assess_drift_with_keywords(
            "file.pdf",
            "/Finances Bin/file.pdf",
            "/Users/file.pdf",
        )

        assert assessment == "likely_accidental"
        assert "root" in reason.lower() or "accidental" in reason.lower()


# =============================================================================
# LLM Assessment Tests
# =============================================================================


class TestLLMAssessment:
    """Tests for LLM-powered drift assessment."""

    def test_llm_assessment_accidental(
        self, mock_llm_client, mock_model_router
    ):
        """Test LLM assessment returns accidental."""
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = json.dumps({
            "likely_intentional": False,
            "confidence": 0.88,
            "reason": "File moved to Desktop suggests accidental drag-drop",
        })
        mock_llm_client.generate.return_value = mock_response

        agent = ReFileAgent(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
        )

        assessment, reason, confidence, model_used = agent._assess_drift_with_llm(
            "tax_2024.pdf",
            "/Finances Bin/Taxes/tax_2024.pdf",
            "/Desktop/tax_2024.pdf",
            "2024-01-15T10:00:00",
        )

        assert assessment == "likely_accidental"
        assert confidence == 0.88
        assert model_used == "llama3.1:8b"

    def test_llm_assessment_intentional(
        self, mock_llm_client, mock_model_router
    ):
        """Test LLM assessment returns intentional."""
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = json.dumps({
            "likely_intentional": True,
            "confidence": 0.92,
            "reason": "User reorganized into subfolder",
        })
        mock_llm_client.generate.return_value = mock_response

        agent = ReFileAgent(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
        )

        assessment, reason, confidence, model_used = agent._assess_drift_with_llm(
            "tax_2024.pdf",
            "/Finances Bin/Taxes/tax_2024.pdf",
            "/Finances Bin/Taxes/2024/Federal/tax_2024.pdf",
            "2024-01-15T10:00:00",
        )

        assert assessment == "likely_intentional"
        assert confidence == 0.92

    def test_llm_assessment_failure_returns_empty(
        self, mock_llm_client, mock_model_router
    ):
        """Test that LLM failure returns empty model_used."""
        mock_response = MagicMock()
        mock_response.success = False
        mock_response.error = "Connection error"
        mock_llm_client.generate.return_value = mock_response

        agent = ReFileAgent(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
        )

        assessment, reason, confidence, model_used = agent._assess_drift_with_llm(
            "tax_2024.pdf",
            "/Finances Bin/tax_2024.pdf",
            "/Desktop/tax_2024.pdf",
            "2024-01-15T10:00:00",
        )

        assert model_used == ""
        assert assessment == ""


# =============================================================================
# Escalation Tests
# =============================================================================


class TestEscalation:
    """Tests for T1 to T2 escalation."""

    def test_escalation_on_low_confidence(
        self, mock_llm_client, mock_model_router
    ):
        """Test that low confidence triggers escalation to T2 Smart."""
        # T1 returns low confidence
        t1_response = MagicMock()
        t1_response.success = True
        t1_response.text = json.dumps({
            "likely_intentional": True,
            "confidence": 0.6,  # Below threshold
            "reason": "Uncertain",
        })

        # T2 returns higher confidence
        t2_response = MagicMock()
        t2_response.success = True
        t2_response.text = json.dumps({
            "likely_intentional": False,
            "confidence": 0.92,
            "reason": "Confirmed accidental after deeper analysis",
        })

        mock_llm_client.generate.side_effect = [t1_response, t2_response]

        agent = ReFileAgent(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
            escalation_threshold=0.75,
        )

        assessment, reason, confidence, model_used = agent._assess_drift_with_llm(
            "file.pdf",
            "/original/path/file.pdf",
            "/Desktop/file.pdf",
            "2024-01-15T10:00:00",
        )

        # Should have called LLM twice (T1 then T2)
        assert mock_llm_client.generate.call_count == 2
        # Final confidence should be from T2
        assert confidence == 0.92
        assert model_used == "qwen2.5:14b"
        assert assessment == "likely_accidental"

    def test_no_escalation_on_high_confidence(
        self, mock_llm_client, mock_model_router
    ):
        """Test that high confidence does not trigger escalation."""
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = json.dumps({
            "likely_intentional": True,
            "confidence": 0.92,  # Above threshold
            "reason": "Clear intentional move",
        })
        mock_llm_client.generate.return_value = mock_response

        agent = ReFileAgent(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
            escalation_threshold=0.75,
        )

        assessment, reason, confidence, model_used = agent._assess_drift_with_llm(
            "file.pdf",
            "/original/path/file.pdf",
            "/Work Bin/Projects/file.pdf",
            "2024-01-15T10:00:00",
        )

        # Should call T1 only
        assert mock_llm_client.generate.call_count == 1
        assert model_used == "llama3.1:8b"


# =============================================================================
# Destination Suggestion Tests
# =============================================================================


class TestDestinationSuggestionLogic:
    """Tests for destination suggestion logic."""

    def test_suggest_destination_llm(
        self, mock_llm_client, mock_model_router
    ):
        """Test LLM-powered destination suggestion."""
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = json.dumps({
            "suggested_path": "Finances Bin/Taxes/2024",
            "confidence": 0.9,
            "reason": "Tax document from 2024",
        })
        mock_llm_client.generate.return_value = mock_response

        agent = ReFileAgent(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
        )

        suggestion = agent.suggest_destination(
            "/current/path/tax_2024.pdf",
            "/old/path/tax_2024.pdf",
        )

        assert suggestion.suggested_path == "Finances Bin/Taxes/2024"
        assert suggestion.confidence == 0.9
        assert suggestion.model_used == "qwen2.5:14b"

    def test_suggest_destination_keyword_tax(self):
        """Test keyword-based suggestion for tax file."""
        agent = ReFileAgent()

        suggestion = agent._suggest_destination_with_keywords(
            "tax_2024.pdf",
            "/old/path/tax_2024.pdf",
        )

        assert "Finances" in suggestion.suggested_path or "Taxes" in suggestion.suggested_path
        assert "2024" in suggestion.suggested_path

    def test_suggest_destination_keyword_resume(self):
        """Test keyword-based suggestion for resume file."""
        agent = ReFileAgent()

        suggestion = agent._suggest_destination_with_keywords(
            "resume_2024.pdf",
            "/old/path/resume_2024.pdf",
        )

        assert "Employment" in suggestion.suggested_path or "Resume" in suggestion.suggested_path

    def test_suggest_destination_keyword_va(self):
        """Test keyword-based suggestion for VA file."""
        agent = ReFileAgent()

        suggestion = agent._suggest_destination_with_keywords(
            "va_claim.pdf",
            "/old/path/va_claim.pdf",
        )

        assert "VA" in suggestion.suggested_path

    def test_suggest_destination_keyword_unknown(self):
        """Test keyword-based suggestion for unknown file type."""
        agent = ReFileAgent()

        suggestion = agent._suggest_destination_with_keywords(
            "random_file.pdf",
            "/old/path/random_file.pdf",
        )

        assert "Archive" in suggestion.suggested_path
        assert suggestion.confidence < 0.5


# =============================================================================
# Single File Assessment Tests
# =============================================================================


class TestAssessSingleFile:
    """Tests for single file assessment."""

    def test_assess_single_file_keyword(self, temp_dir_with_files):
        """Test single file assessment with keyword fallback."""
        agent = ReFileAgent()

        file_path = str(temp_dir_with_files / "Desktop" / "tax_2024.pdf")
        record = agent.assess_single_file(
            file_path=file_path,
            original_path="/Finances Bin/Taxes/tax_2024.pdf",
            filed_at="2024-01-15T10:00:00",
        )

        assert record.file_path == file_path
        assert record.drift_assessment == "likely_accidental"
        assert record.model_used == ""

    def test_assess_single_file_with_llm(
        self, temp_dir_with_files, mock_llm_client, mock_model_router
    ):
        """Test single file assessment with LLM."""
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = json.dumps({
            "likely_intentional": False,
            "confidence": 0.88,
            "reason": "Desktop location indicates accidental",
        })
        mock_llm_client.generate.return_value = mock_response

        agent = ReFileAgent(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
        )

        file_path = str(temp_dir_with_files / "Desktop" / "tax_2024.pdf")
        record = agent.assess_single_file(
            file_path=file_path,
            original_path="/Finances Bin/Taxes/tax_2024.pdf",
            filed_at="2024-01-15T10:00:00",
        )

        assert record.drift_assessment == "likely_accidental"
        assert record.confidence == 0.88
        assert record.model_used == "llama3.1:8b"


# =============================================================================
# JSON Parsing Tests
# =============================================================================


class TestJSONParsing:
    """Tests for LLM JSON response parsing."""

    def test_parse_clean_json(self):
        """Test parsing clean JSON response."""
        agent = ReFileAgent()

        text = '{"likely_intentional": false, "confidence": 0.85, "reason": "test"}'
        data = agent._parse_llm_json_response(text)

        assert data is not None
        assert data["likely_intentional"] is False
        assert data["confidence"] == 0.85

    def test_parse_json_in_markdown(self):
        """Test parsing JSON in markdown code block."""
        agent = ReFileAgent()

        text = """Here's the analysis:
```json
{"likely_intentional": false, "confidence": 0.85, "reason": "test"}
```
"""
        data = agent._parse_llm_json_response(text)

        assert data is not None
        assert data["likely_intentional"] is False

    def test_parse_json_with_text(self):
        """Test parsing JSON with surrounding text."""
        agent = ReFileAgent()

        text = 'Based on my analysis, {"likely_intentional": false, "confidence": 0.85, "reason": "test"} is the result.'
        data = agent._parse_llm_json_response(text)

        assert data is not None
        assert data["likely_intentional"] is False

    def test_parse_invalid_json(self):
        """Test handling of invalid JSON."""
        agent = ReFileAgent()

        text = "This is not JSON at all"
        data = agent._parse_llm_json_response(text)

        assert data is None


# =============================================================================
# Report Save/Load Tests
# =============================================================================


class TestReportPersistence:
    """Tests for drift report save/load."""

    def test_save_and_load_report(self, tmp_path):
        """Test saving and loading drift report."""
        record = DriftRecord(
            file_path="/Desktop/file.pdf",
            original_filed_path="/Finances Bin/file.pdf",
            current_path="/Desktop/file.pdf",
            drift_assessment="likely_accidental",
            confidence=0.85,
            model_used="llama3.1:8b",
        )

        result = DriftDetectionResult(
            drift_records=[record],
            files_checked=10,
            files_still_in_place=8,
            files_missing=1,
            model_used="llama3.1:8b",
        )

        report_path = tmp_path / "drift_report.json"
        save_drift_report(result, report_path)

        assert report_path.exists()

        loaded = load_drift_report(report_path)
        assert loaded.files_checked == 10
        assert loaded.files_still_in_place == 8
        assert loaded.files_missing == 1
        assert len(loaded.drift_records) == 1
        assert loaded.drift_records[0].file_path == "/Desktop/file.pdf"
        assert loaded.drift_records[0].drift_assessment == "likely_accidental"

    def test_save_creates_parent_dirs(self, tmp_path):
        """Test that save creates parent directories."""
        record = DriftRecord(
            file_path="/path/file.pdf",
            original_filed_path="/original/file.pdf",
            current_path="/path/file.pdf",
            drift_assessment="likely_intentional",
        )

        result = DriftDetectionResult(drift_records=[record])

        report_path = tmp_path / "nested" / "dir" / "report.json"
        save_drift_report(result, report_path)

        assert report_path.exists()


# =============================================================================
# Convenience Function Tests
# =============================================================================


class TestDetectDriftFunction:
    """Tests for detect_drift convenience function."""

    def test_basic_usage(self, routing_history_with_records, temp_dir_with_files):
        """Test basic function usage."""
        result = detect_drift(
            routing_history=routing_history_with_records,
            search_root=str(temp_dir_with_files),
        )

        assert isinstance(result, DriftDetectionResult)
        assert result.files_checked >= 0

    def test_with_llm_client(
        self, routing_history_with_records, temp_dir_with_files, mock_llm_client
    ):
        """Test function with LLM client."""
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = json.dumps({
            "likely_intentional": True,
            "confidence": 0.95,
            "reason": "File correctly placed",
        })
        mock_llm_client.generate.return_value = mock_response

        result = detect_drift(
            routing_history=routing_history_with_records,
            search_root=str(temp_dir_with_files),
            llm_client=mock_llm_client,
            use_llm=True,
        )

        assert isinstance(result, DriftDetectionResult)


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_routing_history(self, tmp_path):
        """Test with empty routing history."""
        history_path = tmp_path / ".organizer" / "agent" / "routing_history.json"
        history_path.parent.mkdir(parents=True, exist_ok=True)
        history_path.write_text('{"records": []}')

        history = RoutingHistory(history_path)
        agent = ReFileAgent()

        result = agent.detect_drift(history, search_root=str(tmp_path))

        assert result.files_checked == 0
        assert len(result.drift_records) == 0

    def test_file_moved_to_inbox_skipped(self, temp_dir_with_files):
        """Test that files moved to In-Box are skipped."""
        agent = ReFileAgent()

        # In-Box files are handled by Filing-Agent
        assert agent._is_in_inbox("/path/In-Box/file.pdf") is True

    def test_invalid_routed_at_timestamp(self, tmp_path):
        """Test handling of invalid routed_at timestamp."""
        history_path = tmp_path / ".organizer" / "agent" / "routing_history.json"
        history_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "records": [
                {
                    "filename": "file.pdf",
                    "source_path": "/inbox/file.pdf",
                    "destination_bin": "/Finances Bin",
                    "confidence": 0.9,
                    "matched_keywords": [],
                    "routed_at": "invalid-timestamp",
                    "status": "executed",
                },
            ],
        }
        history_path.write_text(json.dumps(data))

        history = RoutingHistory(history_path)
        agent = ReFileAgent()

        result = agent.detect_drift(history, search_root=str(tmp_path))

        # Should handle gracefully and skip the record
        assert result.files_checked == 0

    def test_records_outside_lookback_skipped(self, tmp_path):
        """Test that records outside lookback period are skipped."""
        history_path = tmp_path / ".organizer" / "agent" / "routing_history.json"
        history_path.parent.mkdir(parents=True, exist_ok=True)

        old_date = datetime.now() - timedelta(days=100)
        data = {
            "records": [
                {
                    "filename": "old_file.pdf",
                    "source_path": "/inbox/old_file.pdf",
                    "destination_bin": str(tmp_path / "Archive"),
                    "confidence": 0.9,
                    "matched_keywords": [],
                    "routed_at": old_date.isoformat(),
                    "status": "executed",
                },
            ],
        }
        history_path.write_text(json.dumps(data))

        history = RoutingHistory(history_path)
        agent = ReFileAgent(lookback_days=30)

        result = agent.detect_drift(history, search_root=str(tmp_path))

        # Record is outside 30-day lookback, should be skipped
        assert result.files_checked == 0

    def test_non_executed_records_skipped(self, tmp_path):
        """Test that non-executed routing records are skipped."""
        history_path = tmp_path / ".organizer" / "agent" / "routing_history.json"
        history_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "records": [
                {
                    "filename": "pending.pdf",
                    "source_path": "/inbox/pending.pdf",
                    "destination_bin": str(tmp_path / "Work Bin"),
                    "confidence": 0.8,
                    "matched_keywords": [],
                    "routed_at": datetime.now().isoformat(),
                    "status": "pending",
                },
                {
                    "filename": "corrected.pdf",
                    "source_path": "/inbox/corrected.pdf",
                    "destination_bin": str(tmp_path / "Archive"),
                    "confidence": 0.7,
                    "matched_keywords": [],
                    "routed_at": datetime.now().isoformat(),
                    "status": "corrected",
                },
            ],
        }
        history_path.write_text(json.dumps(data))

        history = RoutingHistory(history_path)
        agent = ReFileAgent()

        result = agent.detect_drift(history, search_root=str(tmp_path))

        # Both records are not executed, should be skipped
        assert result.files_checked == 0

    def test_confidence_clamped(self, mock_llm_client, mock_model_router):
        """Test that confidence values are clamped to 0.0-1.0."""
        # Response with confidence > 1.0
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = json.dumps({
            "likely_intentional": True,
            "confidence": 1.5,  # Should be clamped to 1.0
            "reason": "Test",
        })
        mock_llm_client.generate.return_value = mock_response

        agent = ReFileAgent(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
        )

        assessment, reason, confidence, model_used = agent._assess_drift_with_llm(
            "file.pdf",
            "/original/file.pdf",
            "/current/file.pdf",
            "2024-01-15T10:00:00",
        )

        assert confidence == 1.0

    def test_llm_unavailable_falls_back_to_keywords(
        self, temp_dir_with_files, mock_llm_client, mock_model_router
    ):
        """Test that LLM unavailability falls back to keywords."""
        mock_llm_client.is_ollama_available.return_value = False

        agent = ReFileAgent(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
        )

        file_path = str(temp_dir_with_files / "Desktop" / "tax_2024.pdf")
        record = agent.assess_single_file(
            file_path=file_path,
            original_path="/Finances Bin/tax_2024.pdf",
            filed_at="2024-01-15T10:00:00",
        )

        # Should fall back to keyword assessment
        assert record.model_used == ""
        assert record.drift_assessment == "likely_accidental"

    def test_search_file_by_name_nonexistent_root(self):
        """Test searching with nonexistent search root."""
        agent = ReFileAgent()

        result = agent._search_file_by_name_and_hash(
            "file.pdf",
            expected_hash=None,
            search_root="/nonexistent/path",
        )

        assert result is None


# =============================================================================
# Hash Matching Tests
# =============================================================================


class TestHashMatching:
    """Tests for hash matching in drift detection."""

    def test_search_file_by_hash_finds_matching_file(self, tmp_path):
        """Test that search finds file with matching hash."""
        from organizer.file_dna import compute_file_hash

        # Create a test file
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        test_file = subdir / "test_document.pdf"
        test_file.write_text("unique content for hash test")

        # Compute the hash
        expected_hash = compute_file_hash(test_file)

        agent = ReFileAgent()

        # Search by name and hash
        result = agent._search_file_by_name_and_hash(
            "test_document.pdf",
            expected_hash=expected_hash,
            search_root=str(tmp_path),
        )

        assert result is not None
        assert result == str(test_file)

    def test_search_file_by_hash_rejects_wrong_hash(self, tmp_path):
        """Test that search rejects files with wrong hash."""
        # Create a test file
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        test_file = subdir / "test_document.pdf"
        test_file.write_text("some content")

        # Search with wrong hash
        wrong_hash = "0" * 64  # All zeros, definitely wrong

        agent = ReFileAgent()

        result = agent._search_file_by_name_and_hash(
            "test_document.pdf",
            expected_hash=wrong_hash,
            search_root=str(tmp_path),
        )

        # Should not find the file because hash doesn't match
        assert result is None

    def test_search_file_no_hash_returns_first_match(self, tmp_path):
        """Test that search without hash returns first matching file."""
        # Create a test file
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        test_file = subdir / "test_document.pdf"
        test_file.write_text("some content")

        agent = ReFileAgent()

        result = agent._search_file_by_name_and_hash(
            "test_document.pdf",
            expected_hash=None,
            search_root=str(tmp_path),
        )

        assert result is not None
        assert result == str(test_file)

    def test_drift_detection_uses_hash_for_verification(self, tmp_path):
        """Test that drift detection computes hash for found files."""
        from organizer.file_dna import compute_file_hash

        # Set up routing history
        history_path = tmp_path / ".organizer" / "agent" / "routing_history.json"
        history_path.parent.mkdir(parents=True, exist_ok=True)

        # Create the expected directory structure
        finances_bin = tmp_path / "Finances Bin" / "Taxes"
        finances_bin.mkdir(parents=True)

        # Create file at "drifted" location (Desktop)
        desktop = tmp_path / "Desktop"
        desktop.mkdir()
        drifted_file = desktop / "tax_2024.pdf"
        drifted_file.write_text("tax document content")

        # The expected hash of the drifted file
        expected_hash = compute_file_hash(drifted_file)

        # Create routing history pointing to original location
        from datetime import datetime

        now = datetime.now()
        records_data = {
            "records": [
                {
                    "filename": "tax_2024.pdf",
                    "source_path": "/inbox/tax_2024.pdf",
                    "destination_bin": str(finances_bin),
                    "confidence": 0.95,
                    "matched_keywords": ["tax"],
                    "routed_at": now.isoformat(),
                    "status": "executed",
                },
            ],
            "updated_at": now.isoformat(),
        }
        history_path.write_text(json.dumps(records_data))

        history = RoutingHistory(history_path)
        agent = ReFileAgent()

        # Run drift detection
        result = agent.detect_drift(
            routing_history=history,
            search_root=str(tmp_path),
        )

        # Should detect the drift and include hash
        assert result.files_checked == 1
        if result.drift_records:
            drift = result.drift_records[0]
            # The hash should be computed for the found file
            assert drift.sha256_hash == expected_hash


# =============================================================================
# Routing History Update on Refile Tests
# =============================================================================


class TestRoutingHistoryUpdateOnRefile:
    """Tests for routing history updates when refiling drifted files."""

    def test_mark_as_refiled_called_on_approval(self, tmp_path):
        """Test that mark_as_refiled is called when refile is approved."""
        # Set up routing history with a record
        history_path = tmp_path / ".organizer" / "agent" / "routing_history.json"
        history_path.parent.mkdir(parents=True, exist_ok=True)

        from datetime import datetime

        now = datetime.now()
        records_data = {
            "records": [
                {
                    "filename": "tax_2024.pdf",
                    "source_path": "/inbox/tax_2024.pdf",
                    "destination_bin": "/Finances Bin/Taxes",
                    "confidence": 0.95,
                    "matched_keywords": ["tax"],
                    "routed_at": now.isoformat(),
                    "status": "executed",
                },
            ],
            "updated_at": now.isoformat(),
        }
        history_path.write_text(json.dumps(records_data))

        history = RoutingHistory(history_path)

        # Verify initial status is executed
        record = history.find_by_filename("tax_2024.pdf")
        assert record is not None
        assert record.status == "executed"

        # Mark as refiled (simulating approval)
        result = history.mark_as_refiled("tax_2024.pdf")
        assert result is True

        # Verify status changed
        record = history.find_by_filename("tax_2024.pdf")
        assert record.status == "refiled"

    def test_record_refile_creates_new_entry(self, tmp_path):
        """Test that record_refile creates a new routing entry."""
        # Set up routing history with an original record
        history_path = tmp_path / ".organizer" / "agent" / "routing_history.json"
        history_path.parent.mkdir(parents=True, exist_ok=True)

        from datetime import datetime

        now = datetime.now()
        records_data = {
            "records": [
                {
                    "filename": "tax_2024.pdf",
                    "source_path": "/inbox/tax_2024.pdf",
                    "destination_bin": "/Finances Bin/Taxes",
                    "confidence": 0.95,
                    "matched_keywords": ["tax"],
                    "routed_at": now.isoformat(),
                    "status": "executed",
                },
            ],
            "updated_at": now.isoformat(),
        }
        history_path.write_text(json.dumps(records_data))

        history = RoutingHistory(history_path)

        # Count initial records
        initial_count = len(history.get_all_records())
        assert initial_count == 1

        # Record a refile (file moved from Desktop back to correct location)
        new_record = history.record_refile(
            filename="tax_2024.pdf",
            source_path="/Desktop/tax_2024.pdf",  # Where it drifted to
            destination_bin="/Finances Bin/Taxes/2024",  # New destination
            confidence=0.88,
            matched_keywords=["tax", "2024"],
        )

        # Verify new record was created
        assert new_record is not None
        assert new_record.status == "executed"
        assert new_record.destination_bin == "/Finances Bin/Taxes/2024"

        # Verify we now have 2 records
        all_records = history.get_all_records()
        assert len(all_records) == 2

        # Verify original is marked as refiled
        refiled_records = history.find_refiled()
        assert len(refiled_records) == 1
        assert refiled_records[0].filename == "tax_2024.pdf"

    def test_refile_preserves_original_routing_info(self, tmp_path):
        """Test that refile preserves reference to original routing."""
        history_path = tmp_path / ".organizer" / "agent" / "routing_history.json"
        history_path.parent.mkdir(parents=True, exist_ok=True)

        from datetime import datetime

        now = datetime.now()
        original_destination = "/Finances Bin/Taxes"
        records_data = {
            "records": [
                {
                    "filename": "invoice_2024.pdf",
                    "source_path": "/inbox/invoice_2024.pdf",
                    "destination_bin": original_destination,
                    "confidence": 0.90,
                    "matched_keywords": ["invoice"],
                    "routed_at": now.isoformat(),
                    "status": "executed",
                },
            ],
            "updated_at": now.isoformat(),
        }
        history_path.write_text(json.dumps(records_data))

        history = RoutingHistory(history_path)

        # Get original record for reference
        original = history.find_by_filename("invoice_2024.pdf")
        assert original is not None

        # Record refile
        history.record_refile(
            filename="invoice_2024.pdf",
            source_path="/Downloads/invoice_2024.pdf",
            destination_bin="/Finances Bin/Invoices/2024",
            confidence=0.92,
            matched_keywords=["invoice", "2024"],
            original_record=original,
        )

        # Verify original is marked as refiled (status preserved)
        all_records = history.get_all_records()
        refiled = [r for r in all_records if r.status == "refiled"]
        assert len(refiled) == 1
        assert refiled[0].destination_bin == original_destination

    def test_drift_record_includes_original_routing_info(self, tmp_path):
        """Test that DriftRecord can store original routing record reference."""
        original_routing = {
            "filename": "report.pdf",
            "source_path": "/inbox/report.pdf",
            "destination_bin": "/Work Bin/Reports",
            "confidence": 0.95,
            "matched_keywords": ["report"],
            "routed_at": "2024-01-15T10:00:00",
            "status": "executed",
        }

        drift = DriftRecord(
            file_path="/Desktop/report.pdf",
            original_filed_path="/Work Bin/Reports/report.pdf",
            current_path="/Desktop/report.pdf",
            drift_assessment="likely_accidental",
            confidence=0.85,
            original_routing_record=original_routing,
        )

        # Verify original routing info is stored
        assert drift.original_routing_record == original_routing
        assert drift.original_routing_record["destination_bin"] == "/Work Bin/Reports"

        # Verify roundtrip preserves the data
        restored = DriftRecord.from_dict(drift.to_dict())
        assert restored.original_routing_record == original_routing


# =============================================================================
# LLM Drift Assessment Path Tests (Phase 16.6)
# =============================================================================


class TestLLMDriftAssessmentPath:
    """Tests for LLM-powered drift assessment with T1 Fast."""

    def test_llm_assessment_uses_t1_fast_for_low_complexity(
        self, mock_llm_client, mock_model_router
    ):
        """Test that drift assessment uses T1 Fast model for initial assessment."""
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = json.dumps({
            "likely_intentional": False,
            "confidence": 0.88,
            "reason": "File moved to Desktop suggests accidental drag-drop",
        })
        mock_llm_client.generate.return_value = mock_response

        agent = ReFileAgent(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
        )

        assessment, reason, confidence, model_used = agent._assess_drift_with_llm(
            "tax_2024.pdf",
            "/Finances Bin/Taxes/tax_2024.pdf",
            "/Desktop/tax_2024.pdf",
            "2024-01-15T10:00:00",
        )

        # Verify T1 Fast (8b) was used
        assert model_used == "llama3.1:8b"
        # Verify router was called with low complexity profile
        call_args = mock_model_router.route.call_args
        assert call_args[0][0].complexity == "low"

    def test_llm_reason_captured_in_assessment(
        self, mock_llm_client, mock_model_router
    ):
        """Test that LLM reasoning is captured in the assessment."""
        expected_reason = "Desktop location indicates accidental drag-and-drop behavior"
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = json.dumps({
            "likely_intentional": False,
            "confidence": 0.92,
            "reason": expected_reason,
        })
        mock_llm_client.generate.return_value = mock_response

        agent = ReFileAgent(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
        )

        assessment, reason, confidence, model_used = agent._assess_drift_with_llm(
            "file.pdf",
            "/original/path/file.pdf",
            "/Desktop/file.pdf",
            "2024-01-15T10:00:00",
        )

        assert reason == expected_reason

    def test_llm_model_used_field_populated_in_drift_record(
        self, temp_dir_with_files, mock_llm_client, mock_model_router
    ):
        """Test that model_used field is populated in DriftRecord."""
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = json.dumps({
            "likely_intentional": False,
            "confidence": 0.88,
            "reason": "Desktop location",
        })
        mock_llm_client.generate.return_value = mock_response

        agent = ReFileAgent(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
        )

        file_path = str(temp_dir_with_files / "Desktop" / "tax_2024.pdf")
        record = agent.assess_single_file(
            file_path=file_path,
            original_path="/Finances Bin/Taxes/tax_2024.pdf",
            filed_at="2024-01-15T10:00:00",
        )

        assert record.model_used == "llama3.1:8b"
        assert record.drift_assessment == "likely_accidental"


# =============================================================================
# LLM Unavailability / Graceful Degradation Tests (Phase 16.6)
# =============================================================================


class TestLLMUnavailabilityDrift:
    """Tests for graceful degradation when LLM is unavailable."""

    def test_ollama_down_uses_keyword_fallback(
        self, temp_dir_with_files, mock_llm_client, mock_model_router
    ):
        """Test that Ollama being down triggers keyword fallback."""
        mock_llm_client.is_ollama_available.return_value = False

        agent = ReFileAgent(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
        )

        file_path = str(temp_dir_with_files / "Desktop" / "tax_2024.pdf")
        record = agent.assess_single_file(
            file_path=file_path,
            original_path="/Finances Bin/tax_2024.pdf",
            filed_at="2024-01-15T10:00:00",
        )

        # Should use keyword fallback (no model_used)
        assert record.model_used == ""
        # Should still correctly assess Desktop as accidental
        assert record.drift_assessment == "likely_accidental"

    def test_ollama_check_exception_falls_back_to_keywords(
        self, temp_dir_with_files, mock_llm_client, mock_model_router
    ):
        """Test that exception during Ollama check triggers keyword fallback."""
        mock_llm_client.is_ollama_available.side_effect = Exception("Connection error")

        agent = ReFileAgent(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
        )

        file_path = str(temp_dir_with_files / "Desktop" / "tax_2024.pdf")
        record = agent.assess_single_file(
            file_path=file_path,
            original_path="/Finances Bin/tax_2024.pdf",
            filed_at="2024-01-15T10:00:00",
        )

        assert record.model_used == ""
        assert record.drift_assessment == "likely_accidental"

    def test_no_llm_client_uses_keyword_fallback(self, temp_dir_with_files):
        """Test that absence of LLM client uses keyword fallback."""
        agent = ReFileAgent()

        file_path = str(temp_dir_with_files / "Desktop" / "tax_2024.pdf")
        record = agent.assess_single_file(
            file_path=file_path,
            original_path="/Finances Bin/tax_2024.pdf",
            filed_at="2024-01-15T10:00:00",
        )

        assert record.model_used == ""
        assert record.drift_assessment == "likely_accidental"

    def test_use_llm_false_bypasses_llm(
        self, temp_dir_with_files, mock_llm_client, mock_model_router
    ):
        """Test that use_llm=False bypasses LLM even when available."""
        agent = ReFileAgent(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
            use_llm=False,
        )

        file_path = str(temp_dir_with_files / "Desktop" / "tax_2024.pdf")
        record = agent.assess_single_file(
            file_path=file_path,
            original_path="/Finances Bin/tax_2024.pdf",
            filed_at="2024-01-15T10:00:00",
        )

        # LLM should not be called
        mock_llm_client.generate.assert_not_called()
        assert record.model_used == ""

    def test_model_router_runtime_error_falls_back_to_keywords(
        self, mock_llm_client, mock_model_router
    ):
        """Test that router failure triggers keyword fallback."""
        mock_model_router.route.side_effect = RuntimeError("No model available")

        agent = ReFileAgent(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
        )

        assessment, reason, confidence, model_used = agent._assess_drift_with_llm(
            "tax_2024.pdf",
            "/Finances Bin/tax_2024.pdf",
            "/Desktop/tax_2024.pdf",
            "2024-01-15T10:00:00",
        )

        # Should return empty model_used, indicating failure
        assert model_used == ""
        assert assessment == ""

    def test_llm_generate_fails_falls_back_to_keywords(
        self, temp_dir_with_files, mock_llm_client, mock_model_router
    ):
        """Test that LLM generate failure falls back to keywords."""
        mock_response = MagicMock()
        mock_response.success = False
        mock_response.error = "Connection timeout"
        mock_llm_client.generate.return_value = mock_response

        agent = ReFileAgent(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
        )

        file_path = str(temp_dir_with_files / "Desktop" / "tax_2024.pdf")
        record = agent.assess_single_file(
            file_path=file_path,
            original_path="/Finances Bin/tax_2024.pdf",
            filed_at="2024-01-15T10:00:00",
        )

        # Should fall back to keywords
        assert record.model_used == ""
        assert record.drift_assessment == "likely_accidental"


# =============================================================================
# Prompt Registry Integration Tests (Phase 16.6)
# =============================================================================


class TestPromptRegistryIntegrationDrift:
    """Tests for prompt registry integration in drift assessment."""

    def test_uses_prompt_from_registry_when_available(
        self, mock_llm_client, mock_model_router, tmp_path
    ):
        """Test that assess_drift prompt is loaded from registry when available."""
        from organizer.prompt_registry import PromptRegistry

        # Create a custom prompts directory with assess_drift prompt
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        custom_prompt = """# Prompt: assess_drift
# Version: 2.0.0
# Last-Modified: 2024-01-15
# Description: Custom drift assessment

Custom prompt for '{filename}' at '{current_path}'.
Was this intentional?"""
        (prompts_dir / "assess_drift.txt").write_text(custom_prompt)

        mock_registry = PromptRegistry(prompts_dir=prompts_dir)

        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = json.dumps({
            "likely_intentional": True,
            "confidence": 0.9,
            "reason": "Custom test",
        })
        mock_llm_client.generate.return_value = mock_response

        agent = ReFileAgent(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
            prompt_registry=mock_registry,
        )

        agent._assess_drift_with_llm(
            "test.pdf",
            "/original/test.pdf",
            "/current/test.pdf",
            "2024-01-15T10:00:00",
        )

        # Check that the LLM was called with custom prompt content
        call_args = mock_llm_client.generate.call_args
        prompt_used = call_args[0][0]
        assert "Custom prompt" in prompt_used

    def test_falls_back_to_inline_prompt_when_registry_missing(
        self, mock_llm_client, mock_model_router, tmp_path
    ):
        """Test fallback to inline prompt when registry prompt not found."""
        from organizer.prompt_registry import PromptRegistry

        # Create empty prompts directory (no assess_drift)
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "other_prompt.txt").write_text("# Some other prompt")

        mock_registry = PromptRegistry(prompts_dir=prompts_dir)

        # Mock the get method to raise KeyError for assess_drift
        original_get = mock_registry.get

        def mock_get(name, **kwargs):
            if name == "assess_drift":
                raise KeyError("Missing variable")
            return original_get(name, **kwargs)

        mock_registry.get = mock_get

        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = json.dumps({
            "likely_intentional": True,
            "confidence": 0.85,
            "reason": "Test",
        })
        mock_llm_client.generate.return_value = mock_response

        agent = ReFileAgent(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
            prompt_registry=mock_registry,
        )

        # Should not raise, should fall back to inline prompt
        assessment, reason, confidence, model_used = agent._assess_drift_with_llm(
            "test.pdf",
            "/original/test.pdf",
            "/current/test.pdf",
            "2024-01-15T10:00:00",
        )

        assert model_used != ""  # LLM was called successfully

    def test_prompt_registry_used_for_destination_suggestion(
        self, mock_llm_client, mock_model_router, tmp_path
    ):
        """Test that prompt registry is used for destination suggestion prompts."""
        from organizer.prompt_registry import PromptRegistry

        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()

        # Create suggest_refile_destination prompt
        custom_prompt = """# Prompt: suggest_refile_destination
# Version: 1.0.0
# Last-Modified: 2024-01-15
# Description: Suggest destination for drifted file

Where should '{filename}' go now that '{original_path}' is gone?
Content: {content}"""
        (prompts_dir / "suggest_refile_destination.txt").write_text(custom_prompt)

        mock_registry = PromptRegistry(prompts_dir=prompts_dir)

        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = json.dumps({
            "suggested_path": "Finances Bin/Taxes/2024",
            "confidence": 0.9,
            "reason": "Tax document",
        })
        mock_llm_client.generate.return_value = mock_response

        agent = ReFileAgent(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
            prompt_registry=mock_registry,
        )

        agent._suggest_destination_with_llm(
            "tax_2024.pdf",
            "/old/path/tax_2024.pdf",
            "tax document content preview",
        )

        # Verify the custom prompt was used
        call_args = mock_llm_client.generate.call_args
        prompt_used = call_args[0][0]
        assert "Where should" in prompt_used


# =============================================================================
# Destination Suggestion When Original Path Gone Tests (Phase 16.6)
# =============================================================================


class TestDestinationSuggestionOriginalPathGone:
    """Tests for LLM-powered destination suggestion when original path is gone."""

    def test_llm_suggests_destination_when_original_path_gone(
        self, mock_llm_client, mock_model_router
    ):
        """Test that LLM suggests new destination when original path doesn't exist."""
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = json.dumps({
            "suggested_path": "Finances Bin/Taxes/Federal/2024",
            "confidence": 0.92,
            "reason": "Tax document from 2024, categorized under Federal taxes",
        })
        mock_llm_client.generate.return_value = mock_response

        agent = ReFileAgent(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
        )

        suggestion = agent._suggest_destination_with_llm(
            "tax_2024.pdf",
            "/nonexistent/old/path/tax_2024.pdf",
            "IRS Form 1040 for tax year 2024",
        )

        assert suggestion is not None
        assert suggestion.suggested_path == "Finances Bin/Taxes/Federal/2024"
        assert suggestion.confidence == 0.92
        assert "tax" in suggestion.reason.lower() or "Tax" in suggestion.reason

    def test_llm_uses_t2_smart_for_destination_suggestion(
        self, mock_llm_client, mock_model_router
    ):
        """Test that T2 Smart is used for destination suggestion (complex task)."""
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = json.dumps({
            "suggested_path": "VA/Claims/2024",
            "confidence": 0.88,
            "reason": "VA claim document",
        })
        mock_llm_client.generate.return_value = mock_response

        agent = ReFileAgent(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
        )

        suggestion = agent._suggest_destination_with_llm(
            "va_claim.pdf",
            "/old/path/va_claim.pdf",
            "VA claim content",
        )

        # Verify T2 Smart (14b) was used for complex analysis
        call_args = mock_model_router.route.call_args
        assert call_args[0][0].complexity == "medium"
        assert suggestion.model_used == "qwen2.5:14b"

    def test_llm_destination_suggestion_failure_returns_none(
        self, mock_llm_client, mock_model_router
    ):
        """Test that LLM failure returns None for destination suggestion."""
        mock_response = MagicMock()
        mock_response.success = False
        mock_response.error = "Model unavailable"
        mock_llm_client.generate.return_value = mock_response

        agent = ReFileAgent(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
        )

        suggestion = agent._suggest_destination_with_llm(
            "file.pdf",
            "/old/path/file.pdf",
            "content preview",
        )

        assert suggestion is None

    def test_suggest_destination_falls_back_to_keywords_when_llm_unavailable(
        self, mock_llm_client, mock_model_router
    ):
        """Test that suggest_destination uses keywords when LLM is unavailable."""
        mock_llm_client.is_ollama_available.return_value = False

        agent = ReFileAgent(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
        )

        suggestion = agent.suggest_destination(
            "/current/tax_2024.pdf",
            "/old/nonexistent/tax_2024.pdf",
        )

        # Should use keyword fallback
        assert suggestion.model_used == ""
        assert "Finances" in suggestion.suggested_path or "Taxes" in suggestion.suggested_path

    def test_llm_invalid_json_returns_none(self, mock_llm_client, mock_model_router):
        """Test that invalid JSON from LLM returns None for suggestion."""
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = "This is not valid JSON response"
        mock_llm_client.generate.return_value = mock_response

        agent = ReFileAgent(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
        )

        suggestion = agent._suggest_destination_with_llm(
            "file.pdf",
            "/old/path/file.pdf",
            "content",
        )

        assert suggestion is None

    def test_llm_empty_suggested_path_returns_none(
        self, mock_llm_client, mock_model_router
    ):
        """Test that empty suggested_path from LLM returns None."""
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = json.dumps({
            "suggested_path": "",  # Empty path
            "confidence": 0.5,
            "reason": "Unable to determine",
        })
        mock_llm_client.generate.return_value = mock_response

        agent = ReFileAgent(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
        )

        suggestion = agent._suggest_destination_with_llm(
            "file.pdf",
            "/old/path/file.pdf",
            "content",
        )

        assert suggestion is None


# =============================================================================
# Learned Rules Integration Tests (Phase 16.6)
# =============================================================================


class TestLearnedRulesIntegrationDrift:
    """Tests for learned rules integration as source of truth for correct placement."""

    def test_learned_rules_used_for_destination_suggestion(self, tmp_path):
        """Test that learned rules are checked for destination suggestion."""
        from organizer.learned_rules import LearnedRuleStore, StoredRule

        # Create a learned rules store with a tax rule
        rules_path = tmp_path / "learned_routing_rules.json"
        store = LearnedRuleStore(
            rules_path=rules_path,
            taxonomy_path=None,
            auto_load=False,
        )
        store.add_rule(StoredRule(
            pattern="tax",
            destination="Finances Bin/Taxes/Learned",
            confidence=0.9,
            pattern_type="keyword",
            reasoning="Tax documents go to Finances Bin",
        ))

        agent = ReFileAgent(
            learned_rule_store=store,
            use_learned_rules=True,
        )

        suggestion = agent._suggest_destination_with_keywords(
            "tax_2024.pdf",
            "/nonexistent/old/path/tax_2024.pdf",
        )

        # Should use learned rule destination
        assert "Learned" in suggestion.suggested_path
        assert suggestion.confidence == 0.9

    def test_learned_rules_disabled_uses_hardcoded_keywords(self, tmp_path):
        """Test that disabling learned rules falls back to hardcoded keywords."""
        from organizer.learned_rules import LearnedRuleStore, StoredRule

        rules_path = tmp_path / "learned_routing_rules.json"
        store = LearnedRuleStore(
            rules_path=rules_path,
            taxonomy_path=None,
            auto_load=False,
        )
        store.add_rule(StoredRule(
            pattern="tax",
            destination="CustomBin/Taxes",
            confidence=0.9,
            pattern_type="keyword",
        ))

        agent = ReFileAgent(
            learned_rule_store=store,
            use_learned_rules=False,  # Disabled
        )

        suggestion = agent._suggest_destination_with_keywords(
            "tax_2024.pdf",
            "/old/path/tax_2024.pdf",
        )

        # Should use hardcoded keyword rules, not learned rules
        assert "CustomBin" not in suggestion.suggested_path
        assert "Finances" in suggestion.suggested_path or "Taxes" in suggestion.suggested_path

    def test_learned_rules_no_match_falls_through_to_hardcoded(self, tmp_path):
        """Test that no learned rule match falls through to hardcoded keywords."""
        from organizer.learned_rules import LearnedRuleStore, StoredRule

        rules_path = tmp_path / "learned_routing_rules.json"
        store = LearnedRuleStore(
            rules_path=rules_path,
            taxonomy_path=None,
            auto_load=False,
        )
        # Add a rule that won't match
        store.add_rule(StoredRule(
            pattern="specific_pattern_xyz",
            destination="CustomBin/Specific",
            confidence=0.9,
            pattern_type="keyword",
        ))

        agent = ReFileAgent(
            learned_rule_store=store,
            use_learned_rules=True,
        )

        suggestion = agent._suggest_destination_with_keywords(
            "tax_2024.pdf",  # Won't match "specific_pattern_xyz"
            "/old/path/tax_2024.pdf",
        )

        # Should fall through to hardcoded keywords
        assert "Finances" in suggestion.suggested_path or "Taxes" in suggestion.suggested_path
        assert "CustomBin" not in suggestion.suggested_path

    def test_learned_rules_year_subpath_preserved(self, tmp_path):
        """Test that year is preserved in suggested subpath from learned rules."""
        from organizer.learned_rules import LearnedRuleStore, StoredRule

        rules_path = tmp_path / "learned_routing_rules.json"
        store = LearnedRuleStore(
            rules_path=rules_path,
            taxonomy_path=None,
            auto_load=False,
        )
        store.add_rule(StoredRule(
            pattern="invoice",
            destination="Finances Bin/Invoices",
            confidence=0.85,
            pattern_type="keyword",
            reasoning="Invoices go to Finances Bin/Invoices",
        ))

        agent = ReFileAgent(
            learned_rule_store=store,
            use_learned_rules=True,
        )

        suggestion = agent._suggest_destination_with_keywords(
            "invoice_2024_march.pdf",
            "/old/path/invoice_2024_march.pdf",
        )

        # Year should be appended to the suggestion
        assert "2024" in suggestion.suggested_path
        assert "Invoices" in suggestion.suggested_path


# =============================================================================
# T2 Smart Escalation Tests (Phase 16.6)
# =============================================================================


class TestT2SmartEscalationDrift:
    """Tests for T1 to T2 escalation in drift assessment."""

    def test_escalation_triggers_on_low_confidence(
        self, mock_llm_client, mock_model_router
    ):
        """Test that low T1 confidence triggers T2 escalation."""
        # T1 returns low confidence
        t1_response = MagicMock()
        t1_response.success = True
        t1_response.text = json.dumps({
            "likely_intentional": True,
            "confidence": 0.5,  # Below default threshold of 0.75
            "reason": "Uncertain about this move",
        })

        # T2 returns higher confidence with different assessment
        t2_response = MagicMock()
        t2_response.success = True
        t2_response.text = json.dumps({
            "likely_intentional": False,
            "confidence": 0.95,
            "reason": "After deeper analysis, this appears accidental",
        })

        mock_llm_client.generate.side_effect = [t1_response, t2_response]

        agent = ReFileAgent(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
            escalation_threshold=0.75,
        )

        assessment, reason, confidence, model_used = agent._assess_drift_with_llm(
            "file.pdf",
            "/original/file.pdf",
            "/Desktop/file.pdf",
            "2024-01-15T10:00:00",
        )

        # Should have called both T1 and T2
        assert mock_llm_client.generate.call_count == 2
        # Final result should be from T2
        assert confidence == 0.95
        assert model_used == "qwen2.5:14b"
        assert assessment == "likely_accidental"

    def test_escalation_uses_same_prompt(
        self, mock_llm_client, mock_model_router
    ):
        """Test that escalation uses the same prompt for T2."""
        t1_response = MagicMock()
        t1_response.success = True
        t1_response.text = json.dumps({
            "likely_intentional": True,
            "confidence": 0.6,
            "reason": "Not sure",
        })

        t2_response = MagicMock()
        t2_response.success = True
        t2_response.text = json.dumps({
            "likely_intentional": True,
            "confidence": 0.9,
            "reason": "Confirmed intentional",
        })

        mock_llm_client.generate.side_effect = [t1_response, t2_response]

        agent = ReFileAgent(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
            escalation_threshold=0.75,
        )

        agent._assess_drift_with_llm(
            "test.pdf",
            "/original/test.pdf",
            "/new/test.pdf",
            "2024-01-15T10:00:00",
        )

        # Both calls should have the same prompt
        calls = mock_llm_client.generate.call_args_list
        assert len(calls) == 2
        prompt_1 = calls[0][0][0]
        prompt_2 = calls[1][0][0]
        assert prompt_1 == prompt_2

    def test_escalation_does_not_trigger_when_above_threshold(
        self, mock_llm_client, mock_model_router
    ):
        """Test that high confidence does not trigger escalation."""
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = json.dumps({
            "likely_intentional": True,
            "confidence": 0.92,  # Above threshold
            "reason": "Clear intentional move",
        })
        mock_llm_client.generate.return_value = mock_response

        agent = ReFileAgent(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
            escalation_threshold=0.75,
        )

        assessment, reason, confidence, model_used = agent._assess_drift_with_llm(
            "file.pdf",
            "/original/file.pdf",
            "/Work Bin/file.pdf",
            "2024-01-15T10:00:00",
        )

        # Should only call T1
        assert mock_llm_client.generate.call_count == 1
        assert model_used == "llama3.1:8b"

    def test_custom_escalation_threshold(
        self, mock_llm_client, mock_model_router
    ):
        """Test that custom escalation threshold is respected."""
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = json.dumps({
            "likely_intentional": True,
            "confidence": 0.85,  # Above custom threshold of 0.8
            "reason": "Clear move",
        })
        mock_llm_client.generate.return_value = mock_response

        agent = ReFileAgent(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
            escalation_threshold=0.8,  # Custom threshold
        )

        agent._assess_drift_with_llm(
            "file.pdf",
            "/original/file.pdf",
            "/Work Bin/file.pdf",
            "2024-01-15T10:00:00",
        )

        # 0.85 > 0.8, should not escalate
        assert mock_llm_client.generate.call_count == 1

    def test_escalation_t2_failure_uses_t1_result(
        self, mock_llm_client, mock_model_router
    ):
        """Test that T2 failure falls back to T1 result."""
        t1_response = MagicMock()
        t1_response.success = True
        t1_response.text = json.dumps({
            "likely_intentional": True,
            "confidence": 0.6,  # Will trigger escalation
            "reason": "T1 assessment",
        })

        t2_response = MagicMock()
        t2_response.success = False  # T2 fails
        t2_response.error = "Model overloaded"

        mock_llm_client.generate.side_effect = [t1_response, t2_response]

        agent = ReFileAgent(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
            escalation_threshold=0.75,
        )

        assessment, reason, confidence, model_used = agent._assess_drift_with_llm(
            "file.pdf",
            "/original/file.pdf",
            "/Desktop/file.pdf",
            "2024-01-15T10:00:00",
        )

        # Should use T1 result when T2 fails
        assert confidence == 0.6
        assert model_used == "llama3.1:8b"  # T1 model
        assert reason == "T1 assessment"


# =============================================================================
# Additional JSON Parsing Edge Cases (Phase 16.6)
# =============================================================================


class TestJSONParsingDriftEdgeCases:
    """Additional JSON parsing edge cases for LLM responses."""

    def test_parse_json_with_newlines(self):
        """Test parsing JSON with newlines inside strings."""
        agent = ReFileAgent()

        text = '''{"likely_intentional": false, "confidence": 0.85, "reason": "File was\\nmoved to Desktop"}'''
        data = agent._parse_llm_json_response(text)

        assert data is not None
        assert data["likely_intentional"] is False

    def test_parse_json_with_unicode(self):
        """Test parsing JSON with unicode characters."""
        agent = ReFileAgent()

        text = '{"likely_intentional": true, "confidence": 0.9, "reason": "Intentional → moved"}'
        data = agent._parse_llm_json_response(text)

        assert data is not None
        assert data["likely_intentional"] is True

    def test_parse_json_missing_confidence(self):
        """Test handling of missing confidence field."""
        agent = ReFileAgent()

        text = '{"likely_intentional": false, "reason": "Test"}'
        data = agent._parse_llm_json_response(text)

        assert data is not None
        assert "likely_intentional" in data
        # confidence key is missing but that's OK

    def test_parse_json_extra_text_after(self):
        """Test parsing JSON with extra text after the closing brace."""
        agent = ReFileAgent()

        text = '{"likely_intentional": true, "confidence": 0.8, "reason": "test"} Let me know if you need more info.'
        data = agent._parse_llm_json_response(text)

        assert data is not None
        assert data["likely_intentional"] is True

    def test_confidence_as_string_handled_t1_only(
        self, mock_llm_client, mock_model_router
    ):
        """Test that confidence as string is handled gracefully without escalation."""
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = json.dumps({
            "likely_intentional": True,
            "confidence": "high",  # String instead of float
            "reason": "Test",
        })
        mock_llm_client.generate.return_value = mock_response

        agent = ReFileAgent(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
            escalation_threshold=0.3,  # Set low threshold to prevent escalation
        )

        assessment, reason, confidence, model_used = agent._assess_drift_with_llm(
            "file.pdf",
            "/original/file.pdf",
            "/current/file.pdf",
            "2024-01-15T10:00:00",
        )

        # T1 converts string confidence to default 0.5
        # Since 0.5 > 0.3 (threshold), no escalation happens
        assert confidence == 0.5

    def test_negative_confidence_clamped_to_zero(
        self, mock_llm_client, mock_model_router
    ):
        """Test that negative confidence is clamped to 0.0."""
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = json.dumps({
            "likely_intentional": True,
            "confidence": -0.5,  # Negative
            "reason": "Test",
        })
        mock_llm_client.generate.return_value = mock_response

        agent = ReFileAgent(
            llm_client=mock_llm_client,
            model_router=mock_model_router,
        )

        assessment, reason, confidence, model_used = agent._assess_drift_with_llm(
            "file.pdf",
            "/original/file.pdf",
            "/current/file.pdf",
            "2024-01-15T10:00:00",
        )

        assert confidence == 0.0


# =============================================================================
# Detection Result Model Used Field Tests (Phase 16.6)
# =============================================================================


class TestDriftDetectionResultModelUsed:
    """Tests for model_used field in DriftDetectionResult."""

    def test_result_model_used_from_multiple_drifts(self, tmp_path):
        """Test that result.model_used aggregates models from all drift records."""
        record1 = DriftRecord(
            file_path="/Desktop/file1.pdf",
            original_filed_path="/Finances Bin/file1.pdf",
            current_path="/Desktop/file1.pdf",
            drift_assessment="likely_accidental",
            model_used="llama3.1:8b",
        )
        record2 = DriftRecord(
            file_path="/Desktop/file2.pdf",
            original_filed_path="/Work Bin/file2.pdf",
            current_path="/Desktop/file2.pdf",
            drift_assessment="likely_accidental",
            model_used="qwen2.5:14b",  # Different model (escalation)
        )

        result = DriftDetectionResult(
            drift_records=[record1, record2],
            files_checked=5,
        )

        # Model used should be set manually in detect_drift, not here
        # But drift records should preserve their individual model_used
        assert result.drift_records[0].model_used == "llama3.1:8b"
        assert result.drift_records[1].model_used == "qwen2.5:14b"

    def test_result_used_keyword_fallback_flag(self):
        """Test used_keyword_fallback flag in result."""
        result = DriftDetectionResult(
            used_keyword_fallback=True,
            model_used="",
        )

        assert result.used_keyword_fallback is True
        assert result.model_used == ""

    def test_to_dict_includes_model_used(self):
        """Test that to_dict includes model_used field."""
        result = DriftDetectionResult(
            files_checked=10,
            model_used="llama3.1:8b",
            used_keyword_fallback=False,
        )

        d = result.to_dict()
        assert d["model_used"] == "llama3.1:8b"
        assert d["used_keyword_fallback"] is False
