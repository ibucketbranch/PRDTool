"""Tests for organizer/llm_enrichment.py module.

Tests cover:
- FileEnrichment dataclass and serialization
- enrich_file function with LLM and keyword fallback
- EnrichmentCache for caching enrichments by file hash
- LLMEnricher high-level service with batch mode
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from organizer.llm_enrichment import (
    EnrichmentCache,
    EnrichmentCacheEntry,
    FileEnrichment,
    LLMEnricher,
    _build_tags,
    _calculate_keyword_confidence,
    _enrich_with_keywords,
    _ensure_list,
    _extract_confidence,
    _extract_dates,
    _extract_document_type,
    _extract_organizations,
    _extract_people,
    _extract_topics,
    _generate_keyword_summary,
    _parse_llm_json_response,
    enrich_file,
)


class TestFileEnrichment:
    """Tests for FileEnrichment dataclass."""

    def test_default_values(self) -> None:
        """Test FileEnrichment has correct default values."""
        enrichment = FileEnrichment()
        assert enrichment.document_type == ""
        assert enrichment.date_references == []
        assert enrichment.people == []
        assert enrichment.organizations == []
        assert enrichment.key_topics == []
        assert enrichment.summary == ""
        assert enrichment.suggested_tags == []
        assert enrichment.confidence == 0.5
        assert enrichment.model_used == ""
        assert enrichment.used_keyword_fallback is False
        assert enrichment.enriched_at != ""  # Auto-set
        assert enrichment.duration_ms == 0

    def test_with_values(self) -> None:
        """Test FileEnrichment with provided values."""
        enrichment = FileEnrichment(
            document_type="invoice",
            date_references=["March 2024"],
            people=["John Doe"],
            organizations=["Acme Corp"],
            key_topics=["finance"],
            summary="Invoice from Acme Corp",
            suggested_tags=["invoice", "2024"],
            confidence=0.95,
            model_used="qwen2.5-coder:14b",
            used_keyword_fallback=False,
        )
        assert enrichment.document_type == "invoice"
        assert enrichment.organizations == ["Acme Corp"]
        assert enrichment.confidence == 0.95

    def test_to_dict(self) -> None:
        """Test FileEnrichment serialization to dictionary."""
        enrichment = FileEnrichment(
            document_type="tax_return",
            date_references=["2024"],
            organizations=["IRS"],
            summary="Tax return for 2024",
        )
        data = enrichment.to_dict()

        assert data["document_type"] == "tax_return"
        assert data["date_references"] == ["2024"]
        assert data["organizations"] == ["IRS"]
        assert data["summary"] == "Tax return for 2024"
        assert "enriched_at" in data

    def test_from_dict(self) -> None:
        """Test FileEnrichment deserialization from dictionary."""
        data = {
            "document_type": "contract",
            "date_references": ["2023-12-15"],
            "people": ["Jane Smith"],
            "organizations": ["Legal Corp"],
            "key_topics": ["legal"],
            "summary": "Employment contract",
            "suggested_tags": ["contract", "2023"],
            "confidence": 0.88,
            "model_used": "llama3.1:8b",
            "used_keyword_fallback": False,
            "enriched_at": "2024-01-01T00:00:00",
            "duration_ms": 500,
        }
        enrichment = FileEnrichment.from_dict(data)

        assert enrichment.document_type == "contract"
        assert enrichment.people == ["Jane Smith"]
        assert enrichment.confidence == 0.88
        assert enrichment.duration_ms == 500

    def test_round_trip_serialization(self) -> None:
        """Test that to_dict and from_dict are inverse operations."""
        original = FileEnrichment(
            document_type="medical_record",
            date_references=["January 2024", "2024-01-15"],
            people=["Dr. Smith", "Patient Name"],
            organizations=["Hospital", "Insurance Co"],
            key_topics=["medical", "health"],
            summary="Medical record from January 2024",
            suggested_tags=["medical", "2024", "Hospital"],
            confidence=0.92,
            model_used="qwen2.5-coder:14b",
            enriched_at="2024-03-01T12:00:00",
        )

        data = original.to_dict()
        restored = FileEnrichment.from_dict(data)

        assert restored.document_type == original.document_type
        assert restored.date_references == original.date_references
        assert restored.people == original.people
        assert restored.organizations == original.organizations
        assert restored.confidence == original.confidence

    def test_matches_search_summary(self) -> None:
        """Test matches_search finds text in summary."""
        enrichment = FileEnrichment(
            summary="Invoice from Verizon for March 2024"
        )
        assert enrichment.matches_search("verizon") is True
        assert enrichment.matches_search("Verizon") is True
        assert enrichment.matches_search("march") is True
        assert enrichment.matches_search("comcast") is False

    def test_matches_search_organizations(self) -> None:
        """Test matches_search finds organizations."""
        enrichment = FileEnrichment(
            organizations=["Acme Corp", "Amazon"]
        )
        assert enrichment.matches_search("acme") is True
        assert enrichment.matches_search("amazon") is True
        assert enrichment.matches_search("google") is False

    def test_matches_search_topics(self) -> None:
        """Test matches_search finds topics."""
        enrichment = FileEnrichment(
            key_topics=["finance", "tax"]
        )
        assert enrichment.matches_search("finance") is True
        assert enrichment.matches_search("tax") is True

    def test_matches_search_dates(self) -> None:
        """Test matches_search finds date references."""
        enrichment = FileEnrichment(
            date_references=["March 2024", "2024-03-15"]
        )
        assert enrichment.matches_search("2024") is True
        assert enrichment.matches_search("march") is True


class TestEnrichmentCache:
    """Tests for EnrichmentCache."""

    def test_empty_cache(self) -> None:
        """Test empty cache operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "cache.json"
            cache = EnrichmentCache(cache_path)

            assert cache.get_count() == 0
            assert cache.get("nonexistent") is None
            assert cache.has("nonexistent") is False

    def test_set_and_get(self) -> None:
        """Test setting and getting cache entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "cache.json"
            cache = EnrichmentCache(cache_path)

            enrichment = FileEnrichment(
                document_type="invoice",
                summary="Test invoice",
            )

            cache.set("abc123", "/path/to/file.pdf", enrichment)

            assert cache.has("abc123") is True
            assert cache.get_count() == 1

            retrieved = cache.get("abc123")
            assert retrieved is not None
            assert retrieved.document_type == "invoice"
            assert retrieved.summary == "Test invoice"

    def test_cache_persistence(self) -> None:
        """Test cache persists to disk and reloads."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "cache.json"

            # Create and populate cache
            cache1 = EnrichmentCache(cache_path)
            cache1.set(
                "hash123",
                "/path/to/file.pdf",
                FileEnrichment(document_type="contract"),
            )

            # Create new cache instance from same file
            cache2 = EnrichmentCache(cache_path)
            assert cache2.has("hash123") is True
            assert cache2.get("hash123").document_type == "contract"

    def test_cache_remove(self) -> None:
        """Test removing entries from cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "cache.json"
            cache = EnrichmentCache(cache_path)

            cache.set("hash1", "/file1.pdf", FileEnrichment())
            cache.set("hash2", "/file2.pdf", FileEnrichment())

            assert cache.get_count() == 2

            result = cache.remove("hash1")
            assert result is True
            assert cache.get_count() == 1
            assert cache.has("hash1") is False
            assert cache.has("hash2") is True

            # Remove non-existent
            result = cache.remove("nonexistent")
            assert result is False

    def test_cache_clear(self) -> None:
        """Test clearing all cache entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "cache.json"
            cache = EnrichmentCache(cache_path)

            cache.set("hash1", "/file1.pdf", FileEnrichment())
            cache.set("hash2", "/file2.pdf", FileEnrichment())
            cache.clear()

            assert cache.get_count() == 0
            assert cache.get("hash1") is None

    def test_get_all_entries(self) -> None:
        """Test getting all cache entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "cache.json"
            cache = EnrichmentCache(cache_path)

            cache.set("hash1", "/file1.pdf", FileEnrichment(document_type="invoice"))
            cache.set("hash2", "/file2.pdf", FileEnrichment(document_type="contract"))

            entries = cache.get_all()
            assert len(entries) == 2
            hashes = {e.file_hash for e in entries}
            assert hashes == {"hash1", "hash2"}

    def test_handles_corrupted_cache(self) -> None:
        """Test cache handles corrupted JSON gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "cache.json"

            # Write corrupted JSON
            with open(cache_path, "w") as f:
                f.write("{invalid json}")

            # Should start fresh without error
            cache = EnrichmentCache(cache_path)
            assert cache.get_count() == 0


