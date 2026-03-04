"""Fuzzy matching module for comparing folder name similarity.

This module provides functions to normalize folder names and determine
if two folder names are similar enough to be considered the same category.
"""

import re
from difflib import SequenceMatcher


def normalize_folder_name(name: str) -> str:
    """Normalize a folder name for comparison.

    Normalizes by:
    - Converting to lowercase
    - Removing underscores, hyphens, and spaces
    - Removing trailing numbers (e.g., "_1", "_2023")
    - Removing common suffixes like "Docs", "Files"
    - Converting plural forms to singular (basic singularization)

    Args:
        name: The folder name to normalize.

    Returns:
        The normalized folder name.

    Examples:
        >>> normalize_folder_name("Resume")
        'resume'
        >>> normalize_folder_name("Resumes")
        'resume'
        >>> normalize_folder_name("Resume_Docs")
        'resume'
        >>> normalize_folder_name("Resume_1")
        'resume'
        >>> normalize_folder_name("Tax_2023")
        'tax'
        >>> normalize_folder_name("Documents_1")
        'document'
    """
    if not name:
        return ""

    # Convert to lowercase
    result = name.lower()

    # Remove common suffixes before other processing
    common_suffixes = ["_docs", "_files", "_documents", "-docs", "-files", "-documents"]
    for suffix in common_suffixes:
        if result.endswith(suffix):
            result = result[: -len(suffix)]
            break

    # Remove trailing numbers (including year patterns like _2023)
    result = re.sub(r"[_\-\s]*\d+$", "", result)

    # Replace underscores, hyphens, and spaces with nothing
    result = re.sub(r"[_\-\s]+", "", result)

    # Basic singularization: handle common plural patterns
    result = _singularize(result)

    return result


def _singularize(word: str) -> str:
    """Convert a word from plural to singular form (basic implementation).

    Args:
        word: The word to singularize.

    Returns:
        The singular form of the word.
    """
    if not word:
        return word

    # Handle common irregular plurals
    irregulars = {
        "taxes": "tax",
        "indices": "index",
        "matrices": "matrix",
        "analyses": "analysis",
        "theses": "thesis",
    }
    if word in irregulars:
        return irregulars[word]

    # Words ending in 'ies' -> 'y' (e.g., 'categories' -> 'category')
    if word.endswith("ies") and len(word) > 3:
        return word[:-3] + "y"

    # Words ending in 'es' after 'sh', 'ch', 'x', 's', 'z' -> remove 'es'
    if word.endswith("es") and len(word) > 2:
        if word[-3] in "shxsz" or word.endswith("ches"):
            return word[:-2]

    # Don't singularize words ending in 'sis' (e.g., analysis, thesis, basis)
    if word.endswith("sis"):
        return word

    # Words ending in 's' (but not 'ss') -> remove 's'
    if word.endswith("s") and not word.endswith("ss") and len(word) > 1:
        return word[:-1]

    return word


def get_similarity_score(name1: str, name2: str) -> float:
    """Calculate the similarity score between two folder names.

    Uses normalized names and SequenceMatcher for comparison.

    Args:
        name1: First folder name.
        name2: Second folder name.

    Returns:
        A float between 0.0 and 1.0, where 1.0 means identical.
    """
    norm1 = normalize_folder_name(name1)
    norm2 = normalize_folder_name(name2)

    # If normalized names are identical, return 1.0
    if norm1 == norm2:
        return 1.0

    # Use SequenceMatcher for fuzzy comparison
    return SequenceMatcher(None, norm1, norm2).ratio()


def are_similar_folders(name1: str, name2: str, threshold: float = 0.8) -> bool:
    """Determine if two folder names are similar enough to be consolidated.

    Args:
        name1: First folder name.
        name2: Second folder name.
        threshold: Minimum similarity score (0.0 to 1.0) to consider folders similar.
            Default is 0.8.

    Returns:
        True if the folders are similar (score >= threshold), False otherwise.

    Examples:
        >>> are_similar_folders("Resume", "Resumes")
        True
        >>> are_similar_folders("Tax_2023", "Tax")
        True
        >>> are_similar_folders("Documents_1", "Documents")
        True
        >>> are_similar_folders("Resume", "Taxes")
        False
    """
    score = get_similarity_score(name1, name2)
    return score >= threshold
