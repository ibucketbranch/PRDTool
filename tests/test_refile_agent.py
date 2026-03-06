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
