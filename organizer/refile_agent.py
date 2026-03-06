"""ReFileMe-Agent for detecting and handling drifted files.

After filing, a user may accidentally move a file. The ReFileMe-Agent detects
drift by comparing current locations against routing history, determines if
the drift was intentional or accidental using LLM assessment, and proposes
refile actions.

Uses T1 Fast for initial drift assessment (intentional vs accidental),
escalates to T2 Smart when confidence is low. Falls back to path-type
heuristics (taxonomy path = intentional, Desktop/Downloads = accidental)
if LLM is unavailable.

Example usage:
    agent = ReFileAgent(llm_client=client, model_router=router)
    drift_records = agent.detect_drift(routing_history, filesystem_path)
    for record in drift_records:
        print(f"{record.file_path}: {record.drift_assessment}")
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from organizer.file_dna import compute_file_hash
from organizer.model_router import ModelTier, TaskProfile
from organizer.routing_history import RoutingHistory

if TYPE_CHECKING:
    from organizer.llm_client import LLMClient
    from organizer.model_router import ModelRouter
    from organizer.prompt_registry import PromptRegistry


# Default lookback period for drift detection (days)
DEFAULT_LOOKBACK_DAYS = 90

# Paths that typically indicate accidental drift
ACCIDENTAL_DRIFT_PATHS = {
    "Desktop",
    "Downloads",
    "Trash",
    ".Trash",
    "tmp",
    "temp",
    "Temporary Items",
}


def _now_iso() -> str:
    """Get current timestamp in ISO format."""
    return datetime.now().isoformat()


@dataclass
class DriftRecord:
    """A file that has moved from its filed location.

    Attributes:
        file_path: Current path where the file was found.
        original_filed_path: Path where the file was originally filed.
        current_path: Same as file_path (for clarity in API).
        filed_by: Agent or method that originally filed the file.
        filed_at: ISO timestamp when the file was filed.
        detected_at: ISO timestamp when drift was detected.
        sha256_hash: Hash of the current file for verification.
        drift_assessment: "likely_intentional" or "likely_accidental".
        reason: Natural language explanation of the assessment.
        model_used: LLM model used for assessment (empty if keyword fallback).
        confidence: Confidence in the assessment (0.0-1.0).
        suggested_destination: Where to refile (if original path gone).
        original_routing_record: The original routing record for reference.
    """

    file_path: str
    original_filed_path: str
    current_path: str
    filed_by: str = ""
    filed_at: str = ""
    detected_at: str = ""
    sha256_hash: str = ""
    drift_assessment: str = ""  # "likely_intentional" or "likely_accidental"
    reason: str = ""
    model_used: str = ""
    confidence: float = 0.5
    suggested_destination: str = ""
    original_routing_record: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Set default timestamp if not provided."""
        if not self.detected_at:
            self.detected_at = _now_iso()
        if not self.current_path:
            self.current_path = self.file_path

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "file_path": self.file_path,
            "original_filed_path": self.original_filed_path,
            "current_path": self.current_path,
            "filed_by": self.filed_by,
            "filed_at": self.filed_at,
            "detected_at": self.detected_at,
            "sha256_hash": self.sha256_hash,
            "drift_assessment": self.drift_assessment,
            "reason": self.reason,
            "model_used": self.model_used,
            "confidence": self.confidence,
            "suggested_destination": self.suggested_destination,
            "original_routing_record": self.original_routing_record,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DriftRecord":
        """Create DriftRecord from dictionary."""
        return cls(
            file_path=data.get("file_path", ""),
            original_filed_path=data.get("original_filed_path", ""),
            current_path=data.get("current_path", ""),
            filed_by=data.get("filed_by", ""),
            filed_at=data.get("filed_at", ""),
            detected_at=data.get("detected_at", ""),
            sha256_hash=data.get("sha256_hash", ""),
            drift_assessment=data.get("drift_assessment", ""),
            reason=data.get("reason", ""),
            model_used=data.get("model_used", ""),
            confidence=data.get("confidence", 0.5),
            suggested_destination=data.get("suggested_destination", ""),
            original_routing_record=data.get("original_routing_record", {}),
        )

    @property
    def is_likely_accidental(self) -> bool:
        """Check if drift is likely accidental (high priority)."""
        return self.drift_assessment == "likely_accidental"

    @property
    def is_likely_intentional(self) -> bool:
        """Check if drift is likely intentional (low priority)."""
        return self.drift_assessment == "likely_intentional"


