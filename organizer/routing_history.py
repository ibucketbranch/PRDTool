"""Persistent routing history for learning from corrections.

Tracks every file routing so the agent can detect when a user moves a file
back to In-Box (correction) and avoid repeating the same mistake.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_HISTORY_PATH = ".organizer/agent/routing_history.json"
MAX_ENTRIES = 10_000


def _now_iso() -> str:
    return datetime.now().isoformat()


@dataclass
class RoutingRecord:
    """A single routing event."""

    filename: str
    source_path: str
    destination_bin: str
    confidence: float
    matched_keywords: list[str] = field(default_factory=list)
    routed_at: str = ""
    status: str = "executed"  # executed | corrected | reverted | error

    def __post_init__(self) -> None:
        if not self.routed_at:
            self.routed_at = _now_iso()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RoutingRecord":
        return cls(
            filename=data.get("filename", ""),
            source_path=data.get("source_path", ""),
            destination_bin=data.get("destination_bin", ""),
            confidence=data.get("confidence", 0.0),
            matched_keywords=data.get("matched_keywords", []),
            routed_at=data.get("routed_at", ""),
            status=data.get("status", "executed"),
        )


class RoutingHistory:
    """Persistent log of file routings with FIFO eviction at cap."""

    def __init__(self, history_path: str | Path = DEFAULT_HISTORY_PATH):
        self.history_path = Path(history_path)
        self._records: list[RoutingRecord] = []
        self._load()

    def _load(self) -> None:
        """Load history from disk."""
        if not self.history_path.exists():
            self._records = []
            return
        try:
            data = json.loads(self.history_path.read_text(encoding="utf-8"))
            self._records = [
                RoutingRecord.from_dict(r) for r in data.get("records", [])
            ]
        except (json.JSONDecodeError, OSError):
            self._records = []

    def _save(self) -> None:
        """Save history to disk."""
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "records": [r.to_dict() for r in self._records],
            "updated_at": _now_iso(),
        }
        self.history_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def record(self, record: RoutingRecord) -> None:
        """Append a routing record and evict if over cap."""
        self._records.append(record)
        while len(self._records) > MAX_ENTRIES:
            self._records.pop(0)
        self._save()

    def find_by_filename(self, filename: str) -> RoutingRecord | None:
        """Find the most recent routing for this filename."""
        for r in reversed(self._records):
            if r.filename == filename:
                return r
        return None

    def find_by_destination(self, destination_bin: str) -> list[RoutingRecord]:
        """Find all routings to a given destination."""
        return [r for r in self._records if r.destination_bin == destination_bin]

    def get_recent(self, limit: int = 50) -> list[RoutingRecord]:
        """Get the most recent N records."""
        return self._records[-limit:][::-1]

    def is_correction(self, filename: str) -> bool:
        """True if this file was previously routed and is back in In-Box."""
        return self.find_by_filename(filename) is not None
