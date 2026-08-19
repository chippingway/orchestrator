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

A responsibility answers on the owner module that defines it and nowhere else — the workflow package, the whole
analytics tree, and both Streamlit pages included — so a patch targets that module and there is no second site a mock
could be left on. Where a leaf does resolve a name at call time it is to read a knob rather than to borrow a helper —
the analytics settings, which `patch.object(analytics_settings, "ANALYTICS_LOG_PATH", ...)` decides for every owner that
reads one, because `observability/analytics/settings.py` is the single holder they all resolve through. Each of those
boundaries is named where its owner is described below.

A bare tag in the map below — `implementing`, `fixing`, `validating` — names the *stage*: the handler and the
subpackage holding it. For a stage the orchestrator labels itself, the GitHub label an issue carries is a different
string, spelled `workflow:<tag>` here and everywhere else in these docs. `in_review`, `question`, `discussion`, and
the `done` / `rejected` terminals were never namespaced, so for those the two coincide; see
[Workflow labels](#workflow-labels).

```
orchestrator/
  __init__.py           the package version and the `__all__` naming it, bound
                        here so `import orchestrator` costs no owner behind it
  cli.py                `agent-orchestrator` console-script entry point and
                        the polling process's composition point
  __main__.py           `python -m orchestrator` launch form over `cli.main`;
                        the target `run.sh` launches
  runtime/              the polling process's own owners
    __init__.py         package marker only; the composition names an owner
    state.py            the mutable state one run carries, and the
                        shell-style code a signal stop exits with
    logs.py             the stderr and rotating-file destinations a run
                        settles before its first client
    startup.py          the options a run is started with, one client per
                        configured repo, and the scheduler every tick shares
    ticks.py            one pass over the configured repos: the per-repo
                        tick, the fan-out, and the reap / prune drains
    loop.py             one-shot vs recurring polling, the interruptible
                        wait, and the guaranteed scheduler drain
    self_update.py      the git probes behind the self-restart guard
    shutdown.py         the signal handler, the bounded-drain watchdog, and
                        the forced exit it ends at
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
  github/
    __init__.py         stable public surface (`__all__`): the composed
                        `GitHubClient` and the pinned durable-state model,
                        re-exported from their owner modules
    aliases.py          the descriptor three owners bind a stateless helper
                        onto the client with, so class, instance, and module
                        access all answer with the one module function
    client.py           authenticated `GitHubClient` over the mixin chain:
                        token resolution, PyGithub setup, worker-thread clone,
                        cached label reads with a sweep-counted retry window on
                        a confirmed-absent one, stage-enter events
    checks.py           status / check-run normalization, failure-before-pending
                        folding, and the fail-closed check-read client mixin
    comments.py         comment-author trust policy (is_trusted_author /
                        filter_trusted) gating comment authors on the
                        ALLOWED_ISSUE_AUTHORS allowlist
    events.py           audit event record construction and the optional
                        JSONL sink
    issues.py           non-PR issue filtering, issue-query options, the
                        issue-state attribute and its open / closed values, and
                        the issue-client mixin (polling, label writes, events,
                        comments, child creation)
    labels.py           workflow/control label vocabulary, bootstrap
                        specifications, predicates, and the label-bootstrap
                        client mixin, which renames a pre-namespace label in
                        place rather than creating a second one beside it
    pinned_state.py     authenticated pinned-state model, parser, and the
                        state / comment-watermark client mixin
    pull_requests.py    stateless PR status helpers plus the pull-request
                        client mixin (lookup by open state and the commit-
                        pinned one beside it, which widens to every state and
                        answers a third way when GitHub could not be asked at
                        all, creation, comments, body rewrite, labeling,
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
    __init__.py         the package API: the label vocabularies, the transition
                        guard and the predicate under it, the illegal-write
                        exception, and the per-repo `tick` that resolves the
                        engine inside the call
    state.py            typed workflow state: the `WorkflowLabel` /
                        `ControlLabel` vocabularies, strict label coercion, the
                        declared transition graph, the transition guard, and
                        the `workflow:` namespace boundary -- the bare stage
                        tag under a label, the pre-namespace alias tables, and
                        which labels one issue's write owns
    engine/
      __init__.py       package marker only; callers import an owner directly
      comments.py       the orchestrator marker and capped id ledger both
                        comment posters write, the trusted-author thread read
                        every prompt quotes -- over a caller's own snapshot or
                        a read of its own, retaining the orchestrator's
                        recorded ids when a caller offers them -- the paragraph
                        break that read and the prompt builders share, and the
                        tracked-repos block
      dispatch.py       one tick's pollable issues turned into handler calls:
                        the hard-skip filter, the family / fanout partition and
                        its cap exemptions, the per-worker refetch, the
                        scheduler submits, the timed per-issue dispatch, and the
                        one log line every isolated per-issue failure reports on
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
                        and its followup, PR-comment followup, decompose,
                        discussion and its followup) plus the plan-publication
                        clause both discussion prompts carry, the commit-style
                        / foreground-only notes, the empty-body placeholders,
                        and the single-decision comment
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
      discussion/
        __init__.py     package marker only; callers import an owner directly
        handler.py      the order one discussion tick asks its questions in:
                        whether the conversation is over at all, whose turn it
                        is and whether the humans have answered, what the
                        checkout already holds, then what the round left behind
        terminal.py     what the plan PR has become, polled ahead of every
                        agent path: the merged and closed-unmerged finalizes,
                        the open-PR hold that keeps the checkout and both
                        branches, the marker lookup that finds a pull request
                        the crash window left unrecorded, and the pre-PR close
                        that rejects without tearing anything down
        session.py      the pinned agent and session a conversation is locked
                        to, the filter its replies and consumed watermark are
                        drawn through, and the prompt a round gets given what
                        it has to resume -- paired with the replies that
                        prompt has therefore read, since a full-context round
                        derives both from one snapshot of the thread
        run.py          one round in the issue's own worktree, the restorer
                        that checkout is rebuilt by, the probes bracketing it,
                        and the branch and SHA it records opening on
        outcomes.py     the pause, timeout, write, and response decisions one
                        finished round is classified by, and their routing
        publication.py  one reading of what the branch carries, which commits
                        are this stage's to publish and which only to finish,
                        the push and found-or-opened PR a plan alone earns,
                        and the records that publication hands the next tick
        parks.py        every way the stage hands the issue back, including a
                        reply into a checkout no round may open on, and the
                        funnel that stamps each park's reason and puts back
                        the consumed ceiling the shared helper overwrites
        models.py       the run, the agent identity and session, the prompt
                        paired with the replies it read, the round with the
                        HEAD it opened on, the assessed outcome, and the
                        artifact a publication is decided from
        state.py        the park reasons, wire keys, run identity, the plan
                        path the prompt and the check share, the commit the
                        plan PR carries (which implementing reads against that
                        PR's head so a merged plan is not mistaken for merged
                        work), the open-round flag and
                        the in-flight publication marker that say which commit
                        under a park is this stage's -- and, while the marker
                        stands, that no other commit is -- the predicate
                        that says which park is this stage's own, the one that
                        says whether it already asked for the checkout to be
                        repaired, and the one that says the plan is already
                        published
      documenting/
        __init__.py     package marker only; callers import an owner directly
        handler.py      the order one final-docs tick asks its questions in
        preconditions.py
                        the terminals, the missing-`pr_number` guard, the
                        parked-no-input fast path, and the refused bare continue
        drift.py        a body edit mid-hop: the dropped approval, the unwind
                        sentinel, and the relabel back to
                        `workflow:validating`
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
        drift.py        the `workflow:resolving_conflict` reroute a stuck
                        validating-route park earns when its worktree has fallen
                        behind base
        resume.py       the quiet window, the dev run, the ACK fast path, and
                        the `workflow:validating` relabel a pushed fix earns
        models.py       the frozen records the owners hand each other
        state.py        the pinned-state keys they share
      implementing/
        __init__.py     package marker only; callers import an owner directly
        handler.py      the order one tick asks its questions in
        spawn.py        awaiting-human vs active, the restorer the checkout
                        comes back from, the recovered-worktree shortcut and
                        the certified baseline it stands down for, and the
                        retry-gated fresh spawn
        session_read.py the locked session read plus the stale / overflow /
                        quota classifiers and the blockquote they quote with
        session.py      the three session retirements, the per-issue 24h spawn
                        cap, and the fresh-spawn prompt
        resume.py       the two resume entry points and the historical call
                        shape they keep
        execution.py    one resume, its poisoned-session retry, and what each
                        attempt is allowed to persist
        worktree.py     the checkout a resume runs in, restored when reaped
        disposition.py  the `before_sha` publish / timeout-park decision, the
                        certified floor a clean exit is credited against, and
                        the timeout park's own next-tick recovery
        parks.py        the session-limit, question, silent-failure, and
                        dirty-tree parks
        publication.py  the push, the PR reuse (re-bodied when it was opened
                        elsewhere) or open, and the validating handoff with
                        its counter resets
        drift.py        a body edit mid-implementation: the resume it earns and
                        the `ACK:` that answers it
        drift_preflight.py
                        a pre-session edit and the quiet timeout recovery
        continue_command.py
                        `/orchestrator continue` on a parked issue
        read_only_relabel.py
                        the `question` / `discussion` -> `workflow:implementing`
                        relabel guards, and the reconcile that keeps an
                        accepted plan handoff in step with its PR until a
                        developer publishes
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
                        `workflow:fixing` relabel
        drift.py        a body edit on an open PR: the unread PR conversation
                        captured first, the dev resume, and the
                        `workflow:validating` return both outcomes earn
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
                        the in_review watermark seed before the
                        `workflow:documenting` relabel
        verify.py       how a non-ok verify result reads and the park it earns
        watermarks.py   the seed walk past leading orchestrator comments and the
                        ratchet that never regresses one
        requested_changes.py
                        the PR feedback and `workflow:fixing`-labeled dev fix,
                        plus the
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
  git/
    __init__.py         package marker only; callers import an owner directly
    authentication.py   per-repo token resolution, the askpass session and its
                        detached environment, the authenticated worktree /
                        target-root fetches, the remote-ref read that answers
                        what a branch is at without consulting a local one, the
                        hardened lease push of a caller-named commit, and the
                        refusal logger, named orchestrator.git_plumbing for the
                        operator filters that select on it
    commands.py         plain / hardened git execution, the argv hardening
                        prefixes, the replacement-object and graft shutoff the
                        hardened environment carries, and the unsafe
                        local-transport probe
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
                        labels, and the shared logger, named
                        orchestrator.base_sync for the operator filters that
                        select on it
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
      probes.py         HEAD snapshot and whether HEAD is the branch a caller
                        publishes to, hardened NUL-delimited porcelain status
                        read in both
                        its answers (the path list, and whether git could be
                        asked at all), and the two reads a named commit is
                        judged by -- its base-relative changed paths, and
                        whether a path survived into its tree
      process.py        one command's group spawn / kill / drain and its verdict
      runner.py         stripped child env and fail-fast command sequencing
    worktrees/
      __init__.py       package marker only; callers import an owner directly;
                        cleanup, creation, decomposition, and terminal each
                        name their logger orchestrator.worktree_lifecycle for
                        the operator filters that select on it
      cleanup.py        lock-held issue-worktree removal and local branch
                        deletion behind their best-effort boundaries
      creation.py       issue / PR worktree creation, stale-worktree reuse,
                        the new-commit probe the reuse decision turns on, and
                        the one move that brings a checkout the creators would
                        have reused onto the head a pull request is really open
                        against -- or onto the base once that PR has merged
      decomposition.py  decomposer scratch path, detached creation, and
                        best-effort removal
      paths.py          slug sanitization, git-ref-safe branch segments, path
                        and branch derivation, pinned/legacy branch resolution
      recovery.py       candidate-branch discovery, the unpushed-commit probe,
                        and the absolute tip read of one caller-named branch
                        that a recorded SHA is compared against
      terminal.py       question-stage teardown and terminal local + remote
                        branch cleanup composed from cleanup.py
  observability/
    __init__.py         package marker only; home of the usage parsers, the
                        analytics configuration, recording, retention,
                        read-path, and replay owners beside them, the visual
                        theme both Streamlit pages are drawn in, the whole of
                        the analytics page beneath it -- the state a run
                        carries, the reads it issues under that state, the
                        banners and headline numbers it reports above them,
                        the panels and figures it draws them as, and the order
                        one render reaches all of them in -- and the whole of
                        the trajectory viewer beside it: the file-backed read
                        model, the filters over it, and every builder its page
                        is drawn from
    analytics/
      __init__.py       package marker only; home of the sink configuration,
                        its append side, the by-age prune that bounds it, what
                        a read is asked for, dials with, and answers with, and
                        the replay that fills the database behind it together
                        with the command that starts one
      config.py         the parse of the six sink / database environment
                        knobs, the `Settings` view every adapter reads one
                        back through, and the read-path URL fallback
      settings.py       those six knobs as parsed for this process: the one
                        holder every owner reads them off and a caller
                        patches one on
      sink.py           what both sinks share on the way to disk: the record
                        envelope, the locked JSONL line, the one lock each of
                        them holds, and the channel a refused write is
                        reported on
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
        events.py       the analytics sink's append, the three recorders a
                        producer calls directly, and the shared envelope
                        republished for them
        models.py       typed requests and the keyword signatures a call
                        is bound through
        agent_exit.py   the order one finished run is summarized and
                        written in, and the recorder that enters it
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
      sync/             the JSONL -> Postgres ingestion and its command
        __init__.py     package marker only; callers import an owner directly
        columns.py      what a record must carry, which fields the table
                        promotes, and the two columns that hold JSON
        records.py      the encoding a record's content hash is taken over,
                        and the coercion each required field is narrowed by
        rows.py         the INSERT a batch is sent under, the positional tuple
                        that fills it, and the reason a line is skipped for
        models.py       the counts a replay is read back as, the mutable
                        tallies behind them, and what one pass carries
                        between lines
        ingest.py       the startup scan and the in-file skip set both dedup
                        filters read, the batched flush, and the progress and
                        malformed records dropped along the way
        database.py     the lazily imported driver, the two adapters a caller
                        may replace, the quiet rollback and close, and the
                        rollup left refreshed
        redaction.py    what the dialled URL looks like once it reaches a log
                        line
        run.py          the service entry point: what one replay resolves to,
                        which configured states are a no-op, and the
                        transaction shape around the ingest
        cli.py          the `-m` entry point an operator schedules: the
                        arguments, the UTC-pinned logging, the stdout summary,
                        and the exit code one run is read back as
      trajectories/     the opt-in per-run reasoning sink
        __init__.py     package marker only; callers import an owner directly
        models.py       the head/tail and whole-record caps, the snapshot one
                        record is measured against, and the headline and
                        running budget it is charged as
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
    dashboard/          the Streamlit analytics page: the visual theme both
                        pages are drawn in and the one name a page hands it
                        down under, the state one run of it carries
                        and the bar its window is picked in,
                        the two waves its load is staged into, the fan-out
                        each is issued through and the dispatch that drives
                        both, the seven a
                        headline or lifecycle section is drawn from, the six a
                        comparison panel is and the three a skill panel is,
                        what one of those reads then runs on and is narrowed
                        by, the banners a window is interrupted with above all
                        of them, the numbers it is summarized by beneath them,
                        the strip those numbers are shown in, the line
                        drawn under three of them, and the banner, filter line,
                        and delta pill that strip sits among, the markup a
                        card, a banner, a tile, and a compact table are drawn
                        as, the four panels listed in that table — the last two
                        each split across the five owners a sortable one
                        needs — the two cards three of those panels are
                        reported on, the listing of the
                        runs beneath them, and the two
                        that are markup rather than a figure, the figures the
                        rest are drawn as and the defaults every one of them
                        is handed, and the shapes a whole render is threaded
                        through
      __init__.py       package marker only; callers import an owner directly
      palette.py        the page chrome and semantic colors, the seven maps
                        pinning a dimension value to a hue, and the ordered
                        fallback a value no map covers resolves through
      tokens.py         the radii, card inset, grid gap, and content width the
                        page is laid out on, and the two font stacks it is set
                        in
      layout.py         the Plotly layout every figure is merged with: the
                        margins, font, gridlines, legend, and card-colored
                        backgrounds they share
      css.py            the stylesheet the page injects for its own chrome,
                        with every token interpolated from the two owners above
      formatting.py     the compact money, token, and count renderings a KPI
                        tile, an axis tick, and a bar label are narrow enough
                        to need
      theme.py          the five owners above read back under one name, which
                        is the theme object a page hands every panel it draws
      tables.py         the compact table the hand-rolled panels are drawn as:
                        the stylesheet each scopes to itself, the header and
                        body they are assembled from, and the bar width, short
                        repository name, missing count, and unpriced amount a
                        cell reports
      issue_table.py    the first of those panels: the six columns a window's
                        costliest issues are ranked into, the rules their
                        in-row bars and status pills are painted by, and the
                        readings one issue is reduced to and rendered as
      skill_trigger_table.py
                        the second: the six columns a cohort's skill use is
                        reported in, the busiest rate in the table its bar is
                        drawn as a share of, and the label a category the sink
                        left empty is read under
      skill_adoption_columns.py
                        the third arrives split by what a click moves: the
                        nine columns it is read across, the key each is
                        ordered by, and the two query parameters a heading
                        writes
      skill_adoption_sort.py
                        the parse those parameters are read back through and
                        the two orders they select, including the
                        repository-then-rate default
      skill_adoption_headers.py
                        the header row each heading is drawn as a sort control
                        in, and what a click on one offers
      skill_adoption_rows.py
                        what one `(repo, role, backend, skill)` cell says: the
                        undefined rate a skill nobody was offered reports, the
                        real zero one nobody loaded does, and the two
                        diagnostics counted apart from both
      skill_adoption.py the panel those cells are sorted into, and the notice
                        a window with no session evidence renders instead
      skill_matrix_columns.py
                        the fourth arrives split the same five ways: the
                        seven columns it is read across, the key each is
                        ordered by, and its own two query parameters
      skill_matrix_sort.py
                        the parse those parameters are read back through and
                        the two orders they select, including the
                        repository-then-rate default
      skill_matrix_headers.py
                        the header row each heading is drawn as a sort control
                        in, and what a click on one offers
      skill_matrix_rows.py
                        what one `(repo, role, backend, skill)` cell says, and
                        the tone a cohort that triggered nothing is drawn in
      skill_matrix.py   the panel those cells are sorted into, and the notice
                        a window with no catalog-backed cell renders instead
      skill_panel.py    the card the adoption table leads and the two
                        invocation views fold collapsed under, the single
                        notice a window with no run at all is answered with,
                        and the caption a window nobody adopted anything in is
                        qualified by rather than nagged over
      skill_trigger_panel.py
                        the trigger-rate card a caller reaching past that one
                        still gets, its own notice and enable-tracking prompt,
                        and the matrix folded collapsed beneath it
      recent_runs.py    the runs under those four panels rather than a fifth
                        in that table: the columns one is scanned by, the
                        offset its timestamp is read on, the collapsed expander
                        the page ends on, and the notice a window with no
                        `agent_exit` row renders in place of an empty frame
      drilldown.py      one issue's trace under that listing: the read it
                        issues outside the cached wrappers, the columns one
                        event is traced in, and the notices a number typed
                        before a repository, an empty window, and a failed
                        read are answered with
      drilldown_request.py
                        the call shape that trace is still reachable under:
                        the declared signature seven keywords are bound
                        through, and the typed request they are read back as
      page_states.py    what is drawn where none of those panels can be: the
                        startup state an un-ingested database is answered with
                        and stopped on, the notice a window matching no row
                        renders together with the load line its skipped second
                        wave would have carried, and the footer a page that
                        did draw closes on
      usage_panel.py    the hero card above all of them: the header it is
                        titled by, the toggle deciding whether a day's tokens
                        stack by what they were spent on or by who spent them,
                        the session key that mode survives a rerun in, and the
                        per-day per-backend totals the second stack is drawn
                        from
      windows.py        the half-open UTC window a run reports over, the
                        presets that name one, and the clamp that keeps a
                        preset inside the data extent
      filters.py        the offset a timestamp is displayed in, the issue and
                        stage selections a read is narrowed by, and the key
                        every cached read is stored under
      date_controls.py  the five slots the filter bar that window is picked in
                        is laid out across, the label naming it, and the three
                        presets it offers inline
      date_filter.py    the bar itself: the window a preset opens the pickers
                        on, the inclusive days they hand back, and the
                        half-open window plus the filter-line slot the caller
                        leaves with
      page_controls.py  the whole band above the panels and the load it
                        opens: the sidebar a run is narrowed in and the
                        selections it answers with, the offset that run's
                        timestamps are displayed against, the filters those
                        selections normalize into, the controls the band is
                        read back as, and the staged plan every panel below
                        is then drawn from
      read_mode.py      the parallel-read knob and its truthy spellings, the
                        parse that reads it and the flag one process's loads
                        are issued under, the worker cap, and the refusal an
                        unconfigured database is answered with, message
                        and URL check together
      read_plan.py      the two waves one page load is staged into, the cached
                        task each entry is bound as and the TTL it is held
                        for, and the current / previous key pair they are
                        issued under
      fanout.py         one wave of named readers run the way that flag said:
                        on the calling thread, or across a pool capped at the
                        worker count beside the knob
      dispatch.py       both waves driven around the render between them: one
                        spinner over the pair, the banner and stop a failed
                        read is answered with, and the line a completed load
                        is measured by
      page_pipeline.py  what is drawn in between, and the load it is drawn
                        inside: the banner and filter line written back into
                        the slots the controls left, the banners a window is
                        worth interrupting a page for, the four-tile strip
                        every section below is read against, and the staged
                        load whose first pass is also where one can end early
      chart_sections.py the five cards a window's figures are drawn on, in
                        the order the page stacks them
      page_sections.py  the four panels beneath those cards, and the one call
                        the whole second wave is drawn by
      page_models.py    the seven frozen shapes one render is threaded
                        through: the caller's module handles, the selections
                        every read is narrowed by together with the issue
                        scope and window span read off them, the controls and
                        page they open on, what one load answers with, and the
                        rows, totals, and counts the paired repository-spend
                        and run-health section is drawn from
      rollups.py        the seven reads a headline or lifecycle section is
                        drawn from, the cap the run list among them is read
                        under, and the ranking depth the spend table borrows
                        from the KPI owner
      breakdowns.py     the six reads a comparison panel is drawn from, each
                        naming the rollup or breakdown query owner that
                        answers it
      skills.py         the three reads a skill panel is drawn from, each
                        naming the skill query owner that answers it off an
                        `agent_exit` row's `extras`
      scoped_reads.py   the checkout of this thread's analytics connection one
                        read is issued inside, which is what keeps that read's
                        cache key connection-free
      filter_binding.py the filters a cache key is read back as, and the
                        windowed read issued under them
      static_metadata.py
                        the extent and filter vocabulary a page opens on, the
                        TTL both are cached for, and the banner a failed one
                        stops the run with
      insights.py       the two observations a window is worth interrupting a
                        page for -- runs exiting non-zero, and runs the parser
                        could not price -- the ratio each is raised at, and the
                        banner line a crossing is rendered as
      kpis.py           the four numbers a window is summarized by beneath
                        those banners: the move against the window before it,
                        the run-health tiles, the order and depth a spend table
                        is cut to, and the share of spend that was a second
                        pass
      kpi_series.py     the per-day spend, token, and resolved lines drawn
                        under three of those numbers, the two token totals they
                        and the tiles are counted by, and the throughput pair
                        reported beside them
      kpi_strip.py      the strip itself: what one is built from, the scalars a
                        window and the one before it are reduced to, and the
                        four display entries a page opens with
      sparkline_points.py
                        where each day of one of those lines sits in a box too
                        narrow for an axis: the window's own range it is
                        scaled to, the floor a window without one is clamped
                        at, and the window that is left undrawn instead
      sparkline_html.py the SVG that projection is written as: the polyline
                        the line is stroked along, the same trace closed along
                        the bottom edge of the box into the tint under it, the
                        box a window with nothing to draw still holds, and the
                        keyword surface a caller asks for one through
      summary_html.py   the band that strip sits in: the banner naming what the
                        database holds, the line restating what a run's filters
                        narrowed it to, the pill one tile's move against the
                        window before it is annotated with, and the four tiles
                        assembled around them
      card_html.py      the markup the banners and the run-health tiles are
                        drawn as, and the header every panel beneath them is
                        titled by: the hidden mark the stylesheet selects a
                        card's container by, the banner stack, and the
                        reliability strip whose numbers the caller's own
                        formatter renders
      backend_card.py   what a run on one backend is worth -- the cost of a
                        million tokens, the cost of a run, and the share of
                        billable input the cache answered -- the guard each of
                        those ratios divides through, and the card they are
                        laid out on
      coverage_card.py  the share of a window's spend the parser could price,
                        sized by token volume wherever there is any and by run
                        count where there is none, drawn as one bar and the
                        legend beneath it
      stage_cost_panel.py
                        the paired lifecycle bars a window's spend is split
                        across: the 7:5 columns the stage and review-round
                        figures are laid out in, and the one height both are
                        pinned to together with the row and base measurement it
                        is built from
      issue_cost_panel.py
                        the ranking beneath those bars and the backends beside
                        it: the columns a window's costliest issues and its
                        per-backend cards are split into, the coverage bar that
                        closes the second, and the two notices an unpriced
                        window and a window with no run at all are answered with
      reliability_panel.py
                        the pair beneath those two: the window's spend by
                        repository beside the six tiles its runs are read for
                        and the per-day strip of the issues they resolved,
                        bounded by the last day the window covers rather than
                        by its half-open end
      activity_panel.py the card beneath all three: the weekday-by-hour grid a
                        window's tokens are laid out on, the zone its hours are
                        headed and annotated in, and the one selectbox that
                        picks that zone, keyed under the name the next rerun
                        reads the offset back off
      render_config.py  the Plotly configuration every one of those figures is
                        handed: the hover toolbar switched off once for the
                        whole page rather than per call site
      charts/           the Plotly figures those reads are drawn as: what
                        every family is built out of, the frame the horizontal
                        cost families share, the generic spend ranking, the
                        per-repository one drawn through it, the per-stage
                        cache split, the per-review-round one beside it, the
                        weekday-by-hour grid, and the per-day throughput strip
                        above the two, and the usage family's own shaping,
                        axes, traces, and hero figure
        __init__.py     package marker only; callers import an owner directly
        primitives.py   the placeholder a window holding no rows is answered
                        with, the money, mono, and two-line-tick labels a bar
                        is annotated by, and the height and legend a
                        horizontal-bar panel is laid out with
        cost_layout.py  the margin, `USD` axis, and height every horizontal
                        cost panel is framed by, plus the request one series of
                        bars is described by and built from
        cost_horizontal.py
                        the generic ranking a window's spend is drawn as: the
                        order, tint, and flip behind its bars, and the pinned
                        call shape the builder is bound through
        cost_repo.py    the per-repository ranking drawn through it: the short
                        name a bar is labelled by, the agent runs its sub-line
                        counts, and the accent every bar takes
        cost_stage.py   the per-stage split of that spend into what the cache
                        paid for and what it did not: the ranking and full-price
                        fallback behind the halves, the shading a cache half is
                        tinted with, and the stack they are drawn as
        cost_review.py  the same split per review round and across the two
                        roles a round is worked by: the round order and labels
                        behind the rows, the totals each role's bar is labelled
                        by, and the four series they are described as
        heatmap.py      the 7x24 weekday-by-hour token-volume grid: the cells a
                        window's points are bucketed into, the labels and hour
                        span shaping them, and the layout that squares them off
        throughput.py   the per-day resolved-issue strip: the calendar a
                        window's days are filled in from, the series those days
                        and counts arrive as, and the height it is pinned to
        usage_bands.py  the four bands a day of usage is counted into, the mode
                        its stack is switched with, the per-day table they are
                        accumulated in, and the roll-up of the series into one
                        bucket per day
        usage_series.py the days that roll-up spans, the shapes they and the
                        axis maxima travel in, the completion of the days only
                        the per-backend read saw, and the height each stack
                        reaches
        usage_axis.py   the step count and pinned height a usage figure is
                        drawn at, the rounding that gives each axis a maximum
                        it divides into equal steps, and the layout the token
                        and cost scales are assembled in
        usage_traces.py the shaping that decides whether a window has a chart
                        at all, the band a stack is added one of at a time, the
                        two modes it is stacked in, and the cost line overlaid
                        on the secondary axis
        usage.py        the hero figure those pieces are assembled into --
                        stack, cost overlay, and the layout merged over both --
                        and the backend-day stub published beside it
    trajectory_viewer/  the file-backed trajectory page's read model, every
                        inline-HTML builder it is drawn with, and the controls
                        and rendering a run of it is driven by
      __init__.py       package marker only; callers import an owner directly
      constants.py      the event a line is read for, the brackets a run is
                        wrapped in, the tells that mark a fixture, and the
                        banner an unconfigured sink answers with
      coercion.py       the narrowing every untyped record field passes
                        through, so an older or hand-edited line costs a
                        smaller row rather than a failed read
      models.py         the four frozen views a record is read back as and the
                        declared constructor signatures two of them are built
                        through
      runs.py           the run record itself, with the views below bound onto
                        it as properties and its cached per-turn index
      usage_views.py    a run's step and tool-call tallies, its model, cost,
                        and token total, and the per-turn usage lookup
      timeline_views.py the one ordered sequence a run renders as, the labels
                        it is picked by, and the fixture tells applied to it
      parsing.py        one decoded line read back as a record: the event it
                        is accepted for, the position it is stamped with, and
                        the step and turn narrowing under it
      reading.py        one pass over the file: the lines skipped, the
                        newest-first order records come back in, and the read
                        error warned about rather than raised
      log_paths.py      which file that is, read off the settings holder a
                        caller hands in, and the banner an unconfigured sink
                        answers with instead
      filter_models.py  the two spellings one filter request arrives as, the
                        normalized form a match reads, and the distinct values
                        a page is offered
      filter_values.py  one value: the distinct ones collected off a read, the
                        empty selection that constrains nothing, and the text
                        a free-text needle is compared against
      filtering.py      which runs one request keeps, in the order the read
                        handed them over, and the request it refuses to take
                        twice
      summaries.py      the headline counts the surviving runs are totalled
                        into, the money among them counted only where a run
                        recorded some
      css.py            the stylesheet this page adds on top of the chrome
                        both pages share, with the two font stacks
                        interpolated from the geometry owner
      summary_html.py   the banner naming what the file holds and what the
                        filters left, the five KPI tiles beside it, and the
                        exact-cents money they are rendered with
      run_html.py       one run's metadata grid, its overview-table row, and
                        the label it is picked by, each marking a fixture
                        where the record is one
      usage_html.py     what a run cost: the reported run-level row, the
                        per-turn estimate strip, and the note saying why the
                        two need not sum
      timeline_html.py  the badge, name, and position one timeline entry is
                        headed by, and which entry a usage strip is drawn
                        above
      page_models.py    the two frozen shapes one run of the page carries --
                        the file as it was read, and what the controls
                        answered
      page_setup.py     what a run settles first: the two stylesheets, the
                        opt-in refusal, and the one pass over the file
      controls.py       the sidebar an operator narrows a read with, and the
                        narrowing those answers drive
      picker.py         the capped overview table and the uncapped repo →
                        issue → run cascade that reaches every match
      run_render.py     the detail card one selected run is read in full
                        through, notices before timeline
      page_render.py    the order a whole page is drawn in, and the two empty
                        reads it stops short on
  apps/                 the two Streamlit pages a `streamlit run` names; the
                        polling loop is launched at cli.py instead
    __init__.py         package marker only; an app is named to be launched
    bootstrap.py        the repo-root `sys.path` shim a script launch needs,
                        standard library only so it resolves before it runs
    analytics_dashboard.py
                        the analytics page's `streamlit run` target, composing
                        the dashboard owners inside the passes that draw
    trajectory_dashboard.py
                        the trajectory viewer's `streamlit run` target,
                        composing the viewer owners inside `main()`
  skills/               the two skill-enumeration owners
    __init__.py         package marker only; callers name an owner
    catalog.py          per-tick repo skill-catalog collection: enumerate
                        SKILL.md definitions on the target base ref and
                        append one `repo_skill_catalog` analytics record
    discovery.py        per-run filesystem skill discovery and codex tool
                        list, plus the skill roots and SKILL.md marker
                        `catalog.py` reads back
```

Five rules hold for the tree as a whole, each with a check under `tests/repository/` that finds its subjects on disk so
a module added anywhere is covered the day it lands. The root is the three files above plus the ten packages under
them, held to that exact inventory: a module parked beside them would be importable next to the package that owns the
responsibility, and both would answer. No module wears one of the retired domain families as a prefix. Every family is
forbidden in the private spelling its compatibility leaves carried (`_dashboard_read_core.py`), and the families whose
word names a domain package and nothing else — `dashboard_`, `workflow_`, `git_`, `state_machine` — in the public
spelling as well, so `workflow_state.py` fails one level down exactly as it would at the root. A word that also names a
responsibility *inside* a package keeps its public spelling: `charts/usage_axis.py` and `usage/trajectory_models.py`
are owners under the family's own package rather than that family flattened out of it. Nothing is named for an
inventory of names either — `exports.py`, `manifest.py`, `compatibility.py`, whole or as the tail of a prefixed one,
the decomposer's output manifest excepted — and nothing carries a `.pyi` stub or a module-level `__getattr__` /
`__dir__`: a re-export is the owner's own object bound at import, so a lookup lands on the module that defines the name
rather than on something answering for it.

Imports run one way through four layers — `config/` at the bottom, the domains that do the work above it, `workflow/`
deciding with them, and `cli.py` / `__main__.py` / `runtime/` / `apps/` composing the lot. The direction is read
twice, because deferring an import weakens where it lands but not whether it belongs. At module scope, where an import
decides what a package costs to load and whether it can be loaded at all, nothing points up but `workflow/state.py` —
named exactly, and only by the two layers its labels type, `github/` and `git/`. Over every scope, the only reaches
left are declared one by one in `tests/repository/test_layering.py`: three base-sync owners posting a notice or a park
through the workflow's comment and guard owners, deferred to a call because at module scope they would be a cycle. An
undeclared hop fails wherever it is written, and a declared one fails if it is bound at module scope after all. The
launch forms compose each other and are reached from nothing below them at any scope, and no import anywhere is
relative, because a relative target names its module by position and no layer can be read off it. And a package either
publishes an explicit `__all__` of its owners' own objects, with nothing else of the package's own left in its
namespace beside it, or fronts nothing and imports nothing at all — the submodules on a marker package are what other
modules' imports planted there, not what its initializer loaded, so naming the package costs no owner behind it. That
second half is read from the initializer's source, because the namespace cannot tell an eager sibling import from
somebody else's; what an initializer imports from outside the package for its own use is a helper rather than a
surface, and is held to neither. The eight that publish are listed under
[`configuration/operations.md#continuous-integration`](configuration/operations.md#continuous-integration), where each
is also a scoped lint waiver.

The test tree mirrors this one, and two more checks hold it there: every package above has a mirrored tests package,
and every directory the suite collects from carries an initializer of its own, with nothing at the tests root but the
suite-wide fixtures. The mirror is why the same short module name recurs once per domain — one `test_imports.py` per
package — and those initializers are what keep the recurrences distinct at collection.

Nothing under `git/publication/` sits behind a facade: the
divergence probe, the first-commit-subject read, the two subject-shape predicates, the two title helpers, and the
squash entry point are each reached on the owner that defines them, `git.publication.probes`, `.titles`, or `.squash`.
No facade of the publication domain's own sits beside `git/publication/`, and two checks in
`tests/git/publication/test_imports.py` assert that none does and that no aggregate over the git domains sits above
the package either, so every publication name answers on its owner alone -- the conventional-commit pattern and the
recent-base-subject read, the plan and the preparation it comes from, the whole rewrite half, and the parsing and
subject-vocabulary helpers the probes are built on included. A test intercepting one
targets the module its caller reads it off.
That is `git.publication.probes` for base sync's divergence check, for the ahead/behind reads the documenting prep,
the conflicts routing, and validating's stranded-fix probe take, and for the first-commit subject behind a fresh dev
PR; `git.publication.titles` for the two title helpers that same PR falls back to; and
`git.publication.squash` for validating's squash. Inside the package the owners bind their
collaborators directly -- `probes` calls `git.commands`, `titles` calls `probes`, `planning` calls `git.commands`,
both siblings, and the verification probes for its HEAD and dirty-file guards, `rewrite` calls `git.commands`,
`git.authentication`, and the verification probes, and `squash` calls `planning` and `rewrite` -- so a patch that has
to intercept the hardened reset, the force-push, or the plan a rewrite spends targets the owner module. The stage
side is bound that way too: validating's approval arc calls `squash._squash_and_force_push` directly, so a mock that
has to intercept the squash a review approval runs targets `git.publication.squash`. What
`orchestrator.branch_publication` names is
the logger `rewrite` reports a failed rollback on, spelled out literally rather than derived from the module path, so
the prefix an operator's level and handler selection is keyed on holds still while the owners beneath it move.
`git/verification/` is bound the same way -- `output`
calls `models`, `process` calls `output` and `probes`, `runner` calls `process` -- and the validating approval gate
reaches `runner._run_verify_commands` directly, so a patch that has to intercept the verify run, the HEAD snapshot, or
the dirty-file scan targets the owner module. `_run_verify_commands` answers on `git.verification.runner` alone, as
`VerifyResult` and `_truncate_verify_output` do on their owners and `_head_sha` / `_head_on_branch` /
`_worktree_status` (with `_reported_paths` and `_suppressed_index_paths` under it) /
`_worktree_dirty_files` / `_committed_paths_since` / `_revision_contains_path` / `_commit_present` /
`_commit_contains` on
`git.verification.probes`: every stage owner that compares a HEAD
watermark, refuses a dirty tree, proves one clean, asks which paths a branch's commits change against base, asks
whether a path survived them as a regular file -- a symlink or a gitlink resolves at the same path while carrying no
document -- asks whether an id it is about to record names a commit this clone can read at all, or asks whether the
commit it is about to push over a tip keeps what is on it,
asks whether the checkout's `HEAD` is the branch it is about to publish to
at all, names the probe owner, so a mock for any of them lands there. No
facade of the verification domain's own sits beside `git/verification/`: a check in
`tests/git/verification/test_imports.py` asserts nothing resolves at `orchestrator.verify` or at the inventory and
resolver-hook paths a second import site would be built from, so every verification name is defined on an owner and
answers there alone. `git/authentication.py` binds the same way --
the authenticated fetches and the push reach `git.commands` and `git.locks` plus their own token, session, lease, and
refusal helpers directly -- so a patch that has to intercept the transport probe, the target-root lock, the session,
or the remote-ref lease read targets `orchestrator.git.authentication`. The squash rewrite and every stage fetch
and push name that owner, so a mock that
has to intercept that force-push, either conflict fetch, validating's pre-fix fetch, the documenting prep or
drift-unwind fetch, or the implementing, validating, conflict, or docs push targets it -- as does the discussion
stage's pre-spawn base read, `_remote_branch_tip`, which asks the remote what a branch is at without consulting a
local ref at all.
The plain and hardened runners answer on `git.commands`, which documenting's drift reset, the divergence and
base-distance reads conflicts takes, and fixing's behind-base probe all name directly.
The no-prompt environment
and the whole lock surface -- the registry, its guard, and the per-root lock -- answer on `git.commands` and
`git.locks` alone, which a check in `tests/git/test_imports.py` pins. No facade of the
git-execution domain's own sits beside `git/authentication.py`, `git/commands.py`, and `git/locks.py`: two further
checks there assert that nothing resolves at `orchestrator.git_plumbing`, at `orchestrator.worktrees`, or at the
inventory and resolver-hook paths a second import site for either would be built from, and that no inventory in the
package names either spelling as a target. What `orchestrator.git_plumbing` still names is the logger
`authentication` reports a fetch or
push refusal on, spelled out literally rather than derived from the module path, so the prefix an operator's level
and handler selection is keyed on holds still. A mock lands on
`orchestrator.git.commands` / `orchestrator.git.locks` for those stage git calls and for the hardened command or
the lock a `git/worktrees/` owner runs under. The `git/worktrees/` owners
bind the same way — the creators reach `git.commands`, `git.locks`, `git.authentication`, and their in-package
`paths` / `recovery` siblings directly, the decomposer lifecycle resolves its own path helper, and `terminal`
composes its local teardown from `cleanup` — so a patch that has to intercept the git plumbing, the authenticated
fetch, the new-commit probe, or the worktree path one of them runs against targets `orchestrator.git.commands` /
`orchestrator.git.authentication` / the owner module.
`workflow/stages/question/handler.py` and
`workflow/engine/terminals.py` call `terminal._cleanup_question_worktree` / `terminal._cleanup_terminal_branch`
directly — the terminal owner reading its branch name off `worktrees.paths` first —
so a mock for either one lands on that owner. Every other stage owner binds that way too --
the PR-aware and plain creators, the new-commit probe, the branch and worktree-path derivations, the
unpushed-commit probe, and the whole decomposer path/creation/removal trio -- so a mock for the checkout a stage
restores, names, probes, or tears down lands on `git.worktrees.creation` / `.paths` / `.recovery` /
`.decomposition`. The two sanitizers, the
branch and worktree-path derivations, and the pinned/legacy resolver answer on `git.worktrees.paths`, the
unpushed-commit probe on `recovery`, the two creators, the new-commit probe, the PR-branch start point (the PR's own
remote head while THIS tick's fetch of it landed, and `<remote>/<base>` only when the REMOTE says there is no such
branch -- a merged PR whose branch GitHub deleted keeps its `pr_number`, so naming a ref nobody has would fail every
later tick's `worktree add` and no implementer would run again, while reading a failed fetch as that deletion would
rebuild a live PR at base and force-push over it, so an unconfirmed absence raises instead. A remote-tracking ref
outlives the fetch that wrote it, so one a failed fetch left behind is not anchored on either: restored from it, an
interrupted publication comes back looking like a branch somebody reset, and the recovery retires its marker while the
plan sits published on a PR nobody recorded), the base anchor a finished pull request's branch ends on (a base this
tick fetched or nothing at all, for that same reason: a cached ref names the base as of the last fetch that worked,
which for work that has only just merged is a base without it), and the
handoff anchor
(`_anchor_pr_worktree`, the one mutation here that MOVES a checkout the creators would have reused -- for the caller
that has already proved it carries nothing of its own and needs the branch on the head a PR is really open against
(re-read from the remote rather than taken from the caller, since the head it names was read off GitHub before this
ran and a commit pushed in between leaves the fetch bringing THAT one while the named one still resolves underneath
it), or
on the base once that PR has merged and the design it carried has landed there,
and hardened like every other reset in the repository since both the checkout and the common repo it shares are ones
an agent has had)
on `creation`, the decomposer's
path, creation, and removal on `decomposition`, and the two teardowns on `terminal`. The slug pattern and the
worktrees root answer on `git.worktrees.paths` alone. No facade of the
worktree-lifecycle domain's own sits beside `git/worktrees/`: three checks in
`tests/git/worktrees/test_imports.py` assert that nothing resolves at `orchestrator.worktree_lifecycle`, at
`orchestrator.worktrees`, or at the inventory and resolver-hook paths a second import site for either would be
built from, that no inventory in the package names either spelling as a target, and that each of the
twenty-nine names the owners define -- the removal and
branch-deletion steps under `cleanup` and the `worktree` argv `creation` runs, the decomposer's own removal
runner, the candidate-branch and commit-count reads under `recovery`, and the slug digest internals under `paths`
among them -- is defined on the owner it is paired with. What `orchestrator.worktree_lifecycle` still names is the
logger
`cleanup`, `creation`, `decomposition`, and `terminal` all report on, spelled out literally in each rather than
derived from the module path and pinned by a fourth check in the same module, so the prefix an operator's level and
handler selection is keyed on holds still. `git/base_sync/` binds the same way: `models` and `state` carry only
data -- the frozen auto-rebase models and the pinned-state keys, park reasons, detour labels, and logger every
behavioral owner binds straight off `state` -- while its twelve behavioral owners bind their collaborators.
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
than the aggregate surface. No facade of the base-sync domain's own sits beside the package: a check in
`tests/git/base_sync/test_imports.py` asserts nothing resolves at `orchestrator.base_sync` or at the inventory
and resolver-hook paths a second import site would be built from, so every base-sync name answers on the owner
that defines it and nowhere else. `state` still names its
logger `orchestrator.base_sync` -- the one place that string
is a contract rather than a module path, because operator log filters select on it -- and the three
keyword-call adapters, the PR sync in `pr`, the conflict route in `conflicts`, and the crash recovery in
`recovery`, still take the pre-context argument lists their callers spell, normalizing each into the typed
context entrypoint beside it. Nothing inside the package reads a
collaborator back off a facade either, so a test that has to intercept the per-worktree sync the refresh
drives, the PR-aware coordinator it hands a worktree off to, or the conflict route a failed rebase takes
patches `refresh` / `pr` / `conflicts`. Every caller above the package names an owner the same way: the tick names
`refresh` for the opening pass, the conflicts owners name `pre_pr` for the base rebase and the in-progress probe,
and every stage that must leave an auto-rebase park alone names `state` for the park reasons -- so a mock lands on
the base-sync owner, and a mock left anywhere else would let the real fetch, rebase, or vocabulary answer instead.
The collaborators these owners reach *upward* are call-time imports: `persistence` binds the awaiting-human
park from `workflow/engine/guards.py` -- not from its own `guards` sibling, which owns the publication
refusals -- and the PR-comment poster straight off its owning module, and `publication` and `conflicts` bind
the same poster for their notices, so a patch for the park targets `orchestrator.workflow.engine.guards` and
one for any of the notices targets `orchestrator.workflow.engine.comments`.

`orchestrator/workflow/__init__.py` is the package API and nothing more: six names. Five are re-exported from
`workflow/state.py` beside it -- `WorkflowLabel` and `ControlLabel`, the `guard_transition` write guard and the
`is_allowed_transition` predicate under it, and the `IllegalTransition` an illegal write raises -- and the sixth is a
`tick` that resolves `workflow/engine/tick.py` inside the call. That last part is a layering constraint, not a
style choice. The GitHub and git layers below the engine import `workflow/state.py` for the label vocabulary they are
typed by, and a submodule import runs the initializer first, so an engine import at module scope would send
`github/labels.py` and `github/issues.py` straight back into the GitHub client they are still initializing.
Importing the package therefore costs the initializer and the state owner, and pulls in neither the stage tree, the
engine, the config and analytics graph, nor the git and GitHub subsystems -- which
`tests/workflow/test_imports.py` holds by probing both import paths in a clean interpreter. Those three layers --
`github/labels.py`, `github/issues.py`, and the `git/base_sync/` owners -- all bind the state owner directly, and no
flat module sits beside the package: a check in `tests/workflow/test_imports.py` asserts nothing resolves at that
module path. So `workflow/state.py` is the one module that *defines* the label vocabulary, its graph, and the write
guard, and the two sites they answer on are that owner and the package API's re-export of five of them -- the same
objects, which `tests/workflow/test_imports.py` pins by identity, so the graph a caller reads cannot fork. In-tree
callers name the owner; the re-export is for callers outside the tree.

Two log channels come out of this package, and each owner spells its own literally rather than deriving one from
`__name__`: the engine and stage owners report on `orchestrator.workflow` and `workflow/state.py` on
`orchestrator.state_machine`. Both are what an operator's filter and handler select on, so a module moved between
packages must not take its channel with it -- which `tests/workflow/test_imports.py` holds by walking the package
and checking every owner that declares a logger.

`workflow/engine/comments.py` is bound the same way. Its own helpers call each other directly -- both posters stamp the
marker and append to the id ledger in-module, and the thread read applies the per-comment trust filter in-module -- and
the workflow and stage leaves that post a comment, quote one, or read the thread import the owner rather than reaching
for the name on a facade. So a patch that has to intercept a posted issue or PR comment, the tracked-repos block, or
the conversation text a prompt quotes targets `orchestrator.workflow.engine.comments`. The thread read comes in two
spellings for one reason: a caller that derives something else from the same thread -- the discussion stage's
conversation rebuild, which also has to record how far that text read -- passes the snapshot it already holds, because
a second read is a different thread and the two answers would then disagree by whatever landed between them. That
caller is also the one that passes recorded orchestrator ids, which the per-comment filter retains past the allowlist:
a deployment listing its humans and not its bot would otherwise rebuild a conversation with only one side of it in.
Recorded ids and not the body marker, since a marker anyone can paste is a safe reason to DROP a comment and an
allowlist bypass as a reason to keep one.

`workflow/engine/messages.py` is bound the same way. It owns both halves of what an agent's last message is worth:
the strict markers read out of it -- the review and documentation verdicts, the drift `ACK:`, and the operator's
`/orchestrator continue` together with the refusal a guidance-free one earns -- and the stderr block a park comment or
log line carries when there was no usable message at all. Its own parsers call each other in-module, and the workflow
and stage leaves that read a verdict, quote a blockquote, or classify a continue import the owner. So a patch that has
to intercept a verdict parse, an ack read, a continue classification or refusal, or a stderr diagnostic targets
`orchestrator.workflow.engine.messages`. The implementing stage keeps its own
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
`workflow/stages/decomposition/validation.py` so the two cannot disagree, and the plan path the two discussion prompts
promise is handed in by the discussion stage, whose publication check refuses every other path — the same pairing seen
from the other side. It reaches `comments.py` for the thread text,
the tracked-repos block, and the paragraph break its own sections are joined on -- one definition is what keeps a
quoted thread and the prompt built around it breaking the same way -- and `messages.py` for the blockquote; the stage
leaves that build a prompt or append a note import the owner. So a
patch that has to intercept a built prompt, a shared note, or the single-decision comment targets
`orchestrator.workflow.engine.prompts`. A prompt with only one caller stays with that caller:
`engine/drift.py` composes the drift-resume prompt beside the route that sends it and borrows just the two notes from
here, so a patch aimed at that prompt still targets the drift owner.

No flat module sits beside these three owners, or beside the decomposition stage's manifest and validation helpers: a
check in `tests/workflow/test_imports.py` asserts nothing resolves at the flat message module paths, so the posters
and thread read, the marker parsers, the prompt builders, and the manifest decode and child checks are each answered
on their owner alone.

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
`orchestrator.workflow.engine.usage`. The
spawn itself is named on `agents/runner.py`, the owner that defines it, and that call is the seam the stage tests
replace to drive a handler without a CLI, so `patch.object(agents.runner, "run_agent", ...)` is what intercepts it --
a mock left anywhere else would let a real CLI run. Everything after the spawn is fail-open — the record
and trajectory guards live inside
`recording.record_agent_exit`, the skill emission carries its own here — because none of it is worth a run whose
audit pair already fired; an exception out of the spawn is the deliberate exception and propagates.

`workflow/engine/drift.py` is bound the same way. It owns what the orchestrator treats as the human's requirements —
one SHA-256 over the issue title, body, and the comments a human actually wrote — together with the six filters that
keep it from moving on content nobody wrote: the pinned-state comment, the hidden marker every posted comment carries,
the legacy ids from before that marker existed, third-party bots, authors outside `ALLOWED_ISSUE_AUTHORS`, and a bare
`/orchestrator continue`. The routes a real move is handed to sit with the hash because they are the only reason it is
computed: a mid-implementation drift resumes the locked dev session with the updated title, body, and thread quoted
and then advances `last_action_comment_id` past everything it quoted, so the next validating→in_review handoff does
not replay those comments as fresh PR feedback; a pre-implementation drift instead clears the manifest state, names
the children it stops tracking in a notice, and flips the label back to `workflow:decomposing`. It reaches
`comments.py` for the id ledger and the thread text, `messages.py` for the blockquote and the bare-continue test, and
`prompts.py` for the two shared notes, and every stage leaf that hashes, detects, resumes, or reroutes imports the
owner. So a patch that has to intercept a hash, a drift detection, the resume prompt or its watermark bump, or the
decomposition reroute targets `orchestrator.workflow.engine.drift`. No flat module sits beside the package: a check in
`tests/workflow/test_imports.py` asserts nothing resolves at the drift module paths, so the owner is the one import
site the hash, its filters, and the two routes answer on.

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
`orchestrator.workflow.engine.guards`. The base-sync `persistence` owner reaches the park through a call-time import
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
`orchestrator.workflow.engine.pickup`. The stage
handler it dispatches in the same tick is reached through a call-time import of `workflow/stages/decomposition/run.py`
or `workflow/stages/implementing/handler.py` — the stage tree imports this subpackage, so binding either at module scope
would point that edge back at itself — which also makes the stage module the target for a patch that
has to intercept the dispatch. Each start names the owner its handler lives on, so that patch target is the same one
`_STAGE_HANDLER_TARGETS` names.

`workflow/engine/terminals.py` is bound the same way. It owns how an issue stops being worked. Three conditions end
one — the linked PR merged (`done`), the linked PR closed unmerged (`rejected`), and a human closed the issue while
its PR is still open (`rejected` too) — and what they share is the tail rather than the condition: a terminal stamp
(`merged_at` / `closed_without_merge_at`), a terminal label, the cumulative usage receipt, and one
`write_pinned_state`, in that order, so the receipt's comment id rides the state the stamp is written with. Branch
cleanup sits outside that tail on purpose: it runs on the two arcs where the PR is gone and the branch is dead weight,
and is withheld on the open-PR arc — along with its `pr_closed_without_merge` emit — so an operator can still reopen
or salvage what the closed issue left behind. The two entry points differ only in who fetched the PR:
`_drain_review_pr_terminals` takes one the caller already holds (`in_review`, `fixing`, `resolving_conflict`, with
`pr=None` a deliberate no-op so fixing's own fetch failure passes through), while `_finalize_if_pr_merged` and
`_finalize_if_issue_closed` fetch their own at handler entry for `implementing`, `documenting`, `validating`, and the
umbrella / blocked child aggregation — which is why each owns its fetch-failure answer, the merged check leaving the
issue alone and the closed-issue check deferring the tick so a transient failure cannot label a merged-PR issue
`rejected`. `workflow/stages/discussion/terminal.py` takes neither entry point and composes the arcs itself, because
its third condition is not the one above: a closed issue whose plan PR is still open KEEPS its `discussion` label,
since that label is what the closed-issue sweep finds the issue by and the plan the humans are still reading is what
decides. So it reaches `_finalize_merged_pr` (with `close_if_open_only`, the issue may already be closed) and
`_finalize_rejected_pr` directly for the verdict on that pull request, and `_finalize_closed_issue_with_open_pr` with
`pr=None` for a close with no pull request to poll at all — which is the same shape that arc already serves, a close
whose PR is not the thing being decided, and which records as fully as the other two while emitting no event (there is
no PR for the payload to name) and reaping no branch. Its own helpers call each other in-module and reach `usage.py`
for the stamp and the receipt and
`git.worktrees` for the branch name and the cleanup, and every stage leaf that drains or finalizes a terminal imports
the owner, so a patch that has to intercept an arc, a drain, or an entry-time finalize targets
`orchestrator.workflow.engine.terminals`. The issue-state vocabulary the closed-issue arc reads and writes -- the
attribute PyGithub carries it on and its open / closed values -- is named on `github/issues.py`, the owner of the
GitHub wire spelling, which `dispatch.py` reads its own closed-issue probe off too.

`workflow/engine/dispatch.py` is bound the same way. It owns everything between "the repo has open issues" and "one
`_handle_<stage>` is running", and the pieces sit together because each is only safe given the one before it. The
`backlog` / `paused` filter runs twice on purpose — once in `_classify_pollable_issue` so a parked issue never reaches
the partition, and once in `_process_issue` so a directly dispatched one is still refused — and the early drop is not
an optimization: a parked issue carries no workflow label, so leaving it in would fold it into the family bucket, flip
that bucket cap-counted, and reserve the only per-repo slot under the default `parallel_limit=1`. The partition itself
is the concurrency contract: the cross-issue writers (`workflow:decomposing` / `workflow:blocked` /
`workflow:umbrella` and the unlabeled-pickup `None`) collect into one bucket that drains sequentially, everything else
fans out, and a label read that raises is answered `(False, None)` so the unreadable issue lands in the serialized
bucket where `_process_issue`'s own per-issue exception isolation can pick up a sustained failure. Cap exemption is
what keeps that serialization from deadlocking — a bucket whose every label is a no-agent handler
(`_CAP_EXEMPT_FAMILY_LABELS`) and a closed fan-out issue whose handler is a terminal finalize both skip the per-repo
and global caps. Only issue numbers cross a thread boundary; `_refetch_and_process` mints a per-worker client and
refetches against it, because PyGithub's `Issue` and the `Requester` chain behind it are not documented thread-safe.
Its own helpers call each other in-module, and each handler is reached through a call-time import of the module
`_STAGE_HANDLER_TARGETS` pairs with its label — twelve of the thirteen entries name conflicts, decomposition,
discussion, documenting, fixing, implementing, question, validating, and in_review owners under `workflow/stages/`,
and the thirteenth names the `pickup` sibling an unlabeled issue starts on. The import is deferred because the stage
tree imports this subpackage, so binding one at module scope would point that edge back at itself; the lookup stays an
attribute read on whichever module the table names, and every stage is named by the owner its handler lives on. That
makes the owning module the target for a patch that has to intercept a dispatched handler, and this owner the target
for one aimed at the partition, the cap-exemption probe, the timed dispatch, or a scheduler submit. It also owns the
one log line every isolated per-issue failure reports on, which `workflow/engine/tick.py` reads off it so a tick's
three isolation points cannot spell the same failure three ways.

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
mode targets `orchestrator.workflow.engine.tick`. The package API's own `tick` is a thin entry point that resolves
this owner inside the call, and it is what the per-repo `workflow.tick(...)` in `runtime/ticks.py` drives. Both
passes a test has to replace to drive a tick without a git remote or a clone are named on their own owners: the base
refresh on `git/base_sync/refresh.py` and the catalog emission on `orchestrator/skills/catalog.py`, so
`patch.object(refresh, "_refresh_base_and_worktrees", ...)` and
`patch.object(catalog, "_emit_repo_skill_catalog", ...)` are what intercept them.

Stage-private helpers stay private to the stage that owns them (`_bump_in_review_watermarks`,
`_seed_legacy_in_review_watermarks`, `_emit_conflict_round_incremented`). A helper more than one stage reaches for
stays on the owner that defines it, and the borrower names that owner: fixing's quiet window imports
`_comment_created_at` from `in_review/watermarks.py`, so that module is where a patch aimed at it lands.

`orchestrator/__init__.py` is the whole of the package root, and it is metadata: the distribution version and the
explicit `__all__` naming it, bound there rather than resolved on demand. Nothing else sits beside it but the two
launch forms, `cli.py` and `__main__.py`, so an implementation module at the root would be a surface with no
subpackage to name it by -- and `import orchestrator`, which every launch form and every owner import runs first,
costs that one module and no owner behind it. The import-cost checks in `tests/runtime/test_imports.py` and
`tests/apps/test_imports.py` hold that by comparing what a fresh interpreter plants against the root package alone,
and `tests/repository/test_package_metadata.py` pins the published surface to the version.

`orchestrator/runtime/` holds the polling process itself, one owner per thing a run is made of, and
`orchestrator/cli.py` above them is where they are composed. `state.py` is what makes that split possible: the values
the signal handler, the watchdog thread, the per-repo tick workers, and the loop all read and write travel as one
`RuntimeState` the composition creates and passes in, so no owner reads a process-wide module attribute back and two
runs in one interpreter never share one. `logs.py` settles the stderr and rotating-file destinations before the first
client is built; `startup.py` parses the two options, connects one client per configured spec and ensures its labels
once, and builds the single `IssueScheduler` every tick shares; `ticks.py` owns one pass — the per-repo tick, the
fan-out across a `ThreadPoolExecutor` when more than one repo is configured, and the completion reap and analytics
prune that end it; `loop.py` decides whether a run is one pass or many, waits a second at a time so a signal is
honoured inside the interval rather than at the end of it, and guarantees the drain around the body; `self_update.py`
owns the git probes behind the self-restart guard; and `shutdown.py` owns the handler both stop signals are routed
into, the daemon watchdog that bounds the drain, and the forced exit it ends at. `cli.main` creates the state and
hands it to each owner in the order a startup depends on — logging, then the handlers, then the clients, then the
scheduler it publishes on the state before the first tick can hand it work — and returns whichever answer came first,
a restart the loop asked for or the signal that stopped the run. The initializer binds nothing and no owner names the
composition, so a test patches the owner that defines a collaborator and injects the state it wants a run driven on.
Three checks under `tests/runtime/` hold that: the owners on disk are the ones the map above declares, importing one
plants neither the CLI nor an app, and nothing answers at the flat spellings this package replaces — a second copy of
the loop, the signal handling, or the state a live deployment runs on would be free to drift from these owners
silently and invisible to a patch aimed at one.

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
`orchestrator.skills.discovery`, the module that defines them. No flat module sits beside the package: a check under
`tests/skills/` asserts the package root carries none and holds the direction the package runs in — neither owner may
reach the workflow engine, a stage, or an application entrypoint, because a catalog is observation the tick drives
rather than state a handler consults.

`orchestrator/observability/` is the destination for the four surfaces that watch a run without steering it: the
analytics sink and everything downstream of it (`analytics/` over `recording/`, `query/`, `sync/`, and `trajectories/`),
the parser that meters one finished agent run (`usage/`), the Streamlit page over the operator's Postgres target
(`dashboard/`), and the file-backed trajectory viewer beside it (`trajectory_viewer/`, holding that page's read model,
every inline-HTML builder it is drawn with, and the controls and rendering one run of it is driven by). The parser is
the first to
arrive: its owners live under `usage/`, whose initializer publishes the parser surface, while the callers that meter a
run — `agents/models.py`, `workflow/engine/usage.py`, and the analytics recording and trajectory writers — name the
owner they need. No flat module sits beside the package: a check under `tests/observability/usage/` asserts the
package root carries none, so the owner a caller imports is the only site a parse resolves through.

`analytics/config.py` is the first owner under the analytics destination: the six environment knobs the two JSONL
sinks and the Postgres surfaces are configured by, the `off` / `disabled` / `none` disable vocabulary three of them
share, the parse of each, the `Settings` view an adapter reads one back through, and the fallback a read's
`db_url=None` resolves through. Every adapter obtains configuration there — the `settings` holder beside it, both
sinks' appends and the prune beside them, the two skill readers, the two read-path owners under `analytics/query/`,
the sync request, and the trajectory viewer's `log_paths.py`, which is handed a holder by the page that composes it —
so a knob's name appears in one place.

`analytics/settings.py` is where those parsed values are *bound*, and it is the sole settings holder: every knob is
read out of the environment once, at its import, and a caller patches one there. `live_settings` resolves it behind a
function-local import, so nothing on the append path pays for it until a record is actually written — which matters
because this is the one owner under the analytics destination that reaches `orchestrator.config`, for the `LOG_DIR`
the default analytics sink lives under. The `Settings` view reads each attribute on demand, so a knob patched between
two reads reaches the second and a holder carrying only the knobs its caller touches stays usable; `settings_on`
answers for whichever holder a caller hands it, which is how the trajectory viewer resolves its file on the holder its
page passes down.

`analytics/sink.py` is what both write packages share on the way to disk: the `ts` / `repo` / `issue` / `event`
envelope every record satisfies, the encoding and locking one JSONL line reaches disk under, the fail-open answer to a
filesystem that refuses the write, and the `orchestrator.analytics` channel a refusal is reported on. It sits above
`recording/` and `trajectories/` and imports neither, which is what keeps the recording graph free of a back edge: an
`agent_exit` composes the trajectory write, so the trajectory writers reach the envelope and the line here rather than
back through the recorders that called them. Both sinks' locks are minted here for a second reason — an append and the
retention prune that rewrites the file under it are safe only while both hold one lock object, and a caller is free to
take `append_record` (or `append_trajectory_record`) off its owner rather than call through a package. One mint per
process is what keeps every such reference and `retention.py`'s serializing against each other. The two locks stay
separate objects, so neither sink's writers ever block on the other's file.

`analytics/recording/` is the append side of that sink, and the second publishing initializer in the tree: its
`__all__` is the six recorders a producer calls — the `build_record` envelope, the `append_record` beneath it, and one
each for a stage entered, a stage evaluated, a repo's skill catalog scanned, and a tracked agent run finished — bound
once, at import, to the owner's own object. Five come from `events` and the sequenced one from `agent_exit`; the
envelope is the shared `sink` owner's, republished on `events` because that is the import site a producer already
names. The owners under it divide by what a record costs to produce: `events` holds the append that resolves the
analytics knob and the three recorders a producer calls directly, `models` the typed requests and the keyword
signatures a call is bound through, and the four steps a finished run is summarized by are `usage` (tokens and cost),
`skills` (the opt-in evidence), `catalog` (the out-of-band Codex capabilities either falls back to), and `agent_exit`
(the order they compose and write in, plus the recorder that enters it). Every producer names the package —
`github/client.py` for the paired audit / analytics stage-enter hook, `workflow/engine/dispatch.py` for the timed
handler, `workflow/engine/usage.py` for the tracked run, and `skills/catalog.py` for the per-tick catalog.

`events` is the bottom of that graph: it imports `config`, `sink`, and `models`, and none of its siblings. That is what
lets `agent_exit` own the producer-facing `record_agent_exit` and still reach the append through `events` — the family
with a sequence to run before it writes is the one that needs the composition, so it depends on the vocabulary rather
than the reverse. Each recorder dispatches its own `append_record` on `events`, which is what makes
`patch.object(events, "append_record", ...)` intercept an internal append, and every knob is read off the `settings`
holder inside the call, so importing a recorder costs an importer nothing but the recorders.

`analytics/retention.py` is the other side of that pair: the by-age prune both sinks are bounded by. It publishes
three entry points, one caller each — the polling tick's fail-open wrapper, and one prune per sink — over
`retention_scan.py` (the timestamp a record is judged by, and the split of a file into kept lines and a removed count)
and `retention_rewrite.py` (the same-directory temp file, the `os.replace` that swaps it in, and the lock held across
the read and that swap). Each sink brings its own path, its own retention knob, and its own lock, so an operator can
keep the two files for different windows and neither rewrite ever blocks on the other's append; the scan and the
rewrite are shared, so the two cannot disagree about what an expired or malformed record costs. *Which* files a bare
prune rewrites is read off the `settings` holder inside the call, the same way both appends resolve where they land,
so an operator who pruned and an operator who appended cannot disagree about which file the knob names. Every
filesystem touch downgrades `OSError` to a logged no-op, and the wrapper swallows anything else, so a misconfigured
sink costs a warning rather than a tick.

`runtime/ticks.py`'s `run_tick` names that owner directly, and names it inside the call so the tick's own import never
pays for the prune graph. The wrapper it calls dispatches `prune_old_records` on this module rather than the function
object it closed over, so `patch.object(retention, "prune_old_records", ...)` still intercepts.

`analytics/trajectories/` is the opt-in per-run reasoning sink, and its owners divide by what one record passes
through on the way to disk: `models` holds the head/tail and whole-record caps, the snapshot of them one record is
measured against,
and the headline and running budget a record is charged as; `sanitize` the leaf-by-leaf redaction and the head/tail
cut; `serialize` the record's shape and the order the turn and step arrays are drawn from the budget in; `persistence`
the opt-in gate, the parse, the Codex backfill, and the fail-open guard the whole write rides; `api` the bare
`append_trajectory_record` an operator reaches. The direction is the point:
`recording/agent_exit` names `persistence`, never the reverse, and no owner here names the recorders — the envelope
`serialize` builds and the channel `persistence` logs a failure on both come off the shared `sink` owner above both
packages, which is what keeps that composition acyclic. Every knob is read off the `settings` holder inside the call,
so the gate, the append, and the by-age prune all resolve the same `TRAJECTORY_LOG_PATH`. The append's lock is minted
on `sink.py` beside the analytics sink's, and `retention.py`'s trajectory prune takes that same object, so the
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
resolve an omitted `db_url=` through `config.resolve_db_url`, and every caller names the owner that answers it: the
sixteen dashboard read adapters — seven headline and lifecycle, six comparison, three skill — name the query owners
their reads are defined on, and each panel drawn from one of those reads names the model owner the row it is typed
against is defined on, so a row a page unpacks is the class the read family constructed.

`analytics/sync/` is the other Postgres-facing family, and everything a replay does — down to the command that starts
one — now lives there. `columns` owns the inventory both shapes meet on — the four fields a
record must carry, the list the table promotes a column of its own for, and which columns hold JSON — kept in one
place because the required-key guard, the promotion, and the INSERT's parameter order all read it and a row lands in
the wrong column the moment two of them disagree. Anything outside the promoted list goes to the `extras` JSONB
column, so a record written by a newer orchestrator version loses no fields to a database that has no column for them
yet; that blob and the promoted `models` array are the two cells a caller's `json_adapter` is applied to.
`records` owns what one record hashes to, and that encoding is pinned rather than chosen: `sort_keys=True` with
default separators, matching what `analytics/sink.py` wrote the line with, so a record round-trips through file → parse
→ hash without drifting off the key the INSERT deduplicates on. Its parse beside that narrows each required field to
the type its column is declared as — a naive `ts` reads as UTC, the same reading `retention_scan.py` gives it, so a
line from an older writer still lands — and refuses the whole record when any of the four cannot be narrowed, because
a row the table would reject costs more to send than to skip. `rows` owns the line itself: the statement is built
from the same column list in the same order as the tuple that fills it, so the row stays positional with no per-row
dict-to-tuple mapping between them, and every way a line can fail — not JSON, JSON that is not an object, a required
field the table would reject — resolves to a reason string rather than an exception, since one bad line in a rotated
JSONL file must not abort the replay of the thousands after it. A blank line is the one case that is not a failure at
all: it comes back with neither a row nor a reason, which is what keeps it out of the malformed tally the operator
reads. None of the three names psycopg, so a caller
can hash a record or lay a row out on a machine with no driver installed.

Above them, `run` is the service: `sync_jsonl_to_postgres` resolves the source and the destination to the caller's own
values or the two knobs — read live rather than at import, so a replay follows whichever environment the settings were
resolved against — while the connection factory and the JSON adapter fall back to `database`'s defaults instead, which
is what lets a whole run be driven over a connection of its own on a machine with no driver installed. It answers three
configured states with empty counts and a log line rather than a failure, because
the CLI is scheduled by an operator who may not have deployed Postgres yet. What a real run then guarantees is the
transaction shape: a driver error rolls back and propagates so the command exits non-zero rather than reporting
success over a half-inserted batch, the connection is closed either way, and a successful commit is always followed by
the rollup refresh — including on a run that inserted nothing, since rerunning the sync is the documented recovery
path for a rollup an earlier failed refresh left behind. `ingest` owns the two dedup filters and the batching between
them: one scan of the unique `content_hash` index answers for the whole file, a hash queued earlier in that same file
joins the set the lines after it are measured against, and `ON CONFLICT (content_hash) DO NOTHING` stays the
authoritative backstop underneath both because a concurrent writer can land a row after the scan already answered. The
buffer size is read off the module as a pass starts rather than frozen into a default, so a caller that pins a smaller
one is driving the loop that actually runs. `database` keeps psycopg inside the two factories a caller may replace, so
the load path stays driver-free and the ImportError only surfaces on a sync that really dials; the rollback, the
close, and the view refresh around it are each logged and swallowed, because rows already committed must not be turned
into a failed sync by cleanup. `redaction` is what the dialled URL looks like in a log line: credentials collapse to
`***` in both places libpq accepts them while the host, database, and every other parameter survive, so the operator
can still tell which endpoint answered.

`cli` sits on top of `run` as the entry point an operator schedules — the module `python -m` names. It parses the
three arguments, installs the logging the run is watched through, and reports that run twice: as the exit code a cron
or systemd unit branches on, and as the stdout summary that survives a filtered log stream. Both surfaces are pinned
to UTC and say so, because a piped `2>&1` on a host whose local clock is offset would otherwise interleave two clocks
hours apart; the converter is set on that one formatter instance rather than on `logging.Formatter`, whose attribute
is process-wide and would take every other formatter in the process with it. The service is named on the command's own
module rather than bound into the call that drives it, so a substitute installed there is what the command runs —
which is how the operator-facing failure path is covered without a database.

`dashboard/` is the destination for the Streamlit analytics page, and the theme both pages are drawn in is the first
thing to arrive there. It divides by what a value is: `palette.py` holds the chrome and semantic colors plus the seven
maps that pin a dimension value — an event kind, a stage, a cost source, a token type, a backend, an agent role, a
review round — to a hue so it reads the same on every panel; `tokens.py` holds the measurements and the two font
stacks; `layout.py` assembles the Plotly layout every figure is merged with; `css.py` interpolates the stylesheet the
page injects out of both token owners rather than restating a hue or a radius, which is what keeps the chrome and the
charts inside it from drifting apart; and `formatting.py` holds the compact renderings a KPI tile, an axis tick, and a
bar label are too narrow to skip. None of the five imports Plotly or Streamlit, so a caller can read a color at module
load without pulling the optional `dashboard` group into its own import surface.
`theme.py` is the sixth, and it defines nothing: the panel owners take a theme as a parameter rather than importing
one, so a page needs a single object carrying every value they name, and this one reads all five owners back under
one name. The analytics app's `load_dashboard_modules` hands it to the renderers beneath it, getting the style
owners' own objects rather than copies. No
chart module is among its callers: every family reads its hues off the palette owner directly, so a color reaches a
figure without a hop through the composed handle.

The state one run of that page carries sits beside the theme. `windows.py` owns the half-open UTC window every read is
bounded by, the presets that name one, and the clamp that keeps a preset inside the data extent — the label, the day
count, and the arithmetic together, because a preset is only a name for a window the same owner builds. `filters.py`
owns what a run narrows and displays that window by — the display offset, the issue number typed into a free text box,
the stage multiselect's three states, and the key every cached read is stored under — because the key is built from
the other three, and a selection normalized in one module and hashed in another is how two different filter sets end
up sharing a cache entry. `read_mode.py` owns the parallel-read knob, its truthy spellings, the worker cap, and the
text an unconfigured database is refused with, together with the three reads over them — the parse, the flag it binds
at import, and the refusal — so what a page's reads are issued under is settled in one place. The flag and the URL are
read at opposite times on purpose: the flag is parsed once at that module's import, because an operator turns the
fan-out on by restarting the Streamlit process, while the database URL is read inside the call off whichever analytics
package the name resolves to.

`date_controls.py` and `date_filter.py` are where an operator picks that window. The first owns the row the filter bar
is laid out in — five slots rather than a row of equal ones, because each holds a different widget: the label naming
the bar, the preset radio, the two date pickers, and the room the filter line is written into. It also names the three
presets offered inline once, since the options the radio lists and the position the current one reopens at are read
off the same tuple, and a preset offered by one and unknown to the other falls to the last option — which is how a bar
could reopen on `All` after every rerun. `Custom` is deliberately not among the three: it names no window of its own,
so it stays the sidebar fallback rather than a fourth button that resolves to nothing. The second owns the round trip
drawn inside those slots. What the preset resolves to is what the pickers are seeded with, and what they hand back is
the window every read below is bounded by, which is why the two sit in one owner. The dates an operator reads and
types are inclusive — `To` is the last day the window covers — while the reads are bounded `ts < end`, so the end
picker is seeded one day back from the half-open boundary and the pair is handed to the window owner, which puts that
day back. Both pickers are clamped to the recorded extent, because a window reaching past what the database holds is a
panel drawn over days nobody wrote, and a preset that resolves to nothing — `Custom`, or any preset on an extent with
no rows — falls back to the whole extent rather than to an empty bar. The chosen preset is written to the session only
after the bar is drawn, so a rerun reopens the radio on the choice the operator just made; the fifth slot is handed
back as an empty placeholder rather than filled here, because the line restating what the filters narrowed to counts
runs, which the first wave of reads has not answered yet.

`page_controls.py` is the whole band that bar sits in, and the load the choices made there open. Both halves are one
owner because they are one description: the sidebar's selections are normalized into the filters every shape carries,
and those filters are hashed into the pair of cache keys the two waves are bound to, so nothing between the widget an
operator touched and the first read issued can narrow one without narrowing the other. The sidebar and the bar answer
different questions about the same window — which rows it holds, and which days — so the selections come back raw and
are normalized in one place afterwards. Three of those normalizations are the point of it. `All` in the repository box
is the absence of a repository rather than a repository named `All`. The two multiselects are read asymmetrically, and
by column rather than by preference: `event` is `NOT NULL`, so that selection maps straight through and a box still
holding everything narrows nothing, while `stage` is optional and the box offers only the stages actually recorded —
so a stage selection still holding everything collapses to no clause at all, which is what keeps the rows carrying no
stage inside the window a default page reports rather than silently dropping them. Clearing either box is the clause
matching nothing rather than the absence of one, since an operator who unticked every value is asking for exactly
that. The issue box is free text, so `123` and `#123` are one number and anything
else is none. The placeholder the topbar is written into is taken between the sidebar and the bar, because the banner
it holds counts rows the first wave has not answered yet. The display offset is the one selection this owner does not
draw: the card offering it sits at the foot of the page while the read it changes is bound at the top, so it travels
through the session — seeded here on the first render, read back on every one after, and passed beside the cache key
rather than hashed into it, since an offset moves which cell a row is counted into rather than which rows the window
holds. The clock a load is measured against is stamped here too, as the plan is built rather than inside the dispatch
that runs it, which is what leaves the empty-window notice — the one path that skips that dispatch — a reading to
report the load off.

`read_plan.py` is what that state is spent on: the two waves one page load is staged into, the cached task each entry
of a wave is bound as, and the pair of keys those entries are issued under. The split is what lets the page paint
before the load finishes — the first wave is exactly the six reads the chrome above the fold is reduced from, so the
topbar, the KPI strip, and the window banner render while the ten panels beneath them are still being read — and both
registries sit in one owner because moving a read between waves changes what renders early rather than what any one
panel shows. Nothing is issued while a wave is built: an entry is a name and an adapter with its arguments already
bound, since a parallel load runs those callables on worker threads and only the main thread rendering between the
waves may write to the page. Every entry is cached for a minute, because Streamlit reruns the whole script on each
widget interaction and an uncached wave would put all sixteen queries on Postgres per nudge of the filter bar. The
keys are hashed as a pair off one filter set — this window, and the equal-length span before it, measured by the
window owner's own arithmetic — so the two spans the delta pills and the cost-trend banner compare cannot end up
narrowed differently. `fanout.py` then runs one of those waves the way the flag said — on the calling thread, or
across a pool capped at the worker count beside the knob — keying each result by the name it was submitted under and
letting the first read error reach the caller, because a failed load is answered with one banner rather than a
partial page.

`dispatch.py` is what drives both of those waves, and the order a page paints in is the whole of what it decides. The
pair runs inside a single spinner with the first-wave render between them, so an operator watches one indicator over
the load while the chrome that render draws is already on screen. That render is also where a load can end early: a
window holding no rows has nothing for the ten panels to draw, so a render reporting nothing back short-circuits the
second wave and leaves the load unlogged here — `page_states.py`, which drew the banner that ended it, measures it
instead, because what the load spent is the six reads already issued. The first read error the fan-out lets through
becomes one banner
naming what to check and the stop that ends the script, rather than a trace from the window, the tiles, and every
panel below them saying the same thing sixteen times. Every load that does come back emits one `dashboard.load:` INFO
line carrying the wall clock, the read count off the plan, and which way they were issued, because the fan-out is an
operator's switch rather than a setting and a single grep has to be able to A/B the two branches. That line goes out
on the `orchestrator._dashboard_read_dispatch` logger, spelled out literally rather than derived from the module path,
so the name an operator's level and handler selection is keyed on holds still while the module emitting it moves.

`page_pipeline.py` is what fills the gap that staging opens. The banner and the filter line go into the two slots the
controls reserved, the banners a window is worth interrupting a page for go between them, and the four-tile strip goes
under those — all three off the first wave, while the panels beneath are still being read. Its first pass is also the
one branch a load can end on: a window whose first wave reported no event at all has nothing for the panels to draw,
so the chrome is written, the empty-window notice takes over, and reporting nothing back is what the dispatch above
short-circuits the second wave on. That makes the return value a short circuit rather than only a result, which is why
it is `None` rather than an empty strip. Every sibling it draws with is named on the owner that holds it, so a page
and a fix under one of those owners land on the same object.

`chart_sections.py` and `page_sections.py` are the order every panel below that strip is reached in once the second
wave answers. Each panel is its own owner; what these two decide is which comes first, and that order is the page's
argument rather than a layout preference. The five cards a figure is drawn on stack in the first: whether a day's cost
tracked the work behind it, where that cost went across the lifecycle, which issues and backends it went to, whether
the runs it went to held up, and — last, because it is the only card that keeps the clock rather than reducing the
window to a reading — when they ran. The four beneath them are the second: what those runs were working with, the rows
every reading above was reduced from, the trace an operator opens one of those rows into, and the line the page signs
off on. The paired repository-spend and run-health card is the one handed a shape rather than keyword rows, because it
is the only one drawn from four reads at once and a repo list and a throughput series passed positionally are two
arguments nothing would catch swapped. The single call the whole wave is drawn by sits with the second half: splitting
the order across two calls is what lets a caller draw either half against a stand-in, and keeping the pair in one call
is what keeps the page's order readable from one place.

`page_models.py` holds what a render carries between all of that and the panels below it. Streamlit reruns the whole
script on every widget interaction, so a render is one pass with nothing kept between passes, and these seven frozen
shapes are what that pass threads from the controls at the top of the page down to the last table on it. Frozen is the
point: a section is handed the window, the filters, and the reads the sections beside it were handed, so a panel that
could narrow its own copy is a page whose chart and whose table report different windows under one filter line. The
module handles travel as one of those shapes rather than three parameters because nothing under `dashboard/` imports
Streamlit or pandas and every panel takes its theme as a parameter — a render is handed the caller's own, and carrying
them together is what keeps that true through a pipeline several calls deep. The filter shape is the one with
readings derived rather than
stored, and both are decisions rather than conveniences: the issue scope answers nothing until a repository is picked,
because GitHub issue numbers repeat across repositories and a number typed while every repo is selected would open a
drill-down over unrelated runs, and the window span is measured in whole days and floored at one, since it is what
per-day rates are divided by and a window opened and closed on the same date would otherwise divide by zero. The last
of the seven is the odd one out: the paired repository-spend and run-health section is the only one drawn from four
reads at once, so it is handed a shape of its own rather than the positional arguments a repo list and a throughput
series could be swapped between. The
vocabulary those fields are annotated in is imported at runtime rather than for a type checker alone: postponed
evaluation leaves an annotation as text, and `get_type_hints` resolves that text in the globals of the module the
class names.

What that wave is made of arrives with the panels each reader is drawn for. Each is a window a page already decided,
so the whole of an adapter is the query owner's read it names beside the binding that issues it.

`rollups.py` holds the seven a headline or lifecycle section is built from: the window totals every tile is reduced
from, the previous window they are compared against, the daily activity cells, the per-stage table, the newest agent
runs, the cost-ranked issue rows, and the review-round split. Which family answers one follows what it is read off:
four are day-bucketed and `rollup_reads.py`'s, the review-round split is what that bucket threw a column away for and
`breakdown_reads.py`'s, and the run list and the issue rows are scanned off the raw events table under no bucket at
all, so they are `raw_reads.py`'s. Three of the seven carry a decision beyond which read answers them. The run list
stops at the newest hundred, which is what keeps it readable on a long window — and why the reliability tiles above it
are reduced from the window's own totals instead. The spend table is cut to the ranking depth `kpis.py` holds, read at
call time so the rows fetched and the rows drawn cannot become two different numbers. And the previous window is
answered by the KPI-only rollup rather than the full summary, because the delta pills and the cost-trend banner want a
handful of scalars: reusing the heavy shape would put a second whole-window scan on every cold load.

`breakdowns.py` holds the six a comparison section is built from — the backend and repository tallies, the cost-source
coverage, the weekday-by-hour heatmap, the daily throughput, and the daily token split by backend. Which owner answers
one follows the column the read groups by: three are day-bucketed and answered off `rollup_reads.py`, and three need
what the day bucket threw away and are answered off `breakdown_reads.py`. The heatmap is the one adapter with a second
argument: a display offset changes which cell a row is counted into and not which rows the window holds, so it travels
beside the key rather than inside it.

`skills.py` holds the three a skill section is drawn from — the aggregate trigger rates, the per-repository trigger
cells beneath them, and the per-session adoption cells above both. These sit under one owner because one family
answers all three: a skill name, the set a repository offered, and the count one run loaded are recorded in an
`agent_exit` row's `extras`, which the day-bucketed rollup does not carry, so each names `skill_reads.py`. None of the
three carries a filter of its own, so the key is the whole of each signature.

Under that wave, and before it, sit the three owners a page's reads go through. `scoped_reads.py` owns the checkout of
this thread's analytics connection a read is issued inside — the one place a socket is added to a read, which is why
the cached wrappers above it can key on the filter set alone: a `psycopg.Connection` is unhashable, and a stringified
one would make every refreshed socket look like a cache miss. `filter_binding.py` owns the other half of that key —
the positions the filter owner hashed, read back as the keyword vocabulary the query owners are bound by, plus the
windowed read then issued through the scope — so a key packed in one module and unpacked in another cannot leave a
widget reporting a window nobody asked for. `static_metadata.py` owns the two reads no filter narrows: the recorded
extent a preset is anchored and clamped to, and the repo, event, and stage values the filter bar offers. Both take no
argument, which is what makes their cache key empty, and both are cached for five minutes — measured against the
sync's ingest cadence rather than Streamlit's rerun cadence, which fires on every widget interaction. That pair is
also the page's first read, so a failure there is answered rather than reported: the run names the knob to check and
stops, instead of leaving every widget below it to fail on its own.

`insights.py` is what the page opens with, above every panel that wave feeds. It holds the two questions worth
interrupting an operator for and the ratio each is asked at: a window whose agent runs exit non-zero more than a tenth
of the time is describing a broken workload rather than the one the panels plot, and a window whose runs arrive
unpriced that often is one whose spend is an undercount, because the rate tables in `observability/usage/prices.py`
are missing SKUs the parser is seeing. Each threshold sits beside the arithmetic that crosses it, so a page cannot
open on a band nobody else can tune; both spellings an unpriced run reaches the second one under — what the parser
writes when no table covered the SKU, and what a NULL column is bucketed as — are counted together there even though
the coverage bar keeps them apart. Crossing nothing is an empty list rather than a banner saying so, which is what the
caller branches on for a section header that would otherwise sit above nothing.

`kpis.py` sits directly beneath it, holding the four reductions the headline tiles report: how a total moved against
the window before it, how that window's agent runs came out, where its spend went, and how much of that spend was a
second pass. Two of them settle something a caller could otherwise get wrong on its own. The tiles read every count
off the window's own totals rather than the recent-runs read, because a window holding more rows than that read's cap
would report a failure and timeout count stopping at the newest hundred. The rework share names the review-round
buckets that count as a second pass rather than comparing a round number, because the breakdown producing them keeps
rounds 3, 4, and 5 apart and groups only 6 and above. The third is the top-cost ordering, which is total down to the
row -- issues tying on cost fall back to run count and then to the repository and issue number naming them, and an
unpriced issue sorts below every priced one rather than beside the cheapest -- so a table redrawn on the same window
is the same table.

`kpi_series.py` and `kpi_strip.py` are how those reductions reach the page. The series owner holds what a number is
counted over: a token total is the four columns added together -- input, output, cache read, and cache write --
wherever it is taken, because a window totalling all four under a sparkline counting fewer would be a line below its
own headline, and the two shapes it is taken off are read apart only because a window's aggregate spells those columns
`total_*` and a point in the day series does not. The days a line is plotted over are the days the activity series
holds rather than a calendar over the window, with resolved counts looked up against them and defaulting to zero, so a
day that ran agents without resolving anything draws a gap instead of dropping the spend and token points beside it,
and a resolution dated outside those days is not an extra point on the lines. The strip owner is what a page's
first-wave rows then become: the window's own aggregate and the one before it, the day series, the throughput days,
and the review-round split arrive together and leave as four display entries plus the resolved / rejected pair the
reliability tiles are also reported with. Two of those readings are not a division. Cost per resolved issue is an em
dash when nothing was resolved, because a window that resolved nothing has no such cost and printing one is a number
an operator could act on; the rework share falls back to zero the same way when no review round recorded any spend, so
an unpriced window reports no rework rather than failing to draw the tile. The theme is handed in rather than
imported, because the module a page renders through is the one whose formatters and hues a tile has to match.

`sparkline_points.py` and `sparkline_html.py` are how one of those per-day lines reaches the tile above it. The box a
tile has room for is too narrow for an axis, a tick, or a label, so the shape of the line is the whole reading — and
what decides that shape is scaling the window to its own lowest and highest day rather than to zero, since a
fortnight of spend that drifted by a percent would otherwise draw as a flat rule and read as a window nothing
happened in. Two windows have no range to scale against, and they are answered differently. One whose days are all
equal floors its span at an epsilon and settles along the baseline, rather than the projection dividing by zero.
One with no days at all, or one whose days are every zero, is left undrawn: it would sit on that same baseline, so
drawing it would let a window that never rose and a window that reported nothing say the same thing in one stroke.
A day a read answered with a null is counted as a zero first, so a quiet day pulls the window's floor down to zero
instead of dropping out of the line. The rendering owner beside it writes that projection as markup rather than asking
Plotly for it — three figures per page for a shape with no axis, legend, or hover would be the alternative, since
three of the strip's four tiles carry a line — and writes both strings from the one projection, since the polyline the
line is stroked along and the path the tint under it is filled from trace the same days and differ only in the two
points that close the second one along the bottom edge of the box. That edge is the line the window's own lowest day
is drawn on, so the tint sits under the stroke rather than beside it however the window moved; a window with nothing
to draw still renders the empty box at the requested size, so the strip keeps its tiles lined up. The keyword surface
a caller asks for one through — `values`, `color`, `w`, and `h` — is bound as an explicit signature rather than
spelled as parameters, because two of those names are shorter than a parameter may be spelled here and the historical
site still answers a call that names them.

`summary_html.py` is the band that strip sits in: the banner naming what the database holds, the line under the filter
bar restating what a run narrowed it to, the pill one tile's move against the window before it is annotated with, and
the four tiles assembled around them. They are one owner because they are drawn as one band — a tile carries the pill,
and every class name across them is one `css.py` writes rules for, so a pill spelled in one module and the tile
carrying it in another are two places the strip can stop agreeing with the stylesheet painting it. The coloring is a
cost dashboard's: a rise reads red and a drop green, and `invert` is for the readings where up is the good direction —
issues resolved, success rate — swapping the hue only, since the arrow keeps following the value's sign and which way
a tile moved must not be readable off the color alone. A window with no prior to compare against, or one that did not
move, renders no pill at all, because a placeholder in that slot reads as a control that does nothing. What reaches
the markup as caller text is escaped — the banner's span label and spend figure, and each tile's label, value, and
sub-line — because the page writes this with `unsafe_allow_html=True` and a KPI label or an already-formatted amount
is text the dashboard was handed rather than text it owns; the repository, event, day, and run counts beside them,
and the filter line's own dates, are formatted integers and ISO text with nothing in them to escape. The banner and
the filter line take their formatters as
arguments for the same reason the strip takes its whole theme: the module a page renders through is the one whose
formatting a figure has to match, so the same total reads the same way in the banner and in the tile below it. The two
keyword surfaces are bound as explicit signatures rather than spelled as parameters: the pill's is
`value`, which a parameter here may not be named, and the banner's is six readings, more than one call is given to
name, so the banner takes one request object underneath while both still answer the call every caller spells.

`card_html.py` is how the banners and the run-health tiles among those numbers reach the browser, and the header every
panel below them is titled by. Each of the
three is a string handed to `st.markdown(unsafe_allow_html=True)` whose class names are the ones `css.py` writes rules
for, which is why they sit in one owner: a header spelled in one module and a tile in another are two places the
chrome can stop agreeing with the stylesheet painting it. The header's first element is a hidden mark, because that is
what the stylesheet selects a card's container by — Streamlit renders no class of its own to catch. What a card is
told stays with the owner that decided it: a banner arrives as the shape `insights.py` raises, so only the glyph and
the class its severity paints through are settled here and a severity nothing is mapped for falls back to the neutral
one rather than an empty box; a tile arrives already reduced by `kpis.py`, and its number is rendered by the formatter
the caller injects, since the same strip is drawn beside counts and percentages and a value already reading as text
passes through untouched. Every value a caller passes is escaped on the way in — a repo name, a skill, an issue title,
and a severity all reach a card off the sink rather than out of this repository, and the whole surface is markup a
browser is asked to interpret.

`tables.py` is the markup beside it, holding the compact table four panels are listed in rather than the chrome
around them. Those four are inline HTML rather than `st.dataframe` —
the most expensive issues, the aggregate skill-trigger rates, the per-session adoption matrix, and the
invocation-level trigger matrix — because each carries an in-row bar, a status pill, or a sortable header Streamlit's
own table cannot draw, and a panel hand-rolling its own type scale, header row, and hairline rule stops matching the
three beside it the first time a padding is nudged. The class name is interpolated rather than fixed so each panel
scopes its rules to itself, and a caller's extra rules are appended inside the same `<style>` tag the shared ones are
written in, so a panel cannot render styled by half of what it asked for. The four readings a cell is built from sit
here rather than beside the compact formatters because of the last of them: a bar is drawn as a share of the widest
one in its own table, a repository is labelled without the owner hosting it, a missing count reports as zero — and an
amount nobody priced reports as a dash, because a run that cost nothing and a run the parser could not price are
different answers, and a table spelling both `$0.00` would hide the gap the coverage banner is raised for.

`issue_table.py` is the first of those four panels, holding the six columns a window's costliest issues are ranked
into and what one row of them says. Spend is drawn twice — as the amount and as a bar under the repository and issue
number naming the row — and that bar is a share of the widest row in this table rather than of any window-wide figure,
so a window whose issues were all cheap still reads as a ranking rather than as a column of stubs; a window with no
priced run has no widest row to be a share of, so the ranking divides by one and every bar renders empty rather than
the panel raising on a page opened to find out that nothing was priced. Two of its columns are judgements rather than
counts. A review round is drawn in the warn tone from the third one on, because that is where an issue has been
round-tripped past what the flow expects and is worth an operator's eye, and below it the number is plain — which is
what keeps the tone meaning something when it does appear. A row with no failed run reads `clean` rather than a zero,
since the column answers whether the issue needs looking at rather than how many runs it took to get there. The
repository naming a row arrives off the sink, so it is escaped into the markup like every other value a panel here
is handed.

`skill_trigger_table.py` is the second of the four, holding the six columns each `(role, backend)` cohort's skill use
is reported in. A rate is drawn twice there as well — as the percentage and as a bar beside it — and that bar is a
share of the busiest cohort in this table rather than of every run in the window, so a window where every cohort is
quiet still reads as a comparison rather than as a row of stubs; a window where none of them triggered anything has no
busiest cohort to be a share of, so the ranking divides by one and every bar renders empty rather than the panel
raising on a page opened to find out that nothing was tracked. A cohort the sink recorded no role or backend for is
labelled `unknown` rather than left blank, matching the bucket the read groups a NULL under, because a category this
panel drops is one an operator would read as never having run — and the row projections behind the adoption table and
the trigger matrix both read that label off this owner directly, so all three tables bucket a missing category the
same way. Both categories arrive off the sink, so both are
escaped into the markup.

The last two of the four are the ones an operator can reorder, so each arrives split by what a click moves rather than
as one owner. The per-session adoption table is the third, and the page's primary skill metric: it counts by logical
agent session rather than by run, so a session that reached for one skill a dozen times still counts once and a
talkative run cannot outweigh a quiet one. `skill_adoption_columns.py` holds the vocabulary a click is expressed in:
the nine columns, the key each is ordered by — the four naming ones compared case-insensitively — and the `adopt_sort`
/ `adopt_dir` pair a heading writes, prefixed so the trigger matrix below it can carry its own selection in the same
URL without either table reordering the other. Two of its five counts are diagnostics rather than the metric: a skill
some session loaded without reporting it available, and a `SKILL.md` a run only mentioned in passing. They are columns
of their own precisely so neither can be read into the rate beside them, and they are orderable like the rest because
a window's incidental references are a finding an operator sorts to the top. `skill_adoption_sort.py` reads the pair
back with the same tolerance for a stale link the matrix has, and defaults to repository ascending then adoption rate
descending. `skill_adoption_headers.py` draws the row those clicks come from. `skill_adoption_rows.py` says what one
cell is worth, and its job is keeping the two quiet cells apart: a skill no session was offered has no denominator, so
its rate is undefined and reads as an em-dash, while one that was offered and loaded by nobody has a real `0%` — the
offered-but-ignored finding the panel exists to surface. Both are toned down rather than dropped, as is every zero
count beside them. `skill_adoption.py` assembles them, and renders a notice naming the opt-in switch for the one
window with no session evidence at all, since a quiet panel would otherwise read as a bug rather than as tracking
nobody turned on.

The invocation-level trigger matrix is the fourth, split the same five ways. `skill_matrix_columns.py` holds the
vocabulary a click is
expressed in: the seven columns, the key each is ordered by — the four naming ones compared case-insensitively, so a
repository an operator reads as one name does not split into two runs of rows over how the sink capitalized it — and
the `mtx_sort` / `mtx_dir` pair a heading writes, prefixed so the adoption table above it can carry its own selection
in the same URL without either table reordering the other. `skill_matrix_sort.py` reads that pair back and answers
with an order. The parameters are untrusted input, since a sort lives in the URL precisely so it can be shared: a
column the vocabulary no longer offers, or a direction with no column beside it, degrades to the default rather than
raising on a page opened to read a table. That default orders on two keys at once — repository ascending, then trigger
rate descending — so each repository leads with the skills its runs actually reached for, which is why it is a reading
of its own rather than one of the clicked columns. `skill_matrix_headers.py` draws the row those clicks come from,
where each heading is an anchor targeting the current tab, because a sort that opened a second copy of the page would
lose the filters the matrix was narrowed by; the active column offers the reverse of what it is showing and is the
only one drawn with an arrow, while an inactive one offers descending if it counts and ascending if it names.
`skill_matrix_rows.py` says what one cell is worth: an offered-but-never-triggered cohort is the finding the panel
pairs a catalog with triggers for, so its count and derived rate are both toned down rather than dropped while the
cohort's own run total stays plain — that total is the denominator the zero is read against, not part of the finding.
`skill_matrix.py` assembles them, and answers the one window that has no table to draw: with no catalog-backed cell at
all it renders a notice naming the opt-in switch, since a quiet panel on a page opened to find out what ran would
otherwise read as a bug rather than as tracking nobody turned on.

`skill_panel.py` and `skill_trigger_panel.py` are what three of those four tables are reported on. The first holds the
card the page draws: the adoption table leads it, because that is the primary metric, and the aggregate rates and the
trigger matrix fold into a collapsed expander beneath, so a per-run diagnostic cannot be read as the headline. One
notice covers the whole card — a window with no `agent_exit` row has nothing for any of the three to report, so it is
answered once rather than three times. The caption under the adoption table is the reading decided here, and it exists
to keep the page from recommending a switch that is already on: a present row is itself evidence that something was
recorded, so a window whose cells are all zero is captioned as the genuine 0% it is, naming whichever of availability,
loads, or incidental references the window actually carried so an operator can match it against the columns above. A
window with no cells at all is captioned nothing, since the table already renders the notice naming the switch and
saying it twice would read as two separate problems. Whether the window carried adoption evidence is also what the
fold beneath is handed, because the same question is asked one level down: no run triggering a skill is a genuine
no-trigger once tracking is confirmed on, and a prompt to turn it on otherwise.

`skill_trigger_panel.py` is the card that led the skill section before the adoption one did. Nothing in the render
pipeline reaches it now; it stays whole — header, notice, aggregate rates, and the matrix folded under them — for a
caller that names it, and its enable-tracking prompt is unconditional where the adoption card's is not, since a window
of trigger rates carries no per-session evidence to tell a genuine no-trigger apart from tracking nobody turned on.
Both owners are handed their `st` rather than reaching for one, so neither names Streamlit. Besides the row models
each is typed against, the first reaches the card header, all three of those tables, and both sort parses; the second
reaches the header, the two tables it draws, and the matrix parse alone.

`recent_runs.py` is the listing under those four tables rather than a fifth panel among them. Every panel above it
reduces a window to a reading, so this is where an operator lands once one of those readings raises a question the
aggregate cannot answer: which run, on which issue, at what cost. That is also why it is the one panel drawn as
`st.dataframe`
rather than hand-rolled markup — it carries no in-row bar, status pill, or sortable heading of its own, and
Streamlit's own table already sorts, widens, and scrolls a raw listing. It opens collapsed, because a listing as long
as the read's cap allows would push the per-issue drill-down below it off the screen the page ends on, and a window
with no `agent_exit` row renders the notice instead of an empty frame, so the expander says why it holds nothing
rather than showing a header with no rows under it. The timestamp is the one reading converted here: every panel above
this one reports over a window rather than at an instant, so this is the only place a stored UTC instant is read back
as a wall clock — and the clock is the offset the sidebar picked rather than the server's, since the operator asking
which run this was is reading against their own day. The columns are ordered the way that question is asked: when and
where, then what ran, then how it went, then what it cost. Streamlit and pandas are the caller's, handed in as
parameters, so the row projection stays readable with neither installed.

`drilldown.py` is the last narrowing on the page, under that listing: one issue's events in the order they happened,
which is where an operator lands once a run in the listing raised a question the row cannot answer — what ran before
it, how long each step took, and where the cost went. It is the one page read issued outside the cached wrappers,
because it is scoped by an issue on top of the window and filter set those keys are hashed from; it still goes through
the scope owner, so it runs on the socket the waves above it opened rather than dialing one of its own. A repository
has to be picked before a number narrows anything — GitHub issue numbers repeat across repositories, so a trace opened
while every repo is selected would interleave runs sharing nothing but a number — and the section names the control
that answers it instead. The subheading is written before that check, so a number typed too early still says which
issue the notice is about. The other two answers are the empty window, which names the repository, issue, and filters
it found nothing under rather than drawing an empty frame, and the failed read, which banners itself and returns:
every panel above this one already rendered, so a trace that cannot reach the database is not a reason to stop the
page. Streamlit and pandas are the caller's here too.

`drilldown_request.py` is the call shape that section is still reachable under. The render pipeline threads the frozen
shapes the page-state owner holds, but the drill-down predates them, and a caller outside that pipeline names the
seven keyword arguments it was written with. Both spellings meet here, so the section itself is written against the
state every panel beside it is handed and nothing on the page carries the older vocabulary. Those keywords are bound
through a declared signature that is also what the adapter reports, which keeps the historical shape one thing rather
than three descriptions of the same call — and binding is what makes it strict, so an unknown or missing keyword
raises here instead of reaching the render as a half-filled request. The theme handle is the one a
drill-down has no use for, so it is handed the modules shape with that slot left unanswered rather than a shape of its
own.

`page_states.py` is what is drawn where none of those panels can be. Two of its three renders are dead ends, and they
are dead ends of different kinds. A database nobody has ingested into has no extent to pick a window from, so there
is nothing below the banner to render: it draws that banner with every count it carries zeroed, names the sync command
that fills the table, and stops the script where it stands rather than falling through to a filter bar with no dates
to offer. A window that merely matched nothing still has a page around it, so that one keeps the chrome already
rendered above it, says which way to broaden, and hands the page on to the trace at the foot of it — an operator
narrowing to one issue is exactly who lands on an empty window, and that trace is scoped by the issue on top of the
window rather than by the cache key the reads it skipped share, so it can still have something to show. Emitting the
load line is the other half of that hand-off: the dispatch owner times a load off the line `run_read_waves` ends on,
and a window short-circuiting the second wave never reaches it, so the notice that ended the load reports it instead —
off the plan's own clock and the first wave alone, rather than the full inventory nobody paid for. The third render is
the footer beneath a page that did draw, restating the window and the run count everything above it was measured over;
it closes on the day before the window's end, since the reads beneath the page are issued under `ts < end` and
restating `end` itself would name a day none of those numbers covered. Streamlit and the theme are the caller's here
too, so the markup this owner assembles stays readable without either.

`usage_panel.py` is the card above every one of those panels, the first one under the KPI strip, so it answers the
question the page is opened with: whether a day's cost tracks the work behind it. The figure carrying both readings is
the usage chart family's; what this owner decides is the card around it — the header naming it, the one control an
operator has over it, and the rows the chart is handed for the mode they picked. That control is a two-value radio
rather than a checkbox because neither stack is the drilldown of the other: by token type is what a day's tokens went
on, by backend is who spent them, and an operator switches between the two readings rather than opening one out of the
other. Streamlit reruns the whole script on every interaction, so the picked mode is kept in the page's own session
state and the radio is seeded from it by index — the widget takes an option's position rather than its value, and a
mode read back any other way would snap the hero card to the default stack every time a filter beside it moved. The
per-backend rows are totalled here rather than read that way, since the same `(day, backend)` cell can arrive more
than once and a stack drawn off the raw rows would show the last of them instead of the day; they are totalled only
when the backend stack is the one being drawn, because the token-type bands already ride on the time-series points.
The header, the figure builder, and the Plotly defaults all come off their owners directly, so what this card is
titled by, drawn as, and configured with are the objects every panel beside it uses. Streamlit is the caller's, handed
in as a parameter, and the figure builder reaches Plotly inside its own call, so importing this owner costs neither.

`backend_card.py` and `coverage_card.py` hold two more panels drawn as markup rather than as a figure, each with the
arithmetic behind its own. The first answers what work on one backend is worth, in three readings an
operator compares agents by: what a million tokens cost, what a run cost, and how much of the billable input the cache
answered. All three are ratios a thin window can leave dividing by zero, so all three go through one guard that
answers nothing rather than raising — a backend with no runs yet is a card reading zero, not a page that stopped.
What counts as a token there is the whole billed band, input through cache write, because that is what the spend
printed beside it was charged for; cache leverage is deliberately the narrower reading of the same row, cache reads
over the input they stood in for, since the question is what share of *billable* input the cache answered rather than
what share of every token it touched. The second answers whether the money everywhere else on the page can be trusted:
one segment per `cost_source`, sized by token share whenever the window carries any and by run share only when it does
not, because a handful of high-token runs can dominate spend while looking like a thin slice of the run count. A
window with neither divides by one, so an empty bar renders flat rather than raising on a page opened to find out that
the window is empty. Each segment is built as both strings it appears in at once — the slice and its legend line —
because the two carry the same hue and the same percentage, and computing them apart is where a legend could start
naming a width the bar above it does not have. Both owners take the theme as a parameter, the way every card builder
here is handed one: a page resolves a single theme object and passes it down, so a card is tinted and set from what
the chrome and charts around it were.

`stage_cost_panel.py` and `issue_cost_panel.py` are the first two of the three sections a window's spend is compared
across, and each is
a pair of columns rather than a panel: the money is only readable as an answer once two cuts of it sit beside each
other. The first pairs the two lifecycle axes — which stage of an issue's life the spend landed in, and which review
cycle it landed in — and pins both figures to one height, taken off whichever of the two reads came back with more
buckets. That is the decision the pairing exists for: a horizontal bar family sizes itself by its own row count, so
two panels left to size themselves stand at different heights the moment one axis is longer, and an operator
comparing spend across the gutter would be comparing bars of two different thicknesses. The columns are split 7:5
rather than evenly because the stage axis carries the wider vocabulary — a full stage name needs room a round bucket,
which is a digit or `6+`, does not.

The second pairs the work with the agent that did it: the window's costliest issues ranked on the left, one
efficiency card per backend on the right, so an expensive issue and whether the backend behind it is expensive per
run or merely busy are one glance apart. The coverage bar closes that right column rather than standing on its own,
because it is the qualification on the money the cards above it report — what share of the window's spend the parser
could price at all — and it is drawn only where the window carries that split, since a bar with nothing to divide
would claim a reading no row supports. The two columns render different empty states for the same reason they are
paired: a window can carry runs the parser could not price, so the ranking says no run in it had a recorded cost,
while the cards beside it are drawn from `agent_exit` rows directly and their absence is the window having no run to
report. Streamlit and the theme are the caller's, handed in as parameters, so neither owner names either. Everything
each section is assembled out of it names itself: the header above a column, the ranking, table, card, and bar inside
one, and — for the bars — the two figure builders in `charts/cost_stage.py` and `charts/cost_review.py`, since a
panel is the card and the figure together and a builder handed down would let a pairing whose whole point is one
shared height be drawn by two families that measure it differently. The Plotly configuration is the exception both
reach for at call time rather than bind, off the owner below.

`reliability_panel.py` is the third pair beneath them, split the same way and paired for the same kind of reason: the
narrow column qualifies the wide one. A repository leading the window's spend reads differently once the runs that
spend came from are known to have failed or timed out, so the ranking sits beside the six run-health tiles and the
per-day strip of the issues those runs resolved. That strip is handed the window's own bounds, since the read behind
it returns only the days something resolved on and a strip drawn straight off the rows would run three busy days
together and read as a week of steady output. The closing bound is the day *before* the window ends: every read
beneath the page is issued under `ts < end`, so the last day an operator asked for is the one before that end, and
drawing through `end` itself would add a trailing empty day no read covered. What the section is handed is the page
state rather than the rows — it is the only panel typed against the shape a load assembles for it — and what it draws
with it names itself: the header, the tile reduction, the markup that strip is written as, and the two figure
builders in `charts/cost_repo.py` and `charts/throughput.py`. Its two figures take the Plotly configuration the same
way the bars above them do — read off the owner below at call time rather than bound here — so a page whose toolbar
decision changed does not leave this pair drawn under the one it was imported with.

`activity_panel.py` closes that run, and is the one section that keeps the clock rather than reducing the window to a
reading: the same tokens laid out by the hour and weekday they landed on, so a window that reads as steady spend can
still show itself as two overnight bursts. An hour only means something in a zone, which is why the page's one
control over that zone sits inside this card instead of in the sidebar beside the filters — it is the only selection
that changes what a figure means rather than which rows reach it. Nothing here shifts a timestamp: the cells arrive
already bucketed, because the read behind them was issued under the offset the page picked up from the same session
key this selectbox writes. The zone named in the header and on the x-axis is therefore true only while the widget and
that read name one key, and the offset is formatted once so the two cannot disagree over one set of cells. The help
text says the same offset moves the run listing's `ts` column, since that is the one selection two panels share. The
header, the grid in `charts/heatmap.py`, and the Plotly configuration read off the owner below at call time are all
this owner's own, the way the three pairs above it name theirs.

`render_config.py` holds the one thing every figure below is handed alongside itself: the Plotly configuration the
page draws each of them under. It is one mapping rather than a keyword spelled at each `st.plotly_chart`, because a
hover toolbar switched off in every panel but one is chrome over exactly the card nobody remembered. What it switches
off is that toolbar — camera, zoom, pan, autoscale — since this page is read rather than driven: every figure is
already scoped to the window the filter bar picked, and a stray drag inside one leaves a card zoomed into a range no
filter names and no control undoes short of a rerun. It is published as a read-only proxy because every call site
shares it, and each hands Plotly a plain-dict copy — the proxy is not JSON-serializable, and copying is what keeps one
panel's configuration from becoming the next panel's. Configuration is data, so the owner names neither Plotly nor
Streamlit and a caller that needs only the switch pays for nothing else under the package.

`charts/` is where what those reads answer becomes a figure, and `primitives.py` is the first owner in it: the pieces
every family is drawn out of rather than a family of its own. The no-data placeholder is the sharpest of them. Plotly
answers an empty series with a blank canvas rather than an error, so a card that read nothing and a card that failed
to load would look alike; every builder routes that branch through the one placeholder instead, carrying the height
the non-empty panel was pinned to so an empty card cannot stand half again as tall as the ones beside it. The labels
are the same argument at a smaller scale: a bar's amount comes off the formatter a KPI tile is rendered by, its text
is set in the mono stack so a column of amounts lines up on the decimal point, and a tick is the label with its
subtitle beneath it in the muted tint. The horizontal-bar helpers settle the shape those families share — one row
height per bar over the fixed margin and axis base underneath unless the caller pinned a height, and the legend above
the plot at the left edge — because a family sizing itself drifts from the ones beside it the first time a row is
added. The owner names the theme owners it draws with and nothing else, so the dependency under the families runs one
way and a direct import of any single chart module stays cycle-free. Plotly is reached inside the one call that builds
a figure, which is what keeps importing anything under `dashboard/` free of the optional dependency group.

`cost_layout.py` sits above it with the frame three families share — the generic ranking, the per-stage split, and the
per-review-round split all draw dollars along a horizontal axis, and they read as one page only while the gutter their
labels sit in, the `USD` axis under a `$` tick prefix, and the height they grow by are decided once. The bar itself
arrives as a frozen request rather than a pile of keyword arguments, because what differs between those families is
which halves are present: a side-by-side split names an offsetgroup so its bars share a y bucket, and only the outer
trace of a stack carries the total, so an amount is labelled once per bar instead of once per segment.

`cost_horizontal.py` is the first family on that frame and the one the per-repository adapter draws through. Rows of
label, subtitle, cost, and color become one bar each, ranked by spend unless the caller has already ordered them, and
the whole series is flipped on the way out because a Plotly bar axis draws the first row at the bottom — all four
columns together, or a label would part company with the amount beside it. A row naming no color falls back to the
caller's accent and then the page's, so a ranking is one hue rather than a striped chart. The builder takes
`*args` / `**kwargs` and binds them through a pinned `Signature`, which is what keeps `items` the name the rows may be
passed by and keeps `inspect.signature` reporting that call shape rather than the pair the body receives.

`cost_stage.py` is the family beside it on that same frame, cutting each stage's bar in two: what the model was billed
at full price, and what it was billed at the cache rate. The halves are stacked rather than drawn side by side, so a
bar's length is still the stage's whole spend and the split inside it reads as the share the cache paid for, and only
the outer half carries the dollar text. Both halves are tinted from the stage's one hue — the cache half a translucent
shade of it — because a palette of its own for the cache segments would read as twice as many stages; that shading is
where the per-review-round split gets its own cache tint too, which is why it lives here rather than inside the
stacking. A row carrying neither half but a total is a window read before the split existed, and plotting it straight
would draw an empty bar for spend that happened, so the whole total becomes the full-price half. The sub-line counts
`runs` — the agent-exit subset of `StageBreakdown.count` — because those exits are what reported the spend the bar
is drawn from. The one value this family takes from the one beside it is the height an empty cost panel comes to, so
a split with nothing to draw is the same size card as a ranking with nothing to rank. Like the per-repository adapter
below, it is handed rows rather than the ranking's tuples, so besides the theme owners it draws with and that one
height, the only thing it names outside the package is `analytics/query/run_models.py`, the row a stage's halves
arrive on.

`cost_repo.py` sits directly on top of the ranking, an adapter rather than a figure of its own: a per-repository row
becomes a label, a subtitle, an amount, and a tint, and the order, flip, and frame are the ranking's. What it decides
is how a repository reads. The label drops the `owner/` prefix, which is the same across every bar an operator is
comparing and would spend the gutter the amounts have to fit beside — the full slug stays on the row. The subtitle
counts agent runs rather than events, because the amount beside it is what those runs came to and the cheap stage rows
would overstate a quiet repository. Every bar takes the page's accent, since a repository is not a category the page
tints by and a striped ranking would suggest a distinction the rows do not carry. A window matching no repository
routes through the shared placeholder at the ranking's own empty height and says so in its own words, so an operator
who filtered the repositories away is told that rather than that no data exists. Besides the ranking and the theme
owners beneath it, the only thing it names outside the package is `analytics/query/cost_models.py`, the row those bars
arrive as.

`cost_review.py` is the last family on that frame, cutting a round's spend the way the per-stage split cuts a stage's
but twice over: a row carries a development bar and a review bar side by side, in offset groups of their own so they
share the row rather than stacking into each other, and each is split into its full-price and cache halves within its
own bar. Only the outer half carries the dollar text, and the legend is read back to front so its entries fall in the
order the bars are drawn. Rows are ordered by the round rather than ranked by spend, because a round number is an
ordinal and what the panel is read for is the shape of the rework curve; a bucket the window holds no rows for drops
out instead of drawing an empty row, and the runs carrying no round at all come last under a label of their own. The
sub-line counts the two roles' runs separately, because the bars beside it are drawn from two different populations.
It takes two values from the families beside it — the empty-panel height from the ranking, and the cache shading from
the per-stage split, so a cache segment reads the same on both — and gives its rows more of the panel than the shared
row height allows, since two bars share a row here. A window with nothing to draw answers in two ways rather than one:
no rows at all is a filter that matched no agent exits, while rows carrying neither development nor review runs is a
window whose spend was all something else, and an operator told "no data" for the second would go looking for a broken
query. Besides those two values and the theme owners it draws with, the only thing it names outside the package is
`analytics/query/cost_models.py`, the row a round's four halves arrive on.

`heatmap.py` is the next family here, drawn straight off the shared pieces rather than that frame: the 7x24 grid a
window's activity rhythm is read off, a row
per weekday and a column per hour. What fills a cell is token volume rather than event count, because counting events
would weigh the cheap `stage_enter` and `stage_evaluation` rows the same as the agent exits that drive spend and the
busiest-looking hours would be the ones that cost nothing — the per-cell count stays on the row for a caller that wants
it. The rows are drawn in the weekday numbering the read arrives under, Sunday first, so a point's weekday indexes its
row directly rather than through a re-mapping that could shift every cell an operator reads off the axis. A point
naming a cell the grid does not have is dropped rather than raised on, since one out-of-range weekday is not worth a
page that fails to load. The empty window is the one place this family answers differently from the shared placeholder:
the grid is still drawn and the "nothing matches" sentence is annotated over it, because an empty heatmap is a legible
result where an empty bar series is not. Nothing here shifts a timestamp — the hour axis is annotated with the zone the
caller says the cells were read under — so besides the theme owners it draws with, the only thing it names outside the
package is `analytics/query/activity_models.py`, the row those cells arrive as.

`throughput.py` sits beside it: the per-day strip a window's resolved-issue rhythm is read off, one bar as tall as the
issues that reached a resolved stage that day. The read only returns days that carried such a row at all, so a strip
drawn straight off the rows would run three busy days together and read as a week of steady output. Given the window's
inclusive bounds the days between them are the days drawn, and the ones no row named are drawn at zero, because a
continuous baseline is what makes a quiet day legible as a quiet day instead of as an interval the axis skipped —
without both bounds the rows are the calendar, so a caller with no window to hand still gets a strip. That makes the
shared placeholder reachable only in the second case: a bounded window always has days, and a range nothing resolved
in is an all-zero baseline rather than a sentence. Either way the pinned height travels with the figure, since the
panel shares the narrow reliability column with the tiles above it. Unlike the grid beside it this family does route
its empty state through `primitives.py`, and like it the only thing it names outside the package besides the theme
owners is `analytics/query/activity_models.py`, the row those counts arrive as.

`usage_bands.py` and `usage_series.py` are the next to arrive, holding the shaping the usage family does before any
figure is built. The series arrives one row per `(day, event)`, so several rows land on the same date and the two
cache counters are two columns of one band; the roll-up in `usage_bands.py` is the single place those rows become a
day, summing
cache read and cache write into the one Cache band the legend names and counting an aggregate the query left NULL as
zero rather than failing the page's load. The band names live with it because the same four keys are the
accumulator's slots, the stack's trace order, and the input to the axis maximum — a second spelling of "cache" would
accumulate into a band no trace reads — and its daily total is tokens only, because cost rides the secondary axis
under a range of its own. `usage_series.py` is the layer above: the day span a figure is drawn along, the two frozen
shapes that span and the axis maxima travel in, the completion that gives a day only the per-backend read saw a
zeroed bucket so its stack lands on its own date rather than past the end of the axis, and the height each mode
measures a stack by — a per-backend stack as tall as that day's backends add up to, a token-type stack as tall as its
three bands. Backends come back sorted because their order is the legend's order and the color each is drawn in is
picked off its position among them. Like the grid beside it, `usage_bands.py` names one thing outside the package —
`analytics/query/overview_models.py`, the row a series arrives as — and the dependency between these two runs one
way, from the series owner down to the bands it counts.

`usage_axis.py` and `usage_traces.py` sit above that pair. Tokens and dollars are orders of
magnitude apart, so the stack keeps the left axis and the cost line rides a secondary one on the right; `usage_axis.py`
cuts both into the same number of steps from zero, which is what lets a single horizontal rule mean something on
either scale. The step an axis would otherwise take is raised to 1, 2, 2.5, 5, or 10 times the decade beneath it and
the maximum is that step times the count, so an axis is labelled in the numbers an operator reads off a ruler, and a
window with nothing in it is still given a span — a range of `[0, 0]` draws no gridlines to read the empty state
against. The mode travels this far down because the token axis is scaled to the stack that is actually drawn:
measuring the bands under a per-backend stack would leave the tallest band drawn past the top of its own axis. Only
the token axis draws the rules, because two grids over one plot would cross wherever the two roundings disagree.
`usage_traces.py` is what is drawn against them: the shaping that answers a window holding nothing with no chart at
all — the caller then draws the shared placeholder — the band a stack is added one of at a time, the two modes it is
stacked in, and the cost line overlaid on the secondary axis as a line with markers rather than another layer of the
stack. A backend's color is picked off its position among the sorted backends and a token band takes the fixed hue its
name is spelled in, both from the palette owner; besides that and the two owners beneath it, `usage_traces.py` names
`analytics/query/overview_models.py` for the row a series arrives as, and `usage_axis.py` names nothing outside the
package but the layout and palette every figure is drawn with.
Of the two, only the traces owner names Plotly, and only inside the two calls that add a trace; the axis owner hands
back a plain dict the way the layout owner it merges does — so both import in the default install, and an axis maximum
and the two ranges over it are checked there rather than only where the optional group is present.

`usage.py` finishes the family: the hero figure those four are assembled into, and the only one of the five a panel
ever calls — the four beneath it are reached through it. The window is shaped first, the stack is added in the mode
the page asked for, the cost line is
overlaid on the secondary axis, and the layout is merged last — after the traces, because the token axis is scaled to
the stack that was actually drawn. A window nothing came back for never becomes a figure at all: the shaping answers
with nothing to draw, and the shared placeholder is returned in its place at the same pinned height, so an empty hero
panel keeps the slot the drawn one would have taken. The `backend_per_day` stub is published beside it and answers
with an empty mapping; no panel calls it, since the per-backend stack takes its rows through `usage_over_time`'s own
parameter. Besides the four owners beneath it and the placeholder above them, this owner names the two read models its
signatures are typed against — `analytics/query/overview_models.py` for the series a figure is built from and
`analytics/query/cost_models.py` for the rows the stub is handed — and Plotly, inside the one call that builds the
figure. That is what leaves the whole usage path clear of the optional group: none of these five owners names Plotly
at module scope, and neither
does the `usage_panel.py` card that names this owner directly — which is the route the page itself takes — so every
surface the hero figure is reached through imports in the default install. Nothing on the cost, heatmap, or
throughput paths names it at load either — nor do the `stage_cost_panel.py`,
`reliability_panel.py`, and `activity_panel.py` cards that name five of those owners directly, the way the hero card
names the usage one.

The window owner names `analytics/query/overview_models.py` for the extent a preset anchors at, the read-mode owner
names `analytics/config.py` for the URL it refuses without, the scope owner names the connection cache it checks a
socket out of, the metadata owner, the dispatch owner, and the drill-down owner all name the error a failed read
arrives as — the first alongside the two unfiltered reads it issues — the rollup owner names the three read families
its seven adapters are
answered by plus the issue-summary owner
that spells the cost-first ordering one of them asks for, the breakdown owner names the two families its six adapters
are answered by, the skill owner names the one family its three are, and the insight, the KPI, and the two KPI-strip
owners name the result families the window totals, cost-source split, and issue rows they read arrive as -- the last
two of those for the pair of windows a strip reduces rather than the one a tile reports -- while the two card owners
name the family the per-backend and per-cost-source rows they weigh and size arrive as, and the four panels listed in
the compact table name the families the issue rows one ranks, the cohort rows the second reports, and the adoption
cells the third and the matrix cells the fourth are read across arrive as — four of each sortable panel's five owners
name
`analytics/query/skill_models.py` for that cell, since the column vocabulary is typed by what it orders, the parse and
the panel by what they hand back, and the row projection by what it reduces, while the header row is typed by the
column set alone and so names nothing outside — and the two cards those panels are reported on name it as well, for
the cohort rows and matrix cells both are handed and the adoption cells only the first is, while the run listing
beneath those cards names `analytics/query/run_models.py` for the `agent_exit` rows it projects — as does the trace
under that listing, for the traced-event rows it reads, beside the raw family answering the one per-issue read it is
the only page caller of — the two
cost-comparison sections name `analytics/query/cost_models.py` and `analytics/query/run_models.py` between them — the
paired bars for the stage and review-round rows they are drawn from, the ranking beside them for the issue rows it
cuts and the per-backend and per-cost-source rows the cards and the bar in its other column are — the activity grid
that closes those sections names `analytics/query/activity_models.py` for the weekday-by-hour points it draws, the
hero card above
all of them names that same owner for the per-backend daily rows it totals and
`analytics/query/overview_models.py` for the series it hands its figure, the page-state
owner names `analytics/query/overview_models.py` without issuing a read of its own, for the extent a page opened on
and the window totals a comparison panel reports, and the owner drawing the chrome between the two waves names that
same one and `analytics/query/cost_models.py` for the same reason — the window aggregate its banner, filter line, and
strip are all reduced from, and the cost-source rows one of its banners is raised over; those
are the only things
any of the fifty-four reaches outside the package. The fan-out, the read plan, and the filter binding reach nothing
past the siblings they take their worker cap, their adapters, and their scope from — as do the two the filter bar is
drawn out of, which take the presets they offer and the window they resolve from that window owner and each other, and
are handed Streamlit rather than importing it, and the owner above those two, which names no result family at all
because what a run is narrowed by is decided out of the selections an operator made rather than out of anything read
back, and takes the bar it draws, the normalization those selections go through, the knob and the plan its load is
staged by, and the shapes all of it is threaded on as off six siblings, and the two ordering the panels below, which
name no result family either since every row they hand on arrived with the load, so their whole reach is the panels
themselves and the shapes those are typed against — the table markup reaches not one of
those — every value a cell reports is handed to it — the sparkline projection and the Plotly configuration reach
nothing at all, the markup
over the projection only that projection, the chrome around the strip only that markup — for the line a tile carries
— the card
markup names only the insight
owner whose banner shape it renders, the rollup owner names one sibling of
its own beside those query families -- the KPI owner whose ranking depth its spend table is cut to -- and the strip
owner names two: the series owner whose lines it draws under three of its tiles, and that same KPI owner, for the
delta a tile is annotated with and the rework share one of them reports. Four panels reach a sibling a directory down
for the figure inside them: the hero card names `charts/usage.py`, the paired lifecycle bars name
`charts/cost_stage.py` and `charts/cost_review.py`, the repository ranking beside the run-health tiles names
`charts/cost_repo.py` and `charts/throughput.py`, and the activity grid beneath them names `charts/heatmap.py` — each
beside the card markup it is headed by and the Plotly
configuration it hands that figure, so a panel is the card and the figure together rather than two halves a caller
pairs up, and none is titled, drawn, or configured out of a different owner than the panels beside it use. That is
every figure the page draws: no section is handed a chart handle as a parameter and calls a builder off it, which is
why the shape a render is threaded on carries none — the caller's Streamlit, pandas, and theme travel on it, and the
figures are the owners' own.

`trajectory_viewer/` is the fourth destination, and it holds the whole of the file-backed page: the
read model — which file it opens, how a line in it is read, what that line is read back as, what a run then reports,
and what a page narrows and totals those runs into — the inline HTML that read is drawn as: the stylesheet, the
banner and tiles a whole read is summarized in, the three renderings one run is identified by, what it cost, and the
header each timeline entry is read by — and what drives one run of the page over both: the state it carries, the setup
it opens with, the controls it is narrowed by, the cascade one run is picked through, and the card that run is read in.
`constants` is the vocabulary — the one event this viewer reads, the two brackets a run's prompt and final output are
rendered as (the sink writes neither as a step, so there is nothing on the write side for them to agree with), the three
tells that mark a fixture, and the banner an operator gets when the sink was never switched on. `coercion` is the
narrowing under every field: the JSONL is append-only and was written by whichever version was running at the time, so a
missing field, a number spelled as a string, or a scalar where an array belongs each yields the declared type's empty
value rather than an exception — and a `bool` is refused ahead of `int`, because it is one in Python and a `true` where
a token count belongs is a corrupt record. `models` holds the four frozen views a record is read back as, and their
bodies are why two of them declare a constructor signature instead of taking the generated one: a dataclass cannot hold
a field and a property of the same name, so the field is named apart while the keyword a caller passes and the attribute
it reads back stay `content` — the spelling the sink writes — and binding the call against that declared signature is
what keeps positional construction, keyword construction, and `inspect.signature` all reporting the one public shape.

`runs` is the record those pieces compose into, and it deliberately defines no view of its own: `usage_views` and
`timeline_views` do, bound on as properties so a caller reads `run.timeline` and `run.cost_usd` rather than calling a
helper with the run in hand. `usage_views` answers off the summary the sink already wrote rather than re-adding the
turns — that summary is the figure a provider reported, and the per-turn rows are a claude-only detail a codex record
does not carry at all — so a record written before the usage feature degrades to zero tokens, no model, and an unpriced
cost instead of raising; only the per-turn lookup reads the turns, and it goes through the record's cached index so a
page walking a timeline does not rescan the tuple per entry. `timeline_views` owns the one ordered sequence two record
vintages both render as, the cohort label a run is picked by and the issue-prefixed label above it, and the fixture
tells — where a stepless record is judged on the prompt and session tells alone, because "every step is a `Skill` call"
is vacuously true of no steps and would hide a real run from an operator who turned the toggle on. Both view owners
name the record only under `TYPE_CHECKING`, which is what keeps the dependency one-way: the record imports them, and
importing any owner here costs nothing outside the package, the analytics settings holder included.

`parsing` is what turns a decoded line into one of those records, and it sits above the whole package: it names the
coercion, the vocabulary, the views, and the record, and nothing here names it back. Two decisions are made there and
nowhere else. An object is a run only when it carries this viewer's own event, so an audit line sharing a file is
dismissed rather than rendered as a run with every field empty. And the position the caller counted the line off with
is what the record is stamped with, because the file is append-only and that position is the only thing two
same-second records are ordered by. Everything else is narrowing: a step with no kind, a turn that is not an object,
and a scalar where an array belongs are each dropped, so one hand-edited entry costs its own row rather than the run
around it — which is also why a record written before the usage feature parses at all, with `run_usage=None`, no
turns, and every `step.turn` unset.

`reading` drives that parse over a whole file and sits above it, and the two of them are the only owners here that
decide what a bad line costs: a blank line, a line that is not JSON, and a record another producer wrote are each
skipped, and what is left comes back newest first with the position each line was counted off with as the tiebreak —
timestamps are second-precision, and the file is append-only, so the record appended later is the more recent one. The
two ways the read itself fails part company on purpose: a missing file is what a sink switched on but not yet written
to looks like, so it answers empty and silently, while every other `OSError` is warned about first — on the
`orchestrator.trajectory_reader` logger, spelled literally rather than taken from `__name__` because an operator's
filter is keyed on that name and it has to stay put while the module holding it moves — and then answers empty too,
because a page that stays up showing nothing is what an unreadable file
should cost. `log_paths` answers which file that is, and it is the one owner here that names something outside the
package: the trajectory knob is parsed by `analytics/config.py`, so the viewer reads the sink's own setting rather
than a second parse of the same variable. What it names is the settings *view*, not the `analytics/settings.py` holder
the parsed values are bound on — the holder is handed in by the caller, so importing this owner costs nothing of that
holder's read of the process configuration, and *which* holder a read resolves
against stays the caller's question. That is what makes a patch on the caller's own holder the interception every read
it makes goes through. When the knob is unset — the sink is opt-in and default-off — the
answer is the banner naming the knob and the relaunch that lands it, rather than an empty table an operator would
read as "nothing ran".

The four filter and summary owners sit off to the other side of that read, and none of them opens anything.
`filter_models` holds the shapes: one request arrives either as an options object or as the keyword fields it is made
of, both spellings historical, and whichever arrived is narrowed once — every multi-value selection to a set, the
free-text needle stripped and folded — so a run is walked against values normalized for the whole read rather than per
run. `filter_values` owns one value at a time: the distinct ones a dropdown is offered, collected off the runs already
read and sorted, with an empty field dropped rather than offered as a blank choice; the empty *selection* that
constrains nothing, because "nothing ticked" is how a page spells "everything" and reading it as a filter would answer
an operator who narrowed nothing with an empty table; and the text a needle is compared against, which is every text
field a run carries, its steps included, so a search for a path inside a tool command finds the run that ran it.
`filtering` decides which runs one request keeps: it refuses a call that spells the request both ways at once rather
than silently preferring one, it never reorders what the read handed it, and it asks the fixture toggle and the scalar
and multi-value fields before the free-text search, which is the one predicate that walks a run's whole text.
`summaries` totals the survivors into the page's KPI strip, counting an issue once however many runs it took, a
repository only where a run named one, and the money only over runs that recorded some — an unpriced run contributes
nothing rather than a zero that would read as free work. The three that answer over runs name the record at import
even though none of them builds one, which is the one place the viewer's owners do not take the cheapest chain
available: what a read is annotated in is part of its published surface, `get_type_hints` resolves those annotations
in the defining module's own globals, and a name bound only for a type checker is a `NameError` for the caller asking
what `filter_runs` takes. `filter_models` names no run at all, so it stays the leaf the other three are built on.

The rendering owners sit at the far end of the same direction, and none of them imports Streamlit either. `css` is
the stylesheet this page adds on top of the chrome both pages share: almost every rule is scoped to an `orch-traj-*`
class only this page emits, and the text colors arrive as variables the shared stylesheet declared, so a palette edit
moves both pages at once. What cannot be read that way is named for what it costs. The font stacks are interpolated
from `dashboard/tokens.py`, because no variable was ever declared to hold one. The translucent washes behind the
badges, the fixture tag, and the cache-hit pill are literal `rgba()`, because a variable holds an opaque hex a rule
cannot add an alpha channel to — each one restates a declared color at low alpha, and is the one place a palette edit
has to be mirrored by hand. And two rules re-declare the shared chrome's own `.orch-kpis` grid, because this page
carries five tiles where the analytics one carries four; they win the cascade on injection order — the page writes the
shared sheet first and this one after it — rather than on specificity, which is why the narrow-viewport reflow is
restated beside the column count. `summary_html` draws the banner and those five
tiles off the summary the read model already totalled rather than off the runs, so the figures an operator reads are
the ones the filters produced, and it formats the money itself rather than through the shared compact formatters —
those trade digits for a suffix, so the total-cost tile would read `$12` where the authoritative figure is `$12.50`.
`run_html` is the three renderings one run is identified by: the metadata grid that omits a field the record never
carried rather than drawing an empty tile, the overview row in the order the read handed it over, and the label a
picker narrows to one cohort. It marks a fixture in the two places an operator chooses from — a tagged, dimmed row and
a prefixed label — off the record's own tell. `usage_html` is that same run read for what it cost, twice: the
run-level row is the figure the provider reported, while the strip at an assistant-turn boundary is a claude-only
estimate this orchestrator priced itself, so the row carries the note saying the two need not sum — worded differently
for a backend that recorded no turns at all, where the run summary is the page's only usage surface. A chip is drawn
per fact the record actually carried, which is why the cached-token chip is dropped where a backend reports none
rather than always reading zero; the cost chip is the exception, naming its source whether or not a figure resolved so
an unpriced run does not read as free work. It takes the exact-cents format from `summary_html` rather than spelling a
second one, asking it for four decimals on a turn because a per-turn estimate is routinely sub-cent and two would
floor a real charge to `$0.00`. `timeline_html` heads each entry with its position, its kind, and whatever identifies
it, looking that kind up in one vocabulary so a badge's wording and its color cannot disagree — and a kind this viewer
has no wording for still renders, falling back to the tool-result styling with the kind printed verbatim, because a
record from a newer sink is worth reading unlabelled rather than losing the step. It also decides which entry a usage
strip belongs above: a turn spans several entries, so the strip is drawn once at the first one carrying a new turn
index, and the later entries of that turn — along with the turn inputs carrying no index at all — are paired with
nothing, which is exactly what the strip's own copy promises an operator. Everything a caller passes into any of them
is escaped first, because a page writes these with `unsafe_allow_html=True` and every value in them is record text the
viewer does not own. The KPI tile the strip is drawn from is private to `summary_html`, the owner that defines it, and
every shape and builder here reports that owner — nothing under this package spoofs a module it does not live in.

The six page owners sit above both halves, and none of them imports Streamlit either: the five that draw take it in
as an argument, the way a run and a settings holder are handed in, so drawing a page costs nothing at import and every
control is testable without it.
`page_models` holds the two frozen shapes one run carries — the file as it was read and what the controls then
answered — kept apart because different halves of the run answer them, with the total a property rather than a stored
field so a page cannot claim a count its own runs disagree with. Both are private to that owner, since only the page
above them builds one. `page_setup` is what a
run settles before anything is drawn: the shared stylesheet then this page's, in the order their cascade depends on;
the opt-in banner an unconfigured sink is *stopped* with rather than fallen through from; and the one pass over the
file the whole page is then built off, with the dropdown values collected from what was read rather than declared.
Which file that is comes off the settings holder handed in, the same way `log_paths` takes one. `controls` draws the
sidebar and reads it back as one request, folding every "no clause" spelling together — an unticked multiselect and the
*All* repository both become `None`, because a selection matching nothing is not what an operator who narrowed nothing
asked for — and it takes the issue box's `#123` through the same parse `dashboard/filters.py` gives the analytics page,
so one spelling works on both. `picker` is the two surfaces over the survivors, and they answer different questions:
the overview table is capped at the 200 most recent and says how many matched, because a silently truncated table reads
as a complete one, while the repo → issue → run cascade is deliberately uncapped so every match stays reachable. It
draws the fixture receipt only where the read held fixtures, worded for whichever way the toggle is set. `run_render`
is the card the picked run is read in full through, ordered so that what qualifies a timeline — a synthetic fixture, a
run the sink's budget truncated — is read before the timeline itself. The final output is the one entry handed to
Streamlit as markdown; a prompt, a payload, and a tool result are code blocks, because they are text that must not be
interpreted. `page_render` is where the rest are composed — the banner, then the tiles, then the two picker surfaces,
then the receipt naming how much of the read is on screen and which file it came from — and two of those steps are
returns rather than sections: a file that held no records at all stops at the empty-file notice, because a strip of
zeroes over an empty table reads as "nothing ran" when the answer is "nothing was ever written here", while a read the
filters then emptied stops after the tiles, because those counts are what say the narrowing is what dropped the runs.

`orchestrator/apps/trajectory_dashboard.py` sits above all of it, outside this tree: the only `streamlit run`
target the viewer has, and what composes the page owners under `observability/trajectory_viewer/` into one run of the
page.
Everything it composes is imported inside `main()`, Streamlit included: the repo root only reaches `sys.path` on the
line above, in the shim `apps/bootstrap.py` owns, so under a script launch no `orchestrator.*` name resolves before
then — which is why importing the app costs that shim and nothing else. The analytics settings holder the sink's knob
is read off is resolved at call time for the same reason, and handing it down is the one place a caller's world is
bound: `page_setup` and `log_paths` beneath it answer on whichever holder arrives rather than on one they captured.

`orchestrator/apps/analytics_dashboard.py` sits the same way above `observability/dashboard/`: the canonical
`streamlit run` target, and what composes those owners into one run of the analytics page — the three handles every
pass draws with, the chrome, the refusal an install with no database behind it is stopped by, the two reads no filter
narrows, and then either the notice that there is no span to pick a window from or the controls, the staged load, and
the panels beneath. Each owner is imported inside the pass that reaches it, alongside Streamlit and pandas,
for the reason the viewer's app defers its own: the repo root only reaches `sys.path` on the
line above, so importing the app costs that shim and nothing else, and the refusal reads the URL off the settings
holder at call time rather than a name bound when the module was imported.

Neither page has a root-level site left, and neither does anything under them: every
read, recorder, prune, trajectory write, replay, panel, chart, theme value, record model, filter, and markup builder
is reached on the owner under `observability/` that defines it, and each `streamlit run` target under `apps/` is the
one launch path its page has.

Four rules hold for whatever lands there, each with a check under `tests/observability/` that discovers its own subjects
off disk so a new owner is covered the day it appears. An initializer binds nothing unless the surface it fronts is what
a caller asks for by name, so importing one owner does not charge the importer for its siblings: the recording path runs
inside every tracked agent run, and a binding would put the query owners and the database driver behind that import.
`usage/__init__.py` and `analytics/recording/__init__.py` are the two exceptions and pay that cost deliberately — the
parsers and the recorders are each reached through their package, so one re-exports the nine parsers and the five result
types they return under an `__all__` and the other the six recorders — and the check that excuses them is keyed on that
`__all__`, so a third publishing initializer is a deliberate edit rather than a silent one. What a publisher may charge
for beyond its own owners is declared per package: recording is configured by `analytics/config.py`, writes its lines
through `analytics/sink.py`, meters a run through `usage/`, and hands that run's second record to
`analytics/trajectories/`, so naming it buys those four chains and nothing else.
Nothing under the tree carries an export manifest, a resolver hook, or a `.pyi` surface — a re-export is the owner's own
object, bound once at import rather than resolved per lookup, so the module defining a name stays where a reader finds
it and where a patch has to land, rather than somewhere answering on its behalf. Nothing observed is on the workflow's
decision path, so no module may import the workflow engine, a
stage, or an application entrypoint — the CLI and the runtime loop on one side, and the two `streamlit run` targets
under `apps/` on the other; the dependency runs one way, and an
entrypoint composes these owners rather than the reverse. And Streamlit and Plotly stay function-local: they live in the
optional `dashboard` dependency group, so every module has to import cleanly with both blocked outright *and* with no
attempt on either recorded — a module-scope import that swallows its own `ImportError` is still a load in the install
that has the package — which is what keeps the data an owner shapes testable in an install that has neither.

## Workflow labels

An issue should have at most one workflow label at a time. The set is `workflow:decomposing`, `workflow:ready`,
`workflow:blocked`, `workflow:umbrella`, `workflow:implementing`, `workflow:documenting`, `workflow:validating`,
`in_review`, `workflow:fixing`, `workflow:resolving_conflict`, `question`, `discussion`, and the two terminals
`done` / `rejected`.
The `workflow:` prefix marks what the orchestrator writes itself, so a repository's own vocabulary cannot collide with
it; the five states a human also applies or reads on their own keep the bare spelling. The orchestrator also creates
three non-workflow control labels: `backlog` and `paused` each make per-tick handlers skip the issue entirely
(`backlog` is a "not yet" hold on a fresh issue, `paused` freezes an in-flight one), and
`workflow:community_contribution` is applied by the per-tick open-PR sweep to PRs from non-bot authors outside
`ALLOWED_ISSUE_AUTHORS` so a human reviews them. The two an operator types stay bare; the one the sweep applies is
namespaced on the same rule as the states. Both sets above are closed, and `WorkflowLabel` / `ControlLabel` membership
is what closes them rather than the prefix: a `workflow:`-prefixed name outside them — Dependabot's service labels on
its own update PRs — is not a state, routes nowhere, and survives a label write untouched.

The namespace is a GitHub label spelling and stops at that boundary, which is the distinction the module map above
reads by: a bare tag there names the *stage* — the handler, the subpackage under `orchestrator/workflow/stages/`
holding it, and the identifier analytics rows, audit event payloads, and agent-session attribution have always carried
— while the wire label an issue carries is spelled `workflow:<tag>`. `workflow/state.py` owns both directions:
`stage_name` strips the prefix for those sinks, and `label_for_name` resolves either spelling back to its member.

A repository whose labels predate the namespace is migrated by the startup label bootstrap. Of a namespaced label it
asks a three-way question: where only the pre-namespace spelling exists it is renamed in place rather than
duplicated, so every issue holding it moves across in one edit; where the namespaced label already exists the
bootstrap does nothing and leaves any bare label beside it defined; where neither exists the namespaced one is
created. The seven never-namespaced labels have no second spelling to migrate off and are simply created bare when
missing. Wherever that rename does not run, three reads still take the bare spelling: issue routing, the community
sweep's dedup marker, and the closed-issue sweep's query. A namespaced label outranks a pre-namespace one on the same
issue, and a label write takes off only what it owns, so a bare `blocked` or `ready` the repository uses for its own
triage survives a relabel; see
[`state-machine.md`](state-machine.md#legacy-labels-and-the-migration-off-them).

Label names are part of the public contract because live GitHub issues already carry them. For the meaning of each
label, the control-label semantics, and the per-stage transitions they trigger, see
[`state-machine.md#workflow-labels`](state-machine.md#workflow-labels).

## Process model

There is **only one long-lived process**: `python -m orchestrator`. It is wrapped by `run.sh` so the loop can
self-exit and be restarted with new code.

- **Trigger**: started manually (or by a wrapper). Optional `--once` for a single tick.
- **Tick cadence**: every `POLL_INTERVAL` seconds (default 60).
- **Self-restart guard** (`runtime.self_update.self_modifying_merge_happened`): each tick fetches
  `origin/<ORCHESTRATOR_BASE_BRANCH>` (default `main`); if it advanced past the process's startup SHA *and* the new
  commits touch `orchestrator/`, the loop
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
`runtime.ticks.run_tick`: single-repo deployments stay in-thread, multi-repo deployments use a `ThreadPoolExecutor`
sized to the repo count. A single long-lived `IssueScheduler` (global cap `MAX_PARALLEL_ISSUES_GLOBAL`, per-repo cap
`MAX_PARALLEL_ISSUES_PER_REPO`) is shared across all `tick` calls.

One repo's pass is owned by `workflow/engine/tick.py` — the base refresh, the community-contribution PR sweep, the
skill-catalog emission, and then either the scheduler handoff or the in-tick sequential / bounded-parallel loop, in
that order (see [the owner's paragraph](#top-level-layout) above for why each step depends on the one before it).

The dispatch loop classifies each issue as family-aware (`workflow:decomposing` / `workflow:blocked` /
`workflow:umbrella` / unlabeled — parent ↔ child writes) or fan-out (everything else). Fan-out submits go one callable
per issue. Every family-aware issue this tick is folded into ONE bucket submit per repo that drains them sequentially
on a single executor worker so a stale child cannot starve the parent umbrella issue. When every family-aware issue in
the bucket runs a no-agent handler (`workflow:blocked` or `workflow:umbrella`), the bucket is cap-exempt and runs on a
dedicated executor pool so a pure label / dep-graph walk cannot be blocked by ordinary implementation work. A bucket
containing `workflow:decomposing` or unlabeled pickup stays cap-counted.

Per-issue durable state lives in a single **pinned comment** on the issue (`<!--orchestrator-state {...json...}-->`).
The orchestrator process is stateless; the label and the pinned JSON are the entire dispatch input.

For the full per-tick sequence (eligible-issue enumeration, family vs. fan-out partitioning, the pre-PR rebase /
PR-having clean-rebase + push (with `workflow:resolving_conflict` reached on actual rebase conflicts, plus the
`fixing` worktree-drift dead-lock breaker that hands a stuck validating-route transient fix-loop to
`workflow:resolving_conflict` when the worktree is behind base or carries an unpushed rebase), the read-only skip
the `question` and `discussion` labels take (and the parks and in-flight discussion records that keep taking it after
the label is gone), the per-tick external-merge sweeps, and the complete pinned-state JSON schema), see
[`state-machine.md#per-tick-flow-workflowtick`](state-machine.md#per-tick-flow-workflowtick).

## Stage handlers

Each workflow label dispatches to a `_handle_<label>` function. Every handler lives under
`orchestrator/workflow/stages/` (see the module map above), and the dispatcher reaches one by importing the module its
label is paired with in `_STAGE_HANDLER_TARGETS` and reading the handler off it, so a patch that has to intercept the
dispatch targets that module. A stage-to-stage call names the owner the same way: the decomposition
disabled-rollout and `ready` paths name `stages/implementing/handler.py` for `_handle_implementing`, so a patch that
has to intercept the implementation a `single` verdict routes to targets that owner.

`orchestrator/workflow/stages/` holds every stage -- `decomposition`, `implementing`, `documenting`, `validating`,
`in_review`, `fixing`, `conflicts`, `question`, and `discussion` -- each as a subpackage of responsibility-named
owners. Nothing
answers for a stage beside them, so a name a stage owns has one module to resolve on and a `patch.object` there is the
only interception a caller can need. Two checks in `tests/workflow/stages/test_imports.py` hold that line for every
stage at once: `orchestrator.stages` resolves to nothing the interpreter would find, and every label in
`_STAGE_HANDLER_TARGETS` names an owner inside a stage subpackage here — so a stage arriving later is covered without
anyone adding it there. Dispatch names the owners too: `_STAGE_HANDLER_TARGETS` names the module a handler lives on,
and so does the same-tick start in `workflow/engine/pickup.py`, so a patch meant to intercept a dispatched handler has
to land on the owner. Like `workflow/engine/`, this package and each stage subpackage inside it bind nothing in their
initializers -- the dispatcher resolves one handler per issue, so an eager binding there would charge that import for
every other stage's leaves and for the worktree and GitHub subsystems they reach.

The decomposition owners bind their collaborators directly. `manifest` calls `validation` for the split rules, `run`
calls `session`, `recovery`, and `outcomes` for the order a tick asks them in, `outcomes` calls `manifest` and
`split`, `blocked` and `umbrella` both call `parents` for the child scan and `activation` for the dep-graph walk, and
every owner that writes to GitHub reaches `workflow/engine/` for the comment poster, the run guards, the prompts, and
the usage counters. `state`, `models`, `manifest`, and `validation` deliberately reach nothing — the keys, the
carriers, and the whole parse are decidable without a client, which is why the manifest rules can be exercised without
one. So a patch that has to intercept the manifest parse, a child scan, or the split writer targets the owner module.
What the stage does not own it names on the owner that does: `models`, `run`, and `session` reach
`git.worktrees.decomposition` for the scratch checkout's path, creation, and removal, `run` reaches
`git.worktrees.creation` and `git.verification.probes` for the read-only commit and dirty probes, and `run`,
`blocked`, and `session` reach `stages/implementing/` for the handler a `single` verdict routes to and the retry
budget a fresh spawn consumes — so a mock for any of those lands on the owner. No flat module sits beside these
owners: the `orchestrator.stages` check in `tests/workflow/stages/test_imports.py` covers this stage too, so the
manifest parse, the child scan, the split writer, and all four dispatched handlers are each answered on an owner
alone. `_MAX_CHILDREN` runs the other way: the cap lives with the validator that rejects past it and
`workflow/engine/prompts.py` reads it back, so the bound the decomposer is told and the bound it is judged against
cannot drift apart.

The implementing owners bind their collaborators the same way, and they divide along the decisions one tick makes
rather than the code it runs. `handler` holds the order those decisions are asked in and calls `read_only_relabel` and
`continue_command` for the two preflight signals, `drift` for a body edit, `spawn` for the run itself, and
`disposition` for what the run left behind. `spawn` asks `session` for the retry budget and `drift_preflight` for the
awaiting-human route; `resume` and `execution` split one resume between the call shape callers wrote against and the
attempt-and-retry behind it, over `session` for retirement and `worktree` for the checkout; `disposition` routes a
committed tree to `publication` and everything else to `parks`. `state`, `models`, and `session_read` reach no engine
owner, no GitHub client, and no worktree helper — `session_read` reads the configured agent spec and nothing else —
which is why the pinned-state keys, the carriers, and the CLI-marker classifiers can be exercised without a client. So
a patch that has to intercept a park, a push, a resume, or a session read targets the owner module. The helpers the
stage does not own are named the same way: the branch and worktree names from `git/worktrees/paths.py`, the checkout
and its commit probe from `git/worktrees/creation.py`, the unpushed-branch and branch-tip probes from
`git/worktrees/recovery.py` (the second is how the read-only relabel guard measures a branch against the SHA a
discussion round recorded, which ahead-of-base cannot answer), the
HEAD and dirty reads from `git/verification/probes.py`, the push from `git/authentication.py`, the commit subject and
the PR title builders from `git/publication/`, and the auto-rebase park reasons from `git/base_sync/state.py` — so a
patch on any of those lands on the owner that defines it. No flat module
sits beside these owners: the `orchestrator.stages` check in
`tests/workflow/stages/test_imports.py` covers this stage too, so the dev session, the retry budget, and the park
reasons are each answered on an owner alone — including for the sibling stages that borrow the resume, the session read,
and the question / dirty-tree parks from here.

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
`workflow/stages/validating/watermarks.py`, so a patch that has to intercept one lands on that owner. The git it
runs on is named the same way — the PR-aware creator and the worktree path off `git/worktrees/`, the HEAD and dirty
reads off `git/verification/probes.py`, the fetch and the push off `git/authentication.py`, the hardened runner off
`git/commands.py`, the ahead/behind read off `git/publication/probes.py`, and `_AUTO_REBASE_PARK_REASONS` off
`git/base_sync/state.py`. That
last one is why both precondition reads consult it before they act: a park the pre-tick refresh owns is one whose
retry nudge belongs to `_sync_pr_worktree_to_base`, so the docs stage stays silent rather than answering a comment
addressed to the rebase loop. No flat module sits beside these owners: the `orchestrator.stages` check in
`tests/workflow/stages/test_imports.py` covers this stage too, so the awaiting-human flag, the last-action comment id,
and the park reasons are each answered on an owner alone, `_handle_documenting` included.

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
lands on the owner that defines it. The helpers it does not own are
named the same way — the branch and worktree names and the checkout from `git/worktrees/`, the HEAD and dirty reads
from `git/verification/probes.py`, the fetch and push from `git/authentication.py`, the ahead/behind measurement from
`git/publication/probes.py`, and `_AUTO_REBASE_PARK_REASONS` from `git/base_sync/state.py`, so a patch on any of them
lands on the owner too. No flat module sits beside these owners: the
`orchestrator.stages` check in `tests/workflow/stages/test_imports.py` covers this stage too, so the reviewer round, the
parks, and the watermark seed are each answered on an owner alone. The six names sibling stages borrow —
`_post_user_content_change_result`, `_handle_dev_fix_result`, `_stranded_fix_unpushed`,
`_try_recover_validating_transient_park`, `_VALIDATING_TRANSIENT_PARK_REASONS`, and `_latest_pr_comment_ids` — are
each named on the owner by the caller that borrows it: in_review's and resolving_conflict's
drift routes for the first, fixing's resume and parked owners for the next four, documenting's final-docs handoff for
the last.

The in_review owners divide by the four answers one tick can reach, and `handler` holds the order because the order is
the contract rather than a style choice. `feedback` runs before `drift`: `user_content_hash` covers every human
issue-thread comment as well as the body, so asking drift first would resume the dev over a review comment that should
have been bookmarked and handed to `fixing`. `feedback` routes through `fixing_route` for the flip, and the bookmarks
it writes are deliberately not watermarks — the fixing handler re-reads the same comments to build its prompt. `drift`
reads the PR conversation before the ratchet can leap past it, resumes the dev, and hands both outcomes back to
`workflow:validating` with `review_round` reset. `merge_gate` is last and never merges: an unmergeable PR parks for a
human (no `workflow:resolving_conflict` route from this stage) and a mergeable, approved, unvetoed head earns one HITL
ping per head SHA. `models` and `state` reach nothing at all and `watermarks` reaches no further than the client it is
handed, so the carriers, the wire key, and both the ratchet and the legacy seed are decidable without a worktree or an
agent. So a patch that has to intercept the scan, the route, the resume, or the ping targets the owner module. This
stage owns no dev machinery either: the resume comes from `workflow/stages/implementing/` and the body-edit
disposition from `workflow/stages/validating/drift_outcomes.py`, so a patch on one of those lands on the owner. The
helpers it does not own are named the same way — the worktree names from `git/worktrees/paths.py`, the checkout from
`git/worktrees/creation.py`, the HEAD read from `git/verification/probes.py`, and base-sync's
`_AUTO_REBASE_PARK_REASONS` from `git/base_sync/state.py`, which is what tells a park the rebase loop owns from one
this stage may answer. No flat module sits beside these owners: the `orchestrator.stages` check in
`tests/workflow/stages/test_imports.py` covers this stage too, so the feedback scan, the fixing route, the drift
resume, and the merge ping are each answered on an owner alone. `_comment_created_at` is the one name a sibling
borrows, and its one cross-package caller — fixing's quiet window — names `watermarks` itself.

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
nothing, the ACK fast path, and the `workflow:validating` relabel a pushed fix earns. `models`, `state`, and
`bookmarks` reach no further than the client they are handed, so the carriers, the wire keys, and the whole
reconstruction are decidable without a worktree or an agent. So a patch that has to intercept the rescan, the replay,
the parked dispatch, the reroute, or the run targets the owner module. This stage owns no dev machinery either: the
resume and the poisoned-session drop come from `workflow/stages/implementing/`, the dev-fix disposition, the
stranded-fix probe, and the transient-park recovery from `workflow/stages/validating/`, and the comment timestamp the
quiet window measures from `workflow/stages/in_review/watermarks.py` — so a patch on any of those lands on the owner.
The git it runs on is named the same way — the worktree path and the branch resolver off `git/worktrees/paths.py`, the
creator off `creation`, the HEAD and dirty reads off `git/verification/probes.py`, the plain runner behind the
behind-base probe off `git/commands.py`, and `_AUTO_REBASE_PARK_REASONS` off `git/base_sync/state.py`. No flat module
sits beside these owners: the `orchestrator.stages` check in `tests/workflow/stages/test_imports.py` covers this stage
too, so the pending-fix bookmarks, the review-round counter, and the park reasons are each answered on an owner alone,
`_handle_fixing` included.

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
patch on any of those lands on the owner. The git it runs on is named the same way — the worktree path and the branch
resolver off `git/worktrees/paths.py`, the PR-aware creator off `creation`, the HEAD and dirty reads off
`git/verification/probes.py`, the fetches and the leased push off `git/authentication.py`, the plain and hardened
runners off `git/commands.py`, the ahead/behind read off `git/publication/probes.py`, and the base rebase and its
in-progress probe off `git/base_sync/pre_pr.py`. No flat module sits beside
these owners: the `orchestrator.stages` check in `tests/workflow/stages/test_imports.py` covers this stage too, so the
round counters, the divergence lease, and the park reasons are each answered on an owner alone,
`_handle_resolving_conflict` included.

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
`git/worktrees/terminal.py` — the last one matters because a mock aimed anywhere else would let a real teardown
run. The rest of the worktree surface is named the same way:
`_worktree_path` and `_resolve_branch_name` on `git/worktrees/paths.py`, `_ensure_worktree` and `_has_new_commits` on
`git/worktrees/creation.py`, and `_worktree_dirty_files` on `git/verification/probes.py` — the last two are what the
read-only contract is decided by, so a mock for either has to land there. No flat module sits beside these owners: the
`orchestrator.stages` check in
`tests/workflow/stages/test_imports.py` covers this stage too, so the session lock, the parks, and the wire keys are
each answered on an owner alone, `_handle_question` included.

The discussion stage divides the same way the question stage does, because it is the same shape of conversation held
to a stricter contract: until a human says the two sides understand the design the same way, the agent may not write
anything AND may not decide anything. `handler` holds the order -- `terminal`'s poll of an issue whose plan is
already published (the record its own publication left, read as a pair with `pr_number` so a dev's inherited PR is not
mistaken for one), the
gate that makes a discussion-owned park the humans' turn (a park any other stage wrote does not gate, or an issue
relabeled here while parked elsewhere would stay inert for good), the trusted reply that ends that turn, the two
preflights on what the last round left, then the round and its disposition -- and it is where the stage stops, since
no route from here reaches another stage. `session` is what keeps a multi-round conversation on one
agent: the pinned spec and session id every round after the first is read back from rather than re-resolved, the one
filter both the prompt and the consumed watermark are drawn through (so neither an untrusted reply nor the stage's own
posted analysis can steer the agent or be recorded as read), and the degrade from the followup prompt to the full one
for a round with no session to resume -- since `_run_agent_tracked` starts a fresh agent then, and a bare quote of the
reply would reach it with no design attached. That rebuild is also where the stage's own analyses are retained past
the allowlist by their recorded ids, since a deployment listing its humans and not its bot account would otherwise
hand a fresh agent the answers without the questions -- and it reads the thread ONCE, handing back the replies its
text quoted alongside the text, because a ceiling derived from a second read disagrees with the prompt by whatever
landed between the two. Reading the replies and consuming them are separate calls with the round's provenance write
between them, which is what leaves a reply unconsumed when the tick declines to spawn on it
-- or dies before its disposition, so the next process replays the round against the same answer. What is consumed is
measured over what the round's own prompt was built from and never over the thread as the park finds it, because
minutes of agent run separate the two and a comment that lands in them is one this stage would otherwise read never;
recognizing its own comments without a watermark above them is what `engine/comments`' id list and body marker are
for, and why neither reader here matches on author login. `run` opens the round in the issue's own
`issue-N` worktree -- reusing the tree its predecessor read whenever it is still there -- and owns every probe of it:
the pre-`_ensure_worktree` dirty read, because preparing the checkout force-removes a dirty tree that carries no
commits; the pre-spawn `_head_sha`, because the branch may already carry another stage's commits; and the same
question asked a tick late for a round that never got to answer it -- or asked of a parked issue a reply has just
arrived on, where a tree off the anchor or holding edits stops the round: reported once when the standing park said
nothing about repairing it, and held in silence when that park already carried the paths and the reset command. That
last one is why the SHA is written down before the spawn
rather than only held: a mid-run `paused` suppresses every disposition by contract and a crash takes them with it, and
the next tick reuses the same checkout, so an anchor is the only thing that can tell a commit the ended round made
from one the branch arrived carrying. `discussion_session_id` and the consumed watermark are staged after that write
instead and ride the park's, so a round nobody sees leaves no conversation pointer and consumes no answer. `outcomes`
enforces the write contract on the round
that does come back, checking commits and the dirty tree before interruption and before the response, so a round that
wrote is judged on what it wrote rather than published as a design. What a commit means is `publication`'s to answer:
one reading of the branch -- whether its tree could be read and is clean, what its commits change against the base
commit the round pinned before it spawned, and whether the plan is in HEAD as a regular file at all, since a
deletion changes exactly
the path an addition would -- decides between the agreed plan, which is pushed and opened as a PR, and everything
else, which parks with that reading quoted. Who may reach it is the other half of the answer. The disposition of the
round that committed and the preflight that finds a commit a round never got to report both hold a commit the anchor
attributes to a round of this stage. A parked issue holds nothing of the kind on its face -- its round is over, and a
plan-shaped commit appearing afterwards is somebody else's -- so two records say when it does.
What the push is allowed to overwrite is read before it runs. The lease is pinned to the tip the remote was just
observed at, and what makes that tip publishable is whether the commit being published CONTAINS it (`_commit_contains`):
a branch the remote does not have yet is the ordinary first publication, and every other tip has to be an ancestor of
the plan commit, which a replay after a crash and an inherited PR branch the plan sits on top of both are. A lease
cannot answer that -- it proves the ref has not moved, not that what is on it survives -- so a round that reset an
inherited branch to base before committing its plan would pass every other reading and delete the PR's history.
Anything else is somebody's own write to that branch -- a reviewer amending the plan on
its PR while a publication of it is unfinished -- and parks `discussion_push_failed` naming it. Pinning is what makes
the reading hold: `_push_branch`'s own `ls-remote` fallback would adopt whatever the remote had become as the value it
may clobber, so a publication being retried after a crash would send its older validated commit straight over that
write. The refusal is taken after the in-flight marker is durable, because the reply that retries it reaches the
publication through that marker and a park without one leaves the thread with nothing to answer.
`discussion_base_sha` rides that same pre-spawn write and is the commit the whole reading is measured from: what the
REMOTE said the base branch was at, read through the token rather than off `refs/remotes/<remote>/<base>`, which names
the base but lives in the object store the issue's worktree shares -- an agent can commit code, repoint that ref onto
it, and commit the plan, leaving a diff that shows one file while the branch carries two commits. It is persisted, not
re-read, because the tick that publishes need not be the tick that ran. What is recorded is an id this clone can read
and not merely one the remote named: the base advances between a tick's own fetch and the round that opens in it, and
an absent object fails the local diff that spends the record -- which reports no paths, exactly what a branch changing
nothing reports. So `_commit_present` is asked, one `_authed_target_fetch` of the base supplies what is missing, and a
commit still unreadable after it is recorded as no base rather than as a reading nobody could take.
`discussion_round_open`, written beside the anchor before every spawn and cleared by every park (and by the one
ending that records without parking, the adoption of an already-decided pull request), covers the resumed
round: it runs with the park it is answering still
durable, so one that committed the confirmed plan and was then paused or cut short is judged exactly as the same
crash on an unparked issue is. `discussion_publishing_sha`, written before the push, covers the publication itself --
turning a failed push into a retry (which spends the reply that asked for it, so a failure is not re-asked every poll,
and which replaces `discussion_push_failed` with `discussion_publishing` in that same write, since a reason the
recovery refuses to resume plus a spent reply is a publication nothing would pick up again)
and keeping a crash between `open_pr` and the pinned write from asking an operator
to reset away the commit its PR is open against. Neither becomes a way to publish a design nobody argued out: the
marker is asked first and answers for the branch either way, so a second plan-shaped commit appearing over an
unfinished publication is refused rather than read as the round's own work, and it is spent only by the next round
opening or by the branch going back to the anchor over a remote that no longer carries the commit it names -- the
push sends the SHA it validated rather than `HEAD`, so a local ref that never moved says nothing about whether the
plan went out, and dropping the record on that reading would leave a published plan on a pull request nobody
recorded while another round opened over it. The PR that publication lands on gets the same treatment as the
branch: `find_open_pr` only promises something open on this ref, so a body that does not name the publishing session
is rewritten to the plan's and one that does is left as it stands. What that lookup cannot see is the other half of
the same crash window -- a plan PR merged before anything recorded its number, which closes it and, with auto-delete
on, takes the head branch too -- so `find_pr_for_commit` asks by the publication's own SHA across every state before
the push -- matching on the commits a pull request CARRIES rather than the head it is on, since a human pushing to
that branch or merging the base into it moves the head inside the same window while the published commit stays in
the PR. MERGED, its number is recorded and nothing is pushed or opened: the branch the merge deleted would otherwise
be recreated and a second pull request asked for on a commit already in the base. Closed without merging is the
opposite reading and gets the ordinary publication: nothing landed, the branch is still there, and a recorded
pull request nobody can open would hold the stage on an unreviewable artifact instead of leaving one to read. A
commit list GitHub declines to serve is a third answer (`PR_LOOKUP_UNREADABLE`) rather than a miss, since that list
is the only place an amended, squash-merged publication is still visible; so is an enumeration that never reached
the candidate. Either way the stage writes its marker and stops, and the next tick asks again. The recovery asks
the same pair about the commit the MARKER names, since a checkout rebuilt from the remote comes back on whatever
head the humans left there. The
recovery asks the same question before it judges the branch at all, since a host that lost the checkout and the local
ref rebuilds from the base -- the merge took the branch -- and that tip matches neither the marker nor the anchor.
The same reasoning is why
`git/base_sync/refresh.py` lists this label beside `question` in its read-only gate — and the park beside the label,
since the refresh runs a full tick before the guard that consumes it, and `discussion_round_open` /
`discussion_publishing_sha` beside both, since those are written before the thing they describe and a tick that died
mid-round leaves one standing with no park at all — and why
`stages/implementing/handler.py` asks whether a merged recorded PR is this issue's work having landed before it
finalizes -- a plan PR is a design being agreed to, and two records say which it still is. `discussion_plan_path`
answers first and answers whatever that PR's head is now, because it is retired by this stage's own handoff before
anything spawns: while it stands nothing here has pushed, so a head that has moved is the humans editing the plan they
are agreeing to (a correction, a base merged in to make it mergeable) rather than an implementation to finalize.
`discussion_plan_sha` against the PR's head answers for the ticks after that handoff, which is what stays right when a
tick pushes onto the PR and dies before recording it -- and it is the head the handoff itself read, not the commit
publication pushed, so an amendment the humans made is not what the tick after reads as an implementation. That read
has a third answer: a PR GitHub could not be asked about ends the tick unfinalized and unspawned rather than falling
through to the terminal, which would fetch it again, and a request that failed once and succeeded next would finalize
the very plan the first answer protects. This is also why
`stages/implementing/read_only_relabel.py` refuses a relabel out of a `discussion_*` park -- or out of an unfinished
round, which carries no park at all -- whose branch, or whose checkout's own `HEAD`, has moved off
the SHA the round recorded (a commit made while detached leaves every ref where it was and the plan in the tree,
which is exactly what the shortcut would push), or whose tree `git status` could not report on at all (the list form
of that read answers a failure with no paths, which is what a clean tree answers, and the creators force-remove a
checkout nothing is holding). An unfinished PUBLICATION is refused on its record alone, because the
marker precedes the push and a fresh clone reads clean on every local probe at once, so the way out it names is the
`discussion` label whose recovery finishes it rather than a reset: the tree survives every exit short of the terminal
that finishes the issue, so nothing may rebase over it and nothing may ship as dev
work what this stage did not vouch for — while the commits an issue arrived carrying, which that same record
certifies, still let the relabel through — as does a published plan, whose anchor was moved onto the tip its
publication pushed, and as does the live head of the plan PR itself, which is the design as its reviewers left it.
Once that PR has MERGED the older ahead-of-base reading comes back, because the handoff for a merged plan resets the
branch to the base and records that in the write after the reset: a crash in between leaves a tip no record names,
and an exact match would report the base branch itself as unreviewed work.
Clearing that park hands the certified tip on as `read_only_baseline_sha`,
because `stages/implementing/spawn.py` otherwise reads any branch ahead of base as an interrupted dev run and would
skip the implementer to republish the very commits the discussion was held on top of. The same clear retires
`discussion_plan_path`: the relabel is the humans deciding, and a record left behind would hold this stage inert if the
issue ever came back. What replaces it is that live head, read once and used twice: recorded as the plan commit, and
anchored onto the branch through `worktrees/creation._anchor_pr_worktree` -- one authenticated fetch, a re-read of
what the remote says that branch is on, and a hardened
`reset --hard` (an `update-ref` where the checkout is gone) -- so the developer builds on what was approved instead of
on a tip whose push would take the amendment back out. The re-read is the one that covers the gap between reading the
PR and moving the ref: a human pushing in between leaves the fetch bringing their commit with the one just read still
resolving underneath it, so a local-object check alone would anchor on a head the PR has moved past and the push after
it would take their commit off the remote as its own lease. That call answers with the tip the branch ended up on, and
the baseline records it: the reviewed head, or `<remote>/<base>` when the remote confirms the branch is gone and what it
carried has landed there -- and that base is one the tick fetched, since a cached ref a failed fetch left behind names
the base from before the merge, which for a plan that has just landed is the one base the plan is not in. An answer of
nothing at all HOLDS the handoff -- the tick ends having written nothing, with
the plan record still standing -- because taking it would spawn the developer on a commit the reviewers moved past and
let the ordinary push that follows read their head off the remote as its own lease and overwrite it. Reading GitHub
before the guard rules is what makes the move
crash-safe: a tick that anchors and dies before its write leaves a tip the next one recognizes as the reviewed head
rather than convicting the branch of it. What that write leaves is a state of its own, not a moment: the baseline
beside `discussion_plan_sha` says the handoff was accepted and this stage has published nothing since, and an
interruption anywhere after it -- a live pause, a shutdown sweep, a dead process -- leaves an issue sitting there for
polls while the design is still on an open pull request its reviewers can move.
`_reconcile_open_plan_handoff` is the guard's own reading taken again on each of those ticks, so an amendment made in
that window is inherited rather than read as this stage having pushed (which closes the issue as `done` on a merged
design, or spawns the developer on a checkout whose push takes the correction back out), and a merge is re-anchored at
a base that has moved since. The branch is what ends it, because a push reaches git before it reaches the issue: a tip
past the baseline is a developer's own work, and a tip nothing could read is no answer and holds the tick. The move
itself is marked durably first (`read_only_anchor_sha`), since it too puts the ref on the reviewers' head before
anything records that it did -- and a marker still standing is what tells the branch that crash left from a
developer's commit, which the recovered-work shortcut would otherwise push with no agent having run.
`parks` holds what each of those decisions then says to the
human, and every one of them lands on its one funnel — the funnel puts back two things the shared helper overwrote:
the `park_reason`, which the handler's gate reads back next tick, so a park assembled anywhere else would earn a
second round over the top of the first; and the consumed ceiling, which the helper stamps at the newest comment on
the thread and which has to stay where the round's own prompt read to, or a reply that landed during the run is
recorded as answered by a round that never saw it. `state` and `models` reach no engine or git owner, so the park
reasons, the three predicates the handler gates on — whose park this is, whether it has already asked for the
checkout to be repaired, and whether the plan is already published — the plan path itself, and the carriers are all
decidable without one. Spelling that path on `state` is what keeps the prompt that promises the agent a file and the
check that refuses every other one from drifting apart: the prompt builders are handed it, and the publication check
compares against it. `terminal` is what asks the pull request those records name what it has become, and it is asked
ahead of every local reading because both endings this stage has were made somewhere else: a merged plan PR finalizes
to `done`, one closed unmerged to `rejected`, and either takes the shared tail from `engine/terminals` under
`stage="discussion"` -- the stamp, the label, the receipt before the single write, the event, the close, and
`_cleanup_terminal_branch` last of all. An open one decides nothing and, more to the point, reaps nothing, which is
also what a closed ISSUE with an open plan PR gets: the label it keeps is what leaves it inside the closed-issue sweep
until the pull request itself resolves. A closed issue with no plan PR is the one arc that needs no pull request, and
it rejects without a teardown -- the branch under it may be an unpublished plan commit or a PR the issue merely
arrived here holding. That last reading is taken only once a standing `discussion_publishing_sha` has been looked up
by commit, since the publication opens its pull request before it records the number and a human can decide the issue
inside that window: a decided pull request found there is finalized on the spot (its number and branch written first,
because the event names one and the cleanup resolves the other), and an open one holds like a recorded one.
So the only worktree this stage ever tears down is one whose plan PR is gone: everywhere else
the tree the discussion read is the tree its next round and the operator both look at. The
stage borrows the same engine surfaces question does -- the tracked spawn, the awaiting-human park, the prompt
builder, the trusted conversation text, and the stderr diagnostics from `workflow/engine/`, `_worktree_path` and
`_resolve_branch_name` from `git/worktrees/paths.py`, `_ensure_worktree` from `git/worktrees/creation.py`,
`_branch_tip_sha` from `git/worktrees/recovery.py` -- the anchor comparison falls back to it when the checkout
directory is gone but the branch survives -- and
`_head_sha`, `_worktree_status` beside the `_worktree_dirty_files` list its other callers read,
`_committed_paths_since`, and `_revision_contains_path` from `git/verification/probes.py` -- those are what the
write contract is decided by, so a mock for any of them has to land there. The status form is the one a publication
asks, because an unreadable tree and a clean one are the same empty list and only one of them may be pushed over.
Opening a round adds two more: `_remote_branch_tip` from `git/authentication.py`, read before the spawn so the base
the round's work is finally measured against is the remote's answer rather than a local ref the round could repoint,
and `_commit_present` beside it, because the diff that spends that answer is local -- an id the store lacks is fetched
in through `_authed_target_fetch` from the same owner, or recorded as no base at all.
Publishing adds the
push from that same owner and the commit subject and PR title builders from `git/publication/`, the same
owners every dev PR is opened through. It takes one restorer question of its own: an issue
carrying a `pr_number` is discussed on the branch that PR is open against, so a pruned local ref is rebuilt by
`_ensure_pr_worktree` from the PR head rather than by `_ensure_worktree` from the base branch, which would drop the
PR's commits out of the tree the round reads. A publication in flight answers that question the same way and earlier,
which is why `_remote_branch_tip` is read a second time there: the marker precedes the push and `pr_number` follows
the PR, so a crash between them leaves a pushed branch and an open PR with nothing pinned naming either -- and if the
worktree and the local ref are gone as well, only the remote can say the branch exists to restore from.

Most stage handlers run the user-content drift hook (`_compute_user_content_hash` → `_detect_user_content_change`) so
an out-of-band human edit re-routes the issue back to `workflow:decomposing` (when no dev session exists yet), resumes
the locked dev session with the updated body (implementing, validating, in_review, resolving_conflict), or unwinds
back to `workflow:validating` without resuming dev (documenting). Both halves of that hook sit on the
`workflow/engine/drift.py` owner the stage leaves import directly, so a patch aimed at the hook targets that owner.
`_handle_fixing`, `_handle_question`, and `_handle_discussion` skip the drift hook — see
[`state-machine.md#user-content-drift-detection`](state-machine.md#user-content-drift-detection) for the per-handler
routing.

For per-stage internal flow — pickup, drift handling, decomposing, ready, blocked, umbrella, implementing,
documenting, validating, in_review, fixing, resolving_conflict, question, discussion — see
[`state-machine.md#stage-handlers`](state-machine.md#stage-handlers).

## Agent subprocess (`agents.run_agent`)

`run_agent(backend, prompt, cwd, ...)` dispatches to the per-backend runner (`codex.run_codex` /
`claude.run_claude`); `backend` is one of `"codex"` / `"claude"` and is re-validated at call time so a
misuse fails loudly. Both runners return a unified
`AgentResult(session_id, last_message, exit_code, timed_out, stdout, stderr, interrupted, usage)`. `interrupted`
(default `False`) flags a run the runner observed exiting on SIGTERM/SIGKILL — the shape the orchestrator's
shutdown sweep (`terminate_all_running`) produces when it kills an in-flight agent group — and is distinct
from `timed_out` (the orchestrator's own `AGENT_TIMEOUT` firing). `usage` (default `None`) is the parsed
`UsageMetrics` -- the one on `observability/usage/metrics.py` -- that `recording.record_agent_exit` attaches during a
tracked run so callers can read token / cost metrics off the result without re-parsing stdout; it stays `None` for a
result that never flowed through
`_run_agent_tracked` or whose usage parse failed (fail-open). The developer (implementing), reviewer
(validating), decomposer (decomposing), question, and discussion handlers consume it: `_accumulate_issue_usage` — in
`workflow/engine/usage.py`, which each of those handlers binds directly — folds
each run's `usage` into the per-issue `issue_agent_runs` / `issue_total_tokens` / `issue_total_cost_usd` /
`issue_cost_sources` counters on the pinned state
([`state-machine.md#pinned-state`](state-machine.md#pinned-state)); at each terminal (PR merge / reject, umbrella
close, closed question, and both discussion endings — the verdict the humans leave on the plan PR, and a close of the
issue before one exists) `_format_issue_usage_verdict` beside it reads those counters back into one visible receipt
comment — the sole read-side consumer, and nothing gates on the figure. `CodexResult` is kept as a
transitional alias.

The role command specs (`DEV_AGENT` / `REVIEW_AGENT` / `DECOMPOSE_AGENT`), their parsing, the durable per-session
lock, and the resume mechanic are documented in
[`workflow/command-specs.md`](workflow/command-specs.md). Which stage spawns which role is in
[`workflow/roles.md`](workflow/roles.md). What follows is the subprocess shape only.

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

### Hardened local git (`git.commands._git_hardened`)

Every local git operation inside a worktree the agent can write to runs through this envelope: the `-c` overrides
that neutralize `core.hooksPath` / `core.fsmonitor` / `credential.helper` / commit signing, `GIT_CONFIG_GLOBAL` and
`GIT_CONFIG_SYSTEM` detached from `~/.gitconfig` and `/etc/gitconfig`, and the orchestrator's committer identity.

Git's own output is decoded with `surrogateescape` rather than strictly, for the same class of reason. A repository
path is bytes, and a committed file whose name is not valid UTF-8 makes a strict decode raise inside `subprocess`
before any caller sees a return code -- taking the tick out where the probe should have reported the extra path and
parked the artifact it invalidates.

It also turns object replacement off — `GIT_NO_REPLACE_OBJECTS=1` for `refs/replace/<oid>` and
`GIT_GRAFT_FILE=/dev/null` for the graft file. Neither of those is config, so nothing above reaches them, and each is
writable by an agent whose linked worktree shares the clone's refs and git dir. Left on, they change what git says a
commit's tree and parents ARE without changing the commit anyone named: a decomposer could stand a synthetic commit
carrying its code in for the base and have the plan check measure against that, while the push — which names the real
SHA — carries the code as well. Both are disabled for every hardened read, so a probe and the push it gates are
talking about the same objects.

Two more sit on the working-tree operations themselves rather than in the envelope, because neither is config either.
`core.worktree` in a linked worktree's own `config.worktree` — which an agent
enables by writing `extensions.worktreeConfig` into the clone it shares — points every path operation at any directory
it likes, and a `-c core.worktree=` override does NOT win against it, so the tree is named with `--work-tree` instead:
by `verification/probes._worktree_status`, which would otherwise report on a clean shadow checkout, and by the
`reset --hard` in `worktrees/creation._move_branch_onto`, which would otherwise report success and move the ref while
writing the reviewed commit's files into that other directory -- leaving the issue's checkout on the plan it had, the
handoff baseline naming a tip the tree is not on, and whatever was in the redirected directory overwritten.
And `assume-unchanged` / `skip-worktree` are bits on an index entry: git honours them by not comparing the file, so a
tracked path the agent rewrote reports clean. Those entries are read separately (`git ls-files -v`) and answered as
paths AND as a withheld `readable`, so a caller refusing on what git listed and one that has to prove the tree empty
both fail closed on them.

## Push path (`git.authentication._push_branch`)

The orchestrator (not the agent) pushes. The push is hardened against the agent-controlled worktree:

- Token delivered via `GIT_ASKPASS` tempfile, never argv.
- Detaches from `~/.gitconfig` and `/etc/gitconfig` (`GIT_CONFIG_GLOBAL=/dev/null`, `GIT_CONFIG_SYSTEM=/dev/null`).
- Disables `core.hooksPath`, `credential.helper`, `core.fsmonitor`.
- Refuses to push if the config the push resolves — the worktree's local config plus any `include.path` file or
  per-worktree `config.worktree` it pulls in, with global/system detached — carries any `url.*.insteadOf` /
  `pushInsteadOf` rewrite or any `http.*` proxy/TLS setting (e.g. `http.proxy`, `http.sslVerify=false`) that could
  tunnel the token-bearing push through an attacker proxy or disable certificate verification. Env-var proxies
  (`https_proxy`) are operator-set and stay honored — only agent-writable config-file transport is rejected.
- Pushes via an explicit refspec (no upstream stored): `HEAD:refs/heads/<branch>` by default, or
  `<revision>:refs/heads/<branch>` when the caller names the commit it means. A caller that decided to push by
  inspecting a commit — the discussion stage's plan publication — names it, because `HEAD` between the reading and
  the push is not necessarily the commit that was checked.

## Observability

Four independent observability surfaces — an opt-in audit event log, a project-local analytics JSONL sink, an opt-in
(default-off) trajectory JSONL sink that `record_agent_exit` fills with redacted, head/tail-truncated per-run reasoning
trajectories — each carrying a denormalized run-level token-usage / cost summary (plus a claude-only per-turn
breakdown) alongside the step timeline — and an operator-deployed Postgres aggregation target (with a Streamlit
dashboard and the `orchestrator/observability/usage/` parser that feeds it). The trajectory sink has its own separate
Streamlit page — the file-backed trajectory viewer (`orchestrator/apps/trajectory_dashboard.py` over the pure
read model under `orchestrator/observability/trajectory_viewer/`),
which reads the JSONL directly (usage and cost included) and needs no Postgres.
None of them feed back into dispatch: workflow correctness keys off the pinned state JSON and the workflow label, so
every surface is observation-only and safe to truncate, rotate, or delete. That is also why all four migrate into
`orchestrator/observability/` — the destination and the rules its owners inherit are described under
[Top-level layout](#top-level-layout).

For the per-sink schema, event-kind tables, append / retention / rotation semantics, the analytics-DB compose layout,
the sync / read-model / dashboard wiring, and the usage parser's cost-precedence rules, see
[`observability.md`](observability.md).

## Summary of "what runs when"

- **`cli.main` polling loop** — long-lived Python process. Trigger: manual start (or wrapper). Cadence: every
  `POLL_INTERVAL`s.
- **`workflow.tick(gh, spec)`** — function call. Trigger: each loop iteration. Cadence: once per tick per configured
  `RepoSpec`; multi-repo fans out across a `ThreadPoolExecutor`, single-repo stays in-thread.
- **`_refresh_base_and_worktrees(gh, spec)`** — function call. Trigger: start of each `workflow.tick`. Cadence: once
  per tick per repo: one `git fetch <spec.remote_name> <spec.base_branch>`, then per-worktree dispatch (pre-PR
  worktrees rebase directly; PR-having worktrees behind base are rebased + pushed in the refresh itself via
  `_sync_pr_worktree_to_base` and routed to `workflow:validating` on success, with `workflow:resolving_conflict`
  reached when the auto rebase actually leaves conflicted files).
- **`_handle_*` per issue** — function call. Trigger: issue's workflow label. Cadence: once per tick per open issue;
  concurrent up to `spec.parallel_limit` per repo and `MAX_PARALLEL_ISSUES_GLOBAL` across all repos. No-agent family
  buckets (`workflow:blocked` / `workflow:umbrella`) are cap-exempt.
- **decomposer agent (`DECOMPOSE_AGENT`)** — subprocess (fresh or resumed). Trigger: `_handle_decomposing` (retry
  budget OK) or HITL resume. Cadence: one shot per tick when needed. The same role spec also backs the two
  operator-applied conversation stages, which pin their own keys and resume their own sessions rather than a
  decomposing one: `_handle_question` (`question_agent` + `question_session_id`, read-only for the whole
  conversation) and `_handle_discussion` (`discussion_agent` + `discussion_session_id`,
  `agent_role="decomposer"` / `stage="discussion"`, spawned fresh on the opening round and resumed on each trusted
  human reply after it — read-only until a human confirms the design on the thread, and from there allowed exactly
  one commit of `plans/issue-<number>.md` for the stage to publish).
- **implementer agent (`DEV_AGENT`)** — subprocess. Trigger: `_handle_implementing` (no commits yet, retry budget OK)
  or HITL resume. Cadence: one shot per tick when needed.
- **reviewer agent (`REVIEW_AGENT`)** — subprocess (fresh session). Trigger: `_handle_validating`, round < max.
  Cadence: one shot per tick.
- **dev-fix agent** — subprocess (resumed dev session). Trigger: reviewer says CHANGES_REQUESTED (dispatched from
  `_handle_validating` after the relabel to `workflow:fixing`), or fresh in_review PR feedback (dispatched from
  `_handle_fixing` after the quiet window) — both run with `stage="fixing"` and bounce back to `workflow:validating`
  for re-review. Cadence: one shot per tick.
- **`_handle_resolving_conflict`** — function call. Trigger: issue label `workflow:resolving_conflict` (operator
  relabel, refresh-time conflicted rebase, or the `fixing` worktree-drift dead-lock breaker when a stuck
  validating-route transient fix-loop is out of sync with the PR head — behind base or an unpushed local rebase); also
  fires on closed-`workflow:resolving_conflict` issues from the polling sweep. Cadence: once per tick per such issue.
- **dev-conflict agent** — subprocess (resumed dev session). Trigger: `_handle_resolving_conflict` and `git rebase`
  left conflicts. Cadence: one shot per tick.
- **`_handle_question`** — function call. Trigger: issue label `question` OR closed-`question` issue from the polling
  sweep. Cadence: once per tick per such issue.
- **question agent (`DECOMPOSE_AGENT` backend)** — subprocess (read-only). Trigger: `_handle_question` (no prior
  session OR new human comment on a parked Q&A). Cadence: one shot per tick when needed.
- **`_handle_discussion`** — function call. Trigger: issue label `discussion` OR closed-`discussion` issue from the
  polling sweep, which keeps yielding that issue every pass while its plan PR is still open. Cadence: once per tick
  per such issue, and the tick spawns nothing at all when the plan PR is already published, when the park on the
  thread is still unanswered, or when the checkout is one no round may open on.
- **discussion agent (`DECOMPOSE_AGENT` backend)** — subprocess. Trigger: `_handle_discussion` (the conversation's
  opening round, or a trusted human reply past the consumed watermark on a parked one). Cadence: one shot per tick
  when needed. No developer or reviewer ever runs on this label: the one thing the stage produces is the plan PR, and
  having that plan built is an operator relabel to `workflow:implementing`.
- **`git push`** — subprocess. Trigger: after dev produces clean commits, or after a discussion round commits the
  confirmed plan and the branch reads as exactly that one file. Cadence: per fix; per discussion, once the humans
  have confirmed the design — with a publication a tick died inside re-attempted on the next tick from the in-flight
  marker, and one whose push itself failed re-attempted on the human's reply to that park.
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
   │  orchestrator process  (python -m orchestrator)                      │
   │  ───────────────────────────────────────────────────                 │
   │   cli.main over orchestrator/runtime/                                │
   │     startup: build per-spec [(spec, GitHubClient), ...] from         │
   │              config.default_repo_specs(); ensure_workflow_labels;    │
   │              build one shared IssueScheduler(global_cap, per_repo)   │
   │     loop every POLL_INTERVAL s:                                      │
   │       1. self-restart check (origin/<ORCHESTRATOR_BASE_BRANCH>       │
   │          moved & touches orchestrator/?)                             │
   │       2. run_tick(state, clients, scheduler):                        │
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
   │       family-aware (`workflow:decomposing` / `workflow:blocked` /    │
   │         `workflow:umbrella` / unlabeled) →                           │
   │         ONE bucket submit per repo that drains sequentially          │
   │         (cap-exempt when every family issue is                       │
   │         `workflow:blocked` or `workflow:umbrella`)                   │
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
