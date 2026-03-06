"""Tests for domain_detector module - LLM-powered domain detection.

Covers:
- DomainContext dataclass creation and serialization
- LLM-powered domain detection with T2 Smart (mock)
- Keyword fallback when LLM unavailable
- Domain signal matching for all supported domains
- Graceful degradation from LLM to keyword fallback
- Confidence score calculation
- Evidence extraction
"""

from unittest.mock import MagicMock

from organizer.domain_detector import (
    DOMAIN_KEYWORDS,
    DOMAIN_TYPES,
    DomainContext,
    DomainDetector,
    detect_domain,
)
from organizer.structure_analyzer import FolderNode, StructureSnapshot


class TestDomainContext:
    """Tests for DomainContext dataclass."""

    def test_create_domain_context(self) -> None:
        """Should create DomainContext with required fields."""
        context = DomainContext(
            detected_domain="medical",
            confidence=0.85,
        )
        assert context.detected_domain == "medical"
        assert context.confidence == 0.85
        assert context.evidence == []
        assert context.model_used == ""
        # detected_at should be auto-set
        assert context.detected_at != ""

    def test_create_domain_context_with_all_fields(self) -> None:
        """Should create DomainContext with all optional fields."""
        context = DomainContext(
            detected_domain="legal",
            confidence=0.92,
            evidence=["Found 'contracts' folder", "Multiple .pdf legal documents"],
            model_used="qwen2.5-coder:14b",
            detected_at="2024-01-15T10:30:00",
        )
        assert context.detected_domain == "legal"
        assert context.confidence == 0.92
        assert context.evidence == ["Found 'contracts' folder", "Multiple .pdf legal documents"]
        assert context.model_used == "qwen2.5-coder:14b"
        assert context.detected_at == "2024-01-15T10:30:00"

    def test_to_dict(self) -> None:
        """Should convert DomainContext to dictionary."""
        context = DomainContext(
            detected_domain="engineering",
            confidence=0.78,
            evidence=["Found 'src' folder", "Code files present"],
            model_used="llama3.1:8b",
        )
        d = context.to_dict()
        assert d["detected_domain"] == "engineering"
        assert d["confidence"] == 0.78
        assert d["evidence"] == ["Found 'src' folder", "Code files present"]
        assert d["model_used"] == "llama3.1:8b"
        assert "detected_at" in d

    def test_from_dict(self) -> None:
        """Should create DomainContext from dictionary."""
        data = {
            "detected_domain": "automotive",
            "confidence": 0.88,
            "evidence": ["Dealership inventory folder", "VIN numbers in filenames"],
            "model_used": "qwen2.5-coder:14b",
            "detected_at": "2024-06-01T14:00:00",
        }
        context = DomainContext.from_dict(data)
        assert context.detected_domain == "automotive"
        assert context.confidence == 0.88
        assert context.evidence == ["Dealership inventory folder", "VIN numbers in filenames"]
        assert context.model_used == "qwen2.5-coder:14b"
        assert context.detected_at == "2024-06-01T14:00:00"

    def test_from_dict_with_defaults(self) -> None:
        """Should handle missing fields with defaults."""
        data: dict = {}
        context = DomainContext.from_dict(data)
        assert context.detected_domain == "generic_business"
        assert context.confidence == 0.0
        assert context.evidence == []
        assert context.model_used == ""

    def test_used_llm_property(self) -> None:
        """Should correctly identify if LLM was used."""
        context_with_llm = DomainContext(
            detected_domain="personal",
            confidence=0.9,
            model_used="qwen2.5-coder:14b",
        )
        assert context_with_llm.used_llm is True

        context_keyword = DomainContext(
            detected_domain="personal",
            confidence=0.7,
            model_used="keyword_fallback",
        )
        assert context_keyword.used_llm is False

        context_no_model = DomainContext(
            detected_domain="personal",
            confidence=0.5,
            model_used="",
        )
        assert context_no_model.used_llm is False


class TestDomainTypes:
    """Tests for domain type constants."""

    def test_all_domains_have_keywords(self) -> None:
        """Every domain type should have keyword signals."""
        for domain in DOMAIN_TYPES:
            assert domain in DOMAIN_KEYWORDS
            assert len(DOMAIN_KEYWORDS[domain]) > 0

    def test_expected_domain_types(self) -> None:
        """Should have all expected domain types."""
        expected = {
            "personal",
            "medical",
            "legal",
            "automotive",
            "creative",
            "engineering",
            "generic_business",
        }
        assert DOMAIN_TYPES == expected


