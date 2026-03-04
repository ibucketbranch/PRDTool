"""Tests for continuous organizer agent project-homing behavior."""

import json
from pathlib import Path

from organizer.continuous_agent import ContinuousAgentConfig, ContinuousOrganizerAgent


def test_project_key_normalizes_versions() -> None:
    """Project keys should collapse version/date variants to same identifier."""
    config = ContinuousAgentConfig(base_path=".")
    agent = ContinuousOrganizerAgent(config)

    assert agent._project_key("1LEOPardv3-Latest") == "leopard"
    assert agent._project_key("LEOPard") == "leopard"


def test_project_homing_proposes_root_move(tmp_path: Path) -> None:
    """A root project folder should be proposed into project cluster path."""
    base = tmp_path / "root"
    projects_bin = base / "Projcts Bin"
    leopard_cluster = projects_bin / "LEOPard"
    root_variant = base / "1LEOPardv3-Latest"

    leopard_cluster.mkdir(parents=True)
    root_variant.mkdir(parents=True)
    (root_variant / "example.txt").write_text("sample", encoding="utf-8")

    config = ContinuousAgentConfig(
        base_path=str(base),
        project_homing_roots=["Projcts Bin"],
    )
    agent = ContinuousOrganizerAgent(config)
    actions = agent._build_project_homing_actions("cycle123")

    assert actions
    assert actions[0].source_folder == str(root_variant.resolve())
    assert actions[0].target_folder == str(
        (leopard_cluster / root_variant.name).resolve()
    )


def test_project_learning_file_is_written(tmp_path: Path) -> None:
    """Project learning memory should persist canonical home after scan."""
    base = tmp_path / "root"
    projects_bin = base / "Projcts Bin"
    leopard_cluster = projects_bin / "LEOPard"
    root_variant = base / "1LEOPardv3-Latest"
    learning_file = tmp_path / "agent" / "project_learning.json"

    leopard_cluster.mkdir(parents=True)
    root_variant.mkdir(parents=True)
    (root_variant / "example.txt").write_text("sample", encoding="utf-8")

    config = ContinuousAgentConfig(
        base_path=str(base),
        project_homing_roots=["Projcts Bin"],
        project_learning_file=str(learning_file),
    )
    agent = ContinuousOrganizerAgent(config)
    _ = agent._build_project_homing_actions("cycle123")

    assert learning_file.exists()
    payload = learning_file.read_text(encoding="utf-8")
    assert "leopard" in payload
    assert str(leopard_cluster.resolve()) in payload


def test_empty_folder_policy_classifies_prune(tmp_path: Path) -> None:
    """Empty folder outside keep policy should produce prune action."""
    base = tmp_path / "root"
    (base / "RandomEmpty").mkdir(parents=True)

    config = ContinuousAgentConfig(
        base_path=str(base),
        empty_folder_policy_file=str(tmp_path / "agent" / "empty_folder_policy.json"),
    )
    agent = ContinuousOrganizerAgent(config)

    summary = agent._evaluate_empty_folders("cycle123")

    assert summary["prune_count"] == 1
    assert summary["review_count"] == 0
    assert summary["actions"]
    assert summary["actions"][0].action_type == "prune_empty_dir"


def test_empty_folder_policy_keeps_va_placeholders(tmp_path: Path) -> None:
    """Default policy should keep empty VA placeholder folders."""
    base = tmp_path / "root"
    (base / "VA/06_Benefits_and_Payments").mkdir(parents=True)

    config = ContinuousAgentConfig(
        base_path=str(base),
        empty_folder_policy_file=str(tmp_path / "agent" / "empty_folder_policy.json"),
    )
    agent = ContinuousOrganizerAgent(config)

    summary = agent._evaluate_empty_folders("cycle123")

    assert summary["kept_count"] == 1
    assert summary["prune_count"] == 0


def test_inbox_proposals_appear_in_queue(tmp_path: Path) -> None:
    """Inbox routings should be converted to ProposedActions and appear in the queue."""
    base = tmp_path / "root"
    inbox = base / "In-Box"
    inbox.mkdir(parents=True)
    (inbox / "resume.pdf").write_text("sample", encoding="utf-8")
    (base / "Personal Bin" / "Resumes").mkdir(parents=True)

    config = ContinuousAgentConfig(
        base_path=str(base),
        inbox_enabled=True,
        inbox_folder_name="In-Box",
        auto_execute=False,
        project_homing_enabled=False,
        queue_dir=str(tmp_path / "queue"),
        plans_dir=str(tmp_path / "plans"),
        logs_dir=str(tmp_path / "logs"),
        state_file=str(tmp_path / "agent" / "state.json"),
        empty_folder_policy_file=str(tmp_path / "agent" / "empty_folder_policy.json"),
    )
    agent = ContinuousOrganizerAgent(config)
    cycle_summary = agent.run_cycle()

    assert cycle_summary["inbox"]["enabled"] is True
    assert cycle_summary["inbox"]["total_files"] == 1
    assert cycle_summary["inbox"]["queue_count"] >= 1
    assert "inbox" in cycle_summary

    queue_path = list(Path(config.queue_dir).glob("pending_*.json"))
    assert queue_path
    queue_data = json.loads(queue_path[0].read_text(encoding="utf-8"))
    inbox_actions = [
        a for a in queue_data["actions"]
        if a.get("action_type") == "inbox_file_move"
    ]
    assert len(inbox_actions) >= 1
    assert inbox_actions[0]["group_name"] == "inbox_file_move"
