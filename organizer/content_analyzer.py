"""Content-aware folder analysis for intelligent consolidation decisions.

This module provides content analysis functionality to make smart decisions about
whether folders should be consolidated based on their actual content, not just
folder names. It queries the database for existing document analysis and uses
that information to determine consolidation compatibility.

Key capabilities:
- Analyze folder content using existing database analysis
- Compare AI categories, date ranges, entities, and path contexts
- Make intelligent consolidation decisions with clear reasoning
- Scan folders for files not yet in the database
- Integration with DocumentProcessor for analyzing new files
"""

import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Protocol

from organizer.database_updater import get_database_connection


class DatabaseConnection(Protocol):
    """Protocol for database connections to allow for different backends."""

    def execute(self, sql: str, parameters: tuple = ()) -> sqlite3.Cursor: ...
    def commit(self) -> None: ...
    def close(self) -> None: ...


class DocumentProcessor(Protocol):
    """Protocol for document processing to allow for different implementations.

    This protocol defines the expected interface for a DocumentProcessor class
    that can find files, extract content, run AI analysis, and store results.
    Implement this protocol to integrate with an existing document processing system.
    """

    def find_files(self, folder_path: str) -> list[str]:
        """Find all processable files in a folder.

        Args:
            folder_path: Path to the folder to scan.

        Returns:
            List of file paths found in the folder.
        """
        ...

    def process_file(self, file_path: str) -> dict:
        """Process a single file: extract content, run AI analysis, store in database.

        Args:
            file_path: Path to the file to process.

        Returns:
            Dictionary with processing results including ai_category, entities, etc.
        """
        ...

    def is_processable(self, file_path: str) -> bool:
        """Check if a file can be processed (e.g., supported file type).

        Args:
            file_path: Path to the file to check.

        Returns:
            True if the file can be processed, False otherwise.
        """
        ...


# Default supported file extensions for document processing
SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".txt",
    ".rtf",
    ".odt",
    ".xls",
    ".xlsx",
    ".csv",
    ".ppt",
    ".pptx",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".tiff",
    ".bmp",
}


@dataclass
class FileInfo:
    """Information about a file on disk."""

    path: str
    filename: str
    extension: str
    size_bytes: int
    modified_time: str
    in_database: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "path": self.path,
            "filename": self.filename,
            "extension": self.extension,
            "size_bytes": self.size_bytes,
            "modified_time": self.modified_time,
            "in_database": self.in_database,
        }


@dataclass
class FolderScanResult:
    """Result of scanning a folder for files."""

    folder_path: str
    total_files: int = 0
    files_in_database: int = 0
    files_not_in_database: int = 0
    files: list[FileInfo] = field(default_factory=list)
    unanalyzed_files: list[FileInfo] = field(default_factory=list)
    scanned_at: str = ""

    def __post_init__(self):
        if not self.scanned_at:
            self.scanned_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "folder_path": self.folder_path,
            "total_files": self.total_files,
            "files_in_database": self.files_in_database,
            "files_not_in_database": self.files_not_in_database,
            "files": [f.to_dict() for f in self.files],
            "unanalyzed_files": [f.to_dict() for f in self.unanalyzed_files],
            "scanned_at": self.scanned_at,
        }


@dataclass
class DocumentInfo:
    """Information about a single document from the database."""

    id: int
    filename: str
    current_path: str
    ai_category: str = ""
    ai_subcategories: list[str] = field(default_factory=list)
    ai_summary: str = ""
    entities: dict = field(default_factory=dict)
    key_dates: list[str] = field(default_factory=list)
    original_path: str = ""
    folder_hierarchy: list[str] = field(default_factory=list)
    pdf_created_date: str = ""
    pdf_modified_date: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "filename": self.filename,
            "current_path": self.current_path,
            "ai_category": self.ai_category,
            "ai_subcategories": self.ai_subcategories,
            "ai_summary": self.ai_summary,
            "entities": self.entities,
            "key_dates": self.key_dates,
            "original_path": self.original_path,
            "folder_hierarchy": self.folder_hierarchy,
            "pdf_created_date": self.pdf_created_date,
            "pdf_modified_date": self.pdf_modified_date,
        }


