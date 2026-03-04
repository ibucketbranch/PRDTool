"""Smart Rules Engine for intelligent consolidation decisions.

This module provides specialized rules for identifying document contexts and
making intelligent consolidation decisions beyond simple name matching and
content analysis. It implements Phase 4 rules from the PRD:

1. MY vs OTHER people's documents - Check entity names in files
2. VA document patterns - Exclude VA documents from general consolidation
3. Code project indicators - Skip code projects entirely

These rules work alongside the content analyzer to provide additional
context-specific intelligence for consolidation decisions.
"""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from organizer.content_analyzer import (
    DatabaseConnection,
    FolderAnalysis,
    analyze_folder_content,
)


# =============================================================================
# Constants and Patterns
# =============================================================================

# VA (Veterans Affairs) document patterns
# Patterns use word boundaries that work with underscores/hyphens as separators
VA_PATTERNS = {
    "folder_names": [
        r"(?:^|[_\-\s])va(?:$|[_\-\s])",  # "VA" as a word
        r"(?:^|[_\-\s])veteran[s]?(?:$|[_\-\s])",
        r"(?:^|[_\-\s])vba(?:$|[_\-\s])",  # Veterans Benefits Administration
        r"(?:^|[_\-\s])vha(?:$|[_\-\s])",  # Veterans Health Administration
        r"disability[_\-\s]*claim[s]?",
        r"service[_\-\s]?connect",
        r"c[&]?p[_\-\s]*exam",  # C&P Exam (Compensation & Pension)
        r"(?:^|[_\-\s])dd[_\-]?214(?:$|[_\-\s])",
        r"military[_\-\s]*record[s]?",
    ],
    "categories": [
        "VA Claims",
        "Veterans Affairs",
        "Military Records",
        "Disability Claims",
        "Service Connected",
    ],
}

# Code project indicators - files/folders that indicate this is a code project
CODE_PROJECT_INDICATORS = {
    "files": [
        "package.json",
        "Cargo.toml",
        "go.mod",
        "pom.xml",
        "build.gradle",
        "setup.py",
        "pyproject.toml",
        "Makefile",
        "CMakeLists.txt",
        "requirements.txt",
        "Gemfile",
        "composer.json",
        "mix.exs",
        "stack.yaml",
        "deno.json",
        "tsconfig.json",
        "webpack.config.js",
        "vite.config.js",
        "next.config.js",
        ".gitignore",
        "Dockerfile",
        "docker-compose.yml",
        ".eslintrc.js",
        ".prettierrc",
    ],
    "folders": [
        ".git",
        ".svn",
        ".hg",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        ".env",
        "vendor",
        "target",
        "build",
        "dist",
        ".next",
        ".nuxt",
        "coverage",
        ".pytest_cache",
        ".tox",
        "src",
        "lib",
        "bin",
        "obj",
    ],
    "extensions": [
        ".py",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".java",
        ".cpp",
        ".c",
        ".h",
        ".hpp",
        ".rs",
        ".go",
        ".rb",
        ".php",
        ".swift",
        ".kt",
        ".scala",
        ".ex",
        ".exs",
        ".erl",
        ".hs",
        ".cs",
        ".fs",
    ],
}

# Common personal name patterns for MY vs OTHER document detection
# These are used to check if a person's name in entities matches the user
MY_DOCUMENT_INDICATORS = [
    # Common "my" patterns in folder/file names
    r"\bmy[_\- ]",
    r"\bpersonal[_\- ]",
    r"\bown[_\- ]",
]

OTHER_DOCUMENT_INDICATORS = [
    # Patterns suggesting documents about OTHER people
    r"\bother[s']?[_\- ]",
    r"\btheir[_\- ]",
    r"\bclient[s']?[_\- ]",
    r"\bemployee[s']?[_\- ]",
    r"\bapplicant[s']?[_\- ]",
    r"\bcandidate[s']?[_\- ]",
    r"\breceived[_\- ]",
    r"\bsubmitted[_\- ]",
    r"\bfrom[_\- ]",
]


