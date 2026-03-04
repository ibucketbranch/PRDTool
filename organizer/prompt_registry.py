"""Prompt management system for LLM operations.

Provides a registry for loading, managing, and substituting variables in prompts.
Prompts are stored as editable .txt files in the `.organizer/prompts/` directory.

Example usage:
    registry = PromptRegistry()
    prompt = registry.get("classify_file", filename="invoice.pdf", content="...")
    response = llm_client.generate(prompt)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_PROMPTS_DIR = ".organizer/prompts"


# Default prompt templates that are created on first run
DEFAULT_PROMPTS: dict[str, str] = {
    "classify_file": """# Prompt: classify_file
# Version: 1.0.0
# Last-Modified: {date}
# Description: Classify a file into a category based on filename and content preview.

Given the filename and content preview below, classify this file into one of the available bins.

Filename: {filename}
Content Preview: {content}

Available Bins:
{bins}

Reply with JSON:
{{
    "bin": "selected_bin_name",
    "subcategory": "optional_subcategory",
    "confidence": 0.0 to 1.0,
    "reason": "brief explanation"
}}""",
    "validate_placement": """# Prompt: validate_placement
# Version: 1.0.0
# Last-Modified: {date}
# Description: Validate if a file belongs in its current location.

File '{filename}' is in '{current_path}'.
Based on its name and content preview, does it belong in '{current_bin}' or should it be in '{expected_bin}'?

Content Preview: {content}

Reply with JSON:
{{
    "belongs_here": true/false,
    "correct_bin": "bin_name",
    "confidence": 0.0 to 1.0,
    "reason": "brief explanation"
}}""",
    "suggest_subfolder": """# Prompt: suggest_subfolder
# Version: 1.0.0
# Last-Modified: {date}
# Description: Suggest subfolder structure for a file within a target bin.

What subfolder structure should '{filename}' have inside '{target_bin}'?
Preserve year/agency hierarchy where appropriate.

Content Preview: {content}

Reply with JSON:
{{
    "suggested_subpath": "subfolder/path",
    "reason": "brief explanation"
}}""",
    "detect_domain": """# Prompt: detect_domain
# Version: 1.0.0
# Last-Modified: {date}
# Description: Detect the domain context from folder structure.

Given this folder structure (top levels with file counts and sample filenames):
{structure_json}

What domain is this?
Options: personal, medical, legal, automotive, creative, engineering, generic_business

Reply with JSON:
{{
    "domain": "detected_domain",
    "confidence": 0.0 to 1.0,
    "evidence": ["signal 1", "signal 2", ...]
}}""",
    "generate_rule": """# Prompt: generate_rule
# Version: 1.0.0
# Last-Modified: {date}
# Description: Generate a routing rule for a folder based on its contents.

Folder '{folder_name}' contains these files: {filename_list}

What routing rule describes what belongs here?

Reply with JSON:
{{
    "pattern": "matching pattern",
    "destination": "folder path",
    "confidence": 0.0 to 1.0,
    "reasoning": "brief explanation"
}}""",
    "assess_drift": """# Prompt: assess_drift
# Version: 1.0.0
# Last-Modified: {date}
# Description: Assess whether a file movement was intentional or accidental.

File '{filename}' was filed at '{original_path}' on {filed_date}.
It is now at '{current_path}'.

Was this move intentional (user reorganized) or accidental (drag-drop)?

Reply with JSON:
{{
    "likely_intentional": true/false,
    "confidence": 0.0 to 1.0,
    "reason": "brief explanation"
}}""",
    "extract_metadata": """# Prompt: extract_metadata
# Version: 1.0.0
# Last-Modified: {date}
# Description: Extract structured metadata from file content.

Extract structured tags from file '{filename}', content:
{content}

Reply with JSON:
{{
    "document_type": "type of document",
    "year": "YYYY or null",
    "organizations": ["org1", "org2"],
    "people": ["name1", "name2"],
    "topics": ["topic1", "topic2"],
    "suggested_tags": ["tag1", "tag2"]
}}""",
    "narrate_structure": """# Prompt: narrate_structure
# Version: 1.0.0
# Last-Modified: {date}
# Description: Generate a plain-English summary of organizational strategy.

