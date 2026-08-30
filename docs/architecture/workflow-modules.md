# Workflow modules

This page maps `orchestrator/workflow/`: the package API, the state owner beside it, the `engine/` owners one tick is
composed of, the `late_split/` domain the late size gate is defined by, and the stage subpackages the label dispatch
routes into. It is split out of
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
  import, and `tests/workflow/stages/test_imports.py` that every labelled target lands on a stage package here. The
  late size gate's own refusal is resolved the same way and for the same reason — it lives on a stage owner, so the
  dispatcher imports it when it routes.
- **Two operator log channels, spelled literally.** The engine, `late_split/`, and stage owners report on
  `orchestrator.workflow`, and `workflow/state.py` on `orchestrator.state_machine`. A module moved between packages
  does not take its channel with it — `tests/workflow/test_imports.py` walks the package and checks every owner that
  declares a logger.
- **Nothing sits flat beside the package.** The retired spellings — `orchestrator.state_machine`,
  `orchestrator.workflow_drift`, `orchestrator.workflow_messages`, and the export and dependency manifests — resolve
  to nothing (`tests/workflow/test_imports.py`), and the repo-wide naming rule in
  `tests/repository/test_package_layout.py` keeps the `workflow_` family from returning one level down.
- **A borrowed helper keeps its owner (convention).** Stage-private helpers stay in the stage that owns them, and
  what more than one stage reaches for stays where it is defined with the borrower naming that owner — fixing's quiet
  window imports `_comment_created_at` from `in_review/watermarks.py`. No check enforces this one; what keeps it is
  that a second copy of a shared helper would drift from the owner and from the tests aimed at it.

## The map

`engine/`, `late_split/`, and every stage package publish nothing, so naming one costs no owner behind it. Each
stage package is listed with the labels its handlers answer for: eight own one label each, and `decomposition/` owns
four — `run.py` for `workflow:decomposing`, `blocked.py` for both `workflow:ready` and `workflow:blocked`, and
`umbrella.py` for `workflow:umbrella`. That is twelve of the dispatch table's thirteen targets; the thirteenth is the
unlabeled entry, which `engine/pickup.py` answers rather than a stage package.

