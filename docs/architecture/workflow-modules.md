# Workflow modules

This page maps `orchestrator/workflow/`: the package API, the state owner beside it, the `engine/` owners one tick is
composed of, and the stage subpackages the label dispatch routes into. It is split out of
[`../architecture.md#top-level-layout`](../architecture.md#top-level-layout), which keeps the top-level map and the
naming rules that hold for the tree as a whole. The packages this one decides with are in
[`platform-modules.md`](platform-modules.md).

Each entry below is the responsibility its module owns, and it answers there and on no second site. What a stage does
per label is in [`../state-machine.md`](../state-machine.md); what the agent it spawns is prompted with and allowed
to write is in [`../workflow.md`](../workflow.md).

## Enforced boundaries

Each rule below names the check that holds it. The last is a convention the tree keeps rather than one a test can
see, and is called out as such.

- **The package API is six names.** Five are `workflow/state.py`'s own objects, re-exported and pinned by identity so
  the graph a caller reads cannot fork; the sixth is `tick`. In-tree callers name the owner, and the re-export is for
  callers outside the tree — `tests/workflow/test_imports.py`.
- **`tick` resolves the engine inside the call.** `github/` and `git/` import `workflow/state.py` for the label
  vocabulary they are typed by, and a submodule import runs this initializer first, so an engine import at module
  scope would send `github/labels.py` and `github/issues.py` back into the client they are still initializing.
  Importing the package therefore costs the initializer and the state owner, and pulls in neither the engine, the
  stage tree, nor the config, analytics, git, and GitHub graphs — `tests/workflow/test_imports.py` probes both import
  paths in a clean interpreter, and `tests/repository/test_layering.py` holds the direction under it.
- **The stage handlers are resolved at call time.** `engine/dispatch.py` pairs each label with the module its handler
  lives on and imports it when it dispatches, as `engine/pickup.py` does for the stage it starts an issue on: the
  stage tree imports `engine/`, so a module-scope bind would point that edge back at itself.
  `tests/workflow/engine/test_dispatch.py` pins that the handler is read off its owner per call rather than bound at
  import, and `tests/workflow/stages/test_imports.py` that every labelled target lands on a stage package here.
- **Two operator log channels, spelled literally.** The engine and stage owners report on `orchestrator.workflow`,
  and `workflow/state.py` on `orchestrator.state_machine`. A module moved between packages does not take its channel
  with it — `tests/workflow/test_imports.py` walks the package and checks every owner that declares a logger.
- **Nothing sits flat beside the package.** The retired spellings — `orchestrator.state_machine`,
  `orchestrator.workflow_drift`, `orchestrator.workflow_messages`, and the export and dependency manifests — resolve
  to nothing (`tests/workflow/test_imports.py`), and the repo-wide naming rule in
  `tests/repository/test_package_layout.py` keeps the `workflow_` family from returning one level down.
- **A borrowed helper keeps its owner (convention).** Stage-private helpers stay in the stage that owns them, and
  what more than one stage reaches for stays where it is defined with the borrower naming that owner — fixing's quiet
  window imports `_comment_created_at` from `in_review/watermarks.py`. No check enforces this one; what keeps it is
  that a second copy of a shared helper would drift from the owner and from the tests aimed at it.

## The map

`engine/` and every stage package publish nothing, so naming one costs no owner behind it. Each stage package is
listed with the labels its handlers answer for: eight own one label each, and `decomposition/` owns four — `run.py`
for `workflow:decomposing`, `blocked.py` for both `workflow:ready` and `workflow:blocked`, and `umbrella.py` for
`workflow:umbrella`. That is twelve of the dispatch table's thirteen targets; the thirteenth is the unlabeled entry,
which `engine/pickup.py` answers rather than a stage package.

```
workflow/                   publishes the two label vocabularies, `guard_transition` and `is_allowed_transition`,
                            `IllegalTransition`, and the per-repo `tick`
  state.py                  the `WorkflowLabel` / `ControlLabel` vocabularies, strict label coercion, the declared
                            transition graph and the guard over it, and the `workflow:` namespace boundary
  engine/                   what every stage is driven by
    comments.py             the orchestrator marker, the capped id ledger both posters write, and the trusted-author
                            thread read every prompt quotes
    dispatch.py             one tick's pollable issues turned into handler calls: the hard-skip filter, the family /
                            fanout partition and its cap exemptions, the per-worker refetch, and the timed dispatch
    drift.py                the user-content hash and the six filters that keep content nobody wrote out of it, the
                            dev resume a drift earns, and the decomposition reset the pre-implementation route takes
    guards.py               what a finished agent run may leave behind: the shutdown-interruption and freshly-read
                            pause refusals, and the awaiting-human park
    messages.py             the markers read out of an agent's last message, and the redact-before-truncate stderr
                            diagnostics a park carries when there was none
    pickup.py               an unlabeled issue's first tick: the author allowlist, the `DECOMPOSE` route, and the
                            greeting / hash / label / state order a start publishes in
    prompts.py              the prompt builders the stages share, the header, notes, and placeholders they are
                            assembled from, and the single-decision comment
    terminals.py            the merged, rejected, and human-closed arcs, the stamp / receipt / label / write tail they
                            share, and the two entry-time finalizers
    tick.py                 one repo's polling pass: the base refresh, the community-contribution sweep, the
                            skill-catalog emission, and the scheduler handoff or in-tick execution behind them
    usage.py                the tracked agent run: the request model, the audit spawn / exit pair, the analytics
                            record, the `skill_triggered` emission, and the per-issue counters a terminal receipt is
                            read off
  stages/
    conflicts/              `workflow:resolving_conflict`
      handler.py            the order one tick asks its questions in: the missing-`pr_number` park, the terminal arcs,
                            the body-edit resume, and the rebase behind them
      routing.py            the awaiting-human resume and `MAX_CONFLICT_ROUNDS` cap that gate the rebase, plus the
                            worktree it runs in
      guards.py             the worktree restore and the two probes that prove a stale PR head is safe to
                            force-publish over
      divergence.py         the park a behind-base worktree earns, the one lease that excuses it, and the
                            crash-recovered push
      rebase.py             the branch and base fetches, the rebase, its `merge_attempt` event, and the three-way
                            disposition
      publication.py        the dirty park, the no-op flip, the rebased-head push, and the hand-off of real conflicts
                            to the dev
      resume.py             the three dev-resume entry points, the shared run, and the `/orchestrator continue`
                            classification
      outcomes.py           the interrupt / timeout / mid-rebase parks read before HEAD, and the push a completed
                            resolution earns
      transitions.py        the park-and-write pair and the pushed-round tail every exit shares
      models.py             the frozen records the owners hand each other
      state.py              the counter keys they share
    decomposition/          `workflow:decomposing`, `workflow:ready`, `workflow:blocked`, and `workflow:umbrella`
      run.py                one `decomposing` tick: the drift / recovery / kill-switch order before the agent, and the
                            pause, dirty-worktree, and interruption checks after it
      session.py            the locked decomposer session: the spec read, the fresh spawn that pins it, the
                            human-reply resume, and the drift reset that retires it
      manifest.py           the fenced-block envelope rules, the JSON decode, and the parse entry point the stage
                            routes on
      validation.py         what a `split` payload must satisfy: the child cap, each child's shape, and the acyclicity
                            of the graph they declare
      outcomes.py           the three dispositions of a finished reply: the unparsed park, the `single` finalize, and
                            the `split` hand-off
      split.py              the crash-safe order a `split` manifest becomes child issues in, and the summary / label /
                            activation tail
      recovery.py           what a tick that died mid-split left behind: the stale-manifest markers, the orphan-child
                            repair, and the incomplete park
      parents.py            the fresh child scan, the rejected and manually-closed parks it earns, and the parent's
                            own drift reroute
      activation.py         the dep-graph walk that releases the next children and the held-dependency line it logs
      blocked.py            the `workflow:blocked` poll and the `workflow:ready` handoff to implementing with its
                            consumed-comment ratchet
      umbrella.py           the `workflow:umbrella` poll and the close its all-done branch earns instead of an
                            implementation pass
      models.py             the run plan and its worktree policy, the locked session, the split plan, and the child
                            scan
      state.py              the pinned-state field names the owners share, the held-child alias, and the
                            issue-reference renderer
    discussion/             `discussion`
      handler.py            the order one round asks its questions in: whether the conversation is over, whose turn it
                            is, what the checkout holds, and what the round left behind
      terminal.py           what the plan PR has become: the merged and closed-unmerged finalizes, the open-PR hold,
                            the marker lookup that finds a PR a crash left unrecorded, and the pre-PR close
      session.py            the pinned agent and session a conversation is locked to, the filter its replies are drawn
                            through, and the prompt paired with the replies it read
      run.py                one round in the issue's own worktree, the restorer that checkout is rebuilt by, and the
                            branch and SHA it records opening on
      outcomes.py           the pause, timeout, write, and response decisions one finished round is classified by, and
                            their routing
      publication.py        which commits are this stage's to publish, the push and found-or-opened plan PR they earn,
                            and the records handed to the next tick
      parks.py              every way the stage hands the issue back, and the funnel that stamps each park's reason
                            and restores the consumed ceiling
      models.py             the run, the agent identity and session, the prompt and its replies, the round, the
                            outcome, and the publication artifact
      state.py              the park reasons and wire keys, the plan path and the commit its PR carries, the
                            open-round and in-flight publication markers, and the three park predicates
    documenting/            `workflow:documenting`
      handler.py            the order one final-docs tick asks its questions in
      preconditions.py      the terminals, the missing-`pr_number` guard, the parked-no-input fast path, and the
                            refused bare continue
      run.py                the branch refresh and diverged-worktree guard, plus the resume, recovered-commit, and
                            fresh-spawn shapes
      outcomes.py           the timeout / dirty / commit / `DOCS: NO_CHANGE` order a finished run is read in
      publication.py        the push, the docs watermarks it stamps, and the PR notice it posts
      drift.py              a body edit mid-hop: the dropped approval, the unwind sentinel, and the relabel to
                            `workflow:validating`
      drift_reset.py        the fetch / probe / hard-reset that puts the worktree back on the PR head, and the parks
                            each failure earns
      handoff.py            the `pr_last_comment_id` ratchet that keeps in_review from replaying a consumed reply, and
                            the relabel
      parks.py              the shared awaiting-human park and the missing-PR, dirty-tree, and question parks
      models.py             the frozen records the owners hand each other
      state.py              the pinned-state keys they share
    fixing/                 `workflow:fixing`
      handler.py            the order one tick asks its questions in, plus the preflight terminals, the
                            missing-`pr_number` park, and the commit the no-feedback bounce publishes before it
                            hands the PR back to the reviewer
      feedback.py           the rescan past the three in_review watermarks and the narrower ratchet a consumed batch
                            advances them by
      bookmarks.py          the `pending_fix_*` ids a replay rebuilds the triggering batch from, and the clear each
                            round earns
      resume.py             the quiet window, the dev run, the ACK fast path, and the `workflow:validating` relabel a
                            pushed fix earns
      parked.py             the four answers an `awaiting_human` tick can reach and the order they are asked in
      continue_command.py   `/orchestrator continue` on a parked fix: the replay, the two refusals, and the guidance
                            passthrough
      drift.py              the `workflow:resolving_conflict` reroute a stuck validating-route park earns when its
                            worktree has fallen behind base
      models.py             the frozen records the owners hand each other
      state.py              the pinned-state keys they share
    implementing/           `workflow:implementing`
      handler.py            the order one tick asks its questions in
      spawn.py              awaiting-human vs active, the restorer the checkout comes back from, the
                            recovered-worktree shortcut and the certified baseline it stands down for, and the
                            retry-gated fresh spawn
      session.py            the three session retirements, the per-issue 24h spawn cap, and the fresh-spawn prompt
      session_read.py       the locked session read plus the stale / overflow / quota classifiers and the blockquote
                            they quote with
      resume.py             the two resume entry points and the historical call shape they keep
      execution.py          one resume, its poisoned-session retry, and what each attempt is allowed to persist
      worktree.py           the checkout a resume runs in, restored when reaped
      disposition.py        the `before_sha` publish / timeout-park decision, the certified floor a clean exit is
                            credited against, and the timeout park's own next-tick recovery
      publication.py        the push, the PR reuse (re-bodied when it was opened elsewhere) or open, and the
                            validating handoff with its counter resets
      parks.py              the session-limit, question, silent-failure, and dirty-tree parks
      drift.py              a body edit mid-implementation: the resume it earns and the `ACK:` that answers it
      drift_preflight.py    a pre-session edit and the quiet timeout recovery
      continue_command.py   `/orchestrator continue` on a parked issue
      read_only_relabel.py  the `question` / `discussion` relabel guards, and the reconcile that keeps an accepted
                            plan handoff in step with its PR
      models.py             the frozen records the owners hand each other
      state.py              the pinned-state keys and CLI marker tuples they share
    in_review/              `in_review`
      handler.py            the order one tick asks its questions in, and the missing-`pr_number` park asked before
                            the rest
      feedback.py           the four surfaces scanned before the drift check, their author filters, and the park that
                            stays silent for the base-sync retry loop
      fixing_route.py       the pending-fix bookmarks, the hash refresh, and the `workflow:fixing` relabel
      drift.py              a body edit on an open PR: the unread PR conversation captured first, the dev resume, and
                            the `workflow:validating` return
      merge_gate.py         the unmergeable park and the one HITL ready-ping an approved, unvetoed head earns per head
                            SHA
      watermarks.py         the one-way issue-side ratchet and the legacy seed a manually-relabeled issue needs
      models.py             the per-tick handles and the drift-resume record
      state.py              the issue-side watermark key they share
    question/               `question`
      handler.py            the order one tick asks its questions in, the closed-issue finalize that outranks them,
                            and both worktree teardowns
      run.py                the resume and fresh-spawn routes, the tracked spawn they share, and the park funnel every
                            exit lands on
      session.py            the locked question-agent identity, the trusted-reply consume, and both prompt builders
      outcomes.py           the read-only violations checked before any answer, and the park each outcome earns
      models.py             the tick record, the locked session, and the outcome
      state.py              the park reasons and pinned-state keys they share
    validating/             `workflow:validating`
      handler.py            the order one review tick asks its questions in, and the terminals it opens with
      reviewer.py           the round cap, the tracked reviewer spawn and its two refusals, and the verdict fan-out
      approval.py           the verify gate, the approval comment, the optional squash, and the in_review watermark
                            seed before the `workflow:documenting` relabel
      verify.py             how a non-ok verify result reads and the park it earns
      watermarks.py         the seed walk past leading orchestrator comments and the ratchet that never regresses one
      requested_changes.py  the PR feedback and `workflow:fixing`-labeled dev fix, plus the no-VERDICT park
      dev_fix.py            what a finished dev fix leaves behind: the stranded-commit probe, the push, and the round
                            bump
      awaiting.py           the three park-reason claims on a human reply and the dev attempt they fall through to
      awaiting_resume.py    the order those claims are asked in and the resume none of them wanted
      drift.py              a body edit mid-review, the three parks that defer, and the consumed-thread watermark
      drift_outcomes.py     the `ACK:` reply that must not park, over the shared fix disposition
      recovery.py           the silent retry of a push race or dev timeout, and the one sentence a park that
                            healed itself owes the thread
      models.py             the frozen records the owners hand each other
      state.py              the pinned-state keys, park reasons, and outcome tokens they share
```