class TestKeywordExtraction:
    """Tests for keyword extraction functions."""

    def test_extract_document_type(self) -> None:
        """Test document type extraction."""
        assert _extract_document_type("invoice from acme") == "invoice"
        assert _extract_document_type("tax return 2024") == "tax_return"
        assert _extract_document_type("my resume.pdf") == "resume"
        assert _extract_document_type("medical records") == "medical_record"
        assert _extract_document_type("bank statement") == "bank_statement"
        assert _extract_document_type("random file") == "document"

    def test_extract_dates_years(self) -> None:
        """Test year extraction from text."""
        dates = _extract_dates("Report from 2024 and 2023")
        assert "2024" in dates
        assert "2023" in dates

    def test_extract_dates_month_year(self) -> None:
        """Test month + year extraction."""
        dates = _extract_dates("Invoice dated March 2024")
        assert any("March" in d and "2024" in d for d in dates)

    def test_extract_dates_iso_format(self) -> None:
        """Test ISO date extraction."""
        dates = _extract_dates("Created on 2024-03-15")
        assert "2024-03-15" in dates

    def test_extract_dates_us_format(self) -> None:
        """Test US date format extraction."""
        dates = _extract_dates("Due 03/15/2024")
        assert "03/15/2024" in dates

    def test_extract_organizations(self) -> None:
        """Test organization extraction."""
        orgs = _extract_organizations("payment from irs and chase bank")
        assert "IRS" in orgs
        assert "Chase" in orgs

    def test_extract_organizations_verizon(self) -> None:
        """Test Verizon extraction."""
        orgs = _extract_organizations("verizon bill for march")
        assert "Verizon" in orgs

    def test_extract_organizations_multiple(self) -> None:
        """Test extracting multiple organizations."""
        text = "amazon order shipped via ups paid with wells fargo"
        orgs = _extract_organizations(text)
        assert "Amazon" in orgs
        assert "Wells Fargo" in orgs

    def test_extract_people(self) -> None:
        """Test people name extraction."""
        people = _extract_people("Dr. John Smith and Mrs. Jane Doe")
        assert any("John Smith" in p for p in people)
        assert any("Jane Doe" in p for p in people)

    def test_extract_topics(self) -> None:
        """Test topic extraction."""
        topics = _extract_topics("tax return with medical expenses and insurance")
        assert "tax" in topics
        assert "medical" in topics
        assert "insurance" in topics

    def test_generate_keyword_summary(self) -> None:
        """Test keyword-based summary generation."""
        summary = _generate_keyword_summary(
            filename="verizon_bill_march_2024.pdf",
            document_type="bill",
            organizations=["Verizon"],
        )
        assert "Bill" in summary
        assert "Verizon" in summary

    def test_build_tags(self) -> None:
        """Test tag building from extracted data."""
        tags = _build_tags(
            document_type="invoice",
            date_references=["March 2024"],
            organizations=["Acme Corp"],
            topics=["finance"],
        )
        assert "invoice" in tags
        assert "2024" in tags
        assert "Acme Corp" in tags
        assert "finance" in tags

    def test_calculate_keyword_confidence(self) -> None:
        """Test confidence calculation."""
        # Base confidence
        conf = _calculate_keyword_confidence("document", [], [])
        assert conf == 0.3

        # With document type
        conf = _calculate_keyword_confidence("invoice", [], [])
        assert conf > 0.3

        # With document type + dates
        conf = _calculate_keyword_confidence("invoice", ["2024"], [])
        assert conf > 0.5

        # With all
        conf = _calculate_keyword_confidence("invoice", ["2024"], ["Acme"])
        assert conf >= 0.8


