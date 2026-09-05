# chipping-orchestrator — Roadmap

## Status as of 2026-09-05

The current tree declares version 0.11.1. The fixed delivery lifecycle is
wired end-to-end: pickup →
`workflow:decomposing` → `workflow:ready` / `workflow:blocked` /
`workflow:umbrella` → `workflow:implementing` → `workflow:validating` →
`workflow:documenting` (final-docs handoff) → `in_review` → terminal
`done` / `rejected`, with `workflow:fixing` and
`workflow:resolving_conflict` as the review-side loops back to
`workflow:validating`. The operator-applied `question` and `discussion`
labels provide read-only Q&A and design-conversation side branches; a
confirmed discussion publishes a plan PR. The `backlog` and `paused`
control labels hold fresh or in-flight work without changing the workflow
state. With the default `DECOMPOSE=on`, every new committed candidate is
measured against `MAX_ADDED_LINES` before its first publication and again,
cumulatively, before every later push onto its PR. Oversized work returns
to `workflow:decomposing` for a resumable single-or-split adjudication that
preserves and reuses the committed candidate rather than throwing it away;
turning decomposition off does not bypass a generation already recorded.

The orchestrator runs as a single long-lived Python process through
`chipping-orchestrator` or `python -m orchestrator`, with `run.sh` wrapping
it for self-restart. It polls one or more configured repos and delegates
coding to `codex` /
`claude` CLI subprocesses in per-issue git worktrees. State lives in
GitHub Issues themselves (one workflow label plus one pinned JSON
comment), so the loop stays stateless and progress is observable on
github.com. Per-repo ticks fan out concurrently; per-issue handlers
within each repo run in parallel up to configurable caps. A durable
per-issue circuit limits lifetime agent-process starts, and a host-wide
maintenance pass reclaims proven-safe terminal worktrees and branches on a
daily interval or on demand.

The observability stack is also in place: audit events, analytics JSONL
with Postgres rollups, repo skill catalogs, session-aware skill adoption
with confirmed / inferred / incidental evidence, the Streamlit analytics
dashboard, and an opt-in file-backed trajectory sink and viewer for
redacted agent run timelines. Agent token / cost usage is captured both
as run-level analytics and as per-issue pinned counters that produce a
terminal receipt comment. Both event streams also carry the late-size and
agent-run-budget transitions; terminal artifact cleanup contributes one
bounded analytics record per candidate it decides about.

For the authoritative behavior, see:

- [`docs/architecture.md`](../docs/architecture.md) — design, module
  map, process / agent / push model.
- [`docs/state-machine.md`](../docs/state-machine.md) — label set,
  per-tick flow, stage-handler semantics, pinned-state schema, label
  lifecycle diagram.
- [`docs/workflow.md`](../docs/workflow.md) — agent roles, command
  specs, session lifecycles.
- [`docs/observability.md`](../docs/observability.md) — audit event
  log, analytics and trajectory sinks, database, dashboards, usage
  parser.
- [`docs/configuration.md`](../docs/configuration.md) — env vars and
  knobs.
- [`docs/security.md`](../docs/security.md) — operator-owned controls.

This file tracks what shipped and what is still open.

## Shipped

The orchestrator is feature-complete against its original scope. Each
shipped area below is a one-line pointer; behavior details live in the
linked docs.

