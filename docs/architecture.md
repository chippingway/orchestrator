# Architecture

Single-process **polling orchestrator** that drives GitHub issues through a label-based state machine, delegating coding
work to a configurable coding-agent CLI (`codex` or `claude`) running as a subprocess in isolated git worktrees.

State lives in GitHub: a workflow label exposes the current stage and a pinned JSON comment holds per-issue durable
state. The orchestrator process is stateless and can restart at any time.

This file covers the high-level system: design constraints, the module map, the process model, the agent subprocess
shape, the push path, and the observability surfaces. The label set, per-stage internals, per-tick flow, and
pinned-state schema live in [`state-machine.md`](state-machine.md); agent roles and command-spec semantics live in
[`workflow.md`](workflow.md).

## Design constraints

GitHub Issues are the orchestrator's task tracker and durable state surface. The process intentionally avoids an
internal database: workflow labels expose the current stage, and the pinned JSON comment holds the per-issue state that
the next tick needs. This keeps progress visible to humans on github.com and lets the process restart without
reconstructing hidden local state.

The orchestrator is not fully autonomous. When a stage hits uncertainty, an unsafe repository state, a malformed agent
response, or an exhausted retry cap, it parks with `awaiting_human` and mentions `HITL_HANDLE`; a later human issue
comment is the resume signal for the parked agent session.

The workflow is deliberately fixed instead of planner-selected: decomposition, implementation, validation, and
acceptance are mandatory phases. Routing is explicit and label-driven.

Agents run on the host as CLI subprocesses with broad local permissions
(`codex --dangerously-bypass-approvals-and-sandbox`, `claude --dangerously-skip-permissions`). The host, container, or
VM around the orchestrator is therefore the real sandbox boundary; token handling and hardened git operations are
designed around that assumption.

## Top-level layout

The workflow, worktree, analytics-read, and dashboard subsystems expose stable lazy facades backed by immutable export
manifests. Their implementations live in responsibility-named private leaves, while facade lookups preserve every
historical import and object identity. Leaves call through the owning facade at runtime where patch interception is
part of the compatibility contract, so `patch.object(workflow, "<helper>", ...)` still intercepts calls made from
other workflow and stage leaves. Once a responsibility has been lifted into an owner module, though, its in-repo
callers bind that owner directly and a patch has to target it instead — the facade keeps resolving the name for
outside callers but is no longer on the call path. Each of those boundaries is named where its owner is described
below.

