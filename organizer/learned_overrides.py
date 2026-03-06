"""Learned overrides from user corrections.

Overrides take priority over built-in ROUTING_RULES in inbox_processor.
When a user corrects a routing, the system learns the pattern and applies
it forever after.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_OVERRIDES_PATH = ".organizer/agent/learned_overrides.json"


def _now_iso() -> str:
    return datetime.now().isoformat()


@dataclass
class LearnedOverride:
    """A user correction that overrides default routing."""

    pattern: str  # keyword or filename fragment
    correct_bin: str
    source: str = "user_correction"  # user_correction | manual
    created_at: str = ""
    hit_count: int = 0

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = _now_iso()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LearnedOverride":
        return cls(
            pattern=data.get("pattern", ""),
            correct_bin=data.get("correct_bin", ""),
            source=data.get("source", "user_correction"),
            created_at=data.get("created_at", ""),
            hit_count=data.get("hit_count", 0),
        )


class OverrideRegistry:
    """Registry of learned overrides with priority over built-in rules."""

    def __init__(self, overrides_path: str | Path = DEFAULT_OVERRIDES_PATH):
        self.overrides_path = Path(overrides_path)
        self._overrides: list[LearnedOverride] = []
        self._load()

    def _load(self) -> None:
        """Load overrides from disk."""
        if not self.overrides_path.exists():
            self._overrides = []
            return
        try:
            data = json.loads(self.overrides_path.read_text(encoding="utf-8"))
            self._overrides = [
                LearnedOverride.from_dict(o) for o in data.get("overrides", [])
            ]
        except (json.JSONDecodeError, OSError):
            self._overrides = []

    def _save(self) -> None:
        """Save overrides to disk."""
        self.overrides_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "overrides": [o.to_dict() for o in self._overrides],
            "updated_at": _now_iso(),
        }
        self.overrides_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def add(self, override: LearnedOverride) -> None:
        """Add a new override. Replaces existing with same pattern."""
        self._overrides = [o for o in self._overrides if o.pattern != override.pattern]
        self._overrides.append(override)
        self._save()

    def find_match(self, filename: str) -> LearnedOverride | None:
        """Find an override that matches the filename (case-insensitive)."""
        stem_lower = Path(filename).stem.lower()
        filename_lower = filename.lower()
        for o in self._overrides:
            pattern_lower = o.pattern.lower()
            if pattern_lower in stem_lower or pattern_lower in filename_lower:
                o.hit_count += 1
                self._save()
                return o
        return None

    def remove(self, pattern: str) -> bool:
        """Remove an override by pattern. Returns True if found and removed."""
        before = len(self._overrides)
        self._overrides = [o for o in self._overrides if o.pattern != pattern]
        if len(self._overrides) < before:
            self._save()
            return True
        return False

    def get_all(self) -> list[LearnedOverride]:
        """Return all overrides."""
        return list(self._overrides)
