"""File DNA module for content-aware file intelligence.

Computes file fingerprints, extracts tags using LLM with keyword fallback,
and maintains a registry of known files for duplicate detection and provenance.

The FileDNA contains:
- SHA-256 hash for exact matching
- Content summary (first 500 chars) for fuzzy matching
- Auto-extracted tags from LLM or keyword analysis
- Provenance tracking (origin, first seen, routed to)
- Duplicate relationship markers

Example usage:
    registry = DNARegistry("/path/to/.organizer/agent/file_dna.json")
    dna = registry.register_file("/path/to/document.pdf", origin="inbox")
    print(dna.auto_tags)  # ["tax_doc", "2024", "IRS"]
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from organizer.model_router import TaskProfile

if TYPE_CHECKING:
    from organizer.llm_client import LLMClient
    from organizer.model_router import ModelRouter
    from organizer.prompt_registry import PromptRegistry


# Hash computation chunk size (8KB)
HASH_CHUNK_SIZE = 8 * 1024

# Default DNA registry path
DEFAULT_DNA_REGISTRY_PATH = ".organizer/agent/file_dna.json"


def _now_iso() -> str:
    """Get current timestamp in ISO format."""
    return datetime.now().isoformat()


@dataclass
class FileDNA:
    """DNA profile of a file for intelligence and deduplication.

    The FileDNA captures the essential characteristics of a file that enable:
    - Exact duplicate detection (via sha256_hash)
    - Fuzzy matching (via content_summary)
    - Content-aware classification (via auto_tags)
    - Provenance tracking (via origin, first_seen_at, routed_to)
    - Relationship linking (via duplicate_of)

    Attributes:
        file_path: Full path to the file.
        sha256_hash: SHA-256 hash of file contents.
        content_summary: First 500 characters of text content.
        auto_tags: List of extracted tags (document_type, year, orgs, etc.).
        origin: How the file entered the system ("inbox", "scan", "import").
        first_seen_at: ISO timestamp when file was first registered.
        routed_to: Destination path if file was routed.
        duplicate_of: Path to canonical file if this is a duplicate.
        model_used: LLM model used for tag extraction (empty if keyword fallback).
    """

    file_path: str
    sha256_hash: str
    content_summary: str = ""
    auto_tags: list[str] = field(default_factory=list)
    origin: str = ""
    first_seen_at: str = ""
    routed_to: str = ""
    duplicate_of: str = ""
    model_used: str = ""

    def __post_init__(self) -> None:
        """Set default timestamp if not provided."""
        if not self.first_seen_at:
            self.first_seen_at = _now_iso()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "file_path": self.file_path,
            "sha256_hash": self.sha256_hash,
            "content_summary": self.content_summary,
            "auto_tags": self.auto_tags.copy(),
            "origin": self.origin,
            "first_seen_at": self.first_seen_at,
            "routed_to": self.routed_to,
            "duplicate_of": self.duplicate_of,
            "model_used": self.model_used,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FileDNA":
        """Create FileDNA from dictionary."""
        return cls(
            file_path=data.get("file_path", ""),
            sha256_hash=data.get("sha256_hash", ""),
            content_summary=data.get("content_summary", ""),
            auto_tags=data.get("auto_tags", []).copy(),
            origin=data.get("origin", ""),
            first_seen_at=data.get("first_seen_at", ""),
            routed_to=data.get("routed_to", ""),
            duplicate_of=data.get("duplicate_of", ""),
            model_used=data.get("model_used", ""),
        )


@dataclass
class TagExtractionResult:
    """Result of tag extraction from file content.

    Attributes:
        document_type: Detected document type (e.g., "tax_return", "invoice").
        year: Extracted year if present.
        organizations: List of organizations mentioned.
        people: List of people mentioned.
        topics: List of topics detected.
        suggested_tags: Combined list of all tags.
        model_used: LLM model used (empty if keyword fallback).
        used_keyword_fallback: Whether keyword fallback was used.
        confidence: Confidence in the extraction (0.0-1.0).
    """

    document_type: str = ""
    year: str = ""
    organizations: list[str] = field(default_factory=list)
    people: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    suggested_tags: list[str] = field(default_factory=list)
    model_used: str = ""
    used_keyword_fallback: bool = False
    confidence: float = 0.5

    def to_tags_list(self) -> list[str]:
        """Convert extraction result to a flat list of tags."""
        tags = list(self.suggested_tags)
        if self.document_type and self.document_type not in tags:
            tags.insert(0, self.document_type)
        if self.year and self.year not in tags:
            tags.append(self.year)
        for org in self.organizations:
            if org and org not in tags:
                tags.append(org)
        return tags


def compute_file_hash(filepath: str | Path) -> str:
    """Compute SHA-256 hash of a file in 8KB chunks.

    Reads the file in chunks to handle large files efficiently without
    loading the entire content into memory.

    Args:
        filepath: Path to the file to hash.

    Returns:
        Hexadecimal SHA-256 hash string.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        PermissionError: If the file can't be read.
        IsADirectoryError: If the path is a directory.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
    if path.is_dir():
        raise IsADirectoryError(f"Path is a directory: {filepath}")

    hasher = hashlib.sha256()

    with open(path, "rb") as f:
        while chunk := f.read(HASH_CHUNK_SIZE):
            hasher.update(chunk)

    return hasher.hexdigest()