```
orchestrator/
  __init__.py           lazy package/version compatibility surface;
  _package_exports.py   owns root-package export resolution and caching
  cli.py                `agent-orchestrator` console-script entry point,
                        delegating to the `main.py` runtime
  __main__.py           `python -m orchestrator` launch form over `cli.main`
  main.py               stable entry-point and test-patch facade
  _main_*.py            CLI/setup, tick fan-out, loop/drain, logging,
                        self-update probes, and shutdown/watchdog leaves
  config/
    __init__.py         stable configuration surface; binds each resolver
                        result as a module attribute (reload / patch target)
    environment.py      env-value parsers plus the `_SettingsResolver` that
                        reads/validates every knob into a resolved mapping
    _dotenv.py          non-secret `.env` loader
    credentials.py      process/token-file GitHub credential resolution and
                        secret redaction over the process environment
    models.py           `RepoSpec` / `RepoEnvEntry` repository-config types
    repositories.py     REPOS entry parsing, validation, and default-spec
                        construction
  state_machine.py      forwarding-only surface over `workflow/state.py`
  comment_trust.py      forwarding-only surface over `github/comments.py`
  github/
    __init__.py         stable public surface (`__all__`): the composed
                        `GitHubClient` and the pinned durable-state model,
                        re-exported from their owner modules
    client.py           authenticated `GitHubClient` over the mixin chain:
                        token resolution, PyGithub setup, worker-thread clone,
                        cached label reads, stage-enter events
    checks.py           status / check-run normalization, failure-before-pending
                        folding, and the fail-closed check-read client mixin
    comments.py         comment-author trust policy (is_trusted_author /
                        filter_trusted) gating comment authors on the
                        ALLOWED_ISSUE_AUTHORS allowlist
    events.py           audit event record construction and the optional
                        JSONL sink
    issues.py           non-PR issue filtering, issue-query options, and the
                        issue-client mixin (polling, label writes, events,
                        comments, child creation)
    labels.py           workflow/control label vocabulary, bootstrap
                        specifications, predicates, and the label-bootstrap
                        client mixin
    pinned_state.py     authenticated pinned-state model, parser, and the
                        state / comment-watermark client mixin
    pull_requests.py    stateless PR status helpers plus the pull-request
                        client mixin (lookup, creation, comments, labeling,
                        SHA-pinned merge, remote-branch delete)
    reviews.py          current-head review aggregation plus the review client
                        mixin (approval verdicts, unread feedback watermarks)
  agents/
    __init__.py         stable runner API plus process-termination re-export
    models.py           agent result / run-option / subprocess-result models
    environment.py      credential filtering plus injected git identity
    sessions.py         session-id and Claude final-message JSONL parsing
    processes.py        shared process registry and subprocess-group lifecycle
    runner.py           shared agent dispatch, result assembly, spawn logging
    backends/           per-backend command construction and execution
      codex.py          Codex command construction, scratch output, execution
      claude.py         Claude command construction and execution
  scheduler/
    __init__.py         stable `IssueScheduler` / `SubmissionRequest` surface
    models.py           typed submissions, legacy-call binding, normalization
    service.py          the concrete `IssueScheduler` over its view,
                        reservation, and execution layers
  workflow/
    __init__.py         lazy compatibility facade for tick, dispatch, shared
                        helpers, and stage-handler patch points, plus its
                        `__init__.pyi` static surface
    state.py            typed workflow state: the `WorkflowLabel` /
                        `ControlLabel` vocabularies, strict label coercion, the
                        declared transition graph, and the transition guard
    engine/
      __init__.py       package marker only; reserved for the tick, dispatch,
                        and remaining shared-helper owners
      comments.py       the orchestrator marker and capped id ledger both
                        comment posters write, the trusted-author thread read
                        every prompt quotes, and the tracked-repos block
      drift.py          the user-content hash, the filters that keep
                        orchestrator, bot, untrusted, and bare-continue
                        comments out of it, the dev-resume prompt and consumed
                        watermark one drift earns, and the decomposition reset
                        and notice the pre-implementation route takes
      guards.py         what a finished agent run may leave behind: the
                        shutdown-interruption and freshly-read hard-skip
                        refusals, and the awaiting-human park beside them
      messages.py       the markers read out of an agent's last message
                        (review / documentation verdicts, drift ack,
                        `/orchestrator continue` and its refusal) and the
                        redact-before-truncate stderr diagnostics
      prompts.py        the prompt builders the stages share (implement,
                        respawn, review, documentation, fix, conflict, question
                        and its followup, PR-comment followup, decompose) plus
                        the commit-style / foreground-only notes, the
                        empty-body placeholders, and the single-decision
                        comment
      usage.py          the tracked agent run: the request model, the audit
                        spawn/exit pair, the analytics record and its
                        configured-model fallback, the `skill_triggered`
                        emission, the per-issue counters that record's usage is
                        folded into and the terminal receipt read off them, and
                        the UTC stamp the stages write
  _workflow_export_manifest.py / _workflow_exports.py
                        immutable historical inventory and lazy resolver hooks
  _workflow_dependencies.py
                        import-time config/analytics bindings shared by leaves
  _workflow_*.py        tick/scheduling, dispatch, pickup, and terminal-routing
                        leaves
  workflow_drift.py     lazy user-content-drift compatibility facade
  workflow_messages.py  lazy prompt/parser/comment compatibility facade
  _workflow_messages_*.py
                        manifest-parsing leaves and the values they share
  git/
    __init__.py         package marker only; callers import an owner directly
    authentication.py   per-repo token resolution, the askpass session and its
                        detached environment, the authenticated worktree /
                        target-root fetches, and the hardened lease push
    commands.py         plain / hardened git execution, the argv hardening
                        prefixes, and the unsafe local-transport probe
    locks.py            per-target-root re-entrant lock registry and accessor
    base_sync/
      __init__.py       package marker only; callers import an owner directly
      conflicts.py      the counter, PR notice, audit event, and relabel a
                        genuinely conflicted rebase is handed to its stage with
      eligibility.py    the label, park / trusted-retry, open-PR, recovery, and
                        clean-tree gates one PR sync clears before a rewrite
      guards.py         the no-op completion and the unreadable-HEAD, dirty-
                        tree, and failed-push parks that refuse publication
      models.py         frozen auto-rebase contexts, requests, recovery
                        snapshots, and decisions
      outcomes.py       recovery notices plus the already-published, unknown-
                        comparison, diverged, dirty, and failed-push answers
      persistence.py    auto-rebase parks, the reset-and-park tail, and the
                        state / notice / event writes a recovery finalizes with
      pr.py             the order a PR-having worktree's gates, rebase, and
                        publication are asked in, plus the legacy keyword
                        signature the refresh still enters through
      pre_pr.py         hardened rebase / merge probes, rebase-in-progress
                        detection, and the aborting pre-PR local rebase
      publication.py    post-rebase HEAD / dirty checks, the lease-pinned
                        force-push, and the notice, event, route, and pinned
                        state an accepted push earns
      recovery.py       the order a recovery asks its questions in, the dirty-
                        guarded reissued push, and the legacy keyword signature
                        callers still enter through
      refresh.py        per-tick authenticated base fetch, worktree discovery,
                        the sync gates, and the per-worktree route
      snapshot.py       the authenticated branch fetch, local / remote head
                        reads, divergence counts, the anchor-clearing no-op
                        exits, and the abort an unreadable read falls to
      startup.py        pre-rebase HEAD guard, the anchor persisted before git
                        runs, and the abort / route / park a failure takes
      state.py          pinned-state keys, park reasons, refresh detour
                        labels, and the shared base-sync logger
    publication/
      __init__.py       package marker only; callers import an owner directly
      planning.py       merge-base, HEAD, dirty and subject preconditions plus
                        the squash message they select
      probes.py         subject vocabulary and predicates, ahead/behind counts,
                        first-commit and recent-base subject reads
      rewrite.py        soft reset, orchestrator-identity commit, lease
                        force-push, and the rollback each post-reset failure
                        takes
      squash.py         plan-then-rewrite entry point stage handlers call
      titles.py         subject-prefix inference and PR-title selection
    verification/
      __init__.py       package marker only; callers import an owner directly
      models.py         VerifyResult statuses / fields and the output budget
      output.py         redact-then-truncate pass over captured verify output
      probes.py         HEAD snapshot and hardened porcelain dirty-file scan
      process.py        one command's group spawn / kill / drain and its verdict
      runner.py         stripped child env and fail-fast command sequencing
    worktrees/
      __init__.py       package marker only; callers import an owner directly
      cleanup.py        lock-held issue-worktree removal and local branch
                        deletion behind their best-effort boundaries
      creation.py       issue / PR worktree creation, stale-worktree reuse, and
                        the new-commit probe the reuse decision turns on
      decomposition.py  decomposer scratch path, detached creation, and
                        best-effort removal
      paths.py          slug sanitization, git-ref-safe branch segments, path
                        and branch derivation, pinned/legacy branch resolution
      recovery.py       candidate-branch discovery and unpushed-commit probes
      terminal.py       question-stage teardown and terminal local + remote
                        branch cleanup composed from cleanup.py
  git_plumbing.py       lazy hardened-git compatibility facade forwarding to
                        the git/ owners
  _git_plumbing_export_manifest.py / _git_plumbing_exports.py
                        immutable historical inventory and lazy resolver hooks
  verify.py             lazy forwarding shell over git/verification/ owners
  worktree_lifecycle.py lazy forwarding shell over git/worktrees/ owners
  branch_publication.py lazy forwarding shell over git/publication/ owners
  _branch_publication_export_manifest.py / _branch_publication_exports.py
                        immutable historical inventory and lazy resolver hooks
  base_sync.py          lazy base-refresh/rebase compatibility facade over the
                        git/base_sync/ owners
  _base_sync_export_manifest.py / _base_sync_exports.py
                        immutable historical inventory and lazy resolver hooks
  worktrees.py          lazy compatibility hub over the five worktree
                        subsystem facades above
  _worktrees_export_manifest.py / _worktrees_exports.py
                        immutable public inventory and lazy resolver hooks
  analytics/
    __init__.py         import-only package compatibility facade and sink bootstrap
    _package_*.py       package initialization, immutable inventory, and hooks
    read.py             lazy read-model compatibility facade with a `.pyi` surface
    _read_*.py          query-family implementations, typed query rows, and hooks
    read_*.py           stable raw, rollup, dashboard, and model compatibility hubs
    read_request*.py    typed filters, connection inputs, options, and legacy binding
    _recording*.py      event-family recording, settings, usage, and JSONL persistence
    _retention*.py      retention scanning and atomic rewrite leaves
    sync.py / _sync_*.py
                        CLI, ingestion, row parsing/mapping, and database lifecycle
    _trajectories.py / _trajectory_*.py
                        trajectory serialization, sanitization, and persistence
  dashboard.py          lazy compatibility facade and direct Streamlit entrypoint
  dashboard_*.py        stable component, read, chart, state, and widget hubs
  _dashboard_*.py       bootstrap/hooks plus focused render, query, and chart leaves
  usage.py              stable usage, skill, and trajectory parser surface
  _usage_*.py           provider payload, pricing, skill, and trajectory leaves
  trajectory_reader.py  pure file-backed filter and summary read model
  _trajectory_*.py      record/view models, parsing, filtering, and file-read leaves
  trajectory_dashboard.py
                        lazy compatibility facade and direct Streamlit entrypoint
  _trajectory_dashboard_*.py
                        viewer bootstrap, page controls, rendering, and HTML leaves
  skill_catalog.py      per-tick repo skill-catalog collection: enumerate
                        SKILL.md definitions on the target base ref and
                        append one `repo_skill_catalog` analytics record;
                        plus the per-run `discover_local_skills` filesystem
                        scan and `discover_codex_tools` baseline that backfill
                        a codex trajectory's offered skills and tools
  _local_skills.py      per-run filesystem skill discovery and codex tool list
  stages/
    <stage>.py          lazy compatibility facade for each historical stage
    _<stage>_exports.py / _<stage>_export_manifest.py
                        stage-specific lazy hooks and complete inventories
    _decomposition_*.py decomposer runs/sessions, child routing, recovery,
                        cleanup, blocked parents, and umbrella handling
    _implementing_*.py  handler entry, sessions, typed resume, recovery,
                        publication, drift, and post-agent dispositions
    _documenting_*.py   preconditions, run, persistence, drift, and outcomes
    _validating_*.py    reviewer/verify flow, watermarks, approval, fixes,
                        drift, and awaiting-human routes
    _in_review_*.py     watermarks, fresh feedback, drift, and manual-merge tail
    _fixing_*.py        bookmarks, quiet-window feedback, resume, and routing
    _conflict_*.py      rebase guards/outcomes, resume, publish, and transitions
    _question_*.py      read-only session, run, outcomes, and handler routing
```

