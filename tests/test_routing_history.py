"""Tests for organizer.routing_history module."""

from pathlib import Path

import pytest

from organizer.routing_history import (
    RoutingHistory,
    RoutingRecord,
)


def test_record_and_find(tmp_path: Path) -> None:
    """Record a routing and find by filename."""
    history_path = tmp_path / "routing_history.json"
    history = RoutingHistory(history_path)

    record = RoutingRecord(
        filename="Tax_2024.pdf",
        source_path="/inbox/Tax_2024.pdf",
        destination_bin="Finances Bin/Taxes",
        confidence=0.95,
        matched_keywords=["tax", "2024"],
    )
    history.record(record)

    found = history.find_by_filename("Tax_2024.pdf")
    assert found is not None
    assert found.filename == "Tax_2024.pdf"
    assert found.destination_bin == "Finances Bin/Taxes"
    assert found.status == "executed"


def test_find_by_filename_returns_none_when_not_found(tmp_path: Path) -> None:
    """find_by_filename returns None when no match."""
    history = RoutingHistory(tmp_path / "routing_history.json")
    assert history.find_by_filename("nonexistent.pdf") is None


def test_fifo_eviction_at_cap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Records are evicted FIFO when over cap."""
    monkeypatch.setattr("organizer.routing_history.MAX_ENTRIES", 50)
    history_path = tmp_path / "routing_history.json"
    history = RoutingHistory(history_path)
    history._save = lambda: None  # Skip save during test
    for i in range(60):  # 10 over cap of 50
        history.record(
            RoutingRecord(
                filename=f"file_{i}.pdf",
                source_path=f"/inbox/file_{i}.pdf",
                destination_bin="Test",
                confidence=0.9,
            )
        )
    assert len(history._records) == 50
    # First 10 records evicted (file_0 through file_9)
    assert history.find_by_filename("file_0.pdf") is None
    assert history.find_by_filename("file_9.pdf") is None
    assert history.find_by_filename("file_10.pdf") is not None


def test_is_correction(tmp_path: Path) -> None:
    """is_correction returns True when file was previously routed."""
    history_path = tmp_path / "routing_history.json"
    history = RoutingHistory(history_path)

    history.record(
        RoutingRecord(
            filename="resume.pdf",
            source_path="/inbox/resume.pdf",
            destination_bin="Personal Bin/Resumes",
            confidence=0.92,
        )
    )

    assert history.is_correction("resume.pdf") is True
    assert history.is_correction("other.pdf") is False


def test_get_recent(tmp_path: Path) -> None:
    """get_recent returns most recent N records in reverse order."""
    history_path = tmp_path / "routing_history.json"
    history = RoutingHistory(history_path)

    for i in range(5):
        history.record(
            RoutingRecord(
                filename=f"file_{i}.pdf",
                source_path=f"/inbox/file_{i}.pdf",
                destination_bin="Test",
                confidence=0.9,
            )
        )

    recent = history.get_recent(limit=3)
    assert len(recent) == 3
    assert recent[0].filename == "file_4.pdf"
    assert recent[1].filename == "file_3.pdf"
    assert recent[2].filename == "file_2.pdf"


# =============================================================================
# Phase 14: Refile History Update Tests
# =============================================================================


class TestMarkAsRefiled:
    """Tests for RoutingHistory.mark_as_refiled()."""

    def test_mark_as_refiled_updates_status(self, tmp_path: Path) -> None:
        """mark_as_refiled updates the record status to 'refiled'."""
        history = RoutingHistory(tmp_path / "routing_history.json")
        history.record(
            RoutingRecord(
                filename="tax_2024.pdf",
                source_path="/inbox/tax_2024.pdf",
                destination_bin="Finances Bin/Taxes",
                confidence=0.95,
            )
        )

        result = history.mark_as_refiled("tax_2024.pdf")
        assert result is True

        record = history.find_by_filename("tax_2024.pdf")
        assert record is not None
        assert record.status == "refiled"

    def test_mark_as_refiled_returns_false_when_not_found(
        self, tmp_path: Path
    ) -> None:
        """mark_as_refiled returns False when filename not in history."""
        history = RoutingHistory(tmp_path / "routing_history.json")
        result = history.mark_as_refiled("nonexistent.pdf")
        assert result is False

    def test_mark_as_refiled_updates_most_recent(self, tmp_path: Path) -> None:
        """mark_as_refiled marks the most recent record, not earlier ones."""
        history = RoutingHistory(tmp_path / "routing_history.json")

        # Record same file twice (e.g., filed, then re-filed)
        history.record(
            RoutingRecord(
                filename="tax_2024.pdf",
                source_path="/inbox/tax_2024.pdf",
                destination_bin="Finances Bin/Taxes",
                confidence=0.92,
            )
        )
        history.record(
            RoutingRecord(
                filename="tax_2024.pdf",
                source_path="/Desktop/tax_2024.pdf",
                destination_bin="Finances Bin/Taxes/2024",
                confidence=0.98,
            )
        )

        history.mark_as_refiled("tax_2024.pdf")

        # Most recent (second) record should be marked
        records = history.get_all_records()
        assert len(records) == 2
        # First record should still be executed
        assert records[0].status == "executed"
        # Second (most recent) should be refiled
        assert records[1].status == "refiled"

    def test_mark_as_refiled_persists_to_disk(self, tmp_path: Path) -> None:
        """mark_as_refiled saves the change to disk."""
        history_path = tmp_path / "routing_history.json"
        history = RoutingHistory(history_path)
        history.record(
            RoutingRecord(
                filename="resume.pdf",
                source_path="/inbox/resume.pdf",
                destination_bin="Work Bin/Resumes",
                confidence=0.88,
            )
        )

        history.mark_as_refiled("resume.pdf")

        # Reload from disk
        history2 = RoutingHistory(history_path)
        record = history2.find_by_filename("resume.pdf")
        assert record is not None
        assert record.status == "refiled"


class TestRecordRefile:
    """Tests for RoutingHistory.record_refile()."""

    def test_record_refile_creates_new_record(self, tmp_path: Path) -> None:
        """record_refile creates a new routing record."""
        history = RoutingHistory(tmp_path / "routing_history.json")

        # Original filing
        history.record(
            RoutingRecord(
                filename="invoice_2024.pdf",
                source_path="/inbox/invoice_2024.pdf",
                destination_bin="Finances Bin/Invoices",
                confidence=0.91,
            )
        )

        # Refile from drifted location
        new_record = history.record_refile(
            filename="invoice_2024.pdf",
            source_path="/Desktop/invoice_2024.pdf",  # Drifted location
            destination_bin="Finances Bin/Invoices/2024",  # New destination
            confidence=0.95,
            matched_keywords=["invoice", "2024"],
        )

        assert new_record.filename == "invoice_2024.pdf"
        assert new_record.source_path == "/Desktop/invoice_2024.pdf"
        assert new_record.destination_bin == "Finances Bin/Invoices/2024"
        assert new_record.status == "executed"

    def test_record_refile_marks_original_as_refiled(self, tmp_path: Path) -> None:
        """record_refile marks the original record as 'refiled'."""
        history = RoutingHistory(tmp_path / "routing_history.json")

        # Original filing
        history.record(
            RoutingRecord(
                filename="contract.pdf",
                source_path="/inbox/contract.pdf",
                destination_bin="Legal Bin/Contracts",
                confidence=0.89,
            )
        )

        # Refile
        history.record_refile(
            filename="contract.pdf",
            source_path="/Downloads/contract.pdf",
            destination_bin="Legal Bin/Contracts/2024",
            confidence=0.94,
        )

        # Check we have two records
        records = history.get_all_records()
        assert len(records) == 2

        # First record should be marked as refiled
        assert records[0].status == "refiled"
        # Second record (the refile) should be executed
        assert records[1].status == "executed"

    def test_record_refile_with_no_original(self, tmp_path: Path) -> None:
        """record_refile works even when there's no original record."""
        history = RoutingHistory(tmp_path / "routing_history.json")

        # Refile without any prior record (edge case)
        new_record = history.record_refile(
            filename="orphan.pdf",
            source_path="/tmp/orphan.pdf",
            destination_bin="Archive/Unknown",
            confidence=0.75,
        )

        assert new_record.status == "executed"
        records = history.get_all_records()
        assert len(records) == 1

    def test_record_refile_persists_both_records(self, tmp_path: Path) -> None:
        """record_refile persists both the refiled and new records to disk."""
        history_path = tmp_path / "routing_history.json"
        history = RoutingHistory(history_path)

        # Original filing
        history.record(
            RoutingRecord(
                filename="report.pdf",
                source_path="/inbox/report.pdf",
                destination_bin="Work Bin/Reports",
                confidence=0.92,
            )
        )

        # Refile
        history.record_refile(
            filename="report.pdf",
            source_path="/Desktop/report.pdf",
            destination_bin="Work Bin/Reports/2024",
            confidence=0.96,
        )

        # Reload from disk
        history2 = RoutingHistory(history_path)
        records = history2.get_all_records()

        assert len(records) == 2
        assert records[0].status == "refiled"
        assert records[1].status == "executed"
        assert records[1].destination_bin == "Work Bin/Reports/2024"


