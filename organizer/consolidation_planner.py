"""Consolidation planner module for scanning and grouping similar folders.

This module provides functionality to scan an existing folder structure,
identify groups of similar folders that should be merged, and generate
a consolidation plan for review before execution.

Phase 2 enhancements add content-aware consolidation decisions using:
- AI categories from database analysis
- Date ranges from key_dates and metadata
- Entities (people, organizations) from entities JSONB
- Original paths from document_locations
- Context bins from folder_hierarchy

Content-aware mode queries the database for existing document analysis
and makes intelligent decisions about whether folders should consolidate.
"""

import json
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

from organizer.canonical_registry import CanonicalRegistry
from organizer.category_mapper import (
    get_category_for_folder_name,
    get_canonical_folder_for_category,
    get_parent_folder_for_category,
)
from organizer.content_analyzer import (
    FolderAnalysis,
    analyze_folder_content,
    analyze_folder_with_processing,
    create_document_processor,
    should_consolidate_folders,
)
from organizer.database_updater import get_database_connection
from organizer.fuzzy_matcher import are_similar_folders

if TYPE_CHECKING:
    from organizer.structure_analyzer import StructureSnapshot


@dataclass
class FolderInfo:
    """Information about a folder in the filesystem."""

    path: str
    name: str
    file_count: int = 0
    total_size: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "path": self.path,
            "name": self.name,
            "file_count": self.file_count,
            "total_size": self.total_size,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FolderInfo":
        """Create from dictionary."""
        return cls(
            path=data["path"],
            name=data["name"],
            file_count=data.get("file_count", 0),
            total_size=data.get("total_size", 0),
        )


@dataclass
class FolderContentSummary:
    """Summary of content analysis for a single folder.

    Used to display per-folder content details in plan output.
    """

    folder_path: str
    ai_categories: set[str] = field(default_factory=set)
    context_bins: set[str] = field(default_factory=set)
    year_clusters: list[str] = field(default_factory=list)
    document_count: int = 0

    def __post_init__(self) -> None:
        """Ensure ai_categories and context_bins are sets."""
        if isinstance(self.ai_categories, (list, frozenset)):
            self.ai_categories = set(self.ai_categories)
        if isinstance(self.context_bins, (list, frozenset)):
            self.context_bins = set(self.context_bins)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "folder_path": self.folder_path,
            "ai_categories": list(self.ai_categories),
            "context_bins": list(self.context_bins),
            "year_clusters": self.year_clusters,
            "document_count": self.document_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FolderContentSummary":
        """Create from dictionary."""
        return cls(
            folder_path=data.get("folder_path", ""),
            ai_categories=set(data.get("ai_categories", [])),
            context_bins=set(data.get("context_bins", [])),
            year_clusters=data.get("year_clusters", []),
            document_count=data.get("document_count", 0),
        )


