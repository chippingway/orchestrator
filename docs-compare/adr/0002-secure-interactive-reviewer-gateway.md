# Secure interactive reviewer gateway: applicability record

- Status: no interactive reviewer gateway is documented
- Snapshot: 2026-09-01 at `8eed5c6a0687`
- Type: comparison topic, not a Chipping Orchestrator ADR

Review is a fixed workflow role executed by a fresh Codex or Claude subprocess for each round. The reviewer receives a
read-only review prompt, and the orchestrator verifies the worktree afterward; provider sandbox/approval bypass flags
mean prompt wording alone is not containment.

There is no browser/mobile interactive reviewer session, pseudoterminal gateway, relay protocol, or network-accessible
approval channel. The real security boundary is the operator-controlled host/container/VM, augmented by secret-filtered
child environments, isolated worktrees, hardened git inspection, and orchestrator-owned publication credentials.

Human review remains on GitHub. The orchestrator consumes trusted PR feedback and observes merge/close outcomes, but
does not expose a separate remote shell or merge action.

Sources: [`../../docs/workflow/roles.md`](../../docs/workflow/roles.md),
[`../../docs/architecture/platform-modules.md`](../../docs/architecture/platform-modules.md), and
[`../../docs/security.md`](../../docs/security.md).