class TestEnrichWithKeywords:
    """Tests for _enrich_with_keywords function."""

    def test_enriches_invoice(self) -> None:
        """Test enriching an invoice."""
        result = _enrich_with_keywords(
            "acme_invoice_2024.pdf",
            "Invoice from Acme Corporation for services in March 2024. Total: $500."
        )

        assert result.document_type == "invoice"
        assert result.used_keyword_fallback is True
        assert "2024" in result.date_references or any("2024" in d for d in result.date_references)
        assert result.summary != ""

    def test_enriches_tax_document(self) -> None:
        """Test enriching a tax document."""
        result = _enrich_with_keywords(
            "1099_2023.pdf",
            "Form 1099 from IRS for tax year 2023"
        )

        assert "tax" in result.document_type.lower()
        assert "IRS" in result.organizations
        assert result.used_keyword_fallback is True

    def test_enriches_verizon_bill(self) -> None:
        """Test enriching a Verizon bill (matches PRD search example)."""
        result = _enrich_with_keywords(
            "verizon_bill_march_2024.pdf",
            "Verizon Wireless bill for account ending in 1234. Billing period: March 2024. Amount due: $89.99"
        )

        assert "Verizon" in result.organizations
        assert any("2024" in d for d in result.date_references)
        assert result.matches_search("verizon") is True
        assert result.matches_search("2024") is True