@dataclass
class FolderGroup:
    """A group of similar folders that should be consolidated.

    Phase 2 adds content-aware fields:
    - should_consolidate: Final decision based on content analysis
    - consolidation_reasoning: List of reasons for the decision
    - decision_summary: Concise one-line summary of the decision reason (Phase 5)
    - ai_categories: Set of AI categories found in the folders
    - date_ranges: Year clusters for each folder
    - content_analysis_done: Whether content analysis was performed
    - folder_content_summaries: Per-folder content analysis details (Phase 5)
    """

    group_name: str
    category_key: Optional[str]
    folders: list[FolderInfo] = field(default_factory=list)
    target_folder: str = ""
    total_files: int = 0
    total_size: int = 0
    # Content-aware fields (Phase 2)
    should_consolidate: bool = True  # Default True for backward compatibility
    consolidation_reasoning: list[str] = field(default_factory=list)
    decision_summary: str = ""  # Concise reason for the decision (Phase 5)
    ai_categories: set[str] = field(default_factory=set)
    date_ranges: dict[str, str] = field(
        default_factory=dict
    )  # folder_path -> year_cluster
    content_analysis_done: bool = False
    confidence: float = 1.0  # Confidence in consolidation decision
    # Per-folder content summaries (Phase 5)
    folder_content_summaries: dict[str, FolderContentSummary] = field(
        default_factory=dict
    )  # folder_path -> summary

    def __post_init__(self) -> None:
        """Calculate totals after initialization."""
        self._recalculate_totals()
        # Ensure ai_categories is a set
        if isinstance(self.ai_categories, (list, frozenset)):
            self.ai_categories = set(self.ai_categories)

    def _recalculate_totals(self) -> None:
        """Recalculate total files and size from folders."""
        self.total_files = sum(f.file_count for f in self.folders)
        self.total_size = sum(f.total_size for f in self.folders)

    def add_folder(self, folder: FolderInfo) -> None:
        """Add a folder to this group."""
        self.folders.append(folder)
        self._recalculate_totals()

    def add_reasoning(self, reason: str) -> None:
        """Add a reasoning line for the consolidation decision."""
        self.consolidation_reasoning.append(reason)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "group_name": self.group_name,
            "category_key": self.category_key,
            "folders": [f.to_dict() for f in self.folders],
            "target_folder": self.target_folder,
            "total_files": self.total_files,
            "total_size": self.total_size,
            "should_consolidate": self.should_consolidate,
            "consolidation_reasoning": self.consolidation_reasoning,
            "decision_summary": self.decision_summary,
            "ai_categories": list(self.ai_categories),
            "date_ranges": self.date_ranges,
            "content_analysis_done": self.content_analysis_done,
            "confidence": self.confidence,
            "folder_content_summaries": {
                k: v.to_dict() for k, v in self.folder_content_summaries.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FolderGroup":
        """Create from dictionary."""
        group = cls(
            group_name=data["group_name"],
            category_key=data.get("category_key"),
            target_folder=data.get("target_folder", ""),
            should_consolidate=data.get("should_consolidate", True),
            consolidation_reasoning=data.get("consolidation_reasoning", []),
            decision_summary=data.get("decision_summary", ""),
            ai_categories=set(data.get("ai_categories", [])),
            date_ranges=data.get("date_ranges", {}),
            content_analysis_done=data.get("content_analysis_done", False),
            confidence=data.get("confidence", 1.0),
            folder_content_summaries={
                k: FolderContentSummary.from_dict(v)
                for k, v in data.get("folder_content_summaries", {}).items()
            },
        )
        group.folders = [FolderInfo.from_dict(f) for f in data.get("folders", [])]
        group._recalculate_totals()
        return group


@dataclass
class ConsolidationPlan:
    """A complete plan for folder consolidation.

    Phase 2 adds content-aware mode which uses database analysis to make
    intelligent consolidation decisions based on AI categories, dates,
    entities, and path contexts.
    """

    created_at: str = ""
    base_path: str = ""
    threshold: float = 0.8
    groups: list[FolderGroup] = field(default_factory=list)
    # Content-aware fields (Phase 2)
    content_aware: bool = False
    db_path: str = ""

    def __post_init__(self) -> None:
        """Set creation timestamp if not provided."""
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    @property
    def total_groups(self) -> int:
        """Return the number of folder groups."""
        return len(self.groups)

    @property
    def total_folders(self) -> int:
        """Return the total number of folders across all groups."""
        return sum(len(g.folders) for g in self.groups)

    @property
    def total_files(self) -> int:
        """Return the total number of files across all groups."""
        return sum(g.total_files for g in self.groups)

    @property
    def groups_to_consolidate(self) -> list[FolderGroup]:
        """Return groups that should be consolidated (content-aware mode)."""
        return [g for g in self.groups if g.should_consolidate]

    @property
    def groups_to_skip(self) -> list[FolderGroup]:
        """Return groups that should NOT be consolidated (content-aware mode)."""
        return [g for g in self.groups if not g.should_consolidate]

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "created_at": self.created_at,
            "base_path": self.base_path,
            "threshold": self.threshold,
            "content_aware": self.content_aware,
            "db_path": self.db_path,
            "groups": [g.to_dict() for g in self.groups],
            "summary": {
                "total_groups": self.total_groups,
                "total_folders": self.total_folders,
                "total_files": self.total_files,
                "groups_to_consolidate": len(self.groups_to_consolidate),
                "groups_to_skip": len(self.groups_to_skip),
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ConsolidationPlan":
        """Create from dictionary."""
        plan = cls(
            created_at=data.get("created_at", ""),
            base_path=data.get("base_path", ""),
            threshold=data.get("threshold", 0.8),
            content_aware=data.get("content_aware", False),
            db_path=data.get("db_path", ""),
        )
        plan.groups = [FolderGroup.from_dict(g) for g in data.get("groups", [])]
        return plan

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> "ConsolidationPlan":
        """Create from JSON string."""
        return cls.from_dict(json.loads(json_str))

    def save(self, path: str | Path) -> None:
        """Save plan to a JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())

    @classmethod
    def load(cls, path: str | Path) -> "ConsolidationPlan":
        """Load plan from a JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_json(f.read())


class ConsolidationPlanner:
    """Scans folder structure and generates consolidation plans.

    The planner analyzes a directory tree, identifies groups of similar folders,
    and suggests how they should be consolidated based on fuzzy matching and
    category mappings.

    Phase 2 adds content-aware consolidation which uses database analysis to
    make intelligent decisions about whether folders should consolidate based on:
    - AI categories from database
    - Date ranges from key_dates and metadata
    - Entities (people, organizations)
    - Original paths and context bins
    """

    def __init__(
        self,
        base_path: str = "",
        threshold: float = 0.8,
        db_path: str = "",
        content_aware: bool = False,
        content_similarity_threshold: float = 0.6,
        analyze_missing: bool = False,
        learned_structure_path: str = "",
        respect_learned_hierarchy: bool = True,
    ):
        """Initialize the planner.

        Args:
            base_path: The root path to scan. If empty, uses current directory.
            threshold: Similarity threshold for folder name matching (0.0 to 1.0).
            db_path: Path to SQLite database for content-aware analysis.
            content_aware: If True, use content analysis to make consolidation decisions.
            content_similarity_threshold: Minimum confidence (0.0-1.0) required for
                content-based consolidation decisions. Default is 0.6 (60%).
                Higher values require more matching rules to approve consolidation.
            analyze_missing: If True and content_aware is enabled, analyze files that
                are not in the database using the DocumentProcessor. This allows for
                content-aware decisions even for folders not yet fully processed.
            learned_structure_path: Path to learned_structure.json. If provided,
                respects learned hierarchy when making consolidation decisions.
            respect_learned_hierarchy: If True (default), never merge folders that
                the learned structure snapshot says are separate. Prevents reshuffling
                user's intentional organization.
        """
        self.base_path = base_path or os.getcwd()
        self.threshold = threshold
        self.db_path = db_path
        self.content_aware = content_aware
        self.content_similarity_threshold = content_similarity_threshold
        self.analyze_missing = analyze_missing
        self._db_conn: Optional[sqlite3.Connection] = None
        self._learned_structure_path = (
            learned_structure_path
            if learned_structure_path
            else os.path.join(base_path or os.getcwd(), ".organizer", "agent", "learned_structure.json")
        )
        self._respect_learned_hierarchy = respect_learned_hierarchy
        self._learned_structure: Optional["StructureSnapshot"] = None

    def _get_db_connection(self) -> Optional[sqlite3.Connection]:
        """Get database connection for content-aware analysis."""
        if not self.db_path:
            return None
        if self._db_conn is None:
            try:
                self._db_conn = get_database_connection(self.db_path)
            except (FileNotFoundError, sqlite3.Error):
                self._db_conn = None
        return self._db_conn

    def _close_db_connection(self) -> None:
        """Close database connection if open."""
        if self._db_conn is not None:
            self._db_conn.close()
            self._db_conn = None

    def _get_learned_structure(self) -> Optional["StructureSnapshot"]:
        """Load learned structure snapshot if available.

        Returns:
            StructureSnapshot if file exists and is valid, None otherwise.
        """
        if self._learned_structure is not None:
            return self._learned_structure

        if not self._respect_learned_hierarchy:
            return None

        try:
            from organizer.structure_analyzer import StructureSnapshot
            self._learned_structure = StructureSnapshot.load(self._learned_structure_path)
            return self._learned_structure
        except (FileNotFoundError, json.JSONDecodeError, ImportError):
            return None

    def _are_folders_separate_in_learned_structure(
        self, folder_path1: str, folder_path2: str
    ) -> bool:
        """Check if two folders are intentionally separate in the learned structure.

        The learned structure represents the user's existing organizational strategy.
        If two folders exist at the same depth level with different parents, or
        are both recorded separately in the snapshot, they should NOT be merged.

        Args:
            folder_path1: Path to first folder.
            folder_path2: Path to second folder.

        Returns:
            True if folders should be kept separate (don't consolidate).
        """
        learned = self._get_learned_structure()
        if learned is None:
            return False  # No learned structure, allow consolidation

        # Check if both folders exist in the learned structure
        folder_paths_in_structure = {f.path for f in learned.folders}
        folder_names_in_structure = {f.name: f for f in learned.folders}

        path1_abs = os.path.abspath(folder_path1)
        path2_abs = os.path.abspath(folder_path2)
        name1 = os.path.basename(folder_path1)
        name2 = os.path.basename(folder_path2)

        # If both exact paths are in the learned structure, check their depths/parents
        if path1_abs in folder_paths_in_structure and path2_abs in folder_paths_in_structure:
            # Both folders were explicitly captured in the learned structure
            # They exist separately, so respect that separation
            return True

        # Check by folder name if paths don't match exactly
        # (paths may have changed since structure was learned)
        node1 = folder_names_in_structure.get(name1)
        node2 = folder_names_in_structure.get(name2)

        if node1 is not None and node2 is not None:
            # Both folder names exist in learned structure
            # If they're at the same depth but different paths, they're intentionally separate
            if node1.depth == node2.depth and node1.path != node2.path:
                return True

        return False

    def scan_folders(
        self, path: Optional[str] = None, max_depth: int = 3
    ) -> list[FolderInfo]:
        """Scan directory structure and collect folder information.

        Args:
            path: Path to scan. If None, uses base_path.
            max_depth: Maximum depth to scan into subdirectories.

        Returns:
            List of FolderInfo objects for all discovered folders.
        """
        scan_path = path or self.base_path
        folders: list[FolderInfo] = []

        self._scan_recursive(scan_path, folders, current_depth=0, max_depth=max_depth)

        return folders

    def _scan_recursive(
        self,
        path: str,
        folders: list[FolderInfo],
        current_depth: int,
        max_depth: int,
    ) -> None:
        """Recursively scan directories.

        Args:
            path: Current path to scan.
            folders: List to append found folders to.
            current_depth: Current recursion depth.
            max_depth: Maximum depth to scan.
        """
        if current_depth > max_depth:
            return

        try:
            entries = os.listdir(path)
        except (PermissionError, OSError):
            return

        for entry in entries:
            entry_path = os.path.join(path, entry)

            if not os.path.isdir(entry_path):
                continue

            # Skip hidden directories
            if entry.startswith("."):
                continue

            # Get folder stats
            file_count, total_size = self._get_folder_stats(entry_path)

            folders.append(
                FolderInfo(
                    path=entry_path,
                    name=entry,
                    file_count=file_count,
                    total_size=total_size,
                )
            )

            # Recurse into subdirectory
            self._scan_recursive(entry_path, folders, current_depth + 1, max_depth)

    def _get_folder_stats(self, path: str) -> tuple[int, int]:
        """Get file count and total size for a folder (non-recursive).

        Args:
            path: Folder path to analyze.

        Returns:
            Tuple of (file_count, total_size_bytes).
        """
        file_count = 0
        total_size = 0

        try:
            for entry in os.listdir(path):
                entry_path = os.path.join(path, entry)
                if os.path.isfile(entry_path):
                    file_count += 1
                    try:
                        total_size += os.path.getsize(entry_path)
                    except OSError:
                        pass
        except (PermissionError, OSError):
            pass

        return file_count, total_size

    def group_similar_folders(self, folders: list[FolderInfo]) -> list[FolderGroup]:
        """Group similar folders together based on fuzzy matching.

        Respects learned hierarchy by not grouping folders that the learned
        structure snapshot indicates should be kept separate.

        Args:
            folders: List of FolderInfo objects to analyze.

        Returns:
            List of FolderGroup objects, each containing similar folders.
        """
        groups: list[FolderGroup] = []
        assigned: set[str] = set()

        for folder in folders:
            if folder.path in assigned:
                continue

            # Find all similar folders
            similar: list[FolderInfo] = [folder]
            assigned.add(folder.path)

            for other in folders:
                if other.path in assigned:
                    continue

                if are_similar_folders(
                    folder.name, other.name, threshold=self.threshold
                ):
                    # Check if learned structure says these should be separate
                    if self._are_folders_separate_in_learned_structure(
                        folder.path, other.path
                    ):
                        # Learned structure says keep separate - skip this pair
                        continue

                    similar.append(other)
                    assigned.add(other.path)

            # Only create a group if there are multiple similar folders
            if len(similar) > 1:
                # Determine category and target
                category_key = get_category_for_folder_name(
                    folder.name, threshold=self.threshold
                )
                group_name = self._generate_group_name(folder.name, category_key)
                target = self._determine_target_folder(category_key, folder.name)

                group = FolderGroup(
                    group_name=group_name,
                    category_key=category_key,
                    target_folder=target,
                )
                for f in similar:
                    group.add_folder(f)

                groups.append(group)

        return groups

    def _analyze_group_content(
        self, group: FolderGroup, conn: sqlite3.Connection
    ) -> FolderGroup:
        """Analyze content of folders in a group and make consolidation decision.

        This method implements the intelligent decision engine (Phase 2):
        1. Query database for all files in both folders
        2. Extract AI categories from ai_category field
        3. Extract date ranges from key_dates[] and metadata dates
        4. Extract entities from entities JSONB (people, organizations)
        5. Extract original paths from document_locations table
        6. Extract context bins from folder_hierarchy array

        Then applies decision rules:
        1. ✅ Same AI category?
        2. ✅ Same date range?
        3. ✅ Same context bin?
        4. ✅ Same entities?
        5. ✅ Compatible original paths?

        Only consolidate if ALL rules pass.

        Args:
            group: The FolderGroup to analyze.
            conn: Database connection for content analysis.

        Returns:
            The same FolderGroup with content analysis results populated.
        """
        group.content_analysis_done = True

        if len(group.folders) < 2:
            group.add_reasoning("Only one folder in group - no comparison needed")
            group.should_consolidate = True
            return group

        # Step 1-6: Gather ALL context from database for each folder
        folder_analyses: dict[str, FolderAnalysis] = {}
        all_entities: dict[str, set[str]] = {}  # Aggregated entities across all folders
        all_context_bins: set[str] = set()
        all_original_paths: set[str] = set()

        # Create processor for analyzing missing files if enabled
        processor = create_document_processor() if self.analyze_missing else None

        if self.analyze_missing:
            group.add_reasoning(
                "Gathering context from database (analyzing missing files):"
            )
        else:
            group.add_reasoning("Gathering context from database:")

        for folder in group.folders:
            # Use analyze_folder_with_processing if analyze_missing is enabled
            if self.analyze_missing and processor:
                analysis = analyze_folder_with_processing(
                    conn,
                    folder.path,
                    processor=processor,
                    analyze_missing=True,
                )
            else:
                analysis = analyze_folder_content(conn, folder.path)
            folder_analyses[folder.path] = analysis
            folder_name = os.path.basename(folder.path)

            # Log what we found
            group.add_reasoning(f"  {folder_name}: {analysis.document_count} documents")

            # Collect AI categories
            for cat in analysis.ai_categories:
                group.ai_categories.add(cat)
            if analysis.ai_categories:
                group.add_reasoning(
                    f"    AI categories: {', '.join(sorted(analysis.ai_categories))}"
                )

            # Record year clusters
            if analysis.year_clusters:
                group.date_ranges[folder.path] = ", ".join(analysis.year_clusters)
                group.add_reasoning(
                    f"    Date ranges: {', '.join(analysis.year_clusters)}"
                )

            # Collect entities
            for entity_type, values in analysis.entities.items():
                if entity_type not in all_entities:
                    all_entities[entity_type] = set()
                all_entities[entity_type].update(values)
            if analysis.entities:
                entity_summary = ", ".join(
                    f"{k}: {len(v)}" for k, v in analysis.entities.items()
                )
                group.add_reasoning(f"    Entities: {entity_summary}")

            # Collect context bins
            all_context_bins.update(analysis.context_bins)
            if analysis.context_bins:
                group.add_reasoning(
                    f"    Context bins: {', '.join(sorted(analysis.context_bins))}"
                )

            # Collect original paths
            all_original_paths.update(analysis.original_paths)
            if analysis.original_paths:
                group.add_reasoning(
                    f"    Original paths: {len(analysis.original_paths)} tracked"
                )

            # Store per-folder content summary for display in plan output (Phase 5)
            group.folder_content_summaries[folder.path] = FolderContentSummary(
                folder_path=folder.path,
                ai_categories=set(analysis.ai_categories),
                context_bins=set(analysis.context_bins),
                year_clusters=list(analysis.year_clusters),
                document_count=analysis.document_count,
            )

        # Check if we have any data to analyze
        total_docs = sum(a.document_count for a in folder_analyses.values())
        if total_docs == 0:
            group.add_reasoning("")
            group.add_reasoning("⚠️ No documents found in database for these folders")
            group.add_reasoning("Falling back to name-based similarity only")
            group.should_consolidate = True
            group.confidence = 0.5
            return group

        group.add_reasoning("")
        group.add_reasoning("Applying decision rules:")

        # Pairwise comparison of folders for consolidation decision
        all_should_consolidate = True
        folder_paths = list(folder_analyses.keys())

        # Track which rules passed/failed across all comparisons for the summary
        all_categories_match = True
        all_dates_match = True
        all_contexts_match = True
        all_entities_match = True
        all_paths_compatible = True
        blocking_reasons: list[str] = []  # Reasons that blocked consolidation

        for i in range(len(folder_paths)):
            for j in range(i + 1, len(folder_paths)):
                path1, path2 = folder_paths[i], folder_paths[j]
                decision = should_consolidate_folders(
                    conn, path1, path2, self.content_similarity_threshold
                )

                # Add decision reasoning to group
                folder1_name = os.path.basename(path1)
                folder2_name = os.path.basename(path2)
                group.add_reasoning(
                    f"  Comparing '{folder1_name}' vs '{folder2_name}':"
                )

                # Show rule results and track for summary
                if decision.matching_categories:
                    group.add_reasoning("    Rule 1: ✅ Same AI category")
                else:
                    group.add_reasoning("    Rule 1: ❌ Different AI categories")
                    all_categories_match = False

                if decision.matching_date_range:
                    group.add_reasoning("    Rule 2: ✅ Same date range")
                else:
                    group.add_reasoning("    Rule 2: ❌ Different date ranges")
                    all_dates_match = False

                if decision.matching_context:
                    group.add_reasoning("    Rule 3: ✅ Same context bin")
                else:
                    group.add_reasoning("    Rule 3: ⚠️ Different/no context bins")
                    all_contexts_match = False

                if decision.matching_entities:
                    group.add_reasoning("    Rule 4: ✅ Same entities")
                else:
                    group.add_reasoning("    Rule 4: ⚠️ Different/no entities")
                    all_entities_match = False

                if decision.compatible_paths:
                    group.add_reasoning("    Rule 5: ✅ Compatible original paths")
                else:
                    group.add_reasoning("    Rule 5: ❌ Incompatible paths")
                    all_paths_compatible = False

                # Add any additional reasoning from the decision
                for reason in decision.reasoning:
                    if reason.startswith("⛔") or reason.startswith("✅ CONSOLIDATE"):
                        group.add_reasoning(f"    → {reason}")

                # Collect blocking reasons for summary
                if not decision.should_consolidate:
                    all_should_consolidate = False
                    # Extract specific blocking reasons from the decision
                    for reason in decision.reasoning:
                        if "Different timeframes" in reason:
                            # Extract the timeframe info
                            blocking_reasons.append(
                                f"Different timeframes ({folder1_name} vs {folder2_name})"
                            )
                        elif "Different AI categories" in reason:
                            blocking_reasons.append(
                                f"Different AI categories ({folder1_name} vs {folder2_name})"
                            )
                        elif (
                            "Incompatible paths" in reason
                            or "Desktop contexts" in reason
                        ):
                            blocking_reasons.append(
                                f"Different path contexts ({folder1_name} vs {folder2_name})"
                            )

                # Track minimum confidence
                group.confidence = min(group.confidence, decision.confidence)

        group.add_reasoning("")

        # Final decision
        group.should_consolidate = all_should_consolidate

        # Generate concise decision summary for display (Phase 5)
        if group.should_consolidate:
            # Build summary of what matched
            matching_parts = []
            if all_categories_match and group.ai_categories:
                matching_parts.append("Same AI category")
            if all_dates_match:
                matching_parts.append("same date range")
            if all_contexts_match:
                matching_parts.append("same context bin")
            if all_entities_match:
                matching_parts.append("same entities")
            if all_paths_compatible:
                matching_parts.append("compatible paths")

            if matching_parts:
                # Capitalize first part
                matching_parts[0] = matching_parts[0][0].upper() + matching_parts[0][1:]
                group.decision_summary = ", ".join(matching_parts)
            else:
                group.decision_summary = "All compatibility checks passed"

            group.add_reasoning(
                "✅ DECISION: CAN CONSOLIDATE - All folder pairs are compatible"
            )
            # Determine target folder using canonical registry
            self._determine_canonical_target(group)
        else:
            # Build summary from blocking reasons
            if blocking_reasons:
                # Use the first blocking reason as the primary summary
                group.decision_summary = blocking_reasons[0]
            elif not all_dates_match:
                group.decision_summary = "Different timeframes"
            elif not all_categories_match:
                group.decision_summary = "Different AI categories"
            elif not all_paths_compatible:
                group.decision_summary = "Different path contexts"
            else:
                group.decision_summary = "Incompatible content"

            group.add_reasoning(
                "❌ DECISION: DO NOT CONSOLIDATE - Incompatible content found"
            )
            group.add_reasoning("Keep folders separate")

        return group

    def _determine_canonical_target(self, group: FolderGroup) -> None:
        """Determine the canonical target folder using registry and category mappings.

        Uses the CanonicalRegistry to check for existing similar folders,
        and category mappings to suggest the appropriate location.

        Args:
            group: The FolderGroup to determine target for.
        """
        # Use category mapper if we have a category
        if group.category_key:
            parent = get_parent_folder_for_category(group.category_key)
            canonical = get_canonical_folder_for_category(group.category_key)
            if parent and canonical:
                group.target_folder = os.path.join(parent, canonical)
                group.add_reasoning(
                    f"Target folder (from category): {group.target_folder}/"
                )
                return

        # Use AI categories if available
        if group.ai_categories:
            # Use the most common AI category
            primary_category = sorted(group.ai_categories)[0]
            group.target_folder = primary_category.replace("/", os.sep)
            group.add_reasoning(
                f"Target folder (from AI category): {group.target_folder}/"
            )
            return

        # Fallback to canonical registry lookup
        if self.base_path:
            registry_path = (
                Path(self.base_path) / ".organizer" / "canonical_folders.json"
            )
            registry = CanonicalRegistry(storage_path=registry_path)

            # Check if any folder in the group matches a canonical folder
            for folder in group.folders:
                existing = registry.get_canonical_folder(folder.name)
                if existing:
                    group.target_folder = existing.path
                    group.add_reasoning(
                        f"Target folder (from registry): {group.target_folder}/"
                    )
                    return

        # Final fallback: use the first folder's name
        if group.folders:
            group.target_folder = group.folders[0].name
            group.add_reasoning(
                f"Target folder (from first folder): {group.target_folder}/"
            )

    def group_similar_folders_content_aware(
        self,
        folders: list[FolderInfo],
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> list[FolderGroup]:
        """Group similar folders with content-aware analysis.

        This method first groups folders by name similarity, then analyzes
        the content of each group using database information to make
        intelligent consolidation decisions.

        Args:
            folders: List of FolderInfo objects to analyze.
            progress_callback: Optional callback(current, total, message) for progress.

        Returns:
            List of FolderGroup objects with content analysis results.
        """
        # First, do name-based grouping
        groups = self.group_similar_folders(folders)

        # If not content-aware or no database, return name-based groups
        conn = self._get_db_connection()
        if not self.content_aware or conn is None:
            return groups

        # Analyze content of each group
        total_groups = len(groups)
        for i, group in enumerate(groups):
            if progress_callback:
                progress_callback(i + 1, total_groups, f"Analyzing {group.group_name}")
            self._analyze_group_content(group, conn)

        return groups

    def _generate_group_name(
        self, sample_name: str, category_key: Optional[str]
    ) -> str:
        """Generate a descriptive group name.

        Args:
            sample_name: A sample folder name from the group.
            category_key: The category key if determined.

        Returns:
            A human-readable group name like "Resume-related".
        """
        if category_key:
            # Capitalize the category key for display
            return f"{category_key.capitalize()}-related"

        # Use the sample name as basis
        base_name = sample_name.split("_")[0].split("-")[0]
        return f"{base_name}-related"

    def _determine_target_folder(
        self, category_key: Optional[str], fallback_name: str
    ) -> str:
        """Determine the target folder path for consolidation.

        Args:
            category_key: The category key if determined.
            fallback_name: Name to use if no category match.

        Returns:
            The suggested target folder path.
        """
        if category_key:
            parent = get_parent_folder_for_category(category_key)
            canonical = get_canonical_folder_for_category(category_key)
            if parent and canonical:
                return os.path.join(parent, canonical)

        # Fallback to using the first part of the name
        return fallback_name

    def create_plan(
        self,
        path: Optional[str] = None,
        max_depth: int = 3,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> ConsolidationPlan:
        """Create a consolidation plan by scanning and grouping folders.

        Args:
            path: Path to scan. If None, uses base_path.
            max_depth: Maximum depth to scan into subdirectories.
            progress_callback: Optional callback(current, total, message) for progress.

        Returns:
            A ConsolidationPlan with all identified folder groups.
        """
        folders = self.scan_folders(path, max_depth)

        # Use content-aware grouping if enabled
        if self.content_aware:
            groups = self.group_similar_folders_content_aware(
                folders, progress_callback
            )
        else:
            groups = self.group_similar_folders(folders)

        plan = ConsolidationPlan(
            base_path=self.base_path,
            threshold=self.threshold,
            groups=groups,
            content_aware=self.content_aware,
            db_path=self.db_path,
        )

        # Clean up database connection
        self._close_db_connection()

        return plan

    def generate_summary(self, plan: ConsolidationPlan) -> str:
        """Generate a human-readable summary of the consolidation plan.

        Args:
            plan: The consolidation plan to summarize.

        Returns:
            A formatted string summary for display.
        """
        lines: list[str] = []

        if plan.content_aware:
            lines.append("CONTENT-AWARE FOLDER ANALYSIS")
            lines.append("=" * 30)
        else:
            lines.append("FOLDER SIMILARITY ANALYSIS")
            lines.append("=" * 28)
        lines.append("")

        if not plan.groups:
            lines.append("No similar folder groups found.")
            return "\n".join(lines)

        lines.append(f"Found {plan.total_groups} similar folder groups:")
        if plan.content_aware:
            lines.append(
                f"  - Groups to consolidate: {len(plan.groups_to_consolidate)}"
            )
            lines.append(f"  - Groups to skip: {len(plan.groups_to_skip)}")
        lines.append("")

        for i, group in enumerate(plan.groups, 1):
            # Header with consolidation status
            status = ""
            if plan.content_aware and group.content_analysis_done:
                if group.should_consolidate:
                    status = " ✅"
                else:
                    status = " ❌"

            lines.append(
                f"Group {i}: {group.group_name}{status} "
                f"({len(group.folders)} folders, {group.total_files} files)"
            )

            # List folders with content info
            for folder in group.folders:
                file_label = "file" if folder.file_count == 1 else "files"

                # Build per-folder content info using folder_content_summaries (Phase 5)
                if plan.content_aware and folder.path in group.folder_content_summaries:
                    summary = group.folder_content_summaries[folder.path]
                    content_parts = []

                    # Show per-folder AI category
                    if summary.ai_categories:
                        ai_cats = ", ".join(sorted(summary.ai_categories))
                        content_parts.append(f'AI: "{ai_cats}"')

                    # Show per-folder context bin
                    if summary.context_bins:
                        context = ", ".join(sorted(summary.context_bins))
                        content_parts.append(f'Context: "{context}"')

                    # Show per-folder date range
                    if summary.year_clusters:
                        dates = ", ".join(summary.year_clusters)
                        content_parts.append(f'Dates: "{dates}"')

                    if content_parts:
                        folder_info = (
                            f"  - {folder.path} ({folder.file_count} {file_label}, "
                            f"{', '.join(content_parts)})"
                        )
                    else:
                        folder_info = (
                            f"  - {folder.path} ({folder.file_count} {file_label})"
                        )
                else:
                    # Fallback for non-content-aware mode or missing summary
                    folder_info = (
                        f"  - {folder.path} ({folder.file_count} {file_label})"
                    )

                    # Add group-level AI category if available (legacy behavior)
                    if plan.content_aware:
                        extras = []
                        if group.ai_categories:
                            extras.append(
                                f"AI: {', '.join(sorted(group.ai_categories))}"
                            )
                        if folder.path in group.date_ranges:
                            extras.append(f"Dates: {group.date_ranges[folder.path]}")
                        if extras:
                            folder_info += f"\n    ({', '.join(extras)})"

                lines.append(folder_info)

            # Consolidation decision and reasoning
            if plan.content_aware and group.content_analysis_done:
                if group.should_consolidate:
                    # Show decision summary with reason (Phase 5)
                    if group.decision_summary:
                        lines.append(
                            f"  → ✅ CAN CONSOLIDATE: {group.decision_summary}"
                        )
                    else:
                        lines.append(
                            f"  → ✅ CAN CONSOLIDATE: {group.confidence:.0%} confidence"
                        )
                    lines.append(f"  → Suggested canonical: {group.target_folder}/")
                else:
                    # Show decision summary with reason (Phase 5)
                    if group.decision_summary:
                        lines.append(
                            f"  → ❌ DO NOT CONSOLIDATE: {group.decision_summary}"
                        )
                    else:
                        lines.append("  → ❌ DO NOT CONSOLIDATE: Incompatible content")
                    lines.append("  → Keep separate")

                # Show reasoning if content-aware
                if group.consolidation_reasoning:
                    lines.append("  Reasoning:")
                    for reason in group.consolidation_reasoning[-5:]:  # Last 5 reasons
                        lines.append(f"    {reason}")
            else:
                lines.append(f"  -> Suggested canonical: {group.target_folder}/")

            lines.append("")

        if plan.content_aware:
            lines.append(
                "Run with --plan to generate full consolidation plan "
                "(content-aware mode enabled)."
            )
        else:
            lines.append("Run with --plan to generate full consolidation plan.")

        return "\n".join(lines)


def scan_folder_structure(
    base_path: str = "",
    threshold: float = 0.8,
    max_depth: int = 3,
    db_path: str = "",
    content_aware: bool = False,
    content_similarity_threshold: float = 0.6,
    analyze_missing: bool = False,
    learned_structure_path: str = "",
    respect_learned_hierarchy: bool = True,
) -> ConsolidationPlan:
    """Convenience function to scan and create a consolidation plan.

    Args:
        base_path: Root path to scan.
        threshold: Similarity threshold for folder name matching.
        max_depth: Maximum depth to scan.
        db_path: Path to SQLite database for content-aware analysis.
        content_aware: If True, use content analysis for consolidation decisions.
        content_similarity_threshold: Minimum confidence (0.0-1.0) required for
            content-based consolidation decisions. Default is 0.6 (60%).
        analyze_missing: If True and content_aware is enabled, analyze files that
            are not in the database using the DocumentProcessor.
        learned_structure_path: Path to learned_structure.json. If provided,
            respects learned hierarchy when making consolidation decisions.
        respect_learned_hierarchy: If True (default), never merge folders that
            the learned structure snapshot says are separate.

    Returns:
        A ConsolidationPlan with all identified folder groups.
    """
    planner = ConsolidationPlanner(
        base_path=base_path,
        threshold=threshold,
        db_path=db_path,
        content_aware=content_aware,
        content_similarity_threshold=content_similarity_threshold,
        analyze_missing=analyze_missing,
        learned_structure_path=learned_structure_path,
        respect_learned_hierarchy=respect_learned_hierarchy,
    )
    return planner.create_plan(max_depth=max_depth)


def generate_plan_summary(plan: ConsolidationPlan) -> str:
    """Convenience function to generate a summary from a plan.

    Args:
        plan: The consolidation plan to summarize.

    Returns:
        A formatted string summary.
    """
    planner = ConsolidationPlanner()
    return planner.generate_summary(plan)


def load_plan_from_file(path: str | Path) -> ConsolidationPlan:
    """Load a consolidation plan from a JSON file.

    Args:
        path: Path to the JSON plan file.

    Returns:
        The loaded ConsolidationPlan.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    return ConsolidationPlan.load(path)


def save_plan_to_file(plan: ConsolidationPlan, path: str | Path) -> None:
    """Save a consolidation plan to a JSON file.

    Args:
        plan: The plan to save.
        path: Path to save the JSON file to.
    """
    plan.save(path)