def get_content_preview(filepath: str | Path, max_chars: int = 500) -> str:
    """Get a text preview of file content.

    Attempts to read the file as text and returns the first max_chars.
    Returns empty string for binary files or if reading fails.

    Args:
        filepath: Path to the file.
        max_chars: Maximum characters to return.

    Returns:
        Content preview string, or empty string if unreadable.
    """
    path = Path(filepath)

    # Skip known binary extensions
    binary_extensions = {
        ".pdf", ".doc", ".docx", ".xls", ".xlsx",
        ".ppt", ".pptx", ".zip", ".tar", ".gz",
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff",
        ".mp3", ".mp4", ".avi", ".mov", ".wmv", ".flv",
        ".exe", ".dll", ".so", ".dylib",
        ".bin", ".dat", ".db", ".sqlite",
    }

    if path.suffix.lower() in binary_extensions:
        return f"[Binary file: {path.suffix}]"

    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read(max_chars)
            # Clean up whitespace but preserve basic structure
            content = " ".join(content.split())
            return content[:max_chars]
    except (OSError, UnicodeDecodeError):
        return ""


def extract_tags(
    filename: str,
    content_text: str,
    llm_client: "LLMClient | None" = None,
    model_router: "ModelRouter | None" = None,
    prompt_registry: "PromptRegistry | None" = None,
    use_llm: bool = True,
) -> TagExtractionResult:
    """Extract structured tags from a file using LLM or keyword fallback.

    Calls T1 Fast model with a prompt to extract structured metadata.
    Falls back to regex year extraction + keyword matching if LLM unavailable.

    Args:
        filename: Name of the file.
        content_text: Text content preview (first 500 chars).
        llm_client: Optional LLM client for T1 extraction.
        model_router: Optional model router for tier selection.
        prompt_registry: Optional registry for loading prompts.
        use_llm: Whether to attempt LLM extraction.

    Returns:
        TagExtractionResult with extracted metadata.
    """
    # Try LLM extraction first if enabled and available
    if use_llm and llm_client is not None:
        try:
            if llm_client.is_ollama_available(timeout_s=5):
                return _extract_tags_with_llm(
                    filename,
                    content_text,
                    llm_client,
                    model_router,
                    prompt_registry,
                )
        except Exception:
            pass  # Fall through to keyword fallback

    # Keyword fallback
    return _extract_tags_with_keywords(filename, content_text)


def _extract_tags_with_llm(
    filename: str,
    content_text: str,
    llm_client: "LLMClient",
    model_router: "ModelRouter | None" = None,
    prompt_registry: "PromptRegistry | None" = None,
) -> TagExtractionResult:
    """Extract tags using T1 Fast LLM model.

    Args:
        filename: Name of the file.
        content_text: Content preview text.
        llm_client: LLM client for generation.
        model_router: Optional router for model selection.
        prompt_registry: Optional prompt registry.

    Returns:
        TagExtractionResult from LLM extraction.
    """
    # Build prompt
    prompt = None
    if prompt_registry is not None:
        try:
            prompt = prompt_registry.get(
                "extract_tags",
                filename=filename,
                first_500_chars=content_text[:500],
            )
        except (KeyError, FileNotFoundError):
            pass

    if prompt is None:
        # Use inline prompt following PRD specification
        prompt = f"""Extract structured tags from file '{filename}', content: '{content_text[:500]}'.

Reply with JSON only:
{{
    "document_type": "type of document (e.g., tax_return, invoice, resume, medical_record)",
    "year": "extracted year if present (e.g., 2024)",
    "organizations": ["list of organizations mentioned"],
    "people": ["list of people mentioned"],
    "topics": ["list of main topics"],
    "suggested_tags": ["combined list of all relevant tags"],
    "confidence": 0.0 to 1.0
}}"""

    # Select model (T1 Fast for high-volume tag extraction)
    model = "llama3.1:8b-instruct-q8_0"  # Default T1 Fast
    if model_router is not None:
        try:
            profile = TaskProfile(task_type="enrich", complexity="low")
            decision = model_router.route(profile)
            model = decision.model
        except RuntimeError:
            pass  # Use default model

    # Generate response
    response = llm_client.generate(prompt, model=model, temperature=0.0)

    if not response.success:
        # Fall back to keywords if LLM fails
        return _extract_tags_with_keywords(filename, content_text)

    # Parse JSON response
    data = _parse_llm_json_response(response.text)
    if data is None:
        return _extract_tags_with_keywords(filename, content_text)

    return TagExtractionResult(
        document_type=data.get("document_type", ""),
        year=str(data.get("year", "")),
        organizations=data.get("organizations", []),
        people=data.get("people", []),
        topics=data.get("topics", []),
        suggested_tags=data.get("suggested_tags", []),
        model_used=response.model_used,
        used_keyword_fallback=False,
        confidence=_extract_confidence(data),
    )


