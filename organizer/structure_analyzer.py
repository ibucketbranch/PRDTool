"""Structure Analyzer module for learning filesystem organization patterns.

Walks the filesystem tree, records folder metadata, and outputs a structured
snapshot that captures the user's existing organizational strategy. This enables
the Learning-Agent to absorb existing folder structures without reshuffling.

The analyzer:
- Walks directory tree up to configurable depth (default: 4 levels)
- Records: folder name, depth, file count, file types, naming patterns
- Respects .organizer ignore patterns and skips system folders
- Outputs learned_structure.json with metadata per node
- Supports LLM-powered strategy narration (T2 Smart)

Example usage:
    analyzer = StructureAnalyzer()
    result = analyzer.analyze("/path/to/root", max_depth=4)
    print(result.total_folders)
    print(result.strategy_description)
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from organizer.model_router import TaskProfile

if TYPE_CHECKING:
    from organizer.llm_client import LLMClient
    from organizer.model_router import ModelRouter
    from organizer.prompt_registry import PromptRegistry


# Default paths
DEFAULT_STRUCTURE_OUTPUT_PATH = ".organizer/agent/learned_structure.json"

# System folders to always skip
SYSTEM_FOLDERS = {
    ".git",
    ".svn",
    ".hg",
    "__pycache__",
    "node_modules",
    ".Trash",
    ".Trashes",
    ".DS_Store",
    ".Spotlight-V100",
    ".fseventsd",
    "Library",
    "System",
    "Applications",
    ".venv",
    "venv",
    ".env",
    "env",
    ".cache",
    ".npm",
    ".yarn",
    ".config",
    ".local",
    "tmp",
    "temp",
    ".organizer",
}

# Default ignore patterns (fnmatch style)
DEFAULT_IGNORE_PATTERNS = [
    "*/.git/*",
    "*/.git",
    "*/__pycache__/*",
    "*/__pycache__",
    "*/node_modules/*",
    "*/node_modules",
    "*/.Trash/*",
    "*/.Trash",
    "*/.*",
]


def _now_iso() -> str:
    """Get current timestamp in ISO format."""
    return datetime.now().isoformat()


@dataclass
class FolderNode:
    """Metadata for a single folder in the structure tree.

    Captures all information about a folder needed for rule learning:
    - Location and depth in the hierarchy
    - File statistics (count, types)
    - Naming pattern analysis
    - Sample filenames for LLM context

    Attributes:
        path: Full absolute path to the folder.
        name: Folder name (last component of path).
        depth: Depth from scan root (0 = root).
        file_count: Number of files directly in this folder.
        subfolder_count: Number of immediate subfolders.
        total_size_bytes: Total size of files in bytes.
        file_types: Counter of file extensions (e.g., {".pdf": 5, ".txt": 3}).
        sample_filenames: Up to 10 sample filenames for LLM context.
        naming_patterns: Detected patterns in filenames (e.g., "YYYY_*", "prefix_*").
        has_date_structure: Whether subfolders suggest date organization (2020, 2021, etc.).
        scanned_at: ISO timestamp when folder was scanned.
    """

    path: str
    name: str
    depth: int
    file_count: int = 0
    subfolder_count: int = 0
    total_size_bytes: int = 0
    file_types: dict[str, int] = field(default_factory=dict)
    sample_filenames: list[str] = field(default_factory=list)
    naming_patterns: list[str] = field(default_factory=list)
    has_date_structure: bool = False
    scanned_at: str = ""

    def __post_init__(self) -> None:
        """Set default timestamp if not provided."""
        if not self.scanned_at:
            self.scanned_at = _now_iso()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "path": self.path,
            "name": self.name,
            "depth": self.depth,
            "file_count": self.file_count,
            "subfolder_count": self.subfolder_count,
            "total_size_bytes": self.total_size_bytes,
            "file_types": dict(self.file_types),
            "sample_filenames": list(self.sample_filenames),
            "naming_patterns": list(self.naming_patterns),
            "has_date_structure": self.has_date_structure,
            "scanned_at": self.scanned_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FolderNode":
        """Create FolderNode from dictionary."""
        return cls(
            path=data.get("path", ""),
            name=data.get("name", ""),
            depth=data.get("depth", 0),
            file_count=data.get("file_count", 0),
            subfolder_count=data.get("subfolder_count", 0),
            total_size_bytes=data.get("total_size_bytes", 0),
            file_types=dict(data.get("file_types", {})),
            sample_filenames=list(data.get("sample_filenames", [])),
            naming_patterns=list(data.get("naming_patterns", [])),
            has_date_structure=data.get("has_date_structure", False),
            scanned_at=data.get("scanned_at", ""),
        )


@dataclass
class StructureSnapshot:
    """Complete snapshot of analyzed folder structure.

    Captures the entire analyzed structure with metadata and optionally
    an LLM-generated strategy description.

    Attributes:
        root_path: Root path that was analyzed.
        max_depth: Maximum depth used for analysis.
        total_folders: Total number of folders analyzed.
        total_files: Total number of files found.
        total_size_bytes: Total size of all files.
        folders: List of FolderNode records.
        strategy_description: LLM-generated description of organizational strategy.
        model_used: LLM model used for narration (empty if keyword analysis only).
        analyzed_at: ISO timestamp when analysis completed.
    """

    root_path: str
    max_depth: int
    total_folders: int = 0
    total_files: int = 0
    total_size_bytes: int = 0
    folders: list[FolderNode] = field(default_factory=list)
    strategy_description: str = ""
    model_used: str = ""
    analyzed_at: str = ""

    def __post_init__(self) -> None:
        """Set default timestamp if not provided."""
        if not self.analyzed_at:
            self.analyzed_at = _now_iso()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "version": "1.0",
            "root_path": self.root_path,
            "max_depth": self.max_depth,
            "total_folders": self.total_folders,
            "total_files": self.total_files,
            "total_size_bytes": self.total_size_bytes,
            "folders": [f.to_dict() for f in self.folders],
            "strategy_description": self.strategy_description,
            "model_used": self.model_used,
            "analyzed_at": self.analyzed_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StructureSnapshot":
        """Create StructureSnapshot from dictionary."""
        folders = [FolderNode.from_dict(f) for f in data.get("folders", [])]
        return cls(
            root_path=data.get("root_path", ""),
            max_depth=data.get("max_depth", 4),
            total_folders=data.get("total_folders", 0),
            total_files=data.get("total_files", 0),
            total_size_bytes=data.get("total_size_bytes", 0),
            folders=folders,
            strategy_description=data.get("strategy_description", ""),
            model_used=data.get("model_used", ""),
            analyzed_at=data.get("analyzed_at", ""),
        )

    def save(self, path: str | Path = DEFAULT_STRUCTURE_OUTPUT_PATH) -> None:
        """Save snapshot to JSON file.

        Args:
            path: Output file path.
        """
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(self.to_dict(), indent=2),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: str | Path = DEFAULT_STRUCTURE_OUTPUT_PATH) -> "StructureSnapshot":
        """Load snapshot from JSON file.

        Args:
            path: Input file path.

        Returns:
            StructureSnapshot loaded from file.

        Raises:
            FileNotFoundError: If file doesn't exist.
            json.JSONDecodeError: If file is invalid JSON.
        """
        file_path = Path(path)
        data = json.loads(file_path.read_text(encoding="utf-8"))
        return cls.from_dict(data)

    def get_folders_at_depth(self, depth: int) -> list[FolderNode]:
        """Get all folders at a specific depth.

        Args:
            depth: Depth level to filter (0 = root).

        Returns:
            List of FolderNode records at that depth.
        """
        return [f for f in self.folders if f.depth == depth]

    def get_top_file_types(self, limit: int = 10) -> list[tuple[str, int]]:
        """Get the most common file types across all folders.

        Args:
            limit: Maximum number of types to return.

        Returns:
            List of (extension, count) tuples, sorted by count descending.
        """
        combined: Counter[str] = Counter()
        for folder in self.folders:
            combined.update(folder.file_types)
        return combined.most_common(limit)


class StructureAnalyzer:
    """Analyzer for learning filesystem organization patterns.

    Walks the filesystem tree, collects metadata about folders and files,
    detects naming patterns, and optionally generates an LLM-powered
    strategy description.

    Example:
        analyzer = StructureAnalyzer()
        result = analyzer.analyze("/path/to/root", max_depth=4)
        result.save()
    """

    def __init__(
        self,
        llm_client: "LLMClient | None" = None,
        model_router: "ModelRouter | None" = None,
        prompt_registry: "PromptRegistry | None" = None,
        use_llm: bool = True,
        ignore_patterns: list[str] | None = None,
    ):
        """Initialize the structure analyzer.

        Args:
            llm_client: Optional LLM client for strategy narration.
            model_router: Optional model router for tier selection.
            prompt_registry: Optional prompt registry for loading prompts.
            use_llm: Whether to use LLM for narration.
            ignore_patterns: Custom ignore patterns (uses defaults if None).
        """
        self._llm_client = llm_client
        self._model_router = model_router
        self._prompt_registry = prompt_registry
        self._use_llm = use_llm
        self._ignore_patterns = ignore_patterns or DEFAULT_IGNORE_PATTERNS.copy()

    def analyze(
        self,
        root_path: str | Path,
        max_depth: int = 4,
        generate_narration: bool = True,
    ) -> StructureSnapshot:
        """Analyze a directory structure and create a snapshot.

        Walks the filesystem tree up to max_depth, collecting metadata
        about each folder. Optionally generates an LLM-powered narration
        of the organizational strategy.

        Args:
            root_path: Root directory to analyze.
            max_depth: Maximum depth to descend (default: 4).
            generate_narration: Whether to generate strategy description.

        Returns:
            StructureSnapshot containing all analyzed data.

        Raises:
            FileNotFoundError: If root_path doesn't exist.
            NotADirectoryError: If root_path is not a directory.
        """
        root = Path(root_path).resolve()

        if not root.exists():
            raise FileNotFoundError(f"Path not found: {root_path}")
        if not root.is_dir():
            raise NotADirectoryError(f"Not a directory: {root_path}")

        # Walk the tree and collect folder nodes
        folders = self._walk_tree(root, max_depth)

        # Compute totals
        total_files = sum(f.file_count for f in folders)
        total_size = sum(f.total_size_bytes for f in folders)

        # Create snapshot
        snapshot = StructureSnapshot(
            root_path=str(root),
            max_depth=max_depth,
            total_folders=len(folders),
            total_files=total_files,
            total_size_bytes=total_size,
            folders=folders,
        )

        # Generate strategy narration if requested
        if generate_narration:
            narration, model = self._generate_narration(snapshot)
            snapshot.strategy_description = narration
            snapshot.model_used = model

        return snapshot

    def _walk_tree(self, root: Path, max_depth: int) -> list[FolderNode]:
        """Walk the directory tree and collect folder metadata.

        Args:
            root: Root directory to start from.
            max_depth: Maximum depth to descend.

        Returns:
            List of FolderNode records.
        """
        folders: list[FolderNode] = []

        # Use os.walk for efficient traversal
        for dirpath, dirnames, filenames in os.walk(root, topdown=True):
            current = Path(dirpath).resolve()
            rel_path = current.relative_to(root)

            # Calculate depth
            depth = len(rel_path.parts) if str(rel_path) != "." else 0

            # Skip if beyond max depth
            if depth > max_depth:
                dirnames.clear()  # Don't descend further
                continue

            # Check if should be ignored
            if self._should_ignore(current):
                dirnames.clear()
                continue

            # Filter out ignored subdirectories (modifies dirnames in place)
            dirnames[:] = [
                d for d in dirnames
                if not self._should_ignore(current / d)
            ]

            # Collect folder metadata
            node = self._analyze_folder(current, depth, dirnames, filenames)
            folders.append(node)

        return folders

    def _should_ignore(self, path: Path) -> bool:
        """Check if a path should be ignored.

        Args:
            path: Path to check.

        Returns:
            True if path should be ignored.
        """
        # Check system folders
        if path.name in SYSTEM_FOLDERS:
            return True

        # Check hidden folders (start with .)
        if path.name.startswith(".") and path.name != ".":
            return True

        # Check ignore patterns
        path_str = str(path)
        for pattern in self._ignore_patterns:
            if fnmatch.fnmatch(path_str, pattern):
                return True
            if fnmatch.fnmatch(path.name, pattern.lstrip("*/")):
                return True

        return False

    def _analyze_folder(
        self,
        folder: Path,
        depth: int,
        subfolders: list[str],
        filenames: list[str],
    ) -> FolderNode:
        """Analyze a single folder and create a FolderNode.

        Args:
            folder: Path to the folder.
            depth: Depth from root.
            subfolders: List of subfolder names.
            filenames: List of filenames in this folder.

        Returns:
            FolderNode with analyzed metadata.
        """
        # Count file types and compute size
        file_types: Counter[str] = Counter()
        total_size = 0
        sample_files: list[str] = []

        for fname in filenames:
            # Skip hidden files
            if fname.startswith("."):
                continue

            file_path = folder / fname
            try:
                if file_path.is_file():
                    total_size += file_path.stat().st_size
                    ext = file_path.suffix.lower() or "(no extension)"
                    file_types[ext] += 1

                    # Collect samples
                    if len(sample_files) < 10:
                        sample_files.append(fname)
            except OSError:
                # Skip files we can't access
                continue

        # Detect naming patterns
        patterns = self._detect_naming_patterns(filenames)

        # Check for date-based subfolder structure
        has_date_structure = self._detect_date_structure(subfolders)

        return FolderNode(
            path=str(folder),
            name=folder.name or str(folder),
            depth=depth,
            file_count=len([f for f in filenames if not f.startswith(".")]),
            subfolder_count=len(subfolders),
            total_size_bytes=total_size,
            file_types=dict(file_types),
            sample_filenames=sample_files,
            naming_patterns=patterns,
            has_date_structure=has_date_structure,
        )

    def _detect_naming_patterns(self, filenames: list[str]) -> list[str]:
        """Detect common naming patterns in filenames.

        Args:
            filenames: List of filenames to analyze.

        Returns:
            List of detected patterns (e.g., "YYYY_*", "prefix_*").
        """
        if not filenames:
            return []

        patterns: list[str] = []

        # Filter out hidden files
        visible_files = [f for f in filenames if not f.startswith(".")]
        if not visible_files:
            return patterns

        # Pattern: Year prefix (2019_*, 2020_*, etc.)
        year_pattern = re.compile(r"^(19|20)\d{2}[_\-]")
        year_count = sum(1 for f in visible_files if year_pattern.match(f))
        if year_count >= 2 and year_count >= len(visible_files) * 0.3:
            patterns.append("YYYY_*")

        # Pattern: Date prefix (2020-01-15_*, etc.)
        date_pattern = re.compile(r"^(19|20)\d{2}[-_](0[1-9]|1[0-2])[-_]")
        date_count = sum(1 for f in visible_files if date_pattern.match(f))
        if date_count >= 2 and date_count >= len(visible_files) * 0.3:
            patterns.append("YYYY-MM-DD_*")

        # Pattern: Common prefix (e.g., "invoice_*", "report_*")
        if len(visible_files) >= 3:
            # Find common prefix
            prefix = os.path.commonprefix(visible_files)
            if len(prefix) >= 3 and not prefix.isdigit():
                # Clean up prefix to end at word boundary
                prefix = re.sub(r"[^a-zA-Z0-9]+$", "", prefix)
                if len(prefix) >= 3:
                    patterns.append(f"{prefix}_*")

        # Pattern: Version suffix (_v1, _v2, _final, etc.)
        version_pattern = re.compile(r"_v\d+|_final|_draft|_rev\d*", re.IGNORECASE)
        version_count = sum(1 for f in visible_files if version_pattern.search(f))
        if version_count >= 2:
            patterns.append("*_vN")

        return patterns

    def _detect_date_structure(self, subfolders: list[str]) -> bool:
        """Detect if subfolders suggest date-based organization.

        Args:
            subfolders: List of subfolder names.

        Returns:
            True if date-based organization is detected.
        """
        if len(subfolders) < 2:
            return False

        # Check for year folders (2019, 2020, 2021, etc.)
        year_pattern = re.compile(r"^(19|20)\d{2}$")
        year_folders = [f for f in subfolders if year_pattern.match(f)]

        if len(year_folders) >= 2:
            return True

        # Check for month folders (01, 02, ... 12 or Jan, Feb, etc.)
        month_patterns = [
            re.compile(r"^(0[1-9]|1[0-2])$"),  # 01-12
            re.compile(r"^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)", re.I),
        ]

        for pattern in month_patterns:
            month_folders = [f for f in subfolders if pattern.match(f)]
            if len(month_folders) >= 3:
                return True

        return False

    def _generate_narration(
        self,
        snapshot: StructureSnapshot,
    ) -> tuple[str, str]:
        """Generate an LLM-powered narration of the organizational strategy.

        Uses T2 Smart model to summarize the structure in plain English.
        Falls back to keyword-based summary if LLM is unavailable.

        Args:
            snapshot: The analyzed structure snapshot.

        Returns:
            Tuple of (narration text, model used).
        """
        # Try LLM narration first if enabled and available
        if self._use_llm and self._llm_client is not None:
            try:
                if self._llm_client.is_ollama_available(timeout_s=5):
                    return self._narrate_with_llm(snapshot)
            except Exception:
                pass  # Fall through to keyword summary

        # Keyword-based fallback
        return self._narrate_with_keywords(snapshot), ""

    def _narrate_with_llm(
        self,
        snapshot: StructureSnapshot,
    ) -> tuple[str, str]:
        """Generate narration using T2 Smart LLM model.

        Args:
            snapshot: The analyzed structure snapshot.

        Returns:
            Tuple of (narration text, model used).
        """
        # Build structure summary for LLM (top 3 levels)
        summary_lines = []
        for folder in snapshot.folders:
            if folder.depth <= 2:
                indent = "  " * folder.depth
                file_info = f"{folder.file_count} files"
                if folder.file_types:
                    top_types = sorted(
                        folder.file_types.items(),
                        key=lambda x: x[1],
                        reverse=True,
                    )[:3]
                    types_str = ", ".join(f"{ext}" for ext, _ in top_types)
                    file_info = f"{folder.file_count} files ({types_str})"
                summary_lines.append(f"{indent}- {folder.name}: {file_info}")

        structure_text = "\n".join(summary_lines[:50])  # Limit context size

        # Build prompt
        prompt = None
        if self._prompt_registry is not None:
            try:
                prompt = self._prompt_registry.get(
                    "structure_narration",
                    structure_json=structure_text,
                )
            except (KeyError, FileNotFoundError):
                pass

        if prompt is None:
            prompt = f"""Summarize this organizational strategy in 2-3 sentences for a non-technical user.

