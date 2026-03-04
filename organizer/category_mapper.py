"""Category mapper module for mapping files to canonical folder paths.

This module provides category definitions and functions to map files to
appropriate canonical folder paths using fuzzy matching and category-based
lookup.
"""

from typing import Optional

from organizer.canonical_registry import CanonicalRegistry
from organizer.fuzzy_matcher import are_similar_folders, normalize_folder_name


# Main category mapping - maps folder patterns to canonical categories
# Each category has:
#   - patterns: list of keywords that indicate this category
#   - canonical_folder: the preferred folder name for this category
#   - parent_folder: the top-level category folder
CONSOLIDATION_CATEGORIES: dict[str, dict] = {
    "employment": {
        "patterns": [
            "resume",
            "resumes",
            "cv",
            "cover letter",
            "cover_letter",
            "coverletter",
            "job",
            "application",
            "job application",
            "employment",
            "career",
            "interview",
        ],
        "canonical_folder": "Resumes",
        "parent_folder": "Employment",
    },
    "finances": {
        "patterns": [
            "tax",
            "taxes",
            "tax return",
            "tax_return",
            "taxreturn",
            "invoice",
            "invoices",
            "receipt",
            "receipts",
            "budget",
            "financial",
            "finance",
            "bank",
            "banking",
            "statement",
            "expense",
            "expenses",
        ],
        "canonical_folder": "Taxes",
        "parent_folder": "Finances Bin",
    },
    "legal": {
        "patterns": [
            "contract",
            "contracts",
            "agreement",
            "agreements",
            "deed",
            "deeds",
            "legal",
            "lease",
            "nda",
            "terms",
            "policy",
            "policies",
            "license",
            "licenses",
        ],
        "canonical_folder": "Contracts",
        "parent_folder": "Contracts",
    },
    "health": {
        "patterns": [
            "medical",
            "doctor",
            "prescription",
            "prescriptions",
            "health",
            "hospital",
            "insurance",
            "dental",
            "vision",
            "lab",
            "test result",
            "vaccination",
            "immunization",
        ],
        "canonical_folder": "Medical",
        "parent_folder": "Health",
    },
    "identity": {
        "patterns": [
            "passport",
            "id",
            "identification",
            "license",
            "driver",
            "ssn",
            "social security",
            "birth certificate",
            "citizenship",
            "visa",
        ],
        "canonical_folder": "Identity",
        "parent_folder": "Personal",
    },
    "education": {
        "patterns": [
            "diploma",
            "degree",
            "transcript",
            "certificate",
            "certification",
            "school",
            "college",
            "university",
            "academic",
            "graduation",
        ],
        "canonical_folder": "Education",
        "parent_folder": "Education",
    },
}


def get_category_for_folder_name(
    folder_name: str, threshold: float = 0.8
) -> Optional[str]:
    """Determine the category for a folder name based on pattern matching.

    Args:
        folder_name: The folder name to categorize.
        threshold: Minimum similarity score for fuzzy matching.

    Returns:
        The category key (e.g., "employment", "finances") if matched, None otherwise.

    Examples:
        >>> get_category_for_folder_name("Resume")
        'employment'
        >>> get_category_for_folder_name("Tax_2023")
        'finances'
        >>> get_category_for_folder_name("RandomFolder")
    """
    normalized = normalize_folder_name(folder_name)

    for category_key, category_info in CONSOLIDATION_CATEGORIES.items():
        for pattern in category_info["patterns"]:
            pattern_normalized = normalize_folder_name(pattern)
            # Check for exact match after normalization
            if normalized == pattern_normalized:
                return category_key
            # Check for fuzzy match
            if are_similar_folders(folder_name, pattern, threshold=threshold):
                return category_key

    return None


def get_canonical_folder_for_category(category_key: str) -> Optional[str]:
    """Get the canonical folder name for a category.

    Args:
        category_key: The category key (e.g., "employment", "finances").

    Returns:
        The canonical folder name, or None if category not found.

    Examples:
        >>> get_canonical_folder_for_category("employment")
        'Resumes'
        >>> get_canonical_folder_for_category("finances")
        'Taxes'
    """
    if category_key in CONSOLIDATION_CATEGORIES:
        return CONSOLIDATION_CATEGORIES[category_key]["canonical_folder"]
    return None