`workflow/__init__.py`, `worktrees.py`, `analytics.read`, and `dashboard.py` publish explicit sorted `__all__`
inventories, `.pyi` surfaces, and immutable target registries. Resolution is lazy and cached on the facade, but the
resolved object is the implementation object's exact identity. Existing direct imports, wildcard imports, and
`patch.object` calls therefore keep working. Base-sync names still resolve on the `base_sync` facade with their
owner's exact identity, and the publication helpers stay patchable by name on `branch_publication` (or on `worktrees` /
`workflow`) because their callers read them off a facade. Inside `git/publication/`, though, the owners bind their
collaborators directly -- `probes` calls `git.commands`, `titles` calls `probes`, `planning` calls `git.commands`,
both siblings, and the verification probes for its HEAD and dirty-file guards, `rewrite` calls `git.commands`,
`git.authentication`, and the verification probes, and `squash` calls `planning` and `rewrite` -- so a patch that has
to intercept the hardened reset, the force-push, or the plan a rewrite spends targets the owner module.
`git/verification/` is bound the same way -- `output`
calls `models`, `process` calls `output` and `probes`, `runner` calls `process` -- and the validating approval gate
reaches `runner._run_verify_commands` directly, so a patch that has to intercept the verify run, the HEAD snapshot, or
the dirty-file scan targets the owner module and not the `verify` shell. That gate is the runner's only caller, so
`_run_verify_commands` is no longer re-exported by `workflow`; it stays on the `worktrees` hub next to `VerifyResult`
and `_truncate_verify_output`, while `_head_sha` / `_worktree_dirty_files` remain on both facades for the stage leaves
that read them off `workflow`. `git/authentication.py` binds the same way --
the authenticated fetches and the push reach `git.commands` and `git.locks` plus their own token, session, lease, and
refusal helpers directly -- so a patch that has to intercept the transport probe, the target-root lock, the session,
or the remote-ref lease read targets `orchestrator.git.authentication` and not `git_plumbing`; `_authed_fetch` /
`_authed_target_fetch` / `_push_branch` themselves stay patchable by name on `git_plumbing`, `worktrees`,
`base_sync`, and `workflow`, and `_push_branch` stays resolvable on `branch_publication` too -- but the squash
rewrite reads it off `git.authentication`, so a mock that has to intercept that force-push targets the owner and
not the facade. The `git/worktrees/` owners
bind the same way — the creators reach `git.commands`, `git.locks`, `git.authentication`, and their in-package
`paths` / `recovery` siblings directly, the decomposer lifecycle resolves its own path helper, and `terminal`
composes its local teardown from `cleanup` — so a patch that has to intercept the git plumbing, the authenticated
fetch, the new-commit probe, or the worktree path one of them runs against targets `orchestrator.git.commands` /
`orchestrator.git.authentication` / the owner module, not `worktree_lifecycle`. The question stage and the
review-terminal actions call `terminal._cleanup_question_worktree` / `terminal._cleanup_terminal_branch` directly,
so a mock for either one lands on the owner even though both names stay forwarded — straight off that owner — on
`workflow`, `worktrees`, and `worktree_lifecycle` for compatibility. `_ensure_worktree`, `_ensure_pr_worktree`,
`_has_new_commits`, and the decomposer helpers themselves stay patchable by name on `worktree_lifecycle`,
`worktrees`, and `workflow`. `git/base_sync/` binds the same way: `models` and `state` carry only data -- the
frozen auto-rebase models and the pinned-state keys, park reasons, detour labels, and logger every behavioral
owner binds straight off `state` -- while its twelve behavioral owners bind their collaborators.
On the refresh side, `refresh` reaches `git.authentication`, `git.commands`, `git.verification.probes`,
`git.worktrees.paths`, and its `pre_pr` and `pr` siblings directly, `pre_pr` reaches `git.commands`, `pr`
reaches `eligibility`, `startup`, and `publication` for the order it asks them in, `eligibility`
reaches `github.comments` for the trusted-reply filter, the verification probes for its clean-tree gate, and
`recovery` for the interrupted rebase it settles before rejecting a label or starting a new one, and `startup`
reaches `git.commands`, `git.verification.probes`, and its `pre_pr`, `persistence`, and `conflicts` siblings
for the pre-rebase HEAD read, the rebase it anchors, the abort a failure runs, and the conflict route or park
it ends in. `conflicts` itself reaches only `models`, `state`, and the label enum.
`publication` reaches `git.verification.probes`, `git.worktrees.paths`, `git.authentication`, and its
`guards` sibling for the post-rebase HEAD and dirty reads, the branch name, the lease-pinned push, and
every refusal that precedes it, and `guards` reaches `persistence` for the reset-and-park tail three of
its four exits end in. On the
crash-recovery side, `recovery` calls `snapshot` for the reads, `outcomes` for the answers, `persistence` for
the finalize a landed push earns, and `git.authentication` / the verification probes for the reissued push and
the dirty scan guarding it; `snapshot` reaches `git.authentication`, `git.commands`, the `git.publication` and
verification probes, `git.worktrees.paths`, and `persistence` for the fetch, the `rev-parse` of the remote
head, the divergence counts and the local HEAD read, the branch name, and the reset-and-park its abort ends
in; `outcomes` calls its `persistence` sibling
for the finalize and the reset-and-park tail and `snapshot` for the unverified abort; and `persistence` calls
`git.commands` for the reset and clean. A patch that has to intercept the base fetch, the worktree root, the
dirty-file scan, the rev-list behind count, the pre- or post-rebase HEAD read, the rebase either sync path
runs, the crash recovery an eligibility gate triggers, the hardened git command a park, a rebase abort, or a
`rev-parse` runs, the authenticated push the publication leases, or the sibling
helper an owner delegates to therefore targets
`orchestrator.git.commands` / `orchestrator.git.authentication` / the probe owner / the owner module rather
than `base_sync`. Every base-sync
name still resolves on `base_sync` with the owner's exact identity, so historical imports and the three
keyword-call adapters -- the PR sync in `pr`, the conflict route in `conflicts`, and the crash recovery in
`recovery` -- keep working; but nothing inside the package reads a collaborator back off the facade,
so a test that has to intercept the per-worktree sync the refresh drives, the PR-aware coordinator it hands a
worktree off to, or the conflict route a failed rebase takes patches `refresh` / `pr` / `conflicts` and not
the facade.
The collaborators these owners reach *upward* are call-time imports: `persistence` binds the awaiting-human
park from `workflow/engine/guards.py` -- not from its own `guards` sibling, which owns the publication
refusals -- and the PR-comment poster straight off its owning module, and `publication` and `conflicts` bind
the same poster for their notices, so a patch for the park targets `orchestrator.workflow.engine.guards` and
one for any of the notices targets `orchestrator.workflow.engine.comments` -- the
`workflow` forward of `_park_awaiting_human` and the `base_sync` and `workflow_messages` forwards of
`_post_pr_comment` still resolve, but they are
not what these owners call. `orchestrator.workflow` is itself a package, and its initializer *is* that facade:
the lazy hooks are all that live there, and nothing in it reaches into `workflow/engine/` or `workflow/state.py`, so
importing the facade resolves no manifest target and pulls in neither the stage tree, the config and analytics
graph behind the shared dependency bindings, nor the git and GitHub
subsystems the targets sit on. An import that cheap is what lets the GitHub and git layers reach
`workflow/state.py` for the label vocabulary they are typed by -- a submodule import runs the initializer first, so
anything bound there would be a cost every one of them pays. `github/labels.py`, `github/issues.py`, and the
`git/base_sync/` owners all bind that owner directly, and `state_machine.py` forwards its
labels, graph, coercion, and guard for callers that still reach for the historical module. Config and analytics modules
retain their original import-time identity through `_workflow_dependencies.py`, so a diagnostic reload does not
silently rebind already-imported workflow leaves. The analytics package has its own import-only bootstrap so an
explicit package reload still reparses sink settings and keeps stale package holders isolated as before.

