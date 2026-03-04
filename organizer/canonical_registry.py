"""Canonical folder registry for persistent folder name management.

This module provides a registry that tracks canonical folder names and
enables detection of similar folders to prevent redundant folder creation.
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from organizer.fuzzy_matcher import are_similar_folders, normalize_folder_name


@dataclass
class FolderEntry:
    """Represents a registered folder in the canonical registry."""

    path: str
    normalized_name: str
    category: str = ""

    def to_dict(self) -> dict:
        """Convert entry to dictionary for JSON serialization."""
        return {
            "path": self.path,
            "normalized_name": self.normalized_name,
            "category": self.category,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FolderEntry":
        """Create entry from dictionary."""
        return cls(
            path=data["path"],
            normalized_name=data["normalized_name"],
            category=data.get("category", ""),
        )


@dataclass
class CanonicalRegistry:
    """Registry for tracking canonical folder names.

    The registry persists folder information to a JSON file and provides
    methods to detect similar folders, register new folders, and retrieve
    canonical paths for folder names.

    Attributes:
        storage_path: Path to the JSON file for persistence.
        threshold: Similarity threshold for folder matching (0.0 to 1.0).
        folders: Dictionary mapping normalized names to FolderEntry objects.
    """

    storage_path: Path = field(
        default_factory=lambda: Path(".organizer/canonical_folders.json")
    )
    threshold: float = 0.8
    folders: dict[str, FolderEntry] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Load existing registry data from storage if available."""
        self.storage_path = Path(self.storage_path)
        self.load()

    def load(self) -> None:
        """Load registry data from the JSON storage file."""
        if self.storage_path.exists():
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.folders = {
                    key: FolderEntry.from_dict(entry)
                    for key, entry in data.get("folders", {}).items()
                }

    def save(self) -> None:
        """Save registry data to the JSON storage file."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "folders": {key: entry.to_dict() for key, entry in self.folders.items()}
        }
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def register_folder(self, path: str, category: str = "") -> Optional[FolderEntry]:
        """Register a folder in the registry.

        If a similar folder already exists, returns the existing entry
        instead of creating a new one.

        Args:
            path: The folder path to register.
            category: Optional category for the folder (e.g., "Employment", "Finances").

        Returns:
            The existing similar FolderEntry if one exists, None if the folder
            was newly registered.

        Examples:
            >>> registry = CanonicalRegistry(storage_path=Path("/tmp/test.json"))
            >>> registry.register_folder("/docs/Resume")  # Returns None (new)
            >>> registry.register_folder("/docs/Resumes")  # Returns existing entry
            FolderEntry(path='/docs/Resume', ...)
        """
        folder_name = os.path.basename(path.rstrip("/\\"))
        normalized = normalize_folder_name(folder_name)

        # Check if a similar folder already exists
        existing = self._find_similar_folder(folder_name)
        if existing is not None:
            return existing

        # Register as new canonical folder
        entry = FolderEntry(path=path, normalized_name=normalized, category=category)
        self.folders[normalized] = entry
        self.save()
        return None

    def _find_similar_folder(self, name: str) -> Optional[FolderEntry]:
        """Find a similar folder in the registry.

        Args:
            name: The folder name to search for.

        Returns:
            The FolderEntry if a similar folder exists, None otherwise.
        """
        for entry in self.folders.values():
            entry_name = os.path.basename(entry.path.rstrip("/\\"))
            if are_similar_folders(name, entry_name, threshold=self.threshold):
                return entry
        return None

    def get_canonical_folder(self, proposed_name: str) -> Optional[FolderEntry]:
        """Get the canonical folder for a proposed folder name.

        Args:
            proposed_name: The proposed folder name to look up.

        Returns:
            The canonical FolderEntry if a similar folder exists, None otherwise.

        Examples:
            >>> registry = CanonicalRegistry()
            >>> registry.register_folder("/docs/Resume")
            >>> registry.get_canonical_folder("Resumes")
            FolderEntry(path='/docs/Resume', ...)
            >>> registry.get_canonical_folder("Taxes")  # Returns None
        """
        return self._find_similar_folder(proposed_name)

    def get_or_create(self, category: str, name: str, base_path: str = "") -> str:
        """Get the canonical path for a folder, creating if necessary.

        This is the main entry point for folder resolution. It checks if a
        similar folder already exists and returns its path, otherwise
        registers the new folder and returns its path.

        Args:
            category: The category for the folder (e.g., "Employment").
            name: The folder name (e.g., "Resumes").
            base_path: Optional base path prefix for the folder.

        Returns:
            The canonical path for the folder.

        Examples:
            >>> registry = CanonicalRegistry()
            >>> registry.get_or_create("Employment", "Resume", "/iCloud")
            '/iCloud/Employment/Resume'
            >>> registry.get_or_create("Employment", "Resumes", "/iCloud")
            '/iCloud/Employment/Resume'  # Returns existing canonical path
        """
        # Check if a similar folder already exists
        existing = self.get_canonical_folder(name)
        if existing is not None:
            return existing.path

        # Create new canonical path
        if base_path:
            path = (
                os.path.join(base_path, category, name)
                if category
                else os.path.join(base_path, name)
            )
        else:
            path = os.path.join(category, name) if category else name

        # Register and return the new path
        self.register_folder(path, category=category)
        return path

    def list_folders(self, category: Optional[str] = None) -> list[FolderEntry]:
        """List all registered folders, optionally filtered by category.

        Args:
            category: Optional category to filter by.

        Returns:
            List of FolderEntry objects.
        """
        if category is None:
            return list(self.folders.values())
        return [entry for entry in self.folders.values() if entry.category == category]

    def clear(self) -> None:
        """Clear all entries from the registry and save."""
        self.folders.clear()
        self.save()
