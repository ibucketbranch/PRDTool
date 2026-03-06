"""Tests for organizer.routing_history module."""

import json
from pathlib import Path

import pytest

from organizer.routing_history import (
    DEFAULT_HISTORY_PATH,
    MAX_ENTRIES,
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
