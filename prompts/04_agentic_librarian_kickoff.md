# Agentic Librarian Kickoff Prompt

Use this to run continuous document/folder organization with safety controls.

---

Goal:
Operate a continuous organizer agent over `{base_path}` that improves findability
by context, age, and project affinity while preserving safety.

Requirements:
- Queue-first actions (reviewable proposals).
- No destructive file deletion by default.
- Keep rollback/audit logs for all moves.
- Learn project identity and canonical homes over time.

Policy:
1. Classify actions:
   - keep
   - review
   - move
   - prune-empty (policy-based only)
2. Respect protected/system paths:
   - `.git`, hidden/system directories, configured keep paths.
3. Use confidence thresholds:
   - auto-execute only high-confidence actions.

Tasks:
- Ensure service is deployed/running.
- Generate one cycle and summarize proposals.
- Highlight ambiguous items requiring manual policy decisions.
- Update policy files from approved decisions.

Output:
- Current service status
- Proposed actions summary
- High-risk/low-confidence items
- Recommended approvals for next cycle