`workflow/engine/comments.py` is bound the same way. Its own helpers call each other directly -- both posters stamp the
marker and append to the id ledger in-module, and the thread read applies the per-comment trust filter in-module -- and
the workflow and stage leaves that post a comment, quote one, or read the thread import the owner rather than reaching
for the name on a facade. So a patch that has to intercept a posted issue or PR comment, the tracked-repos block, or
the conversation text a prompt quotes targets `orchestrator.workflow.engine.comments`; `workflow`,
`workflow_messages`, `workflow_drift`, and `base_sync` each still resolve their historical slice of those names to the
owner's exact object for callers outside the package.

`workflow/engine/messages.py` is bound the same way. It owns both halves of what an agent's last message is worth:
the strict markers read out of it -- the review and documentation verdicts, the drift `ACK:`, and the operator's
`/orchestrator continue` together with the refusal a guidance-free one earns -- and the stderr block a park comment or
log line carries when there was no usable message at all. Its own parsers call each other in-module, and the workflow
and stage leaves that read a verdict, quote a blockquote, or classify a continue import the owner. So a patch that has
to intercept a verdict parse, an ack read, a continue classification or refusal, or a stderr diagnostic targets
`orchestrator.workflow.engine.messages`; `workflow`, `workflow_messages`, and `workflow_drift` each still resolve
their historical slice of those names to the owner's exact object. The implementing stage keeps its own
`_as_blockquote` on `stages/_implementing_session_read.py`, so a patch aimed at that stage's quoting still targets the
stage leaf.

`workflow/engine/prompts.py` is bound the same way. It owns the prompt builders the stages share, and the reason they
sit together is that they share their parts: one header carrying the issue body and the trust-filtered thread text, one
foreground-only note appended by whichever of them can end in a commit, one commit-style note on the subset of those
whose agent also writes a subject (the conflict prompt takes the first without the second -- it replays subjects an
earlier commit already carried), and one set of placeholders for an empty body or thread. Each marker a prompt
promises -- `VERDICT:`, `DOCS: NO_CHANGE`, `ACK:`, the
fenced manifest -- is parsed by `engine/messages.py` or the manifest leaves, so the prompt and the parser that reads
its answer are edited as a pair. It reaches `comments.py` for the thread text and the tracked-repos block and
`messages.py` for the blockquote, and the stage leaves that build a prompt or append a note import the owner. So a
patch that has to intercept a built prompt, a shared note, or the single-decision comment targets
`orchestrator.workflow.engine.prompts`; `workflow`, `workflow_messages`, and `workflow_drift` each still resolve their
historical slice of those names to the owner's exact object. A prompt with only one caller stays with that caller:
`engine/drift.py` composes the drift-resume prompt beside the route that sends it and borrows just the two notes from
here, so a patch aimed at that prompt still targets the drift owner.

`workflow/engine/usage.py` is bound the same way. It owns what a tracked agent run is bookended by: the frozen request
a caller describes the run with, the `agent_spawn` / `agent_exit` audit pair, the analytics record the exit appends
(carrying the model read out of `extra_args` as the parser's fallback, and forwarding the prompt and worktree the
opt-in trajectory record is built from), and the `skill_triggered` events that record's return value drives. They
share the one request object, so a field added for the audit event is already the field the record and the skill
event repeat. `_now_iso` sits with them because the pinned-state stamps it writes — `last_agent_action_at`,
`last_review_at`, `decomposed_at`, the terminal `merged_at` — all mark when a run or its verdict landed. The
per-issue meter closes the same loop: the `UsageMetrics` the record attaches to the returned result is exactly what
`_accumulate_issue_usage` folds into the `issue_agent_runs` / `issue_total_tokens` / `issue_total_cost_usd` /
`issue_cost_sources` counters, and `_format_issue_usage_verdict` reads them back into the one receipt line
`_post_issue_usage_verdict` posts as a tracked comment at a terminal. The fold deliberately sits outside the spawn:
`_run_agent_tracked` writes no pinned state, so the handler that owns the write stays its only writer and an
interrupted run that never persists simply undercounts. Its own helpers call each other in-module, and every stage
leaf that spawns an agent, stamps a run, or folds its usage imports the owner, so a patch that has to intercept a
tracked run, its exit record, the emitted skill events, or the per-issue counters targets
`orchestrator.workflow.engine.usage`; `workflow` still resolves the whole group to the owner's exact object. The one
name it deliberately reaches back through the facade for is `run_agent`: that is the seam the stage tests replace to
drive a handler without a CLI, so `patch.object(workflow, "run_agent", ...)` stays the way to intercept the spawn
itself. Everything after the spawn is fail-open — the record and trajectory guards live inside
`analytics.record_agent_exit`, the skill emission carries its own here — because none of it is worth a run whose
audit pair already fired; an exception out of the spawn is the deliberate exception and propagates.

