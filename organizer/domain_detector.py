"""Domain Detector module for identifying the organizational domain of a folder structure.

Uses LLM-powered analysis (T2 Smart) to detect the domain (personal, medical, legal,
automotive, creative, engineering, generic_business) from folder structure context.
Falls back to keyword-based matching if LLM is unavailable.

This replaces the rule-based domain_detector with LLM-native detection.

Example usage:
    detector = DomainDetector(llm_client, model_router)
    context = detector.detect_domain(structure_snapshot)
    print(f"Domain: {context.detected_domain}, Confidence: {context.confidence}")
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from organizer.model_router import TaskProfile

if TYPE_CHECKING:
    from organizer.llm_client import LLMClient
    from organizer.model_router import ModelRouter
    from organizer.prompt_registry import PromptRegistry
    from organizer.structure_analyzer import StructureSnapshot


# Valid domain types
DOMAIN_TYPES = {
    "personal",
    "medical",
    "legal",
    "automotive",
    "creative",
    "engineering",
    "generic_business",
}

# Keyword signals for each domain (used for fallback)
DOMAIN_KEYWORDS: dict[str, set[str]] = {
    "personal": {
        "photos",
        "pictures",
        "family",
        "personal",
        "home",
        "recipes",
        "vacation",
        "holidays",
        "memories",
        "diary",
        "journal",
        "kids",
        "pets",
        "hobbies",
    },
    "medical": {
        "medical",
        "health",
        "doctor",
        "hospital",
        "prescription",
        "insurance",
        "va",
        "veterans",
        "claims",
        "disability",
        "diagnosis",
        "treatment",
        "lab",
        "results",
        "pharmacy",
        "nexus",
        "dbq",
        "ptsd",
        "mental",
        "therapy",
    },
    "legal": {
        "legal",
        "lawyer",
        "attorney",
        "court",
        "case",
        "contract",
        "agreement",
        "litigation",
        "lawsuit",
        "estate",
        "trust",
        "will",
        "deposition",
        "subpoena",
        "pleading",
    },
    "automotive": {
        "car",
        "auto",
        "vehicle",
        "dealership",
        "inventory",
        "vin",
        "service",
        "repair",
        "maintenance",
        "parts",
        "sales",
        "lease",
        "finance",
        "trade-in",
        "lot",
    },
    "creative": {
        "design",
        "art",
        "music",
        "video",
        "photo",
        "portfolio",
        "project",
        "creative",
        "render",
        "edit",
        "draft",
        "concept",
        "sketch",
        "brand",
        "assets",
    },
    "engineering": {
        "code",
        "source",
        "src",
        "lib",
        "api",
        "build",
        "deploy",
        "test",
        "spec",
        "docs",
        "config",
        "data",
        "logs",
        "scripts",
        "dev",
        "prod",
        "staging",
        "infrastructure",
    },
    "generic_business": {
        "finance",
        "accounting",
        "invoice",
        "receipt",
        "tax",
        "payroll",
        "hr",
        "employee",
        "client",
        "vendor",
        "report",
        "quarterly",
        "annual",
        "budget",
        "expense",
    },
}


def _now_iso() -> str:
    """Get current timestamp in ISO format."""
    return datetime.now().isoformat()


@dataclass
class DomainContext:
    """Result of domain detection analysis.

    Captures the detected domain type, confidence score, supporting evidence,
    and the model used for detection.

    Attributes:
        detected_domain: The identified domain type (e.g., "personal", "medical").
        confidence: Confidence score from 0.0 to 1.0.
        evidence: List of signals/reasons that support the domain classification.
        model_used: The LLM model used for detection (empty if keyword fallback).
        detected_at: ISO timestamp when detection was performed.
    """

    detected_domain: str
    confidence: float
    evidence: list[str] = field(default_factory=list)
    model_used: str = ""
    detected_at: str = ""

    def __post_init__(self) -> None:
        """Set default timestamp if not provided."""
        if not self.detected_at:
            self.detected_at = _now_iso()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "detected_domain": self.detected_domain,
            "confidence": self.confidence,
            "evidence": list(self.evidence),
            "model_used": self.model_used,
            "detected_at": self.detected_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DomainContext":
        """Create DomainContext from dictionary."""
        return cls(
            detected_domain=data.get("detected_domain", "generic_business"),
            confidence=data.get("confidence", 0.0),
            evidence=list(data.get("evidence", [])),
            model_used=data.get("model_used", ""),
            detected_at=data.get("detected_at", ""),
        )

    @property
    def used_llm(self) -> bool:
        """Check if LLM was used (vs keyword fallback)."""
        return bool(self.model_used) and self.model_used != "keyword_fallback"


class DomainDetector:
    """Detects the organizational domain of a folder structure.

    Uses T2 Smart LLM model to analyze folder structure and determine
    the domain type. Falls back to keyword-based matching when LLM
    is unavailable.

    Example:
        detector = DomainDetector(llm_client, model_router)
        context = detector.detect_domain(snapshot)
        print(context.detected_domain)  # "medical"
    """

    def __init__(
        self,
        llm_client: "LLMClient | None" = None,
        model_router: "ModelRouter | None" = None,
        prompt_registry: "PromptRegistry | None" = None,
    ):
        """Initialize the domain detector.

        Args:
            llm_client: LLM client for domain detection.
            model_router: Model router for tier selection.
            prompt_registry: Prompt registry for loading prompts.
        """
        self._llm_client = llm_client
        self._model_router = model_router
        self._prompt_registry = prompt_registry

    def detect_domain(
        self,
        snapshot: "StructureSnapshot",
        use_llm: bool = True,
    ) -> DomainContext:
        """Detect the domain type from a structure snapshot.

        Analyzes the folder structure using T2 Smart model to identify
        the organizational domain. Falls back to keyword matching if
        LLM is unavailable.

        Args:
            snapshot: The analyzed folder structure.
            use_llm: Whether to attempt LLM detection (default True).

        Returns:
            DomainContext with detection results.
        """
        # Try LLM detection first if enabled and available
        if use_llm and self._llm_client is not None:
            try:
                if self._llm_client.is_ollama_available(timeout_s=5):
                    return self._detect_with_llm(snapshot)
            except Exception:
                pass  # Fall through to keyword fallback

        # Keyword-based fallback
        return self._detect_with_keywords(snapshot)

    def _build_structure_summary(
        self,
        snapshot: "StructureSnapshot",
        max_depth: int = 3,
    ) -> str:
        """Build a text summary of folder structure for LLM prompt.

        Args:
            snapshot: The folder structure snapshot.
            max_depth: Maximum depth to include in summary.

        Returns:
            Formatted text summary of the structure.
        """
        summary_lines = []
        for folder in snapshot.folders:
            if folder.depth > max_depth:
                continue

            indent = "  " * folder.depth
            file_info = f"{folder.file_count} files"

            # Add file types if available
            if folder.file_types:
                top_types = sorted(
                    folder.file_types.items(),
                    key=lambda x: x[1],
                    reverse=True,
                )[:3]
                types_str = ", ".join(f"{ext}" for ext, _ in top_types)
                file_info = f"{folder.file_count} files ({types_str})"

            # Add sample filenames for more context
            samples = ""
            if folder.sample_filenames:
                sample_list = folder.sample_filenames[:5]
                samples = f" [samples: {', '.join(sample_list)}]"

            summary_lines.append(f"{indent}- {folder.name}: {file_info}{samples}")

        # Limit total size for LLM context
        return "\n".join(summary_lines[:100])

    def _detect_with_llm(self, snapshot: "StructureSnapshot") -> DomainContext:
        """Detect domain using T2 Smart LLM model.

        Args:
            snapshot: The folder structure snapshot.

        Returns:
            DomainContext from LLM analysis.
        """
        # Build structure summary
        structure_text = self._build_structure_summary(snapshot, max_depth=3)

        # Build prompt (try registry first, fall back to default)
        prompt = None
        if self._prompt_registry is not None:
            try:
                prompt = self._prompt_registry.get(
                    "domain_detection",
                    structure_json=structure_text,
                )
            except (KeyError, FileNotFoundError):
                pass

        domain_options = ", ".join(sorted(DOMAIN_TYPES))
        if prompt is None:
            prompt = f"""Given this folder structure (top 3 levels with file counts and sample filenames):