Summarize this organizational strategy in 2-3 sentences for a non-technical user:
{structure_json}""",
}


@dataclass
class PromptMetadata:
    """Metadata extracted from a prompt file header.

    Attributes:
        name: The prompt name (from header or filename).
        version: The prompt version (e.g., "1.0.0").
        last_modified: When the prompt was last modified.
        description: Brief description of what the prompt does.
    """

    name: str
    version: str
    last_modified: str
    description: str


@dataclass
class LoadedPrompt:
    """A loaded prompt with its metadata and template.

    Attributes:
        metadata: Metadata about the prompt.
        template: The prompt template text (with variable placeholders).
        source_path: Path to the source file (or None if from defaults).
    """

    metadata: PromptMetadata
    template: str
    source_path: Path | None


class PromptRegistry:
    """Registry for loading and managing LLM prompts.

    Prompts are stored as .txt files in the prompts directory with a header
    containing version and metadata. Variables are substituted using {name}
    placeholders.

    Example:
        registry = PromptRegistry()
        prompt = registry.get("classify_file", filename="doc.pdf", bins="Tax, Medical")
    """

    def __init__(self, prompts_dir: str | Path | None = None):
        """Initialize the prompt registry.

        Args:
            prompts_dir: Directory containing prompt files. If None, uses
                the default `.organizer/prompts` directory.
        """
        if prompts_dir is None:
            self._prompts_dir = Path(DEFAULT_PROMPTS_DIR)
        else:
            self._prompts_dir = Path(prompts_dir)

        self._cache: dict[str, LoadedPrompt] = {}
        self._ensure_defaults()

    def _ensure_defaults(self) -> None:
        """Ensure default prompts exist if directory is missing or empty."""
        if not self._prompts_dir.exists():
            self._prompts_dir.mkdir(parents=True, exist_ok=True)
            self._create_default_prompts()
        elif not any(self._prompts_dir.glob("*.txt")):
            self._create_default_prompts()

    def _create_default_prompts(self) -> None:
        """Create default prompt files from templates."""
        today = datetime.now().strftime("%Y-%m-%d")

        for name, template in DEFAULT_PROMPTS.items():
            filepath = self._prompts_dir / f"{name}.txt"
            if not filepath.exists():
                content = template.replace("{date}", today)
                filepath.write_text(content)

    def _parse_header(self, content: str) -> PromptMetadata:
        """Parse prompt metadata from file header comments.

        Args:
            content: The full prompt file content.

        Returns:
            PromptMetadata with extracted values.
        """
        name = ""
        version = "1.0.0"
        last_modified = ""
        description = ""

        # Parse header lines
        for line in content.split("\n"):
            line = line.strip()
            if not line.startswith("#"):
                break

            # Remove leading # and whitespace
            line = line.lstrip("#").strip()

            if line.startswith("Prompt:"):
                name = line.split(":", 1)[1].strip()
            elif line.startswith("Version:"):
                version = line.split(":", 1)[1].strip()
            elif line.startswith("Last-Modified:"):
                last_modified = line.split(":", 1)[1].strip()
            elif line.startswith("Description:"):
                description = line.split(":", 1)[1].strip()

        return PromptMetadata(
            name=name,
            version=version,
            last_modified=last_modified,
            description=description,
        )

    def _extract_template(self, content: str) -> str:
        """Extract the template portion (non-header) from prompt content.

        Args:
            content: The full prompt file content.

        Returns:
            The template text without header comments.
        """
        lines = content.split("\n")
        template_lines = []
        in_header = True

        for line in lines:
            if in_header and line.strip().startswith("#"):
                continue
            in_header = False
            template_lines.append(line)

        return "\n".join(template_lines).strip()

    def _load_prompt(self, name: str) -> LoadedPrompt:
        """Load a prompt from file.

        Args:
            name: The prompt name (without .txt extension).

        Returns:
            LoadedPrompt with metadata and template.

        Raises:
            FileNotFoundError: If prompt file doesn't exist and no default.
        """
        filepath = self._prompts_dir / f"{name}.txt"

        if filepath.exists():
            content = filepath.read_text()
            metadata = self._parse_header(content)
            template = self._extract_template(content)

            # Fill in name from filename if not in header
            if not metadata.name:
                metadata.name = name

            return LoadedPrompt(
                metadata=metadata,
                template=template,
                source_path=filepath,
            )

        # Check if we have a default
        if name in DEFAULT_PROMPTS:
            today = datetime.now().strftime("%Y-%m-%d")
            content = DEFAULT_PROMPTS[name].replace("{date}", today)
            metadata = self._parse_header(content)
            template = self._extract_template(content)

            if not metadata.name:
                metadata.name = name

            return LoadedPrompt(
                metadata=metadata,
                template=template,
                source_path=None,
            )

        raise FileNotFoundError(f"Prompt '{name}' not found at {filepath}")

    def get(self, prompt_name: str, **variables: Any) -> str:
        """Get a prompt with variables substituted.

        Args:
            prompt_name: The prompt name.
            **variables: Variables to substitute in the template.
                Use {variable_name} placeholders in prompts.

        Returns:
            The prompt text with variables substituted.

        Raises:
            FileNotFoundError: If prompt doesn't exist.
            KeyError: If a required variable is missing.
        """
        if prompt_name not in self._cache:
            self._cache[prompt_name] = self._load_prompt(prompt_name)

        prompt = self._cache[prompt_name]
        template = prompt.template

        # Substitute variables
        # Use a custom formatter to handle missing keys gracefully
        # while still raising errors for completely unknown placeholders
        try:
            # Find all placeholders
            placeholders = re.findall(r"\{(\w+)\}", template)
            missing = [p for p in placeholders if p not in variables]

            if missing:
                raise KeyError(f"Missing required variables: {missing}")

            return template.format(**variables)
        except KeyError as e:
            raise KeyError(f"Variable substitution error in prompt '{prompt_name}': {e}")

    def get_raw(self, name: str) -> str:
        """Get the raw prompt template without variable substitution.

        Args:
            name: The prompt name.

        Returns:
            The raw prompt template text.

        Raises:
            FileNotFoundError: If prompt doesn't exist.
        """
        if name not in self._cache:
            self._cache[name] = self._load_prompt(name)

        return self._cache[name].template

    def get_metadata(self, name: str) -> PromptMetadata:
        """Get metadata for a prompt.

        Args:
            name: The prompt name.

        Returns:
            PromptMetadata with version and description.

        Raises:
            FileNotFoundError: If prompt doesn't exist.
        """
        if name not in self._cache:
            self._cache[name] = self._load_prompt(name)

        return self._cache[name].metadata

    def list_prompts(self) -> list[str]:
        """List all available prompt names.

        Returns:
            List of prompt names (without .txt extension).
        """
        names: set[str] = set()

        # Add prompts from files
        if self._prompts_dir.exists():
            for filepath in self._prompts_dir.glob("*.txt"):
                names.add(filepath.stem)

        # Add default prompts
        names.update(DEFAULT_PROMPTS.keys())

        return sorted(names)

    def reload(self, name: str | None = None) -> None:
        """Reload prompt(s) from disk, clearing the cache.

        Args:
            name: Specific prompt to reload, or None to reload all.
        """
        if name is None:
            self._cache.clear()
        elif name in self._cache:
            del self._cache[name]

    def has_prompt(self, name: str) -> bool:
        """Check if a prompt exists.

        Args:
            name: The prompt name.

        Returns:
            True if prompt exists (in files or defaults).
        """
        filepath = self._prompts_dir / f"{name}.txt"
        return filepath.exists() or name in DEFAULT_PROMPTS

    def get_variables(self, name: str) -> list[str]:
        """Get the list of variables in a prompt template.

        Args:
            name: The prompt name.

        Returns:
            List of variable names found in the template.

        Raises:
            FileNotFoundError: If prompt doesn't exist.
        """
        template = self.get_raw(name)
        return re.findall(r"\{(\w+)\}", template)

    @property
    def prompts_dir(self) -> Path:
        """Get the prompts directory path."""
        return self._prompts_dir


# Convenience functions for module-level usage


def get_prompt(name: str, **variables: Any) -> str:
    """Get a prompt with variables substituted using the default registry.

    Args:
        name: The prompt name.
        **variables: Variables to substitute in the template.

    Returns:
        The prompt text with variables substituted.
    """
    registry = PromptRegistry()
    return registry.get(name, **variables)


def list_available_prompts() -> list[str]:
    """List all available prompt names.

    Returns:
        List of prompt names.
    """
    registry = PromptRegistry()
    return registry.list_prompts()
