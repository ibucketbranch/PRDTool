"""Taxonomy utilities for managing bin structure and locked status.

This module provides utilities for loading, validating, and querying the taxonomy.
Locked bins cannot be renamed, moved, or merged by the agent. Subcategories can
still be created under locked bins.

Example usage:
    taxonomy = load_taxonomy("/path/to/ROOT_TAXONOMY.json")
    if is_bin_locked(taxonomy, "VA"):
        print("VA bin is locked - cannot rename or move")
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TaxonomyBin:
    """Represents a top-level bin in the taxonomy.

    Attributes:
        name: The bin name (e.g., "VA", "Finances Bin").
        locked: Whether the bin is locked (cannot be renamed/moved/merged).
        subcategories: Dict of subcategory names to their paths.
    """

    name: str
    locked: bool = False
    subcategories: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "locked": self.locked,
            "subcategories": self.subcategories.copy(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaxonomyBin":
        """Create from dictionary."""
        return cls(
            name=data.get("name", ""),
            locked=data.get("locked", False),
            subcategories=data.get("subcategories", {}),
        )


@dataclass
class Taxonomy:
    """Represents the full taxonomy structure.

    Attributes:
        version: Version string for the taxonomy.
        description: Human-readable description.
        bins: Dict mapping bin names to TaxonomyBin objects.
        rules: Dict of rule names to bin mappings.
    """

    version: str = ""
    description: str = ""
    bins: dict[str, TaxonomyBin] = field(default_factory=dict)
    rules: dict[str, str] = field(default_factory=dict)

    def get_locked_bins(self) -> list[str]:
        """Get list of all locked bin names."""
        return [name for name, bin_obj in self.bins.items() if bin_obj.locked]

    def is_bin_locked(self, bin_name: str) -> bool:
        """Check if a bin is locked.

        Args:
            bin_name: The bin name to check.

        Returns:
            True if the bin is locked, False otherwise.
        """
        bin_obj = self.bins.get(bin_name)
        if bin_obj:
            return bin_obj.locked
        return False

    def get_bin_names(self) -> list[str]:
        """Get list of all bin names."""
        return list(self.bins.keys())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary (original format with locked fields)."""
        result: dict[str, Any] = {
            "version": self.version,
            "description": self.description,
            "canonical_roots": [],
            "locked_bins": {},
            "rules": self.rules.copy(),
        }

        for name, bin_obj in self.bins.items():
            result["canonical_roots"].append(name)
            if bin_obj.locked:
                result["locked_bins"][name] = True

        return result