`workflow/engine/drift.py` is bound the same way. It owns what the orchestrator treats as the human's requirements —
one SHA-256 over the issue title, body, and the comments a human actually wrote — together with the six filters that
keep it from moving on content nobody wrote: the pinned-state comment, the hidden marker every posted comment carries,
the legacy ids from before that marker existed, third-party bots, authors outside `ALLOWED_ISSUE_AUTHORS`, and a bare
`/orchestrator continue`. The routes a real move is handed to sit with the hash because they are the only reason it is
computed: a mid-implementation drift resumes the locked dev session with the updated title, body, and thread quoted and
then advances `last_action_comment_id` past everything it quoted, so the next validating→in_review handoff does not
replay those comments as fresh PR feedback; a pre-implementation drift instead clears the manifest state, names the
children it stops tracking in a notice, and flips the label back to `decomposing`. It reaches `comments.py` for the
id ledger and the thread text, `messages.py` for the blockquote and the bare-continue test, and `prompts.py` for the
two shared notes, and every stage leaf that hashes, detects, resumes, or reroutes imports the owner. So a patch that
has to intercept a hash, a drift detection, the resume prompt or its watermark bump, or the decomposition reroute
targets `orchestrator.workflow.engine.drift`; `workflow` resolves the five names it published and `workflow_drift`
resolves the whole group to the owner's exact object.

`workflow/engine/guards.py` is bound the same way. It owns what a finished agent run is allowed to leave behind.
Two of its three helpers decline a run: `_ignore_if_interrupted` reads the shutdown sweep's kill off the result,
and `_paused_during_agent_run` re-reads `paused` / `backlog` off a **freshly fetched** issue, because the
dispatcher screened those labels once at tick start and the handler has been holding that snapshot for as long as
the agent ran. Both answer by returning True and letting the caller `return` without writing, so the pinned-state
mutations it staged in memory are simply dropped and the next tick re-derives the run from durable state. The
third, `_park_awaiting_human`, publishes one instead — the HITL comment, `awaiting_human`, a cleared
`park_reason`, the `last_action_comment_id` ratchet, and the `park_awaiting_human` event — and still leaves
`gh.write_pinned_state` to its caller, which is the rule all three share and the reason they sit together. It
reaches `comments.py` for the park comment, and every stage leaf that calls one of the three imports the
owner, so a patch that has to intercept an interruption check, a mid-run pause check, or a park targets
`orchestrator.workflow.engine.guards`; `workflow` still resolves all three names to the owner's exact object for
callers outside the package. The base-sync `persistence` owner reaches the park through a call-time import
instead, which is what keeps a workflow-layer module out of its import graph. Two parks sit outside the helper:
`_on_question` and `_on_dirty_worktree` on `stages/_implementing_parks.py` compose the same comment,
`awaiting_human` flag, `last_action_comment_id` ratchet, and `park_awaiting_human` event themselves, each
beside stage-specific state the helper does not write — the classified park reason and the silent-park counter
on one, the dirty-file count carried on the other's event — so a patch aimed at either targets the stage leaf.

Stage-private helpers stay private to their stage facade (`_bump_in_review_watermarks`,
`_seed_legacy_in_review_watermarks`, `_emit_conflict_round_incremented`). Cross-stage helpers like `_comment_created_at`
are re-exported from the facade because more than one stage reaches for them.

## Workflow labels

An issue should have at most one workflow label at a time. The set is `decomposing`, `ready`, `blocked`, `umbrella`,
`implementing`, `documenting`, `validating`, `in_review`, `fixing`, `resolving_conflict`, `question`, and the two
terminals `done` / `rejected`. The orchestrator also creates three non-workflow control labels: `backlog` and `paused`
each make per-tick handlers skip the issue entirely (`backlog` is a "not yet" hold on a fresh issue, `paused` freezes
an in-flight one), and `community_contribution` is applied by the per-tick open-PR sweep to PRs from non-bot authors
outside `ALLOWED_ISSUE_AUTHORS` so a human reviews them.