class TestFindRefiled:
    """Tests for RoutingHistory.find_refiled()."""

    def test_find_refiled_returns_refiled_records(self, tmp_path: Path) -> None:
        """find_refiled returns all records with status='refiled'."""
        history = RoutingHistory(tmp_path / "routing_history.json")

        # Create some records
        history.record(
            RoutingRecord(
                filename="file1.pdf",
                source_path="/inbox/file1.pdf",
                destination_bin="Test/Folder1",
                confidence=0.9,
            )
        )
        history.record(
            RoutingRecord(
                filename="file2.pdf",
                source_path="/inbox/file2.pdf",
                destination_bin="Test/Folder2",
                confidence=0.9,
            )
        )

        # Mark file1 as refiled
        history.mark_as_refiled("file1.pdf")

        refiled = history.find_refiled()
        assert len(refiled) == 1
        assert refiled[0].filename == "file1.pdf"

    def test_find_refiled_returns_empty_when_none(self, tmp_path: Path) -> None:
        """find_refiled returns empty list when no records are refiled."""
        history = RoutingHistory(tmp_path / "routing_history.json")
        history.record(
            RoutingRecord(
                filename="active.pdf",
                source_path="/inbox/active.pdf",
                destination_bin="Test",
                confidence=0.9,
            )
        )

        refiled = history.find_refiled()
        assert len(refiled) == 0