@dataclass
class FolderAnalysis:
    """Analysis results for a folder's content."""

    folder_path: str
    document_count: int = 0
    documents: list[DocumentInfo] = field(default_factory=list)
    ai_categories: set[str] = field(default_factory=set)
    date_range: tuple[str, str] | None = None  # (earliest, latest)
    year_clusters: list[str] = field(
        default_factory=list
    )  # e.g., ["2002-2003", "2024-2025"]
    entities: dict[str, set[str]] = field(default_factory=dict)  # type -> values
    original_paths: set[str] = field(default_factory=set)
    context_bins: set[str] = field(default_factory=set)
    analyzed_at: str = ""

    def __post_init__(self):
        if not self.analyzed_at:
            self.analyzed_at = datetime.now().isoformat()
        # Convert sets to regular sets if they're frozensets
        if isinstance(self.ai_categories, frozenset):
            self.ai_categories = set(self.ai_categories)
        if isinstance(self.original_paths, frozenset):
            self.original_paths = set(self.original_paths)
        if isinstance(self.context_bins, frozenset):
            self.context_bins = set(self.context_bins)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "folder_path": self.folder_path,
            "document_count": self.document_count,
            "documents": [d.to_dict() for d in self.documents],
            "ai_categories": list(self.ai_categories),
            "date_range": self.date_range,
            "year_clusters": self.year_clusters,
            "entities": {k: list(v) for k, v in self.entities.items()},
            "original_paths": list(self.original_paths),
            "context_bins": list(self.context_bins),
            "analyzed_at": self.analyzed_at,
        }


@dataclass
class ConsolidationDecision:
    """Decision about whether two folders should be consolidated."""

    folder1_path: str
    folder2_path: str
    should_consolidate: bool
    confidence: float  # 0.0 to 1.0
    reasoning: list[str] = field(default_factory=list)
    matching_categories: bool = False
    matching_date_range: bool = False
    matching_context: bool = False
    matching_entities: bool = False
    compatible_paths: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "folder1_path": self.folder1_path,
            "folder2_path": self.folder2_path,
            "should_consolidate": self.should_consolidate,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "matching_categories": self.matching_categories,
            "matching_date_range": self.matching_date_range,
            "matching_context": self.matching_context,
            "matching_entities": self.matching_entities,
            "compatible_paths": self.compatible_paths,
        }


def _parse_json_field(value: str | None) -> dict | list:
    """Parse a JSON field from the database, handling None and errors."""
    if value is None:
        return {}
    if isinstance(value, (dict, list)):
        return value
    try:
        import json

        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return {}