# Path context indicators - different source folders = different contexts
# These patterns help identify the source/context of a folder
PATH_CONTEXT_PATTERNS = {
    # Microsoft-related paths (Windows, OneDrive, etc.)
    "microsoft": [
        r"microsoft",
        r"onedrive",
        r"windows",
        r"win32",
        r"office365",
        r"sharepoint",
        r"azure",
    ],
    # macOS-related paths
    "macos": [
        r"macos",
        r"mac[\s_\-]?os",
        r"apple",
        r"icloud",
        r"darwin",
    ],
    # Google-related paths
    "google": [
        r"google[\s_\-]?drive",
        r"gdrive",
        r"google[\s_\-]?docs",
    ],
    # Dropbox-related paths
    "dropbox": [
        r"dropbox",
    ],
    # Work vs Personal contexts
    "work": [
        r"\bwork\b",
        r"\boffice\b",
        r"\bjob\b",
        r"\bcompany\b",
        r"\bcorporate\b",
        r"\bbusiness\b",
    ],
    "personal": [
        r"\bpersonal\b",
        r"\bhome\b",
        r"\bprivate\b",
    ],
    # Archive/backup contexts
    "archive": [
        r"\barchive[ds]?\b",
        r"\bbackup[s]?\b",
        r"\bold\b",
        r"\blegacy\b",
    ],
}

# Desktop folder patterns that indicate different system sources
DESKTOP_CONTEXT_PATTERNS = {
    "microsoft_desktop": [
        r"microsoft.*desktop",
        r"onedrive.*desktop",
        r"windows.*desktop",
        r"desktop.*microsoft",
        r"desktop.*onedrive",
        r"desktop.*windows",
    ],
    "macos_desktop": [
        r"macos.*desktop",
        r"mac.*desktop",
        r"icloud.*desktop",
        r"apple.*desktop",
        r"desktop.*macos",
        r"desktop.*mac",
        r"desktop.*icloud",
    ],
}


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class RuleResult:
    """Result of applying a smart rule to a folder or folder group."""

    rule_name: str
    applies: bool  # Whether the rule applies to this folder/group
    action: str  # "skip", "exclude_from_consolidation", "allow", "special_handling"
    confidence: float  # 0.0 to 1.0
    reasoning: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "rule_name": self.rule_name,
            "applies": self.applies,
            "action": self.action,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "metadata": self.metadata,
        }


@dataclass
class SmartRulesResult:
    """Combined result of all smart rules applied to a folder."""

    folder_path: str
    should_skip: bool = False  # Skip entirely (e.g., code project)
    should_exclude_from_consolidation: bool = False  # Keep separate (e.g., VA docs)
    is_my_document: Optional[bool] = None  # True=MY, False=OTHER, None=unknown
    path_contexts: list[str] = field(default_factory=list)  # Detected path contexts
    rule_results: list[RuleResult] = field(default_factory=list)
    overall_reasoning: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "folder_path": self.folder_path,
            "should_skip": self.should_skip,
            "should_exclude_from_consolidation": self.should_exclude_from_consolidation,
            "is_my_document": self.is_my_document,
            "path_contexts": self.path_contexts,
            "rule_results": [r.to_dict() for r in self.rule_results],
            "overall_reasoning": self.overall_reasoning,
        }


# =============================================================================
# Code Project Detection
# =============================================================================