def load_taxonomy(path: str | Path) -> Taxonomy:
    """Load taxonomy from a JSON file.

    The taxonomy file should have this structure:
    {
        "version": "2026-02-22",
        "description": "...",
        "canonical_roots": ["VA", "Finances Bin", ...],
        "locked_bins": {"VA": true, "Finances Bin": true, ...},  # optional
        "rules": {...}
    }

    Args:
        path: Path to the taxonomy JSON file.

    Returns:
        Taxonomy object.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    with open(path) as f:
        data = json.load(f)

    taxonomy = Taxonomy(
        version=data.get("version", ""),
        description=data.get("description", ""),
        rules=data.get("rules", {}),
    )

    # Get locked bins from the locked_bins dict
    locked_bins = data.get("locked_bins", {})

    # Build TaxonomyBin objects for each canonical root
    for root_name in data.get("canonical_roots", []):
        is_locked = locked_bins.get(root_name, False)
        taxonomy.bins[root_name] = TaxonomyBin(
            name=root_name,
            locked=is_locked,
        )

    # Add subcategories if present
    for subcat_key in ["family_members", "finance_subcategories"]:
        if subcat_key in data:
            subcats = data[subcat_key]
            # Find the parent bin for these subcategories
            for subcat_name, subcat_path in subcats.items():
                parent_bin = subcat_path.split("/")[0] if "/" in subcat_path else ""
                if parent_bin and parent_bin in taxonomy.bins:
                    taxonomy.bins[parent_bin].subcategories[subcat_name] = subcat_path

    return taxonomy


def save_taxonomy(taxonomy: Taxonomy, path: str | Path) -> None:
    """Save taxonomy to a JSON file.

    Args:
        taxonomy: The Taxonomy object to save.
        path: Path to save the JSON file.
    """
    with open(path, "w") as f:
        json.dump(taxonomy.to_dict(), f, indent=2)


def is_bin_locked(taxonomy: Taxonomy | dict[str, Any], bin_name: str) -> bool:
    """Check if a bin is locked.

    Supports both Taxonomy objects and raw dict format.

    Args:
        taxonomy: Taxonomy object or raw dict from JSON.
        bin_name: The bin name to check.

    Returns:
        True if the bin is locked, False otherwise.
    """
    if isinstance(taxonomy, Taxonomy):
        return taxonomy.is_bin_locked(bin_name)

    # Raw dict format
    locked_bins = taxonomy.get("locked_bins", {})
    return locked_bins.get(bin_name, False)


def get_locked_bins(taxonomy: Taxonomy | dict[str, Any]) -> list[str]:
    """Get list of all locked bin names.

    Args:
        taxonomy: Taxonomy object or raw dict from JSON.

    Returns:
        List of locked bin names.
    """
    if isinstance(taxonomy, Taxonomy):
        return taxonomy.get_locked_bins()

    # Raw dict format
    locked_bins = taxonomy.get("locked_bins", {})
    return [name for name, is_locked in locked_bins.items() if is_locked]


def validate_bin_operation(
    taxonomy: Taxonomy | dict[str, Any],
    bin_name: str,
    operation: str,
) -> tuple[bool, str]:
    """Validate if an operation can be performed on a bin.

    Args:
        taxonomy: Taxonomy object or raw dict from JSON.
        bin_name: The bin to operate on.
        operation: The operation type ("rename", "move", "merge", "create_subcategory").

    Returns:
        Tuple of (is_allowed, reason).
    """
    if operation not in ("rename", "move", "merge", "create_subcategory"):
        return False, f"Unknown operation: {operation}"

    is_locked = is_bin_locked(taxonomy, bin_name)

    # Locked bins can have subcategories created, but cannot be renamed/moved/merged
    if operation == "create_subcategory":
        return True, "Subcategories can always be created under any bin"

    if is_locked:
        return False, f"Bin '{bin_name}' is locked and cannot be {operation}d"

    return True, f"Operation '{operation}' is allowed on bin '{bin_name}'"


def is_path_under_locked_bin(
    taxonomy: Taxonomy | dict[str, Any],
    path: str,
) -> tuple[bool, str]:
    """Check if a path is under a locked bin.

    Args:
        taxonomy: Taxonomy object or raw dict from JSON.
        path: The path to check (e.g., "VA/Claims/2024").

    Returns:
        Tuple of (is_under_locked, bin_name if locked else "").
    """
    # Extract the root bin from the path
    parts = path.replace("\\", "/").split("/")
    if not parts:
        return False, ""

    root_bin = parts[0]

    if is_bin_locked(taxonomy, root_bin):
        return True, root_bin

    return False, ""


def create_default_taxonomy() -> Taxonomy:
    """Create a default taxonomy with standard bins (all locked by default).

    Returns:
        A new Taxonomy with standard root bins.
    """
    default_bins = [
        "Family Bin",
        "Finances Bin",
        "Legal Bin",
        "Personal Bin",
        "Work Bin",
        "VA",
        "Archive",
        "Needs-Review",
    ]

    taxonomy = Taxonomy(
        version="2026-03-03",
        description="Default taxonomy with locked root bins",
    )

    for bin_name in default_bins:
        taxonomy.bins[bin_name] = TaxonomyBin(
            name=bin_name,
            locked=True,  # All root bins are locked by default
        )

    return taxonomy
