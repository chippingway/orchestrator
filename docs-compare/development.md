# Development guide

How to install, test, and change Chipping Orchestrator. The repository-wide authority is
[`../AGENTS.md`](../AGENTS.md); before editing `orchestrator/`, `tests/`, or documentation, read
[`../.agents/skills/develop/SKILL.md`](../.agents/skills/develop/SKILL.md).

## Prerequisites

- Linux host for the documented runtime deployment;
- Python 3.12 or newer (CI proves 3.12 and 3.13);
- Git;
- `uv`;
- authenticated Codex and/or Claude CLIs for roles routed to them;
- a repository-scoped GitHub fine-grained PAT for live operation;
- Docker only for the optional local analytics Postgres service.

## Install

```bash
uv sync --locked
```

This creates `.venv` and installs the committed runtime/dev resolution. `uv sync --locked --no-dev` installs the
runtime-only dependency set. The optional dashboard group is separate:

```bash
uv sync --group dashboard
```

## Run

```bash
uv run python -m orchestrator --once
uv run python -m orchestrator --log-level DEBUG
./run.sh
```

Live runs use configured GitHub repositories. Prefer hermetic tests for development checks and do not point an
experimental run at production issues without intending its state changes.

## Focused and full tests

```bash
uv run pytest tests
.venv/bin/python -m pytest
```

Tests mirror the package layout. Stage tests live under the matching stage package, repository invariants under
`tests/repository/`, and shared GitHub fakes under `tests/support/github/`. Patch the module that owns the called name.

## Lint and style

```bash
.venv/bin/python -m ruff check orchestrator tests
uv run ruff check orchestrator tests --select=I001 --fix
uv run flake8 orchestrator tests --select=WPS
```

Ruff's locked default set plus `E501` is the contract. Do not narrow selectors to silence a new diagnostic. Suppression
comments name the exact rule and reason; bare/file-wide `noqa` is rejected by repository tests. Imports are sorted and
WPS rules enforce naming/complexity/ownership conventions.

## Package and smoke check

```bash
uv build
uv run --no-project --isolated --with dist/<wheel> chipping-orchestrator --help
```

CI builds sdist then wheel and launches the installed console script in an isolated environment so editable-source or
lockfile leakage cannot hide a packaging error.

## Documentation checks

Relative links and anchors across the authoritative docs, README, AGENTS guidance, and skill files are checked by the
test suite. Architecture/state/workflow docs are owner inventories and must change with moved public responsibilities.
`plans/` remains non-authoritative and untouched unless explicitly requested.

## Analytics development

The optional Postgres service is operator-owned:

```bash
cd analytics-db
docker compose up -d
```

Never traverse or modify `analytics-db/data/`; it is a protected runtime bind mount. Tests target `tests` explicitly
and do not require fixing permissions there.

## CI gate

The main workflow runs on Python 3.12 and 3.13:

- Ruff;
- WPS Flake8;
- pytest with informational coverage;
- distribution build;
- isolated wheel/console-script smoke check.

Separate workflows cover dependency review, weekly vulnerability audit, CodeQL, and OpenSSF Scorecard. Workflow
actions are pinned to full commit SHAs.

## Commit and change discipline

- Conventional subject-only commits (`feat`, `fix`, `chore`, `docs`, `refactor`, `test`).
- Keep changes surgical; do not add dependencies or speculative abstractions without an explicit ask.
- Source files carry the Apache-2.0 copyright/SPDX header described in the develop skill.
- Run `git diff --check origin/main...HEAD` before push.
- Preserve label spellings, pinned-state fields, markers, watermarks, and event shapes unless performing an explicit
  migration.

