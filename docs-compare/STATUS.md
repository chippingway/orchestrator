# Chipping Orchestrator status

This is a documentation-derived snapshot at commit `8eed5c6a0687` on 2026-09-01. The project has no native
`docs/STATUS.md`, and this page is not an independent implementation audit. It records only behavior presented as
current by the authoritative docs; `plans/` is excluded because repository guidance says it is non-authoritative.

## Build and test

The documented local gate is:

```bash
.venv/bin/python -m ruff check orchestrator tests
uv run ruff check orchestrator tests --select=I001 --fix
uv run flake8 orchestrator tests --select=WPS
.venv/bin/python -m pytest
uv build
```

CI runs lint, tests, packaging, and an isolated installed-CLI smoke check on Python 3.12 and 3.13. Separate workflows
cover dependency review, standing vulnerability audit, CodeQL, and Scorecard.

## Documented current capabilities

### Runtime and configuration

- One long-running Python polling process, plus `--once` mode and `run.sh` self-update/restart wrapper.
- Single- or multi-repository configuration with per-repo roots/base/remotes/parallel limits.
- Global/per-repo concurrency caps, duplicate-active protection, family serialization, and bounded shutdown.
- `.env`/process configuration with GitHub tokens deliberately resolved outside repository `.env`.
- Optional systemd user-service deployment.

### GitHub workflow

- Namespaced workflow-label vocabulary, legacy-label migration, strict typo guard, and configurable transition guard.
- Authenticated state-only pinned JSON comment with schema/recovery validation.
- Unlabeled pickup; decomposition into single or child work; ready/blocked/umbrella family behavior.
- Implementation, fresh-agent validation, local verify, squash, final documentation, in-review feedback, fixing, and
  conflict-resolution loops.
- Operator-applied multi-turn `question` and `discussion` conversations; discussion can publish a plan-only PR after
  explicit human confirmation.
- `backlog` and `paused` controls, trusted-comment allowlist, retry commands, typed park reasons, and human mentions.
- External merge/close finalization and manual-merge-only policy.

### Agents and workspaces

- Codex and Claude backends selectable independently for decomposer, developer, and reviewer roles.
- Full backend+args command specs, durable session locks for resumed roles, and fresh reviewer per round.
- Per-issue isolated worktrees/branches and multi-repo name collision protection.
- Secret-filtered agent and verify environments, process-group timeout/shutdown cleanup, normalized result/usage parsing.
- Hardened git reads, exact-commit/lease-pinned publication, local verification, and conservative dirty/unreadable parks.

### Late size gate

- Cumulative added-line measurement against an exact base/candidate pair before initial and subsequent PR pushes.
- Structured late adjudication (`single`, `split`, `question`) with lineage/cycle/generation evidence.
- Snapshot custom refs, idempotent child creation, PR supersession, obligation ledgers, cancellation/restart, and cleanup.
- Closed-owner checks around irreversible remote steps and preserved evidence on failures.

### Observability

- Rotating process log.
- Optional audit JSONL and default analytics JSONL with observation-only failure semantics.
- Token/cost usage parser and per-issue visible usage receipt.
- Optional skill-trigger evidence/catalog/adoption analytics.
- Optional, default-off trajectory JSONL and file-backed Streamlit viewer.
- Optional Postgres replay, materialized rollup/read model, and Streamlit analytics dashboard.

### Security and repository controls

- Comment-author trust boundary and pinned-state authentication.
- Agent/verify secret filtering and orchestrator-owned GitHub push credentials.
- Hardened local Git and custom-ref namespace checks.
- CI token minimization, SHA-pinned actions, dependency review/vulnerability scanning, CodeQL, and Scorecard.
- Documented operator checklist for 2FA, scanning, branch protection, required checks, backups, and private reporting.

## Not documented as runtime features

- local HTTP/API daemon;
- desktop or mobile application;
- terminal/browser multiplexing;
- native structured Chat UI or provider-host persistence;
- coding-agent backends other than Codex and Claude;
- remote product telemetry or PostHog;
- hosted multi-tenant control/execution plane.

## Status limits

The native docs are unusually detailed and may describe recent implementation at finer granularity than this summary.
Conversely, this page does not infer unfinished work from human `plans/` notes. A later code or issue audit is required
for roadmap/completeness claims beyond this documentation snapshot.

