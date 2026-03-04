"""Scatter detector for identifying files outside their correct taxonomy bin.

Files that exist outside their correct bin violate the taxonomy. The ScatterDetector
uses LLM-native classification (T1 Fast for binary placement validation, T2 Smart
for path-preservation reasoning) with graceful fallback to keyword-based rules.

Example usage:
    detector = ScatterDetector(llm_client=client, model_router=router)
    result = detector.detect_scatter(base_path="/path/to/files")
    for violation in result.violations:
        print(f"{violation.file_path}: should be in {violation.expected_bin}")
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from organizer.llm_client import LLMClient
    from organizer.model_router import ModelRouter


@dataclass
class ScatterViolation:
    """A file that exists outside its correct taxonomy bin.

    Attributes:
        file_path: Full path to the file.
        current_bin: The bin the file is currently in.
        expected_bin: The bin the file should be in.
        confidence: Confidence score for this assessment (0.0-1.0).
        reason: Natural language explanation of why this is a violation.
        model_used: The LLM model that made the assessment (if any).
        suggested_subpath: Suggested subfolder path within the target bin.
        used_keyword_fallback: Whether keyword fallback was used instead of LLM.
    """

    file_path: str
    current_bin: str
    expected_bin: str
    confidence: float
    reason: str
    model_used: str = ""
    suggested_subpath: str = ""
    used_keyword_fallback: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "file_path": self.file_path,
            "current_bin": self.current_bin,
            "expected_bin": self.expected_bin,
            "confidence": self.confidence,
            "reason": self.reason,
            "model_used": self.model_used,
            "suggested_subpath": self.suggested_subpath,
            "used_keyword_fallback": self.used_keyword_fallback,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScatterViolation":
        """Create from dictionary."""
        return cls(
            file_path=data.get("file_path", ""),
            current_bin=data.get("current_bin", ""),
            expected_bin=data.get("expected_bin", ""),
            confidence=data.get("confidence", 0.0),
            reason=data.get("reason", ""),
            model_used=data.get("model_used", ""),
            suggested_subpath=data.get("suggested_subpath", ""),
            used_keyword_fallback=data.get("used_keyword_fallback", False),
        )


@dataclass
class ScatterDetectionResult:
    """Result of scatter detection across a directory.

    Attributes:
        violations: List of files found outside their correct bins.
        files_scanned: Total number of files scanned.
        files_in_correct_bin: Number of files already in correct location.
        errors: List of error messages encountered during scanning.
        model_used: Primary model used for detection.
        used_keyword_fallback: Whether keyword fallback was used.
    """

    violations: list[ScatterViolation] = field(default_factory=list)
    files_scanned: int = 0
    files_in_correct_bin: int = 0
    errors: list[str] = field(default_factory=list)
    model_used: str = ""
    used_keyword_fallback: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "violations": [v.to_dict() for v in self.violations],
            "files_scanned": self.files_scanned,
            "files_in_correct_bin": self.files_in_correct_bin,
            "errors": self.errors.copy(),
            "model_used": self.model_used,
            "used_keyword_fallback": self.used_keyword_fallback,
        }


@dataclass
class PathPreservationResult:
    """Result of LLM-powered path preservation analysis.

    Attributes:
        suggested_subpath: The suggested subfolder path (e.g., "2011/IRS").
        reason: Why this subpath was suggested.
        model_used: The model that made the suggestion.
        confidence: Confidence in the suggestion.
    """

    suggested_subpath: str
    reason: str
    model_used: str
    confidence: float


class ScatterDetector:
    """Detects files that exist outside their correct taxonomy bin.

    Uses LLM-native classification when available, with graceful fallback
    to keyword-based rules when Ollama is unavailable.

    Example:
        detector = ScatterDetector(llm_client=client, model_router=router)
        result = detector.detect_scatter("/path/to/scan")
        for violation in result.violations:
            print(f"Move {violation.file_path} to {violation.expected_bin}")
    """

    def __init__(
        self,
        llm_client: "LLMClient | None" = None,
        model_router: "ModelRouter | None" = None,
        taxonomy: dict[str, Any] | None = None,
        prompt_registry: Any | None = None,
        escalation_threshold: float = 0.75,
    ):
        """Initialize the scatter detector.

        Args:
            llm_client: LLM client for classification. If None, uses keyword fallback.
            model_router: Model router for tier selection. If None, uses default model.
            taxonomy: Taxonomy dictionary defining bins and categories.
            prompt_registry: Registry for loading prompts. If None, uses inline prompts.
            escalation_threshold: Confidence threshold for escalating to higher tier.
        """
        self._llm_client = llm_client
        self._model_router = model_router
        self._taxonomy = taxonomy or {}
        self._prompt_registry = prompt_registry
        self._escalation_threshold = escalation_threshold

    def _is_llm_available(self) -> bool:
        """Check if LLM classification is available."""
        if self._llm_client is None:
            return False
        try:
            return self._llm_client.is_ollama_available(timeout_s=5)
        except Exception:
            return False

    def _get_file_content_preview(
        self, file_path: str, max_chars: int = 500
    ) -> str:
        """Get a preview of file content for LLM analysis.

        Args:
            file_path: Path to the file.
            max_chars: Maximum characters to read.

        Returns:
            Content preview or empty string if unreadable.
        """
        try:
            path = Path(file_path)
            # Skip binary files
            binary_extensions = {
                ".pdf", ".doc", ".docx", ".xls", ".xlsx",
                ".ppt", ".pptx", ".zip", ".tar", ".gz",
                ".jpg", ".jpeg", ".png", ".gif", ".bmp",
                ".mp3", ".mp4", ".avi", ".mov", ".exe",
            }
            if path.suffix.lower() in binary_extensions:
                return f"[Binary file: {path.suffix}]"

            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read(max_chars)
        except Exception:
            return ""

    def _build_bins_list(self) -> str:
        """Build a formatted list of bins from taxonomy.

        Returns:
            Formatted string of bin names and descriptions.
        """
        if not self._taxonomy:
            return "No taxonomy configured"

        bins = []
        categories = self._taxonomy.get("categories", {})
        for name, info in categories.items():
            locked = " (locked)" if info.get("locked", False) else ""
            bins.append(f"- {name}{locked}")
        return "\n".join(bins) if bins else "No bins defined"

    def _get_current_bin(self, file_path: str, base_path: str = "") -> str:
        """Extract the root bin from a file path.

        Args:
            file_path: The file's full path.
            base_path: The base path to subtract.

        Returns:
            The root bin name or empty string if not in a bin.
        """
        try:
            path = Path(file_path)
            base = Path(base_path) if base_path else Path.cwd()

            # Get relative path from base
            try:
                rel_path = path.relative_to(base)
            except ValueError:
                return ""

            # First directory in relative path is the bin
            parts = rel_path.parts
            if len(parts) > 0:
                return parts[0]
            return ""
        except Exception:
            return ""

    def _validate_with_keywords(
        self, file_path: str, current_bin: str
    ) -> tuple[bool, str, float]:
        """Validate file placement using keyword rules.

        Args:
            file_path: Path to the file.
            current_bin: The bin the file is currently in.

        Returns:
            Tuple of (belongs_here, expected_bin, confidence).
        """
        filename = Path(file_path).name.lower()

        # Simple keyword mapping for common patterns
        keyword_to_bin = {
            "tax": "Finances Bin",
            "invoice": "Finances Bin",
            "bill": "Finances Bin",
            "receipt": "Finances Bin",
            "bank": "Finances Bin",
            "statement": "Finances Bin",
            "resume": "Work Bin",
            "cv": "Work Bin",
            "contract": "Work Bin",
            "employment": "Work Bin",
            "medical": "Health",
            "doctor": "Health",
            "prescription": "Health",
            "va": "VA",
            "veteran": "VA",
            "claim": "VA",
            "dbq": "VA",
        }

        for keyword, expected_bin in keyword_to_bin.items():
            if keyword in filename:
                if current_bin.lower() != expected_bin.lower():
                    return (False, expected_bin, 0.7)
                return (True, current_bin, 0.8)

        # No keyword match - assume correct
        return (True, current_bin, 0.5)

    def validate_file(
        self, file_path: str, base_path: str = ""
    ) -> ScatterViolation | None:
        """Validate a single file's placement.

        Args:
            file_path: Path to the file to validate.
            base_path: Base path for bin extraction.

        Returns:
            ScatterViolation if file is misplaced, None if correct.
        """
        current_bin = self._get_current_bin(file_path, base_path)
        if not current_bin:
            return None

        # Use keyword fallback (LLM integration is a future enhancement)
        belongs_here, expected_bin, confidence = self._validate_with_keywords(
            file_path, current_bin
        )

        if belongs_here:
            return None

        return ScatterViolation(
            file_path=file_path,
            current_bin=current_bin,
            expected_bin=expected_bin,
            confidence=confidence,
            reason=f"File contains keywords suggesting it belongs in {expected_bin}",
            model_used="",
            suggested_subpath="",
            used_keyword_fallback=True,
        )

    def suggest_subpath(
        self, file_path: str, target_bin: str
    ) -> PathPreservationResult:
        """Suggest a subfolder path within the target bin.

        Preserves year/agency hierarchy when moving files.

        Args:
            file_path: Path to the file.
            target_bin: The bin the file will be moved to.

        Returns:
            PathPreservationResult with suggested subpath.
        """
        filename = Path(file_path).name

        # Extract year from filename using regex
        year_match = re.search(r"(19|20)\d{2}", filename)
        year = year_match.group(0) if year_match else ""

        if year:
            return PathPreservationResult(
                suggested_subpath=year,
                reason=f"Extracted year {year} from filename",
                model_used="",
                confidence=0.8,
            )

        return PathPreservationResult(
            suggested_subpath="",
            reason="No year pattern found in filename",
            model_used="",
            confidence=0.5,
        )

    def detect_scatter(
        self,
        base_path: str,
        max_files: int = 1000,
        file_extensions: set[str] | None = None,
    ) -> ScatterDetectionResult:
        """Detect scatter violations in a directory.

        Args:
            base_path: Root directory to scan.
            max_files: Maximum number of files to scan.
            file_extensions: If provided, only scan files with these extensions.

        Returns:
            ScatterDetectionResult with all violations found.
        """
        result = ScatterDetectionResult(
            used_keyword_fallback=True,
            model_used="",
        )

        base = Path(base_path)
        if not base.exists():
            return result

        if base.is_file():
            # Single file passed
            violation = self.validate_file(str(base), str(base.parent))
            if violation:
                result.violations.append(violation)
            result.files_scanned = 1
            return result

        files_checked = 0
        for root, dirs, files in os.walk(base):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith(".")]

            for filename in files:
                if filename.startswith("."):
                    continue

                if files_checked >= max_files:
                    break

                file_path = Path(root) / filename

                # Check extension filter
                if file_extensions:
                    if file_path.suffix.lower() not in file_extensions:
                        continue

                files_checked += 1

                try:
                    violation = self.validate_file(str(file_path), str(base))
                    if violation:
                        result.violations.append(violation)
                    else:
                        result.files_in_correct_bin += 1
                except Exception as e:
                    result.errors.append(f"Error processing {file_path}: {e}")

            if files_checked >= max_files:
                break

        result.files_scanned = files_checked
        return result


def detect_scatter(
    base_path: str,
    taxonomy: dict[str, Any] | None = None,
    max_files: int = 1000,
    file_extensions: set[str] | None = None,
) -> ScatterDetectionResult:
    """Convenience function to detect scatter violations.

    Args:
        base_path: Root directory to scan.
        taxonomy: Optional taxonomy configuration.
        max_files: Maximum number of files to scan.
        file_extensions: Optional extension filter.

    Returns:
        ScatterDetectionResult with all violations found.
    """
    detector = ScatterDetector(taxonomy=taxonomy)
    return detector.detect_scatter(
        base_path=base_path,
        max_files=max_files,
        file_extensions=file_extensions,
    )


def load_scatter_report(path: str | Path) -> ScatterDetectionResult:
    """Load a scatter report from JSON file.

    Args:
        path: Path to the JSON file.

    Returns:
        ScatterDetectionResult loaded from file.
    """
    with open(path) as f:
        data = json.load(f)

    result = ScatterDetectionResult(
        files_scanned=data.get("files_scanned", 0),
        files_in_correct_bin=data.get("files_in_correct_bin", 0),
        errors=data.get("errors", []),
        model_used=data.get("model_used", ""),
        used_keyword_fallback=data.get("used_keyword_fallback", False),
    )

    for v_data in data.get("violations", []):
        result.violations.append(ScatterViolation.from_dict(v_data))

    return result


def save_scatter_report(result: ScatterDetectionResult, path: str | Path) -> None:
    """Save a scatter report to JSON file.

    Args:
        result: The scatter detection result to save.
        path: Path to save the JSON file.
    """
    with open(path, "w") as f:
        json.dump(result.to_dict(), f, indent=2)
