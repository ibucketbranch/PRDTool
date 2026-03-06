"""Deduplication engine for exact and fuzzy duplicate file detection.

Detects duplicate files using:
- Exact hash matching (deterministic, no LLM needed)
- Fuzzy matching via LLM (T2 Smart for content comparison)

Dedup never deletes files - duplicates are moved to Archive/Duplicates/{hash_prefix}/.

Example usage:
    registry = DNARegistry("/path/to/.organizer/agent/file_dna.json")
    engine = DedupEngine(registry)

    # Find exact duplicates (same hash)
    exact_groups = find_exact_duplicates(registry)

    # Find fuzzy duplicates (similar content, LLM-powered)
    fuzzy_groups = find_fuzzy_duplicates(registry, llm_client)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import TYPE_CHECKING, Any

from organizer.model_router import TaskProfile

if TYPE_CHECKING:
    from organizer.file_dna import DNARegistry, FileDNA
    from organizer.llm_client import LLMClient
    from organizer.model_router import ModelRouter
    from organizer.prompt_registry import PromptRegistry


def _now_iso() -> str:
    """Get current timestamp in ISO format."""
    return datetime.now().isoformat()


@dataclass
class DuplicateGroup:
    """A group of duplicate files sharing the same content hash.

    Represents files that are exact byte-for-byte duplicates (same SHA-256 hash).
    One file is designated as the canonical copy; others are duplicates.

    Attributes:
        sha256_hash: SHA-256 hash shared by all files in the group.
        canonical_path: Path to the canonical (keeper) file.
        duplicate_paths: List of paths to duplicate files.
        wasted_bytes: Total storage wasted by duplicates.
    """

    sha256_hash: str
    canonical_path: str
    duplicate_paths: list[str] = field(default_factory=list)
    wasted_bytes: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "sha256_hash": self.sha256_hash,
            "canonical_path": self.canonical_path,
            "duplicate_paths": self.duplicate_paths.copy(),
            "wasted_bytes": self.wasted_bytes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DuplicateGroup":
        """Create DuplicateGroup from dictionary."""
        return cls(
            sha256_hash=data.get("sha256_hash", ""),
            canonical_path=data.get("canonical_path", ""),
            duplicate_paths=data.get("duplicate_paths", []).copy(),
            wasted_bytes=data.get("wasted_bytes", 0),
        )

    @property
    def file_count(self) -> int:
        """Total number of files in the group (canonical + duplicates)."""
        return 1 + len(self.duplicate_paths)


@dataclass
class FuzzyDuplicateGroup:
    """A group of files that are fuzzy duplicates (similar but not identical).

    LLM analysis determines relationship type: versions, related files, etc.

    Attributes:
        representative_path: Path to the representative file.
        similar_paths: List of paths to similar files.
        relationship: Type of relationship (version_of, related, etc.).
        confidence: Confidence in the duplicate assessment (0.0-1.0).
        reason: LLM-generated explanation of why files are duplicates.
        model_used: Model that made the assessment.
        wasted_bytes: Estimated wasted bytes if duplicates were removed.
    """

    representative_path: str
    similar_paths: list[str] = field(default_factory=list)
    relationship: str = "similar"
    confidence: float = 0.0
    reason: str = ""
    model_used: str = ""
    wasted_bytes: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "representative_path": self.representative_path,
            "similar_paths": self.similar_paths.copy(),
            "relationship": self.relationship,
            "confidence": self.confidence,
            "reason": self.reason,
            "model_used": self.model_used,
            "wasted_bytes": self.wasted_bytes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FuzzyDuplicateGroup":
        """Create FuzzyDuplicateGroup from dictionary."""
        return cls(
            representative_path=data.get("representative_path", ""),
            similar_paths=data.get("similar_paths", []).copy(),
            relationship=data.get("relationship", "similar"),
            confidence=data.get("confidence", 0.0),
            reason=data.get("reason", ""),
            model_used=data.get("model_used", ""),
            wasted_bytes=data.get("wasted_bytes", 0),
        )

    @property
    def file_count(self) -> int:
        """Total number of files in the group."""
        return 1 + len(self.similar_paths)


def get_archive_path(base_archive_dir: str | Path, file_hash: str, filename: str) -> str:
    """Generate archive path for a duplicate file.

    Duplicates are archived to: Archive/Duplicates/{hash_prefix}/{filename}
    where hash_prefix is the first 8 characters of the SHA-256 hash.

    Args:
        base_archive_dir: Base archive directory (e.g., "/iCloud/Archive").
        file_hash: SHA-256 hash of the file.
        filename: Original filename to preserve.

    Returns:
        Full path to the archive location.
    """
    base = Path(base_archive_dir)
    hash_prefix = file_hash[:8] if len(file_hash) >= 8 else file_hash
    return str(base / "Duplicates" / hash_prefix / filename)


def find_exact_duplicates(dna_registry: "DNARegistry") -> list[DuplicateGroup]:
    """Find all exact duplicate files by hash.

    Groups files by their SHA-256 hash. This is deterministic and requires
    no LLM - files with the same hash are byte-for-byte identical.

    For each group, the file with the shortest path is designated as canonical.

    Args:
        dna_registry: Registry containing file DNA records.

    Returns:
        List of DuplicateGroup objects, one for each hash with multiple files.
    """
    # Get all duplicate groups from registry (hash -> list of FileDNA)
    hash_groups = dna_registry.find_duplicates()

    groups: list[DuplicateGroup] = []

    for file_hash, dna_list in hash_groups.items():
        if len(dna_list) < 2:
            continue

        # Sort by path length (shortest first), then alphabetically for stability
        sorted_dnas = sorted(dna_list, key=lambda d: (len(d.file_path), d.file_path))

        canonical = sorted_dnas[0]
        duplicates = sorted_dnas[1:]

        # Calculate wasted bytes (sum of duplicate file sizes)
        wasted = 0
        for dna in duplicates:
            try:
                wasted += Path(dna.file_path).stat().st_size
            except (OSError, FileNotFoundError):
                pass

        groups.append(
            DuplicateGroup(
                sha256_hash=file_hash,
                canonical_path=canonical.file_path,
                duplicate_paths=[d.file_path for d in duplicates],
                wasted_bytes=wasted,
            )
        )

    # Sort by wasted bytes (highest first) for prioritization
    groups.sort(key=lambda g: g.wasted_bytes, reverse=True)

    return groups


def _get_filename_similarity(name1: str, name2: str) -> float:
    """Calculate filename similarity score using SequenceMatcher.

    Normalizes filenames before comparison:
    - Removes extensions
    - Removes common copy patterns: (1), _copy, copy of
    - Converts to lowercase

    Args:
        name1: First filename.
        name2: Second filename.

    Returns:
        Similarity score between 0.0 and 1.0.
    """
    def normalize(name: str) -> str:
        # Get stem (without extension)
        stem = Path(name).stem.lower()
        # Remove copy patterns
        stem = re.sub(r"\s*\(\d+\)\s*$", "", stem)
        stem = re.sub(r"_copy\d*$", "", stem, flags=re.IGNORECASE)
        stem = re.sub(r"^copy[\s_-]*of[\s_-]*", "", stem, flags=re.IGNORECASE)
        stem = re.sub(r"[\s_-]+", "", stem)
        return stem

    norm1 = normalize(name1)
    norm2 = normalize(name2)

    if not norm1 or not norm2:
        return 0.0

    if norm1 == norm2:
        return 1.0

    return SequenceMatcher(None, norm1, norm2).ratio()


def _find_fuzzy_candidates(
    dna_registry: "DNARegistry",
    threshold: float = 0.85,
) -> list[tuple["FileDNA", "FileDNA"]]:
    """Find pairs of files with similar filenames for LLM analysis.

    Pre-filters files by filename similarity to avoid expensive LLM calls
    on obviously different files.

    Args:
        dna_registry: Registry containing file DNA records.
        threshold: Minimum filename similarity to consider a pair.

    Returns:
        List of (file_a, file_b) tuples that are candidates for fuzzy dedup.
    """
    all_dnas = dna_registry.get_all()

    # Skip files already marked as duplicates
    active_dnas = [d for d in all_dnas if not d.duplicate_of]

    candidates: list[tuple["FileDNA", "FileDNA"]] = []
    seen_pairs: set[tuple[str, str]] = set()

    for i, dna_a in enumerate(active_dnas):
        for dna_b in active_dnas[i + 1 :]:
            # Skip if same hash (exact duplicate, not fuzzy)
            if dna_a.sha256_hash == dna_b.sha256_hash:
                continue

            # Check filename similarity
            name_a = Path(dna_a.file_path).name
            name_b = Path(dna_b.file_path).name
            similarity = _get_filename_similarity(name_a, name_b)

            if similarity >= threshold:
                # Normalize pair order for deduplication
                pair = tuple(sorted([dna_a.file_path, dna_b.file_path]))
                if pair not in seen_pairs:
                    seen_pairs.add(pair)
                    candidates.append((dna_a, dna_b))

    return candidates


def _analyze_pair_with_llm(
    file_a: "FileDNA",
    file_b: "FileDNA",
    llm_client: "LLMClient",
    model_router: "ModelRouter | None" = None,
    prompt_registry: "PromptRegistry | None" = None,
) -> dict[str, Any] | None:
    """Use LLM to analyze if two files are duplicates.

    Calls T2 Smart model to compare file content and determine relationship.

    Args:
        file_a: First file's DNA.
        file_b: Second file's DNA.
        llm_client: LLM client for T2 Smart.
        model_router: Optional router for model selection.
        prompt_registry: Optional registry for custom prompts.

    Returns:
        Dict with relationship, confidence, reason, model_used, or None on failure.
    """
    name_a = Path(file_a.file_path).name
    name_b = Path(file_b.file_path).name
    content_a = file_a.content_summary[:300] or "[No preview available]"
    content_b = file_b.content_summary[:300] or "[No preview available]"

    # Build prompt
    prompt = None
    if prompt_registry is not None:
        try:
            prompt = prompt_registry.get(
                "analyze_duplicates",
                file_a=name_a,
                content_a=content_a,
                file_b=name_b,
                content_b=content_b,
            )
        except (KeyError, FileNotFoundError):
            pass

    if prompt is None:
        # Use inline prompt following PRD specification
        prompt = f"""Are '{name_a}' (preview: '{content_a}') and '{name_b}' (preview: '{content_b}') duplicates, versions, or unrelated?