class TestGetAllRecords:
    """Tests for RoutingHistory.get_all_records()."""

    def test_get_all_records_returns_copy(self, tmp_path: Path) -> None:
        """get_all_records returns a copy, not the internal list."""
        history = RoutingHistory(tmp_path / "routing_history.json")
        history.record(
            RoutingRecord(
                filename="test.pdf",
                source_path="/inbox/test.pdf",
                destination_bin="Test",
                confidence=0.9,
            )
        )

        records = history.get_all_records()
        records.clear()  # Modify the returned list

        # Internal list should be unaffected
        assert len(history._records) == 1

    def test_get_all_records_empty_history(self, tmp_path: Path) -> None:
        """get_all_records returns empty list for empty history."""
        history = RoutingHistory(tmp_path / "routing_history.json")
        assert history.get_all_records() == []


class TestRoutingRecordRefiledStatus:
    """Tests for the 'refiled' status in RoutingRecord."""

    def test_record_with_refiled_status(self) -> None:
        """RoutingRecord can be created with status='refiled'."""
        record = RoutingRecord(
            filename="old.pdf",
            source_path="/inbox/old.pdf",
            destination_bin="Archive",
            confidence=0.85,
            status="refiled",
        )
        assert record.status == "refiled"

    def test_record_from_dict_with_refiled(self) -> None:
        """RoutingRecord.from_dict correctly handles 'refiled' status."""
        data = {
            "filename": "legacy.pdf",
            "source_path": "/old/path.pdf",
            "destination_bin": "Archive",
            "confidence": 0.8,
            "status": "refiled",
            "matched_keywords": [],
            "routed_at": "2024-01-15T10:30:00",
        }
        record = RoutingRecord.from_dict(data)
        assert record.status == "refiled"

    def test_record_to_dict_with_refiled(self) -> None:
        """RoutingRecord.to_dict correctly serializes 'refiled' status."""
        record = RoutingRecord(
            filename="test.pdf",
            source_path="/path/test.pdf",
            destination_bin="Target",
            confidence=0.9,
            status="refiled",
        )
        data = record.to_dict()
        assert data["status"] == "refiled"