def _extract_tags_with_keywords(
    filename: str,
    content_text: str,
) -> TagExtractionResult:
    """Extract tags using regex and keyword matching.

    Fallback when LLM is unavailable. Extracts:
    - Year from filename using regex
    - Document type from keyword matching
    - Organizations from common patterns

    Args:
        filename: Name of the file.
        content_text: Content preview text.

    Returns:
        TagExtractionResult from keyword extraction.
    """
    tags: list[str] = []
    document_type = ""
    year = ""
    organizations: list[str] = []

    # Combine filename and content for matching
    combined = f"{filename} {content_text}".lower()

    # Extract year from filename (1990-2030)
    year_pattern = re.compile(r"(19[89][0-9]|20[0-2][0-9]|2030)")
    year_match = year_pattern.search(filename)
    if year_match:
        year = year_match.group(1)
        tags.append(year)

    # Document type keywords
    doc_type_keywords = {
        "tax": "tax_doc",
        "invoice": "invoice",
        "receipt": "receipt",
        "resume": "resume",
        "cv ": "resume",
        "contract": "contract",
        "medical": "medical_record",
        "health": "medical_record",
        "bank": "bank_statement",
        "statement": "statement",
        "va ": "va_document",
        "veteran": "va_document",
        "claim": "claim",
        "letter": "correspondence",
    }

    for keyword, doc_type in doc_type_keywords.items():
        if keyword in combined:
            document_type = doc_type
            if doc_type not in tags:
                tags.append(doc_type)
            break

    # Organization patterns
    org_patterns = {
        r"\birs\b": "IRS",
        r"\bssa\b|social.?security": "SSA",
        r"\bva\b(?!\w)|veterans?.?affairs": "VA",
        r"amazon": "Amazon",
        r"chase": "Chase",
        r"wells.?fargo": "Wells Fargo",
        r"bank.?of.?america|bofa": "Bank of America",
        r"verizon": "Verizon",
        r"at.?&.?t|att\b": "AT&T",
        r"apple(?!\s*inc)": "Apple",
        r"google": "Google",
        r"microsoft": "Microsoft",
    }

    for pattern, org in org_patterns.items():
        if re.search(pattern, combined, re.IGNORECASE):
            organizations.append(org)
            if org not in tags:
                tags.append(org)

    return TagExtractionResult(
        document_type=document_type,
        year=year,
        organizations=organizations,
        people=[],
        topics=[],
        suggested_tags=tags,
        model_used="",
        used_keyword_fallback=True,
        confidence=0.7 if tags else 0.3,
    )