@dataclass
class DriftDetectionResult:
    """Result of drift detection across routing history.

    Attributes:
        drift_records: List of detected drift records.
        files_checked: Total number of routing records checked.
        files_still_in_place: Files still at their filed location.
        files_missing: Files not found at filed path or elsewhere.
        errors: List of error messages encountered during detection.
        model_used: Primary model used for assessment.
        used_keyword_fallback: Whether keyword fallback was used.
    """

    drift_records: list[DriftRecord] = field(default_factory=list)
    files_checked: int = 0
    files_still_in_place: int = 0
    files_missing: int = 0
    errors: list[str] = field(default_factory=list)
    model_used: str = ""
    used_keyword_fallback: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "drift_records": [r.to_dict() for r in self.drift_records],
            "files_checked": self.files_checked,
            "files_still_in_place": self.files_still_in_place,
            "files_missing": self.files_missing,
            "errors": self.errors.copy(),
            "model_used": self.model_used,
            "used_keyword_fallback": self.used_keyword_fallback,
        }

    def get_accidental_drifts(self) -> list[DriftRecord]:
        """Get drifts assessed as likely accidental (high priority)."""
        return [r for r in self.drift_records if r.is_likely_accidental]

    def get_intentional_drifts(self) -> list[DriftRecord]:
        """Get drifts assessed as likely intentional (low priority)."""
        return [r for r in self.drift_records if r.is_likely_intentional]


@dataclass
class DestinationSuggestion:
    """Suggested destination for a drifted file.

    Attributes:
        suggested_path: The suggested destination path.
        confidence: Confidence in the suggestion (0.0-1.0).
        reason: Why this destination was suggested.
        model_used: Model that made the suggestion.
    """

    suggested_path: str
    confidence: float
    reason: str
    model_used: str