def get_parent_folder_for_category(category_key: str) -> Optional[str]:
    """Get the parent folder for a category.

    Args:
        category_key: The category key (e.g., "employment", "finances").

    Returns:
        The parent folder name, or None if category not found.

    Examples:
        >>> get_parent_folder_for_category("employment")
        'Employment'
        >>> get_parent_folder_for_category("finances")
        'Finances Bin'
    """
    if category_key in CONSOLIDATION_CATEGORIES:
        return CONSOLIDATION_CATEGORIES[category_key]["parent_folder"]
    return None


def suggest_canonical_path(
    file_path: str,
    file_name: str,
    ai_category: str,
    registry: Optional[CanonicalRegistry] = None,
    base_path: str = "",
    threshold: float = 0.8,
) -> str:
    """Suggest the canonical path for a file based on AI category and existing folders.

    This function first checks if a similar folder already exists in the registry.
    If not, it uses category patterns to determine the appropriate canonical path.

    Args:
        file_path: The current path of the file (used for context).
        file_name: The name of the file being organized.
        ai_category: The category suggested by AI (e.g., "Resume", "Tax_2023").
        registry: Optional CanonicalRegistry instance. If None, a new one is created.
        base_path: Base path prefix for the canonical path.
        threshold: Similarity threshold for fuzzy matching.

    Returns:
        The suggested canonical path for the file.

    Examples:
        >>> suggest_canonical_path("/downloads/doc.pdf", "doc.pdf", "Resume")
        'Employment/Resumes'
        >>> suggest_canonical_path("/downloads/tax.pdf", "tax.pdf", "Tax_2023")
        'Finances Bin/Taxes'
    """
    if registry is None:
        registry = CanonicalRegistry(threshold=threshold)

    # First, check if a similar folder already exists in the registry
    existing = registry.get_canonical_folder(ai_category)
    if existing is not None:
        return existing.path

    # Try to determine the category from the AI-suggested category name
    category_key = get_category_for_folder_name(ai_category, threshold=threshold)

    if category_key is not None:
        parent_folder = get_parent_folder_for_category(category_key)
        canonical_folder = get_canonical_folder_for_category(category_key)

        if parent_folder and canonical_folder:
            # Use get_or_create to register and return canonical path
            return registry.get_or_create(parent_folder, canonical_folder, base_path)

    # Fallback: if no category match, use the AI category directly
    # Use registry to ensure we don't create duplicates
    return registry.get_or_create("", ai_category, base_path)


def map_to_canonical_category(
    folder_name: str,
    registry: Optional[CanonicalRegistry] = None,
    threshold: float = 0.8,
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Map a folder name to its canonical category information.

    This function provides all category information needed for folder consolidation.

    Args:
        folder_name: The folder name to map.
        registry: Optional CanonicalRegistry for checking existing folders.
        threshold: Similarity threshold for fuzzy matching.

    Returns:
        A tuple of (category_key, parent_folder, canonical_folder).
        All values are None if no category match is found.

    Examples:
        >>> map_to_canonical_category("Resume_Docs")
        ('employment', 'Employment', 'Resumes')
        >>> map_to_canonical_category("Tax Returns")
        ('finances', 'Finances Bin', 'Taxes')
        >>> map_to_canonical_category("RandomFolder")
        (None, None, None)
    """
    # First check if registry has this folder
    if registry is not None:
        existing = registry.get_canonical_folder(folder_name)
        if existing is not None and existing.category:
            # Try to find the category key from the stored category
            for key, info in CONSOLIDATION_CATEGORIES.items():
                if info["parent_folder"] == existing.category:
                    return (key, info["parent_folder"], info["canonical_folder"])

    # Try to match based on patterns
    category_key = get_category_for_folder_name(folder_name, threshold=threshold)

    if category_key is not None:
        parent_folder = get_parent_folder_for_category(category_key)
        canonical_folder = get_canonical_folder_for_category(category_key)
        return (category_key, parent_folder, canonical_folder)

    return (None, None, None)


def list_all_categories() -> list[dict]:
    """List all defined categories with their information.

    Returns:
        A list of dictionaries containing category information.

    Examples:
        >>> categories = list_all_categories()
        >>> len(categories) > 0
        True
        >>> categories[0].keys()
        dict_keys(['key', 'patterns', 'canonical_folder', 'parent_folder'])
    """
    return [
        {
            "key": key,
            "patterns": info["patterns"],
            "canonical_folder": info["canonical_folder"],
            "parent_folder": info["parent_folder"],
        }
        for key, info in CONSOLIDATION_CATEGORIES.items()
    ]
