"""Relationship linker module for detecting cross-file relationships.

Detects relationships between files in the same bin using LLM analysis:
- Companions: files that belong together (e.g., nexus_letter.pdf + dbq_ptsd.pdf)
- Versions: different versions of the same document
- References: files that reference each other

Uses T2 Smart for relationship detection. Escalates to T3 Cloud for large
clusters (>50 files). Falls back to keyword/tag matching if LLM unavailable.

Example usage:
    registry = DNARegistry("/path/to/.organizer/agent/file_dna.json")
    relationships = detect_relationships(registry, llm_client)
    for rel in relationships:
        print(f"{rel.source_path} -> {rel.related_path}: {rel.relationship_type}")
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from organizer.model_router import TaskProfile

if TYPE_CHECKING:
    from organizer.file_dna import DNARegistry, FileDNA
    from organizer.llm_client import LLMClient
    from organizer.model_router import ModelRouter
    from organizer.prompt_registry import PromptRegistry


# Threshold for cluster size that triggers T3 escalation
T3_ESCALATION_CLUSTER_SIZE = 50


@dataclass
class FileRelationship:
    """A detected relationship between two files.

    Represents a semantic connection between files identified by LLM analysis
    or keyword matching. Types of relationships:
    - companion: Files that belong together (same case, project, submission)
    - version_of: A newer/older version of the same document
    - reference: One file references the other
    - related: General relationship, not otherwise categorized

    Attributes:
        source_path: Path to the source file.
        related_path: Path to the related file.
        relationship_type: Type of relationship (companion, version_of, reference, related).
        reason: Explanation of why the relationship was detected.
        model_used: LLM model used for detection (empty if keyword fallback).
    """

    source_path: str
    related_path: str
    relationship_type: str
    reason: str = ""
    model_used: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "source_path": self.source_path,
            "related_path": self.related_path,
            "relationship_type": self.relationship_type,
            "reason": self.reason,
            "model_used": self.model_used,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FileRelationship":
        """Create FileRelationship from dictionary."""
        return cls(
            source_path=data.get("source_path", ""),
            related_path=data.get("related_path", ""),
            relationship_type=data.get("relationship_type", "related"),
            reason=data.get("reason", ""),
            model_used=data.get("model_used", ""),
        )


@dataclass
class RelationshipCluster:
    """A cluster of related files in the same bin.

    Used internally to group files before relationship detection.

    Attributes:
        bin_path: Path to the bin containing these files.
        files: List of FileDNA records in this cluster.
        relationships: Detected relationships within the cluster.
    """

    bin_path: str
    files: list["FileDNA"] = field(default_factory=list)
    relationships: list[FileRelationship] = field(default_factory=list)

    @property
    def file_count(self) -> int:
        """Number of files in the cluster."""
        return len(self.files)

    @property
    def needs_t3_escalation(self) -> bool:
        """Whether this cluster should escalate to T3 Cloud."""
        return self.file_count > T3_ESCALATION_CLUSTER_SIZE


def _get_bin_from_path(file_path: str) -> str:
    """Extract the bin (top-level category folder) from a file path.

    Identifies the root bin by looking for common bin patterns.
    Falls back to the parent directory if no bin pattern found.

    Args:
        file_path: Full path to the file.

    Returns:
        Path to the bin containing this file.
    """
    path = Path(file_path)
    parts = path.parts

    # Look for common bin patterns
    bin_patterns = {
        "va", "finances bin", "work bin", "personal bin",
        "employment", "legal", "health", "education",
        "archive", "documents", "projects",
    }

    for i, part in enumerate(parts):
        if part.lower().replace("_", " ").replace("-", " ") in bin_patterns:
            # Return path up to and including the bin
            return str(Path(*parts[: i + 1]))

    # Fall back to parent directory
    return str(path.parent)


def _group_files_by_bin(dna_registry: "DNARegistry") -> dict[str, list["FileDNA"]]:
    """Group files by their containing bin.

    Args:
        dna_registry: Registry containing file DNA records.

    Returns:
        Dictionary mapping bin path to list of files in that bin.
    """
    bins: dict[str, list["FileDNA"]] = defaultdict(list)

    for dna in dna_registry.get_all():
        bin_path = _get_bin_from_path(dna.file_path)
        bins[bin_path].append(dna)

    return dict(bins)


def detect_relationships(
    dna_registry: "DNARegistry",
    llm_client: "LLMClient | None" = None,
    model_router: "ModelRouter | None" = None,
    prompt_registry: "PromptRegistry | None" = None,
    use_llm: bool = True,
    max_pairs_per_cluster: int = 100,
) -> list[FileRelationship]:
    """Detect relationships between files in the same bin.

    For files in each bin, uses T2 Smart to identify companions, versions,
    and references. Escalates to T3 Cloud for clusters > 50 files.

    Falls back to keyword/tag matching if LLM is unavailable.

    Args:
        dna_registry: Registry containing file DNA records.
        llm_client: Optional LLM client for relationship detection.
        model_router: Optional router for model selection.
        prompt_registry: Optional registry for custom prompts.
        use_llm: Whether to use LLM analysis (default True).
        max_pairs_per_cluster: Maximum pairs to analyze per cluster.

    Returns:
        List of FileRelationship objects.
    """
    # Group files by bin
    bins = _group_files_by_bin(dna_registry)

    # Check if LLM is available
    llm_available = False
    if use_llm and llm_client is not None:
        try:
            llm_available = llm_client.is_ollama_available(timeout_s=5)
        except Exception:
            pass

    all_relationships: list[FileRelationship] = []

    for bin_path, files in bins.items():
        if len(files) < 2:
            # Need at least 2 files for relationships
            continue

        # Determine if we need T3 escalation
        use_t3 = len(files) > T3_ESCALATION_CLUSTER_SIZE

        # Get candidate pairs
        pairs = _get_candidate_pairs(files, max_pairs=max_pairs_per_cluster)

        for file_a, file_b in pairs:
            if llm_available and llm_client is not None:
                result = _analyze_relationship_with_llm(
                    file_a,
                    file_b,
                    llm_client,
                    model_router,
                    prompt_registry,
                    use_t3=use_t3,
                )
            else:
                result = _analyze_relationship_with_keywords(file_a, file_b)

            if result is not None:
                all_relationships.append(result)

    return all_relationships


def _get_candidate_pairs(
    files: list["FileDNA"],
    max_pairs: int = 100,
) -> list[tuple["FileDNA", "FileDNA"]]:
    """Get candidate pairs of files for relationship analysis.

    Prioritizes pairs with:
    - Similar filenames
    - Overlapping tags
    - Same document type

    Args:
        files: List of files in the cluster.
        max_pairs: Maximum number of pairs to return.

    Returns:
        List of (file_a, file_b) tuples.
    """
    pairs: list[tuple["FileDNA", "FileDNA", float]] = []  # (a, b, score)

    for i, file_a in enumerate(files):
        for file_b in files[i + 1 :]:
            score = _calculate_pair_priority(file_a, file_b)
            if score > 0:
                pairs.append((file_a, file_b, score))

    # Sort by priority score (highest first) and limit
    pairs.sort(key=lambda p: p[2], reverse=True)

    return [(a, b) for a, b, _ in pairs[:max_pairs]]


def _calculate_pair_priority(file_a: "FileDNA", file_b: "FileDNA") -> float:
    """Calculate priority score for analyzing a pair.

    Higher scores indicate pairs more likely to have a relationship.

    Args:
        file_a: First file's DNA.
        file_b: Second file's DNA.

    Returns:
        Priority score (0.0 to 1.0).
    """
    score = 0.0

    name_a = Path(file_a.file_path).stem.lower()
    name_b = Path(file_b.file_path).stem.lower()

    # Check for shared keywords in filenames
    words_a = set(re.split(r"[\s_\-\.]+", name_a))
    words_b = set(re.split(r"[\s_\-\.]+", name_b))

    # Remove common filler words
    filler_words = {"the", "a", "an", "of", "for", "and", "or", "to", "in", "on"}
    words_a -= filler_words
    words_b -= filler_words

    if words_a and words_b:
        overlap = len(words_a & words_b) / min(len(words_a), len(words_b))
        score += overlap * 0.4

    # Check tag overlap
    tags_a = set(t.lower() for t in file_a.auto_tags)
    tags_b = set(t.lower() for t in file_b.auto_tags)

    if tags_a and tags_b:
        tag_overlap = len(tags_a & tags_b) / max(len(tags_a), len(tags_b))
        score += tag_overlap * 0.4

    # Check for same document type (if first tag is doc type)
    if file_a.auto_tags and file_b.auto_tags:
        if file_a.auto_tags[0].lower() == file_b.auto_tags[0].lower():
            score += 0.2

    return min(score, 1.0)


def _analyze_relationship_with_llm(
    file_a: "FileDNA",
    file_b: "FileDNA",
    llm_client: "LLMClient",
    model_router: "ModelRouter | None" = None,
    prompt_registry: "PromptRegistry | None" = None,
    use_t3: bool = False,
) -> FileRelationship | None:
    """Use LLM to analyze relationship between two files.

    Calls T2 Smart (or T3 Cloud for large clusters) to identify relationship.

    Args:
        file_a: First file's DNA.
        file_b: Second file's DNA.
        llm_client: LLM client for generation.
        model_router: Optional router for model selection.
        prompt_registry: Optional registry for custom prompts.
        use_t3: Whether to use T3 Cloud (for large clusters).

    Returns:
        FileRelationship if a relationship is detected, None otherwise.
    """
    name_a = Path(file_a.file_path).name
    name_b = Path(file_b.file_path).name
    tags_a = ", ".join(file_a.auto_tags[:5]) if file_a.auto_tags else "none"
    tags_b = ", ".join(file_b.auto_tags[:5]) if file_b.auto_tags else "none"
    content_a = file_a.content_summary[:200] or "[No preview available]"
    content_b = file_b.content_summary[:200] or "[No preview available]"

    # Build prompt
    prompt = None
    if prompt_registry is not None:
        try:
            prompt = prompt_registry.get(
                "detect_relationship",
                file_a=name_a,
                tags_a=tags_a,
                content_a=content_a,
                file_b=name_b,
                tags_b=tags_b,
                content_b=content_b,
            )
        except (KeyError, FileNotFoundError):
            pass

    if prompt is None:
        # Use inline prompt following PRD specification
        prompt = f"""Analyze the relationship between these two files in the same folder:

