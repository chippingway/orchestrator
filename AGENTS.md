# Repository guide for AI agents

This file is the entry point for AI coding agents (Codex, Claude, etc.) working on this repository. `CLAUDE.md` is a
symlink to this file, so both conventions resolve to the same content.

It is loaded into every agent session — keep it short. For anything beyond a pointer, edit the linked docs instead.

## What this project is

`agent-orchestrator` is a GitHub-Issue-driven workflow that watches issues on configured repos, drives them through a
label-based state machine, and spawns local CLI agents (`codex`, `claude`) in per-issue git worktrees to implement
them and open PRs. State lives entirely in GitHub (one workflow label + one pinned JSON comment per issue), so the
orchestrator process is stateless.

- User-facing overview: [`README.md`](README.md)
- Architecture, module map, process / agent / push model: [`docs/architecture.md`](docs/architecture.md)
- Workflow state machine (labels, per-tick flow, stage handlers): [`docs/state-machine.md`](docs/state-machine.md)
- Agent roles, command specs, session lifecycles: [`docs/workflow.md`](docs/workflow.md)
- Configuration / env vars: [`docs/configuration.md`](docs/configuration.md) is the full reference; basic knobs in
  [`.env.example`](.env.example), common advanced overrides in [`.env.example.advanced`](.env.example.advanced)
- Observability (audit event log, analytics sink / database, usage parser):
  [`docs/observability.md`](docs/observability.md)
- Security checklist and operator-owned controls: [`docs/security.md`](docs/security.md)

## Repository layout

