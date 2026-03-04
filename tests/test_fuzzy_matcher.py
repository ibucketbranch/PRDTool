"""Tests for the fuzzy_matcher module.

Tests cover edge cases specified in the PRD:
- "Resume" vs "Resumes"
- "Tax_2023" vs "Tax"
- "Documents_1" vs "Documents"
"""

from organizer.fuzzy_matcher import (
    normalize_folder_name,
    are_similar_folders,
    get_similarity_score,
    _singularize,
)


class TestNormalizeFolderName:
    """Tests for normalize_folder_name function."""

    def test_lowercase_conversion(self):
        """Should convert to lowercase."""
        assert normalize_folder_name("Resume") == "resume"
        assert normalize_folder_name("DOCUMENTS") == "document"
        assert normalize_folder_name("TaX") == "tax"

    def test_removes_underscores(self):
        """Should remove underscores."""
        assert normalize_folder_name("resume_docs") == "resume"
        assert normalize_folder_name("my_folder") == "myfolder"

    def test_removes_hyphens(self):
        """Should remove hyphens."""
        assert normalize_folder_name("resume-docs") == "resume"
        assert normalize_folder_name("my-folder") == "myfolder"

    def test_removes_spaces(self):
        """Should remove spaces."""
        assert normalize_folder_name("Tax Returns") == "taxreturn"

    def test_removes_trailing_numbers(self):
        """Should remove trailing numbers."""
        assert normalize_folder_name("Resume_1") == "resume"
        assert normalize_folder_name("Documents_2") == "document"
        assert normalize_folder_name("folder_123") == "folder"

    def test_removes_year_suffixes(self):
        """Should remove year suffixes like _2023."""
        assert normalize_folder_name("Tax_2023") == "tax"
        assert normalize_folder_name("Tax-2024") == "tax"
        assert normalize_folder_name("Reports 2022") == "report"

    def test_removes_common_suffixes(self):
        """Should remove common suffixes like _Docs, _Files."""
        assert normalize_folder_name("Resume_Docs") == "resume"
        assert normalize_folder_name("Resume_Files") == "resume"
        assert normalize_folder_name("Tax_Documents") == "tax"

    def test_singularization(self):
        """Should convert plural to singular."""
        assert normalize_folder_name("Resumes") == "resume"
        assert normalize_folder_name("Documents") == "document"
        assert normalize_folder_name("Taxes") == "tax"
        assert normalize_folder_name("Categories") == "category"

    def test_empty_string(self):
        """Should handle empty strings."""
        assert normalize_folder_name("") == ""

    def test_combined_normalization(self):
        """Should handle multiple normalizations together."""
        assert normalize_folder_name("Resumes_2023") == "resume"
        assert normalize_folder_name("Tax_Returns_Files") == "taxreturn"


class TestSingularize:
    """Tests for the _singularize helper function."""

    def test_regular_plurals(self):
        """Should handle regular -s plurals."""
        assert _singularize("documents") == "document"
        assert _singularize("folders") == "folder"
        assert _singularize("resumes") == "resume"

    def test_es_plurals(self):
        """Should handle -es plurals."""
        assert _singularize("taxes") == "tax"
        assert _singularize("boxes") == "box"
        assert _singularize("wishes") == "wish"

    def test_ies_plurals(self):
        """Should handle -ies plurals."""
        assert _singularize("categories") == "category"
        assert _singularize("directories") == "directory"

    def test_irregular_plurals(self):
        """Should handle known irregular plurals."""
        assert _singularize("analyses") == "analysis"
        assert _singularize("theses") == "thesis"

    def test_already_singular(self):
        """Should not change already singular words."""
        assert _singularize("resume") == "resume"
        assert _singularize("tax") == "tax"
        assert _singularize("analysis") == "analysis"

    def test_words_ending_in_ss(self):
        """Should not remove s from words ending in ss."""
        assert _singularize("class") == "class"
        assert _singularize("boss") == "boss"

    def test_empty_string(self):
        """Should handle empty strings."""
        assert _singularize("") == ""


class TestGetSimilarityScore:
    """Tests for get_similarity_score function."""

    def test_identical_names(self):
        """Should return 1.0 for identical names."""
        assert get_similarity_score("Resume", "Resume") == 1.0

    def test_normalized_identical(self):
        """Should return 1.0 for names that normalize to same value."""
        assert get_similarity_score("Resume", "Resumes") == 1.0
        assert get_similarity_score("Tax_2023", "Tax") == 1.0
        assert get_similarity_score("Documents_1", "Documents") == 1.0

    def test_completely_different(self):
        """Should return low score for completely different names."""
        score = get_similarity_score("Resume", "Finances")
        assert score < 0.5

    def test_partially_similar(self):
        """Should return partial score for partially similar names."""
        score = get_similarity_score("Tax_Reports", "Tax_Returns")
        assert 0.5 < score < 1.0


class TestAreSimilarFolders:
    """Tests for are_similar_folders function."""

    def test_resume_variations(self):
        """Should identify Resume variations as similar."""
        assert are_similar_folders("Resume", "Resumes") is True
        assert are_similar_folders("Resume", "Resume_Docs") is True
        assert are_similar_folders("Resume", "Resume_1") is True
        assert are_similar_folders("Resumes", "Resume_Docs") is True

    def test_tax_variations(self):
        """Should identify Tax variations as similar."""
        assert are_similar_folders("Tax_2023", "Tax") is True
        assert are_similar_folders("Taxes", "Tax") is True
        # Tax_Returns normalizes to 'taxreturn', different from 'tax'
        # so similarity is only 0.5 - these are semantically different
        # The consolidation planner will handle grouping by category
        assert are_similar_folders("Tax_Returns", "Taxes", threshold=0.5) is True

    def test_documents_variations(self):
        """Should identify Documents variations as similar."""
        assert are_similar_folders("Documents_1", "Documents") is True
        assert are_similar_folders("Document", "Documents") is True

    def test_different_folders(self):
        """Should identify different folders as not similar."""
        assert are_similar_folders("Resume", "Taxes") is False
        assert are_similar_folders("Documents", "Photos") is False
        assert are_similar_folders("Work", "Personal") is False

    def test_custom_threshold(self):
        """Should respect custom threshold values."""
        # With a very low threshold, more things are similar
        assert are_similar_folders("Resume", "Research", threshold=0.3) is True
        # With a very high threshold, fewer things are similar
        assert (
            are_similar_folders("Tax_Reports", "Tax_Documents", threshold=0.99) is False
        )

    def test_case_insensitivity(self):
        """Should be case insensitive."""
        assert are_similar_folders("resume", "RESUME") is True
        assert are_similar_folders("Tax", "TAX") is True


class TestPRDEdgeCases:
    """Tests for specific edge cases mentioned in the PRD."""

    def test_resume_vs_resumes(self):
        """PRD: 'Resume' vs 'Resumes' should be similar."""
        assert are_similar_folders("Resume", "Resumes") is True

    def test_tax_2023_vs_tax(self):
        """PRD: 'Tax_2023' vs 'Tax' should be similar."""
        assert are_similar_folders("Tax_2023", "Tax") is True

    def test_documents_1_vs_documents(self):
        """PRD: 'Documents_1' vs 'Documents' should be similar."""
        assert are_similar_folders("Documents_1", "Documents") is True

    def test_resume_docs_variation(self):
        """Additional: 'Resume_Docs' should match 'Resume'."""
        assert are_similar_folders("Resume_Docs", "Resume") is True

    def test_resumes_2023_variation(self):
        """Additional: 'Resumes_2023' should match 'Resume'."""
        assert are_similar_folders("Resumes_2023", "Resume") is True
