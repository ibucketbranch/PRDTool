"""Rule Generator module for LLM-powered routing rule generation.

Uses T2 Smart LLM to analyze folders and generate routing rules that describe
what files belong in each folder. Falls back to pattern-based rule generation
when LLM is unavailable.

This module is part of the Learning-Agent (Phase 15) and generates rules
that can be used by the routing pipeline.

Example usage:
    generator = RuleGenerator(llm_client, model_router)
    rules = generator.generate_rules(structure_snapshot)
    rules.save()  # Saves to .organizer/agent/learned_routing_rules.json
"""

from __future__ import annotations

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
    from organizer.structure_analyzer import FolderNode, StructureSnapshot


# Default output path
DEFAULT_RULES_OUTPUT_PATH = ".organizer/agent/learned_routing_rules.json"


def _now_iso() -> str:
    """Get current timestamp in ISO format."""
    return datetime.now().isoformat()


@dataclass
class RoutingRule:
    """A learned routing rule describing what files belong in a folder.

    Attributes:
        pattern: Filename pattern or keyword that triggers this rule.
        destination: Target folder path for matching files.
        confidence: Confidence score from 0.0 to 1.0.
        reasoning: Explanation of why this rule was generated.
        source_folder: The folder this rule was learned from.
        model_used: LLM model that generated this rule (empty if pattern-based).
        generated_at: ISO timestamp when rule was generated.
        enabled: Whether this rule is active (can be toggled by user).
    """

    pattern: str
    destination: str
    confidence: float
    reasoning: str = ""
    source_folder: str = ""
    model_used: str = ""
    generated_at: str = ""
    enabled: bool = True

    def __post_init__(self) -> None:
        """Set default timestamp if not provided."""
        if not self.generated_at:
            self.generated_at = _now_iso()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "pattern": self.pattern,
            "destination": self.destination,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "source_folder": self.source_folder,
            "model_used": self.model_used,
            "generated_at": self.generated_at,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RoutingRule":
        """Create RoutingRule from dictionary."""
        return cls(
            pattern=data.get("pattern", ""),
            destination=data.get("destination", ""),
            confidence=data.get("confidence", 0.0),
            reasoning=data.get("reasoning", ""),
            source_folder=data.get("source_folder", ""),
            model_used=data.get("model_used", ""),
            generated_at=data.get("generated_at", ""),
            enabled=data.get("enabled", True),
        )

    @property
    def used_llm(self) -> bool:
        """Check if LLM was used (vs pattern-based fallback)."""
        return bool(self.model_used) and self.model_used != "pattern_fallback"


