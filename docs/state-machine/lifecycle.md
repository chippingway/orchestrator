# Label lifecycle diagram

The compact reference for every arc the state machine can take, node by node. It is a summary of the handlers rather
than a second source of truth: where the two disagree, the handler pages are authoritative —
[`delivery-stages.md`](delivery-stages.md) for pickup through the PR loop,
[`conversation-stages.md`](conversation-stages.md) for `question` and `discussion`, and
[`labels-and-state.md`](labels-and-state.md) for the label vocabulary the nodes are spelled in.

```
   Legend: a node is the workflow label the issue carries. `in_review`,
   `question`, `discussion`, `done`, and `rejected` are unprefixed; every
   state the orchestrator drives itself is namespaced `workflow:<tag>`. Route,
   handler, and manifest names below are the bare tag, not a label.

   Forward (single-task happy path):
     (none) ──► workflow:decomposing ──► workflow:ready
            ──► workflow:implementing ──► workflow:validating
            ──► workflow:documenting (final-docs handoff)
            ──► in_review ──► done | rejected

   Decompose:
     decision='single' ─► label=workflow:ready  (parent itself implements)
     decision='split'  ─► create children, parent=workflow:blocked
                          (or workflow:umbrella when manifest umbrella=true);
                          child[i] = workflow:ready if no deps
                                     else workflow:blocked
     manifest invalid / question / timeout ─► park HITL

   Validating fix loop:
     workflow:validating --(CHANGES_REQUESTED)──► label=workflow:fixing
       (pre-spawn flip; dev runs with stage="fixing")
         ──► pushed fix: ++review_round, label=workflow:validating
         ──► park (timeout / no-commit / dirty / push fail):
              label stays workflow:fixing, awaiting_human=True; the
              fixing handler owns the awaiting-human cycle and on a
              human-reply pushed fix BUMPS review_round (validating
              route) or RESETS it to 0 (in_review route) —
              discriminator is `pending_fix_at`
     workflow:validating --(awaiting-human resume / drift / transient-
       recovery push)──► ++review_round, label stays workflow:validating
     workflow:validating --(APPROVED, verify ok, squash ok)──►
       label=workflow:documenting (final-docs) ──► in_review
     MAX_REVIEW_ROUNDS exhausted ─► park HITL
     squash failure ─► park HITL on workflow:validating, no relabel

   in_review (orchestrator never merges; merged arc always external):
     pr merged externally               ─► done (close + cleanup)
     pr closed unmerged                 ─► rejected (close + cleanup)
     issue closed manually, PR open     ─► rejected (no branch cleanup;
                                            operator may salvage)
     fresh PR feedback on any of the    ─► label=workflow:fixing (record
       four comment surfaces                pending_fix_at + bookmarks,
                                            clear stale park; no debounce
                                            wait, no dev spawn here)
     user-content drift (pushed or ACK) ─► workflow:validating
                                            (review_round=0; no docs hop)
     mergeable + final-docs-complete or ─► HITL ping (no relabel,
       GitHub-approved current head        awaiting_human stays false)
       + no human CHANGES_REQUESTED
       + head SHA not yet pinged
     unmergeable                        ─► park (unmergeable); a
                                            subsequent human comment
                                            routes to workflow:fixing

   workflow:fixing (terminals mirror in_review; merged arc always external):
     pr merged externally / closed unmerged ─► done / rejected
     Otherwise rescan the three in_review watermarks across all four
     surfaces; if awaiting_human with no new feedback, branch on
     park_reason + pending_fix_at. For a stuck validating-route
     transient park (`_VALIDATING_TRANSIENT_PARK_REASONS` with
     pending_fix_at unset, _try_recover_validating_transient_park
     returns "stuck"), route to workflow:resolving_conflict when the
     clean worktree is out of sync with the PR -- behind base, OR
     already on base but local HEAD != the live pr.head.sha (an
     unpushed local rebase) -- the dead-lock breaker base sync can't
     reach while parked. Every other awaiting-human shape (real agent
     question / dirty park / silent-crash / in_review-route transient)
     stays parked silently to preserve HITL. If no unread feedback at
     all, publish any commit an earlier round stranded in the worktree
     (the same clean-and-strictly-ahead probe the fix disposition uses;
     a push that lands adjusts review_round per pending_fix_at), then
     clear pending_fix_* and bounce to workflow:validating;
     otherwise honour IN_REVIEW_DEBOUNCE_SECONDS. Past the window,
     resume the dev with a `_build_pr_comment_followup` prompt and apply
     the validating fix-loop disposition. Watermarks advance ONLY to the
     max id fed to the dev. On a pushed fix, adjust review_round per
     pending_fix_at (in_review->fixing route resets to 0; validating->
     fixing route bumps by 1) and flip directly to workflow:validating.
     Docs do not run on this exit.

   workflow:resolving_conflict (operator relabel, base-sync flow on
       actual rebase conflicts, or the fixing worktree-drift breaker;
       capped by MAX_CONFLICT_ROUNDS):
     clean rebase, HEAD moved      ─► push, workflow:validating
                                      (++conflict_round)
     base up-to-date no-op         ─► workflow:validating
                                      (++conflict_round, no push)
     conflicts ─► dev resumes      ─► push, workflow:validating
                                      (++conflict_round)
     ahead-of-remote recovered     ─► push, workflow:validating
                                      (++conflict_round)
     already-rebased, behind stale ─► force-publish, workflow:validating
       orchestrator-produced head     (++conflict_round); else
                                      diverged_branch park
     awaiting-human resume push    ─► push, workflow:validating
                                      (++conflict_round)
     drift pushed fix              ─► workflow:validating
     drift ACK / drift _on_question park ─► no relabel; rebase still
                                            unfinished, next tick
                                            re-enters the same label
     conflict_round >= MAX_CONFLICT_ROUNDS ─► park awaiting human
     pr merged externally / closed unmerged ─► done / rejected (terminal)

   any dispatched issue, ahead of every handler (the reuse guard):
     ancestry names a snapshot ─► the RECEIPT first, and it is authoritative:
       ref                         one comment of ours on this child marked
                                   with the owner|cycle|generation its
                                   ancestry names. It outranks every reading
                                   of the ref -- a mirror nobody dropped and a
                                   ref pushed again at the same commit both
                                   look untouched -- so a thread that could
                                   not be READ holds the dispatch rather than
                                   falling through to them. Where the thread
                                   answered and carries none, ask this
                                   host's mirror, resolved and compared
                                   against the recorded commit (free: a
                                   reclamation drops it BEFORE the remote ref
                                   and refuses to take the remote while it
                                   survives; a copy at another commit is an
                                   agent's write and reads as no copy) -- and
                                   only
                                   where the ancestry carries
                                   late_ancestry_mirror_first, since a pointer
                                   written before that ordering may have a
                                   mirror standing beside a reclaimed ref --
                                   and then one read-only ls-remote for the
                                   exact ref and commit. Three answers: absent
                                   is reclaimed and parks; mismatch is the ref
                                   under somebody else's commit and parks
                                   (late_snapshot_repointed), touching the ref
                                   itself no more than the reclamation would;
                                   unreadable is an outage, which parks
                                   nothing and writes nothing -- the dispatch
                                   is HELD and asked again next tick.
                                   A park -> drop the pointer, say so
                                   (late_snapshot_reclaimed) naming the ref
                                   and the owner, and return before the
                                   label's handler is reached -- INCLUDING a
                                   reopened done|rejected child, which is
                                   otherwise a dispatch no-op, and a relabel
                                   straight to another stage. Evaluated on the
                                   child's own dispatch, so no other writer
                                   can undo it
     no ancestry, but the body ─► the same receipt, matched against the lineage
       carries the split's own      the BODY claims: the split records a child
       child marker                 before it seeds one, so a failed seed
                                    leaves exactly this. No receipt is not
                                    permission -- the ref goes before any
                                    receipt does -- but a body is not
                                    authority either, so the OWNER's
                                    generation is read fresh and has to vouch:
                                    same cycle and generation, this issue
                                    among late_consumers. Unvouched -> nothing
                                    (a marker anyone can paste parks nobody);
                                    unreadable, opaque, or no recorded
                                    candidate -> HOLD; vouched -> the ref that
                                    identity names, asked against the commit
                                    the owner recorded, and the same four
                                    answers as above. A park -> write the
                                    claimed lineage back (never the pointer),
                                    which repairs the record and stops it
                                    being asked again
     no ancestry and no marker ─► nothing, and no request
       in the body
     ancestry present, no ref  ─► nothing: this guard has already answered for
       on it                       this child
     label=workflow:decomposing ─► stepped aside, with the adjudication guard
       AND a live generation on    beside it: an issue under adjudication is
       the record                  working from its own candidate, not an
                                   ancestor's. The label alone is not enough
                                   -- a consumer closed while it was being
                                   decomposed reopens on it with no
                                   generation at all, and is asked like any
                                   other child

   the same dispatch, on the same pinned read (the pair below is asked
       AHEAD of the reuse guard above, since both RUN rather than merely
       answer; the greeting refusal is asked behind it):
     late cycle a close ended, ─► the closed-owner ending below, run from
       cleanup unfinished          wherever the owner was left: reaches no
                                   handler, and writes that cycle's rejected
                                   once nothing is owed
     the same cycle settled,   ─► the RESTART. Mint cycle+1 behind a pending
       its rejected PROVED         marker, post one notice scoped to it, apply
       applied, and an operator    label=workflow:decomposing (DECOMPOSE=on)
       has reopened the issue      or workflow:implementing (off), then retire
       and taken the label off     the marker -- which projects the pinned
                                   comment onto the fresh cycle. Asked one
                                   step ahead of the ending above, since a
                                   restart writes its label BEFORE it retires
                                   its marker and the ending would otherwise
                                   hand the issue rejected again.
                                   ALLOWED_ISSUE_AUTHORS is not asked: taking
                                   a label off is a write only a repository's
                                   own people may make. backlog|paused defer
                                   the whole of it; a refused notice or label
                                   keeps the marker and resumes next tick
     no workflow label, a      ─► nothing, logged once a tick. Pickup GREETS
       pinned comment already      an issue and mints its pinned comment, so a
       on the issue, and no        second greeting writes a second one every
       restart authorized          later read shadows. Apply a workflow label
                                   by hand to drive such an issue again

   workflow:blocked (per tick):
     all children = done       ─► parent=workflow:ready
     any child = rejected      ─► park HITL on parent
     dep_graph walk: any workflow:blocked child with all deps=done
                               ─► child=workflow:ready

   workflow:umbrella (per tick):
     all children = done       ─► settle what the late split still owes the
                                  remote, THEN parent=done, issue closed
                                  (no implementation). The branch is retried
                                  unconditionally; a held snapshot ref is
                                  deleted once every recorded direct consumer
                                  has ENDED -- read off the consumer's issue
                                  state, not its label, since reopening keeps
                                  done/rejected. Whether the list names ALL of
                                  them is read off the record's PHASE: while
                                  `splitting` stands it may be short by a
                                  child already on GitHub, empty or not, so
                                  nothing is reclaimed; either side of the
                                  loop it is whole, which is also what lets an
                                  EMPTY list settle a ref no child was cut
                                  from.
                                  EVERY obligation that is not
                                  `reconciled` holds the terminal (a RETAINED
                                  ref included), as does an opaque RESOURCE
                                  ledger or a damaged cycle identity -- the
                                  label stays, which IS the retry, and the
                                  reason is logged on every tick that holds.
                                  An opaque CONSUMER list keeps the ref and
                                  frees the branch: the two ledgers are
                                  written apart and refused apart
     snapshot delete           ─► entry=`reclaiming` BEFORE the delete, then
                                  RE-READ every recorded consumer past that
                                  write and act only if all still ended (a
                                  reopen inside the window keeps the ref and
                                  leaves the entry `reclaiming`); delete --
                                  this host's MIRROR first, and one that will
                                  not go leaves the remote ref alone, so a
                                  surviving mirror can never mean a reclaimed
                                  remote (a transport that raises reads as
                                  REFUSED and emits snapshot_delete_failed);
                                  TELL every consumer, then
                                  entry=`reconciled`. The ref
                                  is never recreated; a refused delete tells
                                  nobody
     telling one consumer      ─► one COMMENT and nothing else, carrying a
                                  marker naming this owner/cycle/generation so
                                  it is said once. This owner never writes a
                                  consumer's pinned state: that is written
                                  whole by whoever writes it, a finalize sets
                                  its terminal label BEFORE its last write,
                                  and closed ready|blocked are swept by
                                  nothing. A consumer it could not reach
                                  leaves the entry `reclaiming`
     `reclaiming` | `failed`   ─► retried past the consumer proof ONLY for a
       whose consumers are no      ref the remote no longer has: one read-only
       longer all ended            ask decides, and a surviving ref is kept
     any child = rejected      ─► park HITL on parent -- and settle the same
       | closed without a          ledger on the way out, from the same fresh
       terminal label              scan: both dispositions CLOSED the child
                                   they name, which is what the reclamation
                                   rule reads, and nothing revisits an OPEN
                                   umbrella either. It decides no terminal:
                                   the park stands, and the issue stays open
                                   on the label that brings the next tick back
     dep_graph walk: any workflow:blocked child with all deps=done
                               ─► child=workflow:ready

   closed on workflow:decomposing | workflow:umbrella | workflow:ready |
   workflow:blocked (cleanup sweep, on the CLOSED_ISSUE_SWEEP_EVERY_N_TICKS
   cadence; the ONE case where the label does not choose the handler -- routed
   by being closed, fanned out cap-exempt so an open decomposer cannot starve
   it, with that route BOUND into the submit so a reopen before the worker
   refetches cannot reach a stage handler. The first two are where an
   adjudication runs; the other two are where a decomposition outcome that
   landed after the close can leave its ending, and only their CLOSED issues
   are asked about):
     any generation            ─► mark the cycle cancelled, once, before any
                                   external call; emit one late_cancellation
                                   from that write
     held plan PR              ─► release the hold, one marked notice, close
                                   it; re-asked every visit, recorded only
                                   where the state moved
     opaque ledger             ─► nothing more but a warning; no entry on it
                                   may be reclaimed around one nobody can type
     branch / ref              ─► the umbrella terminal's rules, verbatim, on
                                   a scan this pass takes itself: retry the
                                   branch, and delete a held ref once every
                                   consumer has ended. Reopened-before-delete
                                   or an unreadable consumer keeps the ref;
                                   the branch settles either way. No consumer
                                   is written to, commented on, or relabelled:
                                   a cancelled cycle owes its children nothing
     nothing left owed         ─► label=rejected, which ends the cycle and
                                   takes the issue out of this sweep. Never
                                   spawns, activates a child, or closes
                                   anything; `rejected` is the one label it
                                   writes, and a reopened owner reaches the
                                   same ending through the dispatcher's guard.
                                   The write is recorded in two phases -- the
                                   cycle it is owed for before it, the proof
                                   it LANDED after -- and that proof is what
                                   makes an operator's later REMOVAL of the
                                   label the restart arc above

   question (operator-applied; no automatic in/out transitions):
     fresh spawn          ─► DECOMPOSE_AGENT runs read-only in issue-N
                             worktree, posts answer, park awaiting human
                             (question_answer)
     human reply          ─► resume locked session, post follow-up,
                             park again
     commits / dirty /    ─► park (question_commits / question_dirty /
       timeout              question_timeout); worktree PRESERVED for
                             operator inspection; base sync skipped
                             while label is question
     agent silent         ─► park (question_silent); worktree torn down
     issue closed         ─► label=done, stamp question_closed_at,
                             cleanup (terminal)
     relabel to           ─► implementing's guard: clean worktree AND
       workflow:implementing  branch ─► drop question park, resume dev;
                             dirty or branch has commits ─► park
                             (question_unsafe_relabel)

   discussion (operator-applied; nothing routes IN, and the only automatic
   ways out are the terminals below: the verdict the humans leave on the plan
   PR, and a close of the issue before one exists):
     first tick           ─► decomposer agent opens the design discussion in
                             the issue-N worktree; response posted, park
                             (discussion_response); worktree PRESERVED
     plan PR recorded,    ─► nothing: no agent, no comment, no write, no
       still open            teardown; the design is with the humans and the
       (plan path +          label stays `discussion` -- which is also what
        pr_number)           keeps a manually CLOSED issue in the closed-issue
                             sweep until that PR resolves. A PR that could not
                             be fetched holds the same way
     plan PR merged       ─► label=done, stamp merged_at, usage receipt, emit
                             pr_merged (stage=discussion), close the issue,
                             then cleanup (worktree + local + remote branch)
     plan PR closed       ─► label=rejected, stamp closed_without_merge_at,
       without merging       usage receipt, emit pr_closed_without_merge
                             (stage=discussion), close the issue, then cleanup
     issue closed with    ─► label=rejected, stamp closed_without_merge_at,
       no plan PR            usage receipt; no event and NO teardown -- the
                             branch may hold an unpublished plan commit or a
                             PR the issue arrived here carrying
     HEAD moved off the  ─► the commit is judged WITHOUT spawning: the agreed
       recorded round SHA    plan is published as the ended round would have,
       on entry              anything else parks (discussion_plan_invalid), so
                             no round inherits it as its baseline
     dirty tree on entry  ─► park (discussion_stranded) WITHOUT spawning; the
                             checkout is left untouched for inspection
     unreadable tree on   ─► park (discussion_unreadable_worktree) WITHOUT
       entry                 spawning; nothing proved it empty, so nothing
                             recreates over it
     the plan's own PR    ─► record its number WITHOUT pushing and WITHOUT a
       already decided        park: the branch a merge deleted is not recreated,
       (merged, or closed     no second pull request is asked for, and no
        without merging)      replacement is opened over a design a human turned
                              down. The humans have decided, so nothing tells
                              them to go and review it -- the terminal above
                              reads those records next tick and finishes the
                              issue `done` or `rejected`
     issue closed inside  ─► the same lookup, run by the terminal instead: a
       that window            decided PR finalizes the issue (pr_number and
                              branch recorded first), an open one holds with the
                              label and checkout intact, and no PR at all falls
                              through to the pre-PR close above
     agent commits the   ─► record the tip being published, push, find-or-open
       agreed plan alone     the plan PR, record plan path + branch +
                             pr_number, re-anchor on the published tip, park
                             (discussion_plan_published); LABEL KEPT
     agent commits        ─► park (discussion_plan_invalid) naming the paths;
       anything else         a run that wrote outranks how it ended. "Anything
                             else" includes a deleted plan and an unreadable
                             worktree: neither proves the artifact is there
     push fails           ─► park (discussion_push_failed); the commit stays,
                             and a reply retries the publication the recorded
                             tip still marks as in flight -- settled before any
                             local probe, so a host that has lost the checkout
                             and the ref retries it from the remote too
     plan-shaped commit   ─► park (discussion_commits) via the blocked resume:
       under a park, with    a commit no round of this stage was running for,
       no round open and     and no publication of its own began, is not this
       no recorded tip       stage's to publish
     recorded tip the     ─► park (discussion_stale_publication) once: while a
       branch has moved      publication is in flight it answers for the
       off                   branch, so a second plan-shaped commit is refused
                             rather than published in the first one's name.
                             A branch back at the round's anchor spends the
                             marker instead -- but only once the remote is
                             shown not to carry the commit it names, or a plan
                             already pushed would be dropped from the record
                             with its pull request left open
     plan committed by a  ─► park (discussion_plan_unattributed): a PR body
       round that recorded    that cannot name the conversation the plan came
       no session             out of is not published
     resumed round paused ─► published on the next tick: the open-round flag
       or cut short after    written before the spawn is what attributes the
       committing the plan   commit under a park that is still durable
     recorded tip under a ─► the publication is finished on the spot, before
       park that is not      the turn-taking gate: its own write already spent
       discussion_push_      the reply that would otherwise carry the tick
       failed                there
     agent timeout        ─► park (discussion_timeout)
     dirty tree after the ─► park (discussion_dirty); the response is NOT
       run                   published as a design
     agent silent         ─► park (discussion_silent)
     paused mid-run       ─► nothing published; the pre-spawn round SHA is
                             what the next tick classifies by
     parked by discussion ─► nothing: no agent, no comment, no write
     parked by any other  ─► the first round opens anyway; that park is not
       stage                 waiting on a reply this stage will ever get
     relabel to           ─► implementing's guard: clean worktree, and a
       workflow:implementing  branch still at the round's recorded SHA (so its
                             commits are the ones the issue arrived with) ─►
                             drop discussion park, resume dev; dirty or a
                             moved/uncertified branch ─► park
                             (discussion_unsafe_relabel)
     human relabel        ─► done | rejected

   any stage ──► [park: awaiting_human=true]
                       (timeout, dirty tree, question, push fail,
                        unknown verdict, max rounds, retry budget
                        exhausted, failed checks, conflict-rounds
                        exhausted, invalid manifest)
                 wait for new human comment ──► resume locked
                                                 session (backend + args)
```