def is_code_project(folder_path: str) -> RuleResult:
    """Check if a folder is a code project that should be skipped.

    Code projects should not be consolidated as they have specific
    directory structures that must be preserved.

    Args:
        folder_path: Path to the folder to check.

    Returns:
        RuleResult indicating whether this is a code project.
    """
    result = RuleResult(
        rule_name="code_project_detection",
        applies=False,
        action="allow",
        confidence=0.0,
    )

    if not os.path.isdir(folder_path):
        result.reasoning.append(f"Path is not a directory: {folder_path}")
        return result

    indicators_found = []
    indicator_files_found = []
    indicator_folders_found = []
    code_files_count = 0

    try:
        entries = os.listdir(folder_path)
    except (PermissionError, OSError) as e:
        result.reasoning.append(f"Cannot access folder: {e}")
        return result

    # Check for indicator files
    for indicator_file in CODE_PROJECT_INDICATORS["files"]:
        if indicator_file in entries:
            indicators_found.append(f"file:{indicator_file}")
            indicator_files_found.append(indicator_file)

    # Check for indicator folders
    for indicator_folder in CODE_PROJECT_INDICATORS["folders"]:
        if indicator_folder in entries:
            full_path = os.path.join(folder_path, indicator_folder)
            if os.path.isdir(full_path):
                indicators_found.append(f"folder:{indicator_folder}")
                indicator_folders_found.append(indicator_folder)

    # Check file extensions in the folder
    for entry in entries:
        entry_path = os.path.join(folder_path, entry)
        if os.path.isfile(entry_path):
            ext = Path(entry).suffix.lower()
            if ext in CODE_PROJECT_INDICATORS["extensions"]:
                code_files_count += 1

    # Calculate confidence based on indicators
    # Strong indicators: .git, package.json, pyproject.toml, etc.
    strong_indicators = [
        ".git",
        "package.json",
        "pyproject.toml",
        "Cargo.toml",
        "go.mod",
    ]
    has_strong_indicator = any(
        ind.split(":")[1] in strong_indicators for ind in indicators_found
    )

    if has_strong_indicator:
        result.confidence = 1.0
    elif len(indicators_found) >= 3:
        result.confidence = 0.9
    elif len(indicators_found) >= 2:
        result.confidence = 0.8
    elif len(indicators_found) == 1 and code_files_count >= 5:
        result.confidence = 0.7
    elif code_files_count >= 10:
        result.confidence = 0.6
    elif len(indicators_found) == 1:
        result.confidence = 0.5
    else:
        result.confidence = 0.0

    # Determine if this is a code project
    if result.confidence >= 0.5:
        result.applies = True
        result.action = "skip"

        if indicator_files_found:
            result.reasoning.append(
                f"Found project files: {', '.join(indicator_files_found)}"
            )
        if indicator_folders_found:
            result.reasoning.append(
                f"Found project folders: {', '.join(indicator_folders_found)}"
            )
        if code_files_count > 0:
            result.reasoning.append(f"Found {code_files_count} code files")

        result.metadata["indicator_files"] = indicator_files_found
        result.metadata["indicator_folders"] = indicator_folders_found
        result.metadata["code_files_count"] = code_files_count
    else:
        result.reasoning.append("No significant code project indicators found")

    return result


# =============================================================================
# VA Document Detection
# =============================================================================


def is_va_document_folder(
    folder_path: str,
    folder_analysis: Optional[FolderAnalysis] = None,
    conn: Optional[DatabaseConnection] = None,
) -> RuleResult:
    """Check if a folder contains VA (Veterans Affairs) documents.

    VA documents should be excluded from general consolidation to preserve
    their organization (e.g., claims, medical records, benefits).

    Args:
        folder_path: Path to the folder to check.
        folder_analysis: Optional pre-computed folder analysis.
        conn: Optional database connection for analysis.

    Returns:
        RuleResult indicating whether this contains VA documents.
    """
    result = RuleResult(
        rule_name="va_document_detection",
        applies=False,
        action="allow",
        confidence=0.0,
    )

    folder_name = os.path.basename(folder_path).lower()
    va_indicators = []

    # Check folder name against VA patterns
    for pattern in VA_PATTERNS["folder_names"]:
        if re.search(pattern, folder_name, re.IGNORECASE):
            va_indicators.append(f"folder_name_match:{pattern}")

    # Check AI categories if we have folder analysis
    if folder_analysis is None and conn is not None:
        folder_analysis = analyze_folder_content(conn, folder_path)

    if folder_analysis:
        for category in folder_analysis.ai_categories:
            category_lower = category.lower()
            for va_category in VA_PATTERNS["categories"]:
                if va_category.lower() in category_lower:
                    va_indicators.append(f"ai_category:{category}")
                    break

        # Check for VA-related organizations in entities
        orgs = folder_analysis.entities.get(
            "organizations", set()
        ) | folder_analysis.entities.get("orgs", set())
        for org in orgs:
            org_lower = org.lower()
            if any(
                va_term in org_lower
                for va_term in ["va", "veteran", "vba", "vha", "department of veteran"]
            ):
                va_indicators.append(f"organization:{org}")

    # Calculate confidence
    if len(va_indicators) >= 3:
        result.confidence = 1.0
    elif len(va_indicators) == 2:
        result.confidence = 0.9
    elif len(va_indicators) == 1:
        result.confidence = 0.7
    else:
        result.confidence = 0.0

    # Determine if this is a VA document folder
    if result.confidence >= 0.5:
        result.applies = True
        result.action = "exclude_from_consolidation"
        result.reasoning.append("VA document patterns detected")
        for indicator in va_indicators:
            result.reasoning.append(f"  - {indicator}")
        result.metadata["va_indicators"] = va_indicators
    else:
        result.reasoning.append("No VA document patterns detected")

    return result


