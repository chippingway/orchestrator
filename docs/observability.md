# Observability

The orchestrator emits three independent JSONL sinks plus an optional Postgres aggregation target. None are read by the
polling tick — workflow correctness keys off the pinned `<!--orchestrator-state ...-->` JSON comment on the issue (and
the workflow label). Every observability surface here is observation-only and safe to truncate, rotate, or delete at any
time.

- **Audit event log** (`EVENT_LOG_PATH`) — opt-in JSONL audit of workflow events, written through
  `GitHubClient.emit_event`.
- **Analytics sink** (`ANALYTICS_LOG_PATH`) — project-local JSONL of raw metric records. The recorders that append it
  are owned by `orchestrator/observability/analytics/recording/` and the by-age prune that bounds it by
  `orchestrator/observability/analytics/retention.py`; the read models are still entered through the
  `orchestrator/analytics/` package, though the reads themselves — and the whole sync, the command that starts one
  included — are owned beside them under `orchestrator/observability/analytics/`.
- **Trajectory sink** (`TRAJECTORY_LOG_PATH`) — opt-in, default-off JSONL sink for per-run agent reasoning
  trajectories, a sibling sink whose writers live in `orchestrator/observability/analytics/trajectories/` and whose
  by-age prune is the same `retention.py` owner, reading its own knobs. `record_agent_exit` is its
  producer: when the sink is on it parses each tracked run's trajectory from the same stdout, redacts and head/tail
  truncates every free-text field, and appends one `agent_trajectory` record — all behind its own fail-open guard. A
  dedicated, file-backed **trajectory viewer** (`orchestrator/apps/trajectory_dashboard.py`) renders it as a separate
  Streamlit page.
- **Analytics database** (`analytics-db/`) — operator-deployed Postgres service that is the aggregation target for the
  analytics sink, with an operator-driven sync CLI and a Streamlit dashboard on top.
- **Usage parser** (`orchestrator/observability/usage/`) — decoder for the agent CLI JSONL stdout that produces the
  token / cost detail the analytics `agent_exit` record carries.

