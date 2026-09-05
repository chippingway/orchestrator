# Chipping Orchestrator CLI

The primary CLI starts the polling process itself. It is not a thin client of an already running HTTP daemon and does
not expose project/session CRUD commands.

Sources: [`../../README.md`](../../README.md) and
[`../../docs/configuration/operations.md`](../../docs/configuration/operations.md).

## Entry points

| Command | Purpose |
|---|---|
| `chipping-orchestrator` | installed console-script entry point to `orchestrator.cli:main` |
| `python -m orchestrator` | module launch form over the same `main` |
| `./run.sh` | production wrapper with self-update/restart behavior |
| `python -m orchestrator --once` | execute one polling tick and exit after draining |
| `python -m orchestrator --log-level DEBUG` | start with verbose process logging |
| `chipping-orchestrator --help` | print the installed CLI surface; used by the wheel smoke test |

`--once` is useful for development, cron-like driving, and deterministic smoke checks. Normal production operation is
the long-running loop under `run.sh` or a systemd user service.

## What the CLI composes

Startup loads validated settings, resolves one GitHub client per repository, ensures/migrates workflow labels, creates
one shared scheduler, configures logs, then starts the one-shot or recurring loop. It does not open a local API port or
write an endpoint discovery file.

## Configuration

Configuration comes from the process environment and non-secret values in `.env`. `GITHUB_TOKEN` is intentionally not
loaded from `.env`; it is resolved from the launch environment or the configured external token file. See
[`../../docs/configuration.md`](../../docs/configuration.md).

## Secondary module commands

These are separate operator tools, not subcommands of the primary console script:

```bash
uv run python -m orchestrator.observability.analytics.sync.cli
uv run streamlit run orchestrator/apps/analytics_dashboard.py
uv run streamlit run orchestrator/apps/trajectory_dashboard.py
```

The sync replays analytics JSONL into optional Postgres. The Streamlit apps are read-only dashboards and do not launch
or control the polling loop.

## Manual smoke test

```bash
uv sync --locked
uv run python -m orchestrator --once
uv run chipping-orchestrator --help
```

The one-tick command reaches the configured GitHub repositories and is therefore an operator/integration action, not a
hermetic unit test. Use the pytest suite and in-memory GitHub doubles for development tests.

## Adding CLI behavior

Keep `cli.py` as the composition point. Workflow decisions belong to workflow owners; GitHub/git/agent behavior
belongs to their domain owners; process loop/shutdown behavior belongs under `runtime/`. A new operator-only tool with
a different dependency surface can use a focused `python -m` entry point, as analytics sync does, instead of growing
the polling CLI into a multi-product command tree.

