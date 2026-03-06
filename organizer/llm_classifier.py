"""LLM-powered document classifier using local Ollama.

Classifies files into canonical bins (Work, Personal, Family, Finances,
Legal, VA, Archive) using filename + path + content preview signals.
Falls back to keyword heuristics when Ollama is unavailable.
"""

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any

from organizer.light_extractor import FileSignals

CANONICAL_CATEGORIES = [
    "Work", "Personal", "Family", "Finances", "Legal", "VA", "Archive",
]

CLASSIFY_PROMPT = """You are a file classification assistant. Classify this file into exactly one category based on the signals below.

Categories (pick ONE):
- Work: Professional/career items (engineering, companies, projects, presentations, technical docs)
- Personal: Personal items (health, education, hobbies, contacts, side projects)
- Family: Family-related (family members, events, photos)
- Finances: Financial documents (banking, taxes, budget, invoices, pay stubs, bills)
- Legal: Legal documents (contracts, patents, court filings, legal correspondence)
- VA: Veterans Affairs (claims, benefits, DD214, CalVet, military service)
- Archive: Old/historical items with no active use

File signals:
- Filename: {filename}
- Path: {path_context}
- Extension: {extension}
- File size: {file_size} bytes
- Content preview: {preview}

Return ONLY valid JSON (no markdown, no explanation):
{{"category": "...", "subcategory": "...", "entities": [...], "key_dates": [...], "summary": "...", "confidence": 0.0}}

Rules:
- "entities" = people, companies, case numbers found in the signals
- "key_dates" = dates found (YYYY-MM or YYYY format)
- "summary" = one sentence describing the file
- "confidence" = 0.0 to 1.0 how confident you are
"""

KEYWORD_RULES: list[tuple[list[str], str, str]] = [
    (["va", "veteran", "dd214", "calvet", "vba", "vha"], "VA", "Veterans Affairs"),
    (["claim", "appeal", "hlr", "supplemental"], "VA", "Claims"),
    (["tax", "irs", "w-2", "w2", "1099", "tax_return"], "Finances", "Taxes"),
    (["invoice", "receipt", "payment", "bill", "statement"], "Finances", "Bills"),
    (["paycheck", "paystub", "pay_stub", "salary", "wage"], "Finances", "Pay Stubs"),
    (["bank", "chase", "wells_fargo", "savings", "checking"], "Finances", "Banking"),
    (["contract", "agreement", "nda", "lease", "legal"], "Legal", "Contracts"),
    (["patent", "trademark", "copyright", "ip"], "Legal", "Patents"),
    (["divorce", "custody", "fl-", "dcss", "child_support"], "Legal", "Family Law"),
    (["resume", "cv", "cover_letter", "job", "employment"], "Work", "Employment"),
    (["intel", "micron", "lexar", "wyse", "dell", "cisco"], "Work", "Engineering"),
    (["api", "sdk", "firmware", "driver", "kernel", "build"], "Work", "Engineering"),
    (["prd", "spec", "requirement", "design_doc"], "Work", "Engineering"),
    (["wedding", "hales", "george", "family_photo"], "Family", "Events"),
    (["camila", "katerina", "hudson", "andres", "guilllermo"], "Family", "Family Members"),
    (["homework", "school", "course", "tuition", "grade"], "Personal", "Education"),
    (["health", "medical", "doctor", "prescription", "covid"], "Personal", "Health"),
]


@dataclass
class Classification:
    category: str = "Archive"
    subcategory: str = ""
    entities: list[str] = field(default_factory=list)
    key_dates: list[str] = field(default_factory=list)
    summary: str = ""
    confidence: float = 0.0
    model_used: str = "keyword_fallback"


