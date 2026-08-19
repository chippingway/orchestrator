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
     all, clear pending_fix_* and bounce to workflow:validating;
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

   workflow:blocked (per tick):
     all children = done       ─► parent=workflow:ready
     any child = rejected      ─► park HITL on parent
     dep_graph walk: any workflow:blocked child with all deps=done
                               ─► child=workflow:ready

   workflow:umbrella (per tick):
     all children = done       ─► parent=done, issue closed
                                  (no implementation)
     any child = rejected      ─► park HITL on parent
     dep_graph walk: any workflow:blocked child with all deps=done
                               ─► child=workflow:ready

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