def _parse_llm_json_response(text: str) -> dict[str, Any] | None:
    """Parse JSON from LLM response, handling common formatting issues.

    Args:
        text: Raw LLM response text.

    Returns:
        Parsed JSON dict, or None if parsing fails.
    """
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to extract JSON from markdown code block
    code_block_pattern = r"```(?:json)?\s*(\{.*?\})\s*```"
    match = re.search(code_block_pattern, text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find JSON object in text
    brace_pattern = r"\{[^{}]*\}"
    matches = re.findall(brace_pattern, text)
    for m in matches:
        try:
            return json.loads(m)
        except json.JSONDecodeError:
            continue

    return None


def _extract_confidence(data: dict[str, Any]) -> float:
    """Extract confidence value from parsed JSON response.

    Args:
        data: Parsed JSON response.

    Returns:
        Confidence value (0.0-1.0), or 0.5 if not found.
    """
    confidence = data.get("confidence")
    if isinstance(confidence, (int, float)):
        return max(0.0, min(1.0, float(confidence)))
    return 0.5


class DNARegistry:
    """Registry for storing and retrieving FileDNA records.

    Provides persistent storage for file DNA profiles, enabling:
    - Fast lookup by path or hash
    - Duplicate detection across the file system
    - Provenance tracking for filed documents
    - Incremental updates as files are processed

    Example:
        registry = DNARegistry("/path/to/.organizer/agent/file_dna.json")
        dna = registry.register_file("/path/to/doc.pdf", origin="inbox")
        duplicates = registry.find_by_hash(dna.sha256_hash)
    """

    def __init__(
        self,
        registry_path: str | Path = DEFAULT_DNA_REGISTRY_PATH,
        llm_client: "LLMClient | None" = None,
        model_router: "ModelRouter | None" = None,
        prompt_registry: "PromptRegistry | None" = None,
        use_llm: bool = True,
    ):
        """Initialize the DNA registry.

        Args:
            registry_path: Path to the JSON registry file.
            llm_client: Optional LLM client for tag extraction.
            model_router: Optional model router for tier selection.
            prompt_registry: Optional prompt registry for loading prompts.
            use_llm: Whether to use LLM for tag extraction.
        """
        self._registry_path = Path(registry_path)
        self._llm_client = llm_client
        self._model_router = model_router
        self._prompt_registry = prompt_registry
        self._use_llm = use_llm

        # In-memory cache: path -> FileDNA
        self._by_path: dict[str, FileDNA] = {}
        # Hash index: hash -> list of paths with that hash
        self._by_hash: dict[str, list[str]] = {}

        # Load existing registry if present
        self._load()

    def _load(self) -> None:
        """Load registry from disk."""
        if not self._registry_path.exists():
            return

        try:
            with open(self._registry_path) as f:
                data = json.load(f)

            for entry in data.get("entries", []):
                dna = FileDNA.from_dict(entry)
                self._by_path[dna.file_path] = dna
                if dna.sha256_hash:
                    if dna.sha256_hash not in self._by_hash:
                        self._by_hash[dna.sha256_hash] = []
                    self._by_hash[dna.sha256_hash].append(dna.file_path)
        except (json.JSONDecodeError, OSError):
            # Start fresh if file is corrupted
            self._by_path = {}
            self._by_hash = {}

    def _save(self) -> None:
        """Save registry to disk."""
        # Ensure parent directory exists
        self._registry_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": "1.0",
            "updated_at": _now_iso(),
            "entry_count": len(self._by_path),
            "entries": [dna.to_dict() for dna in self._by_path.values()],
        }

        with open(self._registry_path, "w") as f:
            json.dump(data, f, indent=2)

    def register_file(
        self,
        file_path: str | Path,
        origin: str = "",
        compute_tags: bool = True,
    ) -> FileDNA:
        """Register a file and compute its DNA.

        Computes hash, extracts content preview, and optionally extracts tags.
        If the file is already registered, updates the existing record.

        Args:
            file_path: Path to the file to register.
            origin: How the file entered the system ("inbox", "scan", "import").
            compute_tags: Whether to extract tags from content.

        Returns:
            FileDNA record for the registered file.

        Raises:
            FileNotFoundError: If the file doesn't exist.
        """
        path = Path(file_path)
        str_path = str(path.resolve())

        # Compute hash
        file_hash = compute_file_hash(path)

        # Get content preview
        content = get_content_preview(path)

        # Extract tags if requested
        auto_tags: list[str] = []
        model_used = ""
        if compute_tags:
            result = extract_tags(
                filename=path.name,
                content_text=content,
                llm_client=self._llm_client,
                model_router=self._model_router,
                prompt_registry=self._prompt_registry,
                use_llm=self._use_llm,
            )
            auto_tags = result.to_tags_list()
            model_used = result.model_used

        # Check if already registered
        existing = self._by_path.get(str_path)
        if existing:
            # Update existing record
            existing.sha256_hash = file_hash
            existing.content_summary = content
            existing.auto_tags = auto_tags
            existing.model_used = model_used
            # Preserve original origin and first_seen_at
            self._save()
            return existing

        # Create new record
        dna = FileDNA(
            file_path=str_path,
            sha256_hash=file_hash,
            content_summary=content,
            auto_tags=auto_tags,
            origin=origin,
            model_used=model_used,
        )

        # Add to indices
        self._by_path[str_path] = dna
        if file_hash not in self._by_hash:
            self._by_hash[file_hash] = []
        self._by_hash[file_hash].append(str_path)

        self._save()
        return dna

    def get_by_path(self, file_path: str | Path) -> FileDNA | None:
        """Look up DNA by file path.

        Args:
            file_path: Path to look up.

        Returns:
            FileDNA if found, None otherwise.
        """
        str_path = str(Path(file_path).resolve())
        return self._by_path.get(str_path)

    def find_by_hash(self, sha256_hash: str) -> list[FileDNA]:
        """Find all files with a given hash.

        Args:
            sha256_hash: SHA-256 hash to search for.

        Returns:
            List of FileDNA records with matching hash.
        """
        paths = self._by_hash.get(sha256_hash, [])
        return [self._by_path[p] for p in paths if p in self._by_path]

    def update_routed_to(self, file_path: str | Path, destination: str) -> bool:
        """Update the routed_to field for a file.

        Args:
            file_path: Path to the file.
            destination: Destination path it was routed to.

        Returns:
            True if updated, False if file not found.
        """
        str_path = str(Path(file_path).resolve())
        dna = self._by_path.get(str_path)
        if dna is None:
            return False

        dna.routed_to = destination
        self._save()
        return True

    def mark_duplicate(
        self, file_path: str | Path, canonical_path: str | Path
    ) -> bool:
        """Mark a file as a duplicate of another.

        Args:
            file_path: Path to the duplicate file.
            canonical_path: Path to the canonical file.

        Returns:
            True if marked, False if file not found.
        """
        str_path = str(Path(file_path).resolve())
        canonical_str = str(Path(canonical_path).resolve())

        dna = self._by_path.get(str_path)
        if dna is None:
            return False

        dna.duplicate_of = canonical_str
        self._save()
        return True

    def get_all(self) -> list[FileDNA]:
        """Get all registered DNA records.

        Returns:
            List of all FileDNA records.
        """
        return list(self._by_path.values())

    def get_count(self) -> int:
        """Get the number of registered files.

        Returns:
            Number of FileDNA records.
        """
        return len(self._by_path)

    def remove(self, file_path: str | Path) -> bool:
        """Remove a file from the registry.

        Args:
            file_path: Path to remove.

        Returns:
            True if removed, False if not found.
        """
        str_path = str(Path(file_path).resolve())
        dna = self._by_path.pop(str_path, None)
        if dna is None:
            return False

        # Remove from hash index
        if dna.sha256_hash in self._by_hash:
            paths = self._by_hash[dna.sha256_hash]
            if str_path in paths:
                paths.remove(str_path)
                if not paths:
                    del self._by_hash[dna.sha256_hash]

        self._save()
        return True

    def clear(self) -> None:
        """Clear all entries from the registry."""
        self._by_path.clear()
        self._by_hash.clear()
        self._save()

    def find_duplicates(self) -> dict[str, list[FileDNA]]:
        """Find all files that have duplicates (same hash, multiple paths).

        Returns:
            Dictionary mapping hash to list of FileDNA records with that hash.
            Only includes hashes with more than one file.
        """
        return {
            h: [self._by_path[p] for p in paths if p in self._by_path]
            for h, paths in self._by_hash.items()
            if len(paths) > 1
        }

    def search_by_tag(self, tag: str) -> list[FileDNA]:
        """Search for files by tag.

        Args:
            tag: Tag to search for (case-insensitive).

        Returns:
            List of FileDNA records containing the tag.
        """
        tag_lower = tag.lower()
        return [
            dna for dna in self._by_path.values()
            if any(t.lower() == tag_lower for t in dna.auto_tags)
        ]

    def search_by_keyword(self, keyword: str) -> list[FileDNA]:
        """Search for files by keyword in path, content, or tags.

        Args:
            keyword: Keyword to search for (case-insensitive).

        Returns:
            List of FileDNA records matching the keyword.
        """
        keyword_lower = keyword.lower()
        results = []

        for dna in self._by_path.values():
            # Check path
            if keyword_lower in dna.file_path.lower():
                results.append(dna)
                continue
            # Check content summary
            if keyword_lower in dna.content_summary.lower():
                results.append(dna)
                continue
            # Check tags
            if any(keyword_lower in t.lower() for t in dna.auto_tags):
                results.append(dna)
                continue

        return results