class ReFileAgent:
    """Agent for detecting and handling drifted files.

    Detects files that have moved from their filed locations using routing
    history comparison. Uses LLM to assess whether drift was intentional
    (user reorganized) or accidental (drag-drop). Falls back to path-type
    heuristics if LLM unavailable.

    Example:
        agent = ReFileAgent(llm_client=client, model_router=router)
        result = agent.detect_drift(routing_history, base_path)
        for record in result.drift_records:
            if record.is_likely_accidental:
                print(f"High priority: {record.file_path}")
    """

    def __init__(
        self,
        llm_client: "LLMClient | None" = None,
        model_router: "ModelRouter | None" = None,
        prompt_registry: "PromptRegistry | None" = None,
        escalation_threshold: float = 0.75,
        use_llm: bool = True,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    ):
        """Initialize the ReFile agent.

        Args:
            llm_client: LLM client for drift assessment. If None, uses keyword fallback.
            model_router: Model router for tier selection. Auto-created if llm_client provided.
            prompt_registry: Registry for loading prompts.
            escalation_threshold: Confidence threshold for escalating to higher tier.
            use_llm: Whether to use LLM for assessment.
            lookback_days: How many days back to check routing history.
        """
        self._llm_client = llm_client
        self._prompt_registry = prompt_registry
        self._escalation_threshold = escalation_threshold
        self._use_llm = use_llm and llm_client is not None
        self._lookback_days = lookback_days

        # Auto-create model router if LLM client is provided
        if model_router is not None:
            self._model_router = model_router
        elif llm_client is not None:
            from organizer.model_router import ModelRouter

            self._model_router = ModelRouter(llm_client=llm_client)
        else:
            self._model_router = None

    def _is_llm_available(self) -> bool:
        """Check if LLM assessment is available."""
        if self._llm_client is None:
            return False
        try:
            return self._llm_client.is_ollama_available(timeout_s=5)
        except Exception:
            return False

    def _is_in_inbox(self, path: str, inbox_patterns: list[str] | None = None) -> bool:
        """Check if a path is in the In-Box.

        Files moved to In-Box are handled by the Filing-Agent, not ReFile-Agent.

        Args:
            path: Path to check.
            inbox_patterns: Optional patterns to match inbox paths.

        Returns:
            True if path appears to be in an inbox folder.
        """
        if inbox_patterns is None:
            inbox_patterns = ["In-Box", "Inbox", "inbox", "in-box"]

        path_lower = path.lower()
        for pattern in inbox_patterns:
            if pattern.lower() in path_lower:
                return True
        return False

    def _is_taxonomy_path(self, path: str, taxonomy_roots: list[str] | None = None) -> bool:
        """Check if a path is a valid taxonomy location.

        Args:
            path: Path to check.
            taxonomy_roots: Known taxonomy root folder names.

        Returns:
            True if path appears to be a taxonomy-organized location.
        """
        if taxonomy_roots is None:
            taxonomy_roots = [
                "VA",
                "Finances Bin",
                "Work Bin",
                "Health",
                "Archive",
                "Employment",
                "Projects",
                "Personal",
            ]

        for root in taxonomy_roots:
            if root in path:
                return True
        return False

    def _is_accidental_location(self, path: str) -> bool:
        """Check if a path indicates accidental drift.

        Paths like Desktop, Downloads, Trash typically indicate accidental moves.

        Args:
            path: Path to check.

        Returns:
            True if path suggests accidental drift.
        """
        parts = Path(path).parts
        for part in parts:
            if part in ACCIDENTAL_DRIFT_PATHS:
                return True
        return False

    def _search_file_by_name_and_hash(
        self,
        filename: str,
        expected_hash: str | None,
        search_root: str,
        max_depth: int = 5,
    ) -> str | None:
        """Search for a file by name and optionally verify by hash.

        Args:
            filename: Name of the file to find.
            expected_hash: Expected SHA-256 hash (if known).
            search_root: Root directory to search in.
            max_depth: Maximum directory depth to search.

        Returns:
            Path to the found file, or None if not found.
        """
        root = Path(search_root)
        if not root.exists():
            return None

        try:
            for path in root.rglob(filename):
                # Check depth
                rel_path = path.relative_to(root)
                if len(rel_path.parts) > max_depth:
                    continue

                # Skip hidden directories
                if any(part.startswith(".") for part in rel_path.parts[:-1]):
                    continue

                if expected_hash:
                    try:
                        actual_hash = compute_file_hash(path)
                        if actual_hash == expected_hash:
                            return str(path)
                    except Exception:
                        continue
                else:
                    # Without hash, return first match
                    return str(path)
        except Exception:
            pass

        return None

    def _parse_llm_json_response(self, text: str) -> dict[str, Any] | None:
        """Parse JSON from LLM response.

        Args:
            text: Raw LLM response text.

        Returns:
            Parsed JSON dict, or None if parsing fails.
        """
        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to extract from markdown code block
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

    def _assess_drift_with_keywords(
        self,
        filename: str,
        original_path: str,
        current_path: str,
    ) -> tuple[str, str, float]:
        """Assess drift using path-type heuristics.

        Args:
            filename: Name of the file.
            original_path: Original filed path.
            current_path: Current location.

        Returns:
            Tuple of (drift_assessment, reason, confidence).
        """
        # Check if moved to an accidental location
        if self._is_accidental_location(current_path):
            return (
                "likely_accidental",
                f"File moved to common accidental location ({Path(current_path).parent.name})",
                0.85,
            )

        # Check if moved to a taxonomy-valid location
        if self._is_taxonomy_path(current_path):
            return (
                "likely_intentional",
                "File moved to a taxonomy-organized location",
                0.75,
            )

        # Check if in root of drive or user folder
        path = Path(current_path)
        if len(path.parts) <= 4:  # Close to root
            return (
                "likely_accidental",
                "File moved to near-root location",
                0.70,
            )

        # Default: uncertain, lean toward intentional
        return (
            "likely_intentional",
            "File location doesn't indicate accidental movement",
            0.55,
        )

    def _assess_drift_with_llm(
        self,
        filename: str,
        original_path: str,
        current_path: str,
        filed_at: str,
    ) -> tuple[str, str, float, str]:
        """Assess drift using LLM with escalation.

        Uses T1 Fast first, escalates to T2 Smart if confidence < threshold.

        Args:
            filename: Name of the file.
            original_path: Original filed path.
            current_path: Current location.
            filed_at: When the file was originally filed.

        Returns:
            Tuple of (drift_assessment, reason, confidence, model_used).
            model_used is empty string if LLM failed (fall back to keywords).
        """
        if self._llm_client is None or self._model_router is None:
            return ("", "", 0.5, "")

        # Build prompt
        prompt = None
        if self._prompt_registry is not None:
            try:
                prompt = self._prompt_registry.get(
                    "assess_drift",
                    filename=filename,
                    original_path=original_path,
                    current_path=current_path,
                    filed_date=filed_at,
                )
            except (KeyError, FileNotFoundError):
                pass

        if prompt is None:
            prompt = f"""File '{filename}' was filed at '{original_path}' on {filed_at}.
It is now at '{current_path}'.
Was this move intentional (user reorganized) or accidental (drag-drop)?

Reply with JSON:
{{
    "likely_intentional": true or false,
    "confidence": 0.0 to 1.0,
    "reason": "brief explanation"
}}"""

        # Start with T1 Fast
        profile = TaskProfile(task_type="validate", complexity="low")

        try:
            decision = self._model_router.route(profile)
            model = decision.model
            tier = decision.tier
        except RuntimeError:
            return ("", "", 0.5, "")

        response = self._llm_client.generate(prompt, model=model, temperature=0.0)

        if not response.success:
            return ("", "", 0.5, "")

        data = self._parse_llm_json_response(response.text)
        if data is None:
            return ("", "", 0.5, "")

        likely_intentional = data.get("likely_intentional", True)
        confidence = data.get("confidence", 0.5)
        if isinstance(confidence, (int, float)):
            confidence = max(0.0, min(1.0, float(confidence)))
        else:
            confidence = 0.5
        reason = data.get("reason", "No reason provided")

        # Escalate to T2 Smart if confidence < threshold
        if confidence < self._escalation_threshold and tier == ModelTier.FAST:
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
                        likely_intentional = smart_data.get(
                            "likely_intentional", likely_intentional
                        )
                        confidence = smart_data.get("confidence", confidence)
                        if isinstance(confidence, (int, float)):
                            confidence = max(0.0, min(1.0, float(confidence)))
                        reason = smart_data.get("reason", reason)
                        model = smart_model
            except RuntimeError:
                pass

        assessment = "likely_intentional" if likely_intentional else "likely_accidental"
        return (assessment, reason, confidence, model)

    def _suggest_destination_with_llm(
        self,
        filename: str,
        original_path: str,
        file_content_preview: str = "",
    ) -> DestinationSuggestion | None:
        """Suggest a new destination using T2 Smart LLM.

        Called when the original filing location no longer exists.

        Args:
            filename: Name of the file.
            original_path: Original path that no longer exists.
            file_content_preview: Optional content preview.

        Returns:
            DestinationSuggestion if successful, None otherwise.
        """
        if self._llm_client is None or self._model_router is None:
            return None

        prompt = None
        if self._prompt_registry is not None:
            try:
                prompt = self._prompt_registry.get(
                    "suggest_refile_destination",
                    filename=filename,
                    original_path=original_path,
                    content=file_content_preview,
                )
            except (KeyError, FileNotFoundError):
                pass

        if prompt is None:
            prompt = f"""File '{filename}' was originally at '{original_path}' but that folder is gone.
Based on the current taxonomy and file content, where should it go now?

Content Preview: {file_content_preview[:500] if file_content_preview else 'N/A'}

Reply with JSON:
{{
    "suggested_path": "path/to/new/location",
    "confidence": 0.0 to 1.0,
    "reason": "brief explanation"
}}"""

        # Use T2 Smart for destination suggestion
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

        suggested_path = data.get("suggested_path", "")
        confidence = data.get("confidence", 0.5)
        if isinstance(confidence, (int, float)):
            confidence = max(0.0, min(1.0, float(confidence)))
        reason = data.get("reason", "LLM suggestion")

        if not suggested_path:
            return None

        return DestinationSuggestion(
            suggested_path=suggested_path,
            confidence=confidence,
            reason=reason,
            model_used=model,
        )

    def _suggest_destination_with_keywords(
        self,
        filename: str,
        original_path: str,
    ) -> DestinationSuggestion:
        """Suggest destination using keyword-based heuristics.

        Args:
            filename: Name of the file.
            original_path: Original path that no longer exists.

        Returns:
            DestinationSuggestion based on heuristics.
        """
        filename_lower = filename.lower()
        path_lower = original_path.lower()
        combined = f"{filename_lower} {path_lower}"

        # Extract year from filename
        year_match = re.search(r"(19|20)\d{2}", filename)
        year = year_match.group(0) if year_match else ""

        # Try to find a matching bin
        bin_keywords = {
            "tax": "Finances Bin/Taxes",
            "invoice": "Finances Bin/Invoices",
            "bill": "Finances Bin/Bills",
            "receipt": "Finances Bin/Receipts",
            "bank": "Finances Bin/Banking",
            "resume": "Employment/Resumes",
            "cv": "Employment/Resumes",
            "contract": "Work Bin/Contracts",
            "medical": "Health/Medical Records",
            "va": "VA",
            "veteran": "VA",
            "claim": "VA/Claims",
        }

        for keyword, bin_path in bin_keywords.items():
            if keyword in combined:
                suggested = bin_path
                if year:
                    suggested = f"{bin_path}/{year}"
                return DestinationSuggestion(
                    suggested_path=suggested,
                    confidence=0.6,
                    reason=f"Keyword '{keyword}' suggests {bin_path}",
                    model_used="",
                )

        # Fall back to Archive
        suggested = "Archive/Unfiled"
        if year:
            suggested = f"Archive/Unfiled/{year}"

        return DestinationSuggestion(
            suggested_path=suggested,
            confidence=0.4,
            reason="No clear category, suggesting Archive",
            model_used="",
        )

    def detect_drift(
        self,
        routing_history: RoutingHistory,
        search_root: str | None = None,
        lookback_days: int | None = None,
    ) -> DriftDetectionResult:
        """Detect files that have drifted from their filed locations.

        Compares routing history against current filesystem state. For each
        executed routing record, checks if the file still exists at the
        filed path. If not, searches by filename and hash to find the file.

        Args:
            routing_history: RoutingHistory instance with filed records.
            search_root: Root directory to search for drifted files.
            lookback_days: How many days back to check (default: lookback_days).

        Returns:
            DriftDetectionResult with all detected drift records.
        """
        if lookback_days is None:
            lookback_days = self._lookback_days

        # Determine if LLM is available
        llm_available = self._use_llm and self._is_llm_available()

        result = DriftDetectionResult(
            used_keyword_fallback=not llm_available,
        )

        # Calculate cutoff date
        cutoff = datetime.now() - timedelta(days=lookback_days)

        # Get recent routing records
        records = routing_history.get_recent(limit=1000)
        models_used: set[str] = set()

        for record in records:
            # Parse routed_at timestamp
            try:
                routed_at = datetime.fromisoformat(record.routed_at)
                if routed_at < cutoff:
                    continue  # Too old
            except (ValueError, TypeError):
                continue  # Invalid timestamp

            # Only check executed routings
            if record.status != "executed":
                continue

            result.files_checked += 1

            # Construct expected path
            expected_path = Path(record.destination_bin) / record.filename

            # Check if file still exists at expected location
            if expected_path.exists():
                result.files_still_in_place += 1
                continue

            # File not at expected location - search for it
            current_path = None
            file_hash = None

            if search_root:
                # Try to compute expected hash from original if we have it
                current_path = self._search_file_by_name_and_hash(
                    record.filename,
                    expected_hash=None,  # No hash available from routing record
                    search_root=search_root,
                )

            if current_path is None:
                # File not found anywhere
                result.files_missing += 1
                continue

            # File found at a different location - this is drift
            # Skip if moved to In-Box (Filing-Agent handles that)
            if self._is_in_inbox(current_path):
                continue

            # Compute hash for verification
            try:
                file_hash = compute_file_hash(current_path)
            except Exception:
                pass

            # Assess the drift
            if llm_available:
                assessment, reason, confidence, model_used = self._assess_drift_with_llm(
                    record.filename,
                    str(expected_path),
                    current_path,
                    record.routed_at,
                )
                if model_used:
                    models_used.add(model_used)
                else:
                    # LLM failed, fall back to keywords
                    assessment, reason, confidence = self._assess_drift_with_keywords(
                        record.filename,
                        str(expected_path),
                        current_path,
                    )
                    model_used = ""
            else:
                assessment, reason, confidence = self._assess_drift_with_keywords(
                    record.filename,
                    str(expected_path),
                    current_path,
                )
                model_used = ""

            # Create drift record
            drift = DriftRecord(
                file_path=current_path,
                original_filed_path=str(expected_path),
                current_path=current_path,
                filed_by="agent",  # Could be enhanced with actual agent info
                filed_at=record.routed_at,
                sha256_hash=file_hash or "",
                drift_assessment=assessment,
                reason=reason,
                model_used=model_used,
                confidence=confidence,
                original_routing_record=record.to_dict(),
            )

            result.drift_records.append(drift)

        result.model_used = ", ".join(sorted(models_used)) if models_used else ""
        return result

    def suggest_destination(
        self,
        file_path: str,
        original_path: str,
    ) -> DestinationSuggestion:
        """Suggest a destination for a drifted file.

        Called when the original filed location no longer exists and we need
        to suggest a new destination.

        Args:
            file_path: Current path of the file.
            original_path: Original path where it was filed.

        Returns:
            DestinationSuggestion with suggested path and reasoning.
        """
        filename = Path(file_path).name

        # Get content preview if possible
        content_preview = ""
        try:
            from organizer.file_dna import get_content_preview

            content_preview = get_content_preview(file_path, max_chars=500)
        except Exception:
            pass

        # Try LLM first
        if self._use_llm and self._is_llm_available():
            suggestion = self._suggest_destination_with_llm(
                filename, original_path, content_preview
            )
            if suggestion is not None:
                return suggestion

        # Fall back to keywords
        return self._suggest_destination_with_keywords(filename, original_path)

    def assess_single_file(
        self,
        file_path: str,
        original_path: str,
        filed_at: str,
    ) -> DriftRecord:
        """Assess drift for a single file.

        Useful for interactive or API-driven assessment.

        Args:
            file_path: Current path of the file.
            original_path: Original path where it was filed.
            filed_at: ISO timestamp when originally filed.

        Returns:
            DriftRecord with assessment.
        """
        filename = Path(file_path).name

        # Compute hash
        file_hash = ""
        try:
            file_hash = compute_file_hash(file_path)
        except Exception:
            pass

        # Assess the drift
        if self._use_llm and self._is_llm_available():
            assessment, reason, confidence, model_used = self._assess_drift_with_llm(
                filename,
                original_path,
                file_path,
                filed_at,
            )
            if not model_used:
                # LLM failed
                assessment, reason, confidence = self._assess_drift_with_keywords(
                    filename,
                    original_path,
                    file_path,
                )
                model_used = ""
        else:
            assessment, reason, confidence = self._assess_drift_with_keywords(
                filename,
                original_path,
                file_path,
            )
            model_used = ""

        return DriftRecord(
            file_path=file_path,
            original_filed_path=original_path,
            current_path=file_path,
            filed_at=filed_at,
            sha256_hash=file_hash,
            drift_assessment=assessment,
            reason=reason,
            model_used=model_used,
            confidence=confidence,
        )