# =============================================================================
# MY vs OTHER Document Detection
# =============================================================================


def detect_document_ownership(
    folder_path: str,
    user_name: Optional[str] = None,
    folder_analysis: Optional[FolderAnalysis] = None,
    conn: Optional[DatabaseConnection] = None,
) -> RuleResult:
    """Detect if documents in a folder are about ME or about OTHER people.

    This helps prevent consolidating personal documents (like MY resumes)
    with documents about other people (like received resumes).

    Args:
        folder_path: Path to the folder to check.
        user_name: Optional name of the user to match against entities.
        folder_analysis: Optional pre-computed folder analysis.
        conn: Optional database connection for analysis.

    Returns:
        RuleResult with metadata indicating MY vs OTHER ownership.
    """
    result = RuleResult(
        rule_name="document_ownership_detection",
        applies=True,  # Always applies - we always try to detect ownership
        action="allow",  # Just informational
        confidence=0.0,
    )

    folder_name = os.path.basename(folder_path).lower()
    my_indicators = []
    other_indicators = []

    # Check folder name for MY patterns
    for pattern in MY_DOCUMENT_INDICATORS:
        if re.search(pattern, folder_name, re.IGNORECASE):
            my_indicators.append(f"folder_pattern:{pattern}")

    # Check folder name for OTHER patterns
    for pattern in OTHER_DOCUMENT_INDICATORS:
        if re.search(pattern, folder_name, re.IGNORECASE):
            other_indicators.append(f"folder_pattern:{pattern}")

    # Get folder analysis if needed
    if folder_analysis is None and conn is not None:
        folder_analysis = analyze_folder_content(conn, folder_path)

    # Check entities for user name match
    if folder_analysis and user_name:
        user_name_lower = user_name.lower()
        user_name_parts = user_name_lower.split()

        people = folder_analysis.entities.get(
            "people", set()
        ) | folder_analysis.entities.get("persons", set())

        user_name_found = False
        other_names_found = []

        for person in people:
            person_lower = person.lower()
            # Check if user name matches
            if user_name_lower in person_lower or all(
                part in person_lower for part in user_name_parts
            ):
                user_name_found = True
                my_indicators.append(f"entity_name_match:{person}")
            else:
                other_names_found.append(person)

        if other_names_found and not user_name_found:
            for name in other_names_found[:3]:  # Limit to first 3
                other_indicators.append(f"other_person:{name}")

    # Determine ownership
    is_my_document = None

    if my_indicators and not other_indicators:
        is_my_document = True
        result.confidence = min(0.5 + 0.2 * len(my_indicators), 1.0)
        result.reasoning.append("Detected as MY document")
        result.reasoning.extend([f"  - {ind}" for ind in my_indicators])
    elif other_indicators and not my_indicators:
        is_my_document = False
        result.confidence = min(0.5 + 0.2 * len(other_indicators), 1.0)
        result.reasoning.append("Detected as OTHER people's document")
        result.reasoning.extend([f"  - {ind}" for ind in other_indicators])
    elif my_indicators and other_indicators:
        # Mixed signals - lower confidence
        if len(my_indicators) > len(other_indicators):
            is_my_document = True
            result.confidence = 0.4
        elif len(other_indicators) > len(my_indicators):
            is_my_document = False
            result.confidence = 0.4
        else:
            result.confidence = 0.2
        result.reasoning.append("Mixed ownership signals detected")
        result.reasoning.append(f"  MY indicators: {len(my_indicators)}")
        result.reasoning.append(f"  OTHER indicators: {len(other_indicators)}")
    else:
        result.reasoning.append("Could not determine document ownership")
        result.confidence = 0.0

    result.metadata["is_my_document"] = is_my_document
    result.metadata["my_indicators"] = my_indicators
    result.metadata["other_indicators"] = other_indicators

    return result


