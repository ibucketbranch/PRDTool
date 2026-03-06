"""Tests for organizer.mcp_server module."""

import json
from pathlib import Path

import pytest

from organizer.mcp_server import (
    _load_config,
    create_prdtool_mcp,
)


def test_load_config_missing(tmp_path: Path) -> None:
    """_load_config returns default when file missing."""
    config = _load_config(tmp_path / "nonexistent.json")
    assert "base_path" in config
    assert config["base_path"] == str(Path.cwd())


def test_load_config_exists(tmp_path: Path) -> None:
    """_load_config loads from file."""
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"base_path": "/test/path", "inbox_enabled": True}),
        encoding="utf-8",
    )
    config = _load_config(config_path)
    assert config["base_path"] == "/test/path"


def test_create_mcp_returns_server(tmp_path: Path) -> None:
    """create_prdtool_mcp returns FastMCP when SDK installed."""
    config_path = tmp_path / "agent_config.json"
    config_path.write_text(
        json.dumps({"base_path": str(tmp_path)}),
        encoding="utf-8",
    )
    try:
        mcp = create_prdtool_mcp(config_path)
        assert mcp is not None
        assert hasattr(mcp, "tool")
    except ImportError as e:
        if "MCP SDK not installed" in str(e):
            pytest.skip("MCP SDK not installed - run: pip install 'mcp[cli]'")
        raise
