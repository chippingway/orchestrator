# Chipping Orchestrator documentation comparison set

This directory is a comparison-oriented description of `chipping-orchestrator`. It follows the reference-page shape
used by Agent Orchestrator (AO)—architecture, code structure, CLI, development, stack, status, SCM observation,
telemetry, environment, distribution, Cloud, harnesses, and network ADR topics—while describing Chipping Orchestrator
only. It intentionally does not compare, rank, or recommend either project.

The authoritative documentation remains [`../docs/README.md`](../docs/README.md), [`../README.md`](../README.md), and
[`../AGENTS.md`](../AGENTS.md). These pages are a normalized secondary view for a later comparison session.

## Snapshot and method

| Field | Value |
|---|---|
| Project | `chipping-orchestrator` |
| Branch | `main` |
| Source commit | `8eed5c6a0687` |
| Prepared | 2026-09-01 |
| Comparison shape | `agent-orchestrator/docs` at commit `be0fe0b322d2` |

The set was synthesized from the six authoritative documentation areas and repository guidance. A page records “not
documented” or “not applicable” when this project has no counterpart; absence is not filled with speculation.

AO source material that consists of screenshots, implementation plans/specs, or research notes is not mirrored
page-for-page. AO's historical npm/bootstrapper page and Chat UI checklist are retained here as short applicability
records because they occupy stable top-level filenames. Chipping's own `plans/` directory is explicitly
non-authoritative and was not used as implementation status.

## Reference pages

| Page | What it records about Chipping Orchestrator |
|---|---|
| [`architecture.md`](architecture.md) | polling process, GitHub-backed state, agents, worktrees, hardened git/push, observability |
| [`backend-code-structure.md`](backend-code-structure.md) | Python package ownership, layers, dependency rules, and tests |
| [`cli/README.md`](cli/README.md) | console/module/run-script entry points and the absence of a daemon-client CLI |
| [`development.md`](development.md) | Python/uv setup, checks, testing, packaging, and documentation rules |
| [`stack.md`](stack.md) | accepted runtime/tooling choices and explicit architecture consequences |
| [`STATUS.md`](STATUS.md) | documentation-derived capability snapshot, not an independent code audit |
| [`scm-observer.md`](scm-observer.md) | GitHub polling and control flow; SCM is the workflow authority, not observation-only |
| [`telemetry.md`](telemetry.md) | local JSONL/usage/trajectory observability and privacy |
| [`posthog-cost-controls.md`](posthog-cost-controls.md) | absence of PostHog plus the project's actual cost/rate controls |
| [`daemon-environment.md`](daemon-environment.md) | process-start environment, `.env`, systemd, and child filtering |
| [`ao-start-bootstrapper-and-npm-deprecation.md`](ao-start-bootstrapper-and-npm-deprecation.md) | distribution applicability; no desktop/npm bootstrapper |
| [`chat-ui-improvements-checklist.md`](chat-ui-improvements-checklist.md) | Chat UI applicability; conversations are GitHub threads |
| [`cloud-development.md`](cloud-development.md) | absence of a documented hosted control plane |
| [`cloud-refactor.md`](cloud-refactor.md) | absence of public/private Cloud shared contracts |

## Harness applicability

- [`harnesses/pi.md`](harnesses/pi.md) records that Pi is not a configured backend.
- [`harnesses/omp.md`](harnesses/omp.md) records that OMP is not a configured backend.

The supported backend selectors in the documented command-spec contract are `codex` and `claude`.

## ADR applicability

The pages under [`adr/`](adr/) preserve AO's network/reviewer/provider-host decision topics as explicit applicability
records:

- [`adr/0001-lan-listener-for-mobile.md`](adr/0001-lan-listener-for-mobile.md)
- [`adr/0002-secure-interactive-reviewer-gateway.md`](adr/0002-secure-interactive-reviewer-gateway.md)
- [`adr/0003-persistent-chat-provider-host.md`](adr/0003-persistent-chat-provider-host.md)
- [`adr/0003-unauthenticated-identity-probe.md`](adr/0003-unauthenticated-identity-probe.md)
- [`adr/0004-cloudflare-tunnel-for-remote-mobile-access.md`](adr/0004-cloudflare-tunnel-for-remote-mobile-access.md)

## Native source map

- [`../docs/architecture.md`](../docs/architecture.md) and focused [`../docs/architecture/`](../docs/architecture/)
- [`../docs/state-machine.md`](../docs/state-machine.md) and focused
  [`../docs/state-machine/`](../docs/state-machine/)
- [`../docs/workflow.md`](../docs/workflow.md) and focused [`../docs/workflow/`](../docs/workflow/)
- [`../docs/configuration.md`](../docs/configuration.md) and focused
  [`../docs/configuration/`](../docs/configuration/)
- [`../docs/observability.md`](../docs/observability.md) and focused
  [`../docs/observability/`](../docs/observability/)
- [`../docs/security.md`](../docs/security.md)