def should_consolidate_by_ownership(
    folder1_path: str,
    folder2_path: str,
    user_name: Optional[str] = None,
    folder1_analysis: Optional[FolderAnalysis] = None,
    folder2_analysis: Optional[FolderAnalysis] = None,
    conn: Optional[DatabaseConnection] = None,
) -> RuleResult:
    """Check if two folders can be consolidated based on document ownership.

    MY documents should not be consolidated with OTHER people's documents.

    Args:
        folder1_path: Path to the first folder.
        folder2_path: Path to the second folder.
        user_name: Optional name of the user to match against entities.
        folder1_analysis: Optional pre-computed analysis for folder1.
        folder2_analysis: Optional pre-computed analysis for folder2.
        conn: Optional database connection for analysis.

    Returns:
        RuleResult indicating if consolidation should be blocked.
    """
    ownership1 = detect_document_ownership(
        folder1_path, user_name, folder1_analysis, conn
    )
    ownership2 = detect_document_ownership(
        folder2_path, user_name, folder2_analysis, conn
    )

    result = RuleResult(
        rule_name="ownership_consolidation_check",
        applies=True,
        action="allow",
        confidence=0.0,
    )

    is_my1 = ownership1.metadata.get("is_my_document")
    is_my2 = ownership2.metadata.get("is_my_document")

    # If both have known ownership and they differ, block consolidation
    if is_my1 is not None and is_my2 is not None:
        if is_my1 != is_my2:
            result.action = "exclude_from_consolidation"
            result.confidence = min(ownership1.confidence, ownership2.confidence)
            result.reasoning.append(
                "Cannot consolidate MY documents with OTHER people's documents"
            )
            folder1_name = os.path.basename(folder1_path)
            folder2_name = os.path.basename(folder2_path)
            result.reasoning.append(f"  {folder1_name}: {'MY' if is_my1 else 'OTHER'}")
            result.reasoning.append(f"  {folder2_name}: {'MY' if is_my2 else 'OTHER'}")
        else:
            result.action = "allow"
            result.confidence = min(ownership1.confidence, ownership2.confidence)
            ownership_type = "MY" if is_my1 else "OTHER"
            result.reasoning.append(f"Both folders contain {ownership_type} documents")
    else:
        # Unknown ownership for one or both - allow with low confidence
        result.action = "allow"
        result.confidence = 0.3
        result.reasoning.append("Could not determine ownership for comparison")

    result.metadata["folder1_ownership"] = ownership1.metadata
    result.metadata["folder2_ownership"] = ownership2.metadata

    return result


# =============================================================================
# Path Context Detection
# =============================================================================


