"""LLM-powered metadata enrichment service.

Extracts structured metadata from file content using LLM with keyword fallback.
Enrichment data powers natural language search and file intelligence features.

The enrichment process extracts:
- Document type classification
- Date references within content
- People and organizations mentioned
- Key topics and themes
- Plain-English summary (1-2 sentences)
- Suggested tags for categorization

Example usage:
    enricher = LLMEnricher()
    result = enricher.enrich_file("invoice.pdf", "Invoice from Acme Corp...")
    print(result.summary)  # "Invoice from Acme Corp for $500, dated March 2024"
    print(result.organizations)  # ["Acme Corp"]
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from organizer.file_dna import compute_file_hash, get_content_preview
from organizer.model_router import TaskProfile

if TYPE_CHECKING:
    from organizer.llm_client import LLMClient
    from organizer.model_router import ModelRouter
    from organizer.prompt_registry import PromptRegistry

# Default paths
DEFAULT_ENRICHMENT_CACHE_PATH = ".organizer/agent/enrichment_cache.json"


def _now_iso() -> str:
    """Get current timestamp in ISO format."""
    return datetime.now().isoformat()


@dataclass
class FileEnrichment:
    """Enriched metadata extracted from file content.

    Contains structured metadata that enables natural language search
    and provides context about the document's content.

    Attributes:
        document_type: Type of document (e.g., "invoice", "tax_return", "contract").
        date_references: List of dates found in content (e.g., ["March 2024", "2023-12-15"]).
        people: List of people mentioned in the document.
        organizations: List of organizations mentioned.
        key_topics: Main topics or themes of the document.
        summary: Plain-English summary (1-2 sentences).
        suggested_tags: Combined list of relevant tags for categorization.
        confidence: Confidence in the enrichment (0.0-1.0).
        model_used: LLM model used for enrichment (empty if keyword fallback).
        used_keyword_fallback: Whether keyword fallback was used.
        enriched_at: ISO timestamp when enrichment was performed.
        duration_ms: Time taken for enrichment in milliseconds.
    """

    document_type: str = ""
    date_references: list[str] = field(default_factory=list)
    people: list[str] = field(default_factory=list)
    organizations: list[str] = field(default_factory=list)
    key_topics: list[str] = field(default_factory=list)
    summary: str = ""
    suggested_tags: list[str] = field(default_factory=list)
    confidence: float = 0.5
    model_used: str = ""
    used_keyword_fallback: bool = False
    enriched_at: str = ""
    duration_ms: int = 0

    def __post_init__(self) -> None:
        """Set default timestamp if not provided."""
        if not self.enriched_at:
            self.enriched_at = _now_iso()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "document_type": self.document_type,
            "date_references": list(self.date_references),
            "people": list(self.people),
            "organizations": list(self.organizations),
            "key_topics": list(self.key_topics),
            "summary": self.summary,
            "suggested_tags": list(self.suggested_tags),
            "confidence": self.confidence,
            "model_used": self.model_used,
            "used_keyword_fallback": self.used_keyword_fallback,
            "enriched_at": self.enriched_at,
            "duration_ms": self.duration_ms,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FileEnrichment":
        """Create FileEnrichment from dictionary."""
        return cls(
            document_type=data.get("document_type", ""),
            date_references=list(data.get("date_references", [])),
            people=list(data.get("people", [])),
            organizations=list(data.get("organizations", [])),
            key_topics=list(data.get("key_topics", [])),
            summary=data.get("summary", ""),
            suggested_tags=list(data.get("suggested_tags", [])),
            confidence=data.get("confidence", 0.5),
            model_used=data.get("model_used", ""),
            used_keyword_fallback=data.get("used_keyword_fallback", False),
            enriched_at=data.get("enriched_at", ""),
            duration_ms=data.get("duration_ms", 0),
        )

    def matches_search(self, query: str) -> bool:
        """Check if this enrichment matches a search query.

        Searches across all text fields: summary, document_type,
        organizations, people, topics, and tags.

        Args:
            query: Search query string.

        Returns:
            True if any field contains the query (case-insensitive).
        """
        query_lower = query.lower()

        # Check summary
        if query_lower in self.summary.lower():
            return True

        # Check document type
        if query_lower in self.document_type.lower():
            return True

        # Check organizations
        for org in self.organizations:
            if query_lower in org.lower():
                return True

        # Check people
        for person in self.people:
            if query_lower in person.lower():
                return True

        # Check topics
        for topic in self.key_topics:
            if query_lower in topic.lower():
                return True

        # Check tags
        for tag in self.suggested_tags:
            if query_lower in tag.lower():
                return True

        # Check date references
        for date_ref in self.date_references:
            if query_lower in date_ref.lower():
                return True

        return False


@dataclass
class EnrichmentCacheEntry:
    """Cache entry for file enrichment.

    Attributes:
        file_hash: SHA-256 hash of the file.
        file_path: Path to the file when enriched.
        enrichment: The enrichment data.
        cached_at: ISO timestamp when cached.
    """

    file_hash: str
    file_path: str
    enrichment: FileEnrichment
    cached_at: str = ""

    def __post_init__(self) -> None:
        """Set default timestamp if not provided."""
        if not self.cached_at:
            self.cached_at = _now_iso()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "file_hash": self.file_hash,
            "file_path": self.file_path,
            "enrichment": self.enrichment.to_dict(),
            "cached_at": self.cached_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EnrichmentCacheEntry":
        """Create EnrichmentCacheEntry from dictionary."""
        return cls(
            file_hash=data.get("file_hash", ""),
            file_path=data.get("file_path", ""),
            enrichment=FileEnrichment.from_dict(data.get("enrichment", {})),
            cached_at=data.get("cached_at", ""),
        )


class EnrichmentCache:
    """Cache for file enrichments, keyed by file hash.

    Prevents re-enriching files that have already been processed.
    Uses SHA-256 hash as key so content changes trigger re-enrichment.

    Example:
        cache = EnrichmentCache()
        enrichment = cache.get("abc123hash")  # Returns cached or None
        cache.set("abc123hash", "/path/to/file.pdf", enrichment)
    """

    def __init__(self, cache_path: str | Path = DEFAULT_ENRICHMENT_CACHE_PATH):
        """Initialize the enrichment cache.

        Args:
            cache_path: Path to the JSON cache file.
        """
        self._cache_path = Path(cache_path)
        self._entries: dict[str, EnrichmentCacheEntry] = {}
        self._load()

    def _load(self) -> None:
        """Load cache from disk."""
        if not self._cache_path.exists():
            return

        try:
            with open(self._cache_path) as f:
                data = json.load(f)

            for entry_data in data.get("entries", []):
                entry = EnrichmentCacheEntry.from_dict(entry_data)
                self._entries[entry.file_hash] = entry
        except (json.JSONDecodeError, OSError):
            # Start fresh if file is corrupted
            self._entries = {}

    def _save(self) -> None:
        """Save cache to disk."""
        # Ensure parent directory exists
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": "1.0",
            "updated_at": _now_iso(),
            "entry_count": len(self._entries),
            "entries": [entry.to_dict() for entry in self._entries.values()],
        }

        with open(self._cache_path, "w") as f:
            json.dump(data, f, indent=2)

    def get(self, file_hash: str) -> FileEnrichment | None:
        """Get cached enrichment by file hash.

        Args:
            file_hash: SHA-256 hash of the file.

        Returns:
            FileEnrichment if cached, None otherwise.
        """
        entry = self._entries.get(file_hash)
        return entry.enrichment if entry else None

    def set(
        self,
        file_hash: str,
        file_path: str,
        enrichment: FileEnrichment,
    ) -> None:
        """Cache an enrichment result.

        Args:
            file_hash: SHA-256 hash of the file.
            file_path: Path to the file.
            enrichment: The enrichment data to cache.
        """
        self._entries[file_hash] = EnrichmentCacheEntry(
            file_hash=file_hash,
            file_path=file_path,
            enrichment=enrichment,
        )
        self._save()

    def has(self, file_hash: str) -> bool:
        """Check if a file hash is cached.

        Args:
            file_hash: SHA-256 hash to check.

        Returns:
            True if cached, False otherwise.
        """
        return file_hash in self._entries

    def remove(self, file_hash: str) -> bool:
        """Remove an entry from the cache.

        Args:
            file_hash: SHA-256 hash to remove.

        Returns:
            True if removed, False if not found.
        """
        if file_hash in self._entries:
            del self._entries[file_hash]
            self._save()
            return True
        return False

    def clear(self) -> None:
        """Clear all entries from the cache."""
        self._entries.clear()
        self._save()

    def get_count(self) -> int:
        """Get the number of cached entries.

        Returns:
            Number of cache entries.
        """
        return len(self._entries)

    def get_all(self) -> list[EnrichmentCacheEntry]:
        """Get all cached entries.

        Returns:
            List of all cache entries.
        """
        return list(self._entries.values())


def enrich_file(
    filename: str,
    content_text: str,
    llm_client: "LLMClient | None" = None,
    model_router: "ModelRouter | None" = None,
    prompt_registry: "PromptRegistry | None" = None,
    use_llm: bool = True,
) -> FileEnrichment:
    """Extract structured metadata from file content.

    Uses T2 Smart model for accurate structured extraction.
    Falls back to keyword/regex extraction if LLM unavailable.

    Args:
        filename: Name of the file.
        content_text: Text content to analyze (first 500+ chars recommended).
        llm_client: Optional LLM client for T2 extraction.
        model_router: Optional model router for tier selection.
        prompt_registry: Optional registry for loading prompts.
        use_llm: Whether to attempt LLM extraction.

    Returns:
        FileEnrichment with extracted metadata.
    """
    start_time = time.time()

    # Try LLM enrichment first if enabled and available
    if use_llm and llm_client is not None:
        try:
            if llm_client.is_ollama_available(timeout_s=5):
                result = _enrich_with_llm(
                    filename,
                    content_text,
                    llm_client,
                    model_router,
                    prompt_registry,
                )
                result.duration_ms = int((time.time() - start_time) * 1000)
                return result
        except Exception:
            pass  # Fall through to keyword fallback

    # Keyword fallback
    result = _enrich_with_keywords(filename, content_text)
    result.duration_ms = int((time.time() - start_time) * 1000)
    return result


def _enrich_with_llm(
    filename: str,
    content_text: str,
    llm_client: "LLMClient",
    model_router: "ModelRouter | None" = None,
    prompt_registry: "PromptRegistry | None" = None,
) -> FileEnrichment:
    """Extract enrichment using T2 Smart LLM model.

    Args:
        filename: Name of the file.
        content_text: Content text to analyze.
        llm_client: LLM client for generation.
        model_router: Optional router for model selection.
        prompt_registry: Optional prompt registry.

    Returns:
        FileEnrichment from LLM extraction.
    """
    # Build prompt
    prompt = None
    if prompt_registry is not None:
        try:
            prompt = prompt_registry.get(
                "extract_metadata",
                filename=filename,
                content=content_text[:1000],  # Use more content for enrichment
            )
        except (KeyError, FileNotFoundError):
            pass

    if prompt is None:
        # Use inline prompt matching PRD specification
        prompt = f"""Extract structured metadata from this file:

