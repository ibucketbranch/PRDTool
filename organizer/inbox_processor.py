"""LLM-native In-Box file processor with keyword fallback.

Scans the In-Box folder and classifies each file using LLM-first classification
with automatic escalation and graceful degradation to keyword-based rules.
Results are returned as routing proposals; the caller decides whether to auto-execute.

Classification strategy:
1. Try LLM classification (T1 Fast model for speed)
2. If confidence < 0.75, escalate to T2 Smart model
3. If LLM unavailable, fall back to keyword ROUTING_RULES
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from organizer.llm_client import LLMClient
    from organizer.learned_rules import LearnedRuleStore
    from organizer.model_router import ModelRouter
    from organizer.prompt_registry import PromptRegistry


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
class LLMClassificationResult:
    """Result from LLM-based classification.

    Attributes:
        bin: The destination bin path.
        subcategory: Optional subcategory within the bin.
        confidence: Confidence score (0.0-1.0).
        reason: LLM's explanation for the classification.
        model_used: The model that produced this result.
        escalated: Whether escalation occurred.
        used_keyword_fallback: Whether keyword fallback was used.
    """

    bin: str
    subcategory: str
    confidence: float
    reason: str
    model_used: str = ""
    escalated: bool = False
    used_keyword_fallback: bool = False


@dataclass
class ClassificationComparison:
    """A/B comparison between LLM and keyword classification results.

    Used during rollout to compare LLM classification against keyword-based
    routing and build confidence in the LLM approach before fully transitioning.

    Attributes:
        filename: Name of the file being classified.
        llm_result: Result from LLM classification (None if LLM unavailable).
        keyword_result: Result from keyword-based classification.
        agreed: Whether both methods agreed on the destination bin.
        winner: Which method's result was used for actual routing.
        timestamp: When the comparison was made.
    """

    filename: str
    llm_result: dict[str, Any] | None
    keyword_result: dict[str, Any]
    agreed: bool
    winner: str  # "llm" or "keyword"
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = _now_iso()


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
    # LLM classification fields
    reason: str = ""  # LLM's explanation for the classification
    model_used: str = ""  # Model that produced this classification
    used_keyword_fallback: bool = False  # Whether keyword fallback was used


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
    """LLM-native In-Box classifier and router with keyword fallback.

    Uses LLM classification by default with automatic escalation.
    Falls back to keyword-based routing when LLM is unavailable.
    """

    def __init__(
        self,
        base_path: str,
        inbox_name: str = "In-Box",
        canonical_registry_path: str = "",
        taxonomy_path: str = "",
        llm_client: "LLMClient | None" = None,
        model_router: "ModelRouter | None" = None,
        prompt_registry: "PromptRegistry | None" = None,
        use_llm: bool = True,
        ab_comparison_enabled: bool = False,
        comparison_logs_dir: str = "",
        routing_history_path: str = "",
        learned_overrides_path: str = "",
        learned_rules_path: str = "",
        use_learned_rules: bool = True,
    ):
        """Initialize the InboxProcessor.

        Args:
            base_path: Root path for file organization.
            inbox_name: Name of the inbox folder.
            canonical_registry_path: Path to canonical registry JSON.
            taxonomy_path: Path to taxonomy JSON.
            llm_client: LLM client for classification. If None, uses keyword only.
            model_router: Model router for tier selection. Created if llm_client provided.
            prompt_registry: Prompt registry for LLM prompts. Created if llm_client provided.
            use_llm: Whether to attempt LLM classification (default True).
            ab_comparison_enabled: If True, run both LLM and keyword classification
                                   and log comparison results.
            comparison_logs_dir: Directory for A/B comparison logs.
                                 Defaults to .organizer/agent/logs if not specified.
            routing_history_path: Path to routing_history.json. Defaults to base_path/.organizer/agent/.
            learned_overrides_path: Path to learned_overrides.json. Defaults to base_path/.organizer/agent/.
            learned_rules_path: Path to learned_routing_rules.json. Defaults to base_path/.organizer/agent/.
            use_learned_rules: Whether to check learned rules before keyword rules (default True).
        """
        self.base_path = Path(base_path)
        self.inbox_dir = self.base_path / inbox_name
        agent_dir = self.base_path / ".organizer" / "agent"
        self._routing_history_path = (
            Path(routing_history_path) if routing_history_path else agent_dir / "routing_history.json"
        )
        self._learned_overrides_path = (
            Path(learned_overrides_path) if learned_overrides_path else agent_dir / "learned_overrides.json"
        )
        self._learned_rules_path = (
            Path(learned_rules_path) if learned_rules_path else agent_dir / "learned_routing_rules.json"
        )
        self._routing_history = None
        self._override_registry = None
        self._learned_rule_store: "LearnedRuleStore | None" = None
        self._use_learned_rules = use_learned_rules
        self._extra_rules: list[tuple[list[str], str]] = []
        self._llm_client = llm_client
        self._model_router = model_router
        self._prompt_registry = prompt_registry
        self._use_llm = use_llm
        self._ab_comparison_enabled = ab_comparison_enabled
        self._comparison_logs_dir = Path(
            comparison_logs_dir or ".organizer/agent/logs"
        )
        self._current_cycle_comparisons: list[ClassificationComparison] = []

        # Initialize LLM components if client provided but router/registry not
        if llm_client is not None and use_llm:
            if model_router is None:
                from organizer.model_router import ModelRouter

                self._model_router = ModelRouter(llm_client=llm_client)
            if prompt_registry is None:
                from organizer.prompt_registry import PromptRegistry

                self._prompt_registry = PromptRegistry()

        if canonical_registry_path:
            self._load_registry_rules(canonical_registry_path)
        if taxonomy_path:
            self._load_taxonomy_rules(taxonomy_path)

    def _get_routing_history(self):
        """Lazy-load routing history."""
        if self._routing_history is None:
            from organizer.routing_history import RoutingHistory
            self._routing_history = RoutingHistory(self._routing_history_path)
        return self._routing_history

    def _get_override_registry(self):
        """Lazy-load learned overrides."""
        if self._override_registry is None:
            from organizer.learned_overrides import OverrideRegistry
            self._override_registry = OverrideRegistry(self._learned_overrides_path)
        return self._override_registry

    def _get_learned_rule_store(self) -> "LearnedRuleStore | None":
        """Lazy-load learned rules store.

        Returns:
            LearnedRuleStore instance if learned rules are enabled and available,
            None otherwise.
        """
        if not self._use_learned_rules:
            return None
        if self._learned_rule_store is None:
            try:
                from organizer.learned_rules import LearnedRuleStore
                self._learned_rule_store = LearnedRuleStore(
                    rules_path=self._learned_rules_path,
                    taxonomy_path=None,  # Taxonomy handled separately
                    override_registry=None,  # Overrides handled separately via _get_override_registry
                    auto_load=True,
                )
            except (ImportError, OSError):
                # Learned rules not available
                self._learned_rule_store = None
        return self._learned_rule_store

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

    def scan(self, cycle_id: str = "") -> InboxCycleResult:
        """Scan In-Box and produce routing proposals (no moves).

        Args:
            cycle_id: Optional cycle identifier for A/B comparison logging.
                     If not provided, a UUID will be generated when A/B mode is enabled.

        Returns:
            InboxCycleResult with routing proposals.
        """
        # Reset comparisons for this scan cycle
        self._current_cycle_comparisons = []

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

        # Save A/B comparison log if enabled and comparisons were made
        if self._ab_comparison_enabled and self._current_cycle_comparisons:
            self._save_comparison_log(cycle_id or str(uuid.uuid4())[:8])

        return result

    def execute(self, result: InboxCycleResult) -> InboxCycleResult:
        """Execute all proposed routings (move files). Records to routing history."""
        from organizer.routing_history import RoutingRecord

        history = self._get_routing_history()
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
                history.record(RoutingRecord(
                    filename=routing.filename,
                    source_path=routing.source_path,
                    destination_bin=routing.destination_bin,
                    confidence=routing.confidence,
                    matched_keywords=routing.matched_keywords,
                    status="executed",
                ))
            except OSError as exc:
                routing.status = "error"
                routing.error = str(exc)
                result.errors += 1
                history.record(RoutingRecord(
                    filename=routing.filename,
                    source_path=routing.source_path,
                    destination_bin=routing.destination_bin,
                    confidence=routing.confidence,
                    matched_keywords=routing.matched_keywords,
                    status="error",
                ))
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

    def _classify_with_keywords(self, filepath: Path, date_signals: dict[str, Any], pdf_text: str) -> InboxRouting:
        """Classify a file using keyword-based rules (fallback method).

        Multi-pass strategy with priority ordering:
        Pass 0: Check learned rules (highest priority after LLM and overrides)
        Pass 1: Match against filename only with keyword rules (high confidence)
        Pass 2: Match against PDF content with keyword rules (lower confidence)
        Pass 3: Category mapper fallback

        This prevents content bleed (e.g. a resume mentioning "veteran"
        being routed to VA instead of Resumes).

        Args:
            filepath: Path to the file to classify.
            date_signals: Date signals extracted from the file.
            pdf_text: Extracted PDF text content.

        Returns:
            InboxRouting with classification result.
        """
        stem_lower = filepath.stem.lower()
        filename_text = f" {stem_lower} "

        # Pass 0: Check learned rules first (before hardcoded ROUTING_RULES)
        learned_store = self._get_learned_rule_store()
        if learned_store is not None:
            # Build content signals for learned rules matching
            content_signals: dict[str, Any] = {}
            if pdf_text:
                # Extract keywords from content for matching
                content_signals["keywords"] = pdf_text.lower().split()[:100]  # First 100 words
            if date_signals.get("filename_years"):
                content_signals["years"] = date_signals["filename_years"]

            match_result = learned_store.match_with_details(filepath.name, content_signals)
            if match_result is not None and match_result.destination:
                # Learned rule matched - high confidence
                return InboxRouting(
                    filename=filepath.name,
                    source_path=str(filepath),
                    destination_bin=match_result.destination,
                    confidence=match_result.confidence,
                    matched_keywords=[f"learned:{match_result.rule_pattern}"],
                    date_signals=date_signals,
                    reason=match_result.reasoning,
                    used_keyword_fallback=True,  # Still considered fallback (not LLM)
                )

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
                    used_keyword_fallback=True,
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
                        used_keyword_fallback=True,
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
                        used_keyword_fallback=True,
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
            used_keyword_fallback=True,
        )

    def _classify(self, filepath: Path) -> InboxRouting:
        """Classify a file using LLM-first strategy with keyword fallback.

        Classification strategy:
        0. Check learned overrides first (user corrections take priority)
        1. Check for correction: file was previously routed, now back in In-Box -> Needs-Review
        2. Try LLM classification (T1 Fast for speed)
        3. If LLM confidence < 0.75, escalate to T2 Smart
        4. If LLM unavailable or fails, fall back to keyword rules

        When A/B comparison mode is enabled, both LLM and keyword classification
        are run for every file, and results are logged for analysis.

        Args:
            filepath: Path to the file to classify.

        Returns:
            InboxRouting with classification result and metadata.
        """
        date_signals = self._extract_date_signals(filepath)

        # 0. Learned overrides take priority over built-in rules
        override_reg = self._get_override_registry()
        override = override_reg.find_match(filepath.name)
        if override:
            return InboxRouting(
                filename=filepath.name,
                source_path=str(filepath),
                destination_bin=override.correct_bin,
                confidence=0.95,
                matched_keywords=[f"override:{override.pattern}"],
                date_signals=date_signals,
                used_keyword_fallback=True,
            )

        # 1. Correction detection: file was previously routed, now back in In-Box
        history = self._get_routing_history()
        if history.is_correction(filepath.name):
            return InboxRouting(
                filename=filepath.name,
                source_path=str(filepath),
                destination_bin="Needs-Review",
                confidence=0.95,
                matched_keywords=["correction_detected"],
                date_signals=date_signals,
                used_keyword_fallback=True,
            )

        # Extract content preview for LLM
        pdf_text = ""
        if filepath.suffix.lower() == ".pdf":
            pdf_text = self._extract_pdf_text(filepath)

        # A/B comparison mode: run BOTH methods and log results
        if self._ab_comparison_enabled:
            return self._classify_with_ab_comparison(filepath, date_signals, pdf_text)

        # Normal mode: LLM-first with keyword fallback
        if self._use_llm and self._llm_client is not None:
            content_preview = pdf_text if pdf_text else ""
            llm_result = self._classify_with_llm(filepath, content_preview)

            if llm_result is not None and llm_result.bin:
                return InboxRouting(
                    filename=filepath.name,
                    source_path=str(filepath),
                    destination_bin=llm_result.bin,
                    confidence=llm_result.confidence,
                    matched_keywords=[f"llm:{llm_result.model_used}"],
                    date_signals=date_signals,
                    reason=llm_result.reason,
                    model_used=llm_result.model_used,
                    used_keyword_fallback=False,
                )

        # Fall back to keyword-based classification
        return self._classify_with_keywords(filepath, date_signals, pdf_text)

    def _classify_with_ab_comparison(
        self, filepath: Path, date_signals: dict[str, Any], pdf_text: str
    ) -> InboxRouting:
        """Classify using both LLM and keyword methods, logging comparison.

        This method is used when A/B comparison mode is enabled. It runs both
        classification methods and stores the comparison for later analysis.

        Args:
            filepath: Path to the file to classify.
            date_signals: Date signals extracted from the file.
            pdf_text: Extracted PDF text content.

        Returns:
            InboxRouting with the winning classification result.
        """
        content_preview = pdf_text if pdf_text else ""

        # Always get keyword result
        keyword_routing = self._classify_with_keywords(filepath, date_signals, pdf_text)
        keyword_result = {
            "bin": keyword_routing.destination_bin,
            "confidence": keyword_routing.confidence,
            "matched_keywords": keyword_routing.matched_keywords,
        }

        # Try LLM classification
        llm_result_dict: dict[str, Any] | None = None
        llm_routing: InboxRouting | None = None

        if self._use_llm and self._llm_client is not None:
            llm_classification = self._classify_with_llm(filepath, content_preview)
            if llm_classification is not None and llm_classification.bin:
                llm_result_dict = {
                    "bin": llm_classification.bin,
                    "subcategory": llm_classification.subcategory,
                    "confidence": llm_classification.confidence,
                    "reason": llm_classification.reason,
                    "model_used": llm_classification.model_used,
                    "escalated": llm_classification.escalated,
                }
                llm_routing = InboxRouting(
                    filename=filepath.name,
                    source_path=str(filepath),
                    destination_bin=llm_classification.bin,
                    confidence=llm_classification.confidence,
                    matched_keywords=[f"llm:{llm_classification.model_used}"],
                    date_signals=date_signals,
                    reason=llm_classification.reason,
                    model_used=llm_classification.model_used,
                    used_keyword_fallback=False,
                )

        # Determine agreement and winner
        llm_bin = llm_result_dict["bin"] if llm_result_dict else ""
        keyword_bin = keyword_result["bin"]
        agreed = llm_bin == keyword_bin if llm_bin else False
        winner = "llm" if llm_routing is not None else "keyword"

        # Log comparison
        comparison = ClassificationComparison(
            filename=filepath.name,
            llm_result=llm_result_dict,
            keyword_result=keyword_result,
            agreed=agreed,
            winner=winner,
        )
        self._current_cycle_comparisons.append(comparison)

        # Return the winning routing
        return llm_routing if llm_routing is not None else keyword_routing

    def _save_comparison_log(self, cycle_id: str) -> Path:
        """Save A/B comparison results to a JSON log file.

        Args:
            cycle_id: Identifier for the current scan cycle.

        Returns:
            Path to the saved log file.
        """
        self._comparison_logs_dir.mkdir(parents=True, exist_ok=True)
        log_path = self._comparison_logs_dir / f"llm_comparison_{cycle_id}.json"

        # Calculate summary statistics
        total = len(self._current_cycle_comparisons)
        agreed_count = sum(1 for c in self._current_cycle_comparisons if c.agreed)
        llm_available_count = sum(
            1 for c in self._current_cycle_comparisons if c.llm_result is not None
        )
        llm_winner_count = sum(
            1 for c in self._current_cycle_comparisons if c.winner == "llm"
        )

        log_data = {
            "cycle_id": cycle_id,
            "timestamp": _now_iso(),
            "summary": {
                "total_files": total,
                "llm_available": llm_available_count,
                "keyword_only": total - llm_available_count,
                "agreed": agreed_count,
                "disagreed": llm_available_count - agreed_count,
                "agreement_rate": (
                    agreed_count / llm_available_count
                    if llm_available_count > 0
                    else 0.0
                ),
                "llm_winner_count": llm_winner_count,
                "keyword_winner_count": total - llm_winner_count,
            },
            "comparisons": [asdict(c) for c in self._current_cycle_comparisons],
        }

        log_path.write_text(json.dumps(log_data, indent=2), encoding="utf-8")
        return log_path

    def get_current_comparisons(self) -> list[ClassificationComparison]:
        """Get the list of comparisons from the current/last scan cycle.

        Returns:
            List of ClassificationComparison objects.
        """
        return self._current_cycle_comparisons

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

    def _get_available_bins(self) -> str:
        """Get a formatted string of available bins for LLM prompting."""
        # Extract unique bins from ROUTING_RULES and extra rules
        bins: set[str] = set()
        for _, dest in ROUTING_RULES:
            bins.add(dest)
        for _, dest in self._extra_rules:
            bins.add(dest)
        return "\n".join(sorted(bins))

    def _parse_llm_json_response(self, text: str) -> dict[str, Any]:
        """Parse JSON from LLM response, handling common formatting issues.

        Args:
            text: Raw LLM response text.

        Returns:
            Parsed JSON as dict, or empty dict if parsing fails.
        """
        # Try to extract JSON from response
        # LLMs sometimes wrap JSON in markdown code blocks
        text = text.strip()

        # Remove markdown code blocks
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        # Try to find JSON object in text
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to find JSON between braces
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass

        return {}

    def _extract_confidence(self, text: str) -> float | None:
        """Extract confidence score from LLM JSON response.

        Args:
            text: Raw LLM response text.

        Returns:
            Confidence score (0.0-1.0) or None if not found.
        """
        parsed = self._parse_llm_json_response(text)
        confidence = parsed.get("confidence")
        if isinstance(confidence, (int, float)):
            return float(confidence)
        return None

    def _classify_with_llm(
        self, filepath: Path, content_preview: str
    ) -> LLMClassificationResult | None:
        """Classify a file using LLM with automatic escalation.

        Uses T1 Fast model first, escalates to T2 Smart if confidence < 0.75.
        Returns None if LLM is unavailable (caller should use keyword fallback).

        Args:
            filepath: Path to the file to classify.
            content_preview: Content preview (first 500 chars) for classification.

        Returns:
            LLMClassificationResult or None if LLM unavailable.
        """
        if (
            not self._use_llm
            or self._llm_client is None
            or self._model_router is None
            or self._prompt_registry is None
        ):
            return None

        # Check if LLM is operational
        if not self._model_router.is_llm_operational():
            return None

        # Build prompt
        bins = self._get_available_bins()
        try:
            prompt = self._prompt_registry.get(
                "classify_file",
                filename=filepath.name,
                content=content_preview[:500] if content_preview else "(no content preview)",
                bins=bins,
            )
        except (FileNotFoundError, KeyError):
            # Prompt not available, fall back to keyword
            return None

        # Create task profile for classification
        from organizer.model_router import TaskProfile

        profile = TaskProfile(
            task_type="classify",
            complexity="low",  # File classification is a low-complexity task
            content_length=len(content_preview),
        )

        # Use generate_with_escalation for automatic escalation handling
        try:
            result = self._model_router.generate_with_escalation(
                prompt=prompt,
                profile=profile,
                confidence_extractor=self._extract_confidence,
                keyword_fallback=None,  # We handle fallback separately
                temperature=0.0,  # Deterministic for consistency
                max_tokens=256,
            )
        except RuntimeError:
            # LLM failed, return None to trigger keyword fallback
            return None

        if result.used_keyword_fallback:
            # Escalation chain exhausted without success
            return None

        # Parse the response
        parsed = self._parse_llm_json_response(result.text)
        if not parsed:
            return None

        bin_value = parsed.get("bin", "")
        if not bin_value:
            return None

        # Build destination path (bin + optional subcategory)
        subcategory = parsed.get("subcategory", "")
        destination = bin_value
        if subcategory and subcategory != bin_value:
            # Only add subcategory if it's not already part of the bin path
            if not bin_value.endswith(subcategory):
                destination = f"{bin_value}/{subcategory}"

        return LLMClassificationResult(
            bin=destination,
            subcategory=subcategory,
            confidence=result.confidence if result.confidence is not None else 0.5,
            reason=parsed.get("reason", ""),
            model_used=result.model_used,
            escalated=result.escalation_count > 0,
            used_keyword_fallback=False,
        )
