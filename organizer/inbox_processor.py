"""Rule-based In-Box file processor.

Scans the In-Box folder and classifies each file by matching its name
(and optionally extracted PDF text) against keyword patterns derived from
the canonical registry and taxonomy.  Results are returned as routing
proposals; the caller decides whether to auto-execute.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now().isoformat()


# ── Keyword → Bin routing table ─────────────────────────────────────
# Priority order matters: first match wins.

ROUTING_RULES: list[tuple[list[str], str]] = [
    # Finance – taxes (before VA because tax forms often mention veterans)
    (["irs", "tax return", "tax ", "taxes", "w-2", "w2 ", "1099", "1040",
      "1098", "1095", "1095b", "1095-b", "schedule c", "k-1", "k1 ",
      "turbotax", "h&r block", "amended return", "fed_state",
      "state_ca"], "Finances Bin/Taxes"),

    # Personal – resumes (before VA because resumes may mention veteran status)
    (["resume", "cv ", "curriculum vitae", "cover letter"], "Personal Bin/Resumes"),

    # VA / disability claims
    (["va ", "va_", "tdiu", "ptsd", "disability rating", "c&p", "nexus",
      "dbq", "service connection", "veteran", "veterans affairs",
      "vba", "supplemental claim", "claim increase",
      "appeal", "nod ", "notice of disagreement",
      "hlr", "higher level review", "higher-level review"], "VA"),

    # Family members
    (["camila"], "Family Bin/Camila"),
    (["hudson"], "Family Bin/Hudson"),
    (["katerina"], "Family Bin/Katerina"),
    (["andres"], "Family Bin/Andres"),
    (["rojas"], "Family Bin/Rojas"),
    (["mom ", " mom", "mom's", "moms"], "Family Bin/Mom"),
    (["dad ", " dad", "dad's", "dads", "disney with dad"], "Family Bin/Dad"),

    # Legal
    (["divorce", "court ", "custody", "attorney", "lawyer",
      "legal ", "affidavit", "subpoena"], "Legal Bin/Divorce"),
    (["trust", "estate plan", "living trust"], "Legal Bin/Estate"),

    # Finance – banking / credit / investments
    (["bank statement", "checking", "savings", "chase ", "wells fargo",
      "bofa", "bank of america", "citi ", "citibank"], "Finances Bin/Banking"),
    (["credit report", "experian", "equifax", "transunion",
      "credit score", "fico"], "Finances Bin/Credit"),
    (["etrade", "e-trade", "fidelity", "vanguard", "schwab", "401k",
      "401(k)", "ira ", "roth", "brokerage", "investment"], "Finances Bin/Investments"),
    (["social security", "ssa ", "ssa_"], "Finances Bin/Social Security Reports"),

    # Finance – general
    (["receipt", "invoice", "purchase", "order confirm", "amazon",
      "paypal", "venmo", "zelle"], "Finances Bin/Receipts"),
    (["statement", "monthly statement", "billing"], "Finances Bin/Statements"),
    (["budget", "expense", "spending"], "Finances Bin/Budget"),

    # Personal
    (["health", "medical", "doctor", "hospital", "pharmacy", "rx ",
      "prescription", "diagnosis", "lab result", "blood test",
      "23andme", "acera"], "Personal Bin/Health"),
    (["bmw", "vehicle", "car ", "dmv", "registration", "title ",
      "insurance policy", "auto insurance"], "Personal Bin/Vehicles"),
    (["mortgage", "lease", "rent ", "property", "hoa ", "deed",
      "escrow", "home inspection", "real estate"], "Personal Bin/RealProperty"),
    (["school", "university", "csu", "college", "transcript",
      "diploma", "degree", "gpa", "education", "tuition"], "Personal Bin/Mikes School Stuff"),
    (["photo", "picture", "image", "img_", "dsc_", "gopro",
      "camera", "screenshot"], "Personal Bin/Photos"),

    # Work
    (["apple ", "apple_", "cupertino"], "Work Bin/Apple"),
    (["evotix"], "Work Bin/Evotix Main"),
    (["intel", "ops archive"], "Work Bin/Intel Ops Archive"),
    (["consulting", "sow ", "engagement", "client "], "Work Bin/Consulting"),
    (["project", "article", "medium", "blog"], "Work Bin/Projects"),
]


# Regex for extracting 4-digit years from filenames (1990-2030)
_FILENAME_YEAR_RE = re.compile(r"(19[89][0-9]|20[0-2][0-9]|2030)")


@dataclass
class InboxRouting:
    """A single proposed file routing decision."""

    filename: str
    source_path: str
    destination_bin: str
    confidence: float
    matched_keywords: list[str] = field(default_factory=list)
    status: str = "proposed"
    error: str = ""
    date_signals: dict[str, Any] = field(default_factory=dict)


@dataclass
class InboxCycleResult:
    """Summary of one In-Box processing pass."""

    inbox_path: str
    scanned_at: str
    total_files: int = 0
    routed: int = 0
    unmatched: int = 0
    errors: int = 0
    routings: list[InboxRouting] = field(default_factory=list)


class InboxProcessor:
    """Stateless, rule-based In-Box classifier and router."""

    def __init__(
        self,
        base_path: str,
        inbox_name: str = "In-Box",
        canonical_registry_path: str = "",
        taxonomy_path: str = "",
    ):
        self.base_path = Path(base_path)
        self.inbox_dir = self.base_path / inbox_name
        self._extra_rules: list[tuple[list[str], str]] = []
        if canonical_registry_path:
            self._load_registry_rules(canonical_registry_path)
        if taxonomy_path:
            self._load_taxonomy_rules(taxonomy_path)

    def _load_registry_rules(self, registry_path: str) -> None:
        """Build supplemental keyword rules from the canonical registry."""
        try:
            data = json.loads(Path(registry_path).read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return
        for folder_name, dest in data.get("mappings", {}).items():
            if dest == "__KEEP_AT_ROOT__":
                continue
            keywords = [folder_name.lower()]
            self._extra_rules.append((keywords, dest))

    def _load_taxonomy_rules(self, taxonomy_path: str) -> None:
        """Build supplemental keyword rules from the taxonomy."""
        try:
            data = json.loads(Path(taxonomy_path).read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return
        for section_key in ("family_members", "finance_subcategories"):
            section = data.get(section_key, {})
            for keyword, dest in section.items():
                self._extra_rules.append(([keyword.replace("_", " ")], dest))

    def scan(self) -> InboxCycleResult:
        """Scan In-Box and produce routing proposals (no moves)."""
        result = InboxCycleResult(
            inbox_path=str(self.inbox_dir),
            scanned_at=_now_iso(),
        )
        if not self.inbox_dir.exists() or not self.inbox_dir.is_dir():
            return result

        for item in sorted(self.inbox_dir.iterdir()):
            if item.name.startswith(".") or item.name == "Processing Errors":
                continue
            if not item.is_file():
                continue

            result.total_files += 1
            routing = self._classify(item)
            result.routings.append(routing)
            if routing.destination_bin:
                result.routed += 1
            else:
                result.unmatched += 1

        return result

    def execute(self, result: InboxCycleResult) -> InboxCycleResult:
        """Execute all proposed routings (move files)."""
        for routing in result.routings:
            if routing.status != "proposed" or not routing.destination_bin:
                continue
            src = Path(routing.source_path)
            dest_dir = self.base_path / routing.destination_bin
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / src.name
            if dest.exists():
                stem = src.stem
                suffix = src.suffix
                dest = dest_dir / f"{stem}_{datetime.now().strftime('%Y%m%d%H%M%S')}{suffix}"
            try:
                shutil.move(str(src), str(dest))
                routing.status = "executed"
            except OSError as exc:
                routing.status = "error"
                routing.error = str(exc)
                result.errors += 1
        return result

    def _extract_date_signals(self, filepath: Path) -> dict[str, Any]:
        """Extract date signals from file metadata and filename."""
        signals: dict[str, Any] = {}
        try:
            stat = filepath.stat()
            mtime = datetime.fromtimestamp(stat.st_mtime)
            signals["mtime_year"] = mtime.year
            signals["mtime_iso"] = mtime.date().isoformat()
        except OSError:
            pass
        filename_years = _FILENAME_YEAR_RE.findall(filepath.name)
        if filename_years:
            signals["filename_years"] = [int(y) for y in filename_years]
        return signals

    def _classify(self, filepath: Path) -> InboxRouting:
        """Match a single file against the routing rules.

        Two-pass strategy: filename match always wins over content match.
        Pass 1: match against filename only (high confidence).
        Pass 2: match against PDF content (lower confidence).
        This prevents content bleed (e.g. a resume mentioning "veteran"
        being routed to VA instead of Resumes).
        """
        stem_lower = filepath.stem.lower()
        filename_text = f" {stem_lower} "

        date_signals = self._extract_date_signals(filepath)

        pdf_text = ""
        if filepath.suffix.lower() == ".pdf":
            pdf_text = self._extract_pdf_text(filepath)

        all_rules = list(ROUTING_RULES) + self._extra_rules

        # Pass 1: filename-only matching (high confidence)
        for keywords, dest in all_rules:
            matched = [kw for kw in keywords if kw in filename_text]
            if matched:
                confidence = 0.92
                if date_signals.get("filename_years") and any(
                    t in filename_text for t in ("tax", "1040", "1099", "1095", "w-2", "w2")
                ):
                    confidence = 0.95
                return InboxRouting(
                    filename=filepath.name,
                    source_path=str(filepath),
                    destination_bin=dest,
                    confidence=confidence,
                    matched_keywords=matched,
                    date_signals=date_signals,
                )

        # Pass 2: content matching for PDFs (lower confidence)
        if pdf_text:
            content_text = f" {pdf_text.lower()} "
            for keywords, dest in all_rules:
                matched = [kw for kw in keywords if kw in content_text]
                if matched:
                    return InboxRouting(
                        filename=filepath.name,
                        source_path=str(filepath),
                        destination_bin=dest,
                        confidence=0.80,
                        matched_keywords=matched,
                        date_signals=date_signals,
                    )

        # Content-based category mapping: try CategoryMapper for taxonomy-aligned categories
        try:
            from organizer.category_mapper import (
                get_canonical_folder_for_category,
                get_category_for_folder_name,
                get_parent_folder_for_category,
            )
            category_key = get_category_for_folder_name(filepath.stem)
            if category_key:
                parent = get_parent_folder_for_category(category_key)
                canonical = get_canonical_folder_for_category(category_key)
                if parent and canonical:
                    dest = f"{parent}/{canonical}"
                    return InboxRouting(
                        filename=filepath.name,
                        source_path=str(filepath),
                        destination_bin=dest,
                        confidence=0.65,
                        matched_keywords=[f"category:{category_key}"],
                        date_signals=date_signals,
                    )
        except ImportError:
            pass

        return InboxRouting(
            filename=filepath.name,
            source_path=str(filepath),
            destination_bin="",
            confidence=0.0,
            matched_keywords=[],
            status="unmatched",
            date_signals=date_signals,
        )

    @staticmethod
    def _extract_pdf_text(filepath: Path, max_chars: int = 2000) -> str:
        """Best-effort first-page text extraction via pdftotext."""
        try:
            out = subprocess.run(
                ["pdftotext", "-l", "1", str(filepath), "-"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return out.stdout[:max_chars] if out.returncode == 0 else ""
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return ""
