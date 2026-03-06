"""Learned Rules Store for routing file decisions.

This module provides the LearnedRuleStore class that loads routing rules
from the rule_generator module and matches files to destinations.

The merge priority is:
1. Learned rules (from structure analysis via LLM)
2. User overrides (from learned_overrides.py)
3. Built-in taxonomy (from ROOT_TAXONOMY.json)
4. Hardcoded ROUTING_RULES (from inbox_processor.py)

Example usage:
    store = LearnedRuleStore()
    destination, confidence = store.match("invoice_2024.pdf", {"keywords": ["invoice"]})
    if destination:
        print(f"Route to: {destination} (confidence: {confidence})")
"""

from __future__ import annotations

import fnmatch
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from organizer.learned_overrides import OverrideRegistry
    from organizer.taxonomy_utils import Taxonomy

# Default paths
DEFAULT_RULES_PATH = ".organizer/agent/learned_routing_rules.json"
DEFAULT_TAXONOMY_PATH = ".organizer/ROOT_TAXONOMY.json"


def _now_iso() -> str:
    """Get current timestamp in ISO format."""
    return datetime.now().isoformat()


@dataclass
class MatchResult:
    """Result of a rule match.

    Attributes:
        destination: The destination folder path.
        confidence: Confidence score from 0.0 to 1.0.
        rule_pattern: The pattern that matched.
        rule_source: Source of the rule (learned, override, taxonomy, hardcoded).
        reasoning: Optional explanation of why this rule matched.
    """

    destination: str
    confidence: float
    rule_pattern: str = ""
    rule_source: str = ""
    reasoning: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "destination": self.destination,
            "confidence": self.confidence,
            "rule_pattern": self.rule_pattern,
            "rule_source": self.rule_source,
            "reasoning": self.reasoning,
        }


@dataclass
class StoredRule:
    """A routing rule stored in the rule store.

    Attributes:
        pattern: The pattern to match (keyword, glob, or regex).
        destination: Target folder path.
        confidence: Base confidence for matches using this rule.
        pattern_type: Type of pattern (keyword, glob, regex).
        source_folder: The folder this rule was learned from.
        reasoning: Explanation of the rule.
        enabled: Whether this rule is active.
        hit_count: Number of times this rule has been matched.
        created_at: When the rule was created.
    """

    pattern: str
    destination: str
    confidence: float = 0.8
    pattern_type: str = "keyword"  # keyword, glob, regex
    source_folder: str = ""
    reasoning: str = ""
    enabled: bool = True
    hit_count: int = 0
    created_at: str = ""

    def __post_init__(self) -> None:
        """Set default timestamp if not provided."""
        if not self.created_at:
            self.created_at = _now_iso()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "pattern": self.pattern,
            "destination": self.destination,
            "confidence": self.confidence,
            "pattern_type": self.pattern_type,
            "source_folder": self.source_folder,
            "reasoning": self.reasoning,
            "enabled": self.enabled,
            "hit_count": self.hit_count,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StoredRule":
        """Create StoredRule from dictionary."""
        return cls(
            pattern=data.get("pattern", ""),
            destination=data.get("destination", ""),
            confidence=data.get("confidence", 0.8),
            pattern_type=data.get("pattern_type", "keyword"),
            source_folder=data.get("source_folder", ""),
            reasoning=data.get("reasoning", ""),
            enabled=data.get("enabled", True),
            hit_count=data.get("hit_count", 0),
            created_at=data.get("created_at", ""),
        )

    def matches(self, filename: str, content_signals: dict[str, Any] | None = None) -> bool:
        """Check if this rule matches a filename.

        Args:
            filename: The filename to check.
            content_signals: Optional content-based signals (keywords, dates, etc.).

        Returns:
            True if the rule matches.
        """
        if not self.enabled:
            return False

        filename_lower = filename.lower()
        stem = Path(filename).stem.lower()
        pattern_lower = self.pattern.lower()

        if self.pattern_type == "keyword":
            # Keyword matching: check if pattern is in filename or stem
            if pattern_lower in filename_lower or pattern_lower in stem:
                return True
            # Also check content signals
            if content_signals:
                keywords = content_signals.get("keywords", [])
                if isinstance(keywords, list):
                    for kw in keywords:
                        if isinstance(kw, str) and pattern_lower in kw.lower():
                            return True

        elif self.pattern_type == "glob":
            # Glob pattern matching (e.g., "*.pdf", "invoice_*")
            if fnmatch.fnmatch(filename_lower, pattern_lower):
                return True
            if fnmatch.fnmatch(stem, pattern_lower.replace(".*", "")):
                return True

        elif self.pattern_type == "regex":
            # Regex pattern matching
            try:
                if re.search(self.pattern, filename, re.IGNORECASE):
                    return True
            except re.error:
                pass  # Invalid regex, skip

        return False


