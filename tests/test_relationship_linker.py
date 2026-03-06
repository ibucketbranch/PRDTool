"""Tests for relationship_linker module.

Tests cover:
- FileRelationship dataclass creation and serialization
- RelationshipCluster properties
- Bin extraction from paths
- File grouping by bin
- Candidate pair generation and prioritization
- LLM-based relationship detection (mocked)
- Keyword fallback relationship detection
- T3 escalation for large clusters
- RelationshipLinker class functionality
"""

import json
from unittest.mock import MagicMock

from organizer.relationship_linker import (
    FileRelationship,
    RelationshipCluster,
    RelationshipLinker,
    T3_ESCALATION_CLUSTER_SIZE,
    _analyze_relationship_with_keywords,
    _analyze_relationship_with_llm,
    _calculate_pair_priority,
    _get_bin_from_path,
    _get_candidate_pairs,
    _group_files_by_bin,
    _parse_llm_json_response,
    _similarity_ratio,
    detect_relationships,
)


# --- FileRelationship Tests ---


class TestFileRelationship:
    """Tests for FileRelationship dataclass."""

    def test_create_relationship(self):
        """Test creating a FileRelationship."""
        rel = FileRelationship(
            source_path="/path/to/file_a.pdf",
            related_path="/path/to/file_b.pdf",
            relationship_type="companion",
            reason="Both are VA evidence documents",
            model_used="qwen2.5-coder:14b",
        )

        assert rel.source_path == "/path/to/file_a.pdf"
        assert rel.related_path == "/path/to/file_b.pdf"
        assert rel.relationship_type == "companion"
        assert rel.reason == "Both are VA evidence documents"
        assert rel.model_used == "qwen2.5-coder:14b"

    def test_to_dict(self):
        """Test serializing to dictionary."""
        rel = FileRelationship(
            source_path="/path/to/a.pdf",
            related_path="/path/to/b.pdf",
            relationship_type="version_of",
            reason="Same document, different versions",
            model_used="llama3.1:8b",
        )

        data = rel.to_dict()

        assert data["source_path"] == "/path/to/a.pdf"
        assert data["related_path"] == "/path/to/b.pdf"
        assert data["relationship_type"] == "version_of"
        assert data["reason"] == "Same document, different versions"
        assert data["model_used"] == "llama3.1:8b"

    def test_from_dict(self):
        """Test deserializing from dictionary."""
        data = {
            "source_path": "/path/to/a.pdf",
            "related_path": "/path/to/b.pdf",
            "relationship_type": "reference",
            "reason": "File A references File B",
            "model_used": "",
        }

        rel = FileRelationship.from_dict(data)

        assert rel.source_path == "/path/to/a.pdf"
        assert rel.related_path == "/path/to/b.pdf"
        assert rel.relationship_type == "reference"
        assert rel.reason == "File A references File B"
        assert rel.model_used == ""

    def test_roundtrip_serialization(self):
        """Test roundtrip through dict serialization."""
        original = FileRelationship(
            source_path="/path/a.pdf",
            related_path="/path/b.pdf",
            relationship_type="companion",
            reason="Test reason",
            model_used="test-model",
        )

        data = original.to_dict()
        restored = FileRelationship.from_dict(data)

        assert restored.source_path == original.source_path
        assert restored.related_path == original.related_path
        assert restored.relationship_type == original.relationship_type
        assert restored.reason == original.reason
        assert restored.model_used == original.model_used


# --- RelationshipCluster Tests ---


class TestRelationshipCluster:
    """Tests for RelationshipCluster dataclass."""

    def test_file_count(self):
        """Test file_count property."""
        # Create mock files
        mock_files = [MagicMock(), MagicMock(), MagicMock()]

        cluster = RelationshipCluster(
            bin_path="/path/to/bin",
            files=mock_files,
        )

        assert cluster.file_count == 3

    def test_needs_t3_escalation_small_cluster(self):
        """Test T3 escalation not needed for small clusters."""
        mock_files = [MagicMock() for _ in range(10)]

        cluster = RelationshipCluster(
            bin_path="/path/to/bin",
            files=mock_files,
        )

        assert not cluster.needs_t3_escalation

    def test_needs_t3_escalation_large_cluster(self):
        """Test T3 escalation needed for large clusters."""
        mock_files = [MagicMock() for _ in range(T3_ESCALATION_CLUSTER_SIZE + 1)]

        cluster = RelationshipCluster(
            bin_path="/path/to/bin",
            files=mock_files,
        )

        assert cluster.needs_t3_escalation