def _parse_array_field(value: str | None) -> list:
    """Parse an array field from the database."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    try:
        import json

        result = json.loads(value)
        return result if isinstance(result, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _extract_year_from_date(date_str: str) -> int | None:
    """Extract year from a date string in various formats."""
    if not date_str:
        return None

    # Try common date formats
    formats = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%Y-%m-%dT%H:%M:%S",
        "%Y",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str.strip()[:19], fmt)
            return dt.year
        except ValueError:
            continue

    # Try to extract 4-digit year directly
    import re

    match = re.search(r"\b(19|20)\d{2}\b", date_str)
    if match:
        return int(match.group())

    return None


def _compute_year_clusters(dates: list[str]) -> list[str]:
    """Compute year clusters from a list of dates.

    Groups consecutive years together (e.g., 2002, 2003 -> "2002-2003").
    """
    years = set()
    for date_str in dates:
        year = _extract_year_from_date(date_str)
        if year:
            years.add(year)

    if not years:
        return []

    sorted_years = sorted(years)
    clusters = []
    cluster_start = sorted_years[0]
    cluster_end = sorted_years[0]

    for year in sorted_years[1:]:
        if year <= cluster_end + 1:
            cluster_end = year
        else:
            if cluster_start == cluster_end:
                clusters.append(str(cluster_start))
            else:
                clusters.append(f"{cluster_start}-{cluster_end}")
            cluster_start = year
            cluster_end = year

    # Add the last cluster
    if cluster_start == cluster_end:
        clusters.append(str(cluster_start))
    else:
        clusters.append(f"{cluster_start}-{cluster_end}")

    return clusters


def _extract_context_bin(path: str) -> str:
    """Extract context bin from a path (e.g., 'Personal Bin', 'Work')."""
    path_lower = path.lower()

    # Common context indicators
    context_indicators = [
        ("desktop", "Desktop"),
        ("documents", "Documents"),
        ("downloads", "Downloads"),
        ("personal", "Personal"),
        ("work", "Work"),
        ("archive", "Archive"),
        ("backup", "Backup"),
        ("icloud", "iCloud"),
        ("dropbox", "Dropbox"),
        ("onedrive", "OneDrive"),
        ("google drive", "Google Drive"),
    ]

    for indicator, context in context_indicators:
        if indicator in path_lower:
            return context

    return "Unknown"


def _check_path_compatibility(paths1: set[str], paths2: set[str]) -> tuple[bool, str]:
    """Check if two sets of paths are compatible for consolidation.

    Returns (compatible, reason).
    """
    if not paths1 or not paths2:
        return True, "No path context to compare"

    # Extract context bins from paths
    contexts1 = {_extract_context_bin(p) for p in paths1}
    contexts2 = {_extract_context_bin(p) for p in paths2}

    # Check for Microsoft vs macOS Desktop conflict
    for p1 in paths1:
        for p2 in paths2:
            p1_lower = p1.lower()
            p2_lower = p2.lower()

            # Check for different "Desktop" sources
            if "desktop" in p1_lower and "desktop" in p2_lower:
                # Check if they're from different ecosystems
                if ("microsoft" in p1_lower) != ("microsoft" in p2_lower):
                    return (
                        False,
                        "Different Desktop contexts (Microsoft vs non-Microsoft)",
                    )
                if ("macos" in p1_lower or "mac" in p1_lower) != (
                    "macos" in p2_lower or "mac" in p2_lower
                ):
                    return False, "Different Desktop contexts (macOS vs non-macOS)"

    # If contexts overlap, they're compatible
    if contexts1 & contexts2:
        return True, f"Matching context: {contexts1 & contexts2}"

    # Different contexts but not necessarily incompatible
    return True, f"Different contexts: {contexts1} vs {contexts2}"


def _check_date_range_overlap(
    range1: tuple[str, str] | None, range2: tuple[str, str] | None
) -> tuple[bool, str]:
    """Check if two date ranges are compatible (overlapping or adjacent).

    Returns (compatible, reason).
    """
    if range1 is None or range2 is None:
        return True, "No date range to compare"

    years1 = set()
    years2 = set()

    for date_str in range1:
        year = _extract_year_from_date(date_str)
        if year:
            years1.add(year)

    for date_str in range2:
        year = _extract_year_from_date(date_str)
        if year:
            years2.add(year)

    if not years1 or not years2:
        return True, "Could not extract years from date ranges"

    # Check for significant year gap (more than 2 years apart)
    min1, max1 = min(years1), max(years1)
    min2, max2 = min(years2), max(years2)

    # Check for overlap or adjacency
    if max1 >= min2 - 1 and max2 >= min1 - 1:
        return True, f"Overlapping date ranges: {min1}-{max1} and {min2}-{max2}"

    # Significant gap - different timeframes
    gap = min(abs(min1 - max2), abs(min2 - max1))
    return (
        False,
        f"Different timeframes: {min1}-{max1} vs {min2}-{max2} (gap: {gap} years)",
    )


def get_folder_metadata(
    conn: DatabaseConnection,
    folder_path: str,
) -> list[DocumentInfo]:
    """Query database for all documents in a folder.

    Args:
        conn: Database connection.
        folder_path: Path to the folder to query.

    Returns:
        List of DocumentInfo objects for files in the folder.
    """
    folder_path = str(Path(folder_path).resolve())
    if not folder_path.endswith("/"):
        folder_path_pattern = folder_path + "/%"
    else:
        folder_path_pattern = folder_path + "%"

    documents = []

    try:
        # Query documents table
        cursor = conn.execute(
            """
            SELECT
                d.id,
                d.filename,
                d.current_path,
                d.ai_category,
                d.ai_subcategories,
                d.ai_summary,
                d.entities,
                d.key_dates,
                d.folder_hierarchy,
                d.pdf_created_date,
                d.pdf_modified_date
            FROM documents d
            WHERE d.current_path LIKE ?
            """,
            (folder_path_pattern,),
        )

        for row in cursor.fetchall():
            doc = DocumentInfo(
                id=row[0],
                filename=row[1] or "",
                current_path=row[2] or "",
                ai_category=row[3] or "",
                ai_subcategories=_parse_array_field(row[4]),
                ai_summary=row[5] or "",
                entities=_parse_json_field(row[6]),
                key_dates=_parse_array_field(row[7]),
                folder_hierarchy=_parse_array_field(row[8]),
                pdf_created_date=row[9] or "",
                pdf_modified_date=row[10] or "",
            )

            # Try to get original path from document_locations
            try:
                loc_cursor = conn.execute(
                    """
                    SELECT path FROM document_locations
                    WHERE document_id = ? AND location_type = 'original'
                    ORDER BY created_at ASC
                    LIMIT 1
                    """,
                    (doc.id,),
                )
                loc_row = loc_cursor.fetchone()
                if loc_row:
                    doc.original_path = loc_row[0]
            except sqlite3.Error:
                pass  # original_path remains empty

            documents.append(doc)

    except sqlite3.Error:
        pass  # Return empty list on error

    return documents


def analyze_folder_content(
    conn: DatabaseConnection,
    folder_path: str,
) -> FolderAnalysis:
    """Analyze the content of a folder using database information.

    This function queries the database for all files in the folder and
    extracts rich context including AI categories, dates, entities, and paths.

    Args:
        conn: Database connection.
        folder_path: Path to the folder to analyze.

    Returns:
        FolderAnalysis with comprehensive folder content analysis.
    """
    documents = get_folder_metadata(conn, folder_path)

    analysis = FolderAnalysis(
        folder_path=folder_path,
        document_count=len(documents),
        documents=documents,
    )

    if not documents:
        return analysis

    # Collect all dates for range calculation
    all_dates = []

    for doc in documents:
        # Collect AI categories
        if doc.ai_category:
            analysis.ai_categories.add(doc.ai_category)

        # Collect dates
        all_dates.extend(doc.key_dates)
        if doc.pdf_created_date:
            all_dates.append(doc.pdf_created_date)
        if doc.pdf_modified_date:
            all_dates.append(doc.pdf_modified_date)

        # Collect entities by type
        if isinstance(doc.entities, dict):
            for entity_type, values in doc.entities.items():
                if entity_type not in analysis.entities:
                    analysis.entities[entity_type] = set()
                if isinstance(values, list):
                    analysis.entities[entity_type].update(values)
                elif isinstance(values, str):
                    analysis.entities[entity_type].add(values)

        # Collect original paths
        if doc.original_path:
            analysis.original_paths.add(doc.original_path)

        # Collect context bins from folder hierarchy
        for folder in doc.folder_hierarchy:
            context = _extract_context_bin(folder)
            if context != "Unknown":
                analysis.context_bins.add(context)

    # Calculate date range
    years = []
    for date_str in all_dates:
        year = _extract_year_from_date(date_str)
        if year:
            years.append(year)

    if years:
        min_year = min(years)
        max_year = max(years)
        analysis.date_range = (str(min_year), str(max_year))

    # Calculate year clusters
    analysis.year_clusters = _compute_year_clusters(all_dates)

    return analysis


def should_consolidate_folders(
    conn: DatabaseConnection,
    folder1_path: str,
    folder2_path: str,
    similarity_threshold: float = 0.6,
) -> ConsolidationDecision:
    """Determine if two folders should be consolidated based on content analysis.

    This function applies multiple rules to decide if folders are compatible:
    1. Same AI category → Can consolidate
    2. Same date range → Can consolidate
    3. Same context bin → Can consolidate
    4. Same entities → Can consolidate
    5. Compatible original paths → Can consolidate

    All rules should pass for high-confidence consolidation.

    Args:
        conn: Database connection.
        folder1_path: Path to the first folder.
        folder2_path: Path to the second folder.
        similarity_threshold: Minimum confidence (0.0-1.0) required for consolidation.
            Default is 0.6 (60%). Higher values require more matching rules.

    Returns:
        ConsolidationDecision with reasoning.
    """
    analysis1 = analyze_folder_content(conn, folder1_path)
    analysis2 = analyze_folder_content(conn, folder2_path)

    decision = ConsolidationDecision(
        folder1_path=folder1_path,
        folder2_path=folder2_path,
        should_consolidate=False,
        confidence=0.0,
    )

    # If either folder has no documents in database, we can't make a content-based decision
    if analysis1.document_count == 0 or analysis2.document_count == 0:
        decision.reasoning.append(
            f"Insufficient data: folder1 has {analysis1.document_count} docs, "
            f"folder2 has {analysis2.document_count} docs in database"
        )
        decision.confidence = 0.0
        return decision

    passed_rules = 0
    total_rules = 5

    # Rule 1: Check AI categories
    if analysis1.ai_categories and analysis2.ai_categories:
        common_categories = analysis1.ai_categories & analysis2.ai_categories
        if common_categories:
            decision.matching_categories = True
            decision.reasoning.append(f"✅ Matching AI categories: {common_categories}")
            passed_rules += 1
        else:
            decision.reasoning.append(
                f"❌ Different AI categories: {analysis1.ai_categories} vs {analysis2.ai_categories}"
            )
    else:
        decision.reasoning.append("⚠️ Missing AI category data")
        passed_rules += 0.5  # Partial credit for missing data

    # Rule 2: Check date ranges
    date_compatible, date_reason = _check_date_range_overlap(
        analysis1.date_range, analysis2.date_range
    )
    if date_compatible:
        decision.matching_date_range = True
        decision.reasoning.append(f"✅ {date_reason}")
        passed_rules += 1
    else:
        decision.reasoning.append(f"❌ {date_reason}")

    # Rule 3: Check context bins
    if analysis1.context_bins and analysis2.context_bins:
        common_context = analysis1.context_bins & analysis2.context_bins
        if common_context:
            decision.matching_context = True
            decision.reasoning.append(f"✅ Matching context bins: {common_context}")
            passed_rules += 1
        else:
            decision.reasoning.append(
                f"❌ Different context bins: {analysis1.context_bins} vs {analysis2.context_bins}"
            )
    else:
        decision.reasoning.append("⚠️ No context bin data")
        passed_rules += 0.5

    # Rule 4: Check entities (people, organizations)
    if analysis1.entities and analysis2.entities:
        # Check for common people
        people1 = analysis1.entities.get("people", set()) | analysis1.entities.get(
            "persons", set()
        )
        people2 = analysis2.entities.get("people", set()) | analysis2.entities.get(
            "persons", set()
        )

        # Check for common organizations
        orgs1 = analysis1.entities.get("organizations", set()) | analysis1.entities.get(
            "orgs", set()
        )
        orgs2 = analysis2.entities.get("organizations", set()) | analysis2.entities.get(
            "orgs", set()
        )

        common_people = people1 & people2 if people1 and people2 else set()
        common_orgs = orgs1 & orgs2 if orgs1 and orgs2 else set()

        if common_people or common_orgs:
            decision.matching_entities = True
            if common_people:
                decision.reasoning.append(f"✅ Matching people: {common_people}")
            if common_orgs:
                decision.reasoning.append(f"✅ Matching organizations: {common_orgs}")
            passed_rules += 1
        elif not people1 and not people2 and not orgs1 and not orgs2:
            decision.reasoning.append("⚠️ No entity data")
            passed_rules += 0.5
        else:
            decision.reasoning.append(
                f"❌ Different entities: people={people1} vs {people2}, orgs={orgs1} vs {orgs2}"
            )
    else:
        decision.reasoning.append("⚠️ No entity data")
        passed_rules += 0.5

    # Rule 5: Check path compatibility
    path_compatible, path_reason = _check_path_compatibility(
        analysis1.original_paths, analysis2.original_paths
    )
    if path_compatible:
        decision.compatible_paths = True
        decision.reasoning.append(f"✅ {path_reason}")
        passed_rules += 1
    else:
        decision.reasoning.append(f"❌ {path_reason}")

    # Calculate confidence and final decision
    decision.confidence = passed_rules / total_rules

    # Consolidate if confidence meets the threshold
    # BUT never consolidate if dates or categories explicitly don't match
    if decision.confidence >= similarity_threshold:
        if (
            not decision.matching_date_range
            and analysis1.date_range
            and analysis2.date_range
        ):
            decision.should_consolidate = False
            decision.reasoning.append(
                "⛔ NOT consolidating: Different timeframes override other matches"
            )
        elif (
            not decision.matching_categories
            and analysis1.ai_categories
            and analysis2.ai_categories
        ):
            decision.should_consolidate = False
            decision.reasoning.append(
                "⛔ NOT consolidating: Different AI categories override other matches"
            )
        else:
            decision.should_consolidate = True
            decision.reasoning.append(
                f"✅ CONSOLIDATE: {decision.confidence:.0%} confidence"
            )
    else:
        decision.reasoning.append(
            f"⛔ NOT consolidating: Confidence {decision.confidence:.0%} "
            f"below threshold {similarity_threshold:.0%}"
        )

    return decision


def analyze_folder_content_from_path(
    db_path: str,
    folder_path: str,
) -> FolderAnalysis:
    """Convenience function to analyze a folder using a database path.

    Args:
        db_path: Path to the SQLite database file.
        folder_path: Path to the folder to analyze.

    Returns:
        FolderAnalysis with comprehensive folder content analysis.

    Raises:
        FileNotFoundError: If the database file doesn't exist.
    """
    conn = get_database_connection(db_path)
    try:
        return analyze_folder_content(conn, folder_path)
    finally:
        conn.close()


def should_consolidate_folders_from_path(
    db_path: str,
    folder1_path: str,
    folder2_path: str,
    similarity_threshold: float = 0.6,
) -> ConsolidationDecision:
    """Convenience function to check consolidation using a database path.

    Args:
        db_path: Path to the SQLite database file.
        folder1_path: Path to the first folder.
        folder2_path: Path to the second folder.
        similarity_threshold: Minimum confidence (0.0-1.0) required for consolidation.
            Default is 0.6 (60%). Higher values require more matching rules.

    Returns:
        ConsolidationDecision with reasoning.

    Raises:
        FileNotFoundError: If the database file doesn't exist.
    """
    conn = get_database_connection(db_path)
    try:
        return should_consolidate_folders(
            conn, folder1_path, folder2_path, similarity_threshold
        )
    finally:
        conn.close()


# ============================================================================
# DocumentProcessor Integration Functions
# ============================================================================


def is_supported_file(file_path: str, extensions: set[str] | None = None) -> bool:
    """Check if a file has a supported extension for document processing.

    Args:
        file_path: Path to the file to check.
        extensions: Set of supported extensions. Defaults to SUPPORTED_EXTENSIONS.

    Returns:
        True if the file extension is supported, False otherwise.
    """
    if extensions is None:
        extensions = SUPPORTED_EXTENSIONS

    ext = Path(file_path).suffix.lower()
    return ext in extensions


def scan_folder_for_files(
    folder_path: str,
    extensions: set[str] | None = None,
    recursive: bool = True,
) -> list[FileInfo]:
    """Scan a folder for files, optionally filtering by extension.

    This is the first step in the document-first approach: find all actual files
    on disk before checking the database.

    Args:
        folder_path: Path to the folder to scan.
        extensions: Set of file extensions to include. If None, includes all files.
        recursive: Whether to scan subdirectories recursively.

    Returns:
        List of FileInfo objects for files found in the folder.
    """
    folder_path = str(Path(folder_path).resolve())
    files: list[FileInfo] = []

    if not os.path.isdir(folder_path):
        return files

    if recursive:
        for root, _, filenames in os.walk(folder_path):
            for filename in filenames:
                file_path = os.path.join(root, filename)
                ext = Path(filename).suffix.lower()

                # Skip if filtering by extension and extension not in list
                if extensions is not None and ext not in extensions:
                    continue

                try:
                    stat = os.stat(file_path)
                    files.append(
                        FileInfo(
                            path=file_path,
                            filename=filename,
                            extension=ext,
                            size_bytes=stat.st_size,
                            modified_time=datetime.fromtimestamp(
                                stat.st_mtime
                            ).isoformat(),
                        )
                    )
                except OSError:
                    # Skip files that can't be accessed
                    pass
    else:
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)
            if not os.path.isfile(file_path):
                continue

            ext = Path(filename).suffix.lower()

            # Skip if filtering by extension and extension not in list
            if extensions is not None and ext not in extensions:
                continue

            try:
                stat = os.stat(file_path)
                files.append(
                    FileInfo(
                        path=file_path,
                        filename=filename,
                        extension=ext,
                        size_bytes=stat.st_size,
                        modified_time=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    )
                )
            except OSError:
                pass

    return files


def check_files_in_database(
    conn: DatabaseConnection,
    files: list[FileInfo],
) -> list[FileInfo]:
    """Check which files from a list are already in the database.

    Updates the in_database field of each FileInfo object.

    Args:
        conn: Database connection.
        files: List of FileInfo objects to check.

    Returns:
        The same list of FileInfo objects with in_database field updated.
    """
    for file_info in files:
        try:
            cursor = conn.execute(
                "SELECT id FROM documents WHERE current_path = ?",
                (file_info.path,),
            )
            result = cursor.fetchone()
            file_info.in_database = result is not None
        except sqlite3.Error:
            file_info.in_database = False

    return files


def scan_folder_with_database(
    conn: DatabaseConnection,
    folder_path: str,
    extensions: set[str] | None = None,
    recursive: bool = True,
) -> FolderScanResult:
    """Scan a folder and check which files are in the database.

    This implements the document-first approach:
    1. Scan folder for actual files on disk
    2. Check database for existing analysis
    3. Identify files that need processing

    Args:
        conn: Database connection.
        folder_path: Path to the folder to scan.
        extensions: Set of file extensions to include. Defaults to SUPPORTED_EXTENSIONS.
        recursive: Whether to scan subdirectories recursively.

    Returns:
        FolderScanResult with information about all files and their database status.
    """
    if extensions is None:
        extensions = SUPPORTED_EXTENSIONS

    # Step 1: Scan folder for files
    files = scan_folder_for_files(folder_path, extensions, recursive)

    # Step 2: Check which files are in database
    files = check_files_in_database(conn, files)

    # Step 3: Build result
    files_in_db = [f for f in files if f.in_database]
    files_not_in_db = [f for f in files if not f.in_database]

    return FolderScanResult(
        folder_path=folder_path,
        total_files=len(files),
        files_in_database=len(files_in_db),
        files_not_in_database=len(files_not_in_db),
        files=files,
        unanalyzed_files=files_not_in_db,
    )


def scan_folder_with_database_from_path(
    db_path: str,
    folder_path: str,
    extensions: set[str] | None = None,
    recursive: bool = True,
) -> FolderScanResult:
    """Convenience function to scan a folder using a database path.

    Args:
        db_path: Path to the SQLite database file.
        folder_path: Path to the folder to scan.
        extensions: Set of file extensions to include. Defaults to SUPPORTED_EXTENSIONS.
        recursive: Whether to scan subdirectories recursively.

    Returns:
        FolderScanResult with information about all files and their database status.

    Raises:
        FileNotFoundError: If the database file doesn't exist.
    """
    conn = get_database_connection(db_path)
    try:
        return scan_folder_with_database(conn, folder_path, extensions, recursive)
    finally:
        conn.close()


def process_unanalyzed_files(
    processor: DocumentProcessor,
    files: list[FileInfo],
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> list[dict]:
    """Process files that are not yet in the database using a DocumentProcessor.

    This function uses the existing DocumentProcessor infrastructure to analyze
    files that haven't been processed yet.

    Args:
        processor: DocumentProcessor instance to use for processing.
        files: List of FileInfo objects for files to process.
        progress_callback: Optional callback(current, total, filename) for progress updates.

    Returns:
        List of processing results from the DocumentProcessor.
    """
    results = []
    total = len(files)

    for i, file_info in enumerate(files):
        if progress_callback:
            progress_callback(i + 1, total, file_info.filename)

        # Check if processor can handle this file
        if not processor.is_processable(file_info.path):
            continue

        try:
            result = processor.process_file(file_info.path)
            results.append(result)
        except Exception as e:
            # Log error but continue processing
            results.append(
                {
                    "path": file_info.path,
                    "error": str(e),
                    "success": False,
                }
            )

    return results


def analyze_folder_with_processing(
    conn: DatabaseConnection,
    folder_path: str,
    processor: DocumentProcessor | None = None,
    analyze_missing: bool = False,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> FolderAnalysis:
    """Analyze folder content, optionally processing unanalyzed files.

    This is the PRIMARY METHOD for content-aware folder analysis:
    1. Scan folder for all files
    2. Query database for existing analysis
    3. Optionally process files not in database using DocumentProcessor
    4. Return comprehensive analysis

    Args:
        conn: Database connection.
        folder_path: Path to the folder to analyze.
        processor: Optional DocumentProcessor for analyzing new files.
        analyze_missing: If True and processor provided, analyze files not in database.
        progress_callback: Optional callback(current, total, filename) for progress updates.

    Returns:
        FolderAnalysis with comprehensive folder content analysis.
    """
    # First, scan the folder to find all files
    scan_result = scan_folder_with_database(conn, folder_path)

    # If we have a processor and should analyze missing files, do so
    if processor and analyze_missing and scan_result.unanalyzed_files:
        process_unanalyzed_files(
            processor, scan_result.unanalyzed_files, progress_callback
        )

    # Now get the analysis using database (which may have been updated)
    return analyze_folder_content(conn, folder_path)


def analyze_folder_with_processing_from_path(
    db_path: str,
    folder_path: str,
    processor: DocumentProcessor | None = None,
    analyze_missing: bool = False,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> FolderAnalysis:
    """Convenience function to analyze a folder with optional processing.

    Args:
        db_path: Path to the SQLite database file.
        folder_path: Path to the folder to analyze.
        processor: Optional DocumentProcessor for analyzing new files.
        analyze_missing: If True and processor provided, analyze files not in database.
        progress_callback: Optional callback(current, total, filename) for progress updates.

    Returns:
        FolderAnalysis with comprehensive folder content analysis.

    Raises:
        FileNotFoundError: If the database file doesn't exist.
    """
    conn = get_database_connection(db_path)
    try:
        return analyze_folder_with_processing(
            conn, folder_path, processor, analyze_missing, progress_callback
        )
    finally:
        conn.close()


class DefaultDocumentProcessor:
    """DocumentProcessor backed by the Goldilocks ingestion pipeline.

    Extracts file signals (filename, path, first 500 chars of content),
    classifies via local Ollama LLM, and stores results in SQLite.
    """

    def __init__(
        self,
        extensions: set[str] | None = None,
        db_path: str = "",
        fast_model: str = "llama3.1:8b-instruct-q8_0",
        smart_model: str = "qwen2.5-coder:14b",
        escalation_threshold: float = 0.7,
    ):
        self.extensions = extensions or SUPPORTED_EXTENSIONS
        self._db_path = db_path
        self._fast_model = fast_model
        self._smart_model = smart_model
        self._escalation_threshold = escalation_threshold

    def find_files(self, folder_path: str) -> list[str]:
        files = scan_folder_for_files(folder_path, self.extensions, recursive=True)
        return [f.path for f in files]

    def is_processable(self, file_path: str) -> bool:
        return is_supported_file(file_path, self.extensions)

    def process_file(self, file_path: str) -> dict:
        """Extract signals, classify via LLM, and store in the database."""
        path_obj = Path(file_path)
        if not path_obj.exists():
            return {"path": file_path, "error": "File not found", "success": False}

        try:
            from organizer.light_extractor import collect_signals
            from organizer.llm_classifier import classify_file

            signals = collect_signals(file_path)
            classification = classify_file(
                signals,
                fast_model=self._fast_model,
                smart_model=self._smart_model,
                escalation_threshold=self._escalation_threshold,
            )

            if self._db_path:
                from organizer.ingestion_pipeline import IngestionPipeline
                pipeline = IngestionPipeline(self._db_path)
                pipeline.ingest_file(file_path)
                pipeline.close()

            return {
                "path": file_path,
                "filename": path_obj.name,
                "extension": path_obj.suffix.lower(),
                "ai_category": classification.category,
                "ai_subcategory": classification.subcategory,
                "entities": classification.entities,
                "key_dates": classification.key_dates,
                "summary": classification.summary,
                "confidence": classification.confidence,
                "model": classification.model_used,
                "success": True,
            }
        except Exception as e:
            return {"path": file_path, "error": str(e), "success": False}


def create_document_processor(
    extensions: set[str] | None = None,
    db_path: str = "",
    fast_model: str = "llama3.1:8b-instruct-q8_0",
    smart_model: str = "qwen2.5-coder:14b",
    escalation_threshold: float = 0.7,
) -> DefaultDocumentProcessor:
    """Create a DocumentProcessor instance backed by the Goldilocks pipeline."""
    return DefaultDocumentProcessor(
        extensions=extensions,
        db_path=db_path,
        fast_model=fast_model,
        smart_model=smart_model,
        escalation_threshold=escalation_threshold,
    )