@dataclass
class LearnedRulesSnapshot:
    """Collection of learned routing rules from structure analysis.

    Attributes:
        root_path: Root path that was analyzed.
        rules: List of generated routing rules.
        total_folders_analyzed: Number of folders that contributed rules.
        model_used: Primary model used for generation.
        generated_at: ISO timestamp when rules were generated.
    """

    root_path: str
    rules: list[RoutingRule] = field(default_factory=list)
    total_folders_analyzed: int = 0
    model_used: str = ""
    generated_at: str = ""

    def __post_init__(self) -> None:
        """Set default timestamp if not provided."""
        if not self.generated_at:
            self.generated_at = _now_iso()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "version": "1.0",
            "root_path": self.root_path,
            "rules": [r.to_dict() for r in self.rules],
            "total_folders_analyzed": self.total_folders_analyzed,
            "model_used": self.model_used,
            "generated_at": self.generated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LearnedRulesSnapshot":
        """Create LearnedRulesSnapshot from dictionary."""
        rules = [RoutingRule.from_dict(r) for r in data.get("rules", [])]
        return cls(
            root_path=data.get("root_path", ""),
            rules=rules,
            total_folders_analyzed=data.get("total_folders_analyzed", 0),
            model_used=data.get("model_used", ""),
            generated_at=data.get("generated_at", ""),
        )

    def save(self, path: str | Path = DEFAULT_RULES_OUTPUT_PATH) -> None:
        """Save rules to JSON file.

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
    def load(cls, path: str | Path = DEFAULT_RULES_OUTPUT_PATH) -> "LearnedRulesSnapshot":
        """Load rules from JSON file.

        Args:
            path: Input file path.

        Returns:
            LearnedRulesSnapshot loaded from file.

        Raises:
            FileNotFoundError: If file doesn't exist.
            json.JSONDecodeError: If file is invalid JSON.
        """
        file_path = Path(path)
        data = json.loads(file_path.read_text(encoding="utf-8"))
        return cls.from_dict(data)

    def get_enabled_rules(self) -> list[RoutingRule]:
        """Get all enabled rules.

        Returns:
            List of rules where enabled=True.
        """
        return [r for r in self.rules if r.enabled]

    def get_rules_for_destination(self, destination: str) -> list[RoutingRule]:
        """Get all rules targeting a specific destination.

        Args:
            destination: Folder path to filter by.

        Returns:
            List of rules with matching destination.
        """
        return [r for r in self.rules if r.destination == destination]


class RuleGenerator:
    """Generates routing rules from folder structure analysis.

    Uses T2 Smart LLM to analyze folder contents and generate rules that
    describe what files belong in each folder. Falls back to pattern-based
    rule generation when LLM is unavailable.

    Example:
        generator = RuleGenerator(llm_client, model_router)
        rules = generator.generate_rules(snapshot)
        rules.save()
    """

    def __init__(
        self,
        llm_client: "LLMClient | None" = None,
        model_router: "ModelRouter | None" = None,
        prompt_registry: "PromptRegistry | None" = None,
        min_files_for_rule: int = 2,
    ):
        """Initialize the rule generator.

        Args:
            llm_client: LLM client for rule generation.
            model_router: Model router for tier selection.
            prompt_registry: Prompt registry for loading prompts.
            min_files_for_rule: Minimum files in folder to generate a rule.
        """
        self._llm_client = llm_client
        self._model_router = model_router
        self._prompt_registry = prompt_registry
        self._min_files_for_rule = min_files_for_rule

    def generate_rules(
        self,
        snapshot: "StructureSnapshot",
        use_llm: bool = True,
        max_rules_per_folder: int = 3,
    ) -> LearnedRulesSnapshot:
        """Generate routing rules from a structure snapshot.

        Analyzes each folder with sufficient files and generates rules
        describing what files belong there.

        Args:
            snapshot: The analyzed folder structure.
            use_llm: Whether to attempt LLM rule generation.
            max_rules_per_folder: Maximum rules to generate per folder.

        Returns:
            LearnedRulesSnapshot containing generated rules.
        """
        rules: list[RoutingRule] = []
        folders_analyzed = 0
        model_used = ""

        # Filter folders that have enough files to learn from
        eligible_folders = [
            f for f in snapshot.folders
            if f.file_count >= self._min_files_for_rule
        ]

        for folder in eligible_folders:
            # Try LLM generation first if enabled and available
            folder_rules = []
            if use_llm and self._llm_client is not None:
                try:
                    if self._llm_client.is_ollama_available(timeout_s=5):
                        folder_rules = self._generate_rules_with_llm(
                            folder,
                            max_rules_per_folder,
                        )
                        if folder_rules and not model_used:
                            model_used = folder_rules[0].model_used
                except Exception:
                    pass  # Fall through to pattern-based

            # Fall back to pattern-based if no LLM rules generated
            if not folder_rules:
                folder_rules = self._generate_rules_from_patterns(
                    folder,
                    max_rules_per_folder,
                )

            if folder_rules:
                rules.extend(folder_rules)
                folders_analyzed += 1

        return LearnedRulesSnapshot(
            root_path=snapshot.root_path,
            rules=rules,
            total_folders_analyzed=folders_analyzed,
            model_used=model_used or "pattern_fallback",
        )

    def _generate_rules_with_llm(
        self,
        folder: "FolderNode",
        max_rules: int,
    ) -> list[RoutingRule]:
        """Generate rules for a folder using T2 Smart LLM.

        Args:
            folder: The folder to analyze.
            max_rules: Maximum number of rules to generate.

        Returns:
            List of generated RoutingRule objects.
        """
        # Build filename list for prompt
        filenames = folder.sample_filenames[:10]  # Limit context size
        filename_list = ", ".join(f"'{f}'" for f in filenames)
        if not filename_list:
            filename_list = "(no sample files available)"

        # Add file type info
        type_info = ""
        if folder.file_types:
            top_types = sorted(
                folder.file_types.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:5]
            type_info = f"\nFile types: {', '.join(f'{ext} ({cnt})' for ext, cnt in top_types)}"

        # Build prompt (try registry first, fall back to default)
        prompt = None
        if self._prompt_registry is not None:
            try:
                prompt = self._prompt_registry.get(
                    "rule_generation",
                    folder_name=folder.name,
                    filename_list=filename_list,
                    type_info=type_info,
                    max_rules=max_rules,
                )
            except (KeyError, FileNotFoundError):
                pass

        if prompt is None:
            prompt = f"""Folder '{folder.name}' contains these files: {filename_list}{type_info}