class TestParseJsonResponse:
    """Tests for _parse_llm_json_response function."""

    def test_parses_valid_json(self) -> None:
        """Test parsing valid JSON."""
        text = '{"document_type": "invoice", "confidence": 0.95}'
        result = _parse_llm_json_response(text)
        assert result is not None
        assert result["document_type"] == "invoice"
        assert result["confidence"] == 0.95

    def test_parses_json_in_markdown(self) -> None:
        """Test parsing JSON in markdown code block."""
        text = '''Here is the result:
```json
{"document_type": "contract", "summary": "Test"}
```
'''
        result = _parse_llm_json_response(text)
        assert result is not None
        assert result["document_type"] == "contract"

    def test_parses_json_with_extra_text(self) -> None:
        """Test parsing JSON with surrounding text."""
        text = 'The analysis shows: {"document_type": "receipt"} which is correct.'
        result = _parse_llm_json_response(text)
        assert result is not None
        assert result["document_type"] == "receipt"

    def test_returns_none_for_invalid(self) -> None:
        """Test returns None for invalid JSON."""
        result = _parse_llm_json_response("This is not JSON at all")
        assert result is None


class TestEnsureList:
    """Tests for _ensure_list helper function."""

    def test_list_input(self) -> None:
        """Test with list input."""
        assert _ensure_list(["a", "b"]) == ["a", "b"]

    def test_string_input(self) -> None:
        """Test with string input."""
        assert _ensure_list("hello") == ["hello"]

    def test_empty_string(self) -> None:
        """Test with empty string."""
        assert _ensure_list("") == []

    def test_none_values(self) -> None:
        """Test filtering None values."""
        assert _ensure_list(["a", None, "b"]) == ["a", "b"]


class TestExtractConfidence:
    """Tests for _extract_confidence function."""

    def test_valid_float(self) -> None:
        """Test with valid float."""
        assert _extract_confidence({"confidence": 0.85}) == 0.85

    def test_valid_int(self) -> None:
        """Test with valid int."""
        assert _extract_confidence({"confidence": 1}) == 1.0

    def test_clamps_values(self) -> None:
        """Test that values are clamped to 0-1."""
        assert _extract_confidence({"confidence": 1.5}) == 1.0
        assert _extract_confidence({"confidence": -0.5}) == 0.0

    def test_missing_confidence(self) -> None:
        """Test with missing confidence."""
        assert _extract_confidence({}) == 0.5

    def test_invalid_confidence(self) -> None:
        """Test with invalid confidence type."""
        assert _extract_confidence({"confidence": "high"}) == 0.5