Folder structure (top 3 levels with file counts):
{structure_text}

Describe what organizational approach is being used (e.g., by category, by date, by project).
Focus on the pattern, not the specific folder names.
Reply with just the summary text, no JSON."""

        # Select model (T2 Smart for complex reasoning)
        model = "qwen2.5-coder:14b"  # Default T2 Smart
        if self._model_router is not None:
            try:
                profile = TaskProfile(task_type="analyze", complexity="medium")
                decision = self._model_router.route(profile)
                model = decision.model
            except RuntimeError:
                pass  # Use default model

        # Generate response
        assert self._llm_client is not None
        response = self._llm_client.generate(prompt, model=model, temperature=0.3)

        if not response.success:
            return self._narrate_with_keywords(snapshot), ""

        # Clean up response (remove any JSON formatting, code blocks, etc.)
        text = response.text.strip()
        # Remove markdown code blocks if present
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(
                line for line in lines
                if not line.startswith("```")
            )
        text = text.strip()

        return text, response.model_used

    def _narrate_with_keywords(self, snapshot: StructureSnapshot) -> str:
        """Generate a keyword-based summary when LLM is unavailable.

        Args:
            snapshot: The analyzed structure snapshot.

        Returns:
            Summary text describing the organizational approach.
        """
        parts = []

        # Count folders with date structure
        date_folders = [f for f in snapshot.folders if f.has_date_structure]
        if date_folders:
            parts.append("date-based organization")

        # Check top-level folder count
        top_level = [f for f in snapshot.folders if f.depth == 1]
        if len(top_level) >= 3:
            parts.append(f"{len(top_level)} main categories")

        # Get dominant file types
        top_types = snapshot.get_top_file_types(3)
        if top_types:
            type_names = [t[0] for t in top_types]
            parts.append(f"primarily {', '.join(type_names)} files")

        # Build summary
        if parts:
            strategy = f"This folder structure uses {', '.join(parts)}."
        else:
            strategy = "This folder structure contains organized documents."

        strategy += f" Total: {snapshot.total_folders} folders, {snapshot.total_files} files."

        return strategy


def analyze_structure(
    root_path: str | Path,
    max_depth: int = 4,
    output_path: str | Path | None = None,
    llm_client: "LLMClient | None" = None,
    model_router: "ModelRouter | None" = None,
    use_llm: bool = True,
) -> StructureSnapshot:
    """Convenience function to analyze a directory structure.

    Args:
        root_path: Root directory to analyze.
        max_depth: Maximum depth to descend (default: 4).
        output_path: Optional path to save the snapshot.
        llm_client: Optional LLM client for narration.
        model_router: Optional model router for tier selection.
        use_llm: Whether to use LLM for narration.

    Returns:
        StructureSnapshot containing analyzed data.
    """
    analyzer = StructureAnalyzer(
        llm_client=llm_client,
        model_router=model_router,
        use_llm=use_llm,
    )

    snapshot = analyzer.analyze(root_path, max_depth=max_depth)

    if output_path is not None:
        snapshot.save(output_path)

    return snapshot


def load_structure(
    path: str | Path = DEFAULT_STRUCTURE_OUTPUT_PATH,
) -> StructureSnapshot:
    """Load a previously saved structure snapshot.

    Args:
        path: Path to the snapshot JSON file.

    Returns:
        StructureSnapshot loaded from file.
    """
    return StructureSnapshot.load(path)
