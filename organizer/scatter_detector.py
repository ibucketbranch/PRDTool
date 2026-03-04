"""Scatter detector for identifying files outside their correct taxonomy bin.

Files that exist outside their correct bin violate the taxonomy. The ScatterDetector
uses LLM-native classification (T1 Fast for binary placement validation, T2 Smart
for path-preservation reasoning) with graceful fallback to keyword-based rules.

Locked bins cannot be renamed or merged by the agent. Every scatter proposal includes
an LLM-generated explanation. If Ollama is unavailable, falls back to category
mapper + filename signals.

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

from organizer.model_router import ModelTier, TaskProfile
from organizer.taxonomy_utils import Taxonomy, is_bin_locked

if TYPE_CHECKING:
    from organizer.llm_client import LLMClient
    from organizer.model_router import ModelRouter
    from organizer.prompt_registry import PromptRegistry


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
        taxonomy: Taxonomy | dict[str, Any] | None = None,
        prompt_registry: "PromptRegistry | None" = None,
        escalation_threshold: float = 0.75,
        use_llm: bool = True,
    ):
        """Initialize the scatter detector.

        Args:
            llm_client: LLM client for classification. If None, uses keyword fallback.
            model_router: Model router for tier selection. If None, auto-created.
            taxonomy: Taxonomy object or dictionary defining bins and categories.
            prompt_registry: Registry for loading prompts. If None, uses inline prompts.
            escalation_threshold: Confidence threshold for escalating to higher tier.
            use_llm: Whether to use LLM for validation. If False, uses keyword fallback.
        """
        self._llm_client = llm_client
        self._taxonomy = taxonomy or {}
        self._prompt_registry = prompt_registry
        self._escalation_threshold = escalation_threshold
        self._use_llm = use_llm and llm_client is not None

        # Auto-create model router if LLM client is provided
        if model_router is not None:
            self._model_router = model_router
        elif llm_client is not None:
            from organizer.model_router import ModelRouter

            self._model_router = ModelRouter(llm_client=llm_client)
        else:
            self._model_router = None

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
        if isinstance(self._taxonomy, Taxonomy):
            for name in self._taxonomy.get_bin_names():
                locked = " (locked)" if self._taxonomy.is_bin_locked(name) else ""
                bins.append(f"- {name}{locked}")
        else:
            # Dict format
            canonical_roots = self._taxonomy.get("canonical_roots", [])
            locked_bins = self._taxonomy.get("locked_bins", {})
            for name in canonical_roots:
                locked = " (locked)" if locked_bins.get(name, False) else ""
                bins.append(f"- {name}{locked}")
        return "\n".join(bins) if bins else "No bins defined"

    def _get_available_bins(self) -> list[str]:
        """Get list of available bins from taxonomy.

        Returns:
            List of bin names.
        """
        if isinstance(self._taxonomy, Taxonomy):
            return self._taxonomy.get_bin_names()
        elif isinstance(self._taxonomy, dict):
            return self._taxonomy.get("canonical_roots", [])
        return []

    def _is_bin_locked(self, bin_name: str) -> bool:
        """Check if a bin is locked.

        Args:
            bin_name: The bin name to check.

        Returns:
            True if the bin is locked, False otherwise.
        """
        return is_bin_locked(self._taxonomy, bin_name)

    def _parse_llm_json_response(self, text: str) -> dict[str, Any] | None:
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

    def _extract_confidence(self, data: dict[str, Any]) -> float:
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

    def _validate_with_llm(
        self,
        file_path: str,
        filename: str,
        current_bin: str,
        expected_bin: str,
        content_preview: str,
    ) -> tuple[bool | None, str, float, str, str | None]:
        """Validate file placement using LLM with escalation.

        Uses T1 Fast model first, escalates to T2 Smart if confidence < threshold.

        Args:
            file_path: Path to the file.
            filename: Name of the file.
            current_bin: Current bin name.
            expected_bin: Expected bin from keyword matching.
            content_preview: File content preview.

        Returns:
            Tuple of (belongs_here, correct_bin, confidence, reason, model_used).
            If model_used is None, LLM failed and caller should fall back to keywords.
        """
        if self._llm_client is None or self._model_router is None:
            return True, current_bin, 0.5, "LLM unavailable", ""

        # Build prompt
        bins_str = self._build_bins_list()

        # Try to get prompt from registry
        prompt = None
        if self._prompt_registry is not None:
            try:
                prompt = self._prompt_registry.get(
                    "validate_placement",
                    filename=filename,
                    current_path=file_path,
                    current_bin=current_bin,
                    expected_bin=expected_bin,
                    content=content_preview,
                )
            except (KeyError, FileNotFoundError):
                pass

        if prompt is None:
            # Use inline prompt
            prompt = f"""File '{filename}' is in '{current_bin}'.