def detect_path_context(
    folder_path: str,
    folder_analysis: Optional[FolderAnalysis] = None,
    conn: Optional[DatabaseConnection] = None,
) -> RuleResult:
    """Detect the path context of a folder (Microsoft, macOS, etc.).

    This helps prevent consolidating folders from different source systems,
    like Microsoft Desktop vs macOS Desktop.

    Args:
        folder_path: Path to the folder to check.
        folder_analysis: Optional pre-computed folder analysis.
        conn: Optional database connection for analysis.

    Returns:
        RuleResult with metadata indicating detected path contexts.
    """
    result = RuleResult(
        rule_name="path_context_detection",
        applies=True,  # Always applies - we always try to detect context
        action="allow",  # Just informational
        confidence=0.0,
    )

    # Normalize the full path for pattern matching
    full_path_lower = folder_path.lower().replace("\\", "/")

    detected_contexts: set[str] = set()
    context_indicators: list[str] = []

    # Check for desktop-specific contexts first (most specific)
    for context_name, patterns in DESKTOP_CONTEXT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, full_path_lower, re.IGNORECASE):
                detected_contexts.add(context_name)
                context_indicators.append(f"desktop_pattern:{context_name}:{pattern}")
                break

    # Check for general path context patterns
    for context_name, patterns in PATH_CONTEXT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, full_path_lower, re.IGNORECASE):
                detected_contexts.add(context_name)
                context_indicators.append(f"path_pattern:{context_name}:{pattern}")
                break

    # Check original paths from database if available
    if folder_analysis is None and conn is not None:
        folder_analysis = analyze_folder_content(conn, folder_path)

    if folder_analysis:
        for original_path in folder_analysis.original_paths:
            original_lower = original_path.lower().replace("\\", "/")
            # Check desktop patterns in original paths
            for context_name, patterns in DESKTOP_CONTEXT_PATTERNS.items():
                for pattern in patterns:
                    if re.search(pattern, original_lower, re.IGNORECASE):
                        detected_contexts.add(context_name)
                        context_indicators.append(
                            f"original_path:{context_name}:{pattern}"
                        )
                        break
            # Check general patterns in original paths
            for context_name, patterns in PATH_CONTEXT_PATTERNS.items():
                for pattern in patterns:
                    if re.search(pattern, original_lower, re.IGNORECASE):
                        detected_contexts.add(context_name)
                        context_indicators.append(
                            f"original_path:{context_name}:{pattern}"
                        )
                        break

    # Calculate confidence based on indicators found
    if len(context_indicators) >= 3:
        result.confidence = 1.0
    elif len(context_indicators) == 2:
        result.confidence = 0.9
    elif len(context_indicators) == 1:
        result.confidence = 0.7
    else:
        result.confidence = 0.0

    # Set reasoning
    if detected_contexts:
        result.reasoning.append(
            f"Detected path contexts: {', '.join(sorted(detected_contexts))}"
        )
        for indicator in context_indicators[:5]:  # Limit to first 5
            result.reasoning.append(f"  - {indicator}")
    else:
        result.reasoning.append("No specific path context detected")

    result.metadata["detected_contexts"] = list(detected_contexts)
    result.metadata["context_indicators"] = context_indicators

    return result