- `orchestrator/` — Python package: tick loop and label-dispatch compatibility facade (the `workflow/` package
  initializer, over the `workflow/state.py` owner -- the workflow / control label vocabularies and their wire
  strings, the strict label coercion and its legacy `value=` adapter, the declared transition graph, and the
  warn-or-raise guard plus the `orchestrator.state_machine` logger it warns through -- and over the
  `workflow/engine/comments.py` owner in the subpackage reserved for its remaining owners: the hidden
  orchestrator marker and the capped tracked-comment id ledger both posting helpers write, the
  trusted-author filter and quoting every prompt reads the issue thread through, and the capped
  tracked-repository awareness block -- and over the `workflow/engine/messages.py` owner beside it: the
  last-marker-wins review and documentation verdicts, the drift `ACK:` read, the `/orchestrator continue`
  recognition, park-reason classification, and guidance-free refusal, the Markdown blockquote every notice
  quotes through, and the redact-before-truncate stderr diagnostics a park comment and a log line
  carry -- and over the `workflow/engine/prompts.py` owner beside those: the prompt builders the stages
  share (implement, fresh-respawn preamble, review, documentation, fix, conflict resolution, question and
  its followup, PR-comment followup, decompose), the shared issue-body / conversation header and its empty
  placeholders, the foreground-only note every commit-producing prompt appends and the commit-style note
  the subject-writing subset of them adds beside it (the conflict prompt replays subjects it did not
  write, so it takes only the first) -- the single-caller drift-resume prompt stays on
  `_workflow_drift_routes.py` and borrows both -- the
  bounded conflicted-path listing, and the single-decision comment and its best-effort manifest
  fields -- and over the `workflow/engine/usage.py` owner beside them: the single tracked-run site
  every agent role spawns through, the frozen run request and the runner kwargs it forwards
  selectively, the `agent_spawn` / `agent_exit` pair around the spawn, the analytics record its exit
  appends (with the configured model read out of `extra_args` as the parser's fallback, and the
  prompt and worktree the trajectory hooks ride on), the fail-open `skill_triggered` emission that
  record's return value drives, and the UTC timestamp the stages stamp pinned state with), per-stage
  lazy facades (`stages/`),
  worktree-subsystem compatibility hub (`worktrees.py`), and the `base_sync.py`,
  `branch_publication.py`, `git_plumbing.py`, `verify.py`, `worktree_lifecycle.py`, `workflow_drift.py`, and
  `workflow_messages.py` subsystem facades. Their immutable `_export_manifest.py` inventories and `_exports.py` hooks
  route historical imports and patch points to responsibility-named private leaves (`_workflow_*`
  and stage-specific prefixes) or straight to the git-package owners -- `git/` for
  `git_plumbing.py`, `git/verification/` for `verify.py`, `git/worktrees/` for `worktree_lifecycle.py`,
  `git/publication/` for `branch_publication.py`, and `git/base_sync/` for every name `base_sync.py`
  publishes: the models, shared state, worktree refresh, rebase-eligibility gates, the PR-route coordinator
  and conflict routing, the rebase startup, publication and its guards, and
  crash-recovery probing, routing, outcomes, and persistence. The package also
  contains per-tick
  repo skill-catalog analytics (`skill_catalog.py`), lazy analytics/read and dashboard facades backed by focused
  recording, query, rendering, usage-provider, and trajectory leaves, the process-local scheduler package
  (`scheduler/`, whose `__init__.py` publishes the narrow public surface (`__all__`) -- `IssueScheduler` and
  `SubmissionRequest`, re-exported from their owners -- over the `models.py` owner (typed submissions,
  legacy-call binding, normalization) and the `service.py` owner (the concrete scheduler and its view,
  reservation, and execution layers)),
  the configuration package (`config/`, whose `__init__.py` binds each setting resolved by the `environment.py`
  `_SettingsResolver`, which draws on the `_dotenv.py` / `credentials.py` / `models.py` / `repositories.py` leaves;
  `credentials.py` also owns secret redaction -- the secret-key shapes plus the environment / configured-token
  passes every stderr, verify-output, and trajectory consumer masks with),
  the agents package (`agents/`, whose `__init__.py` is the stable runner facade over the `models.py` /
  `environment.py` / `sessions.py` / `processes.py` / `runner.py` owners -- `processes.py` owning the shared process
  registry and subprocess-group lifecycle (the facade re-exports only its `terminate_all_running`) and `runner.py`
  owning shared agent dispatch, result assembly, and spawn logging (re-exported as `run_agent`) -- and the
  per-backend command modules in the `backends/` subpackage (`backends/codex.py`, `backends/claude.py`)),
  the github package (`github/`, whose `__init__.py` publishes the narrow public surface (`__all__`) -- the composed
  `GitHubClient` and the pinned durable-state model, re-exported from their owners; every other GitHub surface is
  imported from its owner directly -- over the `client.py` owner (token resolution, PyGithub initialization, the
  composed client class, its worker-thread clone, cached label reads, and the paired audit / analytics stage-enter
  hook), the `labels.py` owner (the workflow/control label vocabulary, bootstrap specifications,
  predicates, and the label-bootstrap client mixin), the `events.py` owner (audit record construction and the
  optional JSONL sink), the `issues.py` owner (non-PR issue filtering, issue-query options, and the issue-client
  mixin: polling with the closed-issue sweep, guarded workflow-label writes, event emission, comments, and
  validated child creation), the `pinned_state.py` owner (the authenticated pinned-state model, parser, and the
  state / comment-watermark client mixin), the `pull_requests.py` owner (stateless PR status helpers plus the
  pull-request client mixin: branch/base lookup, creation, comments, open-PR iteration, labeling, retrieval,
  SHA-pinned merges, and idempotent head-branch deletion), the `reviews.py` owner (current-head review aggregation
  plus the review client mixin: approval and change-request verdicts and the unread conversation / inline / summary
  feedback watermarks), the `checks.py` owner (status / check-run normalization, failure-before-pending folding, and
  the fail-closed check-read client mixin), and the `comments.py` owner (the comment-author trust policy the git
  base-sync gates and the workflow stage leaves both filter through: the `ALLOWED_ISSUE_AUTHORS` allowlist, its
  trust-all empty default, and the case-insensitive login match that gates bots like any other
  author)), the git package (`git/`, whose `__init__.py` binds nothing so callers
  import each owner directly -- the `commands.py` owner (plain / hardened git execution plus the unsafe local
  transport probe), the `authentication.py` owner (per-repository token resolution, the askpass session and its
  detached environment, the authenticated worktree / target-root fetches, and the lease-pinned hardened push), the
  `locks.py` owner (the
  per-target-root re-entrant lock registry), the `verification/` subpackage over the `models.py` owner (the
  `VerifyResult` statuses / fields and the output budget its `output` is truncated to), the `output.py` owner
  (the redact-then-truncate pass that fills that field), the `probes.py` owner (the HEAD snapshot and the
  hardened porcelain dirty-file scan, both run through `commands.py`), the `process.py` owner (one verify
  command's process-group spawn, group kill, bounded drains, and the `VerifyResult` verdict it earns) and the
  `runner.py` owner (the HEAD snapshot, the credential-stripped child environment, and the fail-fast
  `VERIFY_COMMANDS` sequencing the validating stage calls directly, with process registration and environment
  filtering borrowed from `agents/`), the `worktrees/` subpackage, whose `__init__.py` likewise binds nothing
  over the `paths.py` owner (slug sanitization, the git-ref-safe branch segment, branch / path derivation, and
  the pinned / legacy branch resolver), the `recovery.py` owner (candidate-branch discovery and the
  unpushed-commit probes), the `creation.py` owner (the issue / PR worktree creators, their stale-worktree
  reuse, and the new-commit probe the reuse turns on), the `decomposition.py` owner (the decomposer scratch
  checkout's path, detached creation, and best-effort removal), the `cleanup.py` owner (best-effort issue-worktree
  removal and local branch deletion under the target-root lock) and the `terminal.py` owner (the question-stage
  teardown and the terminal local + remote branch cleanup composed from it), and the `publication/` subpackage, whose
  `__init__.py` also binds nothing, over the
  `probes.py` owner (the conventional / repo-local subject vocabulary and predicates, ahead/behind counts,
  first-commit and recent-base subject reads), the `titles.py` owner (subject-prefix inference from base
  history and PR-title selection), the `planning.py` owner (the pre-rewrite merge-base, HEAD, dirty-tree and
  topic-subject probes, their preparation error, and the squash message they select), the `rewrite.py` owner
  (the soft reset, the orchestrator-identity squash commit, the lease-pinned force-push, and the rollback each
  post-reset failure takes) and the `squash.py` owner (the plan-then-rewrite entry point stage handlers call),
  and the `base_sync/`
  subpackage, whose `__init__.py` binds nothing either, over the `models.py` owner (the frozen auto-rebase
  context / request / recovery-context / snapshot / decision / conflict-route dataclasses), the `state.py`
  owner (the pinned-state keys, park reasons, refresh detour labels, and the `orchestrator.base_sync` logger
  every behavioral owner binds directly), the `pre_pr.py` owner (the hardened rebase / merge probes,
  rebase-in-progress detection, and the abort-on-failure local rebase of a branch nobody has pushed), the
  `refresh.py` owner (the per-tick authenticated base fetch, worktree discovery, scheduler-claim and
  hard-skip / question / dirty-tree gates, and the per-worktree route to `pre_pr` or the PR-aware
  coordinator), the `pr.py` owner (that coordinator: the order the gate, rebase, and publication owners are
  asked in, plus the legacy keyword signature the refresh enters through), the `conflicts.py` owner (the
  once-seeded round counter, PR notice, `conflict_round` event, and `resolving_conflict` relabel a genuinely
  conflicted rebase is handed to its stage with), the `eligibility.py` owner (the refresh-driven label check
  that settles a stale recovery
  anchor, the park-reason and trusted-retry-comment decision, the open-PR read that clears an anchor a
  terminal PR left behind, the crash-recovery precedence, and the clean-tree / behind-base start
  probe), the `startup.py` owner (the pre-rebase HEAD guard, the anchor and retry unpark persisted
  before git runs, and the abort / conflict-route / park a failed rebase takes), the `publication.py` owner
  (the post-rebase HEAD and dirty checks, the lease-pinned force-push they gate, and the notice, audit event,
  `validating` route, and pinned-state write an accepted push earns), the `guards.py` owner (the no-op
  completion plus the unreadable-HEAD, dirty-tree, and failed-push parks publication hands off to), the
  `persistence.py` owner (the auto-rebase park, the shared
  reset-and-park tail, and the pinned-state / notice / audit-event writes a recovered rebase finalizes and
  routes with), the `outcomes.py` owner (the two recovery notices plus the already-published,
  unknown-comparison, diverged, dirty, and failed-push answers one verified recovery resolves into), the
  `snapshot.py` owner (the authenticated branch fetch, the local and remote head reads, the divergence
  counts, the anchor-clearing no-op exits, and the reset-and-park abort every unreadable read fails closed
  to) and the `recovery.py` owner (the order those reads and answers are asked in, the dirty-guarded
  reissued push and the finalize it earns, plus its own legacy keyword signature), with
  `git_plumbing.py`, `verify.py`,
  `worktree_lifecycle.py`, `branch_publication.py`, and
  `base_sync.py` kept as the forwarding facades for historical callers), the stable runtime-core
  facade (`main.py`), and the two root modules that forward a historical compatibility surface off a package owner
  without rebuilding any of it: `state_machine.py` over `workflow/state.py`, and `comment_trust.py` over
  `github/comments.py`.
  Full module-by-module map: [`docs/architecture.md`](docs/architecture.md#top-level-layout).
- `tests/` — pytest suite. In-memory GitHub doubles live in `tests/support/github/` and reach the still-flat workflow
  tests through the `tests/fakes.py` bridge. Stage-handler tests in
  `tests/test_workflow_<stage>*.py` (the validating stage is split across review, controls, drift, handoff, pause,
  squash, verify, and watermark modules in `tests/test_workflow_validating_*.py`, with shared fixtures in
  `tests/validating_*_test_support.py`; the in_review stage is split across
  `tests/test_workflow_in_review_*.py`; the implementing stage across
  `tests/test_workflow_implementing_*.py`, and the decomposition, question, and documenting stages across their
  respective focused modules, with shared fixtures in `tests/decomposition*_support.py`,
  `tests/question_*_support.py`, and `tests/documenting_*_support.py`; the resolving-conflict stage is split across
  `tests/test_workflow_conflicts_*.py` — infrastructure tests (`_event_emission`,
  `_list_pollable`, `_routing`) plus the `_handle_resolving_conflict` handler scenarios in focused modules
  (`_clean_rebase` for clean rebase routing, `_agent` for agent execution, `_resume` for awaiting-human resume
  paths, `_dirty` for dirty / rebase-in-progress parking, `_recovery` for recovery pushes, `_diverged` for stale /
  diverged worktree handling, `_publish` for already-rebased force-publish scenarios, `_publish_guard` for the
  publish-guard probe unit tests, `_drift` for hash-drift resume behavior), with resume fixtures in
  `tests/conflict_resume_test_support.py`); scheduler-dispatch tests are split across
  `tests/test_workflow_scheduler_*.py`,
  with subsystem-specific support in
  `tests/scheduler_routing_*.py`; other facade-level helper tests
  include (`tests/test_workflow_pickup.py`,
  `tests/test_workflow_event_emission.py`, `tests/test_workflow_agent_event_emission.py`,
  `tests/test_workflow_model_extraction.py`, `tests/test_workflow_pr_lifecycle.py`,
  `tests/test_workflow_tick_parallel.py`, `tests/test_workflow_drift.py`,
  `tests/test_workflow_backlog_routing.py`, `tests/test_workflow_question_routing.py`,
  `tests/test_workflow_documenting_routing.py`, `tests/test_workflow_fixing_routing.py`,
  `tests/test_workflow_in_review_fresh_feedback.py`, `tests/test_workflow_community_contribution.py`,
  `tests/test_workflow_stage_analytics.py`, `tests/test_workflow_finalize_pr_merged.py`,
  `tests/test_workflow_drain_terminals.py`); shared helpers in `tests/workflow_helpers.py`. Configuration-package
  tests live in `tests/config/`, agent-package owner / import-cycle tests in `tests/agents/`, and github-package
  client (construction, token resolution, worker clone, label cache), label (vocabulary, predicates, and bootstrap),
  event, issue-query, issue-client (real-client polling and child creation), pollable-listing, pinned-state,
  pull-request (status helpers, writes, merges, branch deletion), review (head verdicts, actionable summaries,
  feedback watermarks), check (surface normalization, folding, fail-closed reads), comment-trust (the empty-allowlist
  trust-all default, case-insensitive login matching, missing users, bots, and preserved input order), and
  import-cycle / layering / public-surface
  tests in `tests/github/`. Scheduler-package tests live in `tests/scheduler/`: caps and duplicate-active gating,
  tracked claims, family exclusion, cap-exempt execution, skip logging, shutdown, submission models and `submit`
  compatibility, and import-cycle / public-surface checks, with their worker, coordination, log, and shutdown
  helpers alongside. Git-package tests live in `tests/git/`: plain / hardened command envelopes and real-git
  transport probing, askpass session / environment construction and failed-fetch shaping, the authenticated
  worktree and target-root fetches, the push's lease decisions / per-repository token / transport refusals,
  target-root lock ownership, and import-cycle / package-surface checks, plus
  their shared authentication fixtures, with the verification owners covered under `tests/git/verification/` —
  result fields and statuses, HEAD and porcelain probing against a planted `core.fsmonitor`, command sequencing
  and output budgeting, child-environment stripping and redaction-before-truncation, timeout group-kill and
  bounded drains, fail-closed HEAD-baseline and fail-fast refusals, verify-time mutation detection, and
  import-cycle / layering / package-surface checks, plus the real-git verify-command fixture; the
  worktrees owners covered in `tests/git/worktrees/`: path derivation, git-ref-safe branch segments, pinned /
  legacy branch resolution, real-git unpushed-commit probes, issue / PR creation with stale-worktree reuse and
  remote-branch restoration, the new-commit probe, decomposer path / creation / removal, lock-held worktree removal
  and local branch deletion with their best-effort boundaries, question and PR-terminal teardown ordering against
  both faked plumbing and a real worktree, per-target-root
  serialization against both a blocking fake and a real bare remote, and import-cycle / package-surface checks,
  plus their path, branch-fixture, faked-plumbing, terminal, and real-git support modules (the thread scaffolding
  those serialization tests share with the authenticated-fetch one lives in
  `tests/git/concurrency_test_support.py`);
  the publication owners covered in `tests/git/publication/`: subject
  predicates, per-spec commit-subject reads, ahead/behind folding, prefix inference, PR-title selection,
  squash preparation errors and guard ordering with the message it selects, real-git subject selection and
  no-op / dirty-tree refusals, real-git commit identity, fsmonitor hardening and push-failure rollback, and
  import-cycle / package-surface checks, plus their git-double and real-repository support modules; and the
  base-sync owners
  covered in `tests/git/base_sync/`: request-to-context derivation, model defaults and frozen-ness, the
  published pinned-state keys / park reasons / detour labels / logger name, the hardened rebase and its
  conflicted-path list, rebase-state probing, the aborting pre-PR rebase, the per-tick fetch / discovery
  and the gates that end a sync early, the hard-skip controls / handler-owned label / terminal PR that end
  one worktree's sync before a rewrite, the label, park-and-trusted-retry, open-PR, recovery-precedence, and
  clean-tree eligibility decisions, a real bare remote driving the clean / no-op / conflicting / dirty
  pre-PR paths end to end, the auto-rebase park and its
  reset-and-park tail, the staged recovery state / notice / event / routing writes and the order the park and
  finalize paths publish them in, the recovery notices and the park, abort, and already-published outcomes,
  the anchor a normal rebase sets and every park clears, the abort / conflict / park routes a failed rebase
  takes, the notice / event / relabel a published clean rebase writes and the reset-and-park a rejected push
  falls to, the PR states and counters a refresh leaves untouched, a real bare remote driving the PR-route
  publish and its push-failure rollback,
  the fetch refspec / remote-head reads / divergence probing and their fail-closed exits, the order one
  comparison is routed to a single answer in and the guards the reissued push is leased behind, the recovery
  exits that cannot verify what the remote PR branch carries, real-git recovery of an unpushed rebase, a
  landed push, an out-of-band remote update, and a dirty worktree, the three ways an interrupted rebase
  reaches `validating` again, the historical keyword calls the three compatibility adapters still accept, and
  import-cycle / layering /
  package-surface checks including the guard that no flat `_base_sync_*` implementation leaf returns, plus
  their collaborator patch table, refresh fixtures and scenarios, real-git fixtures, anchor / clean / park
  assertions, and recovery-context / call-order support modules. Workflow-package tests live in
  `tests/workflow/`: the clean-process imports of the package, its `engine/` subpackage, and the `state`,
  `engine/comments.py`, `engine/messages.py`, `engine/prompts.py`, and `engine/usage.py` owners, the guard that
  importing either the facade or the state
  owner resolves no manifest target and no
  dependency binding, the package-surface checks that the facade is the
  initializer, that the engine initializer binds only the submodules planted in it, and that a submodule
  binding leaves its lazy hooks intact, and the state owner's own
  coverage — the label wire strings and their typo-guarded coercion, the transition table and its
  reachability / terminal-liveness invariants (`test_state.py`), and the per-mode guard decisions, terminal
  edges, preserved logger name, and `set_workflow_label` wiring (`test_state_guards.py`). The comment owner's
  coverage lives in `tests/workflow/engine/`: the shared id ledger both posting surfaces append to with its
  marker, idempotent wrap, and eviction cap, the allowlist filter and `@author` quoting the thread read applies,
  and the four historical facades that still forward its names (`test_comments.py`), plus the tracked-repos
  gate, listing, cap, framing, and absent secret fields (`test_comments_tracked_repos.py`). The injected-comment
  thread those filter tests share with the top-level prompt-builder and drift-hash ones lives in
  `tests/comment_trust_test_support.py`. The message owner's coverage lives beside them: the
  redact-before-truncate stderr block and log tail, the `ACK:` marker's last-wins read and its refusal of
  unmarked prose, `/orchestrator continue` recognition and bare-vs-guided classification, the retry / refuse /
  passthrough action per park reason, the refusal that consumes the command it answers, and the three
  historical facades that still forward its names (`test_messages.py`), plus the review and documentation
  marker parsers with the inline / nonfinal / punctuated variants they reject
  (`test_messages_verdicts.py`). The prompt owner's coverage sits beside those: the shared header's body /
  thread text and its empty placeholders across every builder that carries one, the repo-local commit-style
  and foreground-only notes on every commit-producing prompt (the conflict prompt authors no subject, so it
  carries only the second), the conflicted-path listing and its capped remainder, the empty reviewer-feedback
  fallback, and the three historical facades that still forward its names (`test_prompts.py`), plus the
  documentation prompt's own marker / diff-target / `plans/`-exclusion contract
  (`test_prompts_documentation.py`). The tracked-run owner's coverage closes the directory: the single
  analytics record a stage-driven run appends, its context / exit / usage fields and the prompt, stdout,
  stderr, and secrets it must not carry (`test_usage.py`), the configured-model fallback filling only a
  stream that omitted its own model (`test_usage_fallback.py`), the one-per-distinct-skill emission with
  its default-off gate, args privacy, and fail-open guard (`test_usage_skills.py`), the opt-in trajectory
  record and the pinned-off sink it must not write (`test_usage_trajectory.py`), and the `UsageMetrics`
  surfaced on the returned result (`test_usage_metrics.py`), with the wire payloads and issue numbers all
  five share in `tests/workflow/engine/usage_test_support.py`.
- `docs/` — architecture, workflow, and configuration references.
- `run.sh` — production launcher that auto-restarts after self-modifying merges.
- `.env.example` / `.env.example.advanced` — basic and advanced configuration templates; full reference is in
  [`docs/configuration.md`](docs/configuration.md).

## Running and testing

The repo targets Python 3.12+. Local development uses [`uv`](https://github.com/astral-sh/uv) and installs from the
lockfile.

```sh
uv sync --locked                              # creates .venv/ and installs runtime + dev deps from uv.lock
uv run ruff check orchestrator tests          # run Ruff
uv run flake8 orchestrator tests --select=WPS # run wemake-python-styleguide
uv run pytest tests                           # run the test suite
uv run python -m orchestrator.main --once     # one polling tick then exit
uv run python -m orchestrator.main --log-level DEBUG
```

`analytics-db/data/` is the operator-owned Docker bind mount holding the local analytics Postgres volume. It is
runtime state, not source: **never traverse, read, modify, permission-repair, delete, or re-run any command against it
with elevated privileges.** If a tool reports it as unreadable, that is expected — target `tests` explicitly (the
default `pytest` config already ignores the directory) rather than escalating access.

Dev tools (`pytest`, `ruff`, and `wemake-python-styleguide`, which supplies the WPS Flake8 plugin) live in the `dev`
dependency group in `pyproject.toml`; exact versions are pinned in `uv.lock`. CI installs the same set via
`uv sync --locked`.

Tests are the primary correctness gate. Add or update tests for any behavioral change. Prefer extending the in-memory
fakes in `tests/support/github/` over mocking PyGithub directly.

## Code conventions

- **License headers.** Every source file (`*.py`, `*.sh`, `pyproject.toml`) starts with:
  ```
  # Copyright 2026 Geser Dugarov
  # SPDX-License-Identifier: Apache-2.0
  ```
- **Commits.** Conventional Commits: `<type>: <subject>` with types `feat`, `fix`, `chore`, `docs`, `refactor`,
  `test`. Subject line only — no body, no `Co-Authored-By` trailer. Imperative mood, short.
- **Comments.** Sparse — only when the *why* is non-obvious (hidden constraint, race window, GitHub quirk).
- **Dependencies.** `pyproject.toml` pins `PyGithub` and `psycopg[binary]` as runtime deps; `pytest`, `ruff`, and
  `wemake-python-styleguide` live in the `dev` group; the analytics dashboard's `streamlit` and `plotly` live in the
  separate `dashboard` group so the default `uv sync --locked` stays minimal. `uv.lock` is the source of truth for
  exact versions and is committed — regenerate it (`uv lock`) whenever `pyproject.toml` changes. Anything else needs
  justification.
- **Secrets.** `GITHUB_TOKEN` is deliberately *not* loaded from `.env`. Tokens live in
  `~/.config/<owner>/<repo>/token` or the process environment. Rationale:
  [`docs/configuration.md#github-pat`](docs/configuration.md#github-pat).

## Out of scope without explicit ask

- New external dependencies, frameworks, or services.
- Reformatting unrelated files or churning whitespace.
- "Future-proofing" abstractions for hypothetical features. Implement what the issue asks for and stop.

When touching the state machine, agent invocation, or stage handlers, read
[`docs/state-machine.md`](docs/state-machine.md) and [`docs/workflow.md`](docs/workflow.md) first — labels and the
pinned-state JSON schema are part of the public contract that live issues already carry.