Based on its name and content preview, does it belong in '{current_bin}' or should it be in '{expected_bin}'?

Content Preview: {content_preview}

Available bins:
{bins_str}

Reply with JSON:
{{
    "belongs_here": true or false,
    "correct_bin": "bin_name",
    "confidence": 0.0 to 1.0,
    "reason": "brief explanation"
}}"""

        # Start with T1 Fast model
        profile = TaskProfile(task_type="validate", complexity="low")

        try:
            decision = self._model_router.route(profile)
            model = decision.model
            tier = decision.tier
        except RuntimeError:
            # No models available
            return True, current_bin, 0.5, "No LLM models available", ""

        # Generate response
        response = self._llm_client.generate(prompt, model=model, temperature=0.0)

        if not response.success:
            # Return None for model_used to indicate LLM failure
            return None, current_bin, 0.5, f"LLM error: {response.error}", None

        # Parse response
        data = self._parse_llm_json_response(response.text)
        if data is None:
            # Return None for model_used to indicate LLM failure
            return None, current_bin, 0.5, "Failed to parse LLM response", None

        belongs_here = data.get("belongs_here", True)
        confidence = self._extract_confidence(data)
        reason = data.get("reason", "No reason provided")
        correct_bin = data.get("correct_bin", current_bin)

        # Check if we should escalate to T2 Smart
        if confidence < self._escalation_threshold and tier == ModelTier.FAST:
            # Escalate to T2 Smart
            smart_profile = TaskProfile(task_type="validate", complexity="medium")
            try:
                smart_decision = self._model_router.route(smart_profile)
                smart_model = smart_decision.model

                smart_response = self._llm_client.generate(
                    prompt, model=smart_model, temperature=0.0
                )

                if smart_response.success:
                    smart_data = self._parse_llm_json_response(smart_response.text)
                    if smart_data is not None:
                        belongs_here = smart_data.get("belongs_here", belongs_here)
                        confidence = self._extract_confidence(smart_data)
                        reason = smart_data.get("reason", reason)
                        correct_bin = smart_data.get("correct_bin", correct_bin)
                        model = smart_model
            except RuntimeError:
                # Stick with T1 result
                pass

        return belongs_here, correct_bin, confidence, reason, model

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

        Uses LLM validation when available, with automatic escalation from T1 Fast
        to T2 Smart when confidence is low. Falls back to keyword matching when
        LLM is unavailable.

        Args:
            file_path: Path to the file to validate.
            base_path: Base path for bin extraction.

        Returns:
            ScatterViolation if file is misplaced, None if correct.
        """
        current_bin = self._get_current_bin(file_path, base_path)
        if not current_bin:
            return None

        filename = Path(file_path).name

        # First check with keywords to get an expected bin
        kw_belongs_here, kw_expected_bin, kw_confidence = self._validate_with_keywords(
            file_path, current_bin
        )

        if kw_belongs_here:
            # Keywords say it's fine, no violation
            return None

        # Keywords suggest a violation - validate with LLM if available
        if self._use_llm and self._llm_client is not None and self._is_llm_available():
            content_preview = self._get_file_content_preview(file_path)
            (
                llm_belongs_here,
                llm_correct_bin,
                llm_confidence,
                llm_reason,
                model_used,
            ) = self._validate_with_llm(
                file_path,
                filename,
                current_bin,
                kw_expected_bin,
                content_preview,
            )

            # Check if LLM actually succeeded (model_used is not None)
            if model_used is not None:
                if llm_belongs_here:
                    # LLM says it's fine, no violation
                    return None

                # LLM confirms violation - get path preservation suggestion
                expected_bin = llm_correct_bin if llm_correct_bin else kw_expected_bin
                path_result = self.suggest_subpath(file_path, expected_bin)

                return ScatterViolation(
                    file_path=file_path,
                    current_bin=current_bin,
                    expected_bin=expected_bin,
                    confidence=llm_confidence,
                    reason=llm_reason,
                    model_used=model_used,
                    suggested_subpath=path_result.suggested_subpath,
                    used_keyword_fallback=False,
                )
            # LLM failed, fall through to keyword-based result

        # Use keyword-based result - also get path preservation suggestion
        path_result = self.suggest_subpath(file_path, kw_expected_bin)

        return ScatterViolation(
            file_path=file_path,
            current_bin=current_bin,
            expected_bin=kw_expected_bin,
            confidence=kw_confidence,
            reason=f"File contains keywords suggesting it belongs in {kw_expected_bin}",
            model_used="",
            suggested_subpath=path_result.suggested_subpath,
            used_keyword_fallback=True,
        )

    def suggest_subpath(
        self, file_path: str, target_bin: str
    ) -> PathPreservationResult:
        """Suggest a subfolder path within the target bin.

        Uses T2 Smart model for LLM-powered path preservation reasoning.
        Preserves year/agency hierarchy when moving files. Never flattens
        existing hierarchy (e.g., 2011/IRS/1040.pdf stays organized).

        Args:
            file_path: Path to the file.
            target_bin: The bin the file will be moved to.

        Returns:
            PathPreservationResult with suggested subpath.
        """
        filename = Path(file_path).name

        # Try LLM-powered path preservation if available
        if self._use_llm and self._llm_client is not None and self._is_llm_available():
            result = self._suggest_subpath_with_llm(file_path, filename, target_bin)
            if result is not None:
                return result

        # Fall back to keyword-based heuristics
        return self._suggest_subpath_with_keywords(file_path, filename)

    def _suggest_subpath_with_llm(
        self, file_path: str, filename: str, target_bin: str
    ) -> PathPreservationResult | None:
        """Use T2 Smart model to suggest subfolder structure.

        Args:
            file_path: Path to the file.
            filename: Name of the file.
            target_bin: Target bin for the file.

        Returns:
            PathPreservationResult with LLM suggestion, or None if failed.
        """
        if self._llm_client is None or self._model_router is None:
            return None

        content_preview = self._get_file_content_preview(file_path)

        # Try to get prompt from registry
        prompt = None
        if self._prompt_registry is not None:
            try:
                prompt = self._prompt_registry.get(
                    "suggest_subfolder",
                    filename=filename,
                    target_bin=target_bin,
                    content=content_preview,
                )
            except (KeyError, FileNotFoundError):
                pass

        if prompt is None:
            # Use inline prompt
            prompt = f"""What subfolder structure should '{filename}' have inside '{target_bin}'?
Preserve year/agency hierarchy where appropriate.

Content Preview: {content_preview}

Reply with JSON:
{{
    "suggested_subpath": "subfolder/path",
    "reason": "brief explanation"
}}"""

        # Use T2 Smart for path preservation reasoning
        profile = TaskProfile(task_type="analyze", complexity="medium")

        try:
            decision = self._model_router.route(profile)
            model = decision.model
        except RuntimeError:
            return None

        response = self._llm_client.generate(prompt, model=model, temperature=0.0)

        if not response.success:
            return None

        data = self._parse_llm_json_response(response.text)
        if data is None:
            return None

        suggested_subpath = data.get("suggested_subpath", "")
        reason = data.get("reason", "LLM suggestion")

        return PathPreservationResult(
            suggested_subpath=suggested_subpath,
            reason=reason,
            model_used=model,
            confidence=0.85,
        )

    def _suggest_subpath_with_keywords(
        self, file_path: str, filename: str
    ) -> PathPreservationResult:
        """Suggest subfolder using keyword-based heuristics.

        Args:
            file_path: Path to the file.
            filename: Name of the file.

        Returns:
            PathPreservationResult with keyword-based suggestion.
        """
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

        # Try to extract agency patterns
        agency_patterns = {
            r"irs": "IRS",
            r"ssa|social.?security": "SSA",
            r"va|veteran": "VA",
            r"dol|labor": "DOL",
            r"medicare|medicaid": "CMS",
        }

        for pattern, agency in agency_patterns.items():
            if re.search(pattern, filename.lower()):
                return PathPreservationResult(
                    suggested_subpath=agency,
                    reason=f"Detected agency: {agency}",
                    model_used="",
                    confidence=0.75,
                )

        return PathPreservationResult(
            suggested_subpath="",
            reason="No subfolder structure detected",
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

        Uses LLM-powered validation (T1 Fast with escalation to T2 Smart)
        when available, with graceful fallback to keyword-based rules.

        Args:
            base_path: Root directory to scan.
            max_files: Maximum number of files to scan.
            file_extensions: If provided, only scan files with these extensions.

        Returns:
            ScatterDetectionResult with all violations found.
        """
        # Determine if LLM is available
        llm_available = (
            self._use_llm
            and self._llm_client is not None
            and self._is_llm_available()
        )

        result = ScatterDetectionResult(
            used_keyword_fallback=not llm_available,
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
                result.model_used = violation.model_used
                result.used_keyword_fallback = violation.used_keyword_fallback
            result.files_scanned = 1
            return result

        files_checked = 0
        models_used: set[str] = set()
        any_keyword_fallback = False

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
                        if violation.model_used:
                            models_used.add(violation.model_used)
                        if violation.used_keyword_fallback:
                            any_keyword_fallback = True
                    else:
                        result.files_in_correct_bin += 1
                except Exception as e:
                    result.errors.append(f"Error processing {file_path}: {e}")

            if files_checked >= max_files:
                break

        result.files_scanned = files_checked
        result.model_used = ", ".join(sorted(models_used)) if models_used else ""
        result.used_keyword_fallback = any_keyword_fallback or not models_used
        return result


def detect_scatter(
    base_path: str,
    taxonomy: Taxonomy | dict[str, Any] | None = None,
    llm_client: "LLMClient | None" = None,
    model_router: "ModelRouter | None" = None,
    use_llm: bool = True,
    max_files: int = 1000,
    file_extensions: set[str] | None = None,
) -> ScatterDetectionResult:
    """Convenience function to detect scatter violations.

    Uses LLM-powered validation when llm_client is provided, with
    graceful fallback to keyword-based rules when unavailable.

    Args:
        base_path: Root directory to scan.
        taxonomy: Optional taxonomy configuration (Taxonomy object or dict).
        llm_client: Optional LLM client for validation.
        model_router: Optional model router for tier selection.
        use_llm: Whether to use LLM for validation (default True).
        max_files: Maximum number of files to scan.
        file_extensions: Optional extension filter.

    Returns:
        ScatterDetectionResult with all violations found.
    """
    detector = ScatterDetector(
        llm_client=llm_client,
        model_router=model_router,
        taxonomy=taxonomy,
        use_llm=use_llm,
    )
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