def are_path_contexts_compatible(
    folder1_path: str,
    folder2_path: str,
    folder1_analysis: Optional[FolderAnalysis] = None,
    folder2_analysis: Optional[FolderAnalysis] = None,
    conn: Optional[DatabaseConnection] = None,
) -> RuleResult:
    """Check if two folders have compatible path contexts.

    Folders from different system sources (e.g., Microsoft Desktop vs macOS Desktop)
    should not be consolidated.

    Args:
        folder1_path: Path to the first folder.
        folder2_path: Path to the second folder.
        folder1_analysis: Optional pre-computed analysis for folder1.
        folder2_analysis: Optional pre-computed analysis for folder2.
        conn: Optional database connection for analysis.

    Returns:
        RuleResult indicating if path contexts are compatible.
    """
    context1 = detect_path_context(folder1_path, folder1_analysis, conn)
    context2 = detect_path_context(folder2_path, folder2_analysis, conn)

    result = RuleResult(
        rule_name="path_context_compatibility",
        applies=True,
        action="allow",
        confidence=0.0,
    )

    contexts1 = set(context1.metadata.get("detected_contexts", []))
    contexts2 = set(context2.metadata.get("detected_contexts", []))

    folder1_name = os.path.basename(folder1_path)
    folder2_name = os.path.basename(folder2_path)

    # Check for conflicting desktop contexts (most important rule)
    has_microsoft_desktop1 = "microsoft_desktop" in contexts1
    has_macos_desktop1 = "macos_desktop" in contexts1
    has_microsoft_desktop2 = "microsoft_desktop" in contexts2
    has_macos_desktop2 = "macos_desktop" in contexts2

    if (has_microsoft_desktop1 and has_macos_desktop2) or (
        has_macos_desktop1 and has_microsoft_desktop2
    ):
        result.action = "exclude_from_consolidation"
        result.confidence = max(context1.confidence, context2.confidence)
        result.reasoning.append(
            "Cannot consolidate: Different desktop sources (Microsoft vs macOS)"
        )
        result.reasoning.append(
            f"  {folder1_name}: {'Microsoft Desktop' if has_microsoft_desktop1 else 'macOS Desktop'}"
        )
        result.reasoning.append(
            f"  {folder2_name}: {'Microsoft Desktop' if has_microsoft_desktop2 else 'macOS Desktop'}"
        )
        result.metadata["conflict_type"] = "desktop_source"
        result.metadata["folder1_contexts"] = list(contexts1)
        result.metadata["folder2_contexts"] = list(contexts2)
        return result

    # Check for conflicting system contexts (microsoft vs macos, excluding desktop-specific)
    system_contexts1 = {"microsoft", "macos", "google", "dropbox"} & contexts1
    system_contexts2 = {"microsoft", "macos", "google", "dropbox"} & contexts2

    # If both have system contexts and they differ, it's a conflict
    if system_contexts1 and system_contexts2:
        conflicting = system_contexts1 ^ system_contexts2  # XOR to find differences
        common = system_contexts1 & system_contexts2
        if conflicting and not common:
            result.action = "exclude_from_consolidation"
            result.confidence = min(context1.confidence, context2.confidence) * 0.8
            result.reasoning.append(
                f"Cannot consolidate: Different source systems ({', '.join(system_contexts1)} vs {', '.join(system_contexts2)})"
            )
            result.reasoning.append(f"  {folder1_name}: {', '.join(system_contexts1)}")
            result.reasoning.append(f"  {folder2_name}: {', '.join(system_contexts2)}")
            result.metadata["conflict_type"] = "system_source"
            result.metadata["folder1_contexts"] = list(contexts1)
            result.metadata["folder2_contexts"] = list(contexts2)
            return result

    # Check for work vs personal conflict
    has_work1 = "work" in contexts1
    has_personal1 = "personal" in contexts1
    has_work2 = "work" in contexts2
    has_personal2 = "personal" in contexts2

    if (has_work1 and has_personal2) or (has_personal1 and has_work2):
        result.action = "exclude_from_consolidation"
        result.confidence = min(context1.confidence, context2.confidence) * 0.7
        result.reasoning.append(
            "Cannot consolidate: Different context types (work vs personal)"
        )
        ctx1_type = "work" if has_work1 else "personal"
        ctx2_type = "work" if has_work2 else "personal"
        result.reasoning.append(f"  {folder1_name}: {ctx1_type}")
        result.reasoning.append(f"  {folder2_name}: {ctx2_type}")
        result.metadata["conflict_type"] = "work_personal"
        result.metadata["folder1_contexts"] = list(contexts1)
        result.metadata["folder2_contexts"] = list(contexts2)
        return result

    # No conflicts found - allow consolidation
    if contexts1 or contexts2:
        shared = contexts1 & contexts2
        if shared:
            result.reasoning.append(
                f"Path contexts compatible (shared: {', '.join(shared)})"
            )
            result.confidence = max(context1.confidence, context2.confidence)
        else:
            result.reasoning.append("Path contexts compatible (no conflicts)")
            result.confidence = 0.5
    else:
        result.reasoning.append("No path contexts detected for either folder")
        result.confidence = 0.3

    result.metadata["folder1_contexts"] = list(contexts1)
    result.metadata["folder2_contexts"] = list(contexts2)

    return result


# =============================================================================
# Combined Smart Rules Application
# =============================================================================


