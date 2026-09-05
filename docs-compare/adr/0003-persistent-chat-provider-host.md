# Persistent chat provider host: applicability record

- Status: not used by the documented runtime
- Snapshot: 2026-09-01 at `8eed5c6a0687`
- Type: comparison topic, not a Chipping Orchestrator ADR

Chipping Orchestrator launches transient Codex or Claude child processes when a workflow role needs them. Durable
session identifiers and pinned command specifications are stored in the authenticated GitHub state comment so a later
tick can resume a development, decomposition, question, or discussion conversation. Reviewers intentionally start
fresh each round.

No local provider host survives independently to own structured chat sessions, and no daemon/frontend chat protocol is
documented. Shutdown terminates in-flight process groups; a future tick reconstructs intent from GitHub state and the
worktree rather than reconnecting to a resident provider service.

Sources: [`../../docs/workflow/command-specs.md`](../../docs/workflow/command-specs.md),
[`../../docs/workflow/conversations.md`](../../docs/workflow/conversations.md), and
[`../../docs/state-machine/lifecycle.md`](../../docs/state-machine/lifecycle.md).