def _create_mock_snapshot(folders: list[FolderNode]) -> StructureSnapshot:
    """Helper to create a mock StructureSnapshot."""
    return StructureSnapshot(
        root_path="/test/root",
        max_depth=4,
        total_folders=len(folders),
        total_files=sum(f.file_count for f in folders),
        total_size_bytes=sum(f.total_size_bytes for f in folders),
        folders=folders,
    )


class TestKeywordFallback:
    """Tests for keyword-based domain detection fallback."""

    def test_detect_medical_domain(self) -> None:
        """Should detect medical domain from keywords."""
        folders = [
            FolderNode(
                path="/test/VA",
                name="VA",
                depth=0,
                sample_filenames=["nexus_letter.pdf", "dbq_ptsd.pdf", "medical_records.pdf"],
            ),
            FolderNode(
                path="/test/VA/claims",
                name="claims",
                depth=1,
                sample_filenames=["disability_claim.pdf", "treatment_notes.pdf"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        detector = DomainDetector()  # No LLM client - will use fallback
        context = detector.detect_domain(snapshot, use_llm=False)

        assert context.detected_domain == "medical"
        assert context.confidence > 0.5
        assert context.model_used == "keyword_fallback"
        assert len(context.evidence) > 0

    def test_detect_legal_domain(self) -> None:
        """Should detect legal domain from keywords."""
        folders = [
            FolderNode(
                path="/test/Legal",
                name="Legal",
                depth=0,
                sample_filenames=["contract_2024.pdf", "agreement_signed.pdf"],
            ),
            FolderNode(
                path="/test/Legal/Litigation",
                name="Litigation",
                depth=1,
                sample_filenames=["lawsuit_brief.pdf", "court_filing.doc"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        detector = DomainDetector()
        context = detector.detect_domain(snapshot, use_llm=False)

        assert context.detected_domain == "legal"
        assert context.confidence > 0.5

    def test_detect_automotive_domain(self) -> None:
        """Should detect automotive domain from keywords."""
        folders = [
            FolderNode(
                path="/test/Dealership",
                name="Dealership",
                depth=0,
                sample_filenames=["inventory_list.xlsx", "vin_records.csv"],
            ),
            FolderNode(
                path="/test/Dealership/Sales",
                name="Sales",
                depth=1,
                sample_filenames=["vehicle_sales_report.pdf", "trade-in_values.xlsx"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        detector = DomainDetector()
        context = detector.detect_domain(snapshot, use_llm=False)

        assert context.detected_domain == "automotive"

    def test_detect_creative_domain(self) -> None:
        """Should detect creative domain from keywords."""
        folders = [
            FolderNode(
                path="/test/Portfolio",
                name="Portfolio",
                depth=0,
                sample_filenames=["design_concept.psd", "render_final.png"],
            ),
            FolderNode(
                path="/test/Portfolio/Projects",
                name="Projects",
                depth=1,
                sample_filenames=["brand_assets.zip", "video_edit_v2.mp4"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        detector = DomainDetector()
        context = detector.detect_domain(snapshot, use_llm=False)

        assert context.detected_domain == "creative"

    def test_detect_engineering_domain(self) -> None:
        """Should detect engineering domain from keywords."""
        folders = [
            FolderNode(
                path="/test/src",
                name="src",
                depth=0,
                sample_filenames=["main.py", "config.json", "api_handler.ts"],
            ),
            FolderNode(
                path="/test/src/lib",
                name="lib",
                depth=1,
                sample_filenames=["utils.py", "test_suite.py"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        detector = DomainDetector()
        context = detector.detect_domain(snapshot, use_llm=False)

        assert context.detected_domain == "engineering"

    def test_detect_personal_domain(self) -> None:
        """Should detect personal domain from keywords."""
        folders = [
            FolderNode(
                path="/test/Family",
                name="Family",
                depth=0,
                sample_filenames=["vacation_photos.zip", "family_reunion.jpg"],
            ),
            FolderNode(
                path="/test/Personal",
                name="Personal",
                depth=1,
                sample_filenames=["recipes.docx", "holiday_memories.pdf"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        detector = DomainDetector()
        context = detector.detect_domain(snapshot, use_llm=False)

        assert context.detected_domain == "personal"

    def test_detect_generic_business_domain(self) -> None:
        """Should detect generic business domain from keywords."""
        folders = [
            FolderNode(
                path="/test/Finance",
                name="Finance",
                depth=0,
                sample_filenames=["invoice_001.pdf", "expense_report.xlsx"],
            ),
            FolderNode(
                path="/test/Finance/Tax",
                name="Tax",
                depth=1,
                sample_filenames=["tax_return_2024.pdf", "quarterly_report.pdf"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        detector = DomainDetector()
        context = detector.detect_domain(snapshot, use_llm=False)

        assert context.detected_domain == "generic_business"

    def test_default_to_generic_business(self) -> None:
        """Should default to generic_business when no signals match."""
        folders = [
            FolderNode(
                path="/test/random",
                name="random",
                depth=0,
                sample_filenames=["xyz123.dat", "zzz_unknown.bin"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        detector = DomainDetector()
        context = detector.detect_domain(snapshot, use_llm=False)

        assert context.detected_domain == "generic_business"
        assert context.confidence <= 0.5  # Low confidence for default

    def test_confidence_increases_with_more_matches(self) -> None:
        """Confidence should increase with more keyword matches."""
        # Few matches
        folders_few = [
            FolderNode(
                path="/test/medical",
                name="medical",
                depth=0,
                sample_filenames=["doc1.pdf"],
            ),
        ]
        snapshot_few = _create_mock_snapshot(folders_few)
        context_few = DomainDetector().detect_domain(snapshot_few, use_llm=False)

        # Many matches
        folders_many = [
            FolderNode(
                path="/test/medical",
                name="medical",
                depth=0,
                sample_filenames=[
                    "medical_records.pdf",
                    "prescription_list.pdf",
                    "hospital_bills.pdf",
                ],
            ),
            FolderNode(
                path="/test/medical/VA",
                name="VA",
                depth=1,
                sample_filenames=[
                    "va_claims.pdf",
                    "disability_rating.pdf",
                    "treatment_plan.pdf",
                ],
            ),
            FolderNode(
                path="/test/medical/doctors",
                name="doctors",
                depth=1,
                sample_filenames=["doctor_notes.pdf", "diagnosis_report.pdf"],
            ),
        ]
        snapshot_many = _create_mock_snapshot(folders_many)
        context_many = DomainDetector().detect_domain(snapshot_many, use_llm=False)

        assert context_many.confidence >= context_few.confidence


class TestLLMDetection:
    """Tests for LLM-powered domain detection."""

    def test_detect_with_llm_success(self) -> None:
        """Should successfully detect domain using LLM."""
        # Create mock LLM client
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = True
        mock_client.generate.return_value = MagicMock(
            success=True,
            text='{"domain": "medical", "confidence": 0.92, "evidence": ["VA folder found", "Medical documents present"]}',
            model_used="qwen2.5-coder:14b",
        )

        folders = [
            FolderNode(path="/test/VA", name="VA", depth=0, file_count=10),
        ]
        snapshot = _create_mock_snapshot(folders)

        detector = DomainDetector(llm_client=mock_client)
        context = detector.detect_domain(snapshot)

        assert context.detected_domain == "medical"
        assert context.confidence == 0.92
        assert context.model_used == "qwen2.5-coder:14b"
        assert len(context.evidence) == 2
        assert context.used_llm is True

    def test_detect_with_llm_uses_model_router(self) -> None:
        """Should use model router to select model."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = True
        mock_client.generate.return_value = MagicMock(
            success=True,
            text='{"domain": "engineering", "confidence": 0.88, "evidence": ["src folder"]}',
            model_used="qwen2.5-coder:14b",
        )

        mock_router = MagicMock()
        mock_router.route.return_value = MagicMock(model="qwen2.5-coder:14b")

        folders = [
            FolderNode(path="/test/src", name="src", depth=0, file_count=5),
        ]
        snapshot = _create_mock_snapshot(folders)

        detector = DomainDetector(llm_client=mock_client, model_router=mock_router)
        context = detector.detect_domain(snapshot)

        # Should have called route
        mock_router.route.assert_called_once()
        assert context.detected_domain == "engineering"

    def test_detect_llm_fallback_on_unavailable(self) -> None:
        """Should fall back to keywords when LLM unavailable."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = False

        folders = [
            FolderNode(
                path="/test/medical",
                name="medical",
                depth=0,
                sample_filenames=["prescription.pdf", "hospital_visit.pdf"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        detector = DomainDetector(llm_client=mock_client)
        context = detector.detect_domain(snapshot)

        assert context.model_used == "keyword_fallback"
        assert context.used_llm is False
        # Should still detect medical from keywords
        assert context.detected_domain == "medical"

    def test_detect_llm_fallback_on_generation_failure(self) -> None:
        """Should fall back to keywords when LLM generation fails."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = True
        mock_client.generate.return_value = MagicMock(
            success=False,
            text="",
            error="Model error",
        )

        folders = [
            FolderNode(
                path="/test/legal",
                name="legal",
                depth=0,
                sample_filenames=["contract.pdf", "agreement.pdf"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        detector = DomainDetector(llm_client=mock_client)
        context = detector.detect_domain(snapshot)

        assert context.model_used == "keyword_fallback"
        assert context.detected_domain == "legal"

    def test_detect_llm_handles_malformed_json(self) -> None:
        """Should fall back to keywords on malformed JSON response."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = True
        mock_client.generate.return_value = MagicMock(
            success=True,
            text="This is not valid JSON at all",
            model_used="qwen2.5-coder:14b",
        )

        folders = [
            FolderNode(
                path="/test/creative",
                name="creative",
                depth=0,
                sample_filenames=["design_assets.psd", "portfolio.pdf"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        detector = DomainDetector(llm_client=mock_client)
        context = detector.detect_domain(snapshot)

        # Should fall back to keywords
        assert context.model_used == "keyword_fallback"

    def test_detect_llm_extracts_json_from_markdown(self) -> None:
        """Should extract JSON from markdown code blocks."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = True
        mock_client.generate.return_value = MagicMock(
            success=True,
            text="""Here is the analysis:
```json
{"domain": "personal", "confidence": 0.85, "evidence": ["Family photos folder"]}
```
Let me know if you need more details.""",
            model_used="qwen2.5-coder:14b",
        )

        folders = [
            FolderNode(path="/test/Family", name="Family", depth=0, file_count=50),
        ]
        snapshot = _create_mock_snapshot(folders)

        detector = DomainDetector(llm_client=mock_client)
        context = detector.detect_domain(snapshot)

        assert context.detected_domain == "personal"
        assert context.confidence == 0.85
        assert context.model_used == "qwen2.5-coder:14b"

    def test_detect_llm_validates_domain_type(self) -> None:
        """Should default to generic_business for invalid domain."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = True
        mock_client.generate.return_value = MagicMock(
            success=True,
            text='{"domain": "invalid_domain", "confidence": 0.9, "evidence": []}',
            model_used="qwen2.5-coder:14b",
        )

        folders = [FolderNode(path="/test/stuff", name="stuff", depth=0)]
        snapshot = _create_mock_snapshot(folders)

        detector = DomainDetector(llm_client=mock_client)
        context = detector.detect_domain(snapshot)

        assert context.detected_domain == "generic_business"

    def test_detect_llm_clamps_confidence(self) -> None:
        """Should clamp confidence to valid range."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = True
        mock_client.generate.return_value = MagicMock(
            success=True,
            text='{"domain": "legal", "confidence": 1.5, "evidence": []}',
            model_used="qwen2.5-coder:14b",
        )

        folders = [FolderNode(path="/test", name="test", depth=0)]
        snapshot = _create_mock_snapshot(folders)

        detector = DomainDetector(llm_client=mock_client)
        context = detector.detect_domain(snapshot)

        assert context.confidence <= 1.0


class TestConvenienceFunction:
    """Tests for detect_domain convenience function."""

    def test_detect_domain_without_llm(self) -> None:
        """Should work with keyword fallback only."""
        folders = [
            FolderNode(
                path="/test/medical",
                name="medical",
                depth=0,
                sample_filenames=["prescription.pdf", "health_records.pdf"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        context = detect_domain(snapshot, use_llm=False)

        assert context.detected_domain == "medical"
        assert context.model_used == "keyword_fallback"

    def test_detect_domain_with_llm_client(self) -> None:
        """Should use provided LLM client."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = True
        mock_client.generate.return_value = MagicMock(
            success=True,
            text='{"domain": "engineering", "confidence": 0.9, "evidence": ["src folder"]}',
            model_used="qwen2.5-coder:14b",
        )

        folders = [FolderNode(path="/test/src", name="src", depth=0)]
        snapshot = _create_mock_snapshot(folders)

        context = detect_domain(snapshot, llm_client=mock_client)

        assert context.detected_domain == "engineering"
        assert context.used_llm is True


class TestStructureSummaryBuilding:
    """Tests for building structure summaries for LLM prompts."""

    def test_build_structure_summary_respects_max_depth(self) -> None:
        """Should only include folders up to max_depth."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = True
        mock_client.generate.return_value = MagicMock(
            success=True,
            text='{"domain": "personal", "confidence": 0.8, "evidence": []}',
            model_used="qwen2.5-coder:14b",
        )

        folders = [
            FolderNode(path="/test", name="test", depth=0, file_count=1),
            FolderNode(path="/test/level1", name="level1", depth=1, file_count=2),
            FolderNode(path="/test/level1/level2", name="level2", depth=2, file_count=3),
            FolderNode(path="/test/level1/level2/level3", name="level3", depth=3, file_count=4),
            FolderNode(path="/test/level1/level2/level3/level4", name="level4", depth=4, file_count=5),
        ]
        snapshot = _create_mock_snapshot(folders)

        detector = DomainDetector(llm_client=mock_client)
        summary = detector._build_structure_summary(snapshot, max_depth=2)

        # Should include depth 0, 1, 2 but not 3, 4
        assert "test:" in summary
        assert "level1:" in summary
        assert "level2:" in summary
        assert "level3:" not in summary
        assert "level4:" not in summary

    def test_build_structure_summary_includes_file_types(self) -> None:
        """Should include file type information."""
        folders = [
            FolderNode(
                path="/test",
                name="test",
                depth=0,
                file_count=10,
                file_types={".pdf": 5, ".doc": 3, ".txt": 2},
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        detector = DomainDetector()
        summary = detector._build_structure_summary(snapshot)

        assert ".pdf" in summary
        assert "10 files" in summary

    def test_build_structure_summary_includes_samples(self) -> None:
        """Should include sample filenames."""
        folders = [
            FolderNode(
                path="/test",
                name="test",
                depth=0,
                sample_filenames=["invoice.pdf", "receipt.pdf", "statement.pdf"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        detector = DomainDetector()
        summary = detector._build_structure_summary(snapshot)

        assert "samples:" in summary
        assert "invoice.pdf" in summary


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_snapshot(self) -> None:
        """Should handle empty snapshot gracefully."""
        snapshot = _create_mock_snapshot([])

        detector = DomainDetector()
        context = detector.detect_domain(snapshot, use_llm=False)

        assert context.detected_domain == "generic_business"
        assert context.confidence <= 0.5

    def test_llm_exception_handling(self) -> None:
        """Should handle LLM exceptions gracefully."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.side_effect = Exception("Connection error")

        folders = [
            FolderNode(
                path="/test/medical",
                name="medical",
                depth=0,
                sample_filenames=["prescription.pdf"],
            ),
        ]
        snapshot = _create_mock_snapshot(folders)

        detector = DomainDetector(llm_client=mock_client)
        context = detector.detect_domain(snapshot)

        # Should fall back to keywords despite exception
        assert context.model_used == "keyword_fallback"
        assert context.detected_domain == "medical"

    def test_router_exception_handling(self) -> None:
        """Should use default model when router fails."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = True
        mock_client.generate.return_value = MagicMock(
            success=True,
            text='{"domain": "personal", "confidence": 0.8, "evidence": []}',
            model_used="qwen2.5-coder:14b",
        )

        mock_router = MagicMock()
        mock_router.route.side_effect = RuntimeError("No models available")

        folders = [FolderNode(path="/test", name="test", depth=0)]
        snapshot = _create_mock_snapshot(folders)

        detector = DomainDetector(llm_client=mock_client, model_router=mock_router)
        context = detector.detect_domain(snapshot)

        # Should still succeed with default model
        assert context.detected_domain == "personal"