class LearnedRuleStore:
    """Store for learned routing rules with priority-based matching.

    The store implements a priority-based matching system:
    1. Learned rules (highest priority)
    2. User overrides
    3. Built-in taxonomy
    4. Hardcoded ROUTING_RULES (lowest priority)

    Example:
        store = LearnedRuleStore()
        dest, conf = store.match("invoice.pdf")
        if dest:
            print(f"Route to {dest}")
    """

    def __init__(
        self,
        rules_path: str | Path = DEFAULT_RULES_PATH,
        taxonomy_path: str | Path | None = DEFAULT_TAXONOMY_PATH,
        override_registry: "OverrideRegistry | None" = None,
        auto_load: bool = True,
    ):
        """Initialize the rule store.

        Args:
            rules_path: Path to learned rules JSON file.
            taxonomy_path: Path to taxonomy JSON file (optional).
            override_registry: Optional OverrideRegistry for user overrides.
            auto_load: Whether to load rules on initialization.
        """
        self._rules_path = Path(rules_path)
        self._taxonomy_path = Path(taxonomy_path) if taxonomy_path else None
        self._override_registry = override_registry
        self._rules: list[StoredRule] = []
        self._taxonomy: "Taxonomy | None" = None
        self._loaded_at: str = ""
        self._version: str = ""

        if auto_load:
            self._load()

    def _load(self) -> None:
        """Load rules from disk."""
        self._load_rules()
        self._load_taxonomy()
        self._loaded_at = _now_iso()

    def _load_rules(self) -> None:
        """Load learned rules from JSON file."""
        if not self._rules_path.exists():
            self._rules = []
            return

        try:
            data = json.loads(self._rules_path.read_text(encoding="utf-8"))
            self._version = data.get("version", "")

            # Support both the LearnedRulesSnapshot format and a simpler format
            raw_rules = data.get("rules", [])
            self._rules = []

            for raw_rule in raw_rules:
                if not isinstance(raw_rule, dict):
                    continue

                # Determine pattern type from the pattern itself
                pattern = raw_rule.get("pattern", "")
                pattern_type = raw_rule.get("pattern_type", "")

                if not pattern_type:
                    # Infer pattern type
                    if "*" in pattern or "?" in pattern:
                        pattern_type = "glob"
                    elif pattern.startswith("^") or pattern.endswith("$"):
                        pattern_type = "regex"
                    else:
                        pattern_type = "keyword"

                self._rules.append(StoredRule(
                    pattern=pattern,
                    destination=raw_rule.get("destination", ""),
                    confidence=raw_rule.get("confidence", 0.8),
                    pattern_type=pattern_type,
                    source_folder=raw_rule.get("source_folder", ""),
                    reasoning=raw_rule.get("reasoning", ""),
                    enabled=raw_rule.get("enabled", True),
                    hit_count=raw_rule.get("hit_count", 0),
                    created_at=raw_rule.get("created_at", raw_rule.get("generated_at", "")),
                ))

        except (json.JSONDecodeError, OSError):
            self._rules = []

    def _load_taxonomy(self) -> None:
        """Load taxonomy from JSON file."""
        if not self._taxonomy_path or not self._taxonomy_path.exists():
            self._taxonomy = None
            return

        try:
            # Import here to avoid circular imports
            from organizer.taxonomy_utils import load_taxonomy
            self._taxonomy = load_taxonomy(self._taxonomy_path)
        except (json.JSONDecodeError, OSError, ImportError):
            self._taxonomy = None

    def _save(self) -> None:
        """Save rules to disk."""
        self._rules_path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "version": self._version or "1.0",
            "rules": [r.to_dict() for r in self._rules],
            "updated_at": _now_iso(),
        }

        self._rules_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def reload(self) -> None:
        """Reload rules from disk."""
        self._load()

    def match(
        self,
        filename: str,
        content_signals: dict[str, Any] | None = None,
    ) -> tuple[str, float]:
        """Match a filename against all rules with priority ordering.

        Priority order:
        1. Learned rules (from structure analysis)
        2. User overrides (from corrections)
        3. Built-in taxonomy rules
        4. Hardcoded ROUTING_RULES

        Args:
            filename: The filename to match.
            content_signals: Optional content-based signals (keywords, dates, etc.).

        Returns:
            Tuple of (destination, confidence). Returns ("", 0.0) if no match.
        """
        # 1. Check learned rules first (highest priority)
        learned_match = self._match_learned_rules(filename, content_signals)
        if learned_match:
            return learned_match.destination, learned_match.confidence

        # 2. Check user overrides
        override_match = self._match_overrides(filename)
        if override_match:
            return override_match.destination, override_match.confidence

        # 3. Check taxonomy rules
        taxonomy_match = self._match_taxonomy(filename, content_signals)
        if taxonomy_match:
            return taxonomy_match.destination, taxonomy_match.confidence

        # 4. Fall back to hardcoded ROUTING_RULES (handled by caller)
        return "", 0.0

    def match_with_details(
        self,
        filename: str,
        content_signals: dict[str, Any] | None = None,
    ) -> MatchResult | None:
        """Match a filename and return detailed match information.

        Args:
            filename: The filename to match.
            content_signals: Optional content-based signals.

        Returns:
            MatchResult with full details, or None if no match.
        """
        # 1. Check learned rules first
        learned_match = self._match_learned_rules(filename, content_signals)
        if learned_match:
            return learned_match

        # 2. Check user overrides
        override_match = self._match_overrides(filename)
        if override_match:
            return override_match

        # 3. Check taxonomy rules
        taxonomy_match = self._match_taxonomy(filename, content_signals)
        if taxonomy_match:
            return taxonomy_match

        return None

    def _match_learned_rules(
        self,
        filename: str,
        content_signals: dict[str, Any] | None = None,
    ) -> MatchResult | None:
        """Match against learned rules.

        Args:
            filename: The filename to match.
            content_signals: Optional content-based signals.

        Returns:
            MatchResult if matched, None otherwise.
        """
        for rule in self._rules:
            if rule.matches(filename, content_signals):
                # Update hit count
                rule.hit_count += 1
                self._save()

                return MatchResult(
                    destination=rule.destination,
                    confidence=rule.confidence,
                    rule_pattern=rule.pattern,
                    rule_source="learned",
                    reasoning=rule.reasoning,
                )

        return None

    def _match_overrides(self, filename: str) -> MatchResult | None:
        """Match against user overrides.

        Args:
            filename: The filename to match.

        Returns:
            MatchResult if matched, None otherwise.
        """
        if self._override_registry is None:
            return None

        override = self._override_registry.find_match(filename)
        if override:
            return MatchResult(
                destination=override.correct_bin,
                confidence=0.95,  # User overrides have high confidence
                rule_pattern=override.pattern,
                rule_source="override",
                reasoning=f"User override from {override.source}",
            )

        return None

    def _match_taxonomy(
        self,
        filename: str,
        content_signals: dict[str, Any] | None = None,
    ) -> MatchResult | None:
        """Match against taxonomy rules.

        Args:
            filename: The filename to match.
            content_signals: Optional content-based signals.

        Returns:
            MatchResult if matched, None otherwise.
        """
        if self._taxonomy is None:
            return None

        filename_lower = filename.lower()
        stem = Path(filename).stem.lower()

        # Check taxonomy rules mapping
        for rule_pattern, destination in self._taxonomy.rules.items():
            pattern_lower = rule_pattern.lower()
            if pattern_lower in filename_lower or pattern_lower in stem:
                return MatchResult(
                    destination=destination,
                    confidence=0.85,
                    rule_pattern=rule_pattern,
                    rule_source="taxonomy",
                    reasoning=f"Taxonomy rule match: {rule_pattern}",
                )

        return None

    def add_rule(self, rule: StoredRule) -> None:
        """Add or update a rule.

        If a rule with the same pattern exists, it is replaced.

        Args:
            rule: The rule to add.
        """
        # Remove existing rule with same pattern
        self._rules = [r for r in self._rules if r.pattern != rule.pattern]
        self._rules.append(rule)
        self._save()

    def remove_rule(self, pattern: str) -> bool:
        """Remove a rule by pattern.

        Args:
            pattern: The pattern to remove.

        Returns:
            True if a rule was removed, False otherwise.
        """
        before_count = len(self._rules)
        self._rules = [r for r in self._rules if r.pattern != pattern]

        if len(self._rules) < before_count:
            self._save()
            return True
        return False

    def enable_rule(self, pattern: str) -> bool:
        """Enable a rule by pattern.

        Args:
            pattern: The pattern to enable.

        Returns:
            True if a rule was enabled, False otherwise.
        """
        for rule in self._rules:
            if rule.pattern == pattern:
                rule.enabled = True
                self._save()
                return True
        return False

    def disable_rule(self, pattern: str) -> bool:
        """Disable a rule by pattern.

        Args:
            pattern: The pattern to disable.

        Returns:
            True if a rule was disabled, False otherwise.
        """
        for rule in self._rules:
            if rule.pattern == pattern:
                rule.enabled = False
                self._save()
                return True
        return False

    def get_all_rules(self) -> list[StoredRule]:
        """Get all stored rules.

        Returns:
            List of all StoredRule objects.
        """
        return list(self._rules)

    def get_enabled_rules(self) -> list[StoredRule]:
        """Get all enabled rules.

        Returns:
            List of enabled StoredRule objects.
        """
        return [r for r in self._rules if r.enabled]

    def get_rules_for_destination(self, destination: str) -> list[StoredRule]:
        """Get all rules targeting a specific destination.

        Args:
            destination: The destination path to filter by.

        Returns:
            List of rules with matching destination.
        """
        return [r for r in self._rules if r.destination == destination]

    def get_rule_count(self) -> int:
        """Get the total number of rules.

        Returns:
            Number of rules in the store.
        """
        return len(self._rules)

    def get_enabled_rule_count(self) -> int:
        """Get the number of enabled rules.

        Returns:
            Number of enabled rules.
        """
        return len([r for r in self._rules if r.enabled])

    def clear(self) -> None:
        """Clear all rules from the store."""
        self._rules = []
        self._save()

    @property
    def is_loaded(self) -> bool:
        """Check if rules have been loaded.

        Returns:
            True if rules have been loaded.
        """
        return bool(self._loaded_at)

    @property
    def loaded_at(self) -> str:
        """Get the timestamp when rules were loaded.

        Returns:
            ISO timestamp string.
        """
        return self._loaded_at

    @property
    def rules_path(self) -> Path:
        """Get the path to the rules file.

        Returns:
            Path to the rules JSON file.
        """
        return self._rules_path

    @property
    def has_taxonomy(self) -> bool:
        """Check if taxonomy is loaded.

        Returns:
            True if taxonomy is loaded.
        """
        return self._taxonomy is not None