What routing rule(s) describe what belongs here? Generate 1-{max_rules} rules.

Reply with valid JSON only: {{"rules": [{{"pattern": "<keyword or pattern>", "confidence": <0.0-1.0>, "reasoning": "<why this rule>"}}]}}

Rules should be:
- Pattern: A keyword, file extension, or naming pattern that identifies files for this folder
- Confidence: How reliably this pattern identifies files (0.8+ for strong patterns)
- Reasoning: Brief explanation of why files matching this pattern belong here

Example patterns: "invoice", "*.pdf", "tax_*", "2024_*", "medical", "contract"
"""

        # Select model (T2 Smart for complex reasoning)
        model = "qwen2.5-coder:14b"  # Default T2 Smart
        if self._model_router is not None:
            try:
                profile = TaskProfile(task_type="generate", complexity="medium")
                decision = self._model_router.route(profile)
                model = decision.model
            except RuntimeError:
                pass  # Use default model

        # Generate response
        assert self._llm_client is not None
        response = self._llm_client.generate(prompt, model=model, temperature=0.2)

        if not response.success:
            return []

        # Parse JSON response
        return self._parse_llm_response(
            response.text,
            response.model_used,
            folder,
            max_rules,
        )

    def _parse_llm_response(
        self,
        response_text: str,
        model_used: str,
        folder: "FolderNode",
        max_rules: int,
    ) -> list[RoutingRule]:
        """Parse LLM response and extract routing rules.

        Args:
            response_text: Raw response from LLM.
            model_used: Model that generated the response.
            folder: Source folder for rules.
            max_rules: Maximum rules to extract.

        Returns:
            List of RoutingRule objects.
        """
        # Try to extract JSON from response
        text = response_text.strip()

        # Remove markdown code blocks if present
        if text.startswith("```"):
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
        json_match = re.search(r"\{[^{}]*\"rules\"[^{}]*\[.*?\]\s*\}", text, re.DOTALL)
        if json_match:
            text = json_match.group()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return []

        # Extract rules
        raw_rules = data.get("rules", [])
        if not isinstance(raw_rules, list):
            return []

        rules: list[RoutingRule] = []
        for raw_rule in raw_rules[:max_rules]:
            if not isinstance(raw_rule, dict):
                continue

            pattern = raw_rule.get("pattern", "")
            if not pattern:
                continue

            confidence = raw_rule.get("confidence", 0.5)
            if not isinstance(confidence, (int, float)):
                confidence = 0.5
            confidence = max(0.0, min(1.0, float(confidence)))

            reasoning = str(raw_rule.get("reasoning", ""))

            rules.append(RoutingRule(
                pattern=str(pattern),
                destination=folder.path,
                confidence=confidence,
                reasoning=reasoning,
                source_folder=folder.path,
                model_used=model_used,
            ))

        return rules

    def _generate_rules_from_patterns(
        self,
        folder: "FolderNode",
        max_rules: int,
    ) -> list[RoutingRule]:
        """Generate rules using pattern detection when LLM unavailable.

        Args:
            folder: The folder to analyze.
            max_rules: Maximum number of rules to generate.

        Returns:
            List of generated RoutingRule objects.
        """
        rules: list[RoutingRule] = []

        # Rule 1: File extension patterns
        if folder.file_types:
            dominant_ext = max(folder.file_types.items(), key=lambda x: x[1])
            ext, count = dominant_ext
            if count >= 2:
                total_files = sum(folder.file_types.values())
                confidence = min(0.85, count / total_files + 0.3)
                rules.append(RoutingRule(
                    pattern=f"*{ext}",
                    destination=folder.path,
                    confidence=confidence,
                    reasoning=f"Folder contains {count} {ext} files ({count}/{total_files})",
                    source_folder=folder.path,
                    model_used="pattern_fallback",
                ))

        # Rule 2: Naming pattern from folder name
        folder_name = folder.name.lower().strip()
        if folder_name and len(folder_name) >= 3 and not folder_name.isdigit():
            # Clean folder name to create a keyword pattern
            keyword = re.sub(r"[^a-z0-9]+", "_", folder_name).strip("_")
            if len(keyword) >= 3:
                rules.append(RoutingRule(
                    pattern=keyword,
                    destination=folder.path,
                    confidence=0.7,
                    reasoning=f"Files containing '{keyword}' likely belong in '{folder.name}'",
                    source_folder=folder.path,
                    model_used="pattern_fallback",
                ))

        # Rule 3: Common prefix pattern from sample filenames
        if folder.sample_filenames and len(folder.sample_filenames) >= 3:
            # Find common prefix among filenames
            import os.path
            prefix = os.path.commonprefix(folder.sample_filenames)
            # Clean up to word boundary
            prefix = re.sub(r"[^a-zA-Z0-9]+$", "", prefix)
            if len(prefix) >= 3 and not prefix.isdigit():
                rules.append(RoutingRule(
                    pattern=f"{prefix}*",
                    destination=folder.path,
                    confidence=0.65,
                    reasoning=f"Files starting with '{prefix}' pattern",
                    source_folder=folder.path,
                    model_used="pattern_fallback",
                ))

        # Rule 4: Year pattern if naming patterns include YYYY_*
        if "YYYY_*" in folder.naming_patterns or "YYYY-MM-DD_*" in folder.naming_patterns:
            rules.append(RoutingRule(
                pattern="20??_*",
                destination=folder.path,
                confidence=0.7,
                reasoning="Files with year prefix pattern",
                source_folder=folder.path,
                model_used="pattern_fallback",
            ))

        return rules[:max_rules]


def generate_rules(
    snapshot: "StructureSnapshot",
    llm_client: "LLMClient | None" = None,
    model_router: "ModelRouter | None" = None,
    prompt_registry: "PromptRegistry | None" = None,
    use_llm: bool = True,
    output_path: str | Path | None = None,
) -> LearnedRulesSnapshot:
    """Convenience function to generate routing rules from structure snapshot.

    Args:
        snapshot: The analyzed folder structure.
        llm_client: Optional LLM client for rule generation.
        model_router: Optional model router for tier selection.
        prompt_registry: Optional prompt registry for loading prompts.
        use_llm: Whether to attempt LLM rule generation.
        output_path: Optional path to save generated rules.

    Returns:
        LearnedRulesSnapshot containing generated rules.
    """
    generator = RuleGenerator(
        llm_client=llm_client,
        model_router=model_router,
        prompt_registry=prompt_registry,
    )

    rules_snapshot = generator.generate_rules(snapshot, use_llm=use_llm)

    if output_path is not None:
        rules_snapshot.save(output_path)

    return rules_snapshot


def load_rules(
    path: str | Path = DEFAULT_RULES_OUTPUT_PATH,
) -> LearnedRulesSnapshot:
    """Load previously saved routing rules.

    Args:
        path: Path to the rules JSON file.

    Returns:
        LearnedRulesSnapshot loaded from file.
    """
    return LearnedRulesSnapshot.load(path)