File A: '{name_a}'
  Tags: {tags_a}
  Preview: '{content_a}'

File B: '{name_b}'
  Tags: {tags_b}
  Preview: '{content_b}'

Are these files related? If so, how?

Reply with JSON only:
{{
    "has_relationship": true or false,
    "relationship_type": "companion|version_of|reference|related|none",
    "confidence": 0.0 to 1.0,
    "reason": "Brief explanation of the relationship"
}}

Relationship types:
- companion: Files that belong together (same case, project, submission)
- version_of: Different versions of the same document
- reference: One file references the other
- related: General relationship
- none: No meaningful relationship"""

    # Select model (T2 Smart or T3 Cloud)
    model = "qwen2.5-coder:14b"  # Default T2 Smart
    if model_router is not None:
        try:
            complexity = "high" if use_t3 else "medium"
            profile = TaskProfile(task_type="analyze", complexity=complexity)
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

    # Check if relationship exists
    has_relationship = data.get("has_relationship", False)
    if not has_relationship:
        return None

    relationship_type = data.get("relationship_type", "related")
    if relationship_type == "none":
        return None

    confidence = _extract_confidence(data)
    if confidence < 0.5:
        return None

    reason = data.get("reason", "")

    return FileRelationship(
        source_path=file_a.file_path,
        related_path=file_b.file_path,
        relationship_type=relationship_type,
        reason=reason,
        model_used=response.model_used,
    )


def _analyze_relationship_with_keywords(
    file_a: "FileDNA",
    file_b: "FileDNA",
) -> FileRelationship | None:
    """Analyze relationship using keyword/tag matching.

    Fallback when LLM is unavailable. Uses:
    - Filename pattern matching
    - Tag overlap
    - Content keyword matching

    Args:
        file_a: First file's DNA.
        file_b: Second file's DNA.

    Returns:
        FileRelationship if a relationship is detected, None otherwise.
    """
    name_a = Path(file_a.file_path).stem.lower()
    name_b = Path(file_b.file_path).stem.lower()

    # Check for companion patterns (common VA, legal, medical document sets)
    companion_sets = [
        # VA evidence sets
        {"nexus", "dbq", "letter", "statement"},
        {"claim", "evidence", "supporting"},
        {"disability", "rating", "decision"},
        # Legal document sets
        {"complaint", "response", "motion"},
        {"contract", "amendment", "addendum"},
        {"filing", "exhibit", "brief"},
        # Tax document sets
        {"1040", "w2", "1099"},
        {"schedule", "form", "return"},
    ]

    combined_words = set(re.split(r"[\s_\-\.]+", f"{name_a} {name_b}"))

    for companion_set in companion_sets:
        matches = combined_words & companion_set
        if len(matches) >= 2:
            return FileRelationship(
                source_path=file_a.file_path,
                related_path=file_b.file_path,
                relationship_type="companion",
                reason=f"Files share document set keywords: {', '.join(matches)}",
                model_used="",
            )

    # Check tag overlap for same document type
    tags_a = set(t.lower() for t in file_a.auto_tags)
    tags_b = set(t.lower() for t in file_b.auto_tags)

    if tags_a and tags_b:
        common_tags = tags_a & tags_b
        if len(common_tags) >= 2:
            # Check for specific relationship indicators
            tag_str = " ".join(common_tags)

            if any(kw in tag_str for kw in ["va", "veteran", "disability", "claim"]):
                return FileRelationship(
                    source_path=file_a.file_path,
                    related_path=file_b.file_path,
                    relationship_type="companion",
                    reason=f"VA-related documents with shared tags: {', '.join(common_tags)}",
                    model_used="",
                )

            if any(kw in tag_str for kw in ["tax", "1040", "irs", "return"]):
                return FileRelationship(
                    source_path=file_a.file_path,
                    related_path=file_b.file_path,
                    relationship_type="companion",
                    reason=f"Tax-related documents with shared tags: {', '.join(common_tags)}",
                    model_used="",
                )

            # General related documents
            return FileRelationship(
                source_path=file_a.file_path,
                related_path=file_b.file_path,
                relationship_type="related",
                reason=f"Documents share tags: {', '.join(common_tags)}",
                model_used="",
            )

    # Check for version patterns in filenames
    version_patterns = [
        r"_v(\d+)",
        r"-v(\d+)",
        r"\s*v(\d+)",
        r"_rev(\d+)",
        r"\s*rev(\d+)",
        r"_(\d{4})[\-_]?(\d{2})[\-_]?(\d{2})",  # Date patterns
    ]

    for pattern in version_patterns:
        match_a = re.search(pattern, name_a, re.IGNORECASE)
        match_b = re.search(pattern, name_b, re.IGNORECASE)

        if match_a and match_b:
            # Both have version/date pattern, check if base names match
            base_a = re.sub(pattern, "", name_a, flags=re.IGNORECASE).strip()
            base_b = re.sub(pattern, "", name_b, flags=re.IGNORECASE).strip()

            if base_a and base_b and _similarity_ratio(base_a, base_b) > 0.7:
                return FileRelationship(
                    source_path=file_a.file_path,
                    related_path=file_b.file_path,
                    relationship_type="version_of",
                    reason="Different versions of the same document",
                    model_used="",
                )

    return None


def _similarity_ratio(str_a: str, str_b: str) -> float:
    """Calculate simple similarity ratio between two strings."""
    if not str_a or not str_b:
        return 0.0

    # Simple character-based similarity
    chars_a = set(str_a.lower())
    chars_b = set(str_b.lower())

    intersection = len(chars_a & chars_b)
    union = len(chars_a | chars_b)

    return intersection / union if union > 0 else 0.0


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
    """Extract confidence value from parsed JSON response."""
    confidence = data.get("confidence")
    if isinstance(confidence, (int, float)):
        return max(0.0, min(1.0, float(confidence)))
    return 0.5


class RelationshipLinker:
    """High-level interface for relationship detection.

    Wraps the detect_relationships function with configuration and caching.

    Example:
        registry = DNARegistry("/path/to/.organizer/agent/file_dna.json")
        linker = RelationshipLinker(registry, llm_client=client)
        relationships = linker.find_all()
    """

    def __init__(
        self,
        dna_registry: "DNARegistry",
        llm_client: "LLMClient | None" = None,
        model_router: "ModelRouter | None" = None,
        prompt_registry: "PromptRegistry | None" = None,
        use_llm: bool = True,
        max_pairs_per_cluster: int = 100,
    ):
        """Initialize the relationship linker.

        Args:
            dna_registry: Registry containing file DNA records.
            llm_client: Optional LLM client for relationship detection.
            model_router: Optional router for model selection.
            prompt_registry: Optional registry for custom prompts.
            use_llm: Whether to use LLM analysis.
            max_pairs_per_cluster: Maximum pairs to analyze per cluster.
        """
        self._registry = dna_registry
        self._llm_client = llm_client
        self._model_router = model_router
        self._prompt_registry = prompt_registry
        self._use_llm = use_llm
        self._max_pairs = max_pairs_per_cluster

        self._relationships: list[FileRelationship] = []
        self._last_run_used_llm = False

    def find_all(self) -> list[FileRelationship]:
        """Find all relationships in the registry.

        Returns:
            List of detected relationships.
        """
        # Check if LLM is available before running
        if self._use_llm and self._llm_client is not None:
            try:
                self._last_run_used_llm = self._llm_client.is_ollama_available(
                    timeout_s=5
                )
            except Exception:
                self._last_run_used_llm = False
        else:
            self._last_run_used_llm = False

        self._relationships = detect_relationships(
            self._registry,
            llm_client=self._llm_client,
            model_router=self._model_router,
            prompt_registry=self._prompt_registry,
            use_llm=self._use_llm,
            max_pairs_per_cluster=self._max_pairs,
        )

        return self._relationships

    def find_for_file(self, file_path: str) -> list[FileRelationship]:
        """Find relationships involving a specific file.

        Args:
            file_path: Path to the file.

        Returns:
            List of relationships involving this file.
        """
        return [
            rel
            for rel in self._relationships
            if rel.source_path == file_path or rel.related_path == file_path
        ]

    def get_companions(self, file_path: str) -> list[str]:
        """Get companion files for a given file.

        Args:
            file_path: Path to the file.

        Returns:
            List of paths to companion files.
        """
        companions = []
        for rel in self._relationships:
            if rel.relationship_type == "companion":
                if rel.source_path == file_path:
                    companions.append(rel.related_path)
                elif rel.related_path == file_path:
                    companions.append(rel.source_path)
        return companions

    def get_report(self) -> dict[str, Any]:
        """Get a summary report of detected relationships.

        Returns:
            Dict with relationship counts and statistics.
        """
        type_counts: dict[str, int] = defaultdict(int)
        for rel in self._relationships:
            type_counts[rel.relationship_type] += 1

        llm_count = sum(1 for rel in self._relationships if rel.model_used)
        keyword_count = len(self._relationships) - llm_count

        return {
            "total_count": len(self._relationships),
            "by_type": dict(type_counts),
            "llm_detected": llm_count,
            "keyword_detected": keyword_count,
            "used_llm": self._last_run_used_llm,
        }

    @property
    def relationships(self) -> list[FileRelationship]:
        """Get relationships from last find_all() call."""
        return list(self._relationships)
