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
      __init__.py       package marker only; reserved for the remaining
                        shared-helper owners
      comments.py       the orchestrator marker and capped id ledger both
                        comment posters write, the trusted-author thread read
                        every prompt quotes, and the tracked-repos block
      dispatch.py       one tick's pollable issues turned into handler calls:
                        the hard-skip filter, the family / fanout partition and
                        its cap exemptions, the per-worker refetch, the
                        scheduler submits, and the timed per-issue dispatch
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
      pickup.py         an unlabeled issue's first tick: the author allowlist,
                        the `DECOMPOSE` route, the pickup comment / hash /
                        label / state a start publishes, and the same-tick
                        dispatch to the chosen stage
      prompts.py        the prompt builders the stages share (implement,
                        respawn, review, documentation, fix, conflict, question
                        and its followup, PR-comment followup, decompose) plus
                        the commit-style / foreground-only notes, the
                        empty-body placeholders, and the single-decision
                        comment
      terminals.py      how an issue stops being worked: the merged, rejected,
                        and human-closed arcs with their stamps, receipts,
                        events, issue close, and branch cleanup, plus the
                        PR-holding drain and the two entry-time finalizers
      tick.py           one repo's polling pass: the base refresh, the
                        community-contribution sweep, the skill-catalog
                        emission, and the scheduler handoff or the sequential /
                        bounded-parallel in-tick execution behind it
      usage.py          the tracked agent run: the request model, the audit
                        spawn/exit pair, the analytics record and its
                        configured-model fallback, the `skill_triggered`
                        emission, the per-issue counters that record's usage is
                        folded into and the terminal receipt read off them, and
                        the UTC stamp the stages write
    stages/
      __init__.py       package marker only; one subpackage per stage, each
                        owning its label's handler
      conflicts/
        __init__.py     package marker only; callers import an owner directly
        handler.py      the order one tick asks its questions in: the
                        missing-`pr_number` park, the terminal arcs, the
                        body-edit resume, and the rebase behind them
        routing.py      the awaiting-human resume and `MAX_CONFLICT_ROUNDS` cap
                        that gate the rebase, plus the worktree it runs in
        guards.py       the worktree restore and the two probes that prove a
                        stale PR head is safe to force-publish over
        divergence.py   the park a behind-base worktree earns, the one lease
                        that excuses it, and the crash-recovered push
        rebase.py       the branch / base fetches, the rebase, its
                        `merge_attempt` event, and the three-way disposition
        publication.py  the dirty park, the no-op flip, the rebased-head push,
                        and the hand-off of real conflicts to the dev
        resume.py       the three dev-resume entry points, the shared run, and
                        the `/orchestrator continue` classification
        outcomes.py     the interrupt / timeout / mid-rebase parks read before
                        HEAD, and the push a completed resolution earns
        transitions.py  the park-and-write pair and the pushed-round tail every
                        exit shares
        models.py       the frozen records the owners hand each other
        state.py        the counter keys they share
      decomposition/
        __init__.py     package marker only; callers import an owner directly
        state.py        the pinned-state field names the owners share, the
                        held-child alias, and the issue-reference renderer
        models.py       the run plan and its worktree policy, the locked
                        session, the split plan, and the child scan
        manifest.py     the fenced-block envelope rules, the JSON decode, and
                        the parse entry point the stage routes on
        validation.py   what a `split` payload must satisfy: the child cap the
                        decompose prompt states, each child's shape, and the
                        acyclicity of the graph they declare
        session.py      the locked decomposer session: the spec read, the
                        fresh spawn that pins it, the human-reply resume, and
                        the drift reset that retires it
        run.py          one `decomposing` tick: the drift / recovery / kill
                        switch order before the agent, and the pause, dirty
                        worktree, and interruption checks after it
        outcomes.py     the three dispositions of a finished reply: the
                        unparsed park, the `single` finalize, and the `split`
                        hand-off
        recovery.py     what a tick that died mid-split left behind: the
                        stale-manifest markers, the orphan-child repair, and
                        the incomplete park
        split.py        the crash-safe order a `split` manifest becomes child
                        issues in, and the summary / label / activation tail
        parents.py      the fresh child scan, the rejected and manually-closed
                        parks it earns, and the parent's own drift reroute
        activation.py   the dep-graph walk that releases the next children and
                        the held-dependency line it logs
        blocked.py      the `blocked` poll and the `ready` handoff to
                        implementing with its consumed-comment ratchet
        umbrella.py     the `umbrella` poll and the close its all-done branch
                        earns instead of an implementation pass
      documenting/
        __init__.py     package marker only; callers import an owner directly
        handler.py      the order one final-docs tick asks its questions in
        preconditions.py
                        the terminals, the missing-`pr_number` guard, the
                        parked-no-input fast path, and the refused bare continue
        drift.py        a body edit mid-hop: the dropped approval, the unwind
                        sentinel, and the relabel back to `validating`
        drift_reset.py  the fetch / probe / hard-reset + clean that puts the
                        worktree back on the PR head, and the parks each failure
                        earns
        run.py          the branch refresh and diverged-worktree guard, plus the
                        resume / recovered-commit / fresh-spawn shapes
        outcomes.py     the timeout / dirty / commit / `DOCS: NO_CHANGE` order a
                        finished run is read in
        publication.py  the push, the docs watermarks it stamps, and the PR
                        notice it posts
        handoff.py      the `pr_last_comment_id` ratchet that keeps in_review
                        from replaying a consumed reply, and the relabel
        parks.py        the shared awaiting-human park and the missing-PR,
                        dirty-tree, and question parks
        models.py       the frozen records the owners hand each other
        state.py        the pinned-state keys they share
      fixing/
        __init__.py     package marker only; callers import an owner directly
        handler.py      the order one tick asks its questions in, plus the
                        preflight terminals / missing-`pr_number` park it runs
                        before the fix loop can start
        feedback.py     the rescan past the three in_review watermarks and the
                        narrower ratchet a consumed batch advances them by
        bookmarks.py    the `pending_fix_*` ids a replay rebuilds the triggering
                        batch from, and the clear each finished round earns
        continue_command.py
                        `/orchestrator continue` on a parked fix: the replay,
                        the two refusals, and the guidance passthrough
        parked.py       the four answers an `awaiting_human` tick can reach and
                        the order they are asked in
        drift.py        the `resolving_conflict` reroute a stuck validating-route
                        park earns when its worktree has fallen behind base
        resume.py       the quiet window, the dev run, the ACK fast path, and
                        the `validating` relabel a pushed fix earns
        models.py       the frozen records the owners hand each other
        state.py        the pinned-state keys they share
      implementing/
        __init__.py     package marker only; callers import an owner directly
        handler.py      the order one tick asks its questions in
        spawn.py        awaiting-human vs active, the recovered-worktree
                        shortcut, and the retry-gated fresh spawn
        session_read.py the locked session read plus the stale / overflow /
                        quota classifiers and the blockquote they quote with
        session.py      the three session retirements, the per-issue 24h spawn
                        cap, and the fresh-spawn prompt
        resume.py       the two resume entry points and the historical call
                        shape they keep
        execution.py    one resume, its poisoned-session retry, and what each
                        attempt is allowed to persist
        worktree.py     the checkout a resume runs in, restored when reaped
        disposition.py  the `before_sha` publish / timeout-park decision and
                        the timeout park's own next-tick recovery
        parks.py        the session-limit, question, silent-failure, and
                        dirty-tree parks
        publication.py  the push, the PR reuse or open, and the validating
                        handoff with its counter resets
        drift.py        a body edit mid-implementation: the resume it earns and
                        the `ACK:` that answers it
        drift_preflight.py
                        a pre-session edit and the quiet timeout recovery
        continue_command.py
                        `/orchestrator continue` on a parked issue
        question_relabel.py
                        the question -> implementing relabel guards
        models.py       the frozen records the owners hand each other
        state.py        the pinned-state keys and CLI marker tuples they share
      in_review/
        __init__.py     package marker only; callers import an owner directly
        handler.py      the order one tick asks its questions in, and the
                        missing-`pr_number` park asked before the rest
        feedback.py     the four surfaces scanned before the drift check, their
                        orchestrator / untrusted-author filters, and the park
                        that stays silent for the base-sync retry loop
        fixing_route.py the pending-fix bookmarks, the hash refresh, and the
                        `fixing` relabel
        drift.py        a body edit on an open PR: the unread PR conversation
                        captured first, the dev resume, and the `validating`
                        return both outcomes earn
        merge_gate.py   the unmergeable park and the one HITL ready-ping an
                        approved, unvetoed head earns per head SHA
        watermarks.py   the one-way issue-side ratchet and the legacy seed a
                        manually-relabeled issue needs
        models.py       the per-tick handles and the drift-resume record
        state.py        the issue-side watermark key they share
      question/
        __init__.py     package marker only; callers import an owner directly
        handler.py      the order one tick asks its questions in, the
                        closed-issue finalize that outranks them, and both
                        worktree teardowns
        run.py          the resume / fresh-spawn routes, the tracked spawn they
                        share, and the park funnel every exit lands on
        session.py      the locked question-agent identity, the trusted-reply
                        consume, and both prompt builders
        outcomes.py     the read-only violations checked before any answer, and
                        the park each outcome earns
        models.py       the tick record, the locked session, and the outcome
        state.py        the park reasons and pinned-state keys they share
      validating/
        __init__.py     package marker only; callers import an owner directly
        handler.py      the order one review tick asks its questions in, and
                        the terminals it opens with
        reviewer.py     the round cap, the tracked reviewer spawn and its two
                        refusals, and the verdict fan-out
        approval.py     the verify gate, approval comment, optional squash, and
                        the in_review watermark seed before the `documenting`
                        relabel
        verify.py       how a non-ok verify result reads and the park it earns
        watermarks.py   the seed walk past leading orchestrator comments and the
                        ratchet that never regresses one
        requested_changes.py
                        the PR feedback and `fixing`-labeled dev fix, plus the
                        no-VERDICT park
        dev_fix.py      what a finished dev fix leaves behind: the stranded
                        commit probe, the push, and the round bump
        awaiting.py     the three park-reason claims on a human reply and the
                        dev attempt they fall through to
        awaiting_resume.py
                        the order those claims are asked in and the resume none
                        of them wanted
        drift.py        a body edit mid-review, the three parks that defer, and
                        the consumed-thread watermark
        drift_outcomes.py
                        the `ACK:` reply that must not park, over the shared fix
                        disposition
        recovery.py     the silent retry of a push race or dev timeout
        models.py       the frozen records the owners hand each other
        state.py        the pinned-state keys, park reasons, and outcome tokens
                        they share
  _workflow_export_manifest.py / _workflow_exports.py
                        immutable historical inventory and lazy resolver hooks
  _workflow_dependencies.py
                        import-time config/analytics bindings shared by leaves
  _workflow_state.py    immutable values the engine owners share: the logger,
                        the per-issue failure log line, and the issue-state
                        attribute and its open / closed values
  workflow_drift.py     lazy user-content-drift compatibility facade
  workflow_messages.py  lazy prompt/parser/comment compatibility facade
  _workflow_messages_state.py
                        the section separator its prompt leaves share
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
    _read_*.py          the manifest and resolver hooks, plus the seven raw
                        leaves beneath `read_raw.py`, the seven rollup leaves
                        beneath `read_rollup.py`, and the nine breakdown and
                        skill leaves beneath `read_dashboard.py`, which forward
                        to the query owners
    read_dashboard.py   historical import site for the four breakdown and
                        three skill reads that moved
    predicates.py / _predicate_*.py / read_request*.py / read_models*.py / read_raw.py / read_rollup.py
                        historical filter, request-model, keyword-binding,
                        result-model, raw-read, and rollup-read import sites
                        forwarding to the query owners
    sync.py / _sync_*.py
                        CLI, ingestion, row parsing/mapping, and database lifecycle
  dashboard.py          lazy compatibility facade and direct Streamlit entrypoint
  dashboard_*.py        stable component, read, chart, state, and widget hubs
  _dashboard_*.py       bootstrap/hooks plus focused render, query, and chart leaves
  usage.py              temporary compatibility site re-exporting the usage
                        owners under observability/usage/
  trajectory_reader.py  pure file-backed filter and summary read model
  _trajectory_*.py      record/view models, parsing, filtering, and file-read leaves
  trajectory_dashboard.py
                        lazy compatibility facade and direct Streamlit entrypoint
  _trajectory_dashboard_*.py
                        viewer bootstrap, page controls, rendering, and HTML leaves
  observability/
    __init__.py         package marker only; home of the usage parsers, the
                        analytics configuration, recording, retention, and
                        read-path owners beside them, and the destination the
                        observation-only surfaces above migrate the rest of
                        their responsibilities to
    analytics/
      __init__.py       package marker only; home of the sink configuration,
                        its append side, the by-age prune that bounds it, and
                        what a read is asked for, dials with, and answers with
      config.py         the six sink / database environment knobs, the parse
                        the flat package's bootstrap binds, the `Settings`
                        view every adapter reads one back through, and the
                        read-path URL fallback
      retention.py      the three prune entry points: the polling tick's
                        fail-open wrapper and one by-age prune per sink
      retention_scan.py the timestamp a record is judged by and the split of
                        a file into kept lines and a removed count
      retention_rewrite.py
                        the same-directory temp file, the atomic replace, and
                        the lock held across the read and that swap
      recording/        the append side of that sink
        __init__.py     stable recording surface: the six recorders a
                        producer appends through (`__all__`)
        events.py       the record envelope, the sink append under it, and
                        the four producer-facing recorders
        io.py           the locked JSONL append both sinks write through,
                        and the one lock each of them holds
        models.py       typed requests and the keyword signatures a call
                        is bound through
        agent_exit.py   the order one finished run is summarized and
                        written in
        usage.py        token / cost parsing for that run
        skills.py       its opt-in skill fields
        catalog.py      the out-of-band Codex capabilities they fall back to
      query/            the read side of the Postgres target
        __init__.py     package marker only; callers import an owner directly
        connections.py  the deferred driver import, the two connect factories
                        under it, and the one exception a driver failure is
                        wrapped in
        connection_cache.py
                        the persistent socket one thread reuses, and the
                        changed URL or torn-down socket that evicts it
        execution.py    the resolved inputs one read carries, and the single
                        SELECT run on a caller-owned or freshly opened
                        connection
        requests.py     the keyword vocabulary every public read is called by,
                        and the bind of one call into the typed request
        request_models.py
                        the filters, connection, and options that request is
                        made of
        filters.py      the selection a read narrows by, its three scoped
                        projections, and the builder a clause and its bindings
                        accumulate in
        predicates.py   the `WHERE` clause that selection becomes against the
                        events table, the agent-run view, and the daily rollup
        conditions.py   the two splices of a table's own required condition,
                        and the probe for an event filter that leaves a
                        view-backed read no rows
        activity_models.py
                        the cells a volume is bucketed into by when it happened
        overview_models.py
                        the values a window's filters offer, how far its data
                        reaches, what it totals, and its daily series
        cost_models.py  the axes one window's spend is broken down along
        run_models.py   the run, issue, and traced-event rows, and the accessor
                        behind the trace row's `result` alias
        skill_models.py the cells a skill's reach is reported in, and the share
                        each derives
        raw_reads.py    the six reads that stay on the events table rather than
                        the day-bucketed rollup above it
        filter_options.py
                        the unioned distinct-value scan behind the dropdowns,
                        and the bucketing of its tagged rows
        event_breakdowns.py
                        the per-event count inside one window
        agent_exits.py  the newest agent runs in a window, and the selections
                        that leave the table nothing to ask for
        issue_summaries.py
                        the per-issue aggregate scan and the two orderings it
                        is read in
        issue_events.py one issue's event trace, oldest first
        query_rows.py   the named columns the widest SELECT lists are read
                        back through
        raw_values.py   the coercion one raw column is narrowed by, and the
                        cleared multiselect no row can match
        rollup_reads.py the seven reads answered off the day-bucketed rollup
                        rather than the events table beneath it
        summary_queries.py
                        the one round-trip a window's totals and both its
                        breakdowns come back from
        summary_results.py
                        the ranking those breakdowns are read in, and the
                        trailing fields a short totals row leaves at default
        kpi_totals.py   the trimmed previous-window scan a delta is measured
                        against
        time_series.py  one window's volume, spend, and tokens per day and
                        event
        stage_breakdowns.py
                        what each workflow stage counted, cost, and served
                        from cache
        backend_efficiency.py
                        what each backend ran, failed, and spent
        repo_breakdowns.py
                        each repository's share of one window
        throughput_days.py
                        the two terminal stages each day resolved or turned
                        away, and the selections that leave nothing to count
        breakdown_reads.py
                        the four reads whose grouping key the day-bucketed
                        rollup threw away
        review_rounds.py
                        what a window cost per review round, and per role
                        inside each one
        cost_coverage.py
                        which sources that spend could be attributed to
        backend_tokens.py
                        each backend's share of the window's tokens, day by
                        day
        hourly_heatmaps.py
                        one weekday-and-hour activity cell, bucketed in the
                        zone the caller asked for
        skill_reads.py  the three reads answered from the `extras` blob no
                        table above the events one carries
        skill_trigger_rates.py
                        how often each role-and-backend cohort reached for a
                        skill at all
        skill_matrices.py
                        which of a repository's offered skills each cohort
                        triggered, and the catalog scan the zeros come from
        skill_adoption.py
                        how many sessions that could have used a skill did,
                        and the diagnostics beside that ratio
        skill_sessions.py
                        which rows are one logical session, and how far back
                        its evidence reaches
        skill_values.py the cohort a skill cell is filed under, the JSONB
                        payload it is read from, and the matrix ranking
        cache_shares.py the token share one row's cost is split into cache
                        and no-cache bands by, per scan target
        row_cells.py    the readings one rollup cell passes through before it
                        lands in a result field
      sync/             destination for the JSONL -> Postgres ingestion
      trajectories/     the opt-in per-run reasoning sink
        __init__.py     package marker only; callers import an owner directly
        models.py       the head/tail and whole-record caps, the view they are
                        read back through, and the headline and running budget
                        one record is charged as
        sanitize.py     leaf-by-leaf redaction and head/tail truncation
        serialize.py    the record's shape and the order its arrays are
                        charged to the budget in
        persistence.py  the opt-in gate, the parse, the Codex backfill, and
                        the fail-open guard around the write
        api.py          the sink append a caller outside a tracked run
                        reaches
    usage/              the provider payload parsers
      __init__.py       stable parser surface: the nine parsers and the
                        five result types they return (`__all__`)
      protocol.py       shared JSONL vocabulary and parser type aliases
      event_stream.py   resilient line decoding and shared value helpers
      prices.py         first-party claude / codex rate tables
      model_names.py    model-name extraction from nested payload paths
      metrics.py        `UsageMetrics` and the token / cost entry points
      claude_*.py       claude frame decoding, aggregation, and turn count
      codex_*.py        codex cumulative frame decoding and run summary
      skills.py         `SkillTriggers` and the skill-evidence entry points
      skills_*.py       claude tool-use and codex command observation
      skill_commands.py codex SKILL.md reference classification by tier
      shell_segments.py quote-aware command unwrapping and segmentation
      trajectory.py     the per-provider trajectory entry points
      trajectory_models.py
                        the step / turn / trajectory records they return
      trajectory_*.py   claude block, stream, and turn plus codex rebuild
    dashboard/          destination for the Streamlit analytics page
    trajectory_viewer/  destination for the file-backed trajectory page
  skills/               the two skill-enumeration owners
    __init__.py         package marker only; callers name an owner
    catalog.py          per-tick repo skill-catalog collection: enumerate
                        SKILL.md definitions on the target base ref and
                        append one `repo_skill_catalog` analytics record
    discovery.py        per-run filesystem skill discovery and codex tool
                        list, plus the skill roots and SKILL.md marker
                        `catalog.py` reads back
  skill_catalog.py      temporary compatibility site re-exporting the skills
                        owners under skills/
  stages/
    <stage>.py          temporary forwarder for each historical stage, reading
                        every name back off its owners under `workflow/stages/`
    _<stage>_exports.py / _<stage>_export_manifest.py
                        stage-specific lazy hooks and complete inventories