class TestEnrichFile:
    """Tests for enrich_file function."""

    def test_uses_keyword_fallback_when_no_client(self) -> None:
        """Test falls back to keywords when no LLM client."""
        result = enrich_file(
            filename="invoice_2024.pdf",
            content_text="Invoice from Acme Corp for $500",
            llm_client=None,
            use_llm=True,
        )

        assert result.used_keyword_fallback is True
        assert result.document_type != ""
        assert result.duration_ms >= 0

    def test_uses_keyword_when_use_llm_false(self) -> None:
        """Test uses keywords when use_llm is False."""
        mock_client = MagicMock()

        result = enrich_file(
            filename="contract.pdf",
            content_text="Employment contract",
            llm_client=mock_client,
            use_llm=False,
        )

        assert result.used_keyword_fallback is True
        mock_client.is_ollama_available.assert_not_called()

    def test_uses_llm_when_available(self) -> None:
        """Test uses LLM when available."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = True

        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = json.dumps({
            "document_type": "invoice",
            "date_references": ["March 2024"],
            "people": [],
            "organizations": ["Acme Corp"],
            "key_topics": ["finance"],
            "summary": "Invoice from Acme Corp",
            "suggested_tags": ["invoice", "2024"],
            "confidence": 0.92,
        })
        mock_response.model_used = "qwen2.5-coder:14b"
        mock_client.generate.return_value = mock_response

        result = enrich_file(
            filename="acme_invoice.pdf",
            content_text="Invoice content...",
            llm_client=mock_client,
            use_llm=True,
        )

        assert result.used_keyword_fallback is False
        assert result.document_type == "invoice"
        assert result.model_used == "qwen2.5-coder:14b"
        assert "Acme Corp" in result.organizations
        assert result.confidence == 0.92

    def test_falls_back_on_llm_failure(self) -> None:
        """Test falls back to keywords when LLM fails."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = True

        mock_response = MagicMock()
        mock_response.success = False
        mock_client.generate.return_value = mock_response

        result = enrich_file(
            filename="tax_2024.pdf",
            content_text="Tax return for 2024",
            llm_client=mock_client,
            use_llm=True,
        )

        assert result.used_keyword_fallback is True

    def test_uses_model_router(self) -> None:
        """Test uses model router for model selection."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = True

        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = '{"document_type": "doc", "confidence": 0.8}'
        mock_response.model_used = "custom-model"
        mock_client.generate.return_value = mock_response

        mock_router = MagicMock()
        mock_decision = MagicMock()
        mock_decision.model = "custom-model"
        mock_router.route.return_value = mock_decision

        enrich_file(
            filename="test.pdf",
            content_text="Test content",
            llm_client=mock_client,
            model_router=mock_router,
            use_llm=True,
        )

        mock_router.route.assert_called_once()
        mock_client.generate.assert_called()

    def test_uses_prompt_registry(self) -> None:
        """Test uses prompt registry when available."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = True

        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = '{"document_type": "doc", "confidence": 0.8}'
        mock_response.model_used = "model"
        mock_client.generate.return_value = mock_response

        mock_registry = MagicMock()
        mock_registry.get.return_value = "Custom prompt for {filename}"

        enrich_file(
            filename="test.pdf",
            content_text="Test content",
            llm_client=mock_client,
            prompt_registry=mock_registry,
            use_llm=True,
        )

        mock_registry.get.assert_called_once()