```
workflow/                   publishes the two label vocabularies, `guard_transition` and `is_allowed_transition`,
                            `IllegalTransition`, and the per-repo `tick`
  state.py                  the `WorkflowLabel` / `ControlLabel` vocabularies, strict label coercion, the declared
                            transition graph and the guard over it -- including the one edge OUT of a terminal,
                            `done` to `rejected`, which the umbrella cancelled between its label write and its
                            close is corrected over -- and the `workflow:` namespace boundary
  engine/                   what every stage is driven by
    comments.py             the orchestrator marker, the capped id ledger both posters write, and the trusted-author
                            thread read every prompt quotes
    dispatch.py             one tick's pollable issues turned into handler calls: the observation a refused
                            fan-out submit was carrying -- latched from the poll's own closed reading and dropped
                            again only where the RECORD positively says there is nothing to end, since the probe
                            that asks is a request and a request can fail -- the same reading BOUND to an admitted
                            one instead, since the worker refetches and a reopen in that window would answer
                            differently -- the hard-skip filter a held close
                            observation outranks (it is not this tick's reading, so a park, a reopen, and a relabel
                            off the swept labels each leave it standing -- an owner the enumeration never yields is
                            added by number), the family /
                            fanout partition and its cap exemptions, the per-worker refetch and the sequential path's
                            own classify-and-refetch beside it (a CLOSED issue is routed by any of the four cleanup
                            labels, while only the two an adjudication RUNS under earn the refetch an OPEN issue
                            costs, since neither reading of one may be taken from the poll), the hold that keeps a
                            closed reading across the pass that would spend it -- a pass can fail to spend one
                            without failing at all -- the close latched by the ENUMERATION that read it AND
                            written down there, so a worker already holding the issue is answered for the whole
                            window between that reading and the submit that carries it and an accepted task that
                            never starts still leaves a receipt on the thread, the same observation taken at the
                            REFETCH by both paths that take one -- an issue open when it was listed and closed by
                            the time it is read carries a reading nothing else holds -- the record-driven pair
                            asked ahead of every handler (an authorized restart first, then the refusal a cancelled
                            cycle earns, since a restart between its label write and its retirement wears a
                            live-looking label over a record that still says cancelled), the unlabeled issue
                            that already carries a pinned comment and so is one this orchestrator has already
                            MET -- left where a human's label removal put it rather than greeted a second
                            time, since a second pinned comment is shadowed by the first from the moment it
                            is written while the finished workflow in that first one goes on deciding, the
                            park re-applied behind
                            the mark that reading was waived for, the cleanup submission
                            wrapped in the settlement its observation is owed -- kept by a pass that failed, by one
                            nothing ever called, and by one that RAN and left the ending owed under a label no
                            query asks for, settled everywhere else (a swept label reaches the owner on its own
                            cadence), and shared by all three tick paths
                            with the refetch inside the hold --
                            the refusal that keeps a relabelled late adjudication off every other
                            stage's handler, the reading owed for a size-gate pair frozen and never counted --
                            taken ahead of the handler that would otherwise run against a pull request still
                            standing where the gate froze it, and only on the stage the record itself names --
                            and the timed dispatch
    observations.py         the closes a poll saw and could hand to no worker: the process-wide latch the run
                            holding the issue asks before every step the remote keeps (a close and a reopen inside
                            one of its own steps is the reading GitHub cannot give back), the settle a pass that
                            RAN takes -- which moves the per-owner generation with it -- the claim one receipt is
                            posted under, and the memo the attempt that landed a durable receipt writes against
                            the generation it was claimed at -- so a refused post is retried by the next poll
                            rather than lost, two polls in the check/post gap post once, and a settlement landing
                            mid-post leaves no memo to suppress the NEXT reading's receipt, and a receipt that
                            LANDS owes the thread walk again -- the window a worker
                            retiring a cycle holds across its own write, which is what
                            keeps a poll from calling a reading spent against a record whose cycle identity has
                            just come off, is the only place that cycle can still be read, and decides what it
                            observed as it CLOSES, under the lock that closes it, so no interval is left between
                            the answer and the exit for a poll to latch a close in; and the
                            once-per-owner-per-process claim that bounds the thread scan recovering an observation
                            a DEAD process was holding, held for the length of the walk and handed back where it
                            raised
    drift.py                the user-content hash and the six filters that keep content nobody wrote out of it, the
                            dev resume a drift earns, and the decomposition reset the pre-implementation route takes
                            -- manifest, session, and every claim that manifest made about the children it created
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
  late_split/               the late size gate's own domain: what one generation IS, apart from anything that drives
                            one
    formats.py              what any late value has to look like -- a real integer, a git object id, a bounded
                            single-line target -- and the one refusal every owner raises over it
    models.py               the phase / verdict / failure / resource vocabularies, the boundaries a split
                            transaction owns among them, the frozen generation record with the transforms that
                            return a new one -- including the boundary move that refuses to rewind out of one of
                            those, which is the rule every retry above the transaction is held to, and the
                            post-publication entry no record carries unless it can name the stage, the pull
                            request, and the head at once -- and the lineage bound it is read against
    identity.py             the monotonic cycle and generation identities, the child depth the bound still allows,
                            the two local content fingerprints a scope edit and a trusted answer are told apart by,
                            and the bounded name-free print one ledger entry is reported under
    payloads.py             what one hand-edited or older pinned late field reads back as: one reader per field
                            contract -- identity, count, depth, object id, literal flag, member, free text
    ledgers.py              what the two external ledgers read back as, the exact entry shape one of ours has, the
                            verbatim copy anything else is preserved through, and the all-or-nothing reading of the
                            ordered child register, whose entries are positional and so may not be skipped past
    state.py                the `late_*` pinned keys -- the frozen evidence, the publication provenance, the
                            ledgers, and the cancellation and pending-owner-check markers -- and the round trip
                            through them that leaves a legacy comment untouched and an unreadable obligation
                            intact, plus the two keys
                            deliberately outside the group a cleared generation drops: the cycle a retirement
                            dropped, and the two-phase terminal record beside it -- the decision naming the
                            cycle a `rejected` is owed for, and the proof that one landed on the issue, which
                            together are the only durable evidence that the label an operator removes to
                            authorize a restart was ever applied, and which an attempt alone is not
    lineage.py              what a child born of a split inherits and reads back fail-closed: the lineage it
                            continues, the adjudication that created it, the snapshot ref and exact commit it may
                            reuse, and the slice it owns -- plus the two markers that claim a lineage outside the
                            pinned comment, the receipt the transaction stamps into a child's body and the one a
                            reclamation leaves on its thread, and the reader that turns the first back into a
                            lineage when the pinned write that would have recorded one never landed
    exemption.py            the one commit an accepted candidate publishes under -- written, read, and compared
                            fail-closed, and deliberately outside the group a cleared generation drops
    restart.py              the two-phase restart marker: the closed pair of labels it may apply, the cycle it
                            mints, the whole-marker check that decides whether the one a crash left may still be
                            believed, the settled-ledger precondition retirement refuses without, and the fresh
                            cycle it projects
    events.py               the seven families, the per-family schema an event is refused against, the member each
                            detail has to actually be, and the closed vocabulary a verdict category is chosen from
    validation.py           what a generation has to prove before a record of it may be written: the required
                            identity, the format of every field a sink would carry, the publication a marker has to
                            still be able to name, and what each family's own record has to be readable without
    records.py              the bounded payload both sinks carry -- including the closed pair every family's record
                            says which side of publication it was entered on under, and the frozen context only the
                            marked half carries -- and the fields a duplicate record is deduplicated on
    telemetry.py            the dual audit / analytics emission, the stage tag resolved against the label
                            vocabulary, the refusal turned into a logged non-emission, and the guard on each half
                            that keeps a sink from reaching workflow
  stages/
    conflicts/              `workflow:resolving_conflict`
      handler.py            the order one tick asks its questions in: the missing-`pr_number` park, the terminal arcs,
                            the body-edit resume, and the rebase behind them
      routing.py            the awaiting-human resume and `MAX_CONFLICT_ROUNDS` cap that gate the rebase, the
                            worktree it runs in, and the three things a branch can carry into a rebase that are not
                            one -- a behind-base divergence, a round the size gate held and an adjudication has since
                            published, and commits a crashed tick never pushed
      guards.py             the worktree restore and the two probes that prove a stale PR head is safe to
                            force-publish over
      divergence.py         the park a behind-base worktree earns, the one lease that excuses it, and the
                            crash-recovered push -- measured by the size gate first, since a crash between a commit
                            and the gate is the window this recovery exists for, named against the head this
                            stage read, which is the commit the round it finishes is recorded under, and PINNED to
                            the tip the divergence reading was taken against, since "ahead and not behind" is
                            a claim about that one commit and an unpinned push would have the gate adopt whatever
                            the pull request moved to in between; a push neither the exceptional lease nor that tip
                            can name refuses (`unpinnable_recovery`) rather than letting git read the remote for
                            itself. The behind-base probe is taken
                            BEFORE that push, since the reading is the same either side of one and taken first it
                            says which round a held candidate would owe: on base the push completes a round of its
                            own and leaves the receipt for it, behind base it is the preamble to a rebase that owns
                            the round instead
      rebase.py             the branch and base fetches, the rebase, its `merge_attempt` event, and the three-way
                            disposition
      publication.py        the unproven-tree and unreadable-head parks, the no-op flip, the rebased-head push
                            (measured by the size gate first, since a base that moved changes what the branch adds
                            to it), and the hand-off of real conflicts to the dev. Both parks are the same refusal
                            read one step apart: a status that established nothing names no paths and a head that
                            would not resolve reads as the head this stage started on, so taken as absences they
                            hand a reviewer a tree nobody read or a rewritten head the pull request never received
      resume.py             the three dev-resume entry points, the shared run, and the `/orchestrator continue`
                            classification
      outcomes.py           the interrupt / timeout / mid-rebase parks read before HEAD, and the push a completed
                            resolution earns -- measured by the size gate first, since a resolution grows the pull
                            request like any other candidate, and pinned by the pre-rebase head this stage read
      transitions.py        the park-and-write pair and the pushed-round tail every exit shares, plus the round a
                            hold owes: named for the gate to write down ahead of its relabel, read back by the tick
                            the settlement hands the label to -- only over a checkout standing ON the head it names,
                            since in sync with its remote is what a replacement host rebuilt at a moved pull request
                            reads as too -- and dropped by whichever tail finally pays it, since the resumed tick
                            reads a published resolution as a branch already standing on its base, which is the no-op
                            flip that resolves nothing
      models.py             the frozen records the owners hand each other
      state.py              the counter keys they share
    decomposition/          `workflow:decomposing`, `workflow:ready`, `workflow:blocked`, and `workflow:umbrella`
      run.py                one `decomposing` tick: the late route asked before anything else, the drift / recovery /
                            kill-switch order before the agent, and the pause, dirty-worktree, and interruption
                            checks after it
      handoff.py            the two ways this label hands an issue to implementation -- the kill switch and a
                            candidate the size gate settled, the latter releasing the hold and moving
                            `pr_number` onto the pull request the measured commit is on first -- and the re-read
                            the inline handler is given
      session.py            the locked decomposer session: the spec read, the fresh spawn that pins it, the
                            human-reply resume, and the drift reset that retires it
      manifest.py           the fenced-block envelope rules both modes are held to, the JSON decode, and the parse entry
                            point the stage routes on
      validation.py         what a `split` payload must satisfy: the child cap, each child's shape, and the acyclicity
                            of the graph they declare
      outcomes.py           the three dispositions of a finished reply: the unparsed park, the `single` finalize, and
                            the `split` hand-off
      split.py              the crash-safe order a `split` manifest becomes child issues in, and the summary / label /
                            activation tail
      recovery.py           what a tick that died mid-split left behind: the stale-manifest markers, the orphan-child
                            repair, the incomplete park, and the two owners that hold those markers instead -- a
                            human the issue is parked awaiting, and the late transaction while its generation is
                            live
      parents.py            the fresh child scan, the rejected and manually-closed parks it earns -- published
                            apart from the scan, since one caller settles its ledger on the way out of them -- and
                            the parent's own drift reroute
      activation.py         the dep-graph walk that releases the next children, the child it passes over because
                            GitHub reports it closed or the scan holds no issue for it, the latch asked before
                            EVERY relabel -- a relabel is a request, so a close observed after the first child was
                            released may not release the second -- the pull request a late split superseded these
                            children out from under asked in the same place and off this parent's own record, so
                            a caller cannot answer it a child scan too early and a parent that never entered the
                            gate pays nothing, that ask itself a request and so the latch taken on BOTH sides of
                            it, the one behind having nothing between it and the relabel, and the
                            held-dependency line it logs
      blocked.py            the `workflow:blocked` poll and the `workflow:ready` handoff to implementing with its
                            consumed-comment ratchet
      umbrella.py           the `workflow:umbrella` poll, the barriers around everything that acts on the child
                            scan -- past the scan, behind the settlement the terminal waits on, and once more
                            immediately before the write that records the resolution and RETIRES the cycle
                            together -- correlating that retirement to nothing, since the cycle it drops finished
                            -- correlating it to the cycle it dropped, since the barrier behind the write is this
                            process's -- which is what leaves no live cycle under a `done` no sweep queries, with
                            that write held inside the retirement window and the latch asked once more BEHIND it,
                            where a close is answered by putting the cycle back cancelled rather than refused; the
                            resolution said once off that same stamp -- and, on an umbrella a POST-PUBLICATION
                            split made and no other, off a marker naming this cycle and generation on the thread,
                            since only there can the barrier behind it refuse a terminal whose sentence has
                            already gone out and only there may an umbrella held on a reopened pull request repeat
                            itself every poll, while a restart out of a rejected cycle keeps the thread; the
                            publication that split closed asked about once more immediately in front of the
                            retirement write, which is the boundary past which the group is gone and nothing could
                            ask again, a refusal there writing nothing at all; the label and close
                            asked of a record that
                            already says the terminal is due, the close its all-done branch earns
                            instead of
                            an implementation pass, and the reconciliation that close waits on -- the one boundary at
                            which what a late split still owes a remote can be settled, and the last that comes
                            back if it cannot
      late_coordinator.py   the additive late mode's order: the owed owner read and the undelivered park notice both
                            reconciled ahead of every gate, the live-generation gate, the frozen-evidence proof, the
                            hold on the pull request the candidate stands on before any spawn -- and the displaced
                            one no new agent is started under --
                            the content settlement that can end the tick, the completed-result short circuit, the
                            retry-budgeted run whose pre-spawn write holds the accounting back, the read-only proof
                            over the candidate worktree, the fresh owner read every completion but a declined
                            run passes through on its way to settlement, and the split transaction that read hands
                            a cleared `split` on to
      late_session.py       the late run's pinned record -- role, locked spec, session, cycle, source commit,
                            generation, and the whole of what a verdict decided -- the whole-comment budget it is
                            refused past, the rules it is read back through, and the tracked spawn in the candidate's
                            own worktree, resuming the pinned session only for the run that carries a human's answer
                            to the question it asked
      late_hold.py          the cycle-marked hold a reusable open pull request wears: which one that is -- a hold
                            already recorded (released first and re-taken where the publication entry has since
                            named another, since the record holds one identity and one preserved body), then that
                            entry naming the implementation PR the work is already on, then the issue's own
                            `pr_number` -- the one guarded read every decision is
                            made from, the discussion provenance the last of those three has to establish, the
                            identity, head, and original body persisted (and proved persisted) before the edit --
                            a head this reading could not name refusing the hold rather than being recorded absent --
                            the notice worded by the side of publication it is written onto, the spelling an earlier
                            binary wrote beside the two this one does, and the one question that recognizes any of
                            the three as ours, the head that moved under a standing hold reported and never
                            restamped, and the retry, the refusal, and the settled pull request it reconciles to
      late_outcome.py       what one finished reply becomes: the lineage-bound refusal, the durable write that precedes
                            every external effect and closes a completion by carrying the owner read it now owes --
                            under `owner_check` unless a split transaction was interrupted, whose boundary the
                            record itself refuses to let any pre-split write rewind, since the phase is all that
                            says a loop was in flight when nothing is recorded yet -- the
                            announcement a recorded question is reconciled by, and the parks
                            and emissions every late exit shares -- staged for the owner read to release, released
                            anyway where nothing would ever say them, and re-said at the top of a later tick when the
                            comment that should have said them was refused
      late_notice.py        the sentence a park owes the issue until it is actually on the thread: the durable
                            `{reason, message}` beside the flag, matched against the park it explains, the thread
                            read that discharges one a failed write left claiming the opposite of what GitHub holds,
                            and the pinned budget a notice too long to write down is refused past
      late_owner.py         the fresh tri-state read EVERY completed run passes before anything acts on what it
                            left: the latch consulted ahead of GitHub, since a close a poll saw while this worker
                            held the issue is the one reading a request cannot give back, the standing claim it is
                            entered past rather than makes (written by the completion's
                            own write, so a tick that died on the way here still left a park and an owed read), the
                            reconciliation that takes an owed read again ahead of every gate, the
                            cancellation a closed owner earns -- recorded and reported once per cycle, since
                            several barriers reach the same closed reading in one run and the cycle ended at the
                            first, with the repeat's own claim still dropped -- the park an unreadable one takes
                            only where nothing
                            else already holds the issue, and the one follow-up that park owes the thread --
                            posted before the write that clears it. Two barriers beside it take the latch ALONE,
                            for the steps whose own moment is too tight for a request and where a claim would name
                            `owner_check` over the boundary the tick actually reached: the create, the spawn, the
                            developer revision on both sides of its run and against the resume itself, and each
                            step of the `single` publication
                            share one, and the activation past a retirement already standing at `cleaning_up` has
                            its own
      late_snapshot.py      the immutable copy every child of a split is cut from: the ref this generation's
                            identity names, the obligation written ahead of the push and again behind the proof, the
                            create-or-verify that never overwrites, the fetch that proves a child could obtain it,
                            and the one park every refusal takes
      late_children.py      the children a split creates: the umbrella flag and count written before the first one,
                            the owner re-read before every one of them -- the first included, since that flag is a
                            remote write -- the latch asked once more against the create itself, since the
                            orphan lookup ahead of it walks the whole repository, once BEHIND it, and once between
                            the read of the child's own comment and the write that adds to it, since a close
                            landing inside either leaves a real issue: recorded either way, because a child
                            nothing names is the one state no pass can clean up, never seeded, because a
                            cancelled cycle owes its children nothing, and answered back to the loop rather than
                            stopped at, since the seed is the last step of one child's turn and a caller told it
                            succeeded opens the next slice against an ended cycle, the single write that records
                            each as a child, a
                            consumer, and an obligation, the seal that says the register a cancellation stopped
                            the loop over is FINAL -- the count it was measured against is one a cancelled loop
                            can never reach, so the ref would be held on a proof no pass could complete -- withheld
                            on a resumed walk short of the first unrecorded index, where a child an earlier attempt
                            made and never recorded would not be on it, the adopt
                            -- never repeat -- a resumed walk does, the one-receipt-only check a candidate has to
                            pass to be adopted, the manifest test that refuses a slice declaring a receipt of ours,
                            the seed that adds an ancestry without replacing a child's own work, and the body naming
                            the snapshot, the two reuse forms, and the hunk splitting it forbids
      late_transaction.py   the order a cleared split runs in: the four refusals no step below could repair, the
                            snapshot before any child, the owner re-read before every step the remote keeps -- the
                            same guard the handoff took, taken between the children and again between the
                            announcement, the supersession, and the retirement, since a close a poll saw while this
                            worker held the issue reaches no cleanup pass on the tick it happened -- the children
                            before any link, the forward links behind the receipt that stops them repeating, the
                            pull request this cycle's work is on superseded and closed under a marker scoped to
                            this adjudication -- the plan one where the gate was entered before publication, and
                            the implementation one where it was entered past it, which is proved still open
                            and still standing where the reading found it before it is closed, since the tail
                            behind this deletes the branch and hands the work to children and an unsuperseded one
                            is an open change carrying work nobody will finish, with a pull request already
                            closed over THIS adjudication's own receipt recognised as the supersession a crashed
                            tick already made rather than as a human's settlement -- though never a MERGED one,
                            whatever the thread says, and never one whose head moved behind the close, since a
                            close does not freeze the branch the tail behind it reclaims -- the publication
                            asked about between every step of the tail on the same rule the owner is -- in
                            front of the close, the retirement, EVERY child released, and the branch delete,
                            the last two from inside the walk and the reclamation rather than in front of
                            either, since a child scan and a snapshot probe are requests of their own -- since
                            each is licensed by that supersession being on it and a human can merge, reopen, or
                            push in between any two; the close itself made against a SECOND
                            reading taken with no comment listing behind it, so a change settled or pushed to
                            inside the first window is left untouched rather than marked and closed and only
                            then refused, with the receipt that reading skipped handed to the write so no thread
                            scan stands in the interval either; a refusal before the retirement a park with the
                            record still live and one past it the step declined and left to the umbrella's own
                            walk or its terminal, which ask the same question themselves, per relabel and per
                            delete, off the publication group the retirement keeps -- the
                            generation retired onto `workflow:umbrella` in the write that hands the issue on, the
                            activation behind it -- through the shared dep-graph walk, so a child that ended while
                            the supersession was parked is left where it is -- and the branch cleanup recorded as
                            owed and attempted after
      late_cleanup.py       what a split still owes a remote once its children are running, with the latch asked
                            between every obligation it settles, between the fresh consumer proof and the ref
                            delete it authorizes, between that delete and the receipts behind it, and between
                            every two of those receipts, since each is a comment on somebody ELSE's issue -- a cancelled cycle settles by the same rules and tells its
                            consumers nothing -- reported and written
                            back only where a state actually MOVED -- so a remote that goes on refusing one delete
                            costs a request per visit rather than a record and a comment write per visit, while the
                            log goes on naming what is held: the fresh per-consumer
                            scan every rule here is proved against (a read that fails keeps its own ref and stops
                            nothing else), the branch obligations in every state but reconciled and the refs still
                            held, the refusal -- taken immediately in front of the delete, since the snapshot rule
                            beside it may spend a probe first -- to delete a branch at all while the pull request
                            it was superseded under is open again, nothing attempted, nothing recorded failed, the
                            entry left owed and the terminal held, that same pull request asked about once more by
                            the settlement the terminal waits on, which is the hold no ledger carries -- a
                            reclamation that FINISHED owes nothing, so a branch restored and a change reopened
                            after it would find every entry settled and `done` free to fire over them -- and
                            nothing written back for it, since nothing is owed and an entry saying so would send a
                            later pass to delete a branch a human put back, the exact-name check a branch and a snapshot ref each have to
                            pass before anything is deleted by it, the rule that decides whether a ref's recorded consumers have all
                            ended -- read off each consumer's issue state, since a reopen keeps the terminal label,
                            and whether the list names all of them read off the record's phase, since a child is
                            created before it is recorded, with a PRE-SPLIT phase corroborated against the ledgers
                            and against the count the transaction writes ahead of its first create -- which is what
                            upgrades a record an earlier binary rewound, and what tells a `splitting` loop that
                            finished from one still running, since the phase is written beside every child
                            recorded, with a SEALED register answering ahead of that count, since a cancelled loop
                            can never reach one -- beside the claim that no longer rewinds a transaction boundary
                            at all -- the
                            two deletes, the branch one taking the remote ref, the checkout, and the local
                            ref and proving all three gone, the snapshot one ordered on the record before it is
                            carried out and then re-proved against consumers read past that write (and retried past
                            the proof only for a ref one read-only ask shows the remote no longer has, with a
                            raising transport read as the refusal it is), the receipt every child cut from a
                            reclaimed ref is left by a LIVE split -- one comment, marked with this owner, cycle, and
                            generation so it is said once, proved against the child's own thread with the latch
                            asked between that reading and the comment it authorizes, never a write to that
                            child's own pinned state, and left
                            unsaid entirely by a cancelled cycle, which owes its children nothing -- with the entry
                            left `reclaiming` for a consumer it could not reach -- the one write that records any of
                            it, the settle both callers share, what may not be left behind (everything
                            unreconciled, an opaque ledger and a damaged identity included), and the question the
                            umbrella's terminal asks before it closes -- and that a park for a rejected or
                            hand-closed child asks on its way out, since both of those ended the consumer they
                            name and nothing else revisits an open umbrella
      late_reuse.py         what a child born of a split proves before it starts, taken on the child's own
                            dispatch because the owner that reclaimed the ref cannot write another live issue's
                            pinned comment safely: its own owner's receipt read off its thread first, which is what
                            says the reclamation HAPPENED and outranks a mirror nobody dropped or a ref pushed again
                            at the same commit -- so a thread that could not be READ holds the dispatch rather than
                            falling through; then, where the thread answered and carries none, this host's mirror
                            read for the commit it carries -- and only where the pointer carries the stamp saying a
                            reclamation would have dropped it first -- and the remote behind it, whose absent /
                            re-pointed / unreadable answers park, park, and HOLD the dispatch respectively; and,
                            for a child the split recorded but never managed to seed, the same answers over the
                            pointer its BODY marker earns -- corroborated against
                            the owner's own fresh generation first, since a body is a field the world can write and
                            a receipt is posted only after the ref is gone -- with the park, the pointer dropped or
                            the lineage repaired, taken before the label's handler is reached
      late_sweep.py         the cleanup-only pass over an owner a human closed mid-cycle -- reached by being closed
                            on `decomposing` or `umbrella`, where an adjudication runs, or on `ready` or `blocked`,
                            where a decomposition outcome that landed after the close can leave an ending nothing
                            else would find; never by the label alone: the one reading that says
                            whether there is a cycle to end, and the two readings that withhold everything but the
                            mark -- an issue open again between the poll and the refetch, and one an operator has
                            parked with `backlog` or `paused`. Being routed here at all says a close was observed,
                            so either leaves the mark behind and the rest to a later visit. What that ending
                            consists of is `late_cancellation`'s; what is here is the entry a closed issue has
                            no handler to give it -- the close a dead terminal left correlated on the record and
                            receipted on the thread, adopted before anything else is decided; and the one terminal
                            it writes itself, the `done` an
                            umbrella recorded in the write that retired its cycle and a crash took the label off,
                            retried for as long as the remote refuses it because the owner keeps the swept label
                            until it lands; and a swept label put BACK on an owner still owing the remote that a
                            hand relabel moved outside all four, since after a restart the label is the only
                            thing that reaches a closed issue
      late_cancellation.py  the irreversible ending an owner observed closed earns, the mark a CLOSED owner gets
                            from this guard when its label names an ordinary terminal rather than the cleanup
                            sweep, the record read the dispatcher asks of a refused submit for the same window,
                            the refusal EVERY label earns over a
                            cancelled cycle -- each of them names a handler that would act on the issue rather
                            than end it -- with the terminal written wherever the transition graph declares the
                            edge from, plus the `ready` and `blocked` the cycle's own decomposer writes as its
                            ordinary outcome, where a refusal would stand on every visit the sweep makes forever,
                            and never from the unlabeled
                            state, which IS the restart handshake, and
                            deferred whole past a control label that says now is not the time; the reading of that
                            ending the dispatcher takes on the way OUT of a cleanup pass, so a pass that returned
                            with the ending owed under a label no query asks for keeps the observation that routes
                            it back, and the obligations half of the same question, asked by the sweep deciding
                            whether an owner may be let out of it; the receipt a
                            poll leaves on
                            the thread for a close it could hand to no worker -- a comment, since the pinned
                            comment is written whole and the worker holding the issue owns it, retried until one
                            lands, written from the SAME read that answers whether the reading is still owed, and
                            scoped to the cycle a retirement in flight names where the record names none -- the
                            once-per-process scan that adopts one a DEAD process was holding, scoped
                            to the cycle so an operator's authorized restart is not ended by an older close and
                            claimed only once the walk answered; the mark a handler already inside its own child
                            walk takes when the latch answers mid-scan; and the two
                            entries into the ending: the closed owner's, and the dispatcher refusal a REOPENED one
                            takes, which runs the same reconciliation and writes the same terminal -- reaching no
                            handler either way,
                            since an issue worked again without passing the ending would be the cancelled cycle
                            resumed by accident -- the unlabeled state included, which `late_restart` answers
                            one guard ahead and which falls through to nothing, since the pickup path behind
                            it would greet a cancelled cycle as new; the reading of what is owed by ANY
                            measure that decides both, the ending's own list plus the settled-ledger answer
                            the domain gives, since a child receipt and an untypeable consumer ledger are on
                            neither of the first two; the terminal written from the unlabeled state only
                            where the record shows one was never applied, so the operator's own
                            restart (taking `rejected` off) is not undone while a workflow label a human
                            stripped mid-cleanup still earns the ending it interrupted; the cycle that
                            terminal is owed for, recorded before the label write so a tick that dies between
                            the two has something to come back to, with the PROOF a restart reads taken from a
                            label that LANDED -- from the write returning where this pass made it, since a
                            client's cached labels outlive the write that changes them and a closed owner
                            gets no second visit, and from seeing `rejected` on the issue where it did not,
                            which is what backfills a cycle that ended before the record existed, and from
                            the newest workflow label THIS orchestrator applied where neither reached --
                            asked from BEHIND the reconciliation, so an obligation the ending discovers
                            rather than reads is on the ledger before anything decides the cycle owes
                            nothing -- what answers an
                            unlabeled issue over a cancelled cycle is
                            `late_restart`, asked one guard ahead of this one. The pass
                            itself is the cancellation persisted (with the boundary it interrupted, since
                            `cancelling` overwrites the phase every later rule reads) and reported once, before any
                            external call; the held pull request -- the one obligation no other pass ever sees --
                            released, told once over a cycle-scoped marker, and closed, re-asked on every visit
                            because its state is a human's to change and recorded only where that state moved; the
                            branch a supersession left behind but never wrote down taken on as owed, off the
                            announcement's own receipt rather than the phase a retry rewinds, only where the record
                            names none, and only once that pull request is settled -- the boundary is written
                            before the attempt, so it says nothing about whether it landed; the child receipts
                            discharged so the terminal a restart reads is one it will accept; the rest handed to
                            `late_cleanup`'s own rules unchanged, with the consumer
                            scan taken only where a ref is actually held; that pull request asked ONCE MORE on
                            the far side of all of it, since a branch delete, a ref delete and a consumer read apiece
                            stand between the first ask and the terminal; and the `rejected` terminal, written last,
                            only for a closed owner, and only once nothing is owed -- which is what takes the issue
                            out of the sweep for good
      late_settlement.py    what a guarded verdict earns: the announcement a question owes the issue, the exemption
                            naming the measured commit, the hold released and the pull request reconciled
                            against that commit in any state -- with a settled pointer dropped rather than handed on
                            -- or, where the verdict was taken PAST publication, the frozen pull request proved
                            rather than searched for: still open and still standing where the reading found it -- or
                            already standing on the accepted candidate WHERE the approval, or the receipt read with
                            the head it replaced, vouches for it, which is this settlement's own push having landed
                            before the tick died and is finished rather than refused (that head on a fresh pass,
                            ahead of both writes, is something else's push and refuses with every other) -- and
                            otherwise
                            refused, since dropping the number there would push onto a branch whose pull request a
                            human settled and open a second one for a change adjudicated against the first; the push
                            itself made HERE, named and leased by the evidence only this tick still holds, and the
                            label then handed to the stage the record names rather than to implementing --
                            before a pre-publication candidate goes back to the ordinary publication, with the
                            latch asked between every one of those steps and the retirement behind them answered
                            by REINSTATING
                            the cycle rather than refusing, since past that write there is none left to end --
                            the write and that barrier held inside the observations owner's retirement window, so
                            a poll reading the record between them is not told there is nothing to end -- and
                            the split passed on to the transaction that creates its children, and the cycle that
                            retirement dropped recorded outside the group the write clears, so a process that dies
                            before its own barrier leaves a receipt something can still be adopted against
      late_publication.py   the pull request a verdict taken PAST the first push was measured on, read once for
                            both roads out of the adjudication: a `single` publishes onto it and a `split` closes
                            it over a supersession, and neither may look it up -- the entry the gate froze names
                            it and the head it was standing on. One reading, because a fetched pull request is
                            lazy and the reads behind the lookup are what talk, so a caller guarding only the
                            lookup leaves them to raise out of a road whose every other refusal parks -- and a
                            caller's own receipt is read there too, since one that CLOSED the pull request itself
                            and died before the work behind that close was finished cannot tell its own close
                            from a human's by the state alone -- and the pull request those facts were read off
                            travels back with them, so a caller that has to ACT acts on what it proved rather
                            than on a second lookup a human can move something between; plus the question a
                            SETTLED split keeps asking, which three owners share: whether the pull request it
                            closed is still closed over the head it froze, published as the ASK rather than as a
                            fact and taken off the record every time it is put -- the generation for the
                            transaction and the reclamation, the pinned comment for the activation walk -- since
                            a step licensed by an answer the step in front of it took is one a human had time to
                            overtake, and since the retirement that hands the issue to `workflow:umbrella`
                            outlives neither the children still to be released nor the branch still to be
                            deleted
      late_prompt.py        the late-only prompt: the committed candidate, the frozen diff, the measurement, the
                            lineage, and the three outcomes with the bounds they are judged against
      late_reply.py         the late reply's own fence, its three structured decisions, and the envelope and split rules
                            it borrows from the initial mode
      late_content.py       WHICH content the two late-local fingerprints are taken over -- the title and body, and
                            the trusted-thread run the ratcheting watermark covers -- what a comparison against a
                            recorded baseline says moved, and the floor a comment has to clear to be a REPLY rather
                            than conversation the issue was already carrying. The digests themselves are the
                            `late_split/identity` owner's
      late_guidance.py      what that comparison earns: the baseline a first tick takes, the park an edit wins over
                            every concurrent answer, the certificate a bare continue writes, the question a real
                            answer reopens, and the continue that answers none
      late_revision.py      the developer run guidance buys -- the locked session resumed under `agent_role=developer`
                            and `stage=decomposing`, with a latched close asked on BOTH sides of it, since a resume
                            is the same step a spawn is and the run takes hours -- the refusal a candidate whose
                            split already created children
                            earns instead, and the clean tree, re-frozen commit, and fresh measurement its result is
                            reconciled through (which carries none of the last generation's split receipts), with
                            the `ACK:` marker an UNCHANGED commit needs before it counts as an answer
      late_relabel.py       the `workflow:decomposing` label a live generation pins -- one still oversized, or one
                            whose owner read is still owed: the kill-switch route it refuses, and the dispatch it
                            refuses -- with the hand relabel it repairs -- when a human has moved the label out from
                            under an open adjudication
      late_restart.py       the fresh cycle an operator authorizes by taking a settled cancellation's `rejected`
                            back off: what the record has to prove before that gesture counts -- a cycle that
                            exists, one a close already ended, and one that owes nothing under BOTH readings, since
                            the ending's outstanding list and the domain's settled ledger overlap without
                            containing each other (only the first reports a held PR this generation cannot show it
                            held, which no pass can settle and a restart would erase; only the second counts a
                            child receipt or an untypeable consumer ledger, over which the retirement would refuse
                            with the marker already down) -- the proof half of the terminal record, saying
                            this cycle's `rejected` LANDED on the issue, without which a workflow label a
                            human stripped mid-cleanup and a terminal write GitHub refused both read exactly
                            like the removal that authorizes a restart -- the
                            open, unlabeled issue the gesture is read off, and the marker that answers it for
                            itself once a transaction has begun; the identity that record is repaired to before
                            anything is written, since a pinned comment naming another issue would file the fresh
                            cycle and both sinks' records of it under that one, and a root naming no issue at all
                            is a record the telemetry contract refuses outright -- the current issue is the issue
                            the comment was read off, and the root is kept where the record is this issue's own and
                            re-derived from the ancestry otherwise; the control label that defers the whole of it;
                            the `DECOMPOSE` setting that chooses between the two labels a restart may apply, and the
                            record that outranks it from the moment a notice has announced one; then the
                            transaction -- the marker made durable first, the notice said once over a cycle-scoped
                            receipt proved from the thread and ADOPTED off it where an earlier pass posted one and
                            lost the id it tracked in memory only, the label written where the issue is not already
                            on it and put back where the name is there but this orchestrator is not what applied it
                            -- the restart's own application is what separates the fresh cycle from its
                            predecessor's terminal in the history the ending's last-resort proof reads, and GitHub
                            records no event for a label already present -- and the retirement behind both, with the
                            projection that retirement writes: a
                            whitelist keeping the pinned comment's own identity, the bounded orchestrator comment
                            ids, the cumulative issue usage, and the identity joining the fresh cycle to its
                            predecessor, and dropping everything else
      late_models.py        the carriers the late owners hand each other: the tick's subject, the hold, the run, the
                            adjudication, the tri-state owner reading and the park staged for it to release, the
                            split that reading cleared for the transaction which creates its children, the content
                            fingerprint and what the humans have said since, and what one call did
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
      publication.py        the size gate a docs commit passes -- the last one before a human is asked to merge,
                            and handed the commit this pass made so a checkout something moved is refused rather than
                            measured in its place -- then the push, the docs watermarks it stamps, and the PR notice
                            it posts; a held commit leaves the head it produced as the receipt the handoff is still
                            owed, and the handler finishes from that only over a checkout standing ON it, since in
                            sync with its remote is what a replacement host rebuilt at a moved pull request reads as
                            too
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
                            missing-`pr_number` park, and the commit the no-feedback bounce publishes -- measured by
                            the same size gate the shared dev-fix publication passes, so a held candidate stops the
                            bounce rather than being relabelled over -- before it hands the PR back to the reviewer
      feedback.py           the rescan past the three in_review watermarks and the narrower ratchet a consumed batch
                            advances them by
      bookmarks.py          the `pending_fix_*` ids a replay rebuilds the triggering batch from, and the clear each
                            round earns
      resume.py             the quiet window, the dev run, the ACK fast path, the `workflow:validating` relabel a
                            pushed fix earns, and the round a fix the size gate sent to adjudication spends here --
                            no later tick of this stage can, since a settled verdict publishes before handing the
                            issue back
      parked.py             the four answers an `awaiting_human` tick can reach and the order they are asked in
      continue_command.py   `/orchestrator continue` on a parked fix: the replay and what it may hand the dev --
                            guidance, never the command itself -- plus the two refusals and the guidance passthrough
      drift.py              the `workflow:resolving_conflict` reroute a stuck validating-route park earns when its
                            worktree has fallen behind base
      models.py             the frozen records the owners hand each other
      state.py              the pinned-state keys they share
    implementing/           `workflow:implementing`
      handler.py            the order one tick asks its questions in
      spawn.py              awaiting-human vs active, the restorer the checkout comes back from, the
                            recovered-worktree shortcut and the certified baseline it stands down for -- which
                            an unread head cannot spend, since that comparison is what a retirement rests on --
                            and the retry-gated fresh spawn
      session.py            the three session retirements, the per-issue 24h spawn cap, and the fresh-spawn prompt
      session_read.py       the locked session read plus the stale / overflow / quota classifiers and the blockquote
                            they quote with
      resume.py             the two resume entry points and the historical call shape they keep
      execution.py          one resume, its poisoned-session retry -- withheld on an issue a poll observed closed,
                            since that retry is a SECOND agent -- and what each attempt is allowed to persist
      worktree.py           the checkout a resume runs in, restored when reaped
      disposition.py        the publish / timeout-park decision, taken on both readings of what a run left --
                            the head moved off `before_sha`, and the branch is ahead of base -- so a checkout
                            something advanced onto that base is not read as a commit, at the timeout's
                            disposition or at its next-tick recovery; the attribution both readings rest on,
                            which needs BOTH ends of the comparison read and parks where either is not; the
                            certified floor a clean exit is credited against, the size gate every clean
                            committed candidate passes, the timeout and measurement parks' own recoveries, and
                            the approved commit an interrupted publication owes, disposed against the record
                            naming it rather than against any ahead-of-base reading
      late_gate.py          the order the size gate's questions are asked in, taken over one subject so both seams
                            ask them the same way: the switch, the commit the caller named -- proved against the
                            checkout before anything is persisted or pushed, since between the caller's read and this
                            one the worktree is writable and a commit landing there is a different candidate -- the
                            three records that
                            say a commit is already decided (the adjudication's exemption, the gate's own unspent
                            approval, and the commit this stage already pushed), a record already answering, and
                            the count that answers a pair nothing has yet
      late_reading.py       the reading itself, on the two roads into one: a fresh pair frozen before it is counted,
                            so a tick that dies over the diff comes back to the pair this one froze, and a recorded
                            one acted on only once its other fields say what the number MEANS and the base it names
                            is proved present here
      late_overflow.py      what a gate call taken PAST publication freezes before it may measure -- the stage it is
                            taking the issue out of, the pull request the work already has, and the head that pull
                            request is standing on -- and the five refusals that make freezing them fail closed: a
                            tree that is not provably clean, a pull request nothing could read, one that is closed or
                            merged, a caller-named head that is no whole object id or that disagrees with the head
                            this owner reads, and a head that moved off what a live record froze; asked behind the
                            switch, so an install with the gate off pays neither the read nor the park. Also what a
                            record already carrying a publication is re-proved against -- the whole frozen identity
                            rather than the head alone, since a branch reused across two pull requests puts the same
                            commit at the tip of both -- and what the CALLER established rather than what this owner
                            would re-read: the head it pinned its own decision to, checked against the one this owner
                            reads rather than substituted for it, and the stage a same-tick remote relabel
                            wrote over a cached one. That comparison has one carve-out and it is not a preference: a
                            tip a DURABLE RECORD says this issue put there -- an approval's commit, a live record's,
                            or `implementing_published_sha` read with `implementing_published_lease`, the head that
                            receipt replaced -- is this issue's own push having landed, which is the window an
                            approval exists for; anything else at the tip is somebody else's branch move and
                            refuses. The caller's own candidate is deliberately not among them: on a fresh attempt
                            no push of this workflow's has run, so a tip that merely happens to BE that commit says
                            an agent put it there, and waving it through would measure and route the candidate the
                            gate is holding back. The receipt is not among them ALONE either, since one that is
                            never cleared would read a pull request rewound onto a commit published rounds ago as
                            this tick's own push arriving -- and a checkout rewound with it agrees on every local
                            fact there is. Dated by the head it was PINNED to it names the one window it is evidence
                            for, a push made from the head this call was entered on under a process that died
                            before the relabel
      late_publication.py   the answer half, between that entry and the push: the switch, the record, and the count
                            asked in one place, so the seam that reached the gate makes no difference to what it is
                            told -- an install with `DECOMPOSE=off` never reads a pull request, a record already in
                            the gate goes through the ordinary questions, and a commit an approval owes a push is one
                            this gate has already ruled on; a hold is the whole of what the tick did, parked or
                            handed to the adjudication, rather than a bare permission, and anything else carries the
                            commit the push is named against, the head it is leased against, and the head the pull
                            request stands on now, which is what says whether the push has anything left to do
      late_push.py          the one call every gated push onto a pull request the remote already carries goes
                            through -- measure, push named against the measured candidate and leased against the
                            frozen head, spend the debt it paid, close what the route owed for it (in that same
                            write, since past it neither the approval nor the generation is left to say a round was
                            owed, while the caller still has a relabel and a write to make), record what reached the
                            remote so a tick that dies
                            past the push neither re-reads nor re-pushes it, and prove the checkout again on the far
                            side of the effect -- AHEAD of that write, so what the proof answers rides it: a
                            checkout that moved or was dirtied holds the handoff rather than the publication, and
                            the claim it owes lands with the receipt rather than one write behind it, where a crash
                            would take it and leave the stage below reading a dirty worktree as no stranded work;
                            borrowing the initial publication's own two questions for both; a pull request already
                            STANDING on the candidate goes through the same
                            tail, since the request is the only atomic proof that the publication this tick froze is
                            still the one the pull request has -- git has nothing left to send, and the lease moves
                            to the head the branch is on NOW rather than the one an approval was measured against.
                            That write is skipped for a push that had nothing to SEND and finds the receipt naming
                            its commit with no debt beside it, which is a retry of a publication already settled; a
                            push that MOVED the pull request settles whenever a pair the route owes is not already
                            the value on the comment, since the receipt is never cleared and on its own reads a
                            branch pushed back onto an older published commit as a round nothing is left to close
      late_accepted.py      the push an adjudication already accepted, taken with no measurement -- a verdict read
                            this exact diff and said it ships as one change -- but still named against the commit
                            that was DECIDED, still pinned to the head the reading was taken over, and made only
                            over a checkout re-proved to be the one that verdict was reached about
      late_rewrite.py       the publication a squash-on-approval may rewrite and the push it then makes, and the
                            switch asked ahead of both: a squash is NEW work by the switch's own definition -- the
                            commit it publishes is one it makes itself -- so `DECOMPOSE=off` reads no pull request
                            and parks over none, and what such an install does is squash and push under the lease
                            this stage read for itself -- the gate's own switch question, asked here because it reaches
                            it twice and the first of the two is the pull-request read the switch is meant to save.
                            With the
                            switch on: entered on
                            that pull request before the reset destroys anything locally, so a closed or unreadable
                            one, a dirty tree, or a head that moved costs a refusal rather than a rewrite and a
                            rollback; then the commit the squash MADE goes through the whole gate, because that is the
                            object the push would put on the pull request -- the tree is the approved one, but the
                            base moves, and this is the last push before a human is asked to merge. That commit is
                            checked on both sides of the gate, since the gate proves the checkout for itself and a
                            first generation has no record to prove it against, so something committing over the
                            worktree in that window would be measured and published in its place. Which holds keep
                            the rewrite is answered here too (`_rewrite_stands`): the receipt naming the squash
                            says a push landed, a live record naming it says the adjudication owns it or the
                            reconciliation still owes it a count, and a checkout that is not the squash says
                            something else made the commit -- anything else is a reading that REFUSED and froze
                            nothing, where the squash is a local commit nobody measured and the caller puts the
                            branch back rather than leave a retry one commit to call success. And the debt a
                            rollback abandons is dropped there, durably, since the reconciliation ahead of every
                            handler would otherwise stop the tick for a publication that is never coming
      late_reconcile.py     the reading the dispatcher takes for a pair frozen and never counted, scoped to the
                            stage the record names and taken with no run behind it: measured at or under the ceiling
                            the candidate is PUBLISHED before the stage runs -- nothing goes back for a push a
                            settled reading left owed, and the stage behind an unpublished one spawns a reviewer over
                            a pull request that never received it -- measured past the ceiling the issue is routed to
                            the adjudication, and a refusal parks. So does a push that was allowed and did not land.
                            An approval with no generation left behind it is the same window one step on, and
                            `late_debt` beside this answers it.
                            It stops the tick outright where the checkout that pair names is not on this host and
                            where the label has left the stage the pair was frozen on, since neither a re-entry nor
                            the handler is this process's to pick
      late_claims.py        what a post-publication record claims and what it cannot produce: whether a live one
                            still owes its count, and -- ahead of both reconciliations -- the four refusals a record
                            that cannot make a claim whole earns. Read off the RAW fields, because the parse is what
                            loses them: a group missing one member comes back as no group, an approval missing its
                            lease as no approval, a frozen field the comment CARRIES and no reader will type as a
                            field nothing froze, and a spend group with one unusable member as no bookkeeping at all
                            -- so every question behind them answers "nothing owed" and the stage runs over a claim
                            nothing can check, while the freeze quietly re-derives the half it cannot see from a
                            remote that has moved. A field the comment does NOT carry is the same gap: what the
                            write that mints a generation puts down in one go is required rather than merely checked
                            when present, and a base is required beside any count, since a number is taken over a
                            pair. All four claims on the five stages the transition graph's own set names, since
                            `workflow:implementing` has an edge to the adjudication too and its approval carries no
                            head by design; `workflow:decomposing` is asked the publication one ALONE, because that
                            group is what a settlement decides everything by and cannot re-derive, while a verdict
                            taken before publication approves its commit with no head to pin it against -- the very
                            half-written pair the approval claim calls damage
      late_debt.py          the approval the dispatcher pays ahead of every handler, where a crash past the write
                            that granted one left no generation to reconcile from: that write retires the record
                            before the push, deliberately, so what is left names a commit the pull request never
                            received and nothing under the stage reads it. Paid under the id the gate decided about
                            and the head it decided against, both of which live only on the approval by then --
                            and only from a checkout still standing on that commit. One that is absent, unreadable,
                            or standing elsewhere PARKS rather than standing down: the debt says a commit the pull
                            request does not carry was allowed to join it, so a handler behind any of those reads a
                            publication the approved work is not on. A push that LANDS closes what its caller never
                            got to -- the route bookkeeping the approval carried past its own retirement, and the
                            transient park that failed push left -- since no tick behind this one can, and one that
                            misses again leaves both alone and says nothing: a second mention is one nobody can
                            answer any faster, and a rewritten reason turns a park the stage recoveries retry into
                            one only a human clears. The commit is read ONCE and named to the gate,
                            so the proof that the checkout is standing on it and the reading the gate takes behind
                            it are about one approval: a commit landing between the two is refused rather than
                            measured, pushed, and receipted while the debt it was granted for is dropped as paid.
                            A branch some owner deliberately moved off that commit never reaches here -- the auto
                            rebase's own reset drops the approval it abandons. Payable only from the five stages the
                            transition graph's own predicate names, rather than from every label with an edge to the
                            adjudication -- `ready`, `blocked`, and `umbrella` each have one for reasons of their
                            own, none of them a pull request -- and a debt whose label has moved to one of those
                            stops the tick rather than being ignored, since the stage behind it would run over a
                            publication the approved commit never reached
      late_records.py       what one gate call is about -- the publication it was entered on included, where there
                            is one, and the two claims a caller makes about its tick: that no developer ran, which
                            decides whether a moved head is fresh output, and the narrower one that it is answering
                            a reading the gate itself recorded, which is what the switch is asked against -- the
                            answer it hands back, the identities a record of it
                            is minted under, and the validated-or-minted identity every refusal is reported
                            under so a damaged record cannot take its own refusal down with it
      late_freeze.py        the pair a count is taken over -- the candidate proved, the base frozen or
                            re-proved -- whether a recorded one is whole enough to act on, its
                            identity and the issue it names included, and the one state the switch answers
                            outright, which every seam that measures asks the same way
      late_evidence.py      what a recovery proves before it acts: the checkout, both recorded objects, a
                            head that is still the candidate, and a head that is still the commit an approval
                            owes a publication for -- proved ahead of every spawn, and what a refused handoff
                            waits to see back, which is that head with a provably clean tree around it
      late_verdict.py       what a measured candidate earns -- the push and the head an approval on the published
                            side is pinned to, which outlives the generation that froze it for as long as the push
                            is still owed, the `workflow:decomposing` hold and the
                            notice it owes the thread on the side of publication the record was entered on, the
                            approval a publication naming another commit supersedes, the same debt recorded for a
                            candidate that skipped the reading -- an exemption's, a supersession the switch let
                            past -- since no generation was frozen for one and the push it licenses would
                            otherwise leave the branch on the remote with nothing on the issue naming it, and
                            the retirement each is durable behind, that write held inside the observations
                            owner's retirement window with the latch asked ahead of it and the window's own
                            answer behind it, where a close is answered by putting the cycle back cancelled
      late_parks.py         the one park shape every unreadable reading takes, worded on the side of publication it
                            was taken on, the typed failure both sinks carry under the stage the reading happened
                            in, the bare continue that re-reads rather than re-runs, the measurement park a fresh
                            reading retires -- latch and all, since a reconciliation has no run behind it to clear
                            the flag -- and the commits a publication is read by: the one an approval owes a push
                            for with the head it is pinned to, and the one this stage made
      publication.py        the push -- named against the commit the gate decided and pinned to the head a
                            published approval was frozen against, where there is one -- the PR reuse (re-bodied
                            when it was opened elsewhere) or open, and the
                            validating handoff with its counter resets and the commit the push carried (decided
                            once ahead of the push -- the one that passed the gate, or the checkout's own head
                            where the switch named none -- and made durable there), written durably ahead of the
                            relabel so nothing this line spends is stranded on an issue that has moved on and a
                            relabel that fails leaves the branch recognizable -- refused,
                            recoverably, on a checkout that has left the approved commit or stopped being provably
                            clean around it -- both asked before the push and again once the pull request is open,
                            since the worktree is writable while those requests run -- and spending the record of
                            that commit once the handoff it was owed lands
      parks.py              the session-limit, provider-unavailable, question, silent-failure, dirty-tree, and
                            unreadable-tree parks, the last two behind one seam so the caller asks whether the
                            tree is PROVABLY clean
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
      requested_changes.py  the PR feedback and `workflow:fixing`-labeled dev fix, plus the no-VERDICT park and
                            the split that tells a provider's failure from a reviewer's
      dev_fix.py            what a finished dev fix leaves behind: the stranded-commit probe, the size gate every
                            fix route publishes through -- told the state the run really belongs to, since the route
                            that relabels before it spawns reads its own cached labels back -- the push and the
                            approval it spends, and the round bump
      awaiting.py           the three park-reason claims on a human reply and the dev attempt they fall through to
      awaiting_resume.py    the order those claims are asked in and the resume none of them wanted
      drift.py              a body edit mid-review, the three parks that defer, and the consumed-thread watermark
      drift_outcomes.py     the `ACK:` reply that must not park, over the shared fix disposition
      recovery.py           the silent retry of a push race or dev timeout, both through the size gate -- the
                            timeout's commit is the one road to a published pull request nothing else measures --
                            the debt the push that lands pays, the held outcome that owes the caller no follow-up and
                            no relabel, and the one sentence a park that healed itself owes the thread
      rounds.py             the `review_round` a fix pays for on the one event `MAX_REVIEW_ROUNDS` counts -- a head
                            the reviewer has not seen reaching the pull request -- spent by the push that lands and
                            by the hold that sends the candidate to the adjudication, the held form handed to the
                            gate so the count is not lost to a crash in the relabel window
      models.py             the frozen records the owners hand each other
      state.py              the pinned-state keys, park reasons, and outcome tokens they share
```