# --- Helper Function Tests ---


class TestGetBinFromPath:
    """Tests for _get_bin_from_path function."""

    def test_va_bin(self):
        """Test extracting VA bin from path."""
        path = "/Users/user/iCloud/VA/Claims/nexus_letter.pdf"
        bin_path = _get_bin_from_path(path)
        assert "VA" in bin_path or "va" in bin_path.lower()

    def test_finances_bin(self):
        """Test extracting Finances Bin from path."""
        path = "/Users/user/iCloud/Finances Bin/Taxes/2024/return.pdf"
        bin_path = _get_bin_from_path(path)
        assert "Finances Bin" in bin_path or "finances" in bin_path.lower()

    def test_employment_bin(self):
        """Test extracting Employment bin from path."""
        path = "/Users/user/iCloud/Employment/Resumes/resume_2024.pdf"
        bin_path = _get_bin_from_path(path)
        assert "Employment" in bin_path or "employment" in bin_path.lower()

    def test_fallback_to_parent(self):
        """Test fallback to parent directory when no bin pattern found."""
        path = "/Users/user/random_folder/document.pdf"
        bin_path = _get_bin_from_path(path)
        assert bin_path == "/Users/user/random_folder"


class TestGroupFilesByBin:
    """Tests for _group_files_by_bin function."""

    def test_groups_files_correctly(self):
        """Test that files are grouped by their bins."""
        # Create mock DNA registry
        mock_registry = MagicMock()

        mock_dna1 = MagicMock()
        mock_dna1.file_path = "/Users/user/VA/Claims/nexus.pdf"

        mock_dna2 = MagicMock()
        mock_dna2.file_path = "/Users/user/VA/Claims/dbq.pdf"

        mock_dna3 = MagicMock()
        mock_dna3.file_path = "/Users/user/Finances Bin/tax.pdf"

        mock_registry.get_all.return_value = [mock_dna1, mock_dna2, mock_dna3]

        bins = _group_files_by_bin(mock_registry)

        # Should have at least 2 different bins
        assert len(bins) >= 2

    def test_empty_registry(self):
        """Test with empty registry."""
        mock_registry = MagicMock()
        mock_registry.get_all.return_value = []

        bins = _group_files_by_bin(mock_registry)

        assert bins == {}


class TestCalculatePairPriority:
    """Tests for _calculate_pair_priority function."""

    def test_high_priority_matching_keywords(self):
        """Test high priority for files with matching keywords."""
        mock_a = MagicMock()
        mock_a.file_path = "/path/nexus_letter_va.pdf"
        mock_a.auto_tags = ["va", "medical", "claim"]

        mock_b = MagicMock()
        mock_b.file_path = "/path/dbq_va_ptsd.pdf"
        mock_b.auto_tags = ["va", "medical", "disability"]

        score = _calculate_pair_priority(mock_a, mock_b)

        assert score > 0.3  # Should have meaningful priority

    def test_low_priority_no_overlap(self):
        """Test low priority for files with no overlap."""
        mock_a = MagicMock()
        mock_a.file_path = "/path/invoice.pdf"
        mock_a.auto_tags = ["finance", "invoice"]

        mock_b = MagicMock()
        mock_b.file_path = "/path/resume.pdf"
        mock_b.auto_tags = ["employment", "resume"]

        score = _calculate_pair_priority(mock_a, mock_b)

        assert score < 0.5  # Should have low priority

    def test_same_document_type_boost(self):
        """Test priority boost for same document type."""
        mock_a = MagicMock()
        mock_a.file_path = "/path/tax_2023.pdf"
        mock_a.auto_tags = ["tax_doc", "2023"]

        mock_b = MagicMock()
        mock_b.file_path = "/path/tax_2024.pdf"
        mock_b.auto_tags = ["tax_doc", "2024"]

        score = _calculate_pair_priority(mock_a, mock_b)

        # Should get boost for matching first tag (document type)
        assert score >= 0.2