```

`workflow/__init__.py`, `worktrees.py`, `analytics.read`, and `dashboard.py` publish explicit sorted `__all__`
inventories, `.pyi` surfaces, and immutable target registries. Resolution is lazy and cached on the facade, but the
resolved object is the implementation object's exact identity. Existing direct imports, wildcard imports, and
`patch.object` calls therefore keep working. Base-sync names still resolve on the `base_sync` facade with their
owner's exact identity, and the publication helpers stay patchable by name on `branch_publication` (or on `worktrees` /
`workflow`) for the callers that still read them off a facade. Inside `git/publication/`, though, the owners bind their
collaborators directly -- `probes` calls `git.commands`, `titles` calls `probes`, `planning` calls `git.commands`,
both siblings, and the verification probes for its HEAD and dirty-file guards, `rewrite` calls `git.commands`,
`git.authentication`, and the verification probes, and `squash` calls `planning` and `rewrite` -- so a patch that has
to intercept the hardened reset, the force-push, or the plan a rewrite spends targets the owner module. The stage
side is bound that way too: validating's approval arc calls `squash._squash_and_force_push` directly, so a mock that
has to intercept the squash a review approval runs targets `git.publication.squash` even though the name itself keeps
resolving on `branch_publication`, `worktrees`, and `workflow` for the historical callers.
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
`orchestrator.git.authentication` / the owner module, not `worktree_lifecycle`.
`workflow/stages/question/handler.py` and
`workflow/engine/terminals.py` call `terminal._cleanup_question_worktree` / `terminal._cleanup_terminal_branch`
directly — the terminal owner reading its branch name off `worktrees.paths` first —
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
the lazy hooks are all that live there, and nothing in it reaches into `workflow/engine/`, `workflow/stages/`, or
`workflow/state.py`, so importing the facade resolves no manifest target and pulls in neither the stage tree, the
config and analytics graph behind the shared dependency bindings, nor the git and GitHub
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
`_as_blockquote` on `workflow/stages/implementing/session_read.py`, so a patch aimed at that stage's quoting still
targets the stage owner.

`workflow/engine/prompts.py` is bound the same way. It owns the prompt builders the stages share, and the reason they
sit together is that they share their parts: one header carrying the issue body and the trust-filtered thread text, one
foreground-only note appended by whichever of them can end in a commit, one commit-style note on the subset of those
whose agent also writes a subject (the conflict prompt takes the first without the second -- it replays subjects an
earlier commit already carried), and one set of placeholders for an empty body or thread. Each marker a prompt
promises -- `VERDICT:`, `DOCS: NO_CHANGE`, `ACK:`, the
fenced manifest -- is parsed by `engine/messages.py` or the decomposition stage's manifest owners, so the prompt and
the parser that reads its answer are edited as a pair; the child cap the decompose prompt states is read straight off
`workflow/stages/decomposition/validation.py` so the two cannot disagree. It reaches `comments.py` for the thread text
and the tracked-repos block and `messages.py` for the blockquote, and the stage leaves that build a prompt or append a
note import the owner. So a
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
`_on_question` and `_on_dirty_worktree` on `workflow/stages/implementing/parks.py` compose the same comment,
`awaiting_human` flag, `last_action_comment_id` ratchet, and `park_awaiting_human` event themselves, each
beside stage-specific state the helper does not write — the classified park reason and the silent-park counter
on one, the dirty-file count carried on the other's event — so a patch aimed at either targets the stage owner.

`workflow/engine/pickup.py` is bound the same way. It owns the first tick an unlabeled issue gets, which is two
decisions and one publish order. `ALLOWED_ISSUE_AUTHORS` decides whether the orchestrator answers at all — the
allowlist is checked here and nowhere else, so a maintainer who labels an outsider's issue by hand still drives it
through every later stage — and `DECOMPOSE` decides whether `_start_decomposing` or the legacy
`_start_implementing` answers. Both starts then write the same four things in the same order, because everything
downstream reads them back: the greeting first, so its id can anchor `pickup_comment_id` for the validating
handoff's seed-watermark; the `user_content_hash` baseline next, computed with that id already filtered out; then
the workflow label, and only then the pinned state, so a crash between the two leaves an issue the next tick still
routes to the stage it was committed to rather than an unlabeled one it would greet a second time. It reaches
`comments.py` for the greeting and the id ledger, `drift.py` for the baseline, and `usage.py` for the `created_at`
stamp, so a patch that has to intercept the allowlist, either start, or the pickup-comment record targets
`orchestrator.workflow.engine.pickup`; `workflow` still resolves all five names to the owner's exact object. The
stage handler it dispatches in the same tick is reached through a call-time import of
`workflow/stages/decomposition/run.py` or `workflow/stages/implementing/handler.py` — the stage tree imports this
subpackage, so binding either at module scope would point that edge back at itself — which also makes the stage
module, not `workflow`, the target for a patch that has to intercept the dispatch. A migrated stage is named by
the owner its handler lives on rather than by the forwarder it left behind, so that patch target is the same one
`_STAGE_HANDLER_TARGETS` names.

`workflow/engine/terminals.py` is bound the same way. It owns how an issue stops being worked. Three conditions
end one — the linked PR merged (`done`), the linked PR closed unmerged (`rejected`), and a human closed the issue
while its PR is still open (`rejected` too) — and what they share is the tail rather than the condition: a terminal
stamp (`merged_at` / `closed_without_merge_at`), a terminal label, the cumulative usage receipt, and one
`write_pinned_state`, in that order, so the receipt's comment id rides the state the stamp is written with. Branch
cleanup sits outside that tail on purpose: it runs on the two arcs where the PR is gone and the branch is dead
weight, and is withheld on the open-PR arc — along with its `pr_closed_without_merge` emit — so an operator can
still reopen or salvage what the closed issue left behind. The two entry points differ only in who fetched the PR:
`_drain_review_pr_terminals` takes one the caller already holds (`in_review`, `fixing`, `resolving_conflict`, with
`pr=None` a deliberate no-op so fixing's own fetch failure passes through), while `_finalize_if_pr_merged` and
`_finalize_if_issue_closed` fetch their own at handler entry for `implementing`, `documenting`, `validating`, and
the umbrella / blocked child aggregation — which is why each owns its fetch-failure answer, the merged check
leaving the issue alone and the closed-issue check deferring the tick so a transient failure cannot label a
merged-PR issue `rejected`. Its own helpers call each other in-module and reach `usage.py` for the stamp and the
receipt and `git.worktrees` for the branch name and the cleanup, and every stage leaf that drains or finalizes a
terminal imports the owner, so a patch that has to intercept an arc, a drain, or an entry-time finalize targets
`orchestrator.workflow.engine.terminals`; `workflow` still resolves the whole group to the owner's exact object.

`workflow/engine/dispatch.py` is bound the same way. It owns everything between "the repo has open issues" and "one
`_handle_<stage>` is running", and the pieces sit together because each is only safe given the one before it. The
`backlog` / `paused` filter runs twice on purpose — once in `_classify_pollable_issue` so a parked issue never
reaches the partition, and once in `_process_issue` so a directly dispatched one is still refused — and the early
drop is not an optimization: a parked issue carries no workflow label, so leaving it in would fold it into the
family bucket, flip that bucket cap-counted, and reserve the only per-repo slot under the default
`parallel_limit=1`. The partition itself is the concurrency contract: the cross-issue writers (`decomposing` /
`blocked` / `umbrella` and the unlabeled-pickup `None`) collect into one bucket that drains sequentially, everything
else fans out, and a label read that raises is answered `(False, None)` so the unreadable issue lands in the
serialized bucket where `_process_issue`'s own per-issue exception isolation can pick up a sustained failure. Cap
exemption is what keeps that serialization from deadlocking — a bucket whose every label is a no-agent handler
(`_CAP_EXEMPT_FAMILY_LABELS`) and a closed fan-out issue whose handler is a terminal finalize both skip the per-repo
and global caps. Only issue numbers cross a thread boundary; `_refetch_and_process` mints a per-worker client and
refetches against it, because PyGithub's `Issue` and the `Requester` chain behind it are not documented thread-safe.
Its own helpers call each other in-module, and each handler is reached through a call-time import of the module
`_STAGE_HANDLER_TARGETS` pairs with its label — eleven of the twelve entries name conflicts, decomposition,
documenting, fixing, implementing, question, validating, and in_review owners under `workflow/stages/`, and the
twelfth names the `pickup` sibling an unlabeled issue starts on; no entry names a forwarder.
That table stays owner-private,
because the facade's inventory is the historical surface rather than a mirror of the owner: what `workflow` publishes
is `_ISSUE_HANDLER_NAMES`, the label → handler-name half of it, derived from the table so the two cannot disagree
about which labels route. The import is deferred because the stage tree imports this subpackage, so binding one at
module scope would point that edge back at itself; the lookup stays an attribute read on whichever module the table
names, and every stage is named by the owner its handler lives on rather than by the forwarder it left behind.
That makes the owning module, not `workflow`, the target for a patch that has to intercept a
dispatched handler, and this owner the target for one aimed at the partition, the cap-exemption probe, the timed
dispatch, or a scheduler submit. `workflow` still resolves all nineteen names to the owner's exact object for callers
outside the package; `workflow/engine/tick.py` binds the owner directly.

`workflow/engine/tick.py` is bound the same way, and closes the subpackage. It owns one repo's polling pass, which is
four things in one order. The base refresh runs first because everything after it reads what that fetch left behind —
a handler would otherwise rebase onto the base SHA its worktree was created at, and the skill catalog would ls-tree a
stale `<remote_name>/<base_branch>` — and it is the only pass whose failure the tick catches, because a fetch that
fails must not cost the tick its issues. The community-contribution sweep sits here rather than in the stage tree
because it is the one pass with no per-issue home: the outsider PRs it labels carry no pinned state for a handler to
consult, so nothing dispatches them. It and the skill-catalog emission both run before the scheduler / in-tick split
so they fire exactly once per tick on either path, and both are internally fail-open. Past that split the tick either
hands every issue to `dispatch._dispatch_via_scheduler` and returns without waiting, or runs them itself under
`parallel_limit`: `limit == 1` streams `list_pollable_issues()` directly, because materializing it first would lose
every already-yielded issue when a pagination error raises mid-sweep, while `limit > 1` must materialize (the executor
needs the submission count up front to bound `max_workers`) and lets an enumeration failure cost the tick the next one
retries. Either way each issue is wrapped in its own try/except, and the family bucket is submitted as exactly one
task so it holds a single worker slot and leaves the other `limit - 1` free for fanout. It reaches `dispatch.py` for
the partition, the per-worker refetch, and both dispatch routes, so a patch aimed at a sweep helper or an execution
mode targets `orchestrator.workflow.engine.tick`; `workflow` still resolves all eleven names to the owner's exact
object, `tick` among them, which keeps `main._run_tick`'s `workflow.tick(...)` call unchanged. The one collaborator
it deliberately reaches back through the facade for is `_refresh_base_and_worktrees`: that is the seam the tick tests
replace to drive a pass without a git remote or a clone, so `patch.object(workflow, ...)` stays the way to intercept
it. The skill-catalog emission is named on its owner instead — the tick imports `orchestrator/skills/catalog.py`, so
`patch.object(catalog, "_emit_repo_skill_catalog", ...)` is what intercepts that pass and nothing on the tick path
loads the `skill_catalog.py` compatibility site. `workflow._emit_repo_skill_catalog` still resolves to the same
owner object for historical callers.

Stage-private helpers stay private to the stage that owns them (`_bump_in_review_watermarks`,
`_seed_legacy_in_review_watermarks`, `_emit_conflict_round_incremented`). A helper more than one stage reaches for is
re-exported from the facade as well, and that export is the edge a historical caller resolves through; between
stage owners the borrower names the lender's owner instead, so fixing's quiet window imports `_comment_created_at`
from `in_review/watermarks.py` even though `workflow` answers with the same object.

`orchestrator/skills/` holds the two ways this orchestrator answers "which skills are in play". `catalog.py`
enumerates what a target repo *offers* on its base ref — the `git ls-tree` read whose deduped names and preserved
source paths become one `repo_skill_catalog` analytics record per tick per spec — and `discovery.py` enumerates what a
single local codex run was *loaded with*, scanning the run's worktree roots plus the global `$CODEX_HOME/skills` (its
`.system` builtins included) because codex's stream carries no offered-skills or offered-tools frame to read one off.
The skill roots and the `SKILL.md` marker that both scans are defined by live on `discovery`, the owner that reaches
nothing outside the standard library, and `catalog` reads them back so a git pathspec and a filesystem scan cannot
disagree about what a skill definition is. The initializer binds nothing and both live callers name an owner: the tick
calls `catalog._emit_repo_skill_catalog`, and the analytics codex backfill calls `discovery.discover_local_skills` /
`discover_codex_tools` — so a patch that has to intercept a run's offered skills or tools targets
`orchestrator.skills.discovery` and not `skill_catalog`. That leaves root-level `skill_catalog.py` a temporary
compatibility site: it re-exports those four names as the owners' own objects, nothing on the tick or analytics path
imports it any more, and a check under `tests/skills/` holds the direction the package runs in — neither owner may
reach the workflow engine, a stage, or an application entrypoint, because a catalog is observation the tick drives
rather than state a handler consults.

`orchestrator/observability/` is the destination for the four surfaces that watch a run without steering it: the
analytics sink and everything downstream of it (`analytics/` over `recording/`, `query/`, `sync/`, and `trajectories/`),
the parser that meters one finished agent run (`usage/`), the Streamlit page over the operator's Postgres target
(`dashboard/`), and the file-backed trajectory viewer beside it (`trajectory_viewer/`). The parser is the first to
arrive: its owners live under `usage/`, whose initializer publishes the parser surface, while the callers that meter a
run — `agents/models.py`, `workflow/engine/usage.py`, and the analytics recording and trajectory writers — name the
owner they need. Root-level `usage.py` stays behind as a temporary compatibility site re-exporting those owners' own
objects, and nothing on the tick path imports it any more — which is what makes it deletable rather than load-bearing.

`analytics/config.py` is the first owner under the analytics destination: the six environment knobs the two JSONL
sinks and the Postgres surfaces are configured by, the `off` / `disabled` / `none` disable vocabulary three of them
share, the whole set parsed under the names the flat package binds them to, the `Settings` view an adapter reads one
back through, and the fallback a read's `db_url=None` resolves through. Every adapter obtains configuration there —
the flat package's bootstrap, both sinks' appends and the prune beside them, the two skill readers that take their
holder off an exit context, the two read-path owners under `analytics/query/`, and the sync request — so a knob's
name appears in one place, and the flat package keeps no settings leaf of its own.

What the flat package still owns is *which* values are in force: it binds the parsed set at import and is where a
caller patches one, so the view reads them back off it rather than re-parsing. Which *instance* it reads is the
adapter's own answer, and the two are not interchangeable. A recorder passes `settings_on` the package it captured at
its own import, because a package re-imported against a patched environment is not installed under the package name
afterwards — reaching for the name would hand its callers the process-wide values. The read path and the sync have
nothing captured and use `live_settings`, which resolves the name behind a function-local import: binding that import
at module scope would cycle and make the compatibility package load-bearing rather than retirable. The view reads each
attribute on demand, so a knob patched between two reads reaches the second and a holder carrying only the knobs its
caller touches stays usable.

`analytics/recording/` is the append side of that sink, and the second publishing initializer in the tree: its
`__all__` is the six recorders a producer calls — the `build_record` envelope, the `append_record` beneath it, and one
each for a stage entered, a stage evaluated, a repo's skill catalog scanned, and a tracked agent run finished — bound
once, at import, to the `events` owner's own objects. The owners under it divide by what a record costs to produce:
`events` holds the envelope and the recorders, `io` the locked JSONL line both sinks write through, `models` the typed
requests and the keyword signatures a call is bound through, and the four steps a finished run is summarized by are
`usage` (tokens and cost), `skills` (the opt-in evidence), `catalog` (the out-of-band Codex capabilities either falls
back to), and `agent_exit` (the order they compose and write in). Every producer names the package — `github/client.py`
for the paired audit / analytics stage-enter hook, `workflow/engine/dispatch.py` for the timed handler,
`workflow/engine/usage.py` for the tracked run, and `skills/catalog.py` for the per-tick catalog — and none of them
imports the flat analytics package any more.

They still *reach* it, at call time. It is the settings holder: `events.settings_holder` answers with the package
instance the module was imported alongside, read out of `sys.modules` rather than imported, because binding that import
would cycle. The analytics bootstrap replaces `events` with the rest of its implementation set, which is what gives
each package instance its own capture — a reference held across a reload keeps recording into the instance its own
callers patched — and dispatching `append_record` through that holder is what keeps
`patch.object(analytics, "append_record", ...)` intercepting an internal append. A producer that imported the owner
with no package behind it captures nothing and resolves the name inside the call instead. `agent_exit` carries that
same instance on the exit context, so the trajectory owner it hands one run's second record to answers for the
instance the caller entered on without reaching the package through it.

`recording/__init__.py` is *re-executed in place* rather than replaced, and that asymmetry is the compatibility
contract with the producers. A producer names the package at its own import and keeps the object it got back, which for
an owner-first import order is an object that predates the flat package entirely; swapping it would strand that
producer on recorders answering for an instance nobody holds and put a patch aimed at the canonical module outside its
call path. Re-executing the initializer over the fresh `events` instead leaves one package object whose published names
and the facade's bindings are the same objects in every import order.

Both sinks' locks answer the same question one layer down, and that is why they live on `io.py` rather than beside the
appends that take them. An append and the retention prune that rewrites the file under it are safe only while both hold
one lock object, and a caller is free to take `append_record` — or `append_trajectory_record` — off its owner rather
than call through the package: a reference the rebuild never rebinds, and one whose *first* call is what initializes
the facade and triggers that rebuild. Minting each lock on the owner that is loaded once per process is what keeps
every such reference, the facade's `_FILE_LOCK` / `_TRAJECTORY_FILE_LOCK`, and `retention.py`'s serializing against each
other instead of drifting apart at the first reload. The two locks stay separate objects, so neither sink's writers
ever block on the other's file.

`analytics/retention.py` is the other side of that pair: the by-age prune both sinks are bounded by. It publishes
three entry points, one caller each — the polling tick's fail-open wrapper, and one prune per sink — over
`retention_scan.py` (the timestamp a record is judged by, and the split of a file into kept lines and a removed count)
and `retention_rewrite.py` (the same-directory temp file, the `os.replace` that swaps it in, and the lock held across
the read and that swap). Each sink brings its own path, its own retention knob, and its own lock, so an operator can
keep the two files for different windows and neither rewrite ever blocks on the other's append; the scan and the
rewrite are shared, so the two cannot disagree about what an expired or malformed record costs. Like
`trajectories/api`, this owner sits *above* the recorders and is rebuilt for each package instance, because *which*
files a bare prune rewrites is answered by the settings holder the `events` owner beside it captured. Every filesystem
touch downgrades `OSError` to a logged no-op, and the wrapper swallows anything else, so a misconfigured sink costs a
warning rather than a tick.

`main._run_tick` names that owner directly, and names it inside the call for the same reason the read path resolves
`live_settings` there: a module bound at import could be one generation behind the settings the prune has to read. The
wrapper it calls delegates back through the settings holder, so `patch.object(analytics, "prune_old_records", ...)`
still intercepts.

`analytics/trajectories/` is the opt-in per-run reasoning sink, and its owners divide by what one record passes
through on the way to disk: `models` holds the head/tail and whole-record caps, the view they are read back through,
and the headline and running budget a record is charged as; `sanitize` the leaf-by-leaf redaction and the head/tail
cut; `serialize` the record's shape and the order the turn and step arrays are drawn from the budget in; `persistence`
the opt-in gate, the parse, the Codex backfill, and the fail-open guard the whole write rides. The direction is the
point: `recording/agent_exit` names `persistence`, never the reverse, and everything from `persistence` down reads its
settings holder off the exit context rather than importing a package to ask. `api` is the exception and sits *above*
the recorders — a bare `append_trajectory_record`, reached by an operator or the compatibility facade rather than by a
tracked run, has no context to read, so it resolves the path through the same captured holder the recorders use and is
rebuilt alongside them for each package instance. Its lock is the one exception to that rebuild — minted on `io.py`
with the analytics sink's, for the reason above — and `retention.py`'s trajectory prune takes that same object, so the
trajectory file serializes its own append-versus-prune race without ever blocking against the analytics one.

`analytics/query/` holds what a read is asked for, what it dials with, and what it answers with, split by what each
owner decides. On the input side, `requests` owns the keyword vocabulary every public read is called by — one
signature per family, composed from shared parameter groups so an omitted `limit`, `sort_by`, or hour offset is
defaulted in one place — and the bind of such a call into the `request_models` parts a family reads back: the filters,
the connection, and the options. `filters` owns the selection those filters project onto and the builder a clause
accumulates in, appending each condition together with its operand so the `%s` order and the binding order cannot
drift apart. `predicates` owns the one `WHERE` builder behind all three scan targets, so the events table, the
agent-run view (which drops the `events` selection its columns cannot carry), and the daily rollup (which binds
`.date()` bounds against `day`) cannot disagree about what a filter means — including the three-case reading of a
multiselect, where an empty selection is a tautologically-false predicate rather than no filter. `conditions` owns the
splice of a table's own required condition onto either end of that clause, which is what fixes whether its operand
binds before or after the generated ones, plus `agent_event_excluded` — the probe a view-backed read short-circuits on
when the event selection excludes `agent_exit`, because the view has no `event` column to push the filter into.

On the result side there is one owner per family, and each is a plain frozen dataclass module: a page or a test that
only consumes the rows imports one without reaching a connection factory, the configuration behind an omitted
`db_url=`, or the driver those two stand in front of. `activity_models` holds the cells a volume is bucketed into by
when it happened, kept raw so the chart above owns the Monday-first re-ordering rather than the reader. Its
counterpart `overview_models` holds what a page frames one window with before any breakdown of it — the values its
filters offer, how far the data behind them reaches, what it totals, and how those totals move day by day. The first
three construct bare, because "no database configured" and "no rows in the window" are answers a page renders rather
than errors it raises; the series cell is one row of a `GROUP BY`, so it requires the `(day, event, count)` key it was
grouped on and defaults only the aggregates hung off that key. `cost_models` holds the axes that spend is broken down
along (review round, backend, repo, and the pricing confidence the parser could attach), so the cache / no-cache
proration and the NULL bucketing under `"unknown"` are declared once per axis instead of by each chart that plots one.
`run_models` holds the run, issue, and traced-event rows, whose field order is half of a contract the SELECT list
filling them is the other half of, plus the accessor behind the trace row's `result` alias: the column is stored as
`event_result` because a bare `result` is a name the style guide rejects, and the alias is installed as a property so
the two spellings can never hold different values. `skill_models` holds the cells a skill's reach is reported in, each
pairing a numerator with the cohort it is read against and deriving that share itself, guarded against a zero
denominator so a cell that exists only for its window diagnostics still renders.

All four families of reads themselves are here too. `raw_reads` owns the six that stay on `analytics_events` rather
than the day-bucketed rollup above it. Each binds its keyword call against the signature its family is declared with,
decides the answers that need no database — an unconfigured one, a cap of zero, a cleared multiselect — and hands the
filtered window to the projection owner beside it. Those owners split by what each one's SQL decides. `filter_options`
collapses five `SELECT DISTINCT` round-trips into one tagged union and buckets the rows back into the five dropdowns,
sorting in Python so the ordering stays the reader's choice and a tag it does not know is dropped rather than routed
to a bucket the result model has no field for. `event_breakdowns` counts per event off the events table itself, so the
counts stay exact against the window's own bounds rather than the day a rollup would round them to. `agent_exits` pins
`event = 'agent_exit'` ahead of the generated predicate — which is what fixes its operand binding first and the cap
last — and drops the `events` selection that pin makes redundant. `issue_summaries` aggregates one row per
`(repo, issue)` pair and owns the two orderings that table is read in, ranking by cost in SQL because ordering after
the `LIMIT` would silently drop the older expensive issues that mode exists to surface. `issue_events` traces one
issue oldest first, breaking ties on `id` so two events recorded in the same instant read back in the order they
happened. Beneath all five, `query_rows` names the columns of the three SELECT lists wide enough that an unpack read
by index stopped being checkable by eye, so a projection reads those by field instead while the narrower lists stay
positional. Two of the three pad a short row to full width, which is what lets a fixture written against an older,
narrower list still read back with the columns it never carried unset; the recent-exit row does not, so a row short of
its fifteen columns raises rather than filling a run in half. `raw_values` narrows one raw column to what its result
field declares — a NULL stays `None` rather than becoming a zero a page would render as a measurement.

`rollup_reads` owns the other seven, the ones a whole-day window lets scan the rollup instead: what one window
totalled, what the window before it did, its daily series, and its stage, backend, repository, and throughput
breakdowns. It answers the same no-database cases the raw hub does, plus the one short circuit that is about rows
rather than configuration — a backend comparison is about finished runs, so an event selection without `agent_exit`
returns nothing without dialing. One projection owner sits under each read. `summary_queries` applies the window once
in a CTE and reads it back through three `UNION ALL` branches tagged by kind, so a page pays one round-trip for
totals and both breakdowns instead of three scans of the same days, and counts distinct issues over `(repo, issue)`
pairs because issue numbers repeat across repositories. `summary_results` reads those branches back, ranking each
breakdown in Python — count descending, label breaking ties, so a redraw cannot reshuffle a table — and mapping the
totals row through a declared cast list rather than unpacking it, which is what lets a row that predates a column
leave its field at the model default. `kpi_totals` is the trimmed variant a delta pill is measured against, carrying
none of the groupings or distinct counts so the comparison window costs one aggregate pass. `time_series` hangs cost
and the four token bands off the same `(day, event)` cell as the count, so the volume, spend, and token charts pivot
one result. `stage_breakdowns` and `backend_efficiency` both recover the row-weighted mean duration as
`SUM(sum) / SUM(count)` — averaging per-day averages would weight a quiet day like a busy one — and a window with no
recorded duration stays NULL rather than reading as instant; the backend one pins `event = 'agent_exit'` into the
clause and drops the caller's event selection that pin contradicts, bucketing an unrecorded backend under
`"unknown"`. `repo_breakdowns` can count distinct issues bare precisely because it groups by repository already.
`throughput_days` pins `stage_enter` and intersects the caller's stage selection with the two terminals, returning
nothing rather than an empty scan when either selection leaves it nothing to count.

`breakdown_reads` owns the remaining four, the ones whose grouping key that rollup threw away. A review round, a cost
source, and one run's own token split are per-run facts a day bucket aggregated over, so those three scan
`analytics_agent_runs` and carry the same agent-exit short circuit `get_backend_efficiency` does — the view has no
`event` column to push a selection into. An hour of day is what the bucket rounded off instead, so the heatmap stays
on the events table, where that selection becomes an ordinary predicate and no short circuit applies. One projection
owner sits under each: `review_rounds` labels the bucket rather than numbering it, because the axis has to hold a
developer run still in `implementing` (round zero, not yet reviewed), a run with no round recorded at all
(`unknown`, kept separate from it), and the tail past the sixth (one `6+` bucket, so a rare twelve-round issue cannot
stretch the axis), and reports each bucket's cost per role with each role split into cache and no-cache bands.
`cost_coverage` groups by the usage parser's own verdict and never folds `unknown-price` — a model the price tables
carry no entry for — into the `unknown` a run with no recorded source falls to, since only the first is a table to
extend. `backend_tokens` aggregates the whole window off the view rather than the capped newest-runs read, so a
backend busy early in a long window does not flatten toward zero. `hourly_heatmaps` normalizes `ts` to UTC before
adding the caller's offset — a session whose own timezone is not UTC would otherwise shift every bucket a second
time — and binds that offset as a parameter rather than splicing it.

`skill_reads` owns the last three, the ones whose fact is not a column at all: a skill name, the set a repository
offered, and the count one run loaded are recorded inside an `agent_exit` row's `extras` JSONB, which no table above
the events one carries. All three therefore scan `analytics_events` and pin `AGENT_EXIT_CONDITION` themselves, which
is why a selection excluding that event returns without dialing rather than running a query whose two conditions
contradict. `skill_trigger_rates` measures a cohort against every finished run rather than the runs that loaded
something, so a cohort that never triggers is a real zero rather than an absent row, and separates the runs that
loaded at least one skill (a key probe, so an empty load list still reports) from the total loads summed across them.
`skill_matrices` runs two scans because the answer needs a universe as well as observations: the catalog scan takes
only the repository filter — a `repo_skill_catalog` record has no issue and no stage, so pushing the window, issue, or
stage selection onto it would drop every row and silently collapse the padding — and its skills pad every cohort that
ran, so an offered-but-unused skill reads as an explicit zero while a triggered skill outside the catalog keeps its
observed cell. `skill_adoption` measures sessions rather than runs, so a session that repeated one skill counts once,
and carries the cohort's run count, its load rows, and its incidental references beside that ratio without letting any
of them move it. Under it, `skill_sessions` decides which rows are one logical session — a resume id, then a session
id, then the primary key, so an ID-less row stays its own session rather than merging into one anonymous bucket — and
scopes the evidence scan: the window scan picks which sessions count, and the history scan then drops the start bound
and the stage filter while keeping the end bound, so a load from an earlier stage or before the window still counts
while one after it does not. Beneath both aggregates, `skill_values` coerces a JSONB name array from an adapted list,
raw JSON text, or an absent key without ever raising on a malformed blob, normalizes the `(repo, role, backend)`
cohort with an unrecorded label bucketed under `"unknown"`, and owns the matrix ranking.

Beneath the rollup and breakdown families, `cache_shares` owns the token share a row's cost is split into cache and
no-cache bands by, spelled once per set of column names the rollup and the agent-run view use for it — the Codex
cached-tokens counter is already inside the input total, so it weighs in the numerator only, and a row with no tokens
attributes its whole cost to no-cache instead of dividing by zero. `row_cells` owns the three readings a cell from
any family passes through: a positional read with a default for a row narrower than the SELECT list, a nullable cost
column read as a float because a page sums it, and a `day` some drivers widen to a timestamp narrowed back to the
date it was grouped by. The NULL-preserving float coercion those projections share is `raw_values`', so every family
narrows a nullable duration the same way.

On the connection side, `connections` decides what a read dials with: the psycopg import deferred to call time, so a
caller that only consumes the read dataclasses never pays for the driver and a test injects a `connect(db_url)`
factory instead of installing one; the two factories that use it, differing only in whether the socket outlives the
query; and `AnalyticsReadError`, the single exception every driver failure is wrapped in with the original kept as
`__cause__`. `connection_cache` decides how long a socket lives: one thread-local entry keyed on the resolved URL, so
a `with` block asking for a different `db_url=` closes the stale one, and a broken-socket error escaping the block
evicts it before re-raising. Reuse is the point, so a normal exit leaves the connection open and
`close_thread_local_connection` is what drains it. `execution` decides whose connection one SELECT runs on: a
caller-owned `conn=` is used as-is and never closed, because its lifetime belongs to the `analytics_connection` scope
that opened it, while a query without one opens and closes its own descriptor in a `finally`. Both connection paths
resolve an omitted `db_url=` through `config.resolve_db_url`, and every caller that has an owner names it: the
dashboard's three skill read wrappers reach `skill_reads` rather than the facade in front of it. Nothing under
`orchestrator/analytics/` implements a read any more, so what is left there forwards — the `analytics.read` facade
answers the historical connection names, including the underscored ones, with their own objects, and the result classes
too, so a row unpacked off the facade is the class the read family constructed, and all four families of reads
themselves. On the input side `predicates.py`, the three `_predicate_*` leaves, and `read_request*.py` do the same; on
the result side the five `read_models_*` family modules do; and on the read side `read_raw.py` with its seven `_read_*`
leaves, `read_rollup.py` with its seven, and `read_dashboard.py` with its nine, under the private projection,
fragment, condition, and coercion names each published while it owned them. Each of those flat modules names an owner
itself and defines nothing, and the hub above each group sits beside its leaves rather than on top of them:
`predicates.py`, `read_models.py`, `read_raw.py`, and `read_rollup.py` republish everything the leaves beneath them do,
`read_dashboard.py` the subset it published while it owned the two families, and the query rows are the one group no
hub ever published — they were reached on `_read_query_rows.py` then and are still reached there. Whichever module a
historical caller imported hands back the owner's object rather than a copy of it.

Every other responsibility of those three surfaces is still where it was: `orchestrator/analytics/`, `dashboard*.py`,
`trajectory_reader.py`, and `trajectory_dashboard.py` stay the import site every historical caller
names until the one it needs has an owner here.

Four rules hold for whatever lands there, each with a check under `tests/observability/` that discovers its own subjects
off disk so a new owner is covered the day it appears. An initializer binds nothing unless the surface it fronts is what
a caller asks for by name, so importing one owner does not charge the importer for its siblings: the recording path runs
inside every tracked agent run, and a binding would put the query owners and the database driver behind that import.
`usage/__init__.py` and `analytics/recording/__init__.py` are the two exceptions and pay that cost deliberately — the
parsers and the recorders are each reached through their package, so one re-exports the nine parsers and the five result
types they return under an `__all__` and the other the six recorders — and the check that excuses them is keyed on that
`__all__`, so a third publishing initializer is a deliberate edit rather than a silent one. What a publisher may charge
for beyond its own owners is declared per package: recording is configured by `analytics/config.py`, meters a run
through `usage/`, and hands that run's second record to `analytics/trajectories/`, so naming it buys those three chains
and nothing else.
Nothing under the tree carries an export manifest, a resolver hook, or a `.pyi` surface — a re-export is the owner's own
object, bound once at import rather than resolved per lookup, so the module defining a name stays where a reader finds
it and where a patch has to land, rather than a facade answering for it — the compatibility layer this destination
exists to retire. Nothing observed is on the workflow's decision path, so no module may import the workflow engine, a
stage, or an application entrypoint — the CLI and the runtime loop on one side, the two `streamlit run` targets
(`dashboard.py`, `trajectory_dashboard.py`) and the leaves they front on the other; the dependency runs one way, and an
entrypoint composes these owners rather than the reverse. And Streamlit and Plotly stay function-local: they live in the
optional `dashboard` dependency group, so every module has to import cleanly with both blocked outright *and* with no
attempt on either recorded — a module-scope import that swallows its own `ImportError` is still a load in the install
that has the package — which is what keeps the data an owner shapes testable in an install that has neither.

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

One repo's pass is owned by `workflow/engine/tick.py` — the base refresh, the community-contribution PR sweep, the
skill-catalog emission, and then either the scheduler handoff or the in-tick sequential / bounded-parallel loop, in
that order (see [the owner's paragraph](#top-level-layout) above for why each step depends on the one before it).

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

Each workflow label dispatches to a `_handle_<label>` function. Every handler lives under
`orchestrator/workflow/stages/` (see the module map above), and the dispatcher reaches one by importing the module its
label is paired with in `_STAGE_HANDLER_TARGETS` and reading the handler off it, so a patch that has to intercept the
dispatch targets that module rather than `workflow`. The `workflow` package initializer still re-exports every handler
under its original name, and that is the edge a stage-to-stage call resolves through when its caller reads the name off
the facade — `_handle_implementing` from the decomposition recovery and blocked paths — so a patch aimed at one of
those keeps targeting the facade.

`orchestrator/workflow/stages/` is the destination the per-label facades moved to, one stage at a time;
`decomposition`, `implementing`, `documenting`, `validating`, `in_review`, `fixing`, `conflicts`, and `question` have
all arrived. Each became a subpackage of
responsibility-named owners there, and the `orchestrator/stages/<stage>.py` it vacated stays behind as a temporary
forwarder that reads every name back off those owners rather than rebuilding one, so both import sites hand back the
same object. Identity is all a forwarder carries: it caches each name it resolved, so a `patch.object` intercepts the
lookup site it lands on rather than both, and the owner is the site orchestrator code reads. Dispatch makes that
explicit: `_STAGE_HANDLER_TARGETS` names the owner a handler lives on, and so does the same-tick start in
`workflow/engine/pickup.py`, so a patch meant to intercept a dispatched handler has to land on the owner. A forwarder
is dropped once the callers it serves name the owner. Like `workflow/engine/`, the new package and each stage
subpackage inside it bind nothing in their initializers -- the dispatcher resolves one handler per issue, so an eager
binding there would charge that import for every other stage's leaves and for the worktree and GitHub subsystems they
reach.

The decomposition owners bind their collaborators directly. `manifest` calls `validation` for the split rules,
`run` calls `session`, `recovery`, and `outcomes` for the order a tick asks them in, `outcomes` calls `manifest` and
`split`, `blocked` and `umbrella` both call `parents` for the child scan and `activation` for the dep-graph walk, and
every owner that writes to GitHub reaches `workflow/engine/` for the comment poster, the run guards, the prompts, and
the usage counters. `state`, `models`, `manifest`, and `validation` deliberately reach nothing — the keys, the
carriers, and the whole parse are decidable without a client, which is why the manifest rules can be exercised without
one. So a patch that has to intercept the manifest parse, a child scan, or the split writer targets the owner
module. The seams that stay on the facade are the ones a stage does not own: `_handle_implementing`, the decompose
worktree helpers, `_has_new_commits` / `_worktree_dirty_files`, and `_check_and_increment_retry_budget` are read as
`_wf` attributes at call time, and the whole historical inventory still resolves on `orchestrator.stages.decomposition`
with the owner's exact identity. `_MAX_CHILDREN` runs the other way: the cap lives with the validator that rejects past
it and `workflow/engine/prompts.py` reads it back, so the bound the decomposer is told and the bound it is judged
against cannot drift apart.

The implementing owners bind their collaborators the same way, and they divide along the decisions one tick makes
rather than the code it runs. `handler` holds the order those decisions are asked in and calls `question_relabel` and
`continue_command` for the two preflight signals, `drift` for a body edit, `spawn` for the run itself, and
`disposition` for what the run left behind. `spawn` asks `session` for the retry budget and `drift_preflight` for the
awaiting-human route; `resume` and `execution` split one resume between the call shape callers wrote against and the
attempt-and-retry behind it, over `session` for retirement and `worktree` for the checkout; `disposition` routes a
committed tree to `publication` and everything else to `parks`. `state`, `models`, and `session_read` reach no engine
owner, no GitHub client, and no worktree helper — `session_read` reads the configured agent spec and nothing else —
which is why the pinned-state keys, the carriers, and the CLI-marker classifiers can be exercised without a client. So
a patch that has to intercept a park, a push, a resume, or a session read targets the owner module. The seams that stay
on the facade are the ones the stage does not own -- the worktree, git, and push helpers are read as `_wf` attributes
at call time -- and the whole historical inventory still resolves on `orchestrator.stages.implementing` with the
owner's exact identity.

The documenting owners divide by what one final-docs tick has to settle before it may spawn. `handler` asks
`preconditions` first for the checks that end the tick outright — the PR-merged and issue-closed terminals, the
missing-`pr_number` guard, and the bare `/orchestrator continue` refusal — then `drift` for the one that unwinds
instead, then `preconditions` again for the parked-no-input fast path, and only then `run` for the pass and `outcomes`
for what it left behind. `drift` hands the git half to `drift_reset`, which fails closed on every fetch, probe, reset,
and clean because a docs commit left on disk against the old body is what the next tick's recovered-commit shortcut
would push unreviewed. `outcomes` routes a commit or a confirmed `DOCS: NO_CHANGE` to `publication` and everything else
to `parks`, and `publication` calls `handoff` for the `pr_last_comment_id` ratchet that has to precede the `in_review`
relabel. `state` and `models` reach nothing, so the wire keys and the carriers are decidable without a client. This
stage owns no dev session of its own: the resume, the session read, and the question / dirty-tree parks are imported
from `workflow/stages/implementing/` directly, and the `pr_last_comment_id` seed walk from
`workflow/stages/validating/watermarks.py`, so a patch that has to intercept one lands on that owner. The seams
that stay on the facade are the ones neither stage owns — the worktree, fetch, git, and push helpers and base-sync's
`_AUTO_REBASE_PARK_REASONS` are read as `_wf` attributes at call time. That
last one is why both precondition reads consult it before they act: a park the pre-tick refresh owns is one whose
retry nudge belongs to `_sync_pr_worktree_to_base`, so the docs stage stays silent rather than answering a comment
addressed to the rebase loop. The whole historical inventory still resolves on `orchestrator.stages.documenting` with
the owner's exact identity.

The validating owners divide by what one review tick is answering, since the reviewer is only part of what the stage
runs. `handler` opens with the terminals and then holds the order — drift, the awaiting-human park, the reviewer round
— and hands the spawn itself to `reviewer`, which asks `requested_changes` for the round-cap park, meters the run
through the engine's tracked spawn, and fans the verdict out to `approval`, `requested_changes`, or the no-VERDICT
park. `approval` calls `git.verification.runner._run_verify_commands` directly for the gate, `verify` for the park a
non-ok result earns, and `watermarks` for the seed walk that keeps the docs hop and in_review from replaying the
orchestrator's own comments. Between rounds the stage is a dev-fix driver: `awaiting` / `awaiting_resume` (a park a
human replied to), `drift` / `drift_outcomes` (a body edit mid-review), and `recovery` (the parks that clear without
a human) all dispose through `dev_fix`, so the stranded-commit gate, the push, and the `review_round` bump cannot
drift apart between routes. `state`, `models`, and `watermarks` reach no worktree helper, so the wire keys, the
carriers, and the whole seed walk are decidable without one. So a patch that has to intercept a park, a push, the
verdict fan-out, or the watermark seed targets the owner module. This stage owns no dev machinery either: like
documenting it imports the resume, the session read, and the question / dirty-tree parks from
`workflow/stages/implementing/` directly, and the squash from `git/publication/squash.py`, so a patch on one of those
lands on the owner rather than on the facade — which would not intercept the call. The seams that stay on the facade
are the ones the stage does not own — the worktree, fetch, git, and push helpers plus base-sync's
`_AUTO_REBASE_PARK_REASONS` are read as `_wf` attributes at call time — and the whole historical inventory still
resolves on `orchestrator.stages.validating` with the owner's exact identity. Six of its names resolve on `workflow`
as well — `_post_user_content_change_result`, `_handle_dev_fix_result`, `_stranded_fix_unpushed`,
`_try_recover_validating_transient_park`, `_VALIDATING_TRANSIENT_PARK_REASONS`, and `_latest_pr_comment_ids` — but
every in-tree caller of those names the owner itself: in_review's and resolving_conflict's drift routes for the first,
fixing's resume and parked owners for the next four, documenting's final-docs handoff for the last. Those entries
serve historical callers alone.

The in_review owners divide by the four answers one tick can reach, and `handler` holds the order because the order is
the contract rather than a style choice. `feedback` runs before `drift`: `user_content_hash` covers every human
issue-thread comment as well as the body, so asking drift first would resume the dev over a review comment that should
have been bookmarked and handed to `fixing`. `feedback` routes through `fixing_route` for the flip, and the bookmarks
it writes are deliberately not watermarks — the fixing handler re-reads the same comments to build its prompt.
`drift` reads the PR conversation before the ratchet can leap past it, resumes the dev, and hands both outcomes back to
`validating` with `review_round` reset. `merge_gate` is last and never merges: an unmergeable PR parks for a human
(no `resolving_conflict` route from this stage) and a mergeable, approved, unvetoed head earns one HITL ping per head
SHA. `models` and `state` reach nothing at all and `watermarks` reaches no further than the client it is handed, so
the carriers, the wire key, and both the ratchet and the legacy seed are decidable without a worktree or an agent. So a
patch that has to intercept the scan, the route, the resume, or the ping targets the owner module.
This stage owns no dev machinery either: the resume comes from `workflow/stages/implementing/` and the body-edit
disposition from `workflow/stages/validating/drift_outcomes.py`, so a patch on one of those lands on the owner. The
seams that stay on the facade are the ones the stage does not own — the worktree and HEAD helpers plus
base-sync's `_AUTO_REBASE_PARK_REASONS`, which is what tells a park the rebase loop owns from one this stage may
answer — and the whole historical inventory still resolves on `orchestrator.stages.in_review` with the owner's exact
identity. Two of its names keep resolving on `workflow` as well: `_handle_in_review` for the stage-to-stage edge and
`_comment_created_at`, whose one cross-package caller — fixing's quiet window — names `watermarks` itself.

The fixing owners divide by what one tick has to settle, and two of them exist as a pair because the batch that starts
the loop is not the batch that ends it. `feedback` scans forward from the three in_review watermarks; `bookmarks`
rebuilds backward from the `pending_fix_*` ids the in_review route recorded. Both are needed because the first dev
resume advances those watermarks past the triggering feedback, so once a fix has been attempted the batch a
`/orchestrator continue` must replay can only come from the ids. `feedback` also owns the ratchet, deliberately
narrower than `_bump_in_review_watermarks`: it advances each surface only to the max id actually quoted in the prompt,
on the pushed path and the park path alike, so a comment that landed mid-tick survives to the next one.
`continue_command` is the only caller that rebuilds a batch, and the only one that answers with a refusal instead of a
run. `parked` is the dispatcher for an `awaiting_human` tick and the order is the contract: the base-sync retry loop's
own parks are refused first and silently, then the explicit operator command, then the silent recovery — which fires
only on the validating route, because `review_round` accounting and watermark advancement differ between the two and
`pending_fix_at` is what tells them apart. `drift` is the exit from a stuck validating-route transient park whose
worktree has fallen behind base, and it exists because the per-tick base sync stands down on every park, so nobody
else will rebase it. `resume` owns the quiet window, the run, the interruption and live-pause refusals that write
nothing, the ACK fast path, and the `validating` relabel a pushed fix earns. `models`, `state`, and `bookmarks` reach
no further than the client they are handed, so the carriers, the wire keys, and the whole reconstruction are decidable
without a worktree or an agent. So a patch that has to intercept the rescan, the replay, the parked dispatch, the
reroute, or the run targets the owner module. This stage owns no dev machinery either: the resume and the
poisoned-session drop come from `workflow/stages/implementing/`, the dev-fix disposition, the stranded-fix probe, and
the transient-park recovery from `workflow/stages/validating/`, and the comment timestamp the quiet window measures
from `workflow/stages/in_review/watermarks.py` — so a patch on any of those lands on the owner. The seams that stay on
the facade are the ones the stage does not own — the worktree, git, and HEAD helpers plus base-sync's
`_AUTO_REBASE_PARK_REASONS` — and the whole historical inventory still resolves on `orchestrator.stages.fixing` with
the owner's exact identity, with `_handle_fixing` resolving on `workflow` as well.

The conflicts owners divide by what one tick has to establish before the rebase may run and by what it does with the
result, and `handler` holds the order: the pinned `pr_number` (without one the label can only have come from a manual
relabel), then the terminal arcs, then the body edit, then `routing` for the awaiting-human resume and the
`MAX_CONFLICT_ROUNDS` cap. `guards` and `divergence` are a pair around one decision — whether a worktree behind its
remote PR head may be published at all — and both halves fail closed: the refuse-and-park default holds unless
`guards` can prove the worktree is already on the current base AND the head it is behind is one the orchestrator
recorded, in which case `divergence` returns a lease pinned to that exact SHA so a foreign push landing mid-tick is
refused rather than overwritten. `rebase` owns the two fetches, the rebase, and the `merge_attempt` event; publishes a
clean one through `publication`; and hands real conflicted files to the dev. `resume` is the single entry point all
three dev resumes go through, and `outcomes` reads what one left behind in the order that matters — interruption,
timeout, and mid-rebase all precede any HEAD comparison. `transitions` exists because every state-changing exit shares
one of two shapes, a park plus its pinned-state write or the full pushed-round tail, and this stage has eleven of the
first and five of the second. `state` and `models` reach nothing, so the counter keys and the carriers are decidable
without a client. So a patch that has to intercept the divergence verdict, the rebase, a park, or a resume targets the
owner module. This stage owns no dev machinery either: the resume and the question / dirty-tree parks come from
`workflow/stages/implementing/`, the body-edit disposition from
`workflow/stages/validating/drift_outcomes.py`, and the auto-rebase park reasons from `git/base_sync/state.py` — so a
patch on any of those lands on the owner. The seams that stay on the facade are the ones the stage does not own — the
worktree, fetch, git, rebase, and push helpers are read as `_wf` attributes at call time — and the whole historical
inventory still resolves on `orchestrator.stages.conflicts` with the owner's exact identity, with
`_handle_resolving_conflict` resolving on `workflow` as well.

The question owners divide by what one tick has to decide, and the read-only contract is what shapes the split.
`handler` holds the order — the closed-issue finalize outranks everything, then the run, then its disposition — and
owns both worktree teardowns, because the scratch checkout this stage never pushes has to disappear on the terminal arc
and on every safe exit alike, including the ones that raise. `run` picks between the two shapes a tick can take (an
`awaiting_human` resume on a human reply, or the conversation's first spawn), owns the tracked spawn they share, and
owns the park funnel every exit lands on — a funnel that exists because the shared park helper clears `park_reason` and
the stage-specific one has to be restored after it, or the implementing relabel guard loses the `question_` prefix it
refuses on. `session` is the locked identity that keeps a multi-turn Q&A on one backend, and both prompt builders sit
there because the resume degrades to the first-round prompt when no session id survived. `outcomes` is where the
read-only contract is enforced: new commits and a dirty tree are inspected before interruption and before the answer,
and both park with the worktree kept, so a misbehaving run leaves an inspection target. `state` and `models` reach
nothing, so the park reasons, the wire keys, and the carriers are decidable without a client. So a patch that has to
intercept the spawn, a park, the assessment, or a teardown targets the owner module. The stage owns no agent or
worktree machinery: the tracked spawn, the awaiting-human park, the prompt builders, the trusted conversation text, and
the stderr diagnostics come from `workflow/engine/`, and `_cleanup_question_worktree` from
`git/worktrees/terminal.py` — the last one matters because that name also resolves on `workflow` and `worktrees`, so a
mock left on a facade would let a real teardown run. The seams that stay on the facade are the ones the stage does not
own — `_worktree_path`, `_ensure_worktree`, `_resolve_branch_name`, `_has_new_commits`, and `_worktree_dirty_files` are
read as `_wf` attributes at call time — and the whole historical inventory still resolves on
`orchestrator.stages.question` with the owner's exact identity, with `_handle_question` resolving on `workflow` as
well.

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
`UsageMetrics` -- the one on `observability/usage/metrics.py` -- that `analytics.record_agent_exit` attaches during a
tracked run so callers can read token / cost metrics off the result without re-parsing stdout; it stays `None` for a
result that never flowed through
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
dashboard and the `orchestrator/observability/usage/` parser that feeds it). The trajectory sink has its own separate
Streamlit page — the file-backed trajectory viewer (`orchestrator/trajectory_dashboard.py` over the pure
`orchestrator/trajectory_reader.py`), which reads the JSONL directly (usage and cost included) and needs no Postgres.
None of them feed back into dispatch: workflow correctness keys off the pinned state JSON and the workflow label, so
every surface is observation-only and safe to truncate, rotate, or delete. That is also why all four migrate into
`orchestrator/observability/` — the destination and the rules its owners inherit are described under
[Top-level layout](#top-level-layout).

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
   │       4. retention.prune_with_retention_logging()                    │
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
