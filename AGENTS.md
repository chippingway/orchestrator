# Repository guide for AI agents

This file is the entry point for AI coding agents (Codex, Claude, etc.) working on this repository. `CLAUDE.md` is a
symlink to this file, so both conventions resolve to the same content.

It is loaded into every agent session — keep it short. It routes to the authoritative documents; detail belongs
there, not here. Update this file only when repository-wide agent instructions, safety rules, or documentation
routing change — never to track a moved handler, helper, module, or test.

## What this project is

`agent-orchestrator` is a GitHub-Issue-driven workflow that watches issues on configured repos, drives them through a
label-based state machine, and spawns local CLI agents (`codex`, `claude`) in per-issue git worktrees to implement
them and open PRs. State lives entirely in GitHub (one workflow label + one pinned JSON comment per issue), so the
orchestrator process is stateless.

## Where the details live

- User-facing overview: [`README.md`](README.md)
- Architecture, module ownership, process / agent / push model:
  [`docs/architecture.md`](docs/architecture.md) is the entry point, with
  [`docs/architecture/platform-modules.md`](docs/architecture/platform-modules.md) for the package root,
  runtime, config, GitHub, git, agents, scheduler, and skills owners,
  [`docs/architecture/workflow-modules.md`](docs/architecture/workflow-modules.md) for the workflow package
  API, its engine owners, and the stage subpackages, and
  [`docs/architecture/observability-modules.md`](docs/architecture/observability-modules.md) for the analytics,
  usage, dashboard, and trajectory-viewer owners and the two `streamlit run` targets over them
- Workflow state machine (labels, per-tick flow, stage handlers):
  [`docs/state-machine.md`](docs/state-machine.md) is the entry point, with
  [`docs/state-machine/labels-and-state.md`](docs/state-machine/labels-and-state.md) for the label vocabulary,
  per-tick flow, and pinned-state keys,
  [`docs/state-machine/delivery-stages.md`](docs/state-machine/delivery-stages.md) for pickup through the PR
  loop, [`docs/state-machine/conversation-stages.md`](docs/state-machine/conversation-stages.md) for the
  question / discussion handlers, and [`docs/state-machine/lifecycle.md`](docs/state-machine/lifecycle.md) for
  the label-lifecycle diagram
- Agent roles, command specs, session lifecycles: [`docs/workflow.md`](docs/workflow.md) is the entry point, with
  [`docs/workflow/roles.md`](docs/workflow/roles.md) for the roles and the stages that spawn them,
  [`docs/workflow/conversations.md`](docs/workflow/conversations.md) for the question / discussion prompt and session
  contracts, and [`docs/workflow/command-specs.md`](docs/workflow/command-specs.md) for the spec grammar and the
  in-flight session lock
- Configuration / env vars: [`docs/configuration.md`](docs/configuration.md) is the reference, with
  [`docs/configuration/observability.md`](docs/configuration/observability.md) for the observability sinks and
  dashboards and [`docs/configuration/operations.md`](docs/configuration/operations.md) for CI, run modes, systemd,
  and applying `.env` changes; basic knobs in [`.env.example`](.env.example), common advanced overrides in
  [`.env.example.advanced`](.env.example.advanced)
- Observability: [`docs/observability.md`](docs/observability.md) is the entry point mapping every surface, with the
  audit and analytics JSONL sinks in [`docs/observability/event-streams.md`](docs/observability/event-streams.md),
  trajectory recording, transfer, and viewing in
  [`docs/observability/trajectories.md`](docs/observability/trajectories.md), the Postgres service, schema, and sync
  CLI in [`docs/observability/analytics-database.md`](docs/observability/analytics-database.md), the read model and
  Streamlit dashboard over it in
  [`docs/observability/analytics-dashboard.md`](docs/observability/analytics-dashboard.md), and the usage / skill /
  trajectory parsers in [`docs/observability/usage.md`](docs/observability/usage.md)
- Security checklist and operator-owned controls: [`docs/security.md`](docs/security.md)
- Development conventions and the pre-push checklist:
  [`.agents/skills/develop/SKILL.md`](.agents/skills/develop/SKILL.md)

## Repository layout

Top level only. Which module owns what is in
[`docs/architecture.md`](docs/architecture.md#top-level-layout) and the focused pages under
`docs/architecture/`, which are the single place that inventory is maintained.

- `orchestrator/` — the Python package. The root carries the version, `cli.py` (the composition point the
  `agent-orchestrator` console script calls), and `__main__.py` (the `python -m orchestrator` form over it); every
  other module lives under a subpackage named after what it owns: `workflow/` (tick loop, label dispatch, and the
  per-label stage handlers under `workflow/stages/`), `github/`, `git/`, `agents/`, `scheduler/`, `config/`,
  `skills/`, `runtime/` (the polling process), `apps/` (the `streamlit run` targets), and `observability/` (analytics
  sink, dashboards, usage parser).
- `tests/` — pytest suite, mirroring the package layout (`tests/workflow/`, `tests/github/`, `tests/git/`, …).
  In-memory GitHub doubles live in `tests/support/github/`.
- `docs/` — architecture, state-machine, workflow, configuration, observability, and security references.
- `plans/` — human working notes, not specifications (see below).
- `analytics-db/` — operator-owned local analytics database (see below).
- `run.sh` — production launcher that auto-restarts after self-modifying merges.
- `.env.example` / `.env.example.advanced` — basic and advanced configuration templates.

## Development

Read [`.agents/skills/develop/SKILL.md`](.agents/skills/develop/SKILL.md) before changing anything under
`orchestrator/`, `tests/`, or `docs/`. It carries the commands, commit format, license headers, test placement,
comment rules, and dependency policy.

The repo targets Python 3.12+ and installs from the lockfile with [`uv`](https://github.com/astral-sh/uv):

```sh
uv sync --locked                              # creates .venv/ and installs runtime + dev deps from uv.lock
uv run pytest tests                           # run the test suite
uv run python -m orchestrator --once          # one polling tick then exit
```

Tests are the primary correctness gate. Add or update tests for any behavioral change.

## Safety and compatibility

- **`analytics-db/data/` is off limits.** It is the operator-owned Docker bind mount holding the local analytics
  Postgres volume — runtime state, not source. **Never traverse, read, modify, permission-repair, delete, or re-run
  any command against it with elevated privileges.** If a tool reports it as unreadable, that is expected: target
  `tests` explicitly (the default `pytest` config already ignores the directory) rather than escalating access.
- **Workflow labels and pinned-state JSON fields are a compatibility contract.** Live issues already carry them, so a
  rename is a migration, not a refactor. The same holds for comment marker text, watermark fields, and event payload
  shapes. When touching the state machine, agent invocation, or stage handlers, read
  [`docs/state-machine.md`](docs/state-machine.md) and [`docs/workflow.md`](docs/workflow.md) first.
- **Secrets.** `GITHUB_TOKEN` is deliberately *not* loaded from `.env`. Tokens live in
  `~/.config/<owner>/<repo>/token` or the process environment. Rationale:
  [`docs/configuration.md`](docs/configuration.md#github-personal-access-token).
- **`plans/` is working notes, not spec.** Files under `plans/` (roadmap, design explorations, proposals) are
  non-authoritative. Implement what the issue asks for, do not cite a `plans/` document in code, comments, or commit
  messages, and leave those files untouched unless the issue explicitly asks you to edit one.

## Out of scope without explicit ask

- New external dependencies, frameworks, or services.
- Reformatting unrelated files or churning whitespace.
- "Future-proofing" abstractions for hypothetical features. Implement what the issue asks for and stop.