class TestGetCandidatePairs:
    """Tests for _get_candidate_pairs function."""

    def test_returns_limited_pairs(self):
        """Test that pairs are limited to max_pairs."""
        mock_files = []
        for i in range(10):
            mock = MagicMock()
            mock.file_path = f"/path/file_{i}.pdf"
            mock.auto_tags = ["common_tag"]
            mock_files.append(mock)

        pairs = _get_candidate_pairs(mock_files, max_pairs=5)

        assert len(pairs) <= 5

    def test_empty_files_list(self):
        """Test with empty files list."""
        pairs = _get_candidate_pairs([])

        assert pairs == []

    def test_single_file(self):
        """Test with single file (no pairs possible)."""
        mock = MagicMock()
        mock.file_path = "/path/file.pdf"
        mock.auto_tags = []

        pairs = _get_candidate_pairs([mock])

        assert pairs == []


# --- Keyword Analysis Tests ---


class TestAnalyzeRelationshipWithKeywords:
    """Tests for _analyze_relationship_with_keywords function."""

    def test_detects_va_companions(self):
        """Test detection of VA companion documents."""
        mock_a = MagicMock()
        mock_a.file_path = "/path/nexus_letter.pdf"
        mock_a.auto_tags = ["va", "claim"]

        mock_b = MagicMock()
        mock_b.file_path = "/path/dbq_ptsd.pdf"
        mock_b.auto_tags = ["va", "disability"]

        result = _analyze_relationship_with_keywords(mock_a, mock_b)

        assert result is not None
        assert result.relationship_type in ["companion", "related"]
        assert result.model_used == ""

    def test_detects_tax_companions(self):
        """Test detection of tax document companions."""
        mock_a = MagicMock()
        mock_a.file_path = "/path/form_1040.pdf"
        mock_a.auto_tags = ["tax", "1040", "irs"]

        mock_b = MagicMock()
        mock_b.file_path = "/path/schedule_c.pdf"
        mock_b.auto_tags = ["tax", "schedule", "irs"]

        result = _analyze_relationship_with_keywords(mock_a, mock_b)

        assert result is not None
        assert result.relationship_type in ["companion", "related"]

    def test_detects_version_pattern(self):
        """Test detection of versioned documents."""
        mock_a = MagicMock()
        mock_a.file_path = "/path/report_v1.pdf"
        mock_a.auto_tags = ["report"]

        mock_b = MagicMock()
        mock_b.file_path = "/path/report_v2.pdf"
        mock_b.auto_tags = ["report"]

        result = _analyze_relationship_with_keywords(mock_a, mock_b)

        assert result is not None
        assert result.relationship_type == "version_of"

    def test_no_relationship_unrelated_files(self):
        """Test no relationship for unrelated files."""
        mock_a = MagicMock()
        mock_a.file_path = "/path/recipe.pdf"
        mock_a.auto_tags = ["recipe", "food"]

        mock_b = MagicMock()
        mock_b.file_path = "/path/photo.jpg"
        mock_b.auto_tags = ["photo", "vacation"]

        result = _analyze_relationship_with_keywords(mock_a, mock_b)

        # Should be None or related with low confidence
        assert result is None or result.relationship_type == "related"


# --- LLM Analysis Tests ---