def apply_smart_rules(
    folder_path: str,
    user_name: Optional[str] = None,
    folder_analysis: Optional[FolderAnalysis] = None,
    conn: Optional[DatabaseConnection] = None,
) -> SmartRulesResult:
    """Apply all smart rules to a folder and return combined results.

    Args:
        folder_path: Path to the folder to analyze.
        user_name: Optional name of the user for ownership detection.
        folder_analysis: Optional pre-computed folder analysis.
        conn: Optional database connection for analysis.

    Returns:
        SmartRulesResult with all rule results combined.
    """
    result = SmartRulesResult(folder_path=folder_path)

    # Rule 1: Check if this is a code project (skip entirely)
    code_result = is_code_project(folder_path)
    result.rule_results.append(code_result)

    if code_result.applies and code_result.action == "skip":
        result.should_skip = True
        result.overall_reasoning.append("SKIP: Code project detected")
        result.overall_reasoning.extend(code_result.reasoning)
        return result  # No need to check other rules

    # Rule 2: Check if this is a VA document folder (exclude from consolidation)
    va_result = is_va_document_folder(folder_path, folder_analysis, conn)
    result.rule_results.append(va_result)

    if va_result.applies and va_result.action == "exclude_from_consolidation":
        result.should_exclude_from_consolidation = True
        result.overall_reasoning.append("EXCLUDE: VA document folder")
        result.overall_reasoning.extend(va_result.reasoning)

    # Rule 3: Detect document ownership (MY vs OTHER)
    ownership_result = detect_document_ownership(
        folder_path, user_name, folder_analysis, conn
    )
    result.rule_results.append(ownership_result)
    result.is_my_document = ownership_result.metadata.get("is_my_document")

    if result.is_my_document is not None:
        ownership_type = "MY" if result.is_my_document else "OTHER"
        result.overall_reasoning.append(f"Ownership: {ownership_type} documents")

    # Rule 4: Detect path context (Microsoft, macOS, work, personal, etc.)
    path_context_result = detect_path_context(folder_path, folder_analysis, conn)
    result.rule_results.append(path_context_result)
    result.path_contexts = path_context_result.metadata.get("detected_contexts", [])

    if result.path_contexts:
        result.overall_reasoning.append(
            f"Path context: {', '.join(result.path_contexts)}"
        )

    return result


def apply_smart_rules_to_group(
    folder_paths: list[str],
    user_name: Optional[str] = None,
    conn: Optional[DatabaseConnection] = None,
) -> tuple[bool, list[str], dict[str, SmartRulesResult]]:
    """Apply smart rules to a group of folders and determine if they can consolidate.

    Args:
        folder_paths: List of folder paths in the group.
        user_name: Optional name of the user for ownership detection.
        conn: Optional database connection for analysis.

    Returns:
        Tuple of (should_consolidate, reasoning, individual_results)
    """
    should_consolidate = True
    reasoning = []
    individual_results: dict[str, SmartRulesResult] = {}

    # Apply rules to each folder
    for folder_path in folder_paths:
        result = apply_smart_rules(folder_path, user_name, conn=conn)
        individual_results[folder_path] = result

        # If any folder should be skipped, the whole group shouldn't consolidate
        if result.should_skip:
            should_consolidate = False
            folder_name = os.path.basename(folder_path)
            reasoning.append(f"Cannot consolidate: '{folder_name}' is a code project")

        # If any folder is VA documents, mark for exclusion
        if result.should_exclude_from_consolidation:
            should_consolidate = False
            folder_name = os.path.basename(folder_path)
            reasoning.append(
                f"Cannot consolidate: '{folder_name}' contains VA documents"
            )

    # Check for ownership conflicts between folders
    if should_consolidate and len(folder_paths) >= 2:
        my_folders = []
        other_folders = []

        for path, result in individual_results.items():
            if result.is_my_document is True:
                my_folders.append(path)
            elif result.is_my_document is False:
                other_folders.append(path)

        if my_folders and other_folders:
            should_consolidate = False
            reasoning.append(
                "Cannot consolidate: Mix of MY documents and OTHER people's documents"
            )
            my_names = [os.path.basename(p) for p in my_folders]
            other_names = [os.path.basename(p) for p in other_folders]
            reasoning.append(f"  MY: {', '.join(my_names)}")
            reasoning.append(f"  OTHER: {', '.join(other_names)}")

    # Check for path context conflicts between folders
    if should_consolidate and len(folder_paths) >= 2:
        # Check each pair of folders for path context compatibility
        for i, path1 in enumerate(folder_paths):
            for path2 in folder_paths[i + 1 :]:
                compatibility = are_path_contexts_compatible(path1, path2, conn=conn)
                if compatibility.action == "exclude_from_consolidation":
                    should_consolidate = False
                    reasoning.extend(compatibility.reasoning)
                    break
            if not should_consolidate:
                break

    if should_consolidate and not reasoning:
        reasoning.append("All smart rules passed")

    return should_consolidate, reasoning, individual_results