def create_rule_store(
    rules_path: str | Path = DEFAULT_RULES_PATH,
    taxonomy_path: str | Path | None = DEFAULT_TAXONOMY_PATH,
    with_overrides: bool = True,
) -> LearnedRuleStore:
    """Convenience function to create a LearnedRuleStore.

    Args:
        rules_path: Path to learned rules JSON file.
        taxonomy_path: Path to taxonomy JSON file.
        with_overrides: Whether to include the OverrideRegistry.

    Returns:
        Configured LearnedRuleStore instance.
    """
    override_registry = None
    if with_overrides:
        try:
            from organizer.learned_overrides import OverrideRegistry
            override_registry = OverrideRegistry()
        except ImportError:
            pass

    return LearnedRuleStore(
        rules_path=rules_path,
        taxonomy_path=taxonomy_path,
        override_registry=override_registry,
    )


def match_file(
    filename: str,
    content_signals: dict[str, Any] | None = None,
    rules_path: str | Path = DEFAULT_RULES_PATH,
) -> tuple[str, float]:
    """Convenience function to match a file against learned rules.

    Args:
        filename: The filename to match.
        content_signals: Optional content-based signals.
        rules_path: Path to the rules file.

    Returns:
        Tuple of (destination, confidence).
    """
    store = LearnedRuleStore(rules_path=rules_path, auto_load=True)
    return store.match(filename, content_signals)