- **Bootstrap and process model.** Canonical `chipping-orchestrator` and
  `python -m orchestrator` launch forms, polling loop with `--once` and
  `--cleanup-terminal-artifacts`, signal-clean shutdown,
  ancestry-aware self-update detection, and the `run.sh` self-restart
  wrapper. See
  [`docs/architecture.md#process-model`](../docs/architecture.md#process-model).
- **Agent invocation.** `agents.run_agent` dispatches to `codex` /
  `claude`; `DEV_AGENT` / `REVIEW_AGENT` / `DECOMPOSE_AGENT` specs are
  pinned per issue and re-parsed on every resume. See
  [`docs/workflow.md`](../docs/workflow.md).
- **Lifetime agent-run circuit.** Every agent-process start is charged
  durably before invocation against `MAX_AGENT_RUNS_PER_ISSUE`; the
  dispatcher holds an exhausted issue on `agent_run_limit`, and a trusted
  `/orchestrator add-agent-runs N` can extend that issue's allowance.
  Reservation, start, exhaustion, and extension transitions reach both
  observability sinks. See
  [`docs/security.md#bounded-agent-spend-per-issue-max_agent_runs_per_issue`][agent-run-circuit].
- **Security hardening.** Agent and verify-command env strip GitHub
  tokens and secret-shaped vars; provider keys are exact-name
  allowlisted for agent subprocesses only; authenticated git operations
  reject repo-local proxy / TLS overrides; `git push` runs under a
  neutered git-config envelope with a stamped commit identity. Pinned
  state is accepted only from the token-backed account in a state-only
  comment, while `ALLOWED_ISSUE_AUTHORS` can exclude untrusted comments
  from prompts, drift, resumes, and PR-feedback routing. See
  [`docs/security.md`](../docs/security.md).
- **Stage handlers.** Per-stage flow, drift detection, the final-docs
  handoff, manual-merge-only HITL ping, the two `fixing` routes
  (in_review→fixing PR-feedback and validating→fixing
  CHANGES_REQUESTED), the conflict-only `resolving_conflict` route,
  `/orchestrator continue` retry / replay / refusal semantics across
  parked developer paths, and the read-only `question` side branch all
  live under `orchestrator/workflow/stages/`. See
  [`docs/state-machine.md#stage-handlers`](../docs/state-machine.md#stage-handlers).
- **Candidate size gate and automatic late splitting.** With the default
  `DECOMPOSE=on`, `MAX_ADDED_LINES` measures the exact committed candidate
  before first publication and the cumulative PR before every later push;
  switching decomposition off retains unmeasured publication only for new
  work. Oversized work is frozen and adjudicated under
  `workflow:decomposing`: a `single` verdict publishes it under a recorded
  exemption, while a `split` verdict preserves it on immutable refs and
  creates children that reuse the contribution. Equivalent squash and
  clean-rebase rewrites transfer the exemption instead of forcing another
  verdict; durable generation records recover interrupted publication and
  closed-owner cancellation. See
  [`docs/workflow/roles.md#the-size-gate-a-committed-candidate-passes`][size-gate].
- **Control labels.** `backlog` keeps not-yet work out of dispatch;
  `paused` freezes in-flight work across dispatch, base sync, and fresh
  post-agent checks without discarding durable state; and, when
  `ALLOWED_ISSUE_AUTHORS` is configured, `community_contribution` flags
  non-allowlisted PR authors for human review under the wire label
  `workflow:community_contribution`. See
  [`docs/state-machine.md#workflow-labels`](../docs/state-machine.md#workflow-labels).
- **Discussion lifecycle.** The operator-applied `discussion` label runs
  a resumable decomposer-led architecture conversation, publishes a
  confirmed `plans/issue-<number>.md` as a plan PR, and finalizes the
  issue from that PR's outcome without spawning an implementer. See
  [`docs/workflow.md#discussion-stage--architecture-discussion-on-the-discussion-label`](../docs/workflow.md#discussion-stage--architecture-discussion-on-the-discussion-label).
- **Typed, namespaced state machine.** `WorkflowLabel` / `ControlLabel`
  enums in `orchestrator/workflow/state.py`, with a typo guard and a
  configurable transition guard at the single label-write chokepoint.
  Orchestrator-owned wire labels use the `workflow:` namespace, and the
  startup bootstrap migrates legacy bare spellings while the read paths
  remain compatible with live issues that still carry them. See
  [`docs/state-machine.md#typed-states-and-the-transition-guard`][typed-states].
- **Multi-repo support.** `REPOS` drives per-repo fan-out across a
  `ThreadPoolExecutor` with per-repo exception isolation; worktrees are
  slug-namespaced. See
  [`docs/architecture.md#per-tick-flow-workflowtick`](../docs/architecture.md#per-tick-flow-workflowtick).
- **Tracked-repos awareness.** Working-agent reasoning prompts carry a
  compact read-only block listing the *other* repos this orchestrator
  tracks (slug, local `target_root`, base branch), gated on
  `EXPOSE_TRACKED_REPOS` and inert for single-repo hosts. See
  [`docs/workflow.md`](../docs/workflow.md#tracked-repos-awareness-in-working-agent-prompts)
  and [`docs/security.md`](../docs/security.md#cross-repo-awareness-disclosure-expose_tracked_repos).
- **Parallel issue processing.** `MAX_PARALLEL_ISSUES_PER_REPO` and
  `MAX_PARALLEL_ISSUES_GLOBAL` bound concurrency; a long-lived
  `IssueScheduler` enforces the in-flight set, per-repo counter,
  family mutex, and duplicate-active gate. Family-aware buckets drain
  on a single worker; no-agent buckets (`blocked` / `umbrella`) run
  cap-exempt on a dedicated pool. See
  [`docs/architecture.md#per-tick-flow-workflowtick`](../docs/architecture.md#per-tick-flow-workflowtick)
  and [`orchestrator/scheduler/service.py`](../orchestrator/scheduler/service.py).
- **Terminal artifact reclamation.** A daily or on-demand maintenance
  pass discovers current, legacy, local, and remote-only per-issue
  worktrees and branches, then removes only artifacts whose terminal
  ownership, commit survival, clean checkout, quiet period, and lack of
  active PRs are all proved. Scheduler admission barriers, a host lock,
  tip rechecks, and leased ref deletion make ambiguous evidence retain the
  candidate. See
  [`docs/configuration/operations.md#reclaiming-a-finished-issues-artifacts`][artifact-reclamation].
- **Responsibility-owned package layout.** The former flat production and
  test trees are split into domain packages with narrow explicit APIs,
  responsibility-named owners, mirrored tests, and repository checks for
  package layout, import direction, and public exports. The temporary
  compatibility manifests and forwarding modules used during the move
  have been removed. See
  [`docs/architecture.md#top-level-layout`](../docs/architecture.md#top-level-layout).
- **Tests.** Large suites are split into focused per-behavior modules
  with subsystem-specific support harnesses; reusable GitHub behavior
  stays in the in-memory fakes under `tests/support/github/`, reached
  through `tests/support/fakes.py`. See
  [`CLAUDE.md`](../CLAUDE.md).
- **Project CI and supply-chain checks.** Read-only CI runs Ruff,
  WPS-focused Flake8, pytest with coverage, an sdist / wheel build, and an
  isolated installed-console smoke test on Python 3.12 and 3.13. Workflow
  actions are SHA-pinned; dependency review, CodeQL, OpenSSF Scorecard,
  and a weekly whole-lockfile vulnerability scan complement Dependabot's
  cooled update PRs. See
  [`docs/configuration/operations.md#continuous-integration`][continuous-integration]
  and [`SECURITY.md`](../SECURITY.md).
- **Audit event log.** Optional opt-in JSONL sink at `EVENT_LOG_PATH`,
  one record per workflow event, including the late-size and agent-run
  budget families plus opt-in `skill_triggered` events when
  `TRACK_SKILL_TRIGGERS` is enabled. See
  [`docs/observability.md#audit-event-log-event_log_path`](../docs/observability.md#audit-event-log-event_log_path).
- **Analytics sink, database, and dashboard.** JSONL sink at
  `ANALYTICS_LOG_PATH` plus an operator-deployed Postgres aggregation
  target (`analytics-db/`), an operator-driven sync CLI
  (`python -m orchestrator.observability.analytics.sync.cli`), a read
  model under `orchestrator/observability/analytics/query/`, and the
  `orchestrator/apps/analytics_dashboard.py` Streamlit app. Records
  include stage evaluations, agent exits, repo skill catalogs, opt-in
  skill-observation fields, logical-session adoption, invocation-level
  trigger diagnostics, late-size and agent-run budget transitions, and
  terminal-artifact cleanup outcomes. See
  [`docs/observability.md`](../docs/observability.md).
- **Trajectory sink and viewer.** Opt-in `TRAJECTORY_LOG_PATH` records
  redacted, head/tail-truncated `agent_trajectory` JSONL records for
  tracked agent runs; the read and rendering owners under
  `orchestrator/observability/trajectory_viewer/` are composed by
  `orchestrator/apps/trajectory_dashboard.py`, separate from Postgres and
  the analytics dashboard. See
  [`docs/observability.md#trajectory-sink-trajectory_log_path`][trajectory-sink].
- **Agent usage / cost parser.** `orchestrator/observability/usage/`
  decodes JSONL agent stdout into a `UsageMetrics` dataclass;
  CLI-reported cost wins, otherwise a baked-in price table estimates and
  unknown SKUs yield `unknown-price`. The same package parses agent
  trajectories and distinguishes confirmed Claude skill loads, inferred
  direct Codex `SKILL.md` reads, and incidental path references. See
  [`docs/observability.md#usage-parser-orchestratorobservabilityusage`](../docs/observability.md#usage-parser-orchestratorobservabilityusage).
- **Per-issue usage receipts.** Developer, reviewer, decomposer, and
  question / discussion runs fold parsed `UsageMetrics` into pinned-state
  `issue_agent_runs` / `issue_total_tokens` / `issue_total_cost_usd` /
  `issue_cost_sources` counters; terminal done / rejected / closed
  routes surface those counters as a visible receipt comment. See
  [`docs/state-machine.md#pinned-state`](../docs/state-machine.md#pinned-state)
  and
  [`docs/observability.md#usage-parser-orchestratorobservabilityusage`](../docs/observability.md#usage-parser-orchestratorobservabilityusage).

## Future work

Open as of 2026-09-05. The first five entries have no implementation or
public configuration surface yet; expand one into a design document only
when it is picked up. The final item is an existing compatibility cleanup
whose dated removal note has elapsed.

- **Spec-first split.** Insert a `specifying` stage between `ready` and
  `implementing` so a separate spec agent writes failing tests first
  (scoped to test paths) and the orchestrator verifies they fail
  against `origin/<base>` before the implementer runs. Add a
  `spec_skip: true` opt-out to the decomposer manifest for docs /
  refactor work that cannot be expressed as failing tests.
- **Repo memory across issues.** Add a per-target-repo
  `<target_root>/.agent-orchestrator/repo-memory.json` (schema_version,
  verify_commands, top touched files, capped recent failures) updated
  best-effort on merge and folded into decomposer / implementer
  prompts with strict caps. Treat as orchestrator-owned context, not
  PR content.
- **Container / VM isolation + GitHub App migration.** Container or VM
  isolation around the orchestrator host remains an open deployment
  question (the host is currently the real sandbox boundary). Migrate
  from per-repo PATs to a GitHub App installation token.
- **Architectural review at `validating`.** Optional reviewer pass that
  flags structural issues (oversized files, layering violations) that
  the correctness reviewer ignores.
- **Symphony-inspired hooks and policy overrides.** Narrow
  `<target_root>/.agent-orchestrator/policy.toml` overrides (verify
  commands, retry / review-round budgets) with hot-reload, plus three
  workspace lifecycle hooks (`after_create`, `before_run`,
  `after_run`) under `<target_root>/.agent-orchestrator/hooks/`. Both
  opt-in; absent = identical behavior. Full review in
  [`plans/symphony-spec-review.md`](symphony-spec-review.md).
- **Retire the pre-PR rebase compatibility alias.** Confirm that no
  out-of-repo patch still imports `_merge_base_into_worktree`, then remove
  that forwarding function and its compatibility test. The source TODO in
  [`orchestrator/git/base_sync/pre_pr.py`](../orchestrator/git/base_sync/pre_pr.py)
  named 2026-08-24 as the removal point.

## Risks

- **R1 — Codex / Claude CLI output format drift.** Isolated in the
  provider-specific leaves under `orchestrator/agents/backends/` and
  `orchestrator/observability/usage/`; failures surface as
  `session_id=None` (logged) or empty `last_message` (park with stderr
  quoted via `workflow.engine.messages._format_stderr_diagnostics`).
- **R2 — Self-mutation while running.** Per-issue worktrees +
  ancestry-aware self-update detection in
  `runtime.self_update.self_modifying_merge_happened` + the `run.sh`
  self-restart wrapper.
- **R3 — Runaway agent loops / token cost.** Wall-clock timeouts
  (`AGENT_TIMEOUT`, `REVIEW_TIMEOUT`), per-issue retry budget
  (`MAX_RETRIES_PER_DAY`), review / fix cap (`MAX_REVIEW_ROUNDS`),
  conflict-resolution cap (`MAX_CONFLICT_ROUNDS`), and the durable lifetime
  circuit (`MAX_AGENT_RUNS_PER_ISSUE`) bound the separate ways an issue can
  keep spawning agents.
- **R4 — GitHub rate limits.** Idle per-repo polls and closed-issue
  sweeps can exhaust a PAT's 5000 requests/hour at the default cadence
  once enough repos are tracked. Label caching and
  `CLOSED_ISSUE_SWEEP_EVERY_N_TICKS` reduce the floor; operators can
  raise `POLL_INTERVAL` or split repos across tokens.
- **R5 — Race between human controls and orchestrator action.** Trusted
  comment filters, per-surface watermarks, content hashes, and fresh
  post-agent label reads keep late comments from being silently consumed
  and keep agent output from being published after a mid-run pause.
- **R6 — Destructive terminal cleanup.** Artifact reclamation is bounded
  to derived orchestrator names and fails closed on every ambiguous read;
  it also drains scheduler work, takes the host maintenance lock, rechecks
  tips, and uses non-forced / leased deletes. Those are application guards,
  not an OS isolation boundary: arbitrary processes running as the same
  user remain outside the lock's protection.

[typed-states]: ../docs/state-machine.md#typed-states-and-the-transition-guard
[trajectory-sink]: ../docs/observability.md#trajectory-sink-trajectory_log_path
[agent-run-circuit]: ../docs/security.md#bounded-agent-spend-per-issue-max_agent_runs_per_issue
[size-gate]: ../docs/workflow/roles.md#the-size-gate-a-committed-candidate-passes
[artifact-reclamation]: ../docs/configuration/operations.md#reclaiming-a-finished-issues-artifacts
[continuous-integration]: ../docs/configuration/operations.md#continuous-integration
