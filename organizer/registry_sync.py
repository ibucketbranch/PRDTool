"""Registry sync module for synchronizing canonical registry with taxonomy.

This module provides functionality to cross-check and synchronize the
canonical_registry.json against ROOT_TAXONOMY.json:
- Detect orphaned entries (registry mappings that don't match valid taxonomy paths)
- Detect missing entries (taxonomy paths not represented in registry)
- Resync the registry to ensure consistency with taxonomy

Example usage:
    from organizer.registry_sync import resync_registry_with_taxonomy, SyncReport

    report = resync_registry_with_taxonomy(
        registry_path="/path/to/canonical_registry.json",
        taxonomy_path="/path/to/ROOT_TAXONOMY.json"
    )
    print(f"Orphaned entries: {len(report.orphaned_entries)}")
    print(f"Missing entries: {len(report.missing_entries)}")
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SyncReport:
    """Report of canonical registry sync with taxonomy.

    Attributes:
        orphaned_entries: Registry entries with destinations not in taxonomy.
        missing_entries: Taxonomy paths not represented in registry.
        valid_entries: Registry entries that match valid taxonomy paths.
        special_entries: Entries with special handling (e.g., __KEEP_AT_ROOT__).
    """

    orphaned_entries: dict[str, str] = field(default_factory=dict)
    missing_entries: list[str] = field(default_factory=list)
    valid_entries: dict[str, str] = field(default_factory=dict)
    special_entries: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert report to dictionary."""
        return {
            "orphaned_count": len(self.orphaned_entries),
            "missing_count": len(self.missing_entries),
            "valid_count": len(self.valid_entries),
            "special_count": len(self.special_entries),
            "orphaned_entries": self.orphaned_entries.copy(),
            "missing_entries": self.missing_entries.copy(),
            "valid_entries": self.valid_entries.copy(),
            "special_entries": self.special_entries.copy(),
        }

    def summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            "Registry Sync Report",
            "=" * 40,
            f"Valid entries: {len(self.valid_entries)}",
            f"Special entries: {len(self.special_entries)}",
            f"Orphaned entries: {len(self.orphaned_entries)}",
            f"Missing entries: {len(self.missing_entries)}",
        ]

        if self.orphaned_entries:
            lines.append("\nOrphaned (destinations not in taxonomy):")
            for source, dest in sorted(self.orphaned_entries.items())[:10]:
                lines.append(f"  {source} -> {dest}")
            if len(self.orphaned_entries) > 10:
                lines.append(f"  ... and {len(self.orphaned_entries) - 10} more")

        if self.missing_entries:
            lines.append("\nMissing (taxonomy paths without registry entries):")
            for path in sorted(self.missing_entries)[:10]:
                lines.append(f"  {path}")
            if len(self.missing_entries) > 10:
                lines.append(f"  ... and {len(self.missing_entries) - 10} more")

        return "\n".join(lines)


def load_taxonomy_paths(taxonomy_path: str | Path) -> set[str]:
    """Load all valid paths from taxonomy file.

    Extracts canonical_roots, family_members paths, finance_subcategories paths,
    and any paths defined in rules.

    Args:
        taxonomy_path: Path to ROOT_TAXONOMY.json file.

    Returns:
        Set of valid taxonomy paths (e.g., "Family Bin", "Family Bin/Camila").

    Raises:
        FileNotFoundError: If the taxonomy file doesn't exist.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    with open(taxonomy_path) as f:
        data = json.load(f)

    paths: set[str] = set()

    # Add canonical roots (top-level bins)
    for root in data.get("canonical_roots", []):
        paths.add(root)

    # Add family member paths
    for member, path in data.get("family_members", {}).items():
        paths.add(path)
        # Also add the bin portion (e.g., "Family Bin" from "Family Bin/Camila")
        if "/" in path:
            paths.add(path.split("/")[0])

    # Add finance subcategory paths
    for subcat, path in data.get("finance_subcategories", {}).items():
        paths.add(path)
        # Also add the bin portion
        if "/" in path:
            paths.add(path.split("/")[0])

    # Add rule destinations
    for rule_name, dest in data.get("rules", {}).items():
        paths.add(dest)
        # Also add parent portions for nested paths
        parts = dest.split("/")
        for i in range(1, len(parts)):
            paths.add("/".join(parts[:i]))

    return paths


def load_registry_mappings(
    registry_path: str | Path,
) -> tuple[dict[str, str], dict[str, Any]]:
    """Load mappings from canonical registry file.

    Args:
        registry_path: Path to canonical_registry.json file.

    Returns:
        Tuple of (mappings dict, full registry data dict).

    Raises:
        FileNotFoundError: If the registry file doesn't exist.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    with open(registry_path) as f:
        data = json.load(f)

    mappings = data.get("mappings", {})
    return mappings, data