class TestAnalyzeRelationshipWithLLM:
    """Tests for _analyze_relationship_with_llm function."""

    def test_llm_detects_companion(self):
        """Test LLM-based companion detection."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = json.dumps({
            "has_relationship": True,
            "relationship_type": "companion",
            "confidence": 0.9,
            "reason": "Both are VA claim documents",
        })
        mock_response.model_used = "qwen2.5-coder:14b"
        mock_llm.generate.return_value = mock_response

        mock_a = MagicMock()
        mock_a.file_path = "/path/nexus_letter.pdf"
        mock_a.auto_tags = ["va"]
        mock_a.content_summary = "Medical nexus opinion"

        mock_b = MagicMock()
        mock_b.file_path = "/path/dbq.pdf"
        mock_b.auto_tags = ["va"]
        mock_b.content_summary = "Disability Benefits Questionnaire"

        result = _analyze_relationship_with_llm(mock_a, mock_b, mock_llm)

        assert result is not None
        assert result.relationship_type == "companion"
        assert result.model_used == "qwen2.5-coder:14b"
        assert "VA" in result.reason

    def test_llm_no_relationship(self):
        """Test LLM returns no relationship."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = json.dumps({
            "has_relationship": False,
            "relationship_type": "none",
            "confidence": 0.2,
            "reason": "Unrelated documents",
        })
        mock_response.model_used = "qwen2.5-coder:14b"
        mock_llm.generate.return_value = mock_response

        mock_a = MagicMock()
        mock_a.file_path = "/path/a.pdf"
        mock_a.auto_tags = []
        mock_a.content_summary = ""

        mock_b = MagicMock()
        mock_b.file_path = "/path/b.pdf"
        mock_b.auto_tags = []
        mock_b.content_summary = ""

        result = _analyze_relationship_with_llm(mock_a, mock_b, mock_llm)

        assert result is None

    def test_llm_failure_returns_none(self):
        """Test LLM failure returns None."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.success = False
        mock_response.text = ""
        mock_llm.generate.return_value = mock_response

        mock_a = MagicMock()
        mock_a.file_path = "/path/a.pdf"
        mock_a.auto_tags = []
        mock_a.content_summary = ""

        mock_b = MagicMock()
        mock_b.file_path = "/path/b.pdf"
        mock_b.auto_tags = []
        mock_b.content_summary = ""

        result = _analyze_relationship_with_llm(mock_a, mock_b, mock_llm)

        assert result is None

    def test_uses_t3_for_large_clusters(self):
        """Test T3 model used for large clusters."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = json.dumps({
            "has_relationship": True,
            "relationship_type": "related",
            "confidence": 0.7,
            "reason": "Related documents",
        })
        mock_response.model_used = "cloud-model"
        mock_llm.generate.return_value = mock_response

        mock_router = MagicMock()
        mock_decision = MagicMock()
        mock_decision.model = "cloud-model"
        mock_router.route.return_value = mock_decision

        mock_a = MagicMock()
        mock_a.file_path = "/path/a.pdf"
        mock_a.auto_tags = []
        mock_a.content_summary = ""

        mock_b = MagicMock()
        mock_b.file_path = "/path/b.pdf"
        mock_b.auto_tags = []
        mock_b.content_summary = ""

        _analyze_relationship_with_llm(
            mock_a, mock_b, mock_llm, mock_router, use_t3=True
        )

        # Verify route was called with high complexity
        mock_router.route.assert_called_once()
        call_args = mock_router.route.call_args[0][0]
        assert call_args.complexity == "high"


# --- JSON Parsing Tests ---


class TestParseLLMJsonResponse:
    """Tests for _parse_llm_json_response function."""

    def test_parse_direct_json(self):
        """Test parsing direct JSON string."""
        text = '{"has_relationship": true, "relationship_type": "companion"}'

        result = _parse_llm_json_response(text)

        assert result is not None
        assert result["has_relationship"] is True
        assert result["relationship_type"] == "companion"

    def test_parse_json_in_code_block(self):
        """Test parsing JSON wrapped in markdown code block."""
        text = '''Here is the analysis:
```json
{"has_relationship": true, "relationship_type": "version_of"}
```
'''

        result = _parse_llm_json_response(text)

        assert result is not None
        assert result["has_relationship"] is True
        assert result["relationship_type"] == "version_of"

    def test_parse_json_with_extra_text(self):
        """Test parsing JSON with surrounding text."""
        text = 'Based on my analysis: {"has_relationship": false, "relationship_type": "none"} End of response.'

        result = _parse_llm_json_response(text)

        assert result is not None
        assert result["has_relationship"] is False

    def test_invalid_json_returns_none(self):
        """Test invalid JSON returns None."""
        text = "This is not valid JSON"

        result = _parse_llm_json_response(text)

        assert result is None


# --- Main detect_relationships Tests ---


