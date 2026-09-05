# Pi harness applicability

Pi is not a documented Chipping Orchestrator agent backend. The command-spec contract accepts only `codex` and
`claude`, with independent selections for decomposition, implementation, and review.

Consequently the current docs define no Pi installation probe, authentication flow, session-resume adapter, terminal
mode, structured chat mode, or runtime capability matrix. Unknown backend selectors are configuration errors rather
than aliases.

Supporting another backend would require an explicit backend implementation that preserves the normalized result,
session, timeout/interruption, usage, environment-filtering, and process-group contracts, together with parser and
workflow tests. This page records current applicability only; it does not propose that change.

Source: [`../../docs/workflow/command-specs.md`](../../docs/workflow/command-specs.md) and
[`../../docs/workflow/roles.md`](../../docs/workflow/roles.md).