Filename: {filename}
Content: {content_text[:1000]}

Reply with JSON only:
{{
    "document_type": "type of document (e.g., invoice, tax_return, contract, resume)",
    "date_references": ["list of dates found (e.g., 'March 2024', '2023-12-15')"],
    "people": ["list of people mentioned"],
    "organizations": ["list of organizations mentioned"],
    "key_topics": ["main topics or themes"],
    "summary": "1-2 sentence summary of the document",
    "suggested_tags": ["combined list of relevant tags"],
    "confidence": 0.0 to 1.0
}}"""

    # Select model (T2 Smart for structured extraction - needs accuracy)
    model = "qwen2.5-coder:14b"  # Default T2 Smart
    if model_router is not None:
        try:
            profile = TaskProfile(task_type="enrich", complexity="medium")
            decision = model_router.route(profile)
            model = decision.model
        except RuntimeError:
            pass  # Use default model

    # Generate response
    response = llm_client.generate(prompt, model=model, temperature=0.0)

    if not response.success:
        # Fall back to keywords if LLM fails
        return _enrich_with_keywords(filename, content_text)

    # Parse JSON response
    data = _parse_llm_json_response(response.text)
    if data is None:
        return _enrich_with_keywords(filename, content_text)

    return FileEnrichment(
        document_type=data.get("document_type", ""),
        date_references=_ensure_list(data.get("date_references", [])),
        people=_ensure_list(data.get("people", [])),
        organizations=_ensure_list(data.get("organizations", [])),
        key_topics=_ensure_list(data.get("key_topics", [])),
        summary=data.get("summary", ""),
        suggested_tags=_ensure_list(data.get("suggested_tags", [])),
        confidence=_extract_confidence(data),
        model_used=response.model_used,
        used_keyword_fallback=False,
    )


def _enrich_with_keywords(
    filename: str,
    content_text: str,
) -> FileEnrichment:
    """Extract enrichment using regex and keyword matching.

    Fallback when LLM is unavailable. Extracts:
    - Document type from keyword matching
    - Dates from various formats
    - Organizations from common patterns
    - Basic summary from filename

    Args:
        filename: Name of the file.
        content_text: Content text to analyze.

    Returns:
        FileEnrichment from keyword extraction.
    """
    combined = f"{filename} {content_text}".lower()
    combined_original = f"{filename} {content_text}"

    # Extract document type
    document_type = _extract_document_type(combined)

    # Extract dates
    date_references = _extract_dates(combined_original)

    # Extract organizations
    organizations = _extract_organizations(combined)

    # Extract people (basic patterns)
    people = _extract_people(combined_original)

    # Extract topics from keywords
    topics = _extract_topics(combined)

    # Generate basic summary
    summary = _generate_keyword_summary(filename, document_type, organizations)

    # Combine tags
    tags = _build_tags(document_type, date_references, organizations, topics)

    # Calculate confidence based on what was extracted
    confidence = _calculate_keyword_confidence(
        document_type, date_references, organizations
    )

    return FileEnrichment(
        document_type=document_type,
        date_references=date_references,
        people=people,
        organizations=organizations,
        key_topics=topics,
        summary=summary,
        suggested_tags=tags,
        confidence=confidence,
        model_used="",
        used_keyword_fallback=True,
    )


def _extract_document_type(text: str) -> str:
    """Extract document type from text using keyword matching."""
    doc_type_keywords = {
        "invoice": "invoice",
        "receipt": "receipt",
        "tax return": "tax_return",
        "tax": "tax_document",
        "1099": "tax_form",
        "w-2": "tax_form",
        "w2": "tax_form",
        "1040": "tax_form",
        "resume": "resume",
        "cv": "resume",
        "curriculum vitae": "resume",
        "contract": "contract",
        "agreement": "agreement",
        "medical": "medical_record",
        "health": "health_document",
        "prescription": "prescription",
        "bank statement": "bank_statement",
        "statement": "statement",
        "va ": "va_document",
        "veteran": "va_document",
        "claim": "claim",
        "letter": "correspondence",
        "bill": "bill",
        "utility": "utility_bill",
        "insurance": "insurance_document",
        "policy": "policy_document",
    }

    for keyword, doc_type in doc_type_keywords.items():
        if keyword in text:
            return doc_type

    return "document"


def _extract_dates(text: str) -> list[str]:
    """Extract date references from text."""
    dates: list[str] = []

    # Year pattern (4 digits, 1990-2030)
    year_pattern = re.compile(r"\b(19[89][0-9]|20[0-2][0-9]|2030)\b")
    years = year_pattern.findall(text)
    for year in years[:3]:  # Limit to 3 years
        if year not in dates:
            dates.append(year)

    # Month + Year pattern (e.g., "March 2024", "Mar 2024")
    month_year_pattern = re.compile(
        r"\b(January|February|March|April|May|June|July|August|September|"
        r"October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"[\s,]+(\d{4})\b",
        re.IGNORECASE,
    )
    for match in month_year_pattern.finditer(text):
        date_str = f"{match.group(1)} {match.group(2)}"
        if date_str not in dates:
            dates.append(date_str)

    # ISO date pattern (YYYY-MM-DD)
    iso_pattern = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
    for match in iso_pattern.finditer(text):
        if match.group(1) not in dates:
            dates.append(match.group(1))

    # US date pattern (MM/DD/YYYY)
    us_pattern = re.compile(r"\b(\d{1,2}/\d{1,2}/\d{4})\b")
    for match in us_pattern.finditer(text):
        if match.group(1) not in dates:
            dates.append(match.group(1))

    return dates[:5]  # Limit to 5 dates


def _extract_organizations(text: str) -> list[str]:
    """Extract organization names from text."""
    organizations: list[str] = []

    org_patterns = {
        r"\birs\b": "IRS",
        r"\bssa\b|social.?security": "SSA",
        r"\bva\b(?!\w)|veterans?.?affairs": "VA",
        r"amazon": "Amazon",
        r"chase\b": "Chase",
        r"wells.?fargo": "Wells Fargo",
        r"bank.?of.?america|bofa": "Bank of America",
        r"verizon": "Verizon",
        r"at.?&.?t|att\b": "AT&T",
        r"apple(?!\s*inc)": "Apple",
        r"google": "Google",
        r"microsoft": "Microsoft",
        r"facebook|meta\b": "Meta",
        r"netflix": "Netflix",
        r"uber\b": "Uber",
        r"lyft\b": "Lyft",
        r"walmart": "Walmart",
        r"target\b": "Target",
        r"costco": "Costco",
        r"home.?depot": "Home Depot",
        r"lowes|lowe's": "Lowe's",
    }

    for pattern, org in org_patterns.items():
        if re.search(pattern, text, re.IGNORECASE):
            if org not in organizations:
                organizations.append(org)

    return organizations[:10]  # Limit to 10 organizations


def _extract_people(text: str) -> list[str]:
    """Extract people names from text (basic patterns)."""
    # This is a simplified extraction - LLM does much better
    people: list[str] = []

    # Look for common name patterns (Title + Name)
    title_pattern = re.compile(
        r"\b(Mr\.|Mrs\.|Ms\.|Dr\.|Prof\.)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b"
    )
    for match in title_pattern.finditer(text):
        name = f"{match.group(1)} {match.group(2)}"
        if name not in people:
            people.append(name)

    return people[:5]  # Limit to 5 people


def _extract_topics(text: str) -> list[str]:
    """Extract topics from text using keyword matching."""
    topics: list[str] = []

    topic_keywords = {
        "finance": ["invoice", "payment", "bill", "bank", "account", "money"],
        "tax": ["tax", "irs", "1099", "w-2", "refund", "deduction"],
        "medical": ["medical", "health", "doctor", "prescription", "hospital"],
        "legal": ["contract", "agreement", "legal", "attorney", "law"],
        "employment": ["resume", "job", "employment", "salary", "hire"],
        "insurance": ["insurance", "policy", "claim", "coverage"],
        "real_estate": ["property", "mortgage", "lease", "rent"],
        "education": ["school", "university", "degree", "transcript"],
    }

    for topic, keywords in topic_keywords.items():
        if any(kw in text for kw in keywords):
            if topic not in topics:
                topics.append(topic)

    return topics[:5]  # Limit to 5 topics


def _generate_keyword_summary(
    filename: str,
    document_type: str,
    organizations: list[str],
) -> str:
    """Generate a basic summary from extracted information."""
    parts = []

    # Start with document type
    type_display = document_type.replace("_", " ").title()
    parts.append(type_display)

    # Add organization if present
    if organizations:
        parts.append(f"from {organizations[0]}")

    # Add filename context
    name_without_ext = Path(filename).stem
    # Clean up filename for display
    clean_name = name_without_ext.replace("_", " ").replace("-", " ")
    if len(clean_name) < 50:
        parts.append(f"({clean_name})")

    return " ".join(parts) if parts else f"Document: {filename}"


def _build_tags(
    document_type: str,
    date_references: list[str],
    organizations: list[str],
    topics: list[str],
) -> list[str]:
    """Build combined tags list from extracted data."""
    tags: list[str] = []

    if document_type and document_type != "document":
        tags.append(document_type)

    # Add years from dates
    for date_ref in date_references:
        year_match = re.search(r"\b(19[89][0-9]|20[0-2][0-9]|2030)\b", date_ref)
        if year_match and year_match.group(1) not in tags:
            tags.append(year_match.group(1))

    # Add organizations
    for org in organizations[:3]:
        if org not in tags:
            tags.append(org)

    # Add topics
    for topic in topics[:3]:
        if topic not in tags:
            tags.append(topic)

    return tags


def _calculate_keyword_confidence(
    document_type: str,
    date_references: list[str],
    organizations: list[str],
) -> float:
    """Calculate confidence based on what was extracted."""
    confidence = 0.3  # Base confidence for keyword fallback

    if document_type and document_type != "document":
        confidence += 0.2

    if date_references:
        confidence += 0.15

    if organizations:
        confidence += 0.15

    return min(confidence, 0.8)  # Cap at 0.8 for keyword fallback


def _parse_llm_json_response(text: str) -> dict[str, Any] | None:
    """Parse JSON from LLM response, handling common formatting issues."""
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

    # Try to find JSON object in text (handles nested objects better)
    # Find the first { and match to its closing }
    start = text.find("{")
    if start != -1:
        depth = 0
        for i, char in enumerate(text[start:], start):
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        break

    return None


def _extract_confidence(data: dict[str, Any]) -> float:
    """Extract confidence value from parsed JSON response."""
    confidence = data.get("confidence")
    if isinstance(confidence, (int, float)):
        return max(0.0, min(1.0, float(confidence)))
    return 0.5


def _ensure_list(value: Any) -> list[str]:
    """Ensure value is a list of strings."""
    if isinstance(value, list):
        return [str(v) for v in value if v]
    if isinstance(value, str):
        return [value] if value else []
    return []


class LLMEnricher:
    """High-level enrichment service with caching and batch support.

    Wraps the enrichment functionality with:
    - Automatic caching by file hash
    - Batch processing with progress reporting
    - Rate limiting support
    - Integration with FileDNA registry

    Example:
        enricher = LLMEnricher()
        result = enricher.enrich("/path/to/invoice.pdf")
        print(result.summary)
    """

    def __init__(
        self,
        llm_client: "LLMClient | None" = None,
        model_router: "ModelRouter | None" = None,
        prompt_registry: "PromptRegistry | None" = None,
        cache_path: str | Path = DEFAULT_ENRICHMENT_CACHE_PATH,
        use_llm: bool = True,
        use_cache: bool = True,
    ):
        """Initialize the enricher.

        Args:
            llm_client: Optional LLM client for T2 extraction.
            model_router: Optional model router for tier selection.
            prompt_registry: Optional prompt registry for loading prompts.
            cache_path: Path to the enrichment cache file.
            use_llm: Whether to use LLM for enrichment.
            use_cache: Whether to use caching.
        """
        self._llm_client = llm_client
        self._model_router = model_router
        self._prompt_registry = prompt_registry
        self._use_llm = use_llm
        self._use_cache = use_cache

        self._cache = EnrichmentCache(cache_path) if use_cache else None

    def enrich(
        self,
        file_path: str | Path,
        content_text: str | None = None,
        force_refresh: bool = False,
    ) -> FileEnrichment:
        """Enrich a file with metadata extraction.

        Checks cache first (by file hash), then performs enrichment
        if not cached or force_refresh is True.

        Args:
            file_path: Path to the file to enrich.
            content_text: Optional content text (will be extracted if not provided).
            force_refresh: If True, bypass cache and re-enrich.

        Returns:
            FileEnrichment with extracted metadata.
        """
        path = Path(file_path)

        # Compute file hash for cache lookup
        try:
            file_hash = compute_file_hash(path)
        except (FileNotFoundError, PermissionError, IsADirectoryError):
            # Can't hash, proceed without caching
            file_hash = None

        # Check cache
        if (
            self._use_cache
            and self._cache is not None
            and file_hash is not None
            and not force_refresh
        ):
            cached = self._cache.get(file_hash)
            if cached is not None:
                return cached

        # Get content if not provided
        if content_text is None:
            content_text = get_content_preview(path, max_chars=1000)

        # Perform enrichment
        enrichment = enrich_file(
            filename=path.name,
            content_text=content_text,
            llm_client=self._llm_client,
            model_router=self._model_router,
            prompt_registry=self._prompt_registry,
            use_llm=self._use_llm,
        )

        # Cache result
        if self._use_cache and self._cache is not None and file_hash is not None:
            self._cache.set(file_hash, str(path), enrichment)

        return enrichment

    def enrich_batch(
        self,
        file_paths: list[str | Path],
        force_refresh: bool = False,
        progress_callback: "Callable[[int, int, str], None] | None" = None,
        rate_limit_ms: int = 0,
    ) -> list[tuple[str, FileEnrichment]]:
        """Enrich multiple files in sequence.

        Processes files one at a time with optional progress reporting
        and rate limiting.

        Args:
            file_paths: List of file paths to enrich.
            force_refresh: If True, bypass cache for all files.
            progress_callback: Optional callback(current, total, filename).
            rate_limit_ms: Milliseconds to wait between files (0 = no limit).

        Returns:
            List of (file_path, FileEnrichment) tuples.
        """
        results: list[tuple[str, FileEnrichment]] = []
        total = len(file_paths)

        for i, file_path in enumerate(file_paths):
            path = Path(file_path)

            # Report progress
            if progress_callback is not None:
                progress_callback(i + 1, total, path.name)

            # Enrich the file
            enrichment = self.enrich(path, force_refresh=force_refresh)
            results.append((str(path), enrichment))

            # Rate limiting
            if rate_limit_ms > 0 and i < total - 1:
                time.sleep(rate_limit_ms / 1000.0)

        return results

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats.
        """
        if self._cache is None:
            return {"enabled": False, "entry_count": 0}

        return {
            "enabled": True,
            "entry_count": self._cache.get_count(),
        }

    def clear_cache(self) -> None:
        """Clear the enrichment cache."""
        if self._cache is not None:
            self._cache.clear()


# Type hint for Callable
try:
    from typing import Callable
except ImportError:
    pass