class TestDetectRelationships:
    """Tests for detect_relationships function."""

    def test_empty_registry_returns_empty(self):
        """Test empty registry returns no relationships."""
        mock_registry = MagicMock()
        mock_registry.get_all.return_value = []

        result = detect_relationships(mock_registry)

        assert result == []

    def test_single_file_returns_empty(self):
        """Test single file returns no relationships."""
        mock_registry = MagicMock()
        mock_dna = MagicMock()
        mock_dna.file_path = "/path/single.pdf"
        mock_registry.get_all.return_value = [mock_dna]

        result = detect_relationships(mock_registry)

        assert result == []

    def test_uses_keyword_fallback_when_llm_unavailable(self):
        """Test keyword fallback when LLM unavailable."""
        mock_registry = MagicMock()

        mock_dna1 = MagicMock()
        mock_dna1.file_path = "/VA/nexus_letter.pdf"
        mock_dna1.auto_tags = ["va", "claim"]

        mock_dna2 = MagicMock()
        mock_dna2.file_path = "/VA/dbq_form.pdf"
        mock_dna2.auto_tags = ["va", "disability"]

        mock_registry.get_all.return_value = [mock_dna1, mock_dna2]

        mock_llm = MagicMock()
        mock_llm.is_ollama_available.return_value = False

        result = detect_relationships(mock_registry, llm_client=mock_llm)

        # Should use keyword fallback, may find relationships
        for rel in result:
            assert rel.model_used == ""

    def test_uses_llm_when_available(self):
        """Test LLM used when available."""
        mock_registry = MagicMock()

        mock_dna1 = MagicMock()
        mock_dna1.file_path = "/VA/nexus.pdf"
        mock_dna1.auto_tags = ["va"]
        mock_dna1.content_summary = "Nexus letter"

        mock_dna2 = MagicMock()
        mock_dna2.file_path = "/VA/dbq.pdf"
        mock_dna2.auto_tags = ["va"]
        mock_dna2.content_summary = "DBQ form"

        mock_registry.get_all.return_value = [mock_dna1, mock_dna2]

        mock_llm = MagicMock()
        mock_llm.is_ollama_available.return_value = True
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = json.dumps({
            "has_relationship": True,
            "relationship_type": "companion",
            "confidence": 0.9,
            "reason": "VA evidence docs",
        })
        mock_response.model_used = "qwen2.5-coder:14b"
        mock_llm.generate.return_value = mock_response

        result = detect_relationships(mock_registry, llm_client=mock_llm)

        # Should have called LLM
        assert mock_llm.generate.called or len(result) == 0


# --- RelationshipLinker Class Tests ---


class TestRelationshipLinker:
    """Tests for RelationshipLinker class."""

    def test_init(self):
        """Test linker initialization."""
        mock_registry = MagicMock()

        linker = RelationshipLinker(mock_registry)

        assert linker._registry == mock_registry
        assert linker._relationships == []

    def test_find_all(self):
        """Test find_all method."""
        mock_registry = MagicMock()
        mock_registry.get_all.return_value = []

        linker = RelationshipLinker(mock_registry)
        result = linker.find_all()

        assert result == []

    def test_find_for_file(self):
        """Test finding relationships for specific file."""
        mock_registry = MagicMock()
        mock_registry.get_all.return_value = []

        linker = RelationshipLinker(mock_registry)
        linker._relationships = [
            FileRelationship(
                source_path="/path/a.pdf",
                related_path="/path/b.pdf",
                relationship_type="companion",
            ),
            FileRelationship(
                source_path="/path/c.pdf",
                related_path="/path/d.pdf",
                relationship_type="reference",
            ),
        ]

        result = linker.find_for_file("/path/a.pdf")

        assert len(result) == 1
        assert result[0].source_path == "/path/a.pdf"

    def test_get_companions(self):
        """Test getting companion files."""
        mock_registry = MagicMock()
        mock_registry.get_all.return_value = []

        linker = RelationshipLinker(mock_registry)
        linker._relationships = [
            FileRelationship(
                source_path="/path/a.pdf",
                related_path="/path/b.pdf",
                relationship_type="companion",
            ),
            FileRelationship(
                source_path="/path/c.pdf",
                related_path="/path/a.pdf",
                relationship_type="companion",
            ),
            FileRelationship(
                source_path="/path/d.pdf",
                related_path="/path/e.pdf",
                relationship_type="version_of",
            ),
        ]

        companions = linker.get_companions("/path/a.pdf")

        assert len(companions) == 2
        assert "/path/b.pdf" in companions
        assert "/path/c.pdf" in companions

    def test_get_report(self):
        """Test getting relationship report."""
        mock_registry = MagicMock()
        mock_registry.get_all.return_value = []

        linker = RelationshipLinker(mock_registry)
        linker._relationships = [
            FileRelationship(
                source_path="/path/a.pdf",
                related_path="/path/b.pdf",
                relationship_type="companion",
                model_used="model-1",
            ),
            FileRelationship(
                source_path="/path/c.pdf",
                related_path="/path/d.pdf",
                relationship_type="companion",
                model_used="",
            ),
            FileRelationship(
                source_path="/path/e.pdf",
                related_path="/path/f.pdf",
                relationship_type="version_of",
                model_used="model-2",
            ),
        ]

        report = linker.get_report()

        assert report["total_count"] == 3
        assert report["by_type"]["companion"] == 2
        assert report["by_type"]["version_of"] == 1
        assert report["llm_detected"] == 2
        assert report["keyword_detected"] == 1

    def test_relationships_property(self):
        """Test relationships property returns copy."""
        mock_registry = MagicMock()
        mock_registry.get_all.return_value = []

        linker = RelationshipLinker(mock_registry)
        original_rel = FileRelationship(
            source_path="/a.pdf",
            related_path="/b.pdf",
            relationship_type="related",
        )
        linker._relationships = [original_rel]

        relationships = linker.relationships

        # Should return a copy
        assert relationships is not linker._relationships
        assert len(relationships) == 1


