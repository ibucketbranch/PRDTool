"""Tests for the LLM classifier (keyword fallback path)."""

import pytest

from organizer.light_extractor import FileSignals
from organizer.llm_classifier import (
    Classification,
    _classify_with_keywords,
    _extract_years,
    _parse_llm_response,
    CANONICAL_CATEGORIES,
)


def _make_signals(
    filename: str = "file.txt",
    parents: list[str] | None = None,
    preview: str = "",
) -> FileSignals:
    return FileSignals(
        file_path=f"/test/{filename}",
        filename=filename,
        parent_folders=parents or [],
        extension="." + filename.rsplit(".", 1)[-1] if "." in filename else "",
        file_size=1000,
        modified_date="2025-01-01",
        content_preview=preview,
    )


def test_classify_va_claim():
    signals = _make_signals("VA_Claim_2024.pdf", ["VA", "Claims"], "veteran benefits appeal")
    result = _classify_with_keywords(signals)
    assert result.category == "VA"
    assert result.confidence > 0.3


def test_classify_tax_doc():
    signals = _make_signals("W-2_2023.pdf", ["Finances"], "tax return IRS form")
    result = _classify_with_keywords(signals)
    assert result.category == "Finances"


def test_classify_contract():
    signals = _make_signals("NDA_Acme.pdf", ["Legal"], "agreement contract terms")
    result = _classify_with_keywords(signals)
    assert result.category == "Legal"


def test_classify_work_doc():
    signals = _make_signals("API_Spec.pdf", ["Work", "Intel"], "firmware driver build")
    result = _classify_with_keywords(signals)
    assert result.category == "Work"


def test_classify_unknown_defaults_archive():
    signals = _make_signals("random_file.bin", [], "")
    result = _classify_with_keywords(signals)
    assert result.category == "Archive"
    assert result.confidence < 0.3


def test_extract_years():
    assert _extract_years("tax return 2023 filed in 2024") == ["2023", "2024"]
    assert _extract_years("no years here") == []
    assert _extract_years("from 1999 to 2020") == ["1999", "2020"]


def test_parse_llm_response_valid():
    json_str = '{"category": "Work", "subcategory": "Engineering", "entities": ["Intel"], "key_dates": ["2024"], "summary": "API spec", "confidence": 0.85}'
    result = _parse_llm_response(json_str)
    assert result is not None
    assert result.category == "Work"
    assert result.confidence == 0.85
    assert "Intel" in result.entities


def test_parse_llm_response_with_markdown():
    json_str = '```json\n{"category": "VA", "subcategory": "Claims", "entities": [], "key_dates": [], "summary": "test", "confidence": 0.9}\n```'
    result = _parse_llm_response(json_str)
    assert result is not None
    assert result.category == "VA"


def test_parse_llm_response_invalid_category():
    json_str = '{"category": "SomethingElse", "subcategory": "", "entities": [], "key_dates": [], "summary": "", "confidence": 0.5}'
    result = _parse_llm_response(json_str)
    assert result is not None
    assert result.category == "Archive"


def test_parse_llm_response_garbage():
    result = _parse_llm_response("not json at all")
    assert result is None


def test_canonical_categories():
    assert "Work" in CANONICAL_CATEGORIES
    assert "VA" in CANONICAL_CATEGORIES
    assert "Archive" in CANONICAL_CATEGORIES
