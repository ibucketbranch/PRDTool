"""launchd integration for running the organizer agent continuously on macOS."""

from __future__ import annotations

import os
import plistlib
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


DEFAULT_LAUNCHD_LABEL = "com.prdtool.organizer.agent"


@dataclass
class LaunchdResult:
    """Result payload for launchd operations."""

    success: bool
    message: str


def launch_agents_dir() -> Path:
    """Return user LaunchAgents directory."""
    return Path.home() / "Library" / "LaunchAgents"


def plist_path_for_label(label: str) -> Path:
    """Return plist path for a service label."""
    return launch_agents_dir() / f"{label}.plist"


def launchd_domain() -> str:
    """Return launchd GUI domain for the current user."""
    return f"gui/{os.getuid()}"


def launchd_service_target(label: str) -> str:
    """Return launchd service target value."""
    return f"{launchd_domain()}/{label}"


def build_plist_payload(
    *,
    label: str,
    config_path: Path,
    working_directory: Path,
    stdout_log_path: Path,
    stderr_log_path: Path,
) -> dict:
    """Build launchd plist payload for continuous organizer agent."""
    return {
        "Label": label,
        "ProgramArguments": [
            sys.executable,
            "-m",
            "organizer",
            "--agent-run",
            "--agent-config",
            str(config_path),
        ],
        "RunAtLoad": True,
        "KeepAlive": True,
        "WorkingDirectory": str(working_directory),
        "StandardOutPath": str(stdout_log_path),
        "StandardErrorPath": str(stderr_log_path),
    }


def run_launchctl(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Execute launchctl and capture output without raising."""
    return subprocess.run(
        ["launchctl", *args],
        check=False,
        capture_output=True,
        text=True,
    )


def install_launchd_service(
    *,
    label: str,
    config_path: Path,
    working_directory: Path,
    logs_dir: Path,
) -> LaunchdResult:
    """Install and start launchd service for continuous agent."""
    if not config_path.exists():
        return LaunchdResult(
            success=False,
            message=f"Agent config not found: {config_path}",
        )

    launch_agents_dir().mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    plist_path = plist_path_for_label(label)

    payload = build_plist_payload(
        label=label,
        config_path=config_path,
        working_directory=working_directory,
        stdout_log_path=logs_dir / "launchd_stdout.log",
        stderr_log_path=logs_dir / "launchd_stderr.log",
    )
    plist_path.write_bytes(plistlib.dumps(payload))

    target = launchd_service_target(label)
    run_launchctl(["bootout", launchd_domain(), str(plist_path)])

    bootstrap_result = run_launchctl(["bootstrap", launchd_domain(), str(plist_path)])
    if bootstrap_result.returncode != 0:
        stderr = (bootstrap_result.stderr or "").strip()
        return LaunchdResult(
            success=False,
            message=f"launchctl bootstrap failed: {stderr or 'unknown error'}",
        )

    run_launchctl(["enable", target])
    run_launchctl(["kickstart", "-k", target])
    return LaunchdResult(
        success=True,
        message=f"Installed and started launchd service: {label}",
    )


def uninstall_launchd_service(label: str) -> LaunchdResult:
    """Stop and remove launchd service plist."""
    plist_path = plist_path_for_label(label)
    target = launchd_service_target(label)

    run_launchctl(["bootout", launchd_domain(), str(plist_path)])
    run_launchctl(["disable", target])

    if plist_path.exists():
        plist_path.unlink()

    return LaunchdResult(
        success=True,
        message=f"Removed launchd service: {label}",
    )


def launchd_status(label: str) -> LaunchdResult:
    """Get launchd status for the service label."""
    target = launchd_service_target(label)
    result = run_launchctl(["print", target])
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        return LaunchdResult(
            success=False,
            message=f"Service not loaded ({label}). {stderr}".strip(),
        )

    output = (result.stdout or "").strip()
    return LaunchdResult(
        success=True,
        message=f"Service loaded ({label}).\n{output}",
    )

