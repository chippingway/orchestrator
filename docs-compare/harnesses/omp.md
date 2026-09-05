# OMP harness applicability

Open Multi-Provider (OMP) is not a documented Chipping Orchestrator agent backend. The configured command-spec
selectors are `codex` and `claude`; any provider-specific trailing arguments are pinned as part of the selected role's
durable command specification.

The current project therefore has no OMP binary discovery, authentication probe, ACP adapter, TUI/Chat distinction,
or provider-host lifecycle. Agent calls are transient child processes normalized by the Codex and Claude backend
implementations.

Adding OMP would require an explicit adapter that meets the existing session, result, timeout, usage, secret-filtering,
and shutdown contracts plus configuration and workflow coverage. This is an applicability record, not a roadmap item.

Source: [`../../docs/workflow/command-specs.md`](../../docs/workflow/command-specs.md) and
[`../../docs/architecture/platform-modules.md`](../../docs/architecture/platform-modules.md).