def check_registry_against_taxonomy(
    registry_path: str | Path,
    taxonomy_path: str | Path,
) -> SyncReport:
    """Check registry entries against taxonomy without making changes.

    This is a read-only operation that produces a report of what's valid,
    orphaned, or missing without modifying any files.

    Args:
        registry_path: Path to canonical_registry.json file.
        taxonomy_path: Path to ROOT_TAXONOMY.json file.

    Returns:
        SyncReport with validation results.
    """
    report = SyncReport()

    # Load taxonomy paths
    valid_taxonomy_paths = load_taxonomy_paths(taxonomy_path)

    # Load registry mappings
    mappings, _ = load_registry_mappings(registry_path)

    # Track which taxonomy paths have registry entries
    covered_taxonomy_paths: set[str] = set()

    # Check each registry entry
    for source, destination in mappings.items():
        # Handle special entries
        if destination.startswith("__") and destination.endswith("__"):
            report.special_entries[source] = destination
            continue

        # Extract the root bin from the destination
        dest_root = destination.split("/")[0]

        # Check if destination is a valid taxonomy path or under a valid path
        is_valid = False

        # Check exact match
        if destination in valid_taxonomy_paths:
            is_valid = True
        # Check if it's under a valid root bin
        elif dest_root in valid_taxonomy_paths:
            is_valid = True

        if is_valid:
            report.valid_entries[source] = destination
            # Track the root bin as covered
            covered_taxonomy_paths.add(dest_root)
            # Also track the full path if it's in taxonomy
            if destination in valid_taxonomy_paths:
                covered_taxonomy_paths.add(destination)
        else:
            report.orphaned_entries[source] = destination

    # Find taxonomy paths without registry entries
    # Only report root bins and direct subcategories as missing
    for tax_path in valid_taxonomy_paths:
        # Skip paths that are covered
        if tax_path in covered_taxonomy_paths:
            continue

        # Check if any mapping points to this path or under it
        has_entry = False
        for dest in mappings.values():
            if dest == tax_path or dest.startswith(f"{tax_path}/"):
                has_entry = True
                break

        if not has_entry:
            # Only report as missing if it's a meaningful path
            # (root bin or direct subcategory)
            depth = tax_path.count("/")
            if depth <= 1:  # Root bin or one level deep
                report.missing_entries.append(tax_path)

    return report


def resync_registry_with_taxonomy(
    registry_path: str | Path,
    taxonomy_path: str | Path,
    remove_orphans: bool = False,
    add_missing: bool = False,
    dry_run: bool = True,
) -> SyncReport:
    """Resync canonical registry with taxonomy.

    Cross-checks registry against taxonomy and optionally fixes issues.

    Args:
        registry_path: Path to canonical_registry.json file.
        taxonomy_path: Path to ROOT_TAXONOMY.json file.
        remove_orphans: If True, remove orphaned entries from registry.
        add_missing: If True, add placeholder entries for missing taxonomy paths.
        dry_run: If True, don't write changes (just report what would happen).

    Returns:
        SyncReport with validation results and actions taken.
    """
    # First, get the current state
    report = check_registry_against_taxonomy(registry_path, taxonomy_path)

    # If dry_run or no changes requested, return report as-is
    if dry_run or (not remove_orphans and not add_missing):
        return report

    # Load the full registry for modification
    mappings, full_data = load_registry_mappings(registry_path)

    # Remove orphaned entries if requested
    if remove_orphans and report.orphaned_entries:
        for source in report.orphaned_entries:
            if source in mappings:
                del mappings[source]

    # Add missing entries if requested
    if add_missing and report.missing_entries:
        for tax_path in report.missing_entries:
            # Create a placeholder mapping
            # Use the path itself as both source and destination
            path_name = tax_path.split("/")[-1] if "/" in tax_path else tax_path
            if path_name not in mappings:
                mappings[path_name] = tax_path

    # Update the registry data
    full_data["mappings"] = mappings
    full_data["_total_mappings"] = len(mappings)

    # Write back to file
    registry_path = Path(registry_path)
    with open(registry_path, "w") as f:
        json.dump(full_data, f, indent=2)

    # Re-check to get updated report
    return check_registry_against_taxonomy(registry_path, taxonomy_path)


def get_valid_bins_from_taxonomy(taxonomy_path: str | Path) -> list[str]:
    """Get list of valid root bins from taxonomy.

    Args:
        taxonomy_path: Path to ROOT_TAXONOMY.json file.

    Returns:
        List of root bin names.
    """
    with open(taxonomy_path) as f:
        data = json.load(f)

    return data.get("canonical_roots", [])


def get_subcategories_from_taxonomy(taxonomy_path: str | Path) -> dict[str, list[str]]:
    """Get subcategories organized by parent bin.

    Args:
        taxonomy_path: Path to ROOT_TAXONOMY.json file.

    Returns:
        Dict mapping bin names to lists of subcategory paths.
    """
    with open(taxonomy_path) as f:
        data = json.load(f)

    result: dict[str, list[str]] = {}

    # Family members
    for member, path in data.get("family_members", {}).items():
        if "/" in path:
            bin_name = path.split("/")[0]
            if bin_name not in result:
                result[bin_name] = []
            result[bin_name].append(path)

    # Finance subcategories
    for subcat, path in data.get("finance_subcategories", {}).items():
        if "/" in path:
            bin_name = path.split("/")[0]
            if bin_name not in result:
                result[bin_name] = []
            result[bin_name].append(path)

    # Rule destinations with subcategories
    for rule_name, dest in data.get("rules", {}).items():
        if "/" in dest:
            bin_name = dest.split("/")[0]
            if bin_name not in result:
                result[bin_name] = []
            if dest not in result[bin_name]:
                result[bin_name].append(dest)

    return result


def is_valid_registry_destination(
    destination: str,
    taxonomy_path: str | Path,
) -> bool:
    """Check if a registry destination is valid according to taxonomy.

    A destination is valid if:
    - It matches a canonical root
    - It's under a canonical root (even if the full path isn't explicit)
    - It's a special entry (__KEEP_AT_ROOT__, etc.)

    Args:
        destination: The destination path to check.
        taxonomy_path: Path to ROOT_TAXONOMY.json file.

    Returns:
        True if destination is valid, False otherwise.
    """
    # Special entries are always valid
    if destination.startswith("__") and destination.endswith("__"):
        return True

    valid_paths = load_taxonomy_paths(taxonomy_path)

    # Exact match
    if destination in valid_paths:
        return True

    # Check if under a valid root bin
    if "/" in destination:
        root = destination.split("/")[0]
        return root in valid_paths

    return False