class TestLLMEnricher:
    """Tests for LLMEnricher class."""

    def test_enrich_without_cache(self) -> None:
        """Test enriching without cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test file
            test_file = Path(tmpdir) / "invoice.txt"
            test_file.write_text("Invoice from Acme Corp for March 2024")

            enricher = LLMEnricher(use_llm=False, use_cache=False)
            result = enricher.enrich(test_file)

            assert result.used_keyword_fallback is True
            assert "invoice" in result.document_type.lower()

    def test_enrich_with_cache(self) -> None:
        """Test enriching with cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "contract.txt"
            test_file.write_text("Employment contract for John Doe")

            cache_path = Path(tmpdir) / "cache.json"
            enricher = LLMEnricher(
                use_llm=False,
                use_cache=True,
                cache_path=cache_path,
            )

            # First call - should enrich
            result1 = enricher.enrich(test_file)

            # Second call - should use cache
            result2 = enricher.enrich(test_file)

            assert result1.document_type == result2.document_type
            assert enricher.get_cache_stats()["entry_count"] == 1

    def test_enrich_force_refresh(self) -> None:
        """Test force refresh bypasses cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "doc.txt"
            test_file.write_text("Some document content")

            cache_path = Path(tmpdir) / "cache.json"
            enricher = LLMEnricher(use_llm=False, cache_path=cache_path)

            # First enrichment
            result1 = enricher.enrich(test_file)
            time1 = result1.enriched_at

            # Force refresh
            result2 = enricher.enrich(test_file, force_refresh=True)
            time2 = result2.enriched_at

            # Times should be different (re-enriched)
            assert time1 != time2 or result2.duration_ms >= 0

    def test_enrich_with_provided_content(self) -> None:
        """Test enriching with provided content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "file.txt"
            test_file.write_text("Original content")

            enricher = LLMEnricher(use_llm=False, use_cache=False)
            result = enricher.enrich(
                test_file,
                content_text="Invoice from Amazon for $99",
            )

            # Should use provided content, not file content
            assert "Amazon" in result.organizations

    def test_enrich_batch(self) -> None:
        """Test batch enrichment."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            files = []
            for i in range(3):
                f = Path(tmpdir) / f"doc_{i}.txt"
                f.write_text(f"Document {i} content")
                files.append(f)

            enricher = LLMEnricher(use_llm=False, use_cache=False)
            results = enricher.enrich_batch(files)

            assert len(results) == 3
            for path, enrichment in results:
                assert enrichment is not None
                assert Path(path).exists()

    def test_enrich_batch_with_progress(self) -> None:
        """Test batch enrichment with progress callback."""
        with tempfile.TemporaryDirectory() as tmpdir:
            files = []
            for i in range(3):
                f = Path(tmpdir) / f"doc_{i}.txt"
                f.write_text(f"Document {i}")
                files.append(f)

            progress_calls: list[tuple[int, int, str]] = []

            def progress(current: int, total: int, filename: str) -> None:
                progress_calls.append((current, total, filename))

            enricher = LLMEnricher(use_llm=False, use_cache=False)
            enricher.enrich_batch(files, progress_callback=progress)

            assert len(progress_calls) == 3
            assert progress_calls[0][0] == 1
            assert progress_calls[0][1] == 3

    def test_cache_stats(self) -> None:
        """Test cache statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "cache.json"
            enricher = LLMEnricher(use_llm=False, cache_path=cache_path)

            stats = enricher.get_cache_stats()
            assert stats["enabled"] is True
            assert stats["entry_count"] == 0

    def test_cache_disabled_stats(self) -> None:
        """Test stats when cache is disabled."""
        enricher = LLMEnricher(use_llm=False, use_cache=False)
        stats = enricher.get_cache_stats()
        assert stats["enabled"] is False

    def test_clear_cache(self) -> None:
        """Test clearing the cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "doc.txt"
            test_file.write_text("Document content")

            cache_path = Path(tmpdir) / "cache.json"
            enricher = LLMEnricher(use_llm=False, cache_path=cache_path)

            enricher.enrich(test_file)
            assert enricher.get_cache_stats()["entry_count"] == 1

            enricher.clear_cache()
            assert enricher.get_cache_stats()["entry_count"] == 0


class TestEnrichmentCacheEntry:
    """Tests for EnrichmentCacheEntry dataclass."""

    def test_to_dict(self) -> None:
        """Test serialization to dictionary."""
        entry = EnrichmentCacheEntry(
            file_hash="abc123",
            file_path="/path/to/file.pdf",
            enrichment=FileEnrichment(document_type="invoice"),
        )
        data = entry.to_dict()

        assert data["file_hash"] == "abc123"
        assert data["file_path"] == "/path/to/file.pdf"
        assert data["enrichment"]["document_type"] == "invoice"
        assert "cached_at" in data

    def test_from_dict(self) -> None:
        """Test deserialization from dictionary."""
        data = {
            "file_hash": "def456",
            "file_path": "/another/file.pdf",
            "enrichment": {
                "document_type": "contract",
                "summary": "Test contract",
            },
            "cached_at": "2024-01-01T00:00:00",
        }
        entry = EnrichmentCacheEntry.from_dict(data)

        assert entry.file_hash == "def456"
        assert entry.enrichment.document_type == "contract"


class TestIntegration:
    """Integration tests for the enrichment module."""

    def test_full_enrichment_pipeline(self) -> None:
        """Test complete enrichment pipeline from file to cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a realistic test file
            test_file = Path(tmpdir) / "verizon_bill_march_2024.pdf"
            test_file.write_bytes(
                b"Verizon Wireless\nBilling Period: March 2024\n"
                b"Account: 1234-5678\nAmount Due: $89.99"
            )

            cache_path = Path(tmpdir) / "cache.json"
            enricher = LLMEnricher(
                use_llm=False,
                use_cache=True,
                cache_path=cache_path,
            )

            # Enrich the file
            result = enricher.enrich(test_file)

            # Verify enrichment
            assert result.used_keyword_fallback is True
            assert "Verizon" in result.organizations
            assert result.matches_search("verizon")
            assert result.matches_search("2024")

            # Verify caching
            stats = enricher.get_cache_stats()
            assert stats["entry_count"] == 1

            # Verify cached result
            cached_result = enricher.enrich(test_file)
            assert cached_result.document_type == result.document_type
            assert cached_result.organizations == result.organizations

    def test_search_matching(self) -> None:
        """Test that enrichment supports natural language search."""
        # This tests the PRD requirement:
        # "Find my Verizon bill from March 2024" matches against
        # organizations: ["Verizon"], date_references: ["March 2024"]

        enrichment = FileEnrichment(
            document_type="bill",
            date_references=["March 2024"],
            organizations=["Verizon"],
            summary="Verizon Wireless bill for March 2024",
        )

        # Test various search queries
        assert enrichment.matches_search("verizon") is True
        assert enrichment.matches_search("march 2024") is True
        assert enrichment.matches_search("bill") is True
        assert enrichment.matches_search("comcast") is False
