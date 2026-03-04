# Continuous Organizer Agent

This project now includes a long-running organizer agent that can continuously:

- scan your target folder tree
- create context-aware consolidation plans
- write pending actions to a queue for review
- optionally auto-execute only high-confidence groups

Use `python3` for commands in this document (some macOS systems still map
`python` to Python 2).

## Why this exists

Manual waves are useful for one-time cleanup, but your request is an always-on
"librarian" agent. This gives you persistent operation with logs, queueing, and
config-driven behavior.

## Commands

Create config once:

```bash
python -m organizer --agent-init-config --path "/absolute/or/root/path"
```

Run one cycle (safe check):

```bash
python -m organizer --agent-once --agent-config ".organizer/agent_config.json"
```

Run continuously:

```bash
python -m organizer --agent-run --agent-config ".organizer/agent_config.json"
```

Run continuously for a fixed number of cycles:

```bash
python -m organizer --agent-run --agent-max-cycles 3
```

## macOS launchd (auto-run after login)

Install and start the background service:

```bash
python -m organizer --agent-launchd-install --agent-config ".organizer/agent_config.json"
```

Check service status:

```bash
python -m organizer --agent-launchd-status
```

Uninstall service:

```bash
python -m organizer --agent-launchd-uninstall
```

Optional custom label:

```bash
python -m organizer --agent-launchd-install --agent-launchd-label "com.yourname.organizer.agent"
```

## Config

Config file defaults to `.organizer/agent_config.json`.

Key fields:

- `base_path`: root to organize
- `interval_seconds`: scan interval for continuous mode
- `content_aware`: use DB-backed contextual analysis
- `db_path`: SQLite path for metadata analysis
- `auto_execute`: if `false`, queue only; if `true`, execute high-confidence groups
- `min_auto_confidence`: confidence gate for auto-execution
- `project_homing_enabled`: enable root-project rehoming suggestions
- `project_homing_roots`: where project clusters normally live
- `project_homing_min_confidence`: confidence score for homing proposals
- `project_learning_file`: persistent memory of learned project homes
- `empty_folder_policy_file`: policy file for `keep/review/prune` empty-folder decisions

## Outputs

The agent writes:

- plans: `.organizer/agent/plans/plan_*.json`
- pending queue: `.organizer/agent/queue/pending_*.json`
- cycle logs: `.organizer/agent/logs/cycle_*.json`
- state: `.organizer/agent/state.json`

## Safety model

- Uses existing move operations only.
- Does not delete files.
- Defaults to `auto_execute: false` so you can review queue outputs first.

## Learned behavior: project homing

The agent now includes a "project homing" rule for root-level strays:

- Detects root folders that look like project/version snapshots
- Learns and persists canonical project homes (for example `LEOPard`)
- Matches future strays/files by learned project key + existing collateral context
- Proposes a move into that exact project home neighborhood (queue-first by default)

## Empty folder policy

The agent now classifies empties into:

- `keep` (intentional placeholders or allowlisted paths)
- `review` (looks workflow-related)
- `prune` (unintentional empty folders)

Default policy is auto-created at:

- `.organizer/agent/empty_folder_policy.json`

This keeps intentional VA placeholder folders while flagging other empties for prune actions in the queue.

## Runbook: agent ops from UI

The dashboard includes an **Agents** page at `/agents` for managing the
continuous organizer agent without touching the terminal.

### Viewing status

Navigate to the Agents page. Each registered agent shows:

- Live status badge (running / idle / stopped / error / unknown)
- Total cycles completed
- Last cycle timestamp and outcome
- Configured scan interval
- Last cycle summary: groups, proposals, moves, failures, empty-folder
  decisions

Status auto-refreshes every 15 seconds.

### Manual trigger

Click **Run Now** to execute a single agent cycle immediately. This calls
`POST /api/agents` with action `run-once`, which runs
`python3 -m organizer --agent-once` under the hood.

### Start / Stop / Restart

Use the **Start**, **Stop**, and **Restart** buttons to control the launchd
service. These call `launchctl start|stop` on the
`com.prdtool.organizer` service label.

### Audit

Click **Audit Running Agents** to discover:

- All `com.prdtool.*` launchd services (not just the ones we expect)
- Running `python3 -m organizer` processes with PID, CPU, and memory
- Warnings for unexpected services or missing expected ones
- An overall health badge

### API reference

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/agents?basePath=...` | GET | List agents with status |
| `/api/agents` | POST | Control agent (body: `{basePath, agentId, action}`) |
| `/api/agents/audit` | GET | System-wide agent audit |

Actions for POST: `run-once`, `start`, `stop`, `restart`.
