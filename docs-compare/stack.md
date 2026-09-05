# Chipping Orchestrator technical stack

This page summarizes durable technology choices documented by the repository. Use the authoritative architecture and
configuration pages for behavior and settings.

## Principles

- Keep the runtime a stateless polling process; store workflow authority visibly in GitHub.
- Use the real Git CLI and local worktrees rather than implementing repository behavior in a library.
- Treat agent CLIs as transient subprocesses and the host/container/VM as their sandbox.
- Keep optional analytics/dashboard dependencies off the default polling path.
- Prefer explicit modules/owners and repository-enforced dependency direction over facades.

## Accepted stack

| Area | Choice | Purpose |
|---|---|---|
| language | Python 3.12+ | polling runtime and tooling |
| packaging/env | `uv`, `uv.lock`, Hatch build | reproducible install and wheel/sdist |
| GitHub client | PyGithub | issues, labels, comments, PRs, reviews, checks |
| source control | installed `git` via subprocess | worktrees, rebases, measurement, snapshots, push |
| agent backends | installed Codex and Claude CLIs | decomposition, implementation, review, conversations |
| process concurrency | `ThreadPoolExecutor` + `IssueScheduler` | cross-repo and bounded per-issue work |
| workflow store | GitHub labels + authenticated pinned JSON comment | durable restartable state |
| local logs | rotating text log + JSONL sinks | operations, audit, analytics, optional trajectories |
| analytics DB | optional PostgreSQL 16 via Docker Compose | replay/aggregation only |
| analytics driver | `psycopg[binary]` | JSONL replay and dashboard reads |
| dashboards | optional Streamlit + Plotly | analytics and trajectory viewing |
| tests | pytest + pytest-cov | behavior and repository contracts |
| lint | Ruff + wemake-python-styleguide/Flake8 | style, correctness, architecture constraints |
| service supervision | `run.sh`, optional systemd user service | self-update/restart and production lifetime |

## Dependency groups

- Runtime dependencies: PyGithub and `psycopg[binary]` as declared by the project.
- Dev group: pytest, pytest-cov, Ruff, and wemake-python-styleguide.
- Dashboard group: Streamlit and Plotly.

The dashboard group remains optional so a default `uv sync --locked` does not install UI dependencies. The driver is
imported lazily on observability paths where practical.

## Explicit architecture consequences

The documented stack does not include:

- an internal workflow database;
- an HTTP daemon or generated API client;
- Electron/React/React Native product clients;
- a distributed queue/broker;
- provider-neutral Chat/ACP controllers;
- a plugin runtime for arbitrary coding agents;
- remote product telemetry/PostHog.

These absences describe the current documented design and are not a roadmap.

## Distribution

The project builds a Python sdist/wheel and installs a `chipping-orchestrator` console script. Production operation is
the local Python process under `run.sh`/systemd, not a signed auto-updating desktop bundle.