def classify_file(
    signals: FileSignals,
    fast_model: str = "llama3.1:8b-instruct-q8_0",
    smart_model: str = "qwen2.5-coder:14b",
    escalation_threshold: float = 0.7,
    rate_limit_seconds: float = 0.5,
) -> Classification:
    """Classify a file using Ollama LLM with keyword fallback.

    Args:
        signals: FileSignals collected by light_extractor.
        fast_model: Primary Ollama model for bulk classification.
        smart_model: Escalation model for low-confidence results.
        escalation_threshold: Retry with smart model if confidence below this.
        rate_limit_seconds: Delay between Ollama calls.

    Returns:
        Classification with category, entities, dates, summary, confidence.
    """
    result = _classify_with_ollama(signals, fast_model)

    if result and result.confidence >= escalation_threshold:
        if rate_limit_seconds > 0:
            time.sleep(rate_limit_seconds)
        return result

    if smart_model and smart_model != fast_model:
        escalated = _classify_with_ollama(signals, smart_model)
        if escalated and escalated.confidence > (result.confidence if result else 0):
            if rate_limit_seconds > 0:
                time.sleep(rate_limit_seconds)
            return escalated

    if result and result.confidence > 0:
        if rate_limit_seconds > 0:
            time.sleep(rate_limit_seconds)
        return result

    return _classify_with_keywords(signals)


def _classify_with_ollama(signals: FileSignals, model: str) -> Classification | None:
    """Attempt classification via Ollama."""
    try:
        import ollama as ollama_client

        path_context = "/".join(signals.parent_folders) if signals.parent_folders else "(root)"
        preview = signals.content_preview or "(no content preview available)"

        prompt = CLASSIFY_PROMPT.format(
            filename=signals.filename,
            path_context=path_context,
            extension=signals.extension,
            file_size=signals.file_size,
            preview=preview[:400],
        )

        response = ollama_client.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.1, "num_predict": 300},
        )

        content = response.message.content.strip()
        parsed = _parse_llm_response(content)
        if parsed:
            parsed.model_used = model
            return parsed

    except Exception:
        pass
    return None


def _parse_llm_response(content: str) -> Classification | None:
    """Parse JSON response from the LLM."""
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```\w*\n?", "", content)
        content = re.sub(r"\n?```$", "", content)
        content = content.strip()

    try:
        data: dict[str, Any] = json.loads(content)
    except json.JSONDecodeError:
        json_match = re.search(r"\{[^{}]*\}", content, re.DOTALL)
        if not json_match:
            return None
        try:
            data = json.loads(json_match.group())
        except json.JSONDecodeError:
            return None

    category = data.get("category", "Archive")
    if category not in CANONICAL_CATEGORIES:
        for canon in CANONICAL_CATEGORIES:
            if canon.lower() in category.lower():
                category = canon
                break
        else:
            category = "Archive"

    return Classification(
        category=category,
        subcategory=data.get("subcategory", ""),
        entities=data.get("entities", []) or [],
        key_dates=data.get("key_dates", []) or [],
        summary=data.get("summary", ""),
        confidence=min(1.0, max(0.0, float(data.get("confidence", 0.5)))),
    )


def _classify_with_keywords(signals: FileSignals) -> Classification:
    """Fallback classification using keyword matching."""
    text = " ".join([
        signals.filename.lower(),
        "/".join(signals.parent_folders).lower(),
        signals.content_preview[:200].lower(),
    ])
    text = re.sub(r"[^a-z0-9_\-/ ]", " ", text)

    best_score = 0
    best_category = "Archive"
    best_subcategory = ""
    matched_keywords: list[str] = []

    for keywords, category, subcategory in KEYWORD_RULES:
        score = sum(1 for kw in keywords if kw in text)
        if score > best_score:
            best_score = score
            best_category = category
            best_subcategory = subcategory
            matched_keywords = [kw for kw in keywords if kw in text]

    confidence = min(0.85, 0.3 + (best_score * 0.15)) if best_score > 0 else 0.1

    return Classification(
        category=best_category,
        subcategory=best_subcategory,
        entities=matched_keywords[:5],
        key_dates=_extract_years(text),
        summary=f"Classified by keywords: {', '.join(matched_keywords[:3])}" if matched_keywords else "No keyword matches",
        confidence=confidence,
        model_used="keyword_fallback",
    )


def _extract_years(text: str) -> list[str]:
    """Extract year-like patterns from text."""
    years = re.findall(r"\b(19\d{2}|20[0-2]\d)\b", text)
    return sorted(set(years))[:5]