Reply with JSON only:
{{
    "relationship": "exact_duplicate|version_of|related|unrelated",
    "confidence": 0.0 to 1.0,
    "reason": "Brief explanation"
}}"""

    # Select model (T2 Smart for complex reasoning)
    model = "qwen2.5-coder:14b"  # Default T2 Smart
    if model_router is not None:
        try:
            profile = TaskProfile(task_type="analyze", complexity="medium")
            decision = model_router.route(profile)
            model = decision.model
        except RuntimeError:
            pass

    # Generate response
    response = llm_client.generate(prompt, model=model, temperature=0.0)

    if not response.success:
        return None

    # Parse JSON response
    data = _parse_llm_json_response(response.text)
    if data is None:
        return None

    data["model_used"] = response.model_used
    return data


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


def find_fuzzy_duplicates(
    dna_registry: "DNARegistry",
    llm_client: "LLMClient | None" = None,
    model_router: "ModelRouter | None" = None,
    prompt_registry: "PromptRegistry | None" = None,
    threshold: float = 0.85,
    use_llm: bool = True,
) -> list[FuzzyDuplicateGroup]:
    """Find fuzzy duplicates using filename similarity and LLM analysis.

    For candidate pairs with similar filenames, calls T2 Smart model to
    determine if they are duplicates, versions, or unrelated.

    Falls back to filename-only analysis if LLM is unavailable.

    Args:
        dna_registry: Registry containing file DNA records.
        llm_client: Optional LLM client for T2 Smart analysis.
        model_router: Optional router for model selection.
        prompt_registry: Optional registry for custom prompts.
        threshold: Minimum filename similarity to consider (default 0.85).
        use_llm: Whether to use LLM analysis (default True).

    Returns:
        List of FuzzyDuplicateGroup objects.
    """
    # Find candidate pairs based on filename similarity
    candidates = _find_fuzzy_candidates(dna_registry, threshold)

    if not candidates:
        return []

    # Check if LLM is available
    llm_available = False
    if use_llm and llm_client is not None:
        try:
            llm_available = llm_client.is_ollama_available(timeout_s=5)
        except Exception:
            pass

    # Group files by their relationships
    # Using a simple approach: for each confirmed duplicate pair,
    # group them together
    groups: list[FuzzyDuplicateGroup] = []
    processed_files: set[str] = set()

    for file_a, file_b in candidates:
        # Skip if either file already processed
        if file_a.file_path in processed_files or file_b.file_path in processed_files:
            continue

        if llm_available and llm_client is not None:
            # LLM analysis
            result = _analyze_pair_with_llm(
                file_a,
                file_b,
                llm_client,
                model_router,
                prompt_registry,
            )

            if result is None:
                continue

            relationship = result.get("relationship", "unrelated")
            confidence = _extract_confidence(result)
            reason = result.get("reason", "")
            model_used = result.get("model_used", "")

            # Only group if relationship indicates duplicates
            if relationship in ("exact_duplicate", "version_of", "related"):
                wasted = _estimate_wasted_bytes(file_a.file_path, file_b.file_path)
                groups.append(
                    FuzzyDuplicateGroup(
                        representative_path=file_a.file_path,
                        similar_paths=[file_b.file_path],
                        relationship=relationship,
                        confidence=confidence,
                        reason=reason,
                        model_used=model_used,
                        wasted_bytes=wasted,
                    )
                )
                processed_files.add(file_a.file_path)
                processed_files.add(file_b.file_path)
        else:
            # Keyword fallback: use filename similarity and content overlap
            result = _analyze_pair_with_keywords(file_a, file_b)

            if result["relationship"] != "unrelated":
                wasted = _estimate_wasted_bytes(file_a.file_path, file_b.file_path)
                groups.append(
                    FuzzyDuplicateGroup(
                        representative_path=file_a.file_path,
                        similar_paths=[file_b.file_path],
                        relationship=result["relationship"],
                        confidence=result["confidence"],
                        reason=result["reason"],
                        model_used="",  # No model used
                        wasted_bytes=wasted,
                    )
                )
                processed_files.add(file_a.file_path)
                processed_files.add(file_b.file_path)

    # Sort by confidence (highest first)
    groups.sort(key=lambda g: g.confidence, reverse=True)

    return groups


def _analyze_pair_with_keywords(
    file_a: "FileDNA",
    file_b: "FileDNA",
) -> dict[str, Any]:
    """Analyze file pair using keyword/heuristic matching.

    Fallback when LLM is unavailable. Uses:
    - Filename similarity patterns (copy, version numbers)
    - Content summary overlap
    - Tag overlap

    Args:
        file_a: First file's DNA.
        file_b: Second file's DNA.

    Returns:
        Dict with relationship, confidence, reason.
    """
    name_a = Path(file_a.file_path).name.lower()
    name_b = Path(file_b.file_path).name.lower()

    # Check for copy patterns
    copy_patterns = [
        r"\(\d+\)",  # (1), (2), etc.
        r"_copy\d*",  # _copy, _copy2
        r"^copy[\s_-]*of[\s_-]*",  # copy of
        r"_v\d+",  # _v1, _v2
        r"-v\d+",  # -v1, -v2
    ]

    has_copy_pattern = any(
        re.search(pattern, name_a, re.IGNORECASE) or
        re.search(pattern, name_b, re.IGNORECASE)
        for pattern in copy_patterns
    )

    # Calculate content overlap
    content_overlap = 0.0
    if file_a.content_summary and file_b.content_summary:
        content_overlap = SequenceMatcher(
            None, file_a.content_summary, file_b.content_summary
        ).ratio()

    # Calculate tag overlap
    tags_a = set(t.lower() for t in file_a.auto_tags)
    tags_b = set(t.lower() for t in file_b.auto_tags)
    tag_overlap = 0.0
    if tags_a and tags_b:
        intersection = len(tags_a & tags_b)
        union = len(tags_a | tags_b)
        tag_overlap = intersection / union if union > 0 else 0.0

    # Determine relationship
    if has_copy_pattern:
        return {
            "relationship": "version_of",
            "confidence": 0.85,
            "reason": "Filename contains copy/version pattern",
        }
    elif content_overlap > 0.9:
        return {
            "relationship": "version_of",
            "confidence": content_overlap * 0.9,
            "reason": f"Very similar content ({content_overlap:.0%} overlap)",
        }
    elif content_overlap > 0.7 and tag_overlap > 0.5:
        return {
            "relationship": "related",
            "confidence": (content_overlap + tag_overlap) / 2 * 0.8,
            "reason": f"Similar content ({content_overlap:.0%}) and tags ({tag_overlap:.0%})",
        }
    elif content_overlap > 0.5:
        return {
            "relationship": "related",
            "confidence": content_overlap * 0.7,
            "reason": f"Moderate content similarity ({content_overlap:.0%})",
        }
    else:
        return {
            "relationship": "unrelated",
            "confidence": 0.3,
            "reason": "No significant similarity detected",
        }


def _estimate_wasted_bytes(path_a: str, path_b: str) -> int:
    """Estimate wasted bytes (smaller file's size)."""
    try:
        size_a = Path(path_a).stat().st_size
        size_b = Path(path_b).stat().st_size
        return min(size_a, size_b)
    except (OSError, FileNotFoundError):
        return 0


def _extract_confidence(data: dict[str, Any]) -> float:
    """Extract confidence value from parsed JSON response."""
    confidence = data.get("confidence")
    if isinstance(confidence, (int, float)):
        return max(0.0, min(1.0, float(confidence)))
    return 0.5


class DedupEngine:
    """Engine for detecting and managing duplicate files.

    Combines exact hash matching with LLM-powered fuzzy detection.
    Duplicates are never deleted - they're moved to an archive location.

    Example:
        registry = DNARegistry("/path/to/.organizer/agent/file_dna.json")
        engine = DedupEngine(
            registry,
            archive_dir="/iCloud/Archive",
            llm_client=client,
        )
        report = engine.run()
        print(f"Found {report['exact_count']} exact duplicates")
    """

    def __init__(
        self,
        dna_registry: "DNARegistry",
        archive_dir: str | Path = "Archive",
        llm_client: "LLMClient | None" = None,
        model_router: "ModelRouter | None" = None,
        prompt_registry: "PromptRegistry | None" = None,
        fuzzy_threshold: float = 0.85,
        use_llm: bool = True,
    ):
        """Initialize the dedup engine.

        Args:
            dna_registry: Registry containing file DNA records.
            archive_dir: Directory for archiving duplicates.
            llm_client: Optional LLM client for fuzzy detection.
            model_router: Optional router for model selection.
            prompt_registry: Optional registry for custom prompts.
            fuzzy_threshold: Minimum similarity for fuzzy matching.
            use_llm: Whether to use LLM for fuzzy detection.
        """
        self._registry = dna_registry
        self._archive_dir = Path(archive_dir)
        self._llm_client = llm_client
        self._model_router = model_router
        self._prompt_registry = prompt_registry
        self._fuzzy_threshold = fuzzy_threshold
        self._use_llm = use_llm

        self._exact_groups: list[DuplicateGroup] = []
        self._fuzzy_groups: list[FuzzyDuplicateGroup] = []

    def run(self) -> dict[str, Any]:
        """Run deduplication detection.

        Finds both exact and fuzzy duplicates.

        Returns:
            Report dict with duplicate statistics.
        """
        # Find exact duplicates
        self._exact_groups = find_exact_duplicates(self._registry)

        # Find fuzzy duplicates
        self._fuzzy_groups = find_fuzzy_duplicates(
            self._registry,
            llm_client=self._llm_client,
            model_router=self._model_router,
            prompt_registry=self._prompt_registry,
            threshold=self._fuzzy_threshold,
            use_llm=self._use_llm,
        )

        return self.get_report()

    def get_report(self) -> dict[str, Any]:
        """Get a summary report of detected duplicates.

        Returns:
            Dict with duplicate counts and storage savings.
        """
        exact_wasted = sum(g.wasted_bytes for g in self._exact_groups)
        fuzzy_wasted = sum(g.wasted_bytes for g in self._fuzzy_groups)

        return {
            "exact_count": len(self._exact_groups),
            "exact_file_count": sum(g.file_count for g in self._exact_groups),
            "exact_wasted_bytes": exact_wasted,
            "fuzzy_count": len(self._fuzzy_groups),
            "fuzzy_file_count": sum(g.file_count for g in self._fuzzy_groups),
            "fuzzy_wasted_bytes": fuzzy_wasted,
            "total_wasted_bytes": exact_wasted + fuzzy_wasted,
        }

    def get_exact_groups(self) -> list[DuplicateGroup]:
        """Get exact duplicate groups from last run."""
        return list(self._exact_groups)

    def get_fuzzy_groups(self) -> list[FuzzyDuplicateGroup]:
        """Get fuzzy duplicate groups from last run."""
        return list(self._fuzzy_groups)

    def get_archive_path_for(self, file_path: str, file_hash: str) -> str:
        """Get archive destination for a duplicate file.

        Args:
            file_path: Path to the file.
            file_hash: SHA-256 hash of the file.

        Returns:
            Path to archive location.
        """
        filename = Path(file_path).name
        return get_archive_path(self._archive_dir, file_hash, filename)