# =============================================================================
# Phase 16.4: Explainability Fields Tests
# =============================================================================


class TestRoutingRecordExplainability:
    """Tests for explainability fields in RoutingRecord (Phase 16.4)."""

    def test_record_with_explainability_fields(self) -> None:
        """RoutingRecord can be created with reason, model_used, and used_keyword_fallback."""
        record = RoutingRecord(
            filename="tax_2024.pdf",
            source_path="/inbox/tax_2024.pdf",
            destination_bin="Finances Bin/Taxes",
            confidence=0.92,
            matched_keywords=["tax", "2024"],
            reason="File contains 'tax return' in content and '2024' in filename",
            model_used="llama3.1:8b-instruct-q8_0",
            used_keyword_fallback=False,
        )
        assert record.reason == "File contains 'tax return' in content and '2024' in filename"
        assert record.model_used == "llama3.1:8b-instruct-q8_0"
        assert record.used_keyword_fallback is False

    def test_record_default_explainability_values(self) -> None:
        """RoutingRecord has sensible defaults for explainability fields."""
        record = RoutingRecord(
            filename="test.pdf",
            source_path="/inbox/test.pdf",
            destination_bin="Test",
            confidence=0.9,
        )
        assert record.reason == ""
        assert record.model_used == ""
        assert record.used_keyword_fallback is False

    def test_record_to_dict_includes_explainability(self) -> None:
        """RoutingRecord.to_dict includes explainability fields."""
        record = RoutingRecord(
            filename="invoice.pdf",
            source_path="/inbox/invoice.pdf",
            destination_bin="Finances Bin/Invoices",
            confidence=0.88,
            reason="LLM classified as invoice based on content structure",
            model_used="qwen2.5-coder:14b",
            used_keyword_fallback=False,
        )
        data = record.to_dict()
        assert data["reason"] == "LLM classified as invoice based on content structure"
        assert data["model_used"] == "qwen2.5-coder:14b"
        assert data["used_keyword_fallback"] is False

    def test_record_from_dict_with_explainability(self) -> None:
        """RoutingRecord.from_dict correctly handles explainability fields."""
        data = {
            "filename": "resume.pdf",
            "source_path": "/inbox/resume.pdf",
            "destination_bin": "Personal Bin/Resumes",
            "confidence": 0.95,
            "matched_keywords": ["resume"],
            "routed_at": "2024-03-15T14:30:00",
            "status": "executed",
            "reason": "Filename contains 'resume', classified as personal document",
            "model_used": "llama3.1:8b-instruct-q8_0",
            "used_keyword_fallback": False,
        }
        record = RoutingRecord.from_dict(data)
        assert record.reason == "Filename contains 'resume', classified as personal document"
        assert record.model_used == "llama3.1:8b-instruct-q8_0"
        assert record.used_keyword_fallback is False

    def test_record_from_dict_missing_explainability_fields(self) -> None:
        """RoutingRecord.from_dict handles missing explainability fields (legacy data)."""
        # Simulate legacy data without explainability fields
        data = {
            "filename": "old_file.pdf",
            "source_path": "/inbox/old_file.pdf",
            "destination_bin": "Archive",
            "confidence": 0.85,
            "matched_keywords": [],
            "routed_at": "2023-01-01T10:00:00",
            "status": "executed",
            # No reason, model_used, or used_keyword_fallback
        }
        record = RoutingRecord.from_dict(data)
        assert record.reason == ""
        assert record.model_used == ""
        assert record.used_keyword_fallback is False

    def test_record_with_keyword_fallback(self) -> None:
        """RoutingRecord correctly represents keyword fallback routing."""
        record = RoutingRecord(
            filename="bank_statement.pdf",
            source_path="/inbox/bank_statement.pdf",
            destination_bin="Finances Bin/Banking",
            confidence=0.92,
            matched_keywords=["bank", "statement"],
            reason="",  # No LLM reason for keyword fallback
            model_used="",  # No model used
            used_keyword_fallback=True,
        )
        assert record.used_keyword_fallback is True
        assert record.model_used == ""
        assert record.reason == ""