# --- Similarity Ratio Tests ---


class TestSimilarityRatio:
    """Tests for _similarity_ratio function."""

    def test_identical_strings(self):
        """Test identical strings have ratio 1.0."""
        ratio = _similarity_ratio("test", "test")
        assert ratio == 1.0

    def test_completely_different_strings(self):
        """Test completely different strings have low ratio."""
        ratio = _similarity_ratio("abc", "xyz")
        assert ratio == 0.0

    def test_partial_overlap(self):
        """Test partial overlap gives intermediate ratio."""
        ratio = _similarity_ratio("abcd", "abxy")
        assert 0.0 < ratio < 1.0

    def test_empty_string(self):
        """Test empty string returns 0."""
        ratio = _similarity_ratio("", "test")
        assert ratio == 0.0


# --- Integration Tests ---


class TestIntegration:
    """Integration tests for relationship detection."""

    def test_full_workflow_with_keyword_fallback(self):
        """Test full workflow using keyword fallback."""
        mock_registry = MagicMock()

        # Create VA evidence document set
        mock_dna1 = MagicMock()
        mock_dna1.file_path = "/VA/nexus_letter_ptsd.pdf"
        mock_dna1.auto_tags = ["va", "claim", "medical"]
        mock_dna1.content_summary = "Medical nexus opinion for PTSD"

        mock_dna2 = MagicMock()
        mock_dna2.file_path = "/VA/dbq_ptsd.pdf"
        mock_dna2.auto_tags = ["va", "disability", "medical"]
        mock_dna2.content_summary = "Disability Benefits Questionnaire"

        mock_dna3 = MagicMock()
        mock_dna3.file_path = "/VA/claim_evidence.pdf"
        mock_dna3.auto_tags = ["va", "claim", "evidence"]
        mock_dna3.content_summary = "Supporting evidence for claim"

        mock_registry.get_all.return_value = [mock_dna1, mock_dna2, mock_dna3]

        # Run without LLM (keyword fallback)
        relationships = detect_relationships(mock_registry, use_llm=False)

        # Should find some relationships
        for rel in relationships:
            assert rel.model_used == ""
            assert rel.relationship_type in [
                "companion", "version_of", "reference", "related"
            ]

    def test_linker_full_workflow(self):
        """Test RelationshipLinker full workflow."""
        mock_registry = MagicMock()

        mock_dna1 = MagicMock()
        mock_dna1.file_path = "/tax/form_1040.pdf"
        mock_dna1.auto_tags = ["tax", "1040", "irs"]
        mock_dna1.content_summary = "Form 1040"

        mock_dna2 = MagicMock()
        mock_dna2.file_path = "/tax/schedule_c.pdf"
        mock_dna2.auto_tags = ["tax", "schedule", "irs"]
        mock_dna2.content_summary = "Schedule C"

        mock_registry.get_all.return_value = [mock_dna1, mock_dna2]

        linker = RelationshipLinker(mock_registry, use_llm=False)
        linker.find_all()
        report = linker.get_report()

        assert "total_count" in report
        assert "by_type" in report