def detect_drift(
    routing_history: RoutingHistory,
    search_root: str | None = None,
    llm_client: "LLMClient | None" = None,
    model_router: "ModelRouter | None" = None,
    use_llm: bool = True,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> DriftDetectionResult:
    """Convenience function to detect drift in routing history.

    Args:
        routing_history: RoutingHistory instance with filed records.
        search_root: Root directory to search for drifted files.
        llm_client: Optional LLM client for assessment.
        model_router: Optional model router for tier selection.
        use_llm: Whether to use LLM for assessment.
        lookback_days: How many days back to check.

    Returns:
        DriftDetectionResult with all detected drift records.
    """
    agent = ReFileAgent(
        llm_client=llm_client,
        model_router=model_router,
        use_llm=use_llm,
        lookback_days=lookback_days,
    )
    return agent.detect_drift(
        routing_history=routing_history,
        search_root=search_root,
        lookback_days=lookback_days,
    )


def save_drift_report(result: DriftDetectionResult, path: str | Path) -> None:
    """Save a drift detection report to JSON file.

    Args:
        result: The drift detection result to save.
        path: Path to save the JSON file.
    """
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(result.to_dict(), f, indent=2)


def load_drift_report(path: str | Path) -> DriftDetectionResult:
    """Load a drift detection report from JSON file.

    Args:
        path: Path to the JSON file.

    Returns:
        DriftDetectionResult loaded from file.
    """
    with open(path) as f:
        data = json.load(f)

    result = DriftDetectionResult(
        files_checked=data.get("files_checked", 0),
        files_still_in_place=data.get("files_still_in_place", 0),
        files_missing=data.get("files_missing", 0),
        errors=data.get("errors", []),
        model_used=data.get("model_used", ""),
        used_keyword_fallback=data.get("used_keyword_fallback", False),
    )

    for r_data in data.get("drift_records", []):
        result.drift_records.append(DriftRecord.from_dict(r_data))

    return result