class TestRoutingHistoryExplainability:
    """Tests for explainability in RoutingHistory operations."""

    def test_record_preserves_explainability(self, tmp_path: Path) -> None:
        """RoutingHistory.record() preserves explainability fields."""
        history = RoutingHistory(tmp_path / "routing_history.json")

        record = RoutingRecord(
            filename="tax_return.pdf",
            source_path="/inbox/tax_return.pdf",
            destination_bin="Finances Bin/Taxes",
            confidence=0.94,
            reason="Content analysis detected IRS form 1040",
            model_used="llama3.1:8b-instruct-q8_0",
            used_keyword_fallback=False,
        )
        history.record(record)

        found = history.find_by_filename("tax_return.pdf")
        assert found is not None
        assert found.reason == "Content analysis detected IRS form 1040"
        assert found.model_used == "llama3.1:8b-instruct-q8_0"
        assert found.used_keyword_fallback is False

    def test_record_refile_with_explainability(self, tmp_path: Path) -> None:
        """RoutingHistory.record_refile() preserves explainability fields."""
        history = RoutingHistory(tmp_path / "routing_history.json")

        # Original filing
        history.record(
            RoutingRecord(
                filename="contract.pdf",
                source_path="/inbox/contract.pdf",
                destination_bin="Legal Bin/Contracts",
                confidence=0.88,
                reason="Initial classification as legal document",
                model_used="llama3.1:8b-instruct-q8_0",
            )
        )

        # Refile with LLM reasoning
        new_record = history.record_refile(
            filename="contract.pdf",
            source_path="/Desktop/contract.pdf",
            destination_bin="Legal Bin/Contracts/2024",
            confidence=0.95,
            reason="Refile to year-specific folder based on document date",
            model_used="qwen2.5-coder:14b",
            used_keyword_fallback=False,
        )

        assert new_record.reason == "Refile to year-specific folder based on document date"
        assert new_record.model_used == "qwen2.5-coder:14b"
        assert new_record.used_keyword_fallback is False

    def test_explainability_persists_to_disk(self, tmp_path: Path) -> None:
        """Explainability fields persist after reload from disk."""
        history_path = tmp_path / "routing_history.json"
        history = RoutingHistory(history_path)

        history.record(
            RoutingRecord(
                filename="report.pdf",
                source_path="/inbox/report.pdf",
                destination_bin="Work Bin/Reports",
                confidence=0.91,
                reason="Classified as work report based on content",
                model_used="llama3.1:8b-instruct-q8_0",
                used_keyword_fallback=False,
            )
        )

        # Reload from disk
        history2 = RoutingHistory(history_path)
        found = history2.find_by_filename("report.pdf")

        assert found is not None
        assert found.reason == "Classified as work report based on content"
        assert found.model_used == "llama3.1:8b-instruct-q8_0"
        assert found.used_keyword_fallback is False

    def test_get_recent_includes_explainability(self, tmp_path: Path) -> None:
        """get_recent() includes explainability fields in returned records."""
        history = RoutingHistory(tmp_path / "routing_history.json")

        history.record(
            RoutingRecord(
                filename="invoice_001.pdf",
                source_path="/inbox/invoice_001.pdf",
                destination_bin="Finances Bin/Invoices",
                confidence=0.89,
                reason="Invoice detected from content structure",
                model_used="llama3.1:8b-instruct-q8_0",
            )
        )
        history.record(
            RoutingRecord(
                filename="invoice_002.pdf",
                source_path="/inbox/invoice_002.pdf",
                destination_bin="Finances Bin/Invoices",
                confidence=0.92,
                matched_keywords=["invoice"],
                used_keyword_fallback=True,
            )
        )

        recent = history.get_recent(limit=2)
        assert len(recent) == 2

        # Most recent first
        assert recent[0].filename == "invoice_002.pdf"
        assert recent[0].used_keyword_fallback is True

        assert recent[1].filename == "invoice_001.pdf"
        assert recent[1].reason == "Invoice detected from content structure"
        assert recent[1].model_used == "llama3.1:8b-instruct-q8_0"
