"""MCP server for FileRoomba — exposes classification, search, and file intelligence.

Run with: python -m organizer --mcp-server
Or: python -c "from organizer.mcp_server import run; run()"

Claude Desktop config: see docs/claude_desktop_config.json
"""

from __future__ import annotations

import json
from pathlib import Path

# Optional: MCP SDK. If not installed, run_mcp_server() will raise with install hint.
try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    FastMCP = None  # type: ignore

DEFAULT_CONFIG_PATH = ".organizer/agent_config.json"


def _load_config(config_path: str | Path) -> dict:
    """Load agent config JSON."""
    path = Path(config_path)
    if not path.exists():
        return {"base_path": str(Path.cwd())}
    return json.loads(path.read_text(encoding="utf-8"))


def _get_inbox_processor(base_path: str):
    """Create InboxProcessor for given base path."""
    from organizer.inbox_processor import InboxProcessor

    return InboxProcessor(
        base_path=base_path,
        inbox_name="In-Box",
        canonical_registry_path="",
        taxonomy_path="",
        use_llm=False,
    )


def _get_dna_registry(base_path: str):
    """Create DNARegistry for given base path."""
    from organizer.file_dna import DNARegistry

    registry_path = Path(base_path) / ".organizer" / "agent" / "file_dna.json"
    return DNARegistry(registry_path=registry_path, use_llm=False)


def _get_override_registry(base_path: str):
    """Create OverrideRegistry for given base path."""
    from organizer.learned_overrides import OverrideRegistry

    overrides_path = Path(base_path) / ".organizer" / "agent" / "learned_overrides.json"
    return OverrideRegistry(overrides_path)


def create_fileroomba_mcp(config_path: str | Path = DEFAULT_CONFIG_PATH) -> "FastMCP":
    """Create and configure the FileRoomba MCP server."""
    if FastMCP is None:
        raise ImportError(
            "MCP SDK not installed. Run: pip install 'mcp[cli]'"
        )

    config = _load_config(config_path)
    base_path = config.get("base_path", str(Path.cwd()))
    base_path = str(Path(base_path).resolve())

    mcp = FastMCP("fileroomba", json_response=True)

    @mcp.tool()
    def classify_file(filepath: str, content_hint: str = "") -> str:
        """Classify a file and return proposed destination bin.

        Args:
            filepath: Full path to the file.
            content_hint: Optional hint about file content (unused for keyword classification).

        Returns:
            JSON with destination_bin, confidence, matched_keywords.
        """
        path = Path(filepath)
        if not path.exists():
            return json.dumps({"error": f"File not found: {filepath}"})
        processor = _get_inbox_processor(base_path)
        routing = processor._classify(path)
        return json.dumps({
            "destination_bin": routing.destination_bin,
            "confidence": routing.confidence,
            "matched_keywords": routing.matched_keywords,
        })

    @mcp.tool()
    def scan_inbox() -> str:
        """Scan In-Box folder and return routing proposals.

        Returns:
            JSON with total_files, routed, unmatched, files list.
        """
        processor = _get_inbox_processor(base_path)
        result = processor.scan()
        return json.dumps({
            "total_files": result.total_files,
            "routed": result.routed,
            "unmatched": result.unmatched,
            "files": [
                {
                    "filename": r.filename,
                    "destination": r.destination_bin,
                    "confidence": r.confidence,
                }
                for r in result.routings
            ],
        })

    @mcp.tool()
    def search_files(query: str) -> str:
        """Search files by keyword across tags, filename, content.

        Args:
            query: Search keyword.

        Returns:
            JSON with results list (filename, path, tags, confidence).
        """
        registry = _get_dna_registry(base_path)
        results = []
        q = query.lower()
        for dna in registry._by_path.values():
            tags_str = " ".join(dna.auto_tags or []).lower()
            if (
                q in tags_str
                or q in (dna.content_summary or "").lower()
                or q in Path(dna.file_path).name.lower()
            ):
                results.append({
                    "filename": Path(dna.file_path).name,
                    "path": dna.file_path,
                    "tags": dna.auto_tags or [],
                    "confidence": 0.8,
                })
        return json.dumps({"results": results[:50]})

    @mcp.tool()
    def get_file_dna(filepath: str) -> str:
        """Get full DNA record for a file.

        Args:
            filepath: Path to the file.

        Returns:
            JSON with full DNA record or error.
        """
        registry = _get_dna_registry(base_path)
        dna = registry.get_by_path(filepath)
        if dna is None:
            return json.dumps({"error": f"File not in registry: {filepath}"})
        return json.dumps(dna.to_dict())

    @mcp.tool()
    def find_duplicates(filepath: str = "") -> str:
        """Find duplicate files. If filepath given, find dupes of that file. Else return all groups.

        Args:
            filepath: Optional path to check for duplicates.

        Returns:
            JSON with groups (hash, files, wasted_bytes).
        """
        registry = _get_dna_registry(base_path)
        groups = []
        if filepath:
            dna = registry.get_by_path(filepath)
            if dna and dna.sha256_hash:
                matches = registry.find_by_hash(dna.sha256_hash)
                if len(matches) > 1:
                    paths = [m.file_path for m in matches]
                    groups.append({
                        "hash": dna.sha256_hash,
                        "files": paths,
                        "wasted_bytes": 0,
                    })
        else:
            for h, paths in registry._by_hash.items():
                if len(paths) > 1:
                    groups.append({"hash": h, "files": paths, "wasted_bytes": 0})
        return json.dumps({"groups": groups})

    @mcp.tool()
    def get_life_context(domain: str) -> str:
        """Get file summary for a life domain (work/finances/legal/health/family/va/education/personal).

        Args:
            domain: Domain to query.

        Returns:
            JSON with file counts and summary.
        """
        registry = _get_dna_registry(base_path)
        domain_map = {
            "work": ["work", "consulting", "project"],
            "finances": ["tax", "bank", "receipt", "invoice", "finance"],
            "legal": ["legal", "contract", "divorce"],
            "health": ["health", "medical"],
            "family": ["family", "camila", "hudson"],
            "va": ["va", "veteran", "disability"],
            "education": ["school", "education", "transcript"],
            "personal": ["personal", "resume", "vehicle"],
        }
        keywords = domain_map.get(domain.lower(), [domain])
        count = 0
        for dna in registry._by_path.values():
            tags = " ".join(dna.auto_tags or []).lower()
            if any(kw in tags for kw in keywords):
                count += 1
        return json.dumps({
            "domain": domain,
            "file_count": count,
            "keywords_used": keywords,
        })

    @mcp.tool()
    def record_correction(filename: str, wrong_bin: str, correct_bin: str) -> str:
        """Record a user correction (wrong_bin -> correct_bin) as a learned override.

        Args:
            filename: Name of the file that was misrouted.
            wrong_bin: Where it was incorrectly routed.
            correct_bin: Where it should have gone.

        Returns:
            JSON confirmation.
        """
        from organizer.learned_overrides import LearnedOverride

        registry = _get_override_registry(base_path)
        stem = Path(filename).stem or filename
        registry.add(LearnedOverride(pattern=stem, correct_bin=correct_bin))
        return json.dumps({
            "success": True,
            "message": "Override recorded",
            "pattern": stem,
            "correct_bin": correct_bin,
        })

    return mcp


def run() -> None:
    """Run the MCP server on stdio (for Claude Desktop / Cursor)."""
    import sys

    config_path = ".organizer/agent_config.json"
    if Path(config_path).exists():
        config_path = str(Path(config_path).resolve())
    else:
        config_path = str(Path.cwd() / config_path)

    mcp = create_fileroomba_mcp(config_path)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run()