Every module path in this document is the current one. `orchestrator/observability/` holds the usage parser's owners,
the analytics configuration, recording, retention, trajectory-sink, read-path, and sync owners
(`analytics/config.py`, `analytics/recording/`, `analytics/retention*.py`, `analytics/trajectories/`,
`analytics/query/`, `analytics/sync/`), the visual theme both Streamlit pages are drawn in (`dashboard/palette.py`,
`dashboard/tokens.py`, `dashboard/layout.py`, `dashboard/css.py`, `dashboard/formatting.py`), the window, filter, and
read-mode state one run of the analytics page carries plus the bar that window is picked in, the two waves its load is
staged into, the fan-out each
is issued through, and the dispatch that drives both, the seven a
headline or lifecycle section is drawn from, the six a comparison panel is, the three a skill panel is, the
connection, filter binding, and unfiltered metadata each read goes through, and the banners a window is interrupted
with above all of them plus the four numbers it is summarized by beneath those, the per-day lines drawn under three
of them, the strip all four are assembled into, where each day of one of those lines sits and the SVG it is written
as, the banner, filter line, and delta pill that strip sits among, the markup the banners, the run-health tiles, and
every card
header are drawn as, and the two panels drawn as markup rather than as a figure — one backend's efficiency, and
the share of a window's spend that could be priced (`dashboard/windows.py`,
`dashboard/filters.py`, `dashboard/date_controls.py`, `dashboard/date_filter.py`,
`dashboard/read_mode.py`, `dashboard/read_plan.py`, `dashboard/fanout.py`,
`dashboard/dispatch.py`, `dashboard/rollups.py`,
`dashboard/breakdowns.py`, `dashboard/skills.py`, `dashboard/scoped_reads.py`, `dashboard/filter_binding.py`,
`dashboard/static_metadata.py`, `dashboard/insights.py`, `dashboard/kpis.py`, `dashboard/kpi_series.py`,
`dashboard/kpi_strip.py`, `dashboard/sparkline_points.py`, `dashboard/sparkline_html.py`,
`dashboard/summary_html.py`, `dashboard/card_html.py`, `dashboard/backend_card.py`,
`dashboard/coverage_card.py`), the primitives every chart family on
that page is drawn out of plus the frame the horizontal cost families share, the generic spend ranking, the
per-repository one drawn through it, the per-stage cache split, the per-review-round one beside it, the
weekday-by-hour grid, and the per-day throughput strip above them, and the usage family's own bands, day span, stack
heights, aligned axes, traces, and hero figure
(`dashboard/charts/primitives.py`, `dashboard/charts/cost_layout.py`, `dashboard/charts/cost_horizontal.py`,
`dashboard/charts/cost_repo.py`, `dashboard/charts/cost_stage.py`, `dashboard/charts/cost_review.py`,
`dashboard/charts/heatmap.py`,
`dashboard/charts/throughput.py`, `dashboard/charts/usage_bands.py`, `dashboard/charts/usage_series.py`,
`dashboard/charts/usage_axis.py`, `dashboard/charts/usage_traces.py`, `dashboard/charts/usage.py`), the compact
table the panels beside those figures are drawn as, the ranking of a window's costliest issues that is the first
of them, the aggregate skill-trigger rates that are the second, and the per-session adoption table and the
invocation-level trigger matrix that are the last two — each split into the columns a click is expressed in, the parse
and orders behind one, the header row it is clicked from, what one cell says, and the panel they assemble into — plus
the two cards three of those panels are reported on, one leading with adoption and folding the invocation views under
it and one kept for a caller reaching past that, the listing of the runs under all four, and the hero spend and
token-usage card above every one of them
(`dashboard/tables.py`, `dashboard/issue_table.py`, `dashboard/skill_trigger_table.py`,
`dashboard/skill_adoption_columns.py`, `dashboard/skill_adoption_sort.py`,
`dashboard/skill_adoption_headers.py`, `dashboard/skill_adoption_rows.py`, `dashboard/skill_adoption.py`,
`dashboard/skill_matrix_columns.py`, `dashboard/skill_matrix_sort.py`, `dashboard/skill_matrix_headers.py`,
`dashboard/skill_matrix_rows.py`, `dashboard/skill_matrix.py`, `dashboard/skill_panel.py`,
`dashboard/skill_trigger_panel.py`, `dashboard/recent_runs.py`, `dashboard/usage_panel.py`), the three sections that
window's spend is compared across — the paired lifecycle bars and the one height both are pinned to, the ranked
issues beside the backends that ran them, and the per-repository ranking beside the tiles and days those runs are
read for (`dashboard/stage_cost_panel.py`, `dashboard/issue_cost_panel.py`,
`dashboard/reliability_panel.py`) — the
seven frozen shapes one render of that page is
threaded through and the Plotly configuration each of its figures is handed (`dashboard/page_models.py`,
`dashboard/render_config.py`), the
trajectory viewer's whole read model — its file
read, record parse, run models, and the filtering and summary aggregation over them — plus the styling and every
inline-HTML builder that read is drawn with, and the page state, setup, controls, picker, run card, and whole-page
composition one run of it is driven by (`trajectory_viewer/`), and the packages the rest of the analytics sink,
the dashboard, and the trajectory viewer are each migrating into; until a responsibility has an owner in that tree,
the module named for it below stays the import site. The page that composes those viewer owners is not one of them:
it sits beside the tree, at `orchestrator/apps/trajectory_dashboard.py`, and the analytics page is still started at
`orchestrator/dashboard.py`. See
[`architecture.md`](architecture.md#top-level-layout) for that boundary and the rules those owners inherit.

## Audit event log (`EVENT_LOG_PATH`)

Optional, opt-in JSONL sink. When `config.EVENT_LOG_PATH` is set, `github.events.write_event_record` appends one JSON
object per audit event to that file inside `GitHubClient.emit_event`; when unset (the default) the helper
short-circuits to a no-op. The fake `GitHubClient` in `tests/support/github/` calls the same helper.

**Schema.** Every record is built by `github.events.build_event_record` and carries `ts` (UTC ISO-8601 at second
precision), `repo` (the slug `owner/name`), `issue` (issue number, int), and `event` (the kind). `stage` is included
when the emitter passes one (effectively always today). Extras whose value is `None` are dropped. `json.dumps` is
called with `sort_keys=True` so on-disk order is stable across writers.

**Event kinds.** Every kind is emitted through the single `GitHubClient.emit_event` chokepoint, which also appends to a
capped in-memory tail (`recorded_events`, `_RECORDED_EVENTS_CAP = 500`) for tests and short-window debugging — the
file is the durable record.

- `stage_enter` — `set_workflow_label` (via `_emit_stage_enter`) for every label flip; extras: `stage`.
- `agent_spawn` / `agent_exit` — `_run_agent_tracked` (in `workflow/engine/usage.py`) wraps every `run_agent` call
  (decomposer, implementer, reviewer, dev-resume, conflict-resolution dev); extras: `agent` (backend), `agent_role`,
  `review_round`, `retry_count`. `session_id` and `agent_exit`-only fields are described below.
- `skill_triggered` — `_run_agent_tracked` after `agent_exit`, **only when `TRACK_SKILL_TRIGGERS` is on**
  (default off); one event per distinct skill the run triggered; extras: `agent` (backend), `agent_role`,
  `review_round`, `retry_count`, `skill` (the triggered skill name). Reuses the list `record_agent_exit` already parsed;
  off-switch installs emit none.
- `review_verdict` — `_handle_validating` after `_parse_review_verdict` reads the reviewer's last message; extras:
  `verdict` (`approved` / `changes_requested` / `unknown`), `review_round`, `pr_number`, `session_id`.
- `park_awaiting_human` — every `_park_awaiting_human` (in `workflow/engine/guards.py`) call site, plus
  `_on_question`, `_on_dirty_worktree`,
  `_park_verify_failure`, and the question-stage `_park_question` funnel; extras: `stage` (read from the current
  workflow label, not passed in), `reason` (e.g. `agent_timeout`, `push_failed`, `failed_checks`, `agent_question`,
  `agent_session_limit` (a quota-exhausted agent message, parked retryably as `agent_silent`), `dirty_worktree`,
  `reviewer_timeout`, `verify_failed` / `verify_timeout` / `verify_dirty` / `verify_head_changed`, `question_*`, ...).
- `pr_opened` — `_on_commits` after `gh.open_pr` succeeds; extras: `pr_number`, `branch`, `sha`, `retry_count`.
- `pr_merged` — External merge terminal arcs in `_handle_in_review`, `_handle_fixing`, `_handle_resolving_conflict`;
  plus `_finalize_if_pr_merged` (in `workflow/engine/terminals.py`, which also owns those arcs) from
  `_handle_implementing` / `_handle_documenting` / `_handle_validating` entry checks
  and from the `_handle_blocked` / `_handle_umbrella` manually-closed child recovery; extras: `pr_number`, `sha`,
  `merge_method="external"`, `review_round`, `conflict_round`, `retry_count`; `stage` reflects the workflow label at
  finalize entry.
- `pr_closed_without_merge` — `_handle_in_review`, `_handle_fixing`, `_handle_resolving_conflict` when the PR is
  closed without merge; plus `_finalize_if_issue_closed` from `_handle_implementing` / `_handle_documenting` /
  `_handle_validating` entry checks (only when the linked PR is also closed; an open PR with a manually-closed issue is
  left alone); extras: `pr_number`, `sha`, `review_round`, `conflict_round`, `retry_count`; `stage` reflects the
  workflow label at finalize entry.
- `merge_attempt` — Every `git rebase origin/<base>` inside `_handle_resolving_conflict`; extras:
  `method="base_rebase"`, `result` (`success` / `failed` / `conflict`), `pr_number`, `sha`, `conflict_round`,
  `review_round`, `retry_count`.
- `conflict_round` — `_route_pr_worktree_to_resolving_conflict` emits `action="entered"` only when the refresh-time
  rebase actually leaves conflicted files (a merely-behind-base clean rebase no longer emits this);
  `_reconcile_parked_fixing` also emits `action="entered"` (with `stage="fixing"`) when a stuck validating-route
  transient `fixing` park is routed to `resolving_conflict` because its worktree is out of sync with the PR head (behind
  base, or an unpushed local rebase); every increment site (`_emit_conflict_round_incremented`) emits
  `action="incremented"` with `outcome`; extras: `pr_number`, `conflict_round`, `review_round`, `retry_count`, `outcome`
  (for increments), `sha`.
- `base_rebased` — `_sync_pr_worktree_to_base` after a clean refresh-time rebase + push that routes the issue from
  `validating` / `documenting` / `in_review` / `fixing` back to `validating`; also `_recover_pending_auto_base_rebase`
  when a crashed prior tick is finalized; extras: `pr_number`, `sha` (new head), `method` ∈ {`auto_clean_rebase`,
  `crash_recovery_pushed`, `crash_recovery_relabel_only`}, `review_round` (post-reset, so 0), `retry_count`; `stage`
  reflects the workflow label at the start of the rebase.

**`agent_spawn` / `agent_exit` extras.** On top of the shared fields:

- On `agent_spawn`, `session_id` is the resume session id and is OMITTED for fresh spawns (`resume_session_id=None` is
  dropped by `build_event_record`).
- On `agent_exit`, `session_id` is the result id from `AgentResult`. `agent_exit` additionally carries `duration_s`,
  `exit_code`, and `timed_out`.

**`skill_triggered` events (opt-in).** Gated behind `TRACK_SKILL_TRIGGERS` (default off; the same switch that adds the
[`agent_exit` analytics skill fields](#agent_exit-records)). After the `agent_exit` audit event fires,
`_run_agent_tracked` emits one `skill_triggered` event per distinct skill the run triggered, reusing the de-duplicated
first-seen list `record_agent_exit` parsed from the same stdout rather than re-reading it. Each event carries `agent`
(backend), `agent_role`, `review_round`, `retry_count`, and the `skill` name — and never the `Skill` tool's `args`
(Privacy, same names-only contract as the analytics fields). A run that triggered nothing, or any install with the
switch off, emits none, so the default audit log is unchanged. The emission rides its own fail-open guard: a bug here
logs and is swallowed, never disturbing the baseline `agent_spawn` / `agent_exit` events. This is the per-invocation
granularity surface; the rolled-up counts live in the `agent_exit` analytics record below.

**No built-in rotation.** `write_event_record` reopens the file in append mode for every event after
`path.parent.mkdir(parents=True, exist_ok=True)`; there is no long-lived file descriptor, no size cap, no rename, and no
compression. External rotation is operator-managed — pair `EVENT_LOG_PATH` with `logrotate` (or equivalent). Because
each append re-resolves the path, create/rename-style rotation is as safe as `copytruncate`: the next event picks up the
new inode without any `SIGHUP` or restart.

An `OSError` during the append is caught and downgraded to a `log.warning` so a misconfigured path (read-only mount,
disk full, permission failure) cannot stop the per-issue tick from making progress; the missing record is silently
dropped and the pinned state on GitHub remains correct.

**Pinned state is authoritative.** The event log is append-only and observation-only. The orchestrator never reads it
back; every dispatch decision keys off the pinned `<!--orchestrator-state ...-->` JSON comment on the issue (and the
issue's workflow label). If the two disagree, trust pinned state. The append-only log is safe to truncate or delete at
any time without affecting workflow correctness.

## Analytics sink (`ANALYTICS_LOG_PATH`)

Project-local JSONL sink for raw metric records, separate from `EVENT_LOG_PATH`. Opts in or out independently via
`ANALYTICS_LOG_PATH` / `ANALYTICS_RETENTION_DAYS`; the recorders that write it live in
`orchestrator/observability/analytics/recording/`, and the retention prune beside them in
`orchestrator/observability/analytics/retention.py`.

**Module layout.** The append side lives in `orchestrator/observability/analytics/recording/`, whose initializer
publishes the six recorders a producer calls (`build_record`, `append_record`, `record_stage_enter`,
`record_stage_evaluation`, `record_repo_skill_catalog`, `record_agent_exit`) as the `events` owner's own objects.
Beside it are `io.py` (the locked JSONL line both sinks write through, and the one lock each of them holds),
`models.py` (typed requests and the keyword signatures a call is bound through), and the four owners one finished
agent run is summarized by — `usage.py`, `skills.py`, `catalog.py`, and `agent_exit.py`. Every producer names that
package: `orchestrator/github/client.py`, `orchestrator/workflow/engine/dispatch.py`,
`orchestrator/workflow/engine/usage.py`, and `orchestrator/skills/catalog.py`.

One directory up, `retention.py` publishes the three prune entry points — the polling tick's fail-open wrapper
(`prune_with_retention_logging`) and one by-age prune per sink (`prune_old_records`,
`prune_trajectory_records`) — over `retention_scan.py` (the timestamp a record is judged by, and the split of a file
into kept lines and a removed count) and `retention_rewrite.py` (the same-directory temp file, the `os.replace` that
swaps it in, and the lock held across the read and that swap). It sits beside `config.py` rather than inside either
sink's package because both sinks are pruned through it. `main._run_tick` names that owner directly.

`orchestrator/analytics/__init__.py` stays an import-only compatibility facade re-exporting the same objects, including
the three historical prune entry points. Its bootstrap reparses the six sink knobs on every package import and
assembles a fresh recorder, trajectory-append, and retention set — the recording `events` owner, the trajectory `api`
owner, and the `retention` owner are replaced with them — so references held across a package reload keep their
historical isolation. The recording package above `events` is re-executed in place rather than replaced, so the one
module object every producer imported keeps publishing the live recorders, and the facade's bindings and a patch aimed
at the canonical module stay the same objects whichever import came first. Each sink's lock — the object its append
and its prune must share — is minted on `recording/io.py`, which no reload rebuilds, so an append taken off its owner
before the facade existed still serializes against the prune rather than writing into a file being rewritten under it.
The retention scan and rewrite leaves are deliberately *not* in that rebuilt set: they read every path, window, and
lock off the arguments the entry point hands them, so a second copy would buy nothing. The read and sync surfaces are
separate Postgres-facing families, and neither has a responsibility left here: the whole sync has moved out, `sync.py`
included. The column inventory both shapes meet on, the canonical encoding a content hash is taken over, the coercion
each required field is narrowed by, the INSERT with the positional tuple that fills it, the counts a replay is read
back as, the batched ingestion and its two dedup filters, the connection lifecycle and rollup refresh around them, the
URL redaction, `sync_jsonl_to_postgres` itself, and the command that drives it — arguments, UTC-pinned logging, exit
code, and stdout summary — all belong to `observability/analytics/sync/`. The filters a read is asked
for, the binding of its keyword call, the connection lifecycle, the query execution, the frozen models a read answers
with, the six reads that stay on the events table, the seven that scan the daily rollup above it, the four whose
grouping key that rollup threw away, and the three answered from a run's `extras` blob all belong to
`observability/analytics/query/`. What is left here is forwarding: `analytics.read` is a manifest-backed lazy facade,
and `predicates.py`, `_predicate_*.py`, `read_request*.py`, `read_models*.py`, `read_raw.py`, `read_rollup.py`,
`read_dashboard.py`, and the seven raw, seven rollup, and nine breakdown-and-skill `_read_*.py` leaves define nothing
of their own — each binds the owner's object under the name a historical caller imported. `sync.py` and the nine
leaves `_sync_row_schema.py`, `_sync_row_parse.py`, `_sync_row_mapping.py`, the `_sync_rows.py` hub that grouped them,
and `_sync_models.py`, `_sync_redaction.py`, `_sync_database.py`, `_sync_ingest.py`, and `_sync_run.py` forward the
same way, under the private spellings each published while it owned them — `sync.py` additionally stays a working `-m`
target, so an operator's scheduled `python -m orchestrator.analytics.sync` reaches the command owner rather than
breaking.

**Settings ownership.** `ANALYTICS_LOG_PATH`, `ANALYTICS_RETENTION_DAYS`, and `ANALYTICS_DB_URL` (and the sibling
trajectory-sink knobs `TRAJECTORY_LOG_PATH` / `TRAJECTORY_RETENTION_DAYS`, plus `TRACK_SKILL_TRIGGERS`) are parsed by
`orchestrator/observability/analytics/config.py` — *not* in `orchestrator/config/`. That owner reads the environment
inside the call, never at import, so every knob resolves against whatever environment the caller set up; its
`parsed_settings` is what the `orchestrator/analytics` bootstrap binds on the package, and its `resolve_db_url` is the
fallback a read's omitted `db_url=` resolves through. The values stay exposed as package attributes
(`analytics.ANALYTICS_LOG_PATH`, etc.) that tests patch directly via
`patch.object(analytics, "ANALYTICS_LOG_PATH", ...)`, and every adapter reads one back through the owner's `Settings`
view, which reads its attribute on demand so a patch reaches the next read. The two entry points differ only in whose
instance answers: the recorders in `recording/events.py`, the sink append in `trajectories/api.py`, the prune wrappers
in `retention.py`, and the skill readers pass `config.settings_on` the package instance they captured at their own
import (a package reloaded against a patched env is what its own callers drive) — `events.settings_holder` is where
that capture is read out of `sys.modules`, and a producer that imported the recording owner with no analytics package
behind it resolves the name inside the call instead — while the trajectory writers below the append take that instance
off the exit context they are handed, the viewer's `trajectory_viewer/log_paths.py` takes one as an argument from the
`_trajectory_records.py` leaf that captured it (which is what keeps two reloaded readers each on their own file), and
the read and sync paths have nothing captured and use `config.live_settings`, which resolves the package name. The
audit event log (`config.EVENT_LOG_PATH`) stays in `config` because `GitHubClient.emit_event` is a general-purpose
audit surface.

**Filesystem only.** No PostgreSQL, Streamlit, or external services — the sink is one JSONL file under the project log
area. Default path is `<LOG_DIR>/analytics.jsonl`, already covered by the `logs/` `.gitignore` rule. Set
`ANALYTICS_LOG_PATH=` (empty) or to `off` / `disabled` / `none` to disable writes entirely; in that mode `append_record`
and `prune_old_records` are silent no-ops and no file is opened.

**Schema.** Every record is built by `recording.build_record` and carries `ts` (UTC ISO-8601 at second precision),
`repo` (the slug `owner/name`), `issue` (issue number, int), and `event` (the kind). `stage` is included when the caller
passes one; extras whose value is `None` are dropped. `json.dumps` uses `sort_keys=True` so on-disk order is stable. The
JSONL file is the raw foundation layer for the Postgres aggregation step.

**Event kinds written today:**

- `stage_enter` — `GitHubClient._emit_stage_enter` alongside the audit `stage_enter`; one record per workflow label
  transition; carries `stage`.
- `stage_evaluation` — the `_process_issue` dispatcher (in `workflow/engine/dispatch.py`, also reachable as
  `workflow._process_issue`); written by its try/except/finally wrapper; carries `stage`,
  `duration_s` (handler wall-clock), `result` (`"ok"` / `"error"`); omitted for `backlog`- / `paused`-skipped issues
  (no handler runs).
- `agent_exit` — `_run_agent_tracked` (in `workflow/engine/usage.py`); one record per tracked agent invocation; agent
  context + parsed token / model / cost details (see below).
- `repo_skill_catalog` — `orchestrator.skills.catalog._emit_repo_skill_catalog`, driven once per tick per spec by the
  tick owner (in `workflow/engine/tick.py`, reachable as `workflow.tick`); repo-level (not issue-scoped, so `issue` is
  the sentinel `0`); carries `base_branch`, `remote_name`, `skills_available` (deduped `SKILL.md` skill names on the
  base ref), and optional `skill_paths` (name → source paths) — see below.

**Append.** `recording.append_record(record)` reopens the file in append mode for every record after
`path.parent.mkdir(parents=True, exist_ok=True)`. An `OSError` is caught and downgraded to a `log.warning`.
`analytics.append_record` is the same object for as long as the compatibility facade forwards it.

**Retention pruning.** `retention.prune_old_records(*, now=None)` reads the file and removes records whose `ts` is older
than `ANALYTICS_RETENTION_DAYS`. No-op (returns `0`) when the sink is disabled, retention is non-positive, or the file
does not exist. The rewrite goes through a temp file in the sink's own directory followed by `os.replace` so a crash
mid-prune cannot truncate the analytics file. Records with a missing / non-string / unparseable `ts` (and any line that
is not valid JSON) are preserved verbatim so the prune step never silently drops data it cannot interpret.
`analytics.prune_old_records` is the same object for as long as the compatibility facade forwards it.

**Append/prune serialization.** Append and prune share one process-local `threading.Lock`, minted on
`recording/io.py` — the owner no package reload rebuilds, so every reference to `append_record` takes the object the
prune takes — so a concurrent `append_record` cannot land between the prune's read and its `os.replace`. Under the
scheduler-driven dispatch, `workflow.tick` returns as soon as it has submitted per-issue callables, so scheduler
workers may still be running — and calling `append_record` — when `main._run_tick` invokes
`prune_with_retention_logging()`. Without the lock, an append that opened the old inode after the prune's read but
before the replace would be silently lost. The lock is held only around the filesystem ops; JSON serialization happens
outside the critical section.

**Retention cadence.** `main._run_tick` calls `retention.prune_with_retention_logging()` exactly once per polling
iteration after `workflow.tick` returns for every configured repo, regardless of how many repos are configured — the
sink is process-wide, not per-repo. It names the owner inside the call, because the analytics package rebuilds that
owner for each instance it initializes. Right before the prune, `_run_tick` calls `scheduler.reap()` exactly once per
polling pass so worker failure-completion records drain before the next iteration. `_dispatch_via_scheduler`
deliberately does NOT reap. The wrapper catches exceptions and logs the `"removed N record(s)"` message so the call site
in `main` stays a one-liner, and it delegates back through the settings holder so
`patch.object(analytics, "prune_old_records", ...)` still intercepts. Per-tick cost is bounded: the helper reads the
file at most once and only rewrites it when at least one record is older than the retention window.

**Pinned GitHub state is unaffected.** The prune touches only the local file — no issue comment, label, or other
GitHub state is rewritten. The analytics sink is local-filesystem observability and is safe to truncate or delete at any
time.

### `agent_exit` records

`_run_agent_tracked` (in `workflow/engine/usage.py`) appends a single `event="agent_exit"` analytics record after
every tracked agent run, distinct from (and in addition to) the audit `agent_spawn` / `agent_exit` events on
`EVENT_LOG_PATH`. Each record carries:

- **Context** — `repo`, `issue`, `stage`, `agent_role`, `backend`, `review_round`, `retry_count`, `duration_s`,
  `exit_code`, `timed_out`.
- **Spec / session** — the configured `agent_spec` (the role's full `*_AGENT_SPEC` string, e.g. `claude --model
  claude-opus-4-7`), both the `resume_session_id` passed into the spawn and the live `session_id` from the result.
- **Usage parser output** — `input_tokens`, `output_tokens`, `cached_tokens`, `cache_read_tokens`,
  `cache_write_tokens`, the distinct `models` observed in the stream, `turns`, `cost_usd`, and `cost_source`.
- **Skill triggers (opt-in)** — only when `TRACK_SKILL_TRIGGERS` is on (default off): `skills_triggered` (distinct
  skill names, first-seen order), `skills_triggered_count` (total trigger count, so three `develop` pulls read `3` while
  the list carries `develop` once), `skills_evidence` (name → the per-load evidence tier: `confirmed` for a claude
  `Skill` tool call, `inferred` for a codex command that directly reads the skill's `SKILL.md` with a reader verb such
  as `cat` / `sed`), the incidental pair `skills_incidental` / `skills_incidental_count` (path-only references a codex
  run made to a `SKILL.md` without reading it — a `git diff` / `git status` / `rg`, an env-prefixed inspection, a write
  to the file (`>` redirect or `sed -i`), or any other non-reader command — kept out of `skills_triggered`, its count,
  and the `skill_triggered` audit events so a bystander
  mention is never miscounted as a load, but recorded independently: a skill both read *and* inspected appears in both
  buckets), and `skills_available` (the offered-skills set). On **claude** the offered set is
  read from the dedicated `skills` array in the `system`/`init` stream frame — confirmed against a real captured
  `--output-format stream-json` run — so `skills_available` is populated for tracked claude runs independently of what
  they triggered. Codex's `codex exec --json` stream carries no such offered-skills catalog, so for **codex** the set is
  instead discovered out-of-band from the filesystem by `skills.discovery.discover_local_skills(cwd)` — a scan of the
  repo skill roots (`.agents/skills` / `.claude/skills`) under the run's worktree plus the global
  `$CODEX_HOME/skills` codex
  loads, including the built-in skills under that global root's `.system` container (`imagegen`, `openai-docs`, …). It
  runs only for codex, never overrides the claude stream-parsed set, and is fail-open (a missing root leaves the field
  empty). Each
  field is dropped (its key absent) when empty, so a claude run that was offered skills but triggered none records
  `skills_available` while the triggered / evidence keys drop — the "offered but unused" vs "never available" signal —
  and a run with nothing to report keeps the record shape identical to the switch-off case. Parsed via
  `observability/usage/skills.py`'s `parse_agent_skills` under its own fail-open guard inside `record_agent_exit`: a
  skill-parse failure logs and still emits the baseline usage / cost record, and reads only the skill *name* — never
  the `Skill` tool's `args`, the surrounding codex command text, or a command's `aggregated_output` (the file's
  contents). With the switch off the extractor never runs and none of the skill keys appear.

The configured model is pulled out of the role's `extra_args` (via `_configured_model`; recognises `-m <model>` /
`-m=<model>` for codex and `--model <model>` / `--model=<model>` for claude) and forwarded as the parser's
`fallback_model` so a codex run whose stdout includes usage frames but omits the model still records the configured
model and — when it matches a priced family — an estimated `cost_usd`. A stream-reported model always wins over the
fallback.

Prompts, raw stdout / stderr, secrets, and worktree contents are deliberately NOT stored — the sink is a usage / cost
surface, not a debugging mirror. A parser exception or sink IO failure is swallowed so an analytics misconfiguration
cannot stop the per-issue tick.

**Skill-trigger surfaces (shipped).** Both skill-trigger follow-ups (the audit event and the dashboard widget) have now
landed. The per-invocation `skill_triggered` audit event on [`EVENT_LOG_PATH`](#audit-event-log-event_log_path) (see the
[audit event-kinds list](#audit-event-log-event_log_path)) is gated on the same `TRACK_SKILL_TRIGGERS` switch and
reuses the list `record_agent_exit` already parsed — `_run_agent_tracked` emits one event per distinct triggered
skill. The dashboard's primary skill metric is per-session **adoption** (`get_skill_adoption` + the "Skill adoption"
panel), which counts, for each `(repo, role, backend, skill)` cell, how many logical agent sessions had the skill
available and how many loaded it — an incidental `SKILL.md` reference stays a separate diagnostic column and never
raises the rate. The invocation-level views (`get_skill_trigger_rates` and `get_skill_trigger_matrix`) sit
beneath it as a clearly named invocation-level diagnostic — see the
[read model](#read-model-orchestratoranalyticsreadpy) and [dashboard](#dashboard-orchestratordashboardpy) sections
below. All are pure read-side additions over `extras JSONB` with no schema change. See
[Session-aware skill adoption](#session-aware-skill-adoption) for the four evidence forms and the per-session adoption
semantics that sit on top of these fields.

### Session-aware skill adoption

The dashboard's **primary** skill metric is per-session *adoption* — for each `(repo, agent_role, backend, skill)`
cell, what share of the logical agent sessions that had the skill available actually loaded it. It is computed by
`observability/analytics/query/skill_reads.py`'s `get_skill_adoption` and rendered by
`observability/dashboard/skill_panel.py`'s "Skill adoption" card; the
older per-run trigger views
(`get_skill_trigger_rates` / `get_skill_trigger_matrix`) sit beneath it as a clearly named invocation-level diagnostic.
The per-session adoption metric reads the opt-in `agent_exit` skill fields above, so it only carries signal once
`TRACK_SKILL_TRIGGERS` has recorded a session's available and loaded skills. The invocation-level views degrade more
gently with the switch off: the trigger-rate table still counts every `agent_exit` run (a `0` trigger rate), and the
matrix still renders each repo's catalog-backed skills as explicit zero rows, because the `runs` denominator and the
`repo_skill_catalog` records do not depend on the switch. Records written while it was on stay queryable after it is
turned off.

**Four evidence forms.** A skill observation is classified into one of four forms. The first three are emitted on the
`agent_exit` record; the fourth is a read-model inference and is never written to disk:

- **confirmed** *(load)* — a claude `Skill` tool-use block, the firm signal. Recorded in `skills_triggered`, with tier
  `confirmed` in `skills_evidence`.
- **inferred** *(load)* — a codex `command_execution` whose leading verb is an established direct reader
  (`cat` / `sed` / `head` / …) opening a `skills/<name>/SKILL.md`. A heuristic file-open signal. Recorded in
  `skills_triggered`, with tier `inferred` in `skills_evidence`. A single run is homogeneous — claude only confirms,
  codex only infers — so every `skills_evidence` entry on one record shares its tier.
- **incidental** *(not a load)* — a codex *path-only* reference to a `SKILL.md`: a non-reader inspection / search
  (`git diff` / `git status` / `rg`), an env-prefixed inspection (`GIT_PAGER=cat git diff …`), or a write to the file
  (`>` redirect / `sed -i`). Recorded independently in `skills_incidental` / `skills_incidental_count`, deliberately
  kept out of `skills_triggered`, `skills_triggered_count`, `skills_evidence`, and the `skill_triggered` audit events,
  so a bystander mention is never miscounted as a load. A skill both read *and* inspected lands in both buckets.
- **legacy** *(implied availability)* — not an emitted field. Inside `get_skill_adoption`, a load whose logical
  session never reported any `skills_available` metadata (no row carried the `skills_available` *key*) is treated as
  implied availability: the load itself implies the skill was offered, so it still counts in that session's
  availability denominator. An explicit empty `skills_available: []` is metadata ("scanned, found none") and
  **blocks** this fallback, so a load against a session that reported no offered skills does not fabricate availability.

**Logical-session fallback.** Adoption counts by *logical agent session*, not by raw run, so a resume chain that pulled
`develop` across several ticks counts as one adopting session, not several. A session is keyed by `resume_session_id`,
then `session_id`, then the row's primary key — an ID-less row is its own session, never merged into one anonymous
bucket, and the primary-key fallback is stable across both scans below.

**Active window vs. historical lookback.** `get_skill_adoption` runs two `agent_exit` scans and combines them in Python:

- The **active-window** scan applies the full reporting-window filters (date `[start, end)` / repo / stage / issue). It
  selects the *active* sessions (those with a run in the window) and computes the window-scoped invocation diagnostics.
- The **historical-lookback** scan (`WindowFilters.historical_scope`) gathers each active session's availability + load
  evidence from every `agent_exit` row *before the window end*, deliberately dropping the window `start` bound and the
  stage / events filters while keeping `end` / repo / issue — so a load or an availability report from a prior
  stage, or from before the reporting window, still counts toward that session's denominator and `adopted`. History
  rows for sessions that were not active in the window are ignored, so their evidence never leaks into the aggregate.

The retained `end` bound is the **future-evidence cutoff**: evidence recorded *after* the window end never leaks
backward into an earlier window's aggregate, so a later load cannot retroactively raise a past window's adoption.

**Per-session availability denominator.** `sessions` (the denominator) is how many logical sessions in the cohort had
the skill available — its reported `skills_available` union listed it, or the *legacy* fallback above implied it.
`adopted` (the numerator) is how many of those sessions loaded it, counted once per session no matter how many runs
reached for it; `adoption_rate` is `adopted / sessions`. A zero-session cell has an undefined rate that renders as a
muted `—`, never a misleading `0%`.

**Primary adoption vs. invocation-level diagnostics.** The read model carries three **window-scoped invocation** fields
(raw `agent_exit` rows, not sessions, and not the historical evidence): `invocations` is every run in the cohort's
window, `load_rows` the window runs that loaded the skill, and `incidental` the window runs that made a path-only
(incidental) reference to its `SKILL.md`. The load and incidental buckets are independent — a single run can appear
in both — so `incidental` is a parallel count, not a "did-not-load" complement, and it can never raise the adoption
rate. Of these three the adoption table renders only `Invocation loads` (`load_rows`) and `Incidental references`
(`incidental`) as its two trailing columns; `invocations` (the cohort's total window run count) is a read-model field
used for ordering and context, not a displayed column. A pre-window load counts toward `adopted` but toward none of
the three, since all three are window-scoped. The collapsed invocation-level diagnostic beneath the adoption table
(`get_skill_trigger_rates` / `get_skill_trigger_matrix`) reports the same per-run granularity across roles / backends
and per-skill cohorts. See the [read model](#read-model-orchestratoranalyticsreadpy) for the exact query shapes and the
[dashboard](#dashboard-orchestratordashboardpy) for the rendered columns.

### `repo_skill_catalog` records

`orchestrator/skills/catalog.py` appends one repo-level `event="repo_skill_catalog"` analytics record per tick per spec,
driven from `workflow/engine/tick.py` after `_refresh_base_and_worktrees` has fetched `<remote_name>/<base_branch>`,
before the scheduler / in-tick split so it fires once per tick on either dispatch path. It enumerates
the `SKILL.md` definitions the *target repo* carries on its base ref via `git -C <target_root> ls-tree -r --name-only
<remote_name>/<base_branch> .agents/skills .claude/skills`, keeps only direct `<root>/<name>/SKILL.md` definitions (a
`SKILL.md` nested deeper — e.g. `.claude/skills/.system/<name>/SKILL.md` — is ignored, matching the names-only
trigger anchor in `observability/usage/skill_commands.py`), and dedupes by skill name across the two roots while
preserving every source path. The catalog is read from the target repo's base ref, never the orchestrator's own
working tree, so dashboard-local skill files are not scanned.

Each record carries `base_branch`, `remote_name`, `skills_available` (the sorted deduped skill names), and the optional
`skill_paths` (name → sorted source paths; dropped when empty). It is **not** issue-scoped, so its `issue` is the
sentinel `0` — the record still satisfies the `ts` / `repo` / `issue` / `event` envelope the sink and the Postgres
`analytics_events` schema require, and the four catalog fields all land in `extras JSONB` with **no DDL change**. The
whole producer is fail-open: a missing clone, an unfetched ref, a git error, or a sink IO failure logs and is swallowed
so catalog collection never disturbs the polling tick. An empty catalog still records `skills_available: []` (the
"scanned, found none" signal).

## Trajectory sink (`TRAJECTORY_LOG_PATH`)

A sibling, opt-in JSONL sink for agent *reasoning trajectories* — the ordered timeline of tool calls / results
interleaved with the assistant / user text turns, plus the final output a run produced — written by
`orchestrator/observability/analytics/trajectories/`, its two knobs parsed alongside the analytics ones by
`observability/analytics/config.py`. It is kept deliberately
**separate** from the analytics sink so the large free-text trajectory bodies never enter the numeric usage rollup, its
Postgres aggregation, or the dashboard.

**Module layout.** The writers divide by what one record passes through: `models.py` holds the head/tail and
whole-record caps, the view an adapter reads whichever values are in force back through, and the headline and running
budget a record is charged as; `sanitize.py` the leaf-by-leaf redaction and head/tail truncation; `serialize.py` the
record's shape and the order its turn / step arrays are drawn from the budget in; `persistence.py` the opt-in gate, the
stdout parse, the Codex backfill, and the fail-open guard around the write; and `api.py` the bare
`append_trajectory_record` an operator or the compatibility facade reaches.
`recording/agent_exit.py` names `persistence` directly and never the reverse; everything from `persistence` down reads
its settings holder off the exit context it is handed, so a record answers for the package instance the caller entered
on. The by-age prune (`prune_trajectory_records`) lives one directory up in
`orchestrator/observability/analytics/retention.py`, beside the analytics sink's, because the two are pruned through
one scan and one rewrite; it and the append take the sink's dedicated lock, which is minted on `recording/io.py`
beside the analytics one — see the append / prune discipline below for why it cannot live next to the append itself.

**Producer: `record_agent_exit`.** After the baseline `agent_exit` analytics record (and the opt-in skill parse) are
produced, `record_agent_exit` calls `trajectories.persistence.maybe_record_trajectory`, which — only when
`TRAJECTORY_LOG_PATH` is enabled —
parses the run's trajectory from the same stdout (`observability/usage/trajectory.py`'s `parse_agent_trajectory`),
redacts and truncates it, and appends one `event="agent_trajectory"` record. `_run_agent_tracked` (in
`workflow/engine/usage.py`) forwards its
orchestrator-built `prompt` so it can land as the redacted `user_input`; `record_agent_exit` also threads through the
`UsageMetrics` it already parsed for the baseline record so the trajectory can carry a denormalized `run_usage` summary
without a re-parse. The whole block rides its **own** inner fail-open `try/except`: a parser, redactor, or sink
failure logs (`log.exception`) and is swallowed, so it can never drop the baseline `agent_exit` usage / cost record or
the `skill_triggered` audit events, all of which were already produced before it runs. With the sink off (the default)
the block is a no-op before any parse work — the prompt is never read into a record and the `agent_exit` shape is
byte-for-byte unchanged. `main._run_tick` does not yet call `prune_trajectory_records`, so trajectory retention stays
operator-driven for now.

**Record shape.** One `agent_trajectory` record per tracked run carries the standard envelope (`ts`, `repo`, `issue`,
`event`, `stage`) plus correlation context (`agent_role`, `backend`, `session_id`, `review_round`, `retry_count`) and
the redacted trajectory: `user_input` (the orchestrator prompt), `system_prompt`, `tools` (the offered-tools set — read
from claude's stream, and for codex backfilled with the best-effort `skills.discovery.discover_codex_tools()` baseline
since its stream carries no offered-tools frame), `skills_triggered` / `skills_available` (names-only — for codex the
`skills_available` set is backfilled from the out-of-band `skills.discovery.discover_local_skills(cwd)` filesystem scan,
since its stream carries no
offered-skills catalog), a `run_usage` summary, a claude-only per-turn `turns`
array, an ordered `steps` array (each `{kind, name, tool_id, content}` plus a `turn` index on the billed steps, where
`kind` is `tool_call` / `tool_result` / `assistant_message` / `user_message` and `content` is the redacted tool input,
tool result, or text turn — `name` / `tool_id` are `null` on the message turns), and the final `output`. `run_usage`
is the denormalized `UsageMetrics` (`models`, `input_tokens`, `output_tokens`, `cached_tokens`, `cache_read_tokens`,
`cache_write_tokens`, `turns` count, `cost_usd`, `cost_source`) minus `backend` (already on the record) — the run
headline, and the codex surface too, since codex has no per-turn detail. Each `turns[]` entry is one claude assistant
turn (`turn` index, `model`, `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`, and an
always-*estimated* `cost_usd` / `cost_source`); each billed `steps[]` entry (`assistant_message` / `tool_call`) carries
the same `turn` index tying it to its turn, while a `tool_result` / `user_message` step is a turn *input* and omits
`turn`. `build_record` drops every empty / `None` field, so an absent prompt, an empty system prompt, a no-trigger skill
set, or codex's empty per-turn array simply leaves its key off.

**Join keys.** The envelope and correlation context double as join keys back to the numeric sinks. `session_id` (the
live `result.session_id`) is the per-run key onto the [`agent_exit`](#agent_exit-records) analytics record and the
`agent_exit` audit event from the same run — both carry that same result id. The shared context `(repo, issue, stage,
agent_role, backend, review_round, retry_count)` lines up field-for-field with the analytics `agent_exit` record (the
audit events carry the same context under their own names, with backend as `agent`). The paired `agent_spawn` audit
event is **not** keyed by this `session_id`: its `session_id` is the *resume* session id, which is omitted entirely on a
fresh spawn and points at the prior session on a resume — so correlate the trajectory to the spawn through that shared
context, not `session_id`. Either way the heavy free-text trajectory body can be correlated back to the usage / cost /
token row for the same run without ever being stored alongside it — the whole point of keeping it in a separate file.

**Redaction and truncation caps.** Every free-text field — `user_input`, `system_prompt`, each step's `content`, and
`output` — is passed through `config.credentials.redact_secrets` (the same secret-shaped-env-value masker used on
agent stderr) **before** truncation, so a secret straddling an elided boundary cannot survive as two halves. Each field
is then head/tail truncated to its first `_TRAJECTORY_FIELD_HEAD` (`2000`) and last `_TRAJECTORY_FIELD_TAIL` (`2000`)
characters — declared by `trajectories/models.py`, republished under those private names on the analytics package,
which is where a caller shrinks one — with an `...[N chars elided]...` marker in between; the head keeps the
request/intent, the tail the
result/answer. The whole record is additionally bounded: each step is charged its full **serialized** size — the JSON
metadata (`kind` / `name` / `tool_id` / `turn`) plus its truncated content, not just `len(content)`, so even thousands
of empty- or metadata-only steps still consume the budget — and the per-turn `turns` array is charged **and
truncated** against the same budget (turns drawn down first, then steps), so a pathological claude run of thousands of
turns with no tool calls cannot write the whole array in full and blow the budget. Once the running total crosses
`_TRAJECTORY_RECORD_BUDGET` (`200_000`) bytes the remaining turns — then steps — are dropped and a `truncated: true`
flag is set; only the small fixed `run_usage` summary is always kept whole, so one pathological run (thousands of turns
or tool calls) cannot write an unbounded line. Non-string step content (claude tool inputs are dicts; `tool_result`
content a list) is redacted **leaf-by-leaf before** JSON serialization (`sanitize.redact_tree`) — serializing first
would escape a multiline secret's newlines into `\n`, leaving the literal `str.replace` in `redact_secrets` unable to
match the raw env value, so the secret would leak into the serialized content.

**Privacy contract — redaction is not anonymization.** The redactor masks only *secret-shaped* values: env vars whose
name is in the secret-key set or ends in a secret suffix, plus the resolved `GITHUB_TOKEN`, each verbatim occurrence
replaced with `***`. It deliberately does **not** strip issue or repository content. The prompt (`user_input`), the
`system_prompt`, every step's `content` in `steps` (tool inputs / results and the assistant / user text turns), and the
final `output` can — and routinely will — carry issue titles and bodies, quoted source from the worktree, file
paths, diffs, and the agent's own reasoning, all in cleartext after redaction. An enabled trajectory file therefore
carries the same sensitivity as the repositories the orchestrator works on; scope its filesystem permissions (and any
retention) accordingly. This is why the sink is off by default and why it never leaves the local filesystem (next
paragraphs).

**Opt-in, default off.** Unlike `ANALYTICS_LOG_PATH` (which defaults to `<LOG_DIR>/analytics.jsonl`),
`TRAJECTORY_LOG_PATH` defaults *off*: unset, empty, or `off` / `disabled` / `none` (case-insensitive) all disable it;
any other value is the explicit opt-in path. `TRAJECTORY_RETENTION_DAYS` defaults to `90` and mirrors
`ANALYTICS_RETENTION_DAYS` (non-positive keeps trajectories indefinitely).

**Append / prune discipline, dedicated lock.** `append_trajectory_record` reopens the file in append mode per record
after `mkdir(parents=True, exist_ok=True)`, downgrading `OSError` to a `log.warning`; `prune_trajectory_records(*,
now=None)` removes records older than `TRAJECTORY_RETENTION_DAYS` through a temp-file + `os.replace` rewrite, preserves
malformed / unparseable lines verbatim, and no-ops when the sink is disabled, retention is non-positive, or the file is
absent. Both reuse the shared append (`recording/io.py`) and prune (`retention_scan.py` / `retention_rewrite.py`)
cores but hold a **dedicated**
`threading.Lock`, so the trajectory file serializes its own append-vs-prune race without ever blocking against — or
touching — `ANALYTICS_LOG_PATH`, the analytics Postgres sync, or the dashboard. That lock is minted on
`recording/io.py`, beside the analytics sink's and for the same reason: `io.py` is loaded once per process while
`trajectories/api.py` is rebuilt for every analytics package instance, and a caller may hold an
`append_trajectory_record` it imported before any rebuild — a reference the rebuild never rebinds, whose own first call
is what triggers one. A lock re-minted with the append would leave that reference serializing against nothing while the
prune took the replacement, which is precisely the append-during-prune race the lock exists to close.

**No built-in rotation.** As with the audit and analytics sinks, each append reopens the file after `mkdir`; there is no
size cap, long-lived descriptor, or compression. `prune_trajectory_records` is **not yet wired into the polling loop**,
so beyond the by-age prune (which only an in-process caller drives today) retention and rotation are entirely
operator-managed — pair `TRAJECTORY_LOG_PATH` with `logrotate` (or equivalent). Because every append re-resolves the
path, create/rename or `copytruncate` rotation is safe between writes.

**Local filesystem only.** A trajectory record is never written to `ANALYTICS_LOG_PATH`, never replayed into Postgres by
`analytics.sync` (the sync only reads `ANALYTICS_LOG_PATH`), and never surfaced in the **analytics** dashboard
(`orchestrator/dashboard.py`), which renders only the Postgres rollup. The sink is one JSONL file on local disk; the
only reader is the dedicated trajectory viewer below, which reads that file straight off disk.

**Observation-only, like every surface here.** The polling tick never reads the trajectory file back and no dispatch
decision keys off it; workflow state lives entirely in the pinned `<!--orchestrator-state ...-->` JSON comment and the
workflow label. The file is therefore safe to truncate, rotate, or delete at any time without affecting workflow state
or correctness.

### Trajectory operator workflow

There is no trajectory equivalent of `python -m orchestrator.observability.analytics.sync.cli`: trajectories are
deliberately file-backed only, and the analytics Postgres schema does not ingest their free-text bodies. To browse
trajectories on another host, mirror `TRAJECTORY_LOG_PATH` as a file and run the dedicated viewer on that host with
`TRAJECTORY_LOG_PATH` pointing at the mirrored JSONL. Scope the remote path like source code or issue content:
redaction masks secret-shaped values, not repository text or agent reasoning.

For an unattended deployment, mirror the file with SSH-based tooling such as `rsync`. Use a dedicated receiver account
whose key can only write into the trajectory directory. On an Ubuntu receiver, use a neutral shared directory such as
`/srv/orchestrator` instead of landing the file in the receiver user's home. That keeps `/home/forsync` out of the
dashboard read path and lets the Streamlit user read through a shared group:

```sh
# On the remote VPS.
sudo adduser --system --group --shell /bin/bash --home /home/forsync forsync
sudo groupadd -f orchestrator
sudo usermod -aG orchestrator forsync
sudo usermod -aG orchestrator <dashboard-user>
sudo mkdir -p /srv/orchestrator
sudo chown forsync:orchestrator /srv/orchestrator
sudo chmod 2750 /srv/orchestrator
sudo install -d -m 700 -o forsync -g forsync /home/forsync/.ssh

# Confirm rrsync is available; on current Ubuntu it is shipped by rsync.
command -v rrsync
```

Generate a dedicated cron key on the source host:

```sh
ssh-keygen -t ed25519 -f ~/.ssh/forsync_ed25519 -C "trajectory-sync" -N ""
```

Then install the public key on the remote account as one `authorized_keys` line. Pick the network restriction that
matches the deployment:

- **Private overlay / Tailscale available.** Use the exact source host tailnet IP in `from=` when possible;
  `100.64.0.0/10` is the broader Tailscale CGNAT range. A tailnet ACL that allows only the source device to reach SSH on
  the VPS is stronger, with `from=` as defense-in-depth.
- **Public SSH / no Tailscale.** Use the source host's stable public egress IP or CIDR in `from=` instead. If the source
  IP is not stable, omit `from=` and restrict port 22 at the VPS firewall / cloud security group to the narrowest source
  range you can. Keep the forced `rrsync` command and `restrict` either way.

```text
command="/usr/bin/rrsync -wo -no-del /srv/orchestrator",restrict,from="<source-ip-or-cidr>" ssh-ed25519 AAAA... trajectory-sync
```

Lock the SSH account down further with `/etc/ssh/sshd_config.d/forsync.conf`:

```sshconfig
Match User forsync
    AuthenticationMethods publickey
    PasswordAuthentication no
    PermitTTY no
    AllowTcpForwarding no
    AllowAgentForwarding no
    X11Forwarding no
    PermitTunnel no
```

Validate and reload SSH:

```sh
sudo sshd -t
sudo systemctl reload ssh
```

A small source-side wrapper is easier to test than a heavily-quoted crontab line, lets cron fail fast when SSH would
otherwise prompt, and uses the same lock name as trajectory maintenance jobs so sync and prune never overlap each other.
With the `rrsync` root above, `DEST=forsync@<host>:trajectories.jsonl` lands at `/srv/orchestrator/trajectories.jsonl`
on the receiver. `rrsync` rejects absolute destination paths; keep the destination relative to its configured root:

```sh
#!/usr/bin/env bash
set -euo pipefail

SRC=/path/to/agent-orchestrator/logs/trajectories.jsonl
DEST=forsync@<host>:trajectories.jsonl
LOCK=/tmp/agent-orchestrator-trajectory.lock
KEY=/home/<local-user>/.ssh/forsync_ed25519

SSH_CMD="ssh -i $KEY -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=15 -o StrictHostKeyChecking=accept-new"

echo "=== $(date -Is) trajectory sync start ==="
if /usr/bin/flock -n -E 75 "$LOCK" \
  /usr/bin/rsync -az --timeout=120 --chmod=F640 \
    -e "$SSH_CMD" \
    "$SRC" "$DEST"; then
  echo "=== $(date -Is) trajectory sync done ==="
else
  rc=$?
  if [ "$rc" -eq 75 ]; then
    echo "=== $(date -Is) trajectory sync skipped: lock held ==="
    exit 0
  fi
  exit "$rc"
fi
```

Install it as executable before adding the cron entry:

```sh
chmod +x /path/to/agent-orchestrator/bin/sync-trajectories.sh
```

```cron
10 * * * * /path/to/agent-orchestrator/bin/sync-trajectories.sh >> /path/to/agent-orchestrator/logs/trajectory-sync.cron.log 2>&1
```

- `rsync` is a file mirror, not an append-only archive. When local retention later rewrites or shrinks the JSONL, a
  later mirror run will make the remote file match.
- The default `rsync` destination update path already writes a temporary file and renames it into place for this
  single-file mirror; avoid `--inplace`.
- Do not use `--append` or `--append-verify` for this mirror: retention pruning can shrink or rewrite the source file,
  and append-mode transfer would leave stale remote tail data or give remote readers partial in-place writes.
- `StrictHostKeyChecking=accept-new` is convenient on a trusted private network because the first cron-run pins the host
  key and later key changes still fail. The stricter alternative is to pre-seed once with `ssh-keyscan -H <host> >>
  ~/.ssh/known_hosts` and drop that option.
- `--chmod=F640` makes the mirrored file readable by the receiver owner and the shared `orchestrator` group. The setgid
  bit on `/srv/orchestrator` (`2750`) keeps replaced files in that group, so the dashboard user can read them after a
  fresh login / restarted service picks up its new group membership.
- If you migrate from an older `/home/forsync/...` landing path, move the existing file once (`sudo mv
  /home/forsync/agent-orchestrator/trajectories.jsonl /srv/orchestrator/`) and then apply `sudo chgrp orchestrator
  /srv/orchestrator/trajectories.jsonl && sudo chmod 640 /srv/orchestrator/trajectories.jsonl`.
- Verify dashboard readability before launching Streamlit: `id` for the dashboard user must show `orchestrator`, and
  `sudo -u <dashboard-user> head /srv/orchestrator/trajectories.jsonl` should print JSONL.
- If the remote host should keep a longer archive than the local machine, mirror to dated snapshots instead of one fixed
  destination path.
- Treat the remote SSH key as sensitive. For a write-only receiver, constrain it in `authorized_keys` with a forced
  `rrsync` command, no PTY / forwarding, and either a `from=` source restriction or network-level SSH allowlist.
- Rotate `trajectory-sync.cron.log`, or send the wrapper output to the journal with `logger`, so the cron log does not
  grow forever.

The mirror cron does not lock the source file against the running orchestrator. A record that is fully appended before
`rsync` reads the file is copied; a record appended during or after the transfer may be absent until the next mirror
run. If `rsync` ever catches a final line mid-write, the remote file may briefly end with a malformed JSON line after
the destination rename; the trajectory reader skips malformed lines, and the next mirror run repairs the fixed
destination because this command mirrors the whole file rather than using `--append`.

Decide whether the remote file is a **mirror** or an **archive** before enabling retention. A fixed destination path is
a mirror: after local retention prunes old records, the next sync shrinks the remote file too. That is correct for a
remote viewer that should show only the retained window, but wrong if the remote host is meant to preserve history
before the local file is pruned. For an archive, use a different strategy, such as dated snapshots, a never-pruned local
archive file, or a custom high-water-mark shipper.

Because `prune_trajectory_records()` is not called by the polling loop, drive trajectory retention explicitly when you
want `TRAJECTORY_RETENTION_DAYS` to affect the file. The value may live in `.env` like the other non-secret knobs; it is
parsed when the prune process imports `orchestrator.analytics`, which is why the recipe below names that package rather
than the `observability/analytics/retention.py` owner it forwards to. The cron entry relies on `.env` for both
`TRAJECTORY_LOG_PATH` and `TRAJECTORY_RETENTION_DAYS`, runs the prune helper, and logs how many records were removed:

```cron
25 0 * * * cd /path/to/agent-orchestrator && /usr/bin/flock -n -E 75 /tmp/agent-orchestrator-trajectory.lock /home/<user>/.local/bin/uv run python -c 'from orchestrator import analytics; print(f"trajectory prune removed {analytics.prune_trajectory_records()} record(s)")' >> /path/to/agent-orchestrator/logs/trajectory-prune.cron.log 2>&1
```

To make the same cron entry use a one-off retention window instead of `.env`, prefix the command with `env
TRAJECTORY_LOG_PATH=/path/to/agent-orchestrator/logs/trajectories.jsonl TRAJECTORY_RETENTION_DAYS=30`.

Only run this prune command while the orchestrator is stopped or otherwise guaranteed not to append trajectories. The
shared `/tmp/agent-orchestrator-trajectory.lock` serializes operator cron jobs with each other, but not with the live
orchestrator process: the lock the append and the prune share (minted on
`observability/analytics/recording/io.py`) is a process-local `threading.Lock`, not an interprocess file lock. An
external prune process can race with the live polling process and lose a record appended to
the old inode between the prune read and `os.replace`. Schedule pruning after at least one mirror run if the remote
fixed-path mirror should receive records before they age out locally. The prune rewrites only the trajectory JSONL
through the same temp-file + `os.replace` path described above; it never touches GitHub workflow state,
`ANALYTICS_LOG_PATH`, Postgres, or the analytics dashboard.

### Trajectory viewer (`orchestrator/apps/trajectory_dashboard.py`)

A deliberately **separate** Streamlit page from the analytics dashboard, launched the same way (`uv run streamlit run
orchestrator/apps/trajectory_dashboard.py`, opt-in `dashboard` group). The two pages stay apart on purpose: the
analytics dashboard reads the numeric usage / cost rollup from Postgres, while the viewer reads the JSONL trajectory
file **directly** — the trajectory bodies are never in Postgres — so an operator can browse trajectories with nothing
but the file on disk (no database, no `analytics.sync`).

**Read model (`orchestrator/trajectory_reader.py`).** A pure, import-light, Streamlit-free reader (the file-backed
analogue of `orchestrator/analytics/read.py`). `_trajectory_records.py` preserves the historical record API — the
`obj` / `seq` parse call shape included, which it binds against a declared signature and hands the owner as
`sequence` — and is where a caller's world is bound: the log path, the banner, and the read each hand the owner the
analytics package that leaf captured at its own import, so a reload isolates a reader and a patch on that package
intercepts every read made through it. The record vocabulary (`constants`), the field coercion under it (`coercion`),
the immutable sub-views (`models`), the run model (`runs`), the usage and timeline/label views bound onto it
(`usage_views`, `timeline_views`), the parse above them (`parsing`), the file read that drives it (`reading`), the
log-path resolution beside it (`log_paths`, over `analytics/config.py`), the filter shapes, values, and run matching
over the runs it returns (`filter_models`, `filter_values`, `filtering`), and the headline counts they are totalled
into (`summaries`) live under `orchestrator/observability/trajectory_viewer/`, alongside the inline HTML that read is
drawn with (`css`, `summary_html`, `run_html`, `usage_html`, `timeline_html`); the eleven root-level leaves the read
model moved off and the five the HTML moved off forward every historical name to those owners' own objects, and the
views and the record still report `orchestrator._trajectory_records` as their module. `trajectory_reader` defines
none of it: it is the one import site the page and every historical caller reach the whole read model through,
binding the record API off a freshly loaded `_trajectory_records` (so a reload still isolates a reader) and the
filter and summary API off the owners, with `FilterOptions`, `RunFilterOptions`, and `TrajectorySummary` still
reporting `orchestrator.trajectory_reader` as their module — which is also why it imports the typing names those
three are annotated in and uses them for nothing else: `get_type_hints` resolves a class's annotations in the globals
of the module it names. Together they read `TRAJECTORY_LOG_PATH`, parse each `agent_trajectory`
record into a frozen `TrajectoryRun` (with a normalised `TrajectoryStepView` per step), and expose `read_trajectories`
(newest first by `ts`, file order as the tie-break), `filter_options`, `filter_runs` (repo / backend / agent-role /
stage / issue / free-text-search, every filter conjunctive and an empty multi-value meaning "no constraint", plus an
opt-in `exclude_fixtures`), and `summarize`. Each run exposes a normalised, vintage-agnostic `timeline` — the leading
`user_input` prompt, then the ordered `steps[]`, then the final `output`, as one ordered `TimelineEntry` sequence — so
an old steps-only record (only `tool_call` / `tool_result` steps) and a new record whose steps interleave
`assistant_message` / `user_message` text turns render the same way; `tool_calls` still counts only `tool_call` steps,
so the text turns never inflate the tally. `is_fixture` flags the synthetic test-suite records an inherited file may
carry (the sentinel prompt `ignored`, a `sess-*` session id, or a `Skill`-only run), which
`filter_runs(exclude_fixtures=True)` drops. Each run also exposes the record's usage: a `run_usage` (`RunUsageView`) run
summary and a claude-only per-turn `turns` tuple (`TurnUsageView`), with convenience accessors `model` (first of
`run_usage.models`), `cost_usd` / `cost_source` (the authoritative run figure), `total_tokens`, and an O(1)
`usage_for_turn(idx)` lookup so a `TimelineEntry` (which now carries the producing step's `turn` index) can find its
turn's usage while walking the timeline; `summarize` adds `total_cost_usd`, the summed run cost over runs that recorded
one. A pre-usage record parses with `run_usage=None`, `turns=()`, and every `step.turn=None`, so it renders exactly as
before. The same resilience contract the rest of the codebase honours holds: a missing / disabled path, a malformed
line, a non-`agent_trajectory` record, or a renamed field yields a smaller result, never an exception. A file that is
there but cannot be read — anything raising an `OSError` other than `FileNotFoundError`, an unreadable file or a
directory in the knob's place — takes the same empty result with a warning first, through the
`orchestrator.trajectory_reader` logger. That name is spelled out literally in
`observability/trajectory_viewer/reading.py` rather than derived from the module path, so an operator's log filter
selects on it regardless of which module the read lives in. The records are
already redacted and truncated by the sink, so the viewer is a read-only window onto an already-sanitised file — it
adds no redaction of its own and must be scoped (filesystem permissions, who can reach the Streamlit port) with the same
care as the trajectory file itself.

**Page (`orchestrator/apps/trajectory_dashboard.py`).** Reuses the analytics dashboard's theme (CSS variables, fonts,
`fmt_*` formatters) so the two pages read as one family — the owners under `observability/trajectory_viewer/` name
`dashboard/tokens.py`, `dashboard/css.py`, and `dashboard/formatting.py` directly, the leaves still flat reach the same
objects through `orchestrator/dashboard_theme.py` — and reuses `dashboard/filters.py`'s `parse_issue_number` for the
issue filter, so `#123` and `123` mean the same thing on both pages. Streamlit is
imported lazily inside `main()`, alongside every owner the page composes, and the repo-root `sys.path` shim comes
from `orchestrator/apps/bootstrap.py` (`ensure_repo_root_on_path`) — the historical launch path takes the same shim
from `orchestrator/script_launch.py`, which `orchestrator/dashboard.py` also calls. Importing either module (or the
polling tick) therefore never needs the `dashboard` group — `tests/apps/` guards the lazy-import and the
script-launch `sys.path` shape on both of the viewer's launch paths. The layout is intentionally minimal-but-useful: a
sidebar of filters (plus a *Hide synthetic fixtures*
toggle that drives the reader's `exclude_fixtures`, off by default), a topbar + five-tile KPI strip (runs / issues /
repos / tool calls / total cost, the last summed from `summarize`'s `total_cost_usd`), a foldable *Recorded runs*
overview table (capped at the 200 most recent; collapse the expander to focus on a single run), three cascading run
pickers (repo → issue → the run's `detail_label` cohort — stage/role · backend · round · timestamp) that
together still reach every match, and a per-run detail card that lists the offered tools and triggered / available
skills — the triggered-skills row always renders, marked `none` when no skill fired so a run that used no skill is
distinguishable from an omitted row, while the offered-tools and available-skills rows are dropped when empty — a
run-level usage / cost row (model(s), token buckets, turn count, and the authoritative run cost tagged with
its `cost_source` — the codex surface too), then walks the run's normalised `timeline` as one ordered sequence — the
redacted prompt, then the interleaved assistant / user text turns and tool calls / results (each rendered by its
`kind`), then the final output (rendered as markdown; every other entry is shown verbatim in a code block). For a claude
run, a compact per-turn usage strip (model · in / out tokens · cache-read / cache-write · estimated cost, with a
*cache hit* chip when the turn read from cache) is drawn at each assistant-turn boundary in the timeline; the copy
states that per-turn figures are claude-only estimates that need not sum to the authoritative run total, and that
entries without a strip (tool results, user turns) are turn inputs billed on the next turn. A pre-usage record carries
no usage, so the row and strips are absent and it renders exactly as before. The fixtures `is_fixture` flags are tagged
in the overview table and the run-level picker (the `[fixture]` prefix rides the run option; and the detail card carries
a notice) so the operator can tell the inherited test-suite records from real runs even with the toggle off. When the
sink is off it renders the opt-in banner and stops; an empty file or an empty filter set renders an explanatory notice
rather than a blank page. `orchestrator/trajectory_dashboard.py` stays the historical launch path and a lazy
compatibility facade over it, resolving the two page renderings on `page_render` and `main` on the app.
The page state, setup, filters, picker, selected-run rendering, and whole-page composition are owned by
`page_models`, `page_setup`, `controls`, `picker`, `run_render`, and `page_render` under
`observability/trajectory_viewer/`; the five that draw take Streamlit in
as an argument rather than importing it, so none of them puts the `dashboard` group behind an import, and
`page_models` is plain frozen state that never sees it. The facade's bootstrap is still a flat
`_trajectory_dashboard_*` leaf. The historical `_trajectory_dashboard_html.py` surface defines nothing and composes
the Streamlit-free summary, run, usage, timeline, and CSS owners under `observability/trajectory_viewer/`, so every
established HTML helper and patch point keeps its original identity without pulling Streamlit into imports. The
`_trajectory_dashboard_page.py` leaf keeps the historical zero-argument page setup and is where a caller's analytics
world is bound onto the owner's settings-holder argument, the same way `_trajectory_records.py` binds it for the read.

## Analytics database (`analytics-db/`)

Local Postgres service that is the aggregation target for the JSONL sink. The service contract and schema are
operator-deployed via Docker compose; the JSONL→Postgres replay and the CLI the operator drives it through are both
owned by `orchestrator/observability/analytics/sync/` — NOT wired into the polling tick. Orchestrator correctness must
not depend on database availability.

### Service layout

[`../analytics-db/compose.yml`](../analytics-db/compose.yml) brings up a single `postgres:16` container with the data
directory on a host bind (`./data`, gitignored) and the init directory mounted read-only. The port binding is pinned to
`127.0.0.1` so the database is unreachable off-host regardless of firewall configuration; re-binding to `0.0.0.0` is
intentionally a code change rather than an env-var change. Credentials default to `orchestrator` / `orchestrator` and
are overridable via `analytics-db/.env` (`POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_PORT`).
`docker compose` reads `.env` from the compose-file directory, not the orchestrator root.

```sh
cd analytics-db
docker compose up -d                  # start the local service (data lives in ./data, gitignored)
docker compose down                   # stop the container; data on the ./data bind mount is preserved
docker compose down && rm -rf ./data  # stop and wipe history (the bind is a host directory, so `down -v` does NOT remove it)
```

To apply or re-apply the schema against an already-running compose service:

```sh
cd analytics-db
docker compose exec -T analytics-db sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /docker-entrypoint-initdb.d/01-schema.sql'
```

### Endpoint shape

The sync reads a single libpq URL — `ANALYTICS_DB_URL` (default unset, example
`postgresql://orchestrator:orchestrator@127.0.0.1:5432/orchestrator_analytics`) — rather than separate host / port /
user / password variables. Moving the database off-host later (managed Postgres, a different VM, a unix socket) is a
one-line repoint. Empty value and the sentinels `off` / `disabled` / `none` (case-insensitive) disable the sync,
matching `ANALYTICS_LOG_PATH`.

### Schema

[`../analytics-db/init/01-schema.sql`](../analytics-db/init/01-schema.sql) defines:

- **`analytics_events` table.** Columns mirror the JSONL record shape produced by `analytics.build_record`. `ts`,
  `repo`, `issue`, `event` are `NOT NULL`; everything else is nullable so any record across the three event kinds is a
  valid row. An `extras JSONB` column captures any field added to `build_record` before the DDL knows about it — the
  opt-in skill fields (`skills_triggered` / `skills_triggered_count` / `skills_available`, the per-load
  `skills_evidence` tier map, and the `skills_incidental` / `skills_incidental_count` path-only references) are exactly
  such additions, so they need **zero DDL**: an operator-deployed database ingests them the moment
  `TRACK_SKILL_TRIGGERS` is enabled, with no migration and no schema reapply. `source_path` / `source_line` are forensic
  context; the authoritative dedup key is `content_hash` — SHA-256 over the canonical (`sort_keys=True`) JSON form of
  the record.
- **Indexes.** A plain (non-partial) unique index on `content_hash` plus `INSERT ... ON CONFLICT (content_hash) DO
  NOTHING` makes repeated sync runs idempotent. Additional indexes cover the expected query dimensions: `ts`; `(event,
  ts)`; `(repo, issue)`; a partial index on non-null `stage`; per-event-kind partial indexes on `(repo, ts DESC)` for
  `event='agent_exit'` and `event='stage_enter'`; and a composite `(event, repo, stage, ts)` index.
- **`analytics_daily_rollup` materialized view.** Keyed on `(day, repo, issue, event, stage, backend, cost_source)` and
  carrying the aggregates the dashboard's window-bounded widgets need without re-scanning `analytics_events`: token
  totals (`total_input_tokens`, `total_output_tokens`, `total_cached_tokens`, `total_cache_read_tokens`,
  `total_cache_write_tokens`), `total_cost_usd`, `duration_s_sum` + `duration_s_count` (so consumers recover
  `AVG(duration_s)` as `sum / count`), `failed_count` (rows with non-NULL non-zero `exit_code`), `timed_out_count`
  (scoped to `event='agent_exit'` with `timed_out=TRUE`), and `event_count`. `day` is `(ts AT TIME ZONE 'UTC')::date`. A
  unique index on the full key (`NULLS NOT DISTINCT`, Postgres 15+) backs the rollup; a `(day, repo)` supporting index
  keeps `WHERE day BETWEEN x AND y` predicates on a range scan.
- **`analytics_agent_runs` view.** `CREATE OR REPLACE VIEW` over `event = 'agent_exit'` rows that promotes derivations:
  `model` from `COALESCE(models->>0, 'unknown')`, `total_tokens` = `input + output`, `total_cache_tokens` = `cached +
  cache_read + cache_write`, a categorical `review_round_bucket` (`0`, `1`, `2`, `3-5`, `6+`), `failed = exit_code <> 0`
  (NULL preserved), and `has_cost = cost_usd IS NOT NULL` (true for `cost_source` in {`reported`, `estimated`}). Raw
  nullable columns pass through alongside derived ones; `cost_source` passes through verbatim.

The init script runs once when the data volume is empty. `IF NOT EXISTS` guards plus trailing `ALTER TABLE ... ADD
COLUMN IF NOT EXISTS` / `CREATE UNIQUE INDEX IF NOT EXISTS` for `content_hash` keep it idempotent for the
operator-driven case (`psql -f` against an existing instance) and migrate a pre-`content_hash` data volume without
dropping data. MV column changes require `DROP MATERIALIZED VIEW analytics_daily_rollup` followed by a reapply; the
sync's refresh hook does NOT recover from a column mismatch.

### Sync CLI (`orchestrator/observability/analytics/sync/cli.py`)

The command lives here — the argument parser, the UTC-pinned log formatter, the stdout summary, and the exit code —
over the replay `orchestrator/observability/analytics/sync/run.py` owns. Run on demand:

```sh
uv run python -m orchestrator.observability.analytics.sync.cli   # uses configured env vars
uv run python -m orchestrator.observability.analytics.sync.cli --log-path /path/to/rotated.jsonl --db-url postgresql://other/db
```

`python -m orchestrator.analytics.sync` still starts the same run and is kept working for schedulers that already
spell it that way, but it is a temporary forwarder — new cron entries and scripts should name the module above.

**Batched inserts.** Reads `ANALYTICS_LOG_PATH` line by line, accumulates validated row tuples into a buffer sized by
`sync/ingest.py`'s `BATCH_SIZE` (default 500), and flushes each full batch via `cur.executemany("INSERT ... ON CONFLICT
(content_hash) DO NOTHING", batch)`. A multi-thousand-record replay pays one Postgres round-trip per batch instead of
one per row. A final partial batch is flushed at EOF so the tail still lands. The size is read off the owner as a pass
starts, so a caller that pins a smaller buffer drives the loop that actually runs.

**Pre-check dedup.** Before opening the input file the sync issues a single `SELECT content_hash FROM analytics_events
WHERE content_hash IS NOT NULL` and pulls the result into a Python set, so already-present rows are filtered out before
they enter the batch. Newly queued hashes are added to the same set as the loop iterates, so two identical records
inside one JSONL file are deduped against each other before reaching `executemany`. The pre-check reads from the unique
`analytics_events_content_hash_idx`. The server-side `ON CONFLICT (content_hash) DO NOTHING` arbiter stays the
authoritative dedup backstop for racing concurrent writers.

**Counters.** Per-batch `cur.rowcount` drives the cumulative `inserted` / `skipped_duplicate` totals. Duplicates =
`len(batch) - rowcount` for wire-side skips, plus the pre-skip counter for in-Python skips.

**Malformed-line tolerance.** Blank lines are silently skipped; lines that are not valid JSON, JSON that is not an
object, records missing one of the required (`ts` / `repo` / `issue` / `event`) keys, or carrying an unparseable `ts`
are counted as skipped and logged but never enter the batch buffer. The JSONL file is treated as read-only — the sync
never rewrites or truncates it, even when it sees malformed lines. Naive timestamps are interpreted as UTC.

**Transaction shape.** A `psycopg` driver-level error inside a batch flush rolls the transaction back and propagates so
the CLI exits non-zero rather than reporting "success" on a half-inserted run. After the insert transaction commits, the
sync issues `REFRESH MATERIALIZED VIEW analytics_daily_rollup` (non-concurrent) and commits again so the rollup-backed
dashboard widgets catch up. The refresh fires unconditionally on every successful commit — including all-duplicates
and all-malformed runs — so rerunning the sync is the documented recovery path for a stale rollup. A refresh exception
(MV not migrated yet, transient Postgres error, lock-wait timeout) is logged via `log.exception` and swallowed; the
committed inserts are durable, and the next sync's refresh recovers the rollup.

**No-op modes.** `sync_jsonl_to_postgres` is a no-op (no connection attempt, no row insertion, no error) when
`ANALYTICS_DB_URL` is unset or disabled, when `ANALYTICS_LOG_PATH` is explicitly disabled (note that the env var
defaults to `LOG_DIR/analytics.jsonl`, so only the empty value or `off` / `disabled` / `none` turns it off), or when the
JSONL file is absent. The CLI is safe to schedule before the operator deploys Postgres. The driver is `psycopg[binary]`;
the import is lazy inside the connect helper so the module load path remains driver-free for callers that only need
`SyncResult`.

**Module ownership.** Everything above is owned by `observability/analytics/sync/`, split by boundary. `columns.py`
owns the promoted / JSONB / required column inventory; `records.py` owns canonical JSON, `content_hash`, the coercion
each required field is narrowed by, and the routing of everything else into `extras`; `rows.py` validates one line,
builds the INSERT, and lays out the positional tuple that fills it. Those three are driver-free, so a caller can hash a
record or build a row with no psycopg installed. `models.py` owns `SyncResult` and the mutable tallies behind it,
`ingest.py` the pre-check, the in-file skip set, the batched flush, and the progress and malformed records,
`database.py` the lazily imported driver plus the quiet rollback / close and the rollup refresh, `redaction.py` the
credential stripping, `run.py` the resolved request, the no-op gate, the transaction shape, and
`sync_jsonl_to_postgres` itself, and `cli.py` the arguments, the UTC-pinned logging, the stdout summary, and the exit
code. `orchestrator/analytics/sync.py` and the nine flat `_sync_*.py` leaves implement none of it: they are forwarders
answering the historical names — private spellings included — with those owners' own objects, and `sync.py` keeps
working as an `-m` target on top of that.

### Operator feedback

The sync surfaces feedback through one logger and the stdout summary. Every owner under
`observability/analytics/sync/` writes to `orchestrator.analytics.sync`, spelled out literally rather than derived
from the module path, so an operator's log filter keeps selecting the whole replay regardless of which module a line
comes from:

- Every log line is timestamped (UTC, with an explicit `UTC` suffix) via `configure_cli_logging`'s `%(asctime)s`
  formatter and `formatter.converter = time.gmtime`.
- A `connecting to <redacted-url>` / `connection established` pair brackets the connect call so a remote-Postgres
  reachability problem surfaces immediately.
- A `progress lines=N inserted=… duplicate=… malformed=… elapsed=…s` record drops after each batched
  `executemany` flush, so the progress cadence is the 500-row `BATCH_SIZE` itself.
- A final `completed in %.3fs (…)` line carries the wall-clock total.
- The CLI prints a UTC-stamped stdout summary at the end carrying `inserted=` / `duplicate=` / `malformed=` /
  `total_lines=` / `duration_s=`.
- `ANALYTICS_DB_URL` credentials are stripped before logging — both the `user:password@` netloc form and the libpq
  query-string form (`?user=`, `?password=`, `?sslpassword=`, `?passfile=`, case-insensitive per libpq parameter-name
  rules) collapse to `***`.

### Operator workflow

Run `uv run python -m orchestrator.observability.analytics.sync.cli` on whatever cadence you prefer; `--log-path` and
`--db-url` override the env values for one-off replays of archived JSONL files. The default cadence is operator-chosen
because the JSONL sink is already the authoritative analytics surface on disk — the database is for aggregation and
reporting, not durability.

For an unattended deployment, drive the sync from `cron`. A typical entry runs hourly, guards against overlap with
`flock`, and captures output:

```cron
00 * * * * cd /path/to/agent-orchestrator && /usr/bin/flock -n /tmp/agent-orchestrator-analytics-sync.lock /home/<user>/.local/bin/uv run python -m orchestrator.observability.analytics.sync.cli --log-path /path/to/agent-orchestrator/logs/analytics.jsonl --db-url 'postgresql://<user>:<password>@<host>:<port>/<database>' >> /path/to/agent-orchestrator/logs/analytics-sync.cron.log 2>&1
```

- `cd /path/to/agent-orchestrator` so `uv run` finds the project's `pyproject.toml`.
- Absolute `/home/<user>/.local/bin/uv` because cron's `PATH` does not include `~/.local/bin`.
- `flock -n` makes the run a no-op when a previous invocation is still holding the lock, so a long replay never overlaps
  with the next tick.
- `--log-path` and `--db-url` are explicit CLI overrides, so the cron entry does not depend on `.env` being loadable
  from cron's environment.
- `>> ...analytics-sync.cron.log 2>&1` keeps stdout and stderr in the project log area instead of routing failures to
  local `mail`.

### Read model (`orchestrator/analytics/read.py`)

Thin, testable data-access layer over `analytics_events`, the `analytics_agent_runs` view, and the
`analytics_daily_rollup` materialized view. The dashboard's window-bounded aggregates read from the rollup; per-row
drill-downs and widgets the rollup cannot reconstruct exactly stay on the base table or the agent-run view. The module
is Streamlit-free so the read path can be wired into any UI.

`read.py` is a manifest-backed lazy facade with a complete `read.pyi`; it owns no query helpers and preserves the exact
historical object identity, wildcard surface, and `from` imports. The raw, rollup, breakdown, and skill reads are
owned by `raw_reads.py`, `rollup_reads.py`, `breakdown_reads.py`, and `skill_reads.py` with the projection owners
beside them under `observability/analytics/query/`, and the frozen result models every family returns by the five
result-family owners there; `read_raw.py` with the seven raw `_read_*` leaves beneath it, `read_rollup.py` with the
seven rollup `_read_*` leaves beneath it, `read_dashboard.py` with the nine breakdown and skill `_read_*` leaves
beneath it, and `read_models.py` with the `read_models_*` modules beside it, forward the historical names to those
owners' own functions and classes. In-repository callers name an owner rather than that forwarding: the three
skill-panel adapters in `observability/dashboard/skills.py` reach `skill_reads.py` directly, the six comparison-panel
adapters in `observability/dashboard/breakdowns.py` reach `rollup_reads.py` and `breakdown_reads.py` the same way, and
the seven headline and lifecycle adapters in `observability/dashboard/rollups.py` reach those two plus `raw_reads.py`
and the `SORT_BY_COST` spelling `issue_summaries.py` declares, so `analytics.read` stays a compatibility surface for
those sixteen rather than a hop the page depends on.

The shared call boundary is a `ReadRequest` composed of `ReadFilters`, `ReadConnection`, and `ReadOptions`, declared by
`observability/analytics/query/request_models.py`. Its sibling `requests.py` binds every historical keyword signature
into that typed request before the family leaf executes, so existing calls and error behavior are unchanged while
implementation helpers no longer thread large argument lists. Every family leaf reaches `execution.py`'s `ReadQuery`
for the connection inputs one read carries. Both connection paths resolve a caller's omitted `db_url=` through
`observability/analytics/config.py`'s `resolve_db_url`, so the URL-source policy has one home.

**Input owners.** `filters.py` owns `WindowFilters` — the selection a read narrows by, plus the three scoped
projections (`without_events` for a view with no `event` column, `catalog_scope` for repo-level catalog rows,
`historical_scope` for a session's evidence from before the window) — and the builder that accumulates a clause and its
bindings together. `predicates.py` owns the one `WHERE` builder behind all three scan targets, so the events table, the
agent-run view, and the daily rollup read a filter the same way. `conditions.py` owns the two splices that add a
table's own required condition to either end of a generated clause (which fixes whether its operand binds first or
last) and `agent_event_excluded`, the probe view-backed readers short-circuit on.

**Connection owners.** `connections.py` decides what a read dials with — the deferred psycopg import, the per-query and
persistent connect factories over it, `AnalyticsReadError`, and the two judgments a caller makes about a socket rather
than a query (whether a close failed, whether an escaped error means the socket is gone). `connection_cache.py` decides
how long a socket lives: the thread-local entry, the URL it is keyed on, the two evictions, and the
`analytics_connection` / `close_thread_local_connection` pair over them. `execution.py` decides whose connection a
SELECT runs on, and closes only the descriptor it opened itself.

**Result owners.** One module per result family, each a plain frozen-dataclass module that reaches nothing — importing
a row never costs a connection factory, the configuration behind an omitted `db_url=`, or the driver behind those.
`activity_models.py` owns the time-bucketed cells (`BackendDailyTokensRow`, `HourlyHeatmapPoint`, `ThroughputDayRow`);
`overview_models.py` what a page frames a window with — `FilterOptions`, `DataExtent`, and `Summary` construct bare so
an unset `ANALYTICS_DB_URL` still renders a page, while `TimeSeriesPoint` requires the `(day, event, count)` key its
cost and token aggregates hang off; `cost_models.py` the spend breakdowns
(`ReviewRoundBucketRow`, `BackendEfficiencyRow`, `RepoBreakdownRow`, `CostCoverageRow`); `run_models.py` the run,
issue, and traced-event rows (`StageBreakdown`, `EventBreakdown`, `AgentExitRow`, `IssueSummaryRow`, `IssueEventRow`)
plus `public_event_result`, the accessor installed as the trace row's `result` property over its stored `event_result`
column; and `skill_models.py` the skill cells (`SkillTriggerRateRow`, `SkillTriggerMatrixRow`, `SkillAdoptionRow`) with
the zero-denominator-guarded share each derives.

**Raw-read owners.** `raw_reads.py` owns the six reads that stay on `analytics_events` rather than the day-bucketed
rollup above it — `get_filter_options`, `get_data_extent`, `get_event_breakdown`, `get_recent_agent_exits`,
`get_issues`, and `get_issue_events`. It also decides the answers that need no database: an unconfigured URL with no
caller-owned `conn=`, a non-positive `limit`, and a cleared multiselect each return the empty result without dialing,
while an unknown `sort_by` raises before the connect. Each read hands its filtered window to a projection owner:
`filter_options.py` (the tagged union behind the five dropdowns, plus the in-Python bucketing and sort it is read back
through), `event_breakdowns.py` (the per-event count), `agent_exits.py` (the pinned `event = 'agent_exit'` spliced
ahead of the generated predicate, so its operand binds first and the `LIMIT` last), `issue_summaries.py` (the
per-`(repo, issue)` aggregate scan, `SORT_BY_LAST_SEEN` / `SORT_BY_COST`, and the SQL ordering each becomes), and
`issue_events.py` (one issue's trace, `ORDER BY ts ASC, id ASC`). Beneath them, `query_rows.py` names the columns of
the three SELECT lists read back by field rather than by index — recent exits, issue summaries, review-round buckets.
The latter two pad a row shorter than the list to the full width, which is what lets an older, narrower fixture
round-trip with its missing columns unset; the recent-exit row unpacks strictly, so a row short of its fifteen columns
raises. `raw_values.py` owns the NULL-preserving scalar coercions plus the probe for a cleared multiselect.

**Rollup-read owners.** `rollup_reads.py` owns the seven reads that scan `analytics_daily_rollup` instead —
`get_summary`, `get_kpi_prev`, `get_time_series`, `get_stage_breakdown`, `get_backend_efficiency`,
`get_repo_breakdown`, and `get_throughput_breakdown`. A window bounded by whole days is what they have in common, and
what lets them read the rollup rather than a row's own `ts`. It decides the same no-database answers the raw hub does,
plus the agent-run event-filter short-circuit `get_backend_efficiency` returns on. One projection owner sits under
each read: `summary_queries.py` (the `WITH win AS (...)` CTE and its three `UNION ALL` branches) with
`summary_results.py` beside it (the in-Python `count DESC, label ASC` ranking, and the cast list that leaves a short
totals row's trailing fields at their model defaults), `kpi_totals.py` (the trimmed previous-window scalars),
`time_series.py` (the per-`(day, event)` cell), `stage_breakdowns.py`, `backend_efficiency.py`, `repo_breakdowns.py`,
and `throughput_days.py` (the `done` / `rejected` terminals, the stage-selection intersection, and the two
short-circuits that leave nothing to count).

**Breakdown-read owners.** `breakdown_reads.py` owns the remaining four, the ones whose grouping key the rollup threw
away — `get_review_round_breakdown`, `get_cost_coverage`, `get_backend_daily_tokens`, and `get_hourly_heatmap`. The
first three read per-run facts a day bucket aggregated over, so they scan `analytics_agent_runs`; the fourth needs the
hour that bucket rounded off, so it stays on `analytics_events`. It decides the same unconfigured-database answer the
other two hubs do, and the agent-run event-filter short-circuit applies to the three view-backed reads only — the
heatmap's scan has an `event` column, so the selection becomes an ordinary bound predicate there instead. One
projection owner sits under each: `review_rounds.py` (the bucket labelling, the two roles, and each role's cache /
no-cache split), `cost_coverage.py` (the per-source rollup that keeps `unknown-price` distinct from `unknown`),
`backend_tokens.py` (the per-`(day, backend)` token cell), and `hourly_heatmaps.py` (the UTC normalization and the
bound offset).

**Skill-read owners.** `skill_reads.py` owns the last three — `get_skill_trigger_rates`, `get_skill_trigger_matrix`,
and `get_skill_adoption`. Their fact is not a column: a skill name, a repository's offered set, and one run's load
count ride in an `agent_exit` row's `extras` JSONB, which neither the rollup nor the agent-run view carries. All three
therefore scan `analytics_events` and pin `conditions.py`'s `AGENT_EXIT_CONDITION` themselves, so an events selection
that excludes `agent_exit` returns without dialing rather than running a query whose two conditions contradict; the
two capped reads pass a non-positive `limit` through as "every cell". One aggregate owner sits under each:
`skill_trigger_rates.py` (the whole-cohort denominator, the key-presence probe, and the summed trigger count),
`skill_matrices.py` (the repository-scoped catalog scan, the window-scoped runs scan, and the zero-padding between
them), and `skill_adoption.py` (the per-session ratio and the invocation / load / incidental diagnostics beside it).
Beneath the last, `skill_sessions.py` owns the resume-then-session-then-row-id session key and the two scans' scopes —
the window one picks which sessions count, the history one drops the start bound and the stage filter while keeping
the end bound. Beneath both aggregates, `skill_values.py` owns the JSONB name-array coercion, the
`(repo, role, backend)` cohort with its `"unknown"` bucketing, and the matrix ranking.

Beneath the rollup and breakdown families, `cache_shares.py` owns the token-share SQL the cache / no-cache split is
weighted by — spelled once for the rollup's `total_*` sums and once for the agent-run view's per-run columns — and
`row_cells.py` the readings a cell from any family passes through: a positional read with a default for a row
narrower than the SELECT list, a nullable cost column read as a float, and a driver-widened `day` narrowed back to a
date. The NULL-preserving float coercion the stage and backend projections share is `raw_values.py`'s, so both sides
of the read path narrow a nullable duration the same way.

- `get_summary` (rollup) — date-bounded totals + per-event / per-stage breakdowns + token / cost sums, plus
  `total_agent_runs` / `failed_agent_runs` / `timed_out_agent_runs` scoped to `event='agent_exit'`. `distinct_issues` is
  `COUNT(DISTINCT (repo, issue))`. Single round-trip via `WITH win AS (...)` CTE with three `UNION ALL` branches tagged
  by a `kind` discriminator.
- `get_kpi_prev` (rollup) — stripped variant of `get_summary` returning only the cost / token / agent-run scalars the
  dashboard reads off `prev_summary` for KPI deltas. Skips the `COUNT(DISTINCT)`s and `GROUP BY` follow-ups; ~one
  aggregate scan instead of three.
- `get_time_series` (rollup) — daily `(day, event, count)` rollups with per-cell cost / input / output / cache_read /
  cache_write token aggregates.
- `get_stage_breakdown` (rollup) — per-stage counts + weighted `AVG(duration_s)` recovered as `SUM(duration_s_sum) /
  NULLIF(SUM(duration_s_count), 0)`, rolled-up cost / token totals, and a `runs` agent-exit subset count. The total cost
  is further split into cache vs no-cache (`cache_cost_usd` + `no_cache_cost_usd`); each rollup row's `total_cost_usd`
  is weighted by `(total_cached_tokens + total_cache_read_tokens + total_cache_write_tokens) / (total_input_tokens +
  total_output_tokens + total_cache_read_tokens + total_cache_write_tokens)` into the cache stack and the complement
  into no-cache. `total_cached_tokens` is the Codex "portion of input served from cache" counter and is already inside
  `total_input_tokens`, so it stays out of the denominator to avoid double-counting. Token-less rollup rows attribute
  their full cost to no-cache.
- `get_repo_breakdown` (rollup) — per-`repo` rollup of issues / events / agent-exits / cost.
- `get_backend_efficiency` (rollup) — per-backend runs / failed / avg duration / cost / token totals with NULL
  backends surfaced as `"unknown"`. `event = 'agent_exit'` is pinned in the WHERE clause.
- `get_throughput_breakdown` (rollup) — daily resolved / rejected counts over `stage_enter` rows whose `stage` is
  `done` or `rejected`. Short-circuits when the events multiselect excludes `stage_enter` or the stages selection
  excludes both terminals.
- `get_filter_options` (base table) — distinct repos / events / stages / backends / agent_roles for dropdowns. All
  five columns pulled in a single `UNION`'d round-trip with rows tagged by their column.
- `get_data_extent` (base table) — min / max `ts` so the sidebar date picker defaults to a window that contains rows.
- `get_event_breakdown` (base table) — per-event counts (the rollup pre-aggregates more finely than `event` alone, so
  the base-table read is cheaper here).
- `get_recent_agent_exits` (base table) — newest rows filtered to `event='agent_exit'`.
- `get_skill_trigger_rates` (base table) — per-`(agent_role, backend)` skill-trigger aggregate: `runs`, `skill_runs`
  (rows whose `extras` carries a `skills_triggered` key), and `total_triggers` (`SUM` of `skills_triggered_count`), with
  a derived `rate` property. Reads the base table because the skill fields live in `extras JSONB`, which the rollup does
  not carry — no DDL. `event = 'agent_exit'` is pinned and the agent-exit event-filter short-circuit applies. NULL
  `agent_role` / `backend` bucket under `"unknown"`. A `0` rate is a real "no trigger observed" signal but cannot tell a
  tracked-but-quiet run from one whose `TRACK_SKILL_TRIGGERS` was off.
- `get_skill_trigger_matrix` (base table) — per-skill × `(repo, agent_role, backend)` trigger-run matrix. Two
  base-table reads combined in Python: the `repo_skill_catalog` records (the `skills_available` universe a repo offers;
  date/repo-filtered only, since those records are repo-level with `issue = 0` / NULL stage) and the filtered
  `agent_exit` rows (each run's `skills_triggered` list). Each cell carries `skill_runs` (runs *containing* the skill,
  one per run per distinct name — not total invocations) and `runs` (the total agent-exit runs in the cell's cohort,
  so a low/zero trigger count reads against the cohort size). Every catalog skill is zero-padded across the cohorts
  observed for its repo so the matrix carries explicit "offered but never triggered" cells (e.g. `developer / claude /
  review`, `skill_runs = 0`); with the catalog missing it degrades to just the observed-trigger cells. decomposer /
  question cohorts get the same catalog-backed zero rows as developer / reviewer whenever they have agent-exit runs.
  Rows are ordered by `skill_runs` DESC, then cohort `runs` DESC, then a stable `(repo, agent_role, backend, skill)`
  tiebreak, and the list is capped at `limit` rows (default `SKILL_MATRIX_ROW_LIMIT` = 100; a non-positive `limit`
  disables the cap). The agent-exit event-filter short-circuit applies (no catalog read either). NULL `agent_role` /
  `backend` bucket under `"unknown"`. Same `extras JSONB` / no-DDL and `TRACK_SKILL_TRIGGERS`-off caveats as
  `get_skill_trigger_rates`.
- `get_skill_adoption` (base table) — per-skill × `(repo, agent_role, backend)` adoption aggregated by **logical**
  agent session rather than by raw agent run, so a resume chain that pulled `develop` across several ticks counts as one
  adopting session, not several. Two `agent_exit` base-table scans combine in Python. The first applies the full
  reporting-window filters and selects the *active* sessions plus the window-scoped diagnostics; the second reads each
  active session's evidence from every `agent_exit` row *before the window end*, deliberately dropping the window start
  and the stage filter (`WindowFilters.historical_scope`) so a load from a prior stage or from before the window stays
  visible, while the retained `end` bound stops a later load from leaking backward. A session is keyed by
  `resume_session_id`, then `session_id`, then the row's primary key (an ID-less row is its own session, never merged
  into one anonymous bucket). `sessions` is the denominator — sessions in the cohort with the skill available (its
  `skills_available` listed it, or a legacy load with the `skills_available` key absent implied it — an explicit empty
  set does not) — and `adopted` counts the sessions that loaded it, once per session, with a derived `adoption_rate`.
  `invocations` is the cohort's window `agent_exit` run count (every run, so a low `load_rows` reads against it);
  `load_rows` counts the window runs that loaded the skill and `incidental` the window runs that made a path-only
  reference to it — independent buckets, so a run that both loaded and inspected a `SKILL.md` increments both. All
  three are window-scoped, so a pre-window load counts toward `adopted` but not toward them. Rows are
  ordered by `sessions` DESC, then `adopted` DESC, then
  `invocations` DESC, then a stable `(repo, agent_role, backend, skill)` tiebreak, and the list is capped at `limit`
  (default `SKILL_ADOPTION_ROW_LIMIT` = 100; a non-positive `limit` disables the cap). The agent-exit event-filter
  short-circuit (no scans at all), NULL `"unknown"` bucketing, and `extras JSONB` / no-DDL / `TRACK_SKILL_TRIGGERS`-off
  caveats match `get_skill_trigger_matrix`.
- `get_issues` (base table) — date / repo-bounded one-row-per-`(repo, issue)` overview: event count, first / last
  activity, latest non-null stage, agent-exit count, cost / token totals, `max_review_round`, `failed_agent_runs`,
  `max_retry_count`. Bounded by `limit` and ordered by `sort_by` (`"last_seen"` default, `"cost"` orders by
  `SUM(cost_usd) DESC NULLS LAST`; unknown `sort_by` raises `ValueError`).
- `get_issue_events` (base table) — full event trace for a single `(repo, issue)` pair, oldest first.
- `get_hourly_heatmap` (base table) — 7×24 weekday/hour activity cells from `EXTRACT(DOW)` / `EXTRACT(HOUR)` over
  `(ts AT TIME ZONE 'UTC') + tz_offset_hours * INTERVAL '1 hour'` (normalizing first guards against a non-UTC session
  timezone re-shifting the buckets) with per-cell event count + `input + output + cache_read + cache_write` token total.
  `tz_offset_hours` (default `0`, parameter binding only — never spliced) lets the dashboard bucket in a non-UTC zone.
- `get_review_round_breakdown` (agent-run view) — per `review_round_bucket` runs / failed counts + `total_cost_usd`,
  plus per-role (`developer_*` / `reviewer_*`) run counts and cost, each role's cost further split into cache vs
  no-cache (`*_cache_cost_usd` + `*_no_cache_cost_usd`). The split is proportional: each run's cost is weighted by
  `(cached_tokens + cache_read_tokens + cache_write_tokens) / (input_tokens + output_tokens + cache_read_tokens +
  cache_write_tokens)` into the cache stack and the complement into no-cache. `cached_tokens` is the Codex "portion of
  input served from cache" counter and is already inside `input_tokens`, so it stays out of the denominator to avoid
  double-counting. Token-less rows attribute their full cost to no-cache. NULL buckets surface as `"unknown"`.
- `get_backend_daily_tokens` (agent-run view) — per `(day, backend)` token totals feeding the hero chart's "By
  backend" stacked-area toggle.
- `get_cost_coverage` (agent-run view) — per `cost_source` rollups carrying both runs and `total_tokens`. The
  `unknown-price` cohort is exposed verbatim (never collapsed into a generic "unknown") because it is the maintenance
  signal for the price tables in `observability/usage/prices.py`. NULL `cost_source` buckets under `"unknown"`.

**Filter contract.** The agent-run view has no `event` column (its WHERE `event = 'agent_exit'` is baked in), so
view-backed functions cannot push an `event IN (...)` clause down. They honor the dashboard's event-filter contract by
short-circuiting to empty when the operator's events selection excludes `agent_exit` (or is cleared). Rollup readers
preserve the same contract through `build_rollup_window_where`, which emits a tautologically-false predicate on a
cleared multiselect and a parameterised `IN (...)` on a non-empty one.

The rollup window helper translates the dashboard's midnight-aligned UTC `[start, end)` datetimes to `day >=
start.date() AND day < end.date()` predicates so the `(day, repo)` index drives a date-range scan. Sub-day-aligned
bounds collapse to day granularity (the rollup carries no finer resolution), but the dashboard never passes those.

**Connection model.** Each function returns a frozen dataclass or list of dataclasses. `ANALYTICS_DB_URL` unset
short-circuits every function to an empty / zero-valued result with no connection attempt, mirroring the sync's no-op
contract. Connection or query failures (driver-level psycopg errors, schema mismatches, network unreachable) are wrapped
in a single `AnalyticsReadError` whose `__cause__` preserves the underlying exception. The psycopg import is deferred to
call time inside `default_connect`; tests inject a fake `connect(db_url) -> connection` factory.

Every public reader accepts an optional `conn=` so a caller (typically the dashboard, inside an `analytics_connection`
scope) can run many reads on a single shared connection instead of paying the ~1 s psycopg handshake per call; absent
`conn=`, the open-per-call / close-in-`finally` path runs unchanged. A caller-supplied `conn=` always wins over the URL
short-circuit.

`analytics_connection(*, db_url=None, connect=None)` is a context manager that maintains a single thread-local
persistent connection. The first `with` block opens the socket (real psycopg connections open with `autocommit=True`);
subsequent `with` blocks on the same thread reuse it; a broken-connection error (`OperationalError` / `InterfaceError`)
inside the scope close-and-replaces the cached socket before re-raise. `close_thread_local_connection()` drains it
explicitly for shutdown hooks or test teardown. The thread-local cache is keyed on the resolved URL: a later `with`
block on the same thread requesting a different `db_url=` closes the stale socket first. The connection is not part of
any Streamlit cache key (a raw `psycopg.Connection` is not hashable). Close-time exceptions are logged and swallowed,
through the `orchestrator.analytics.connection` logger. That name is spelled out literally in
`observability/analytics/query/connections.py` rather than derived from the module path, so an operator log filter
selects on it regardless of which module the close lives in.

The read model is deliberately separate from the sync: `observability/analytics/sync/` owns the JSONL → Postgres write
path, while reads have a different error story and injection shape.

### Dashboard (`orchestrator/dashboard.py`)

Streamlit app over the read model. Opt-in via the `dashboard` dependency group so the default `uv sync --locked` keeps
installing only the polling runtime plus `pytest`, `ruff`, and `wemake-python-styleguide`. Streamlit (and its transitive
pandas), `plotly`, the Plotly figure builders in `orchestrator/dashboard_charts.py`, and the plotly-free theme reached
through `orchestrator/dashboard_theme.py` are imported lazily inside `main()` — importing `orchestrator.dashboard` from
a test or non-dashboard caller does not require the group to be installed. A regression-guard test in
`tests/test_dashboard.py` asserts that loading `orchestrator.dashboard` keeps `streamlit`, `pandas`, `plotly`, and
`orchestrator.dashboard_charts` out of `sys.modules`.

**Module layout.** `orchestrator/dashboard.py` is a manifest-backed lazy compatibility facade with a complete
`dashboard.pyi`. `_dashboard_facade_bootstrap.py` owns both package import and direct-script setup, while
`_dashboard_runtime.py`, `_dashboard_page_controls.py`, and the drill-down leaf own page orchestration, with the two
date leaves beside them forwarding to the owners the filter bar lives on.
Historical `dashboard.<name>` imports, wildcard exports, and object identity are unchanged — every alias still
resolves to the one object its owner defines. Where a patch has to land is a separate question, and it follows the
call path rather than the alias: the page pipeline reaches the staged plan and the wave dispatch on
`observability/dashboard/`, so a test intercepts those with `patch.object(read_plan | dispatch, ...)`, while
`patch.object(dashboard, ...)` still intercepts the page renderers, and `PLOTLY_CONFIG` for the sections that still
resolve it through the facade at call time — the mapping that alias lands on is `render_config`'s own, and the shapes
the pipeline
threads are `page_models`'. A card builder is the one kind of name on that path a patch must not follow to the owner,
and which module holds the binding is what a case has to name. Two widget sections still draw one off the card hub —
the activity heatmap binds the header and the first-wave pass the banner stack
(`from orchestrator.dashboard_cards import _card_header_html`) — and the state section beside them binds the topbar the
same way off the HTML hub, so what the page calls is the reference captured then
rather than whatever `card_html.py` or `summary_html.py` holds at call time: a
test intercepting
one patches the widget module that draws it — `patch.object(_dashboard_widget_costs, "_card_header_html", ...)`
— and reaches the owner only to assert what an unpatched page renders. The sections that moved sit differently. Each
is a
page renderer `patch.object(dashboard, ...)` still intercepts, because the pipeline resolves it through the facade at
call time, but what one draws with is the panel owner's own module-scope import rather than a
widget module's — so a case that has to intercept the adoption table, the trigger-rate one, the matrix, or either sort
parse patches `skill_panel` or `skill_trigger_panel`, and one that has to intercept the issues table, the efficiency
card, the coverage bar, or the ranking depth patches `issue_cost_panel`. The paired lifecycle bars and the
repository-spend pair beneath them sit there too, and a figure builder is on that list beside the card ones: the
per-stage and per-review-round builders are `stage_cost_panel`'s own module-scope imports off `charts/cost_stage.py`
and `charts/cost_review.py`, and the per-repository ranking and per-day strip are `reliability_panel`'s off
`charts/cost_repo.py` and `charts/throughput.py`, rather than a
chart handle the pipeline hands down, so a case intercepting any of the four patches the owner that names it. Those
two carry one more exception
on the configuration side: they read `PLOTLY_CONFIG` off `render_config` as a module attribute at call time
rather than through the facade, so a case pinning the toolbar for either section patches the owner as well, while the
activity heatmap beneath them still takes its figure from the handed-down chart hub and
is facade-intercepted throughout. The recent-run listing sits
the same way as the panels: the render is
facade-intercepted, but the offset shift each `ts` is converted through is `recent_runs`'s own module-scope import of
`filters`, so a case that has to intercept that shift patches there rather than the widget module. So does the hero
usage card: the render is facade-intercepted, while the card header it is titled by, the usage figure it draws, and
the Plotly defaults it hands that figure are `usage_panel`'s own module-scope imports rather than a widget module's or
a facade lookup — so a case that has to intercept any of the three patches `usage_panel`, and `PLOTLY_CONFIG` on the
facade reaches only the activity heatmap, the last section that still resolves it there.
The repo-root `sys.path` shim that lets `streamlit run` resolve the absolute `orchestrator.*` imports is factored
into the shared import-light `orchestrator/script_launch.py` helper (`ensure_repo_root_on_path`), which
`orchestrator/trajectory_dashboard.py` also calls.
The stable `dashboard_*.py` component hubs delegate to focused `_dashboard_*` leaves grouped by responsibility: cards,
tables, sparklines, and skill matrices; and widget state/usage/cost/skill/run sections. The read, KPI-strip, and chart
leaves beside them — raw, rollup, skill, read-mode, read-plan, and dispatch on one side, the KPI series and values
pair in the middle, the cost and usage ones on the other — hold no implementation of their own; each forwards to the
owners named below, and so do all three card leaves, both sparkline leaves, the chrome leaf beside them, the two the
filter bar is reached through, and the
shared-table, issue-table,
skill-trigger, five adoption,
and five trigger-matrix leaves among the table ones, which is what lets the card hub above them and both skill hubs
claim nothing either, leaving none of the four panels that shared table is assembled into building its own. The
widget-skill section is the same kind of leaf one level up: the two cards three of those panels are reported on are
owners as well, so it forwards both and the widget hub above it claims neither. The widget-usage section beside it is
the same: the hero card above every panel is an owner, so it forwards that render, the two helpers its stack toggle
offers a mode by, and the per-day totals behind that stack, and claims none of the four. The widget-run and
widget-cost sections forward that
way only in part. The listing beneath all four panels is an owner too, so the first hands over that render and the
empty-window notice beside it — which the hub likewise republishes without claiming — while still building the
per-issue drill-down under that listing itself. The three sections a window's spend is compared across are owners as
well, so the second hands over the paired lifecycle bars, the height both are pinned to and the two measurements
behind it, the ranked issues beside the backend cards, the notice that column answers a window with no run with, and
the repository ranking beside the run-health tiles, while still drawing the activity heatmap beneath all three.
The state a run carries
lives under
`orchestrator/observability/dashboard/`, split by what it decides: `windows.py` for the reported span and the presets
that name one, `filters.py` for the offset, issue, stage, and cache key it is narrowed and displayed by,
`date_controls.py` for the five slots the bar that window is picked in is laid out across together with the label and
the three inline presets drawn in the first two of them, `date_filter.py` for the bar itself — the window a preset
opens the pickers on, the inclusive days they hand back, and the half-open window plus the filter-line slot the caller
leaves with — `read_mode.py` for the parallel-read knob, the flag its import binds, and the unconfigured-database
message,
`read_plan.py` for the two waves a load is staged into, the minute each cached entry is held for, and the current /
previous key pair they are issued under,
`fanout.py` for running one wave of named readers the way that flag said, `dispatch.py` for driving both waves around
the render between them — one spinner over the pair, one banner and a stop when a read cannot reach the database, and
one `dashboard.load:` line when the load comes back — `rollups.py` for the seven of those readers a
headline or lifecycle section is drawn from — with the hundred-row cap the run list among them is read under, and the
ranking depth the spend table borrows from the KPI owner — `breakdowns.py` for the six a comparison panel is drawn
from, each naming the rollup or breakdown query owner that answers it, and `skills.py` for the three a skill panel is
drawn from, each naming the skill query owner. What one read of that wave then goes through
lives beside them: `scoped_reads.py` for the thread's analytics connection it is issued inside, `filter_binding.py`
for the filters its cache key is read back as, and `static_metadata.py` for the extent and filter vocabulary a page
opens on, the TTL both are cached for, and the banner a failed one stops the run with. Above every panel that wave
feeds, `insights.py` holds the two observations a window is worth interrupting for — runs exiting non-zero, and runs
the parser could not price — the ratio each is raised at, and the banner line a crossing is rendered as; directly
beneath those, `kpis.py` holds the four numbers the headline tiles report — the move against the window before it,
the run-health tiles, the order and depth a spend table is cut to, and the share of spend that was a second pass.
Beside it, `kpi_series.py` holds the per-day spend, token, and resolved lines drawn under three of those tiles,
together with the two token totals they are counted by and the throughput pair reported beside them, and
`kpi_strip.py` the strip itself — what one is built from, the scalars a window and the one before it are reduced to,
and the four
display entries a page opens with. `sparkline_points.py` and `sparkline_html.py` are how one of those lines reaches
the tile above it — three of the strip's four tiles carry one. The first places each day in a box too narrow for an
axis, scaled to the window's own range, floored at an epsilon where a window has none, and left unprojected where the
window reported nothing at all; the second writes that projection as one polyline and the same trace closed along the
bottom edge of the box into the tint under it, holds the tile's room with an empty box where there was nothing to
project, and binds the `values` / `color` / `w` / `h` surface a caller asks for one through.
`summary_html.py` is the band that strip sits in — the banner naming what the database holds, the line under the
filter bar restating what a run narrowed it to, the pill one tile's move against the window before it is annotated
with, and the four tiles assembled around them. A rise reads red and a drop green, because these numbers are costs;
`invert` swaps the hue for the readings where up is the good direction without moving the arrow off the value's sign,
and a window with nothing to compare against or one that did not move renders no pill at all. What reaches the markup
as caller text is escaped — the banner's span label and spend figure, and each tile's label, value, and sub-line —
while the counts beside them and the filter line's own dates carry nothing to escape; the pill's `value` keyword and the
banner's six keyword-only readings are bound as explicit signatures so both still answer the call every caller spells.
`card_html.py` is what the banners and the run-health tiles reach the browser as, together with the header every panel
beneath them is titled by: the hidden mark `css.py` selects a card's container by, the banner stack whose severity
picks a class and a glyph, and the reliability strip whose numbers the calling page's own formatter renders.
`tables.py` is the markup beside it —
the compact table the four hand-rolled panels are listed in: the stylesheet each scopes to its own class, the header
and body they are assembled from, and the bar width, short repository name, missing count, and unpriced amount a cell
reports. `issue_table.py` is the first of those four: the six columns a window's costliest issues are ranked into,
the rules their in-row bars and status pills are painted by, and the readings one issue is reduced to and rendered
as — its bar a share of the widest row in that table, its review round toned from the third one on, and its run
health a `clean` pill wherever nothing failed. `skill_trigger_table.py` is the second: the six columns a
`(role, backend)` cohort's skill use is reported in, its rate bar a share of the busiest cohort in that table, and
`unknown` the label a category the sink left empty is read under. The last two are the panels an operator can reorder,
so each arrives across five owners. The third is the per-session adoption table, the page's primary skill metric:
`skill_adoption_columns.py` for the nine columns it is read across, the key each is ordered by, and the `adopt_sort` /
`adopt_dir` pair a heading writes — with the two invocation diagnostics among those columns counted apart from the
session pair so neither can be read into the rate between them; `skill_adoption_sort.py` for the parse that reads the
pair back and the repository-then-rate order a table nobody sorted opens in; `skill_adoption_headers.py` for the
header row each column is an in-tab sort link in; `skill_adoption_rows.py` for what one
`(repo, role, backend, skill)` cell says, keeping the undefined rate of a skill nobody was offered apart from the real
zero of one nobody loaded; and `skill_adoption.py` for the panel those cells are sorted into and the
`TRACK_SKILL_TRIGGERS`-naming notice a window with no session evidence renders instead. The fourth is the trigger
matrix, split the same way: `skill_matrix_columns.py` for the seven columns it is read across, the key
each is ordered by, and the `mtx_sort` / `mtx_dir` pair a heading writes; `skill_matrix_sort.py` for the parse that
reads that pair back — a stale column or a lone direction degrading to the default rather than raising — and the
repository-then-rate order a matrix nobody sorted opens in; `skill_matrix_headers.py` for the header row each column
is an in-tab sort link in, with the arrow only the active one carries; `skill_matrix_rows.py` for what one
`(repo, role, backend, skill)` cell says, its zero and derived rate toned down together while the cohort's run total
stays plain; and `skill_matrix.py` for the panel those cells are sorted into and the `TRACK_SKILL_TRIGGERS`-naming
notice a window with no catalog-backed cell renders instead.
`skill_panel.py` and `skill_trigger_panel.py` are the two cards three of those four panels are reported on. The first
is the one the page draws: adoption leads it and the aggregate rates and the trigger matrix fold into a collapsed
expander beneath, one notice answers a window with no `agent_exit` row for the whole card rather than for each table
in it, and the caption under the adoption table qualifies a window nobody adopted anything in — naming whichever of
availability, loads, or incidental references it did carry — instead of recommending a `TRACK_SKILL_TRIGGERS` the
presence of a row already proves is on. Whether that evidence was there is what the fold beneath is handed, so a
window where no run triggered reads as a genuine no-trigger or as a prompt to switch tracking on accordingly. The
second is the card the section led with before adoption did; nothing in the render pipeline draws it now, and its
prompt is unconditional, since trigger rates alone carry no per-session evidence to tell those two windows apart.
`recent_runs.py` is the listing under those four panels rather than a fifth among them — the runs behind the readings
above it, projected into the columns one is scanned by and the offset the sidebar picked, drawn as `st.dataframe`
because a raw listing carries no bar, pill, or sortable heading Streamlit's own table cannot already handle. It opens
collapsed so a window's worth of rows does not push the per-issue drill-down off the screen the page ends on, and a
window with no `agent_exit` row renders the notice rather than an empty frame.
`usage_panel.py` is the card above every one of those panels — the first one under the KPI strip, so it answers the
question the page is opened with: whether a day's cost tracks the work behind it. The figure carrying both readings is
the usage chart family's; this owner decides the card around it — the header naming it, the toggle deciding what it
stacks, and the rows the chart is handed for the mode an operator picked. The toggle is a two-value radio because
neither stack is the drilldown of the other: by token type is what a day's tokens went on, by backend is who spent
them. Streamlit reruns the whole script on every interaction, so the picked mode is kept in the page's own session
state under a key apart from the radio's own and the radio is seeded from it by index, since the widget takes an
option's position rather than its value. The per-backend rows are totalled per day here — the same `(day, backend)`
cell can arrive more than once, and only when the backend stack is the one being drawn, because the token-type bands
already ride on the time-series points.
Two more panels are drawn as markup rather than as a figure: `backend_card.py` for what a run on one backend
is worth — the cost of a million tokens, the cost of a run, and the share of billable input the cache answered, each
divided through one guard so a window a backend barely ran in reads zero rather than raising — and `coverage_card.py`
for how much of a window's spend the parser could price, sized by token share whenever the window carries any and by
run share only when it does not, drawn as one bar and the legend beneath it.
`stage_cost_panel.py`, `issue_cost_panel.py`, and `reliability_panel.py` are the three sections that spend is compared
across, each a pair of
7:5 columns rather than a single panel. The first pairs the two lifecycle axes — spend by workflow stage beside spend
by review cycle, each figure built by naming `charts/cost_stage.py` and `charts/cost_review.py` directly rather than
by reaching a builder off a handle — and pins both to one height taken off whichever of the two reads returned more
buckets, because a horizontal bar family sizes itself by its own row count and two panels left to size themselves
would put bars of two different thicknesses either side of one gutter. The second pairs the work with the agent that
did it:
the window's costliest issues ranked on the left, one efficiency card per backend on the right, and the coverage bar
closing that column because it qualifies the money the cards above it report — drawn only where the window carries a
cost-source split. Its two columns answer an empty window differently, since a window can carry runs the parser could
not price while a window with no `agent_exit` row had nothing to run at all. The third pairs the money with whether
the runs behind it held up: the window's spend by repository on the left, the six run-health tiles over the per-day
strip of the issues those runs resolved on the right, each figure built by naming `charts/cost_repo.py` and
`charts/throughput.py` directly. That strip is handed the window's bounds so a day nothing resolved on stands as a
zero bar, and the closing bound is the day before the window's end — the reads beneath the page are issued under
`ts < end`, so drawing through `end` itself would add a trailing day none of them covered.
`page_models.py` holds the seven frozen shapes a render carries between all of that: the caller's Streamlit, pandas,
chart, and theme handles, the selections every read is narrowed by, the controls and page they open on, what one load
answers with, and the rows, totals, and counts the paired repository-spend and run-health section is drawn from.
Streamlit reruns the whole script on every interaction, so a render is one pass and freezing those
shapes is what keeps a section from narrowing the window the sections beside it were handed. Two readings are derived
rather than stored: the issue scope answers nothing until a repository is picked, since GitHub issue numbers repeat
across repositories, and the window span is measured in whole days and floored at one, since it is the divisor of
every per-day rate.
`render_config.py` holds the Plotly configuration each figure below is handed — the hover toolbar switched off once
for the whole page rather than per call site, published as a read-only proxy every call site copies before handing it
to Plotly.
What those reads are drawn as sits one level down, under `charts/`, where `primitives.py` holds what every figure
family is built out of, `cost_layout.py` the frame the horizontal cost families share, `cost_horizontal.py` the
generic spend ranking, `cost_repo.py` the per-repository one drawn through it, `cost_stage.py` the per-stage cache
split, `cost_review.py` the per-review-round one beside it, `heatmap.py` the weekday-by-hour grid,
`throughput.py` the per-day resolved-issue strip, and
`usage_bands.py` / `usage_series.py` / `usage_axis.py` / `usage_traces.py` / `usage.py` the bands, day span, stack
heights, aligned axes, traces, and assembled hero figure the usage family draws its reads as (see **Chart builders**
below).
`dashboard_state.py` stays the hub the page reads the state off, `dashboard_reads.py` the hub the read inventory
is resolved through, and `dashboard_kpi_strip.py` the hub the strip above the panels is built through, while
`_dashboard_kpi_series.py`, `_dashboard_kpi_values.py`,
`_dashboard_windows.py`, `_dashboard_filter_state.py`, `_dashboard_state_constants.py`,
`_dashboard_read_mode.py`, `_dashboard_read_core.py`, `_dashboard_read_plan.py`, `_dashboard_read_dispatch.py`,
`_dashboard_read_rollups.py`,
`_dashboard_read_breakdowns.py`, `_dashboard_read_skills.py`, `dashboard_kpis.py`, `dashboard_charts_base.py`,
`dashboard_charts_heatmap.py`, `dashboard_charts_throughput.py`, `dashboard_charts_usage.py`,
`dashboard_charts_cost.py`,
`_dashboard_cost_layout.py`, `_dashboard_cost_horizontal.py`, `_dashboard_cost_repo.py`,
`_dashboard_cost_stage.py`, `_dashboard_cost_review.py`,
`_dashboard_usage_models.py`, `_dashboard_usage_data.py`, `_dashboard_usage_axis.py`,
`_dashboard_usage_traces.py`, `_dashboard_usage_chart.py`, `_dashboard_card_headers.py`,
`_dashboard_backend_card.py`, `_dashboard_coverage_card.py`,
`_dashboard_table_html.py`, `_dashboard_issue_table.py`,
`_dashboard_sparkline_data.py`, `_dashboard_sparkline_html.py`, `_dashboard_summary_html.py`,
`_dashboard_skill_trigger_table.py`, `_dashboard_adoption_columns.py`, `_dashboard_adoption_sort.py`,
`_dashboard_adoption_headers.py`, `_dashboard_adoption_rows.py`, `_dashboard_adoption_render.py`,
`_dashboard_matrix_columns.py`, `_dashboard_matrix_sort.py`,
`_dashboard_matrix_headers.py`, `_dashboard_matrix_rows.py`, `_dashboard_matrix_render.py`,
`_dashboard_widget_skills.py`, `_dashboard_widget_usage.py`, and `_dashboard_widget_models.py`
forward each historical name to the owner's own object. `_dashboard_widget_runs.py` forwards the run listing and its
empty-window notice the same way while still building the per-issue drill-down beneath them,
`_dashboard_widget_costs.py` forwards the three spend comparisons, the height the paired bars share with the two
measurements behind it, and the notice the backend cards beside that ranking answer an empty window with, while still
drawing the activity card beneath them, and
`dashboard_widgets.py` forwards the Plotly configuration off the render-config owner and the seven page shapes through
the leaf named for them while still claiming the render passes it stamps. None of the state, read,
KPI-strip, skill-adoption, and
skill-matrix hubs defines a name of
its own, so none of them rewrites a
defining module; the
compatibility metadata that keeps the established defining-module assertions intact belongs to the widget hub alone,
and names only members a flat leaf still defines — `dashboard_cards.py` names none, because all thirteen it
publishes are the card, backend, and coverage owners' own objects, and the widget hub leaves the six the two skill
cards are reached by, the run listing beneath them, the four the three spend comparisons are drawn and sized by, the
four the hero card is, and the seven shapes a render is threaded through out of its own
list for the same reason: a `__module__` stamp
there would move one of
them off the owner that defines it. Streamlit is never imported in these
helpers — `st` (with theme and pandas handles, plus the chart handle the activity-heatmap section is still drawn
through, the hero card, the paired lifecycle bars, and the repository-spend pair naming their own chart
owners instead) is passed in as a parameter.

```sh
uv sync --group dashboard                                  # install streamlit + plotly alongside the runtime + dev deps
uv run streamlit run orchestrator/dashboard.py             # launches a local browser tab
```

**Page chrome.** A sticky topbar carries the page title with the data extent / repo / event summary on the left and the
in-range spend pill on the right. A sticky filter bar exposes `3D` / `7D` / `All` inline presets (anchored at the data
extent's max timestamp and clamped to its min) plus two date inputs for arbitrary windows within the extent. The sidebar
surfaces a `Custom` preset fallback, a repo selector, event / stage multi-selects, and a `#123` / `123` issue-number
input.

**Caching.** Every per-filter read is wrapped in `st.cache_data` keyed by the immutable `DashboardCacheKey(start, end,
repo, events, stages, issue)`, so a filter change invalidates every cached query in lockstep. `dashboard/read_plan.py`
builds those wrappers under `WIDGET_CACHE_TTL_SECONDS = 60` (1 min), so a window nobody changes goes back to Postgres
on the first rerun after that minute rather than on every widget interaction. `get_data_extent` and
`get_filter_options` carry no filter inputs and live in argument-less wrappers under the longer
`STATIC_METADATA_TTL_SECONDS = 300` (5 min) TTL so the sidebar / topbar only re-hit Postgres when `analytics.sync`
ingests new events.

**Two-wave loading.** The 16 widget reads are staged into two waves by `dashboard/read_plan.py`:

- **First wave (6 reads).** `summary`, `prev_summary`, `ts_points`, `review_round_rows`, `throughput_rows`,
  `cost_coverage_rows` — feeds the topbar, filter meta, insight banners, and KPI strip.
- **Second wave (10 reads).** `stage_rows`, `agent_exits`, `issues_rows`, `backend_rows`, `repo_rows`, `heatmap_rows`,
  `backend_daily_rows`, `skill_adoption_rows`, `skill_rows`, `skill_matrix_rows` — feeds the rest of the body.

`dashboard/dispatch.py` drives both waves and renders the above-the-fold chrome between them on the main thread
(worker threads only return data through futures, so every `st.*` write runs on the main thread). The second wave is
skipped on an empty window. A single inline `st.spinner("Loading analytics…")` brackets both waves; a read error from
either wave surfaces as one `st.error` + `st.stop`.

**Body layout, top to bottom:**

1. Computed insight banners (failure rate ≥ 10 %, unpriced cost coverage ≥ 10 %).
2. Four-tile KPI strip — total spend, total tokens (`input + output + cache_read + cache_write`), cost / resolved
   issue, rework share — each with an inline-SVG sparkline and previous-window delta where applicable.
3. Hero `usage_over_time` stacked-area + cost-line chart with a "By token type / By backend" toggle.
4. Side-by-side `cost_by_stage` and `cost_by_review_round` cards; the stage card stacks each stage bar into no-cache +
   cache cost, and the review-round card groups development and review cost bars per round with each role's bar further
   stacked into no-cache + cache cost — so the operator can see how much per-stage and per-round spend still bypasses
   prompt caching.
5. 7/5 split: top-cost issues table (Issue with in-row cost bar, Cost, Runs, Review rds, Retries, status pill) +
   backend-efficiency cards (`$ / 1M tok`, `% cache hit`, `$ / run`) above the cost-source coverage bar (sized by token
   share).
6. Another 7/5 split: `cost_by_repo` bars + six-tile reliability panel (agent runs / success rate / resolved / rejected
   / failures / timeouts — all sourced from the same `Summary` window-wide aggregate) above the
   issues-resolved-per-day bar chart with explicit zero days backfilled.
7. 7 × 24 weekday × hour activity heatmap rendering token volume, with an in-card `UTC` offset selectbox (range `-12
   … +14`, default `UTC+7`) that controls both the heatmap bucketing and the wall-clock conversion of the `ts` column
   in the recent agent-runs table below. The widget binds to `st.session_state["tz_offset_hours"]`; the offset is read
   before the second-wave fan-out so the heatmap query buckets in the chosen zone, and the card subtitle / x-axis title
   render the matching `UTC±N` label.
8. "Skill adoption" panel — the primary per-session adoption matrix above a fold-out invocation-level diagnostic. The
   headline table (`_skill_adoption_html` over `get_skill_adoption`) renders one row per `(repo, agent_role, backend,
   skill)` cell with columns Repo / Role / Backend / Skill / Sessions / Sessions using skill / Adoption rate /
   Invocation loads / Incidental references, counting skill use by **logical agent session** rather than by raw run:
   `Sessions` is how many sessions in the cohort had the skill available, `Sessions using skill` the subset that loaded
   it, and `Adoption rate` their share (`adopted / sessions`, once per session). The two trailing columns are the
   window-scoped invocation diagnostics: `Invocation loads` counts the window runs that loaded the skill and
   `Incidental references` the window runs that made a path-only reference to its `SKILL.md`. The load and incidental
   buckets are independent, so a run that both loaded and inspected it increments both, and an incidental mention
   is a separate column that can never raise the adoption rate (a cell with no available session renders a muted `—`
   rate rather than a misleading `0%`). The read model caps the list at 100 rows (Sessions DESC then Sessions-using
   DESC then Invocations DESC); by default rows display sorted by Repo ascending, then Adoption rate descending. Each
   column header is a clickable sort control writing `adopt_sort` / `adopt_dir` query params (parsed by
   `parse_skill_adoption_sort`), with a ▲ / ▼ indicator; an unknown / absent param falls back to that default order.
   Beneath the adoption table a collapsed `st.expander` ("Invocation-level diagnostics · per-run skill triggers")
   carries the older per-run views as a clearly named diagnostic: the per-`(agent_role, backend)` aggregate table
   (`_skill_triggers_html` over `get_skill_trigger_rates`, showing runs, skill runs, a trigger-rate bar, and total
   trigger count) and, below it, the per-skill **trigger matrix** (`_skill_matrix_html` over
   `get_skill_trigger_matrix`) with columns Repo / Role / Backend / Skill / Runs / Runs with skill / Trigger rate. The
   matrix folds each repo's `repo_skill_catalog` into the observed triggers so a skill the repo offers but no cohort
   fired surfaces as an explicit (muted) `0` "Runs with skill" cell (and a matching muted `0%` trigger rate) rather
   than a missing row (the cohort `Runs` total is never muted); its headers write `mtx_sort` / `mtx_dir` params (parsed
   by `parse_skill_matrix_sort`) and default to Repo ascending, then Trigger rate descending. The three tables degrade
   differently with the switch off: per-session adoption only carries signal once `TRACK_SKILL_TRIGGERS` has recorded
   per-run skill fields, but the trigger-rate table still counts every `agent_exit` run and the matrix still shows
   catalog-backed zero rows (the `runs` denominator and `repo_skill_catalog` records do not depend on the switch). When
   rows are present a zero-adoption window
   captions a neutral genuine-0% result (a present row proves tracking is on), an empty adoption window renders the
   adoption table's fallback notice naming the switch, and the matrix shows its own fallback notice when no
   catalog-backed matrix can be built (no catalog records matched and no run fired a skill).
9. Recent agent-runs table as a collapsible expander; the `ts` column is shifted to the wall-clock of the selected UTC
   offset via `shift_ts`.
10. Per-issue drill-down when a number is entered.

**Filter contract.** `build_window_where` distinguishes three cases for the event / stage selections: `None` is "no
filter on this column", a non-empty sequence emits a parameterised `IN (...)`, and an empty sequence emits a
tautologically-false predicate (`FALSE`). The event multiselect maps straight through (`event` is `NOT NULL` in the
schema). The stage multiselect routes through `resolve_stage_filter(selected, available)` because `options.stages` only
lists non-null stages: the all-selected default collapses to `None` so NULL-stage rows are included; an explicitly
cleared selection still emits `[]`; a proper subset passes through verbatim. Without this asymmetry the default
dashboard would silently exclude `stage_evaluation` rows on issues with no workflow label. The issue number acts as a
SQL-level filter when a specific repo is selected AND triggers the drill-down section; with the repo filter on "All" it
stays inert (GitHub issue numbers are not unique across repos).

**Parallel read fan-out.** Setting `DASHBOARD_PARALLEL_READS=on` (or `1` / `true` / `yes`, case-insensitive) flips the
16 widget reads from sequential to a `ThreadPoolExecutor` capped at eight workers. Each worker opens its own
thread-local psycopg connection via `analytics.read.analytics_connection()` — `psycopg.Connection` is not thread-safe,
so sharing one socket across workers would corrupt the wire protocol. `dashboard/dispatch.py` emits a single INFO log
line on every dashboard load — `dashboard.load: total=X.Xs reads=16 parallel=true|false` on a full render, or
`reads=6` when the empty-window short-circuit skips the second wave — so the two paths can be A/B'd with `grep
dashboard.load streamlit.log`. That line's logger is named `orchestrator._dashboard_read_dispatch` as a pinned
literal rather than after the module holding the emit, so a handler or level selection aimed at it keeps working
across a move. An `AnalyticsReadError` raised by any worker propagates verbatim from the first failing future.

**Chart builders.** `orchestrator/dashboard_charts.py` exposes pure Plotly figure builders: `usage_over_time`
(stacked-area + cost-line overlay with `mode="type"` / `mode="backend"` switch), `cost_horizontal_bars` (shared
primitive), `cost_by_repo` (thin adapter over `cost_horizontal_bars`), `cost_by_stage` (per-stage horizontal bars with
each bar stacked into no-cache + cache cost under `barmode="stack"`; the cache segment uses a translucent shade of the
stage's base color so the pair stays visibly tied to the stage, and only the outer cache segment carries the per-stage
dollar text), `cost_by_review_round` (grouped development/review bars per round, each role's bar further stacked into
no-cache + cache cost via `offsetgroup` + `barmode="relative"`; the cache segment uses a translucent shade of the role's
base color so the pair stays visibly tied to the role), `hour_weekday_heatmap` (faint-to-saturated accent gradient over
per-cell token totals, Sunday-first, with a `tz_label` parameter that annotates the x-axis — the caller passes the
matching offset to `get_hourly_heatmap` so cells already reflect that zone), and `done_per_day_bars` (resolved-per-day
bars with explicit `window_start` / `window_end` for zero-day backfill). `orchestrator/dashboard_charts.py` is a pure
re-export hub: each chart family is reached through a focused leaf -- `usage_over_time` / `backend_per_day` through
`orchestrator/dashboard_charts_usage.py`, the three cost adapters (`cost_by_repo` / `cost_by_stage` /
`cost_by_review_round`) plus `cost_horizontal_bars` through `orchestrator/dashboard_charts_cost.py`,
`hour_weekday_heatmap` through
`orchestrator/dashboard_charts_heatmap.py`, and `done_per_day_bars` through
`orchestrator/dashboard_charts_throughput.py` --
and the hub re-imports each public builder under its original name. All four the cost surface publishes are forwarded
from the charts owners that define them; it defines none of them itself. The shared low-level chart
primitives
(`empty_figure`, the money / mono-textfont / two-line-tick and panel-height / legend helpers) live under
`orchestrator/observability/dashboard/charts/primitives.py`. Every chart family names that owner directly, so no flat
module reads them off `orchestrator/dashboard_charts_base.py` any more; that site stays for the callers outside the
tree that do, forwarding each private spelling to the owner's own object and implementing nothing, so the dependency
runs one way and a direct import of any chart module is cycle-free. The frame the three horizontal cost families are
drawn in (the panel margin, the `USD` axis, the
height, and the `CostBarTrace` request one series of bars is built from) lives beside it in
`orchestrator/observability/dashboard/charts/cost_layout.py`, and `cost_horizontal_bars` itself -- with the ordering,
tinting, and flip behind its bars, and the pinned `Signature` that keeps `items` its first parameter -- in
`charts/cost_horizontal.py`. `cost_by_repo` sits on top of that ranking in `charts/cost_repo.py`, deciding only how a
repository reads: the short name its bar is labelled by with the `owner/` prefix dropped, the agent-run count on the
sub-line rather than an event count, the page accent on every bar, and the shared placeholder in its own words for a
window matching no repository. `cost_by_stage` sits beside the ranking in `charts/cost_stage.py` -- the ranking, the
full-price fallback that lets a row carrying only a total still draw at its true length, the `runs` sub-line, and the
lightening that shades a cache half from the stage's own hue, which is also where the per-review-round split gets the
shading for its own cache halves. `cost_by_review_round` is that split, in `charts/cost_review.py` -- the round order
and labels the rows are laid out and read by, the two-role sub-line beside them, the totals each role's bar is
labelled by, the four series the two roles and their two halves are described as, and the row height a panel carrying
two bars per row is sized with. `orchestrator/_dashboard_cost_layout.py`,
`orchestrator/_dashboard_cost_horizontal.py`, `orchestrator/_dashboard_cost_repo.py`,
`orchestrator/_dashboard_cost_stage.py`, and `orchestrator/_dashboard_cost_review.py` are the historical import sites
the cost surface reaches those five owners through, again forwarding and implementing nothing. The heatmap and
throughput families have moved under the same package:
`orchestrator/observability/dashboard/charts/heatmap.py` builds the grid -- and draws its own empty-state annotation
over it rather than routing through the shared placeholder, because an empty heatmap is still legible -- and
`orchestrator/observability/dashboard/charts/throughput.py` the per-day strip, naming the shared placeholder for the
case that reaches it -- a caller who passed no rows and not both window bounds, since only both of them turn the
window into a calendar to draw zero bars across. In front of each,
`orchestrator/dashboard_charts_heatmap.py` and `orchestrator/dashboard_charts_throughput.py` are the historical sites,
forwarding the public builder plus the spellings beneath it -- the cell / label / layout ones for the grid, the
calendar / series / pinned-height ones for the strip -- to the owner's own objects and implementing nothing. A test
that has to intercept one of them patches the owner, because that is what the flat site resolves to. No chart builder
carries a historical `__module__` stamp -- the cost, heatmap, throughput, and usage sites make no
`preserve_defining_module` call at all -- so each reports the charts owner that defines it.
No owner under `charts/` names Plotly at module scope: the ones that assemble a figure import it inside that call,
and an adapter like `charts/cost_repo.py`, which only shapes rows and hands them to another builder, never imports it
at all -- `from __future__ import annotations` leaves its `go.Figure` return annotation unevaluated. Either way every
owner there stays importable without the optional `dashboard` dependency group. The usage family's own shaping sits
beside those primitives:
`orchestrator/observability/dashboard/charts/usage_bands.py` holds the four bands a day is counted into, the mode its
stack is switched with, the `DailyTokenValues` table they are accumulated in, and the roll-up of a `TimeSeriesPoint`
series into one bucket per day, while `orchestrator/observability/dashboard/charts/usage_series.py` holds the day span
that roll-up produced, the `UsageChartData` / `UsageAxisRanges` shapes it travels in, the completion that gives a day
only the per-backend read saw a bucket of its own, and the height each mode measures a stack by. Above that pair,
`orchestrator/observability/dashboard/charts/usage_axis.py` holds the step count and pinned height the hero panel is
drawn at, the rounding that raises each maximum to a number the axis divides into equal steps, and the layout the
token and cost scales are assembled in -- both from zero and both cut into the same steps, so one horizontal rule
means something on either scale, with only the token axis drawing the rules -- and
`orchestrator/observability/dashboard/charts/usage_traces.py` holds what is drawn against them: the shaping that
answers a window holding nothing with no chart at all, the band a stack is added one of at a time, the two modes it is
stacked in, and the cost line overlaid on the secondary axis. Over all four,
`orchestrator/observability/dashboard/charts/usage.py` is the assembly `usage_over_time` returns -- the window shaped,
the stack added in the mode the page asked for, the cost line overlaid, and the layout merged last so the token axis
is scaled to the stack that was actually drawn, or the shared placeholder at the same pinned height when the shaping
came back with nothing to draw -- with the `backend_per_day` stub published beside it.
`orchestrator/dashboard_charts_usage.py` is the stable surface in front of the five, reaching each through
`orchestrator/_dashboard_usage_models.py`, `orchestrator/_dashboard_usage_data.py`,
`orchestrator/_dashboard_usage_axis.py`, `orchestrator/_dashboard_usage_traces.py`, and
`orchestrator/_dashboard_usage_chart.py` -- their historical import sites, forwarding each name to the owner's own
object and implementing nothing, as the surface in front of them does too. A test that has to intercept a usage
builder patches the owner, because that is what every one of those sites resolves to. No module on that path names
Plotly at module scope, so the flat usage surface imports in the default install the same way its owners do -- and so
does every other chart surface, since no flat chart module pulls it in at load either.
The topbar, filter meta, KPI strip,
sparkline / delta pill, most-expensive-issues table, and skill-trigger-rates aggregate table are reached through
`orchestrator/dashboard_html.py`, which builds none of them itself.
The compact table those two — and the two sortable skill panels named
below — are drawn as lives at `observability/dashboard/tables.py`: the stylesheet each panel scopes to
itself under its own class, the header and body they are assembled from, and the bar width, short repository name,
missing count, and unpriced amount a cell reports. `orchestrator/_dashboard_table_html.py` stays the historical
import site for those seven, forwarding each to the owner's own object and implementing nothing, as the HTML surface
above it does. The most-expensive-issues panel drawn in that table is
`observability/dashboard/issue_table.py` — its six columns, the rules its in-row bars and status pills are painted
by, and the readings one issue is reduced to and rendered as — reached through
`orchestrator/_dashboard_issue_table.py`, which forwards the same way. The skill-trigger-rates panel beside it is
`observability/dashboard/skill_trigger_table.py` — its own six columns, the busiest cohort its rate bars are sized
against, and the `unknown` a category the sink left empty reads as, which the adoption table's and the trigger
matrix's row projections both read off that owner directly — reached through
`orchestrator/_dashboard_skill_trigger_table.py`, which forwards the same way too. The sparkline drawn inside a KPI
tile is `observability/dashboard/sparkline_points.py` for where each day of a window sits — its own range, the epsilon
a flat one is floored at, and the window left unprojected — and
`observability/dashboard/sparkline_html.py` for the polyline, the tint that trace is closed into along the bottom of
the box, the empty box a window with nothing to draw still holds, and the historical
`values` / `color` / `w` / `h` surface, reached through
`orchestrator/_dashboard_sparkline_data.py` and `orchestrator/_dashboard_sparkline_html.py`, which forward the same
way as well. The chrome around that strip — the topbar, the filter-meta line, the delta pill one tile is annotated
with, and the strip itself — is `observability/dashboard/summary_html.py`, which reaches the sparkline owner directly
for the line a tile carries, and is reached through `orchestrator/_dashboard_summary_html.py`, forwarding the same way
too. The bar the filter line sits under is `observability/dashboard/date_controls.py` for the five slots it is laid
out across, the label naming it, and the three presets it offers inline, and
`observability/dashboard/date_filter.py` for the window a preset opens its pickers on, the inclusive days they hand
back, and the bar assembling all of it — reached through `orchestrator/_dashboard_date_widgets.py` and
`orchestrator/_dashboard_date_range.py`, which forward the same way as well; the page pipeline calls the bar on its
owner, so a test intercepting it patches `date_filter`.
Beside them, the insight banners, per-card header, backend-efficiency cards,
cost-source coverage bar, and reliability-tile strip are reached through `orchestrator/dashboard_cards.py` — the first,
second, and last of those built by `observability/dashboard/card_html.py` and forwarded through the flat
`orchestrator/_dashboard_card_headers.py`, the third and fourth by `observability/dashboard/backend_card.py` and
`observability/dashboard/coverage_card.py` through `orchestrator/_dashboard_backend_card.py` and
`orchestrator/_dashboard_coverage_card.py`; the primary per-session skill-adoption table is
`observability/dashboard/skill_adoption_columns.py`, `skill_adoption_sort.py`, `skill_adoption_headers.py`,
`skill_adoption_rows.py`, and `skill_adoption.py` — its nine columns and the `adopt_sort` / `adopt_dir` pair its
headings write, the parse and the two orders behind a click, the header row those clicks come from, what one cell
says, and the sorted panel with the notice a window carrying no session evidence renders instead — reached through the
five `orchestrator/_dashboard_adoption_*.py` leaves and the `orchestrator/dashboard_skill_adoption.py` surface above
them, all forwarding and implementing nothing. The invocation-level per-skill trigger matrix is
`observability/dashboard/skill_matrix_columns.py`, `skill_matrix_sort.py`, `skill_matrix_headers.py`,
`skill_matrix_rows.py`, and `skill_matrix.py` — its seven columns and the `mtx_sort` / `mtx_dir` pair its headings
write, the parse and the two orders behind a click, the header row those clicks come from, what one cell says, and
the sorted panel with the notice a window carrying no catalog-backed cell renders instead — reached through the five
`orchestrator/_dashboard_matrix_*.py` leaves and the `orchestrator/dashboard_skill_matrix.py` surface above them,
which forward every historical name to the owner's own object and implement nothing (all re-exported through
`dashboard.py`). The two cards those tables are reported on are
`observability/dashboard/skill_panel.py` — the adoption card, the caption qualifying a window nobody adopted anything
in, and the invocation views folded collapsed under it — and `observability/dashboard/skill_trigger_panel.py` — the
trigger-rate card the section led with before adoption did, and its own fold-out matrix — reached through
`orchestrator/_dashboard_widget_skills.py`, which forwards all seven historical spellings (the six renders plus the
notice the second card answers an empty window with), and the `orchestrator/dashboard_widgets.py` hub above it, which
republishes the six without claiming any of them. The listing under all four panels is
`observability/dashboard/recent_runs.py` — the columns one run
is scanned by, the offset its timestamp is read on, the collapsed expander it is drawn inside, and the notice a window
with no `agent_exit` row renders instead — reached through `orchestrator/_dashboard_widget_runs.py`, which forwards
those two names and builds the per-issue drill-down beneath them itself. The three sections that listing's window is
compared across are `observability/dashboard/stage_cost_panel.py` — the paired lifecycle bars, the 7:5 columns they
are laid out in, and the one height both figures are pinned to together with the row and base measurement behind it —
`observability/dashboard/issue_cost_panel.py` — the window's costliest issues ranked beside one efficiency card
per backend, the coverage bar closing that column, and the notice those cards answer a window with no run with —
and `observability/dashboard/reliability_panel.py` — the window's spend by repository beside the six run-health tiles
and the per-day strip of the issues its runs resolved, bounded by the last day the window covers rather than by its
half-open end —
reached through `orchestrator/_dashboard_widget_costs.py`, which forwards all seven historical spellings while still
drawing the activity heatmap beneath them. The card above all of them is
`observability/dashboard/usage_panel.py` — the header it is titled by, the two-value toggle deciding what a day's
tokens are stacked by, the session key that mode survives a rerun in, and the per-day per-backend totals the second
stack is drawn from — reached through `orchestrator/_dashboard_widget_usage.py`, which forwards all four historical
spellings and defines none of them. What a whole render of that page is threaded
through is `observability/dashboard/page_models.py` — the seven frozen shapes, with the issue scope and window span
read off the filters among them — reached through `orchestrator/_dashboard_widget_models.py`, which defines nothing
and forwards all seven under the private spellings the pipeline imported them by, and the Plotly configuration every
figure it draws is handed is `observability/dashboard/render_config.py`, reached on the widget hub itself.

**Theme.** The plotly-free theme lives under `orchestrator/observability/dashboard/`, split by what a value is.
`palette.py` holds the chrome colors (cool gray `#f4f5f8` page, white cards, indigo accent, muted ink tints), the
semantic trio the delta pills and insight banners are tinted from, the per-token-type / per-backend / per-agent-role /
per-review-round / per-stage / per-`cost_source` maps, and the `color_for(...)` fallback a value no map covers resolves
through. `tokens.py` holds the spacing tokens, the `1480px` content max-width, and the IBM Plex Sans / Mono stacks.
`layout.py` builds the shared `base_layout(title=...)` Plotly dict; `css.py` interpolates both token owners into the
`PAGE_CSS` string the dashboard injects through `st.markdown(unsafe_allow_html=True)`; and `formatting.py` holds the
`fmt_money` / `fmt_money_exact` / `fmt_tokens` / `fmt_num` formatters. `orchestrator/dashboard_theme.py` stays the
historical import site both pages spell as `theme`, forwarding every name to the owner's own object and implementing
nothing. `.streamlit/config.toml` mirrors the palette into Streamlit's `[theme]` and disables the `[browser]
gatherUsageStats` POST so the launch stays local-observability-only.

**Independence.** The dashboard process is independent of the polling tick: it does not open a GitHub session, does not
write to Postgres, and can be deployed off-host by repointing `ANALYTICS_DB_URL` at a managed Postgres endpoint without
changing the orchestrator's deployment.

### Empty and error states

The dashboard never raises an unhandled exception at the user — every missing-data or misconfiguration case surfaces
as a labeled banner.

- `` `ANALYTICS_DB_URL` is not configured. … `` (top-level `st.warning`, app stops) — *env* — `ANALYTICS_DB_URL`
  is unset, empty, or set to `off` / `disabled` / `none`. Set it in `.env` and **relaunch** `streamlit run
  orchestrator/dashboard.py` (the dashboard reads the URL from the imported analytics module at startup, so a browser
  reload alone will not pick up the new value).
- `Could not load analytics filter options: …` (top-level `st.error`, app stops) — *DB connectivity* — The
  dashboard could not reach Postgres at startup. Confirm `docker compose ps` shows `analytics-db` healthy, that the host
  / port / credentials in `ANALYTICS_DB_URL` match `analytics-db/.env`, and that the user can connect with `psql`.
- `Analytics query failed: …` (top-level `st.error`, app stops) — *DB schema / I/O* — A read query raised
  mid-render. Most commonly the `analytics_events` table is missing — either the volume is fresh and the init script
  has not been applied (`docker compose down && docker compose up -d`) or a manual schema reapply is needed (see
  [Service layout](#service-layout)).
- `No analytics events have been recorded yet. …` (top-level `st.info`, app stops) — *data* — The
  `analytics_events` table holds zero rows. Confirm the JSONL sink is on (`ANALYTICS_LOG_PATH`), that recent workflow
  activity produced records, and run `python -m orchestrator.observability.analytics.sync.cli` to populate Postgres.
- `No analytics events match the current filters.` (page banner) — *data* — The data extent is non-empty but every
  row was filtered out. Widen the window preset, pick `All` for the repo, blank the issue-number input, and confirm the
  event / stage multi-selects still have **every option selected** (an empty multi-select is the documented "show
  nothing" signal).
- `No stage data matches the current filters.` (chart annotation) — *data* — Scoped to the stage breakdown chart.
  Also empty when the only matching rows have a NULL stage (`stage_evaluation` records on issues with no workflow
  label).
- `` No `agent_exit` rows match the current filters. `` — *data* — The window contains `stage_enter` /
  `stage_evaluation` rows but no agent invocations — surfaces in the review-round chart, backend cards, cost coverage
  bar, and recent-runs expander.
- `No agent runs with recorded cost in this window.` — *data* — The top-cost issues table fell back to its empty
  state — no `(repo, issue)` pair in the window has any priced agent runs.
- `No repos match the current filters.` — *data* — The per-repo activity chart is empty for this filter combination.
- `Pick a specific repo in the sidebar before drilling into an issue number …` — *UI guard* — The issue-number
  input is inert with the repo filter on `All` because GitHub issue numbers are not unique across repos.
- ``No analytics events recorded for `<repo>#<n>` under the current filters.`` — *data / filter* — The drill-down
  query returned nothing. Either the issue number is wrong for that repo, the orchestrator has not processed it yet, or
  the event / stage multi-selects exclude every row for that issue.
- `Issue drill-down failed: …` — *DB I/O* — The drill-down query raised but the headline metrics rendered first.
  Same fixes as `Analytics query failed: …`.

If a sidebar multi-select is **explicitly cleared** (no items selected), every dependent widget falls back to "no data"
— that is the documented "show nothing for this dimension" signal. Re-select the items (or hit the `↺` reset chip
Streamlit renders on the widget) to restore the default unfiltered shape.

If `python -m orchestrator.observability.analytics.sync.cli` runs cleanly (non-zero `inserted=`) but the dashboard
still shows zero rows, double-check the `ANALYTICS_DB_URL` the sync used — passing `--db-url postgresql://other/db`
(or a different shell environment) populates a different database than the one the dashboard is reading.

## Usage parser (`orchestrator/observability/usage/`)

Pure-Python helpers that decode the JSONL stdout `agents.AgentResult` carries into a `UsageMetrics` dataclass —
backend, distinct model(s), turn count, input / output / cached / cache-read / cache-write token totals, `cost_usd`, and
a `cost_source` tag of `reported` / `estimated` / `unknown-price` / `no-usage`. No external dependency: the parser is
jq-free.

**Module layout.** The package initializer is the public surface: under a narrow `__all__` it re-exports the nine
parsers `metrics.py`, `skills.py`, and `trajectory.py` define, a per-backend trio each, plus the five result types they
hand back — `UsageMetrics` and `SkillTriggers` from the first two, and `AgentTrajectory` / `TrajectoryStep` /
`TurnUsage` from `trajectory_models.py`. Provider payload handling is split behind them: `protocol.py` holds the JSONL
vocabulary and `event_stream.py` the resilient line decoder, `prices.py` the first-party price tables and
`model_names.py` the nested model-name lookup, `claude_rows.py` / `claude_summary.py` and `codex_rows.py` /
`codex_summary.py` the per-provider frame decoding and run summary, `shell_segments.py` / `skill_commands.py` /
`skills_claude.py` / `skills_codex.py` the skill-evidence classification, and `trajectory_claude_blocks.py` /
`trajectory_claude_stream.py` / `trajectory_claude_turns.py` plus `trajectory_codex.py` the timeline reconstruction. The
trajectory classifier reuses the same event decoder, pricing path, and skill evidence owners, so the resilience and
cost-precedence contracts are defined once. Each published name is bound once at import to its owner's own object, and a
binding does not follow a later patch, so a test intercepting a parser targets the module its caller imported;
`orchestrator/usage.py` remains a temporary compatibility site re-exporting the same surface for historical importers.

**Two parsers, one dispatcher.** `parse_claude_usage(stdout)` consumes claude `--output-format stream-json` events,
groups assistant frames by `message.id` so the final-frame usage wins (claude streams partial counts on intermediate
frames), and sums per-model. `parse_codex_usage(stdout, fallback_model=None)` consumes codex `--json` events and treats
usage as cumulative across the session: the *last* non-zero usage record is the authoritative total.
`parse_agent_usage(backend, stdout, fallback_model=None)` dispatches by backend string the same way `agents.run_agent`
does.

**Cost precedence.** A `total_cost_usd` reported by the CLI itself always wins (`cost_source="reported"`); otherwise the
parser walks first-party Anthropic / OpenAI price tables baked into the module and produces an estimate (`"estimated"`).
When usage is present but the model SKU does not match any priced family, the parser returns
`cost_source="unknown-price"` and `cost_usd=None` rather than guess at zero or bill cached tokens at the input rate. An
empty stream — or one with no usage frames at all — yields `"no-usage"`.

**Resilience.** Malformed JSON lines (banner text, truncated frames, partial flushes) are silently skipped so a single
bad line never invalidates the rest of the stream. `_run_agent_tracked` (in `workflow/engine/usage.py`) calls
`parse_agent_usage` after every tracked agent run and appends the parsed counts to the
[analytics sink](#analytics-sink-analytics_log_path) under `event="agent_exit"`; a parser exception is caught and
downgraded to a `log.exception`.

**Terminal verdict surface.** Beyond the analytics sink, `_accumulate_issue_usage` (in `workflow/engine/usage.py`,
beside `_run_agent_tracked`) folds each run's
`UsageMetrics` into per-issue counters on the pinned state (`issue_agent_runs` / `issue_total_tokens` /
`issue_total_cost_usd` / `issue_cost_sources`; see [state-machine.md](state-machine.md#pinned-state)). When an
issue reaches a terminal, `_format_issue_usage_verdict` renders those counters into one visible receipt line
posted on the issue thread — `:receipt: this issue: N agent runs · T tokens · $X.XX`, with `(est.)` appended when any
run's cost was `estimated` and the figure collapsed to `unknown` when an `unknown-price` run leaves the total
incomplete. The PR merged / rejected finalizers and the closed-`question` terminal post it as a standalone tracked
comment; the `umbrella` close comment appends it. It is a read-only summary — nothing gates on the figure — and it is
skipped when no run was ever counted.

**Skill-trigger extractor (opt-in).** A sibling trio mirrors the usage parsers' two-parsers-one-dispatcher shape and
resilience contract to record which agent *skills* a run loaded, gated behind `TRACK_SKILL_TRIGGERS` (default off;
see [`agent_exit` records](#agent_exit-records)). The result is a names-only evidence model on `SkillTriggers`:
`triggered` / `trigger_counts` are the loaded skills, `evidence` maps each to its tier (`confirmed` / `inferred`), and
`incidental` / `incidental_counts` are path-only references that never become loads. The two buckets are independent —
a skill both read and inspected is recorded in both — the only exclusion is structural: an incidental reference never
enters `triggered` / `trigger_counts` or the `skill_triggered` audit events. `parse_claude_skills(stdout)` reads the
firm **confirmed** signal — `tool_use`
content blocks named `Skill` in the `assistant` stream — and returns `input.skill` in first-seen order, de-duplicating
per invocation by the block `id`. (A captured real stream showed that under `--include-partial-messages` each completed
content block lands in its own `assistant` frame — the content array is partitioned across frames, not a cumulative
snapshot that repeats earlier blocks the way the `usage` sub-object does — so the parser walks every frame and de-dups
by `id` rather than keeping the last frame per message id.) Claude has no dedicated file mechanism, so it produces no
incidental references. `parse_codex_skills(stdout)` recognizes the codex shape: codex has no dedicated `Skill` tool, so
its file-based skill mechanism surfaces only as a `command_execution` item whose shell `command` opens a skill's
`skills/<name>/SKILL.md` file (codex's own "open its SKILL.md" instruction). A captured reviewer run pinned this — codex
both registered-under-`$CODEX_HOME/skills/` and project-local `.agents/skills/` reads match. The command is first
unwrapped (peeling the `bash -lc "…"` shell) and split into sub-commands on **unquoted, unescaped** operators —
quote- and backslash-aware, so a metacharacter inside a quoted argument (`rg 'foo|bar' path`) or a backslash-escaped one
(`rg foo\|cat path`) does not fabricate a spurious segment — then each `SKILL.md` match is routed by its sub-command's
leading verb (skipping any `NAME=value` env prefix). Only a verb
established as a **direct reader** (`cat` / `sed` / `head` / …) makes the reference an **inferred** load; every other
verb — an inspection / search (`git diff` / `git status` / `rg`), an env-prefixed inspection (`GIT_PAGER=cat git
diff …`), or a generic path-only command (`echo …`) — makes it an **incidental** reference. Even a reader verb is
demoted to incidental when the `SKILL.md` is *written* rather than read: an output-redirect target
(`cat t > .agents/skills/x/SKILL.md`) or a non-reading mode (`sed -i` / `--in-place`) is an incidental reference, so a
skill file a run only writes is never miscounted as a load. So a read chained after an inspection still counts, and a
bystander `git diff` over a changed SKILL.md does not fabricate a load. Started/completed
echo the same command, so the parser dedups by the shared `item.id` (last-frame-wins, as for usage) — for inferred
loads and incidental references alike. It reads only the `<name>` path segment and the routing verb — never the command
text or its `aggregated_output` (the file's contents), both of which can echo user content (names-only Privacy). The
inferred signal stays **heuristic** within the reader allowlist: a reader that opens a SKILL.md for an unrelated reason
would still register as an inferred load, while defaulting non-readers to incidental keeps an unrecognized command from
fabricating a trigger. `parse_agent_skills(backend, stdout)` dispatches by backend exactly as `parse_agent_usage` does.
The offered-skills set (`SkillTriggers.available`) is
**confirmed on claude** — read from the dedicated `skills` array in the `system`/`init` frame, captured against a real
stream — and
stays **empty on codex** at the parser layer: a captured `codex exec --json` stream (v0.142.5) carries no offered-skills
frame at all, so `record_agent_exit` backfills the codex offered set out-of-band from the filesystem via
`skills.discovery.discover_local_skills(cwd)` instead. The *triggered* set does not
depend on it either way. As with the usage parsers, malformed JSONL lines are skipped and a missing / renamed field
yields an empty result rather than an exception. Only the skill *name* is ever read — never the `Skill` tool's `args`
(Privacy).

**Trajectory classifier.** A third sibling trio mirrors the same two-parsers-one-dispatcher shape and resilience
contract to reconstruct a run's *trajectory* — the ordered timeline of tool calls / results interleaved with the
assistant / user text turns — into an `AgentTrajectory` dataclass: `backend`, a best-effort `system_prompt` / `tools`,
the names-only `skills` (`SkillTriggers`), an ordered `steps` tuple of `TrajectoryStep` (`kind` is `"tool_call"` /
`"tool_result"` / `"assistant_message"` / `"user_message"`, with `name` / `tool_id` / raw `content` — `name` /
`tool_id` empty on the text turns — plus a `turn` index tying each billed step back to the assistant turn that
produced it), `final_output`, and a best-effort `turns` tuple of per-turn token usage (`TurnUsage`, parallel to `tools`
/ `skills` and claude-only today). `parse_claude_trajectory(stdout)` reads the offered tools from the `system`/`init`
frame's `tools` array, then the ordered timeline: assistant `text` blocks become `assistant_message` turns and
`tool_use` blocks `tool_call` steps; user `text` blocks become `user_message` turns and `tool_result` blocks
`tool_result` steps — calls / results joined by `tool_use_id` and de-duplicated per id the same way
`parse_claude_skills` is, while id-less text blocks ride claude's per-completed-block framing — and the final answer
from the `result` frame's `result` string. It also groups those assistant frames by `message.id` in first-seen order to
assign each a 0-based `turn` index — stamped onto the `assistant_message` / `tool_call` steps that frame produced (a
`tool_result` / `user_message` step is a turn *input*, not billed output, so its `turn` stays `None`) — and emits one
`TurnUsage` per turn: `model`, `input_tokens` / `output_tokens`, `cache_read_tokens` / `cache_write_tokens` (the 5m + 1h
cache-creation buckets summed), and an always-*estimated* `cost_usd` / `cost_source` (`"estimated"`, or
`"unknown-price"` with `cost_usd=None` for an unpriced SKU — a reported `total_cost_usd` is a run-level figure and
never reaches a turn). The per-turn estimate reuses the same `claude_estimate_cost` price path on
`observability/usage/prices.py` as the run aggregate, so the per-turn figures stay in lock-step with
`parse_claude_usage`'s run totals. `parse_codex_trajectory(stdout)` treats each
`command_execution` item as one call (its `command`) plus one result (its `aggregated_output`) and each `agent_message`
item as one `assistant_message` turn (its `text`), collapsing each item's started/completed pair by the shared
`item.id`, and reads the final answer from the last `agent_message` `text`; it leaves `turns` empty with every
`step.turn` `None`, since codex usage frames are cumulative across the session rather than per-turn. Both reuse the
matching skill extractor for the `skills` field. `parse_agent_trajectory(backend, stdout)` dispatches by backend exactly
as the usage / skill dispatchers do. `system_prompt` stays `None` and `tools` stays empty in the classifier whenever a
backend's stream does not expose them (codex exposes neither); the analytics writer backfills codex `tools` out-of-band
from `skills.discovery.discover_codex_tools()`. Malformed JSONL lines are skipped and a missing / renamed field
yields an empty section rather than an exception. Unlike the skill extractor, this classifier records the **raw** stream
payload — tool inputs, tool outputs, and the final text — verbatim: it deliberately does **not** redact, truncate,
or write any file. Those concerns belong to its downstream writer,
`observability/analytics/trajectories/`'s `persistence.maybe_record_trajectory`
(called from `record_agent_exit`), which redacts every free-text field, applies the head/tail and total-record
truncation caps, and appends the `agent_trajectory` record to the
[trajectory sink](#trajectory-sink-trajectory_log_path) — only when `TRAJECTORY_LOG_PATH` is enabled and always behind
its own fail-open guard.

## Summary of "what runs when"

- `retention.prune_with_retention_logging` (function call) — trigger: end of each `main._run_tick` after every
  configured repo drains; cadence: once per tick (process-wide, not per-repo); no-op when the sink is disabled or
  `ANALYTICS_RETENTION_DAYS <= 0`.
- `scheduler.reap` (method call) — trigger: end of each `main._run_tick` after every configured repo drains,
  immediately before the analytics prune; cadence: exactly once per polling pass regardless of repo count; nonblocking
  drain of any worker completions since the last poll. `_dispatch_via_scheduler` deliberately does NOT call `reap`.