Label names are part of the public contract because live GitHub issues already carry them. For the meaning of each
label, the control-label semantics, and the per-stage transitions they trigger, see
[`state-machine.md#workflow-labels`](state-machine.md#workflow-labels).

## Process model

There is **only one long-lived process**: `python -m orchestrator.main`. It is wrapped by `run.sh` so the loop can
self-exit and be restarted with new code.

- **Trigger**: started manually (or by a wrapper). Optional `--once` for a single tick.
- **Tick cadence**: every `POLL_INTERVAL` seconds (default 60).
- **Self-restart guard** (`main._self_modifying_merge_happened`): each tick fetches `origin/<ORCHESTRATOR_BASE_BRANCH>`
  (default `main`); if it advanced past the process's startup SHA *and* the new commits touch `orchestrator/`, the loop
  exits 0 so the wrapper can re-exec the new code. The branch is decoupled from `BASE_BRANCH` so a target repo with a
  different default branch does not interfere with self-update detection.
- **Self-update resilience** (`run.sh self_update`): before each launch — at startup and after every
  self-modifying-merge restart — the wrapper fast-forwards the orchestrator checkout to
  `origin/<ORCHESTRATOR_BASE_BRANCH>`. It skips the pull and warns to stderr if a non-base branch is checked out, and
  warns and continues (rather than exiting) if the fast-forward fails (diverged base branch, rebase in progress, network
  error); either way it launches the existing working tree. A clean fast-forward still updates the tree before launch,
  so the self-modifying-merge flow keeps picking up new code. This is deliberate: under the production systemd unit
  (`Restart=always`) exiting on a self-update failure silently crash-loops the service with the orchestrator never
  running, so a stale-but-running process plus a journal warning is preferred — the warning is the operator's signal
  to restore the checkout.
- **Signals**: SIGINT/SIGTERM set a flag and call `scheduler.shutdown(wait=False)` synchronously so the submit path is
  closed mid-tick; the loop then stops at the next tick boundary and drains. The drain terminates in-flight agent and
  verify subprocess groups up front (`agents.terminate_all_running`) so a worker parked in a long agent / verify run
  unwinds in seconds instead of holding the process for up to `AGENT_TIMEOUT`. A daemon watchdog backstops the drain: if
  it overruns, the watchdog terminates those same groups and hard-exits (`os._exit(128+signum)`) so total signal→exit
  stays within `SHUTDOWN_GRACE_SECONDS` no matter what a thread is blocked on. A second Ctrl+C hits the re-armed kernel
  default handler and kills immediately.

The coding agent runs as a **transient child subprocess**, not a daemon — spawned per tick when work is needed.

## Per-tick flow (`workflow.tick`)

Each tick the polling loop fans `workflow.tick(gh, spec, scheduler=...)` out across **every configured repo** via
`main._run_tick`: single-repo deployments stay in-thread, multi-repo deployments use a `ThreadPoolExecutor` sized to the
repo count. A single long-lived `IssueScheduler` (global cap `MAX_PARALLEL_ISSUES_GLOBAL`, per-repo cap
`MAX_PARALLEL_ISSUES_PER_REPO`) is shared across all `tick` calls.

The dispatch loop classifies each issue as family-aware (`decomposing` / `blocked` / `umbrella` / unlabeled — parent
↔ child writes) or fan-out (everything else). Fan-out submits go one callable per issue. Every family-aware issue this
tick is folded into ONE bucket submit per repo that drains them sequentially on a single executor worker so a stale
child cannot starve the parent umbrella issue. When every family-aware issue in the bucket runs a no-agent handler
(`blocked` or `umbrella`), the bucket is cap-exempt and runs on a dedicated executor pool so a pure label / dep-graph
walk cannot be blocked by ordinary implementation work. A bucket containing `decomposing` or unlabeled pickup stays
cap-counted.

Per-issue durable state lives in a single **pinned comment** on the issue (`<!--orchestrator-state {...json...}-->`).
The orchestrator process is stateless; the label and the pinned JSON are the entire dispatch input.

For the full per-tick sequence (eligible-issue enumeration, family vs. fan-out partitioning, the pre-PR rebase /
PR-having clean-rebase + push (with `resolving_conflict` reached on actual rebase conflicts, plus the `fixing`
worktree-drift dead-lock breaker that hands a stuck validating-route transient fix-loop to `resolving_conflict` when the
worktree is behind base or carries an unpushed rebase), the `question` skip, the per-tick
external-merge sweeps, and the complete pinned-state JSON schema), see
[`state-machine.md#per-tick-flow-workflowtick`](state-machine.md#per-tick-flow-workflowtick).

## Stage handlers

Each workflow label dispatches to a `_handle_<label>` function. The handlers live under `orchestrator/stages/` (see the
module map above) and are re-exported from the `workflow` package initializer so test patches against
`workflow.<helper>` keep intercepting calls from inside a stage handler.

Most stage handlers run the user-content drift hook (`_compute_user_content_hash` → `_detect_user_content_change`) so
an out-of-band human edit re-routes the issue back to `decomposing` (when no dev session exists yet), resumes the locked
dev session with the updated body (implementing, validating, in_review, resolving_conflict), or unwinds back to
`validating` without resuming dev (documenting). Both halves of that hook sit on the `workflow/engine/drift.py` owner
the stage leaves import directly, so a patch aimed at the hook targets the owner rather than the facade.
`_handle_fixing` and `_handle_question` deliberately skip the drift
hook — see [`state-machine.md#user-content-drift-detection`](state-machine.md#user-content-drift-detection) for the
per-handler routing.

For per-stage internal flow — pickup, drift handling, decomposing, ready, blocked, umbrella, implementing,
documenting, validating, in_review, fixing, resolving_conflict, question — see
[`state-machine.md#stage-handlers`](state-machine.md#stage-handlers).

## Agent subprocess (`agents.run_agent`)

`run_agent(backend, prompt, cwd, ...)` dispatches to the per-backend runner (`codex.run_codex` /
`claude.run_claude`); `backend` is one of `"codex"` / `"claude"` and is re-validated at call time so a
misuse fails loudly. Both runners return a unified
`AgentResult(session_id, last_message, exit_code, timed_out, stdout, stderr, interrupted, usage)`. `interrupted`
(default `False`) flags a run the runner observed exiting on SIGTERM/SIGKILL — the shape the orchestrator's
shutdown sweep (`terminate_all_running`) produces when it kills an in-flight agent group — and is distinct
from `timed_out` (the orchestrator's own `AGENT_TIMEOUT` firing). `usage` (default `None`) is the parsed
`usage.UsageMetrics` `analytics.record_agent_exit` attaches during a tracked run so callers can read token /
cost metrics off the result without re-parsing stdout; it stays `None` for a result that never flowed through
`_run_agent_tracked` or whose usage parse failed (fail-open). The developer (implementing), reviewer
(validating), decomposer (decomposing), and question handlers consume it: `_accumulate_issue_usage` — in
`workflow/engine/usage.py`, which each of those handlers binds directly — folds
each run's `usage` into the per-issue `issue_agent_runs` / `issue_total_tokens` / `issue_total_cost_usd` /
`issue_cost_sources` counters on the pinned state
([`state-machine.md#pinned-state`](state-machine.md#pinned-state)); at each terminal (PR merge / reject, umbrella
close, closed question) `_format_issue_usage_verdict` beside it reads those counters back into one visible receipt
comment — the sole read-side consumer, and nothing gates on the figure. `CodexResult` is kept as a
transitional alias.

The role command specs (`DEV_AGENT` / `REVIEW_AGENT` / `DECOMPOSE_AGENT`), their parsing, the durable per-issue session
lock, and the resume mechanic are documented in [`workflow.md`](workflow.md). What follows is the subprocess shape only.

- **Codex command**:
  `codex exec [-C cwd | resume <sid>] --dangerously-bypass-approvals-and-sandbox --json -o <tempfile> <prompt>`. The
  `-o` path is a per-spawn `tempfile.mkstemp` outside the worktree (so target repos without `.codex-*` in `.gitignore`
  don't see it as untracked); `last_message` is read from it and the tempfile is cleaned up on any exit path by a
  per-spawn context manager (`codex.codex_last_message_file`).
- **Claude command**:
  `claude -p --dangerously-skip-permissions --output-format stream-json --include-partial-messages --verbose <prompt>`
  (with `--resume <sid>` when resuming). `last_message` is parsed from the stream-json: prefers the terminal
  `{"type":"result","result":...}` event (honored regardless of how the run ended), falls back to the last
  `assistant`/`message` text content for schema-drift forward-compat. The fallback is gated to clean, completed runs
  (`exit_code == 0`, not timed out, not interrupted); an interrupted or non-zero run with no terminal `result` event
  exposes an empty `last_message` rather than a partial transcript chunk.
- **Input**: prompt string; optional resume session id; timeout (`AGENT_TIMEOUT` / `REVIEW_TIMEOUT`).
- **Output**: `AgentResult(...)`. `session_id` is harvested by walking the JSONL events for any UUID-shaped value at
  `session_id` / `conversation_id` / etc. (shared between both backends).
- **Timeout cleanup** (`processes.terminate_process_group`): on timeout expiry the runner SIGTERMs the agent's whole
  process group (every spawn uses `start_new_session=True`), waits for the leader, then — mirroring the shutdown sweep
  (`terminate_all_running`) — probes the group with `killpg(_, 0)` and SIGKILLs any surviving descendant. Without the
  probe a build grandchild the agent forked (Maven, gradle, a JVM test runner) could keep mutating the worktree after
  the timeout was recorded — the failure mode that stranded a late clean commit behind the implementing-stage
  `agent_timeout` park.

### Environment filtering (`agents.environment.filter_agent_env`)

The agent subprocess env is filtered to keep host secrets and the orchestrator's own GitHub credentials out of agent
reach. The same filter runs for the verify-command runner (with `allow_provider_auth=False`, which also strips provider
keys).

- **GitHub-token-bearing env vars** are stripped (`GITHUB_TOKEN`, `GH_TOKEN`, etc. — the `_FORBIDDEN_AGENT_ENV`
  exact-match set) so a prompt-injected agent cannot push or call the GitHub API.
- **Production-secret-shaped env vars** are stripped by name shape: anything matching `_AGENT_SECRET_SUFFIXES`
  (`_TOKEN`, `_KEY`, `_SECRET`, `_PASSWORD`, `_PAT`, `_CREDENTIAL`) or the bare-name set (`TOKEN`, `KEY`, `SECRET`,
  `PASSWORD`, `PAT`, `CREDENTIAL`). Without this a `STRIPE_API_KEY` / `DATABASE_PASSWORD` set on the host would ride
  into a sandbox-bypassed agent or into the operator-configured verify shell.
- **Credential-file locators** are stripped too (`*_TOKEN_FILE`, `*_KEY_FILE`, `*_SECRET_FILE`, `*_PASSWORD_FILE`,
  `*_CREDENTIAL_FILE`, `*_CREDENTIALS`, `*_CREDENTIALS_FILE`, plus bare `TOKEN_FILE` / `CREDENTIALS` /
  `CREDENTIALS_FILE`). The most important case is `ORCHESTRATOR_TOKEN_FILE`, the orchestrator's own write-credential
  locator.
- **Write-credential locators** (`_AGENT_WRITE_CREDENTIAL_LOCATORS`: `SSH_AUTH_SOCK`, `SSH_ASKPASS`, `GIT_ASKPASS`,
  `GIT_SSH_COMMAND`) are stripped by exact name. The orchestrator's own push path constructs its own `GIT_ASKPASS`
  tempfile.
- **Provider auth** required to reach the agent's own model is allowlisted by exact name in
  `_AGENT_PROVIDER_AUTH_ALLOWLIST` (`ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, `CLAUDE_CODE_OAUTH_TOKEN`,
  `OPENAI_API_KEY`) for agent subprocesses only. The verify runner passes `allow_provider_auth=False` and strips them
  too — a verify shell executes untrusted agent-produced code, and the verify-failure park comment publishes the
  offending command verbatim. Advanced deployments (Bedrock, Vertex, custom proxies) extend the allowlist explicitly.
- **`GIT_AUTHOR_*` / `GIT_COMMITTER_*`** are injected from `AGENT_GIT_NAME` / `AGENT_GIT_EMAIL` (default
  `agent-orchestrator <agent-orchestrator@users.noreply.github.com>`) so agent commits are stamped with the
  orchestrator's identity regardless of the host's `~/.gitconfig`.

## Push path (`workflow._push_branch`)

The orchestrator (not the agent) pushes. The push is hardened against the agent-controlled worktree:

- Token delivered via `GIT_ASKPASS` tempfile, never argv.
- Detaches from `~/.gitconfig` and `/etc/gitconfig` (`GIT_CONFIG_GLOBAL=/dev/null`, `GIT_CONFIG_SYSTEM=/dev/null`).
- Disables `core.hooksPath`, `credential.helper`, `core.fsmonitor`.
- Refuses to push if the config the push resolves — the worktree's local config plus any `include.path` file or
  per-worktree `config.worktree` it pulls in, with global/system detached — carries any `url.*.insteadOf` /
  `pushInsteadOf` rewrite or any `http.*` proxy/TLS setting (e.g. `http.proxy`, `http.sslVerify=false`) that could
  tunnel the token-bearing push through an attacker proxy or disable certificate verification. Env-var proxies
  (`https_proxy`) are operator-set and stay honored — only agent-writable config-file transport is rejected.
- Pushes via explicit refspec `HEAD:refs/heads/<branch>` (no upstream stored).

## Observability

Four independent observability surfaces — an opt-in audit event log, a project-local analytics JSONL sink, an opt-in
(default-off) trajectory JSONL sink that `record_agent_exit` fills with redacted, head/tail-truncated per-run reasoning
trajectories — each carrying a denormalized run-level token-usage / cost summary (plus a claude-only per-turn
breakdown) alongside the step timeline — and an operator-deployed Postgres aggregation target (with a Streamlit
dashboard and the `orchestrator/usage.py` parser that feeds it). The trajectory sink has its own separate Streamlit page
— the file-backed trajectory viewer (`orchestrator/trajectory_dashboard.py` over the pure
`orchestrator/trajectory_reader.py`), which reads the JSONL directly (usage and cost included) and needs no Postgres.
None of them feed back into dispatch: workflow correctness keys off the pinned state JSON and the workflow label, so
every surface is observation-only and safe to truncate, rotate, or delete.

For the per-sink schema, event-kind tables, append / retention / rotation semantics, the analytics-DB compose layout,
the sync / read-model / dashboard wiring, and the usage parser's cost-precedence rules, see
[`observability.md`](observability.md).

## Summary of "what runs when"

- **`main` polling loop** — long-lived Python process. Trigger: manual start (or wrapper). Cadence: every
  `POLL_INTERVAL`s.
- **`workflow.tick(gh, spec)`** — function call. Trigger: each loop iteration. Cadence: once per tick per configured
  `RepoSpec`; multi-repo fans out across a `ThreadPoolExecutor`, single-repo stays in-thread.
- **`_refresh_base_and_worktrees(gh, spec)`** — function call. Trigger: start of each `workflow.tick`. Cadence: once
  per tick per repo: one `git fetch <spec.remote_name> <spec.base_branch>`, then per-worktree dispatch (pre-PR worktrees
  rebase directly; PR-having worktrees behind base are rebased + pushed in the refresh itself via
  `_sync_pr_worktree_to_base` and routed to `validating` on success, with `resolving_conflict` reached when the auto
  rebase actually leaves conflicted files).
- **`_handle_*` per issue** — function call. Trigger: issue's workflow label. Cadence: once per tick per open issue;
  concurrent up to `spec.parallel_limit` per repo and `MAX_PARALLEL_ISSUES_GLOBAL` across all repos. No-agent family
  buckets (`blocked` / `umbrella`) are cap-exempt.
- **decomposer agent (`DECOMPOSE_AGENT`)** — subprocess (fresh or resumed). Trigger: `_handle_decomposing` (retry
  budget OK) or HITL resume. Cadence: one shot per tick when needed.
- **implementer agent (`DEV_AGENT`)** — subprocess. Trigger: `_handle_implementing` (no commits yet, retry budget OK)
  or HITL resume. Cadence: one shot per tick when needed.
- **reviewer agent (`REVIEW_AGENT`)** — subprocess (fresh session). Trigger: `_handle_validating`, round < max.
  Cadence: one shot per tick.
- **dev-fix agent** — subprocess (resumed dev session). Trigger: reviewer says CHANGES_REQUESTED (dispatched from
  `_handle_validating` after the relabel to `fixing`), or fresh in_review PR feedback (dispatched from `_handle_fixing`
  after the quiet window) — both run with `stage="fixing"` and bounce back to `validating` for re-review. Cadence: one
  shot per tick.
- **`_handle_resolving_conflict`** — function call. Trigger: issue label `resolving_conflict` (operator relabel,
  refresh-time conflicted rebase, or the `fixing` worktree-drift dead-lock breaker when a stuck validating-route
  transient fix-loop is out of sync with the PR head — behind base or an unpushed local rebase); also fires on
  closed-`resolving_conflict` issues from the polling sweep. Cadence: once per tick per such issue.
- **dev-conflict agent** — subprocess (resumed dev session). Trigger: `_handle_resolving_conflict` and `git rebase`
  left conflicts. Cadence: one shot per tick.
- **`_handle_question`** — function call. Trigger: issue label `question` OR closed-`question` issue from the polling
  sweep. Cadence: once per tick per such issue.
- **question agent (`DECOMPOSE_AGENT` backend)** — subprocess (read-only). Trigger: `_handle_question` (no prior
  session OR new human comment on a parked Q&A). Cadence: one shot per tick when needed.
- **`git push`** — subprocess. Trigger: after dev produces clean commits. Cadence: per fix.
- **self-restart check** — git fetch + diff. Trigger: start of each tick. Cadence: every tick.

## Architecture schema

```
                     ┌──────────────────────────────────────┐
                     │   GitHub repo(s) (REPO or REPOS)     │
                     │   ─ issues (with workflow labels)    │
                     │   ─ pinned state comment per issue   │
                     │   ─ branches / PRs                   │
                     └──────────────┬───────────────────────┘
                                    │ PyGithub (one token per slug)
                                    │
   ┌────────────────────────────────┴─────────────────────────────────────┐
   │  orchestrator process  (python -m orchestrator.main)                 │
   │  ───────────────────────────────────────────────────                 │
   │   main.py                                                            │
   │     startup: build per-spec [(spec, GitHubClient), ...] from         │
   │              config.default_repo_specs(); ensure_workflow_labels;    │
   │              build one shared IssueScheduler(global_cap, per_repo)   │
   │     loop every POLL_INTERVAL s:                                      │
   │       1. self-restart check (origin/<ORCHESTRATOR_BASE_BRANCH>       │
   │          moved & touches orchestrator/?)                             │
   │       2. _run_tick(clients, scheduler):                              │
   │            N == 1 → in-thread workflow.tick(gh, spec, scheduler)     │
   │            N  > 1 → ThreadPoolExecutor fans workflow.tick across     │
   │                     one worker thread per repo                       │
   │       3. scheduler.reap()  (drain completions; surface failures)     │
   │       4. analytics.prune_with_retention_logging()                    │
   │     shutdown: scheduler.shutdown(wait=True) drains workers on        │
   │               --once / self-restart; a signal stop first kills       │
   │               in-flight agent+verify groups, and a watchdog          │
   │               hard-exits within SHUTDOWN_GRACE_SECONDS on overrun    │
   │                    │                                                 │
   │                    ▼                                                 │
   │   workflow.tick(gh, spec, scheduler) →                               │
   │     _refresh_base_and_worktrees(gh, spec, scheduler): skip           │
   │       worktrees whose handler is still in flight in scheduler        │
   │     classify each pollable issue and submit to scheduler:            │
   │       family-aware (decomposing/blocked/umbrella/unlabeled) →        │
   │         ONE bucket submit per repo that drains sequentially          │
   │         (cap-exempt when every family issue is `blocked` or          │
   │         `umbrella`)                                                  │
   │       fan-out (everything else) →                                    │
   │         one submit per issue, concurrent up to per-repo / global     │
   │         caps                                                         │
   │     scheduler rejects duplicate active / cap hit / family-slot       │
   │       conflict → skipped this tick AND logged with reason            │
   │     accepted workers call gh._for_worker_thread() + refetch the      │
   │       Issue, then run _process_issue → dispatch by label             │
   │                                                                      │
   └─────────┬───────────────────────────────────────┬────────────────────┘
             │ subprocess                            │ subprocess (hardened)
             ▼                                       ▼
   ┌─────────────────────────────┐         ┌─────────────────────────────┐
   │  coding-agent CLI           │         │  git push                   │
   │  (codex or claude,          │         │  ─ GIT_ASKPASS tempfile     │
   │   per-issue worktree)       │         │  ─ no global/system config  │
   │  ─ env: GH tokens stripped  │         │  ─ hooks/helper disabled    │
   │  ─ env: GIT_AUTHOR/COMMITTER│         │  ─ refuses url/http cfg     │
   │     stamped (orchestrator)  │         └──────────────┬──────────────┘
   │  ─ provider auth left alone │                        │
   │  ─ --bypass / --skip perms  │                        │
   │  ─ JSONL → session_id       │                        │
   │  ─ last_message: -o (codex) │                        │
   │     or stream-json (claude) │                        │
   └──────────────┬──────────────┘                        │
                  │ commits to                            │ pushes branch to
                  ▼                                       ▼
   ┌─────────────────────────────────────────────────────────────────────┐
   │  git worktree:  <WORKTREES_DIR>/<owner>__<name>/issue-<n>           │
   │  branch:        orchestrator/<owner>__<name>/issue-<n>              │
   │  ─ slug subdir + slug-namespaced branch keep two repos sharing a    │
   │    target_root from colliding on the same `orchestrator/issue-<n>`  │
   │  ─ created from <spec.remote_name>/<spec.base_branch>               │
   │    in spec.target_root                                              │
   │    (or reused if has unpushed commits)                              │
   └─────────────────────────────────────────────────────────────────────┘
```

## State transition (label lifecycle)

The compact label-lifecycle diagram for every forward, fix-loop, terminal, and HITL-park transition lives in
[`state-machine.md#state-transition-label-lifecycle`](state-machine.md#state-transition-label-lifecycle).