{structure_text}

What domain is this? Options: {domain_options}.

Reply with valid JSON only: {{"domain": "<domain_type>", "confidence": <0.0-1.0>, "evidence": ["<signal1>", "<signal2>", ...]}}

The evidence list should contain 2-5 specific signals from the folder structure that support your classification."""

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
        response = self._llm_client.generate(prompt, model=model, temperature=0.0)

        if not response.success:
            return self._detect_with_keywords(snapshot)

        # Parse JSON response
        return self._parse_llm_response(response.text, response.model_used, snapshot)

    def _parse_llm_response(
        self,
        response_text: str,
        model_used: str,
        snapshot: "StructureSnapshot",
    ) -> DomainContext:
        """Parse LLM response and extract domain context.

        Args:
            response_text: Raw response from LLM.
            model_used: Model that generated the response.
            snapshot: Original structure snapshot (for fallback).

        Returns:
            DomainContext from parsed response or fallback.
        """
        # Try to extract JSON from response
        text = response_text.strip()

        # Remove markdown code blocks if present
        if text.startswith("```"):
            # Find content between ``` markers
            lines = text.split("\n")
            json_lines = []
            in_block = False
            for line in lines:
                if line.startswith("```"):
                    in_block = not in_block
                    continue
                if in_block:
                    json_lines.append(line)
            text = "\n".join(json_lines)
        text = text.strip()

        # Try to find JSON object in text
        json_match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
        if json_match:
            text = json_match.group()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Failed to parse, fall back to keywords
            return self._detect_with_keywords(snapshot)

        # Extract fields
        domain = data.get("domain", "generic_business")
        if domain not in DOMAIN_TYPES:
            domain = "generic_business"

        confidence = data.get("confidence", 0.5)
        if not isinstance(confidence, (int, float)):
            confidence = 0.5
        confidence = max(0.0, min(1.0, float(confidence)))

        evidence = data.get("evidence", [])
        if not isinstance(evidence, list):
            evidence = []
        evidence = [str(e) for e in evidence if e]

        return DomainContext(
            detected_domain=domain,
            confidence=confidence,
            evidence=evidence,
            model_used=model_used,
        )

    def _detect_with_keywords(self, snapshot: "StructureSnapshot") -> DomainContext:
        """Detect domain using keyword matching when LLM is unavailable.

        Args:
            snapshot: The folder structure snapshot.

        Returns:
            DomainContext from keyword analysis.
        """
        # Collect all folder names and sample filenames
        text_corpus: list[str] = []
        for folder in snapshot.folders:
            text_corpus.append(folder.name.lower())
            for fname in folder.sample_filenames:
                text_corpus.append(fname.lower())

        # Score each domain based on keyword matches
        domain_scores: dict[str, tuple[int, list[str]]] = {}

        for domain, keywords in DOMAIN_KEYWORDS.items():
            matches: list[str] = []
            for text in text_corpus:
                # Split on common separators
                words = re.split(r"[_\-\s./\\]+", text)
                for word in words:
                    if word in keywords:
                        matches.append(word)

            domain_scores[domain] = (len(matches), list(set(matches)))

        # Find the domain with the highest score
        best_domain = "generic_business"
        best_score = 0
        best_evidence: list[str] = []

        for domain, (score, matches) in domain_scores.items():
            if score > best_score:
                best_domain = domain
                best_score = score
                best_evidence = matches

        # Calculate confidence based on score
        # More matches = higher confidence, capped at 0.85 for keyword fallback
        if best_score == 0:
            confidence = 0.3  # Low confidence for no matches
        elif best_score < 3:
            confidence = 0.5
        elif best_score < 6:
            confidence = 0.65
        else:
            confidence = min(0.85, 0.65 + (best_score - 6) * 0.02)

        # Build evidence strings
        evidence = [f"Matched keyword: {kw}" for kw in best_evidence[:5]]
        if not evidence:
            evidence = ["No strong domain signals detected, defaulting to generic_business"]

        return DomainContext(
            detected_domain=best_domain,
            confidence=confidence,
            evidence=evidence,
            model_used="keyword_fallback",
        )


def detect_domain(
    snapshot: "StructureSnapshot",
    llm_client: "LLMClient | None" = None,
    model_router: "ModelRouter | None" = None,
    prompt_registry: "PromptRegistry | None" = None,
    use_llm: bool = True,
) -> DomainContext:
    """Convenience function to detect the domain of a folder structure.

    Args:
        snapshot: The analyzed folder structure.
        llm_client: Optional LLM client for detection.
        model_router: Optional model router for tier selection.
        prompt_registry: Optional prompt registry for loading prompts.
        use_llm: Whether to attempt LLM detection (default True).

    Returns:
        DomainContext with detection results.
    """
    detector = DomainDetector(
        llm_client=llm_client,
        model_router=model_router,
        prompt_registry=prompt_registry,
    )
    return detector.detect_domain(snapshot, use_llm=use_llm)
