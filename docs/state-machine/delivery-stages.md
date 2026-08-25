# Delivery stage handlers

The stages that carry an issue from pickup to a merged PR: pickup and decomposition, the family walks that hold a
parent behind its children, the dev / reviewer / docs loop, and the two labels a PR bounces through. Each section is
one handler — its trigger, the pinned state it reads, its internal flow in the order a tick runs it, and every
transition it may produce — plus the drift hook the drift-sensitive handlers share.

The two operator-applied conversation stages are in [`conversation-stages.md`](conversation-stages.md); the labels,
per-tick flow, and pinned-state keys these handlers are typed by are in
[`labels-and-state.md`](labels-and-state.md); the compact lifecycle reference is in [`lifecycle.md`](lifecycle.md).
Which module owns each handler is in
[`../architecture/workflow-modules.md`](../architecture/workflow-modules.md) and the dispatch that reaches one in
[`../architecture.md#stage-handlers`](../architecture.md#stage-handlers); what each agent role's prompt grants and
forbids is in [`../workflow.md`](../workflow.md).

## `_handle_pickup` (no label → `workflow:decomposing` or `workflow:implementing`)
- **Trigger**: open issue with no workflow label.
- **Input**: issue title/body/comments; `config.DECOMPOSE` (default on); `config.ALLOWED_ISSUE_AUTHORS` (default empty
  → allow all).
- **Action**: when `ALLOWED_ISSUE_AUTHORS` is set, an issue authored by anyone outside the list is silently skipped
  (log only); otherwise post a "picking this up" comment, anchor `pickup_comment_id`, snapshot `user_content_hash`
  over title + body + non-orchestrator comments, then route to `workflow:decomposing` (`DECOMPOSE=on`) or
  `workflow:implementing` (`DECOMPOSE=off`) and run that stage's handler in the same tick, so an unlabeled issue's
  first tick ends inside its second stage.

The allowlist, both routes, and the order they publish the comment, hash, label, and pinned state in all live in
`workflow/engine/pickup.py`; the same-tick handler call is a call-time import of the chosen stage's owner under
`workflow/stages/` — `decomposition/run.py` for one route, `implementing/handler.py` for the other.

## User-content drift detection

The drift-sensitive handlers — `_handle_decomposing`, `_handle_ready`, `_handle_blocked`, `_handle_umbrella`,
`_handle_implementing`, `_handle_validating`, `_handle_documenting`, `_handle_in_review`, `_handle_resolving_conflict`
— run `_detect_user_content_change` somewhere in their flow. The hash covers the issue title, body, and every
human-authored *issue-thread* comment body (PR-conversation comments are not in the hash). The hash, the six filters
below, and the routes a detected drift is handed to all live in `workflow/engine/drift.py`.

`_handle_in_review` is the exception in ordering: it runs the four-surface fresh-feedback ID scan FIRST and routes any
unread human comment past those watermarks to `workflow:fixing`, so the drift check that follows reacts only to
changes the ID scan didn't catch (title/body edits, and edits to existing issue-thread comments whose ids are already
below the watermark).

`_handle_fixing`, `_handle_question`, and `_handle_discussion` deliberately skip the drift check. `_handle_fixing`
refreshes `user_content_hash` itself once it has consumed the PR-side feedback; `_handle_question` and
`_handle_discussion` run their own conversation flows on an operator-applied label nothing routes into, so rerouting
an edited issue to `workflow:decomposing` would take it out of the conversation a human deliberately put it in.

Non-human content is filtered six ways:

- pinned-state comments by `PINNED_STATE_MARKER`;
- orchestrator-posted comments by `_ORCH_COMMENT_MARKER` (an HTML comment embedded via `_with_orch_marker`, invisible in
  rendered Markdown, survives id-cap eviction);
- legacy orchestrator comments by id from `orchestrator_comment_ids`;
- third-party Bot/App accounts (Dependabot, Renovate, CI bots) via GitHub's `user.type == "Bot"` structural flag;
- a bare `/orchestrator continue` operator command via `_is_bare_orchestrator_continue` — it is an operator control, not
  requirements content, so it must not shift the hash and route the nudge through drift handling instead of the stage's
  intentional session-limit retry (a comment carrying the command *alongside* genuine guidance is not bare, so it still
  shifts the hash);
- untrusted authors via `github.comments.is_trusted_author` when `ALLOWED_ISSUE_AUTHORS` is set (opt-in; empty
  allowlist trusts everyone), so an outsider's comment cannot shift the hash and re-trigger drift on a public repo.
  The same trust helpers filter the conversation text fed to agent prompts: `_recent_comments_text` (implement /
  review / documentation / decompose / question / drift-resume) and `_thread_text` beneath it, which the `discussion`
  stage calls directly over its own thread snapshot — with one documented retention, the orchestrator's own comments
  by recorded `orchestrator_comment_ids`, since that stage's full-context prompt rebuilds a conversation the
  orchestrator is half of (see
  [the trust boundary](../security.md#comment-trust-boundary-allowed_issue_authors)); the awaiting-human resume paths
  that quote new
  replies directly (`filter_trusted` in the implementing, validating, decomposing, documenting, resolving_conflict,
  question, and discussion resumes) plus the auto-rebase-park retry-unpark in `_sync_pr_worktree_to_base`; and the
  four-surface
  PR-feedback scans driving the `in_review` -> `workflow:fixing` route, the fixing dev-resume, and the `/orchestrator
  continue` batch replay (`filter_trusted` in `_scan_fresh_pr_feedback`, the drift-resume PR-conversation block,
  `_rescan_fixing_feedback`, and `_reconstruct_pending_fix_batch`). On every awaiting-human resume — and the
  auto-rebase retry-unpark — the filter runs on the whole `comments_after` batch up front, so it gates the non-empty
  check, the quoted follow-up, the consumed-watermark advance, and — in `workflow:validating` — the `/orchestrator
  add-review-rounds` review-cap command and the reviewer-respawn nudge; an untrusted comment resumes none of those
  sessions and does not advance the watermark (it is re-filtered on each later tick, never marked consumed). An
  untrusted comment therefore neither shifts the drift hash, sets a pending-fix bookmark, routes `in_review` to
  `workflow:fixing`, resumes an awaiting-human decomposer / developer / reviewer / question / documenting session,
  retries a parked auto-rebase, satisfies the `/orchestrator add-review-rounds` review-cap command, nor reaches any
  agent prompt.

`_detect_user_content_change` durably persists the baseline on its FIRST encounter via `gh.write_pinned_state`, so an
early-return tick cannot silently absorb a later edit as the new baseline. It also carries a **legacy-hash
normalization** path: a baseline written by the pre-issue-#729 algorithm counted a bare `/orchestrator continue`
comment, so after deploy it would compare unequal to the new hash even with no real edit. Before reporting drift the
helper recomputes with the old algorithm (`_compute_user_content_hash(..., include_bare_continue=True)`); if that
reproduces the stored baseline the delta is purely the algorithm change, so it persists the new baseline and reports no
drift — a bare continue outstanding at deploy time cannot fire one false "issue body/content changed" route. On drift
the action depends on lifecycle position:

- **`workflow:decomposing`** — handled inline at the top of `_handle_decomposing`: drop `decomposer_session_id`, wipe
  `children` / `dep_graph` / `expected_children_count` / `umbrella`, clear park flags, post a `:pencil2: issue content
  changed` notice, then fall through in the same tick so the decomposer re-spawns against the updated body.
- **`workflow:ready` / `workflow:blocked` / `workflow:umbrella`** (no implementation has started) — route back to
  `workflow:decomposing` via `_route_drift_to_decomposing`: same state-wipe + notice, plus a label flip to
  `workflow:decomposing`. `decomposer_agent` is preserved across this transition so a mid-flight `DECOMPOSE_AGENT` env
  flip cannot retarget an in-flight issue. Any previously-tracked children are listed in the notice as ORPHANED — the
  orchestrator no longer tracks them, so the operator must close any that no longer apply.
- **`workflow:implementing` / `workflow:validating` / `in_review` / `workflow:resolving_conflict`** (a dev session
  exists and possibly a PR) — post a `:pencil2: issue body changed; resuming dev session` notice (on the issue for
  implementing/validating, on the PR for in_review/resolving_conflict), advance `last_action_comment_id` past every
  visible comment, resume the locked dev session with `_build_user_content_change_prompt`, and route the result
  through `_post_user_content_change_result`.
- **`workflow:documenting`** — route back to `workflow:validating` (no docs spawn) — see the handler section below.

Result routing in `_post_user_content_change_result`:

- a shutdown-`interrupted` resume short-circuits before any branch below: the helper self-guards (returns `"parked"`
  without posting, parking, or pushing) and the drift callers in turn bail WITHOUT writing pinned state (in_review /
  resolving_conflict guard ahead of the helper via `_ignore_if_interrupted`), so the killed run leaves durable state
  untouched for the next process to retry;
- a clean pushed fix hands straight back to `workflow:validating` from every stage that runs the drift resume; from
  `workflow:implementing` the drift path runs `_on_commits` to open/push the PR;
- a no-commit reply whose clean HEAD is strictly ahead of the remote PR branch (a fix a prior parked / interrupted run
  committed but never pushed) is published through the push tail and counted as a pushed fix (`_stranded_fix_unpushed`),
  ahead of the ack check;
- a no-commit reply is otherwise treated as an ack ONLY when it carries the explicit `ACK: <reason>` marker the resume
  prompt instructs the dev to emit when existing work already satisfies the edit;
- any other no-commit response falls back to `_on_question` and parks awaiting human.

Per-stage specifics:

- For **`in_review`** drift, both the "pushed" and "ack" outcomes reset `review_round` (a drift invalidates the prior
  approval) and bounce directly back to `workflow:validating`. The drift block also captures unread PR-conversation
  comments past `pr_last_comment_id` BEFORE posting its notice so the shared id space doesn't silently swallow a PR
  comment.
- For **`workflow:resolving_conflict`** drift, ONLY the "pushed" outcome relabels back to `workflow:validating` (with
  `review_round=0`, `conflict_round` bumped). Ack and parked outcomes stay on `workflow:resolving_conflict` — the
  rebase work is still unfinished. An `interrupted` resume (shutdown sweep killed the run mid-flight) short-circuits
  BEFORE `_post_user_content_change_result` and returns WITHOUT writing pinned state, so the refreshed
  `user_content_hash` / consumed-comment changes are discarded and the next process re-detects and re-runs the drift
  resume (the caller guards via `_ignore_if_interrupted` ahead of the helper; the shared helper also self-guards on
  interrupted as a backstop, returning `"parked"`). A mid-run `paused` / `backlog` (`pause_guard=True`) short-circuits
  the same way, right after the interrupted check.
- For **`workflow:implementing`** drift, the resume runs only when `dev_session_id` is recorded. With recovered
  unpushed commits but no session the handler parks (the commits were authored against the pre-drift body). With no
  session, no recovered commits, and `awaiting_human=True`, park flags are cleared so the fresh-spawn branch fires
  this tick against the updated body.
- For **`workflow:validating`** drift, the handler defers to the awaiting-human branch when `park_reason` is
  reviewer-side (`reviewer_timeout` / `reviewer_failed`): a "retry" reply after a reviewer failure must re-spawn the
  reviewer, not the dev. The new baseline is still persisted so the next tick doesn't loop.

The hash is re-persisted on every reaction so a single edit triggers exactly one re-route, not a loop.

## `_handle_decomposing` (label `workflow:decomposing`)
- **Trigger**: each tick while the label is `workflow:decomposing`.
- **Input**: issue + comments + pinned state (`decomposer_agent` / `decomposer_session_id`, retry-budget keys,
  `children`, `dep_graph`, `expected_children_count`, `umbrella`).
- **Internal flow**:
  1. **User-content drift check** (inline) — see drift section above.
  2. **Half-finished decomposition recovery.** If `expected_children_count` is set OR `children` is non-empty (a prior
     tick crashed mid-split), the handler cannot safely respawn the decomposer. When `expected_children_count` is set
     and `len(children) < expected_children_count`, park with `decomposition_crash`. Otherwise repair any child whose
     pinned `parent_number` was never seeded, then finalize to `workflow:umbrella` (when the flag is true) or
     `workflow:blocked`. Two owners take those markers away from this recovery: an issue already parked awaiting a
     human, and one carrying a live late generation — the split transaction writes the same two markers and resumes
     from its own durable facts, so finalizing on its behalf would hand a parent on before its snapshot, its
     supersession, or what the remote is owed had been settled. Either way the tick ends having changed nothing.
  3. **DECOMPOSE kill switch.** If `config.DECOMPOSE` is off when this handler runs, clear decomposer-side park flags,
     ratchet `last_action_comment_id` past every visible comment, flip the label to `workflow:implementing`, and fall
     into `_handle_implementing`. Step 2 runs first so orphan children are not abandoned. An issue carrying a live
     late generation — recorded, not cancelled, and either oversized or still owing the post-agent owner read — takes
     neither branch: the tick returns leaving it exactly where it is, because the legacy route would publish a
     committed candidate measured past the ceiling as though a `single` verdict had been recorded for it. The owed
     read is the half a size-keyed gate misses: a revision that came back UNDER the ceiling is no longer oversized,
     and nobody has established that the issue it belongs to is still open. The same issue relabelled by hand never
     reaches this handler — or any other — at all: the dispatcher puts the label back first. See
     [`../workflow/roles.md`](../workflow/roles.md#what-the-humans-can-still-change-while-a-candidate-is-frozen).
  4. **Awaiting-human resume OR fresh spawn.** Resume on a new comment; otherwise gate on the per-issue retry budget
     (shared with `implementing`), ensure a read-only worktree, resolve the spec via `_read_decomposer_session`, persist
     `decomposer_agent` BEFORE invoking `run_agent`, and spawn the decomposer. A mid-run `paused` / `backlog` re-check
     (`_paused_during_agent_run`) right after the run returns short-circuits both branches BEFORE the usage fold,
     timeout / read-only park, manifest parse, child creation, or relabel, so the next tick re-runs the decomposer from
     durable state.
  5. **Read-only check.** If the worktree now has commits or dirty files, park awaiting human and KEEP the worktree for
     operator inspection. The decomposer is read-only — without this guard, `_handle_implementing`'s recovery path
     would later push decomposer-authored work as implementation.
  6. **Parse the manifest** via `_parse_manifest` (regex captures the fenced ` ```orchestrator-manifest ` block):
     - invalid manifest → park with the parse error.
     - no fenced block → treat as a question; park.
     - `decision == "single"` → post the collected-context comment (rationale plus the manifest's optional
       `affected_files` / `notes`, built by `_build_single_decision_comment`) so the implementer inherits the
       decomposer's groundwork via `_recent_comments_text`; label `workflow:ready`, stamp `decomposed_at`.
     - `decision == "split"` → for each child call `gh.create_child_issue(...)` with label `workflow:blocked` (the
       child's only birth label) and seed the child's pinned state with `parent_number`; persist `children` /
       `dep_graph` / `umbrella` on the parent; activate no-dep children by flipping `workflow:blocked` →
       `workflow:ready` (best-effort, since `_handle_blocked` / `_handle_umbrella` also treats no-dep children as
       deps-satisfied).
- **Output**: parent → `workflow:ready` / `workflow:blocked` / `workflow:umbrella` / `workflow:implementing`, OR a
  HITL park.

## `_handle_ready` (label `workflow:ready` → `workflow:implementing`)
- **Trigger**: each tick while the label is `workflow:ready`. Reached by a `single`-decision parent or a
  freshly-created child.
- **Action**: post the pickup comment if needed, bump `last_action_comment_id` to the latest visible comment id (so
  comments posted while the issue sat in `workflow:decomposing` / `workflow:blocked` are marked consumed before the
  implementer reads them at spawn), flip to `workflow:implementing`, fall through into `_handle_implementing` on the
  same tick.

## `_handle_blocked` (label `workflow:blocked`)
- **Trigger**: each tick while the label is `workflow:blocked`.
- **Input**: pinned `children` (parent only), optional `dep_graph`, `parent_number` (child only — seeded at
  child-creation time).
- **Internal flow**:
  1. No `children` and `parent_number` is set → no-op (the parent walks the dep graph).
  2. No `children` and no `parent_number` (manual relabel suspected) → park.
  3. Read each child's current label.
  4. Any child `rejected` → park parent awaiting human.
  5. Any child closed but its label is not `done` / `rejected` / `in_review` → retry `_finalize_if_pr_merged` (covers
     an externally-merged child whose own handler has not yet finalized) before falling through to the manually-closed
     park.
  6. Every child `done` → flip parent → `workflow:ready`.
  7. Walk children: any `workflow:blocked` child whose recorded dependencies are all `done` gets relabeled
     `workflow:ready`. A child with no recorded deps is also flipped (vacuous all-done over an empty list).
- **Output**: parent → `workflow:ready` (all done), OR a sibling unblocked, OR a HITL park, OR a no-op for a child
  still waiting on its dependencies.

## `_handle_umbrella` (label `workflow:umbrella`)
- **Trigger**: each tick while the label is `workflow:umbrella` (only ever a parent — set by the decomposer when the
  manifest's `umbrella` boolean is true).
- **Input**: pinned `children` and optional `dep_graph` on the parent, plus the late generation's obligation ledger
  when the umbrella was made by a late split.
- **Internal flow**: mirrors `_handle_blocked` for the rejected / manually-closed checks and dep-graph walk. The only
  difference is the all-done terminal: when every child reaches `done`, reconcile whatever the issue still owes a
  remote, and only then post a checkmark comment, stamp `umbrella_resolved_at`, set label `done`, and close the issue.
  A `children`-less umbrella is treated as corrupt state and parks.
- **What the terminal waits on.** An umbrella made by a late split
  ([`../workflow/roles.md`](../workflow/roles.md#what-a-cleared-split-actually-does)) owes two things — the branch its
  superseded candidate was committed on, and the immutable ref that candidate was preserved under — and this is the
  last tick that could settle either: nothing revisits a closed umbrella, and no other handler reads that ledger. So
  `late_cleanup` retries every `branch` entry that is not `reconciled` — taking down the remote ref, the checkout,
  and the local ref, and settling the entry only once a read afterwards proves all three gone — and deletes each held
  `snapshot_ref` once every recorded direct consumer has **ended**, which all-children-resolved has just made true,
  proved off the child scan this handler already took rather than off requests of its own. "Ended" is the consumer's
  own issue state, not its label: reaching `done`, being `rejected`, and a human closing it all close the issue, and
  reopening preserves the label — so a child reopened while still wearing `done` is live again and keeps the ref. A
  branch target outside the orchestrator namespace or belonging to another issue is refused rather than deleted; a
  consumer that cannot be proved ended keeps the ref.
- **A park settles the same ledger, and decides no terminal.** All-children-resolved is not the only reading that
  ends every consumer: a child `rejected` and a child closed by hand both park the parent for a human, and both
  closed the child — which is the reading the rule takes. Since nothing revisits an *open* umbrella either, a park
  that returned before settling would hold a reclaimable ref and a superseded branch for as long as the human took
  to answer. So the parked path runs the same settlement from the same fresh scan that parked it, reports only what
  it actually did, and leaves the park itself untouched: still `awaiting_human`, still open, still on `umbrella`.
- **Whether the ledger names every consumer is asked first**, off the record's own phase, because the proof above is
  only as complete as the list it walks. A child is created and then recorded in two writes — it must be, since a
  child on GitHub the parent does not record is a child nothing would come back to — so while `splitting` stands the
  list may be short by one that already exists. Its length decides nothing there: a set of ended consumers says as
  little about the child it has not reached as an empty one does, and nothing on the ref is reclaimed either way.
  Either side of the loop the list is whole — before the split nothing has been created, and past it the loop ran to
  the end — which is also what lets an *empty* list settle a ref no child was ever cut from, the snapshot being
  retained ahead of the first child. A restarted cycle, or a phase this binary cannot type, proves nothing and keeps
  the ref.
- **The boundary an interrupted transaction stood at is kept, and a phase before the loop is believed only as far as
  the record bears it out.** A phase is not written only forwards: a transaction re-entered after a crash comes back
  through the whole coordinator, so the plan-PR hold reconciled before anything spawns, the spawn itself, and the
  claim each completion writes would each name a boundary of their own. None of them is written over
  `snapshotting`, `splitting`, or `superseding` — the record refuses that move itself — so a re-entered split
  carries every one of those steps under the boundary it interrupted. That
  matters most in the window with *nothing* recorded, which no ledger can speak to: a child is created before the
  write that records it, so a loop that died between the two leaves an empty list beside a real issue on GitHub, and
  the phase is all that says so. Beside that, the pre-split phases (`measuring` through `snapshotting`) say "nothing
  has been cut from this ref" only on a record that shows no split ever started — a consumer or a split child on
  the ledgers, or the `expected_children_count` the transaction writes in the same durable step as `splitting`,
  ahead of its first create. That count is what upgrades a pinned comment an EARLIER binary already rewound: the
  guard stops new rewinds and nothing migrates records already in flight, so what has to answer for one of those
  is the evidence no phase write ever touched. That same count is then asked of *every* boundary, ahead of the
  phase, because a record the count proves finished is whole wherever it happens to be standing — and more than
  one boundary needs it. `splitting` is two answers rather than one: the phase goes down before the first create
  *and again beside every child recorded*, the last one included, so a crash between that final write and the
  announcement leaves a complete ledger wearing a mid-loop boundary. `snapshotting` is the same question one retry
  later: a transaction resumed after a park rewrites it over whatever boundary it had reached, so a finished split
  comes back wearing the one it started from. Reading either as mid-flight retains the ref for good and holds the
  terminal with it, since nothing revisits a cancelled owner to move the phase on — so the count is compared
  against the positional register the loop appends to, and a register that reached it is a loop that finished. A
  stale count from an ordinary decomposition of the same issue reads the same way and is meant to — being wrong in
  that direction keeps a ref and holds a terminal, where being wrong in the other deletes the only copy of a
  child's work. Past the loop no corroboration is needed: the transaction reaches `superseding` only once every
  child is created *and* recorded.
- **The delete is a small transaction.** The proof above is a reading of live issues and cannot be reproduced, so the
  entry is written `reclaiming` *before* the delete — which is what stops a tick that died between the push and the
  record of it from leaving a ref the ledger calls retained and the remote no longer has. Every recorded consumer is
  then re-read **past that write and immediately ahead of the delete**, because the scan the pass qualified the ref
  on was taken before the branch half ran and before anything was recorded, and each of those steps is a request a
  human can reopen a consumer during. A consumer that came back inside that window keeps the ref: nothing is asked of
  the remote, the entry stays `reclaiming`, and the terminal is held. What is left is the delete request itself,
  which is irreducible.
- **A recorded decision buys one thing.** A later visit acts on a `reclaiming` or `failed` entry only to **finish a
  delete the remote already took**: past the consumer proof it costs one read-only ask about the ref itself and
  qualifies only if the remote no longer has it. A ref still there is one a reopened child may still be cutting
  from, and no record of a past decision outranks the reading in front of it. A transport that raises rather than
  answering is read as the refusal it is, so no attempt is ever spent without a typed `snapshot_delete_failed`
  behind it.
- **The children are told before the entry closes, and told with a comment.** After a delete the remote accepted,
  and before the entry is written `reconciled`, every recorded consumer gets one comment saying the snapshot has been
  reclaimed and that reuse now needs an explicit new split cycle. It carries a hidden marker naming this owner, cycle,
  and generation, so a consumer already holding one of ours is not told twice. The ref is never recreated.
- **A cancelled cycle tells none of them.** The receipt is what a live split owes children it is still responsible
  for; an ending a human's close forced is responsible for none, and leaves each of them exactly as it found it —
  the entry reconciles on the delete alone. Nothing about the ref goes unsaid: the transport drops this host's
  mirror *before* the remote ref and refuses the whole reclamation if that copy cannot be proved gone, so a child
  reopened afterwards finds no mirror, asks the remote once, and is stopped and told by its own guard — which is
  where the receipt would only ever have been read anyway.
- **This owner never writes a consumer's pinned state.** That comment is written *whole* by whoever writes it, so a
  handler of the child's own that read it before this pass and wrote it after would silently undo anything recorded
  here — and a label is no proxy for "no writer": a terminal finalize sets `done` / `rejected` *before* its last
  write, and closed `workflow:ready` / `workflow:blocked` are swept by nothing, so a consumer left on one never
  becomes terminal at all. A comment is appended rather than rewritten, reaches a consumer in every state a consumer
  can be in, and cannot be lost. What acts on it is the child's own guard (below). A consumer the pass could not
  reach, or whose thread it could not read or post to, leaves the entry `reclaiming` rather than reconciling it —
  reconciling is what stops anything coming back, and for a closed owner this pass is the only thing that would. A
  refused delete tells nobody.

## The reuse guard (every dispatch, ahead of every handler)
- **Trigger**: `_route_issue_to_handler` on any issue whose pinned ancestry still names a snapshot ref. It shares its
  pinned read with the live-adjudication guard beside it, so it costs no extra comment walk. Both step aside for
  `workflow:decomposing` — an issue under adjudication is working from its own candidate, not an ancestor's snapshot —
  but only once that read PROVES the adjudication is the issue's own. The label alone proves nothing: a consumer
  closed while it was being decomposed comes back with the label exactly where it was and no generation at all, and
  waving it through would spawn the decomposer against the reuse instructions in its body naming a reclaimed ref.
- **Why here and not in a stage**: the issue this is about is one no handler would touch. A consumer that ended wears
  `done` or `rejected`; reopening leaves the label exactly where it was, and both are terminal no-ops below. Asking
  before the table also means a relabel straight to another stage cannot route around it.
- **Why the child decides**: the owner that reclaimed the ref cannot make this safe from its side, for the reason
  above. Evaluated on the child's own dispatch there is nobody to race: whatever a concurrent writer did to the
  record, the child reads it again and decides again.
- **What it asks, in order**: first the **receipt** — the comment the reclamation posted on this child, marked with
  the owner, cycle, and generation its ancestry names, and authored by the orchestrator's own account. That is the
  authoritative answer, because it records what *happened* rather than what a later reading suggests: a local mirror
  nobody got round to dropping, or a ref somebody pushed again at the same commit, would both make the world look
  untouched while the guarantee the child was given — that its candidate provably came from one adjudication — is
  gone. It costs one walk of the child's own thread per tick, paid only by issues a split created. A thread that
  could not be **read** is not a thread with no receipt on it, and the two may not be collapsed: everything asked
  after this can look untouched while the answer that outranks it sits unseen, so an unreadable thread **holds** the
  dispatch there and then.
- **And when no receipt landed** (a crash, a thread it could not post to): this host's own mirror, which costs
  nothing on the wire. That shortcut is bought by the order a reclamation runs in rather than assumed of it — the
  mirror is dropped *before* the remote ref is touched at all, and a mirror that cannot be proved gone refuses the
  reclamation instead of being logged past, so a mirror still present says nothing has been reclaimed (a ref deleted
  by hand is the one exception, and a child can still read the candidate out of the copy it left). "Still present" is
  read as an identity, not an existence: the copy is a ref in the object store every agent's worktree shares, so it
  is resolved and compared against the exact commit the ancestry records. A copy standing at anything else is
  somebody's write — it says nothing about the ref on the remote and is not a candidate to work from — and goes to
  the ask like an absent one.
- **The shortcut is conditioned on the pointer, not assumed of the world.** It is taken only where the ancestry
  carries `late_ancestry_mirror_first`, the stamp a split writes onto every pointer it seeds. A pointer written
  before that ordering existed belongs to a world where the remote ref went first and the mirror came down
  best-effort afterwards — so a surviving mirror there is as likely to be the residue of a finished reclamation as
  proof one never started, and the child pays the read-only ask instead of trusting it. Nothing migrates: the stamp
  is written by the binary that would do the reclaiming, so its absence is the whole question answered.
- **What the ask decides.** A mirror that is gone (or a pointer with no stamp) is worth one read-only `ls-remote`
  for the exact ref and commit the ancestry records, and the three answers are three different verdicts. `absent` is
  the reclamation this child was not told about, and it parks. `mismatch` is the ref carrying somebody else's commit
  — not the candidate this child was promised, and not something to start work against either — so it parks too,
  under its own reason (`late_snapshot_repointed`) and its own comment; nothing here re-points or deletes that ref,
  exactly as the reclamation refuses one for a human. `unreadable` is an outage, which is evidence of nothing: the
  dispatch is **held** — no park, no comment, no write, and the same question next tick — because parking every
  late-born child through a rate-limit window would be a self-inflicted stop, while continuing would start an agent
  against a ref nobody could vouch for.
- **A child with no recorded ancestry at all** is not automatically an issue of no lineage. The split records a child
  on the parent's ledger *before* it seeds that child's ancestry — a child on GitHub the parent does not record is a
  child nothing would come back to — so a seed that failed leaves an issue whose **body** carries the split's own
  marker and whose pinned comment carries nothing, while the reclamation still counts it as a consumer and still
  leaves its receipt. The body is what decides whether to look, and it costs nothing: the dispatcher already has the
  issue, and every issue no split created stops there without a request.
- **A body marker is corroborated, never believed.** It is the one lineage claim in this workflow that comes out of a
  field the world can write, while everything it competes with is authenticated — a pinned comment only the
  orchestrator writes, a receipt checked against its author. So the **owner's own generation is read fresh** and has
  to vouch for the claim: the same `late_cycle_id` and generation counter, and this issue's number among
  `late_consumers`. A claim it does not vouch for is a claim about nothing and the guard steps aside — parking an
  issue, comment and HITL mention and all, on the strength of a sentence somebody typed into its body is the
  denial of service this check refuses, and it is also the honest answer for the *other* crash window (a child
  created before its number was recorded), since an owner may not reclaim a ref while its own ledger can be short one
  child. A record that could not be read, one whose consumer list this binary cannot type, and one naming no
  candidate are a different answer: the claim may be true and this tick cannot tell, so the dispatch is **held**.
- **What a vouched claim buys** is the whole pointer the failed seed never wrote — the ref the identity mints, and
  the commit the owner recorded preserving — so the ask is the same ask the recorded shape makes: is *this* candidate
  still obtainable. It has to be asked, because the receipt cannot cover the window it is posted after: a ref is
  deleted first, so a silent thread is what that window looks like, and so is a thread this tick could not read. The
  verdicts are the recorded shape's four, re-pointed included. The park writes back the lineage the body claims —
  never the pointer, which was assembled out of the owner's record rather than out of anything this issue holds —
  which both repairs what the failed seed owed and is what stops the question being asked again.
- **What a refusal does**: drops `late_ancestry_snapshot_ref` / `late_ancestry_snapshot_sha`, parks the issue
  (`awaiting_human`, reason `late_snapshot_reclaimed`, or `late_snapshot_repointed` where the ref survived and its
  commit did not) with a comment naming the ref and the owner, and
  returns before the label's handler is reached. Dropping the pointer is what makes the guard cost nothing on every
  tick after — and both writes are taken on the issue's own dispatch, so there is no second writer to lose them to.
- **Anything not `reconciled` holds the terminal**, ref and branch alike — a `retained` ref included. There is no
  reading under which an object still on the remote is settled, and an umbrella closed over one is an object nothing
  would ever come back for: the parent is `done` by then and no pass revisits it. Keeping the label *is* the retry,
  and the reason it is held is logged on every tick that holds, since a hold attempts nothing and so writes and emits
  nothing. An opaque *resource* ledger blocks outright, and so does any ledger entry on a record whose cycle identity
  is damaged; an umbrella with no recorded generation and no ledger owes nothing and answers without a write. An
  opaque *consumer* ledger is refused separately, because the two are preserved and written separately: it is what a
  snapshot's proof would be taken from, so the ref stays — while the superseded branch, which owes no consumer
  anything, is deleted and retried as usual.
- **Output**: terminal `done`, OR a sibling unblocked, OR a HITL park, OR a held terminal (something still owed), OR
  a no-op.
- **A third question rides the same read**, and it is asked FIRST: an owner whose cycle a close already ended and
  whose ending has not been written. Cancellation is irreversible within a cycle, so a human who reopens the issue
  does not get that cycle back, and both labels an adjudication can be wearing name a handler that would act on the
  issue rather than settle it. That guard runs the cleanup below, reaches no handler, and writes that cycle's
  `rejected` ending. It comes first because it is the only one of the three that has to *run* rather than merely
  answer, and the other two can refuse indefinitely — the reuse guard *holds* a dispatch, writing nothing, for as
  long as an ancestor's ref cannot be asked about, and an owner of its own cancelled cycle nested under one would
  spend that whole outage never reconciling its own plan PR, branch, or ref. Nothing is lost by the order: a
  cancelled cycle starts no work, so neither question below is about anything it is going to do, and both are asked
  again on the tick after its ending is written.

## Closed-owner cleanup sweep (no label of its own)
- **Trigger**: an issue that is **closed** while still carrying one of the four cleanup-routed labels —
  `workflow:decomposing` or `workflow:umbrella`, where an adjudication runs, and `workflow:ready` or
  `workflow:blocked`, where an interrupted ending can be *left*. The second pair is the close/agent race made
  recoverable: a decomposition outcome writes one of them, a run spawned before its owner was observed closed lands
  after that observation, and the latch that would route the ending dies with the process — so without the query a
  restart before any cleanup pass loses the ending for good, receipt on the thread or not. Only their **closed**
  issues are asked about; an open `ready` issue is polled and dispatched exactly as ever. It
  is reached past the `backlog` / `paused` filter that parks everything else, because dropping one of these loses
  the close itself — an observed close ends the late cycle irreversibly, and this is the only pass that would ever
  record that, so an owner parked while closed would come back from a reopen and an unpause with a live generation
  and spawn against it. The control label defers what the pass would *do*, not whether the cycle ends: the sweep
  reads the same label and stops at the mark. The
  closed-issue sweep yields those four states beside its own recovery labels, on the same
  `CLOSED_ISSUE_SWEEP_EVERY_N_TICKS` cadence and through the same label cache and absent-label throttle, so it costs
  no request on a tick that sweep is skipping anyway (see
  [labels-and-state.md](labels-and-state.md#pollable-issues-and-finalization)).
- **An owner with no cycle left is asked one question before it is stepped over.** That question is the
  retirement's own correlation: a terminal that made its retirement durable and then died leaves a record naming
  which cycle it dropped, and a close observed inside that write leaves a receipt on the thread naming the same one.
  Where the two agree the cycle goes back cancelled and this pass ends it like any other, `rejected` included.
  Where they do not, what is left is an umbrella whose terminal is due and whose label never landed: that state is
  `umbrella` and closed — exactly what this sweep queries — and the record says which terminal it
  earned (`umbrella_resolved_at`), so `done` is written here. A write GitHub refuses keeps the label, which is the
  retry, so the pass after it writes what this one could not. Anything else with no cycle is left alone: every
  umbrella the initial decomposer made carries no generation and no stamp.
- **Why it is not the label's handler**: every one of the four names a stage handler that would resume the workflow
  the close ended — one spawns the decomposer, one walks the dependency graph and activates children, one hands the
  issue to a developer. The dispatcher
  therefore reads *closed* before it reads the label and routes to `late_sweep._handle_closed_owner_cleanup`
  instead, ahead of even the live-adjudication relabel guard. That classification then **binds**: the submit carries
  a `cleanup_only` route the worker cannot re-derive, so a human who reopens the issue between the poll and the
  refetch cannot turn a cap-exempt submit into an agent-spawning stage handler.
- **Reaching this route at all is what says a close was observed**, and an observed close cancels the generation
  irreversibly. So the handler's own re-read decides how far the pass goes, never whether the cycle ends: an issue
  that is open again is marked cancelled all the same and stopped there — nothing external is done to an issue
  somebody has just reopened, and no terminal is written — and the mark is what hands it to the dispatcher's own
  guard, which owns a reopened cancelled owner and settles it from the next tick.
- **A submission no pass settles is latched, not dropped.** The scheduler admits no second worker for an issue one
  is already running, and this is the only submission whose loss costs an *observation* rather than a turn: the poll
  saw the issue closed, and if a human reopens it before the next pass, no later poll sees that again. So the
  dispatcher latches the reading on `workflow/engine/observations.py` instead of discarding it, and the next tick
  reads it back and routes the issue to this sweep on the strength of it — ahead of the label, ahead of the close,
  and out of the family bucket, because the reading those come from is exactly what the reopen took away. What the
  sweep does with an owner that is open again is the bullet above: mark the cancellation and stop.
- **A pass that RETURNED is not a pass that finished the ending, and the reading is kept where nothing else would
  come back.** A cleanup can run every step and leave the ending owed: a consumer that is live again keeps the ref,
  a remote that refuses a delete keeps the branch, and the `rejected` terminal is one more request GitHub can
  decline. What that decides is only whether this reading is the *last* route. An owner still wearing any of the
  four swept labels is one a later tick reaches on the `CLOSED_ISSUE_SWEEP_EVERY_N_TICKS` cadence an operator set — the
  label staying put *is* the retry — so the latch is handed back there rather than costing a cleanup pass per tick
  for as long as the ending is owed, which for a live consumer can be indefinitely. An owner that is *open* again
  hands it back too, because the sweep may not advance a reopened issue and the dispatcher's own guard owns it. What
  is kept is an owner that is closed, still owes something, and wears a label no query asks for; a read that could
  not answer is kept for the same reason, since it established nothing.
- **What the ending owes outlives the process holding that reading, so the label is repaired too.** The sweep
  queries four labels, and an owner can be moved outside all of them — by a hand relabel, or by an operator putting
  a closed owner onto a terminal over a cycle that still owes something. Inside this process the held reading is
  what brings a tick back to such an owner; after a restart, nothing would. So a sweep that leaves an obligation
  owed puts the owner back under `decomposing` or `umbrella` (whichever the `umbrella` flag says the record
  reached), unguarded, as the repair of a move this workflow never made — and the reading is handed back once that
  repair landed, because the label is now the durable route. A repair GitHub refuses leaves the reading as the only one
  there is, and it is held and said out loud. An ending that finished is left exactly where it is: it wrote
  `rejected`, which is what takes an owner out of the sweep for good.
- **The latch is a barrier the run in flight is held to, not just a note for the next tick.** The worker that owns
  the issue asks it before every step the remote keeps, through the same owner read those barriers already take
  (`late_owner._read_owner` consults the latch before it asks GitHub). That is the reading GitHub cannot give back: a
  close and a reopen that both happened inside one of the run's own steps leaves the issue reporting `open`, and only
  the poll ever saw otherwise. A latched close therefore ends the cycle where the run stands — the cancellation
  persisted by the worker that owns the pinned comment, and nothing further spawned, created, or activated.
- **Where those barriers are, and why each one is there.** Every one of them sits immediately before a step nothing
  takes back, and each covers a window of *remote work* the poll runs beside:
  - **the child loop**, before every child including the first — the write that forces the parent to be an umbrella
    stands ahead of the first create — once more inside the create itself, since the orphan lookup that precedes it
    walks the whole repository on a resumed pass, once *behind* it, and once more between the read of the child's
    own pinned comment and the write that adds to it: the create is a request too, so is that read, and what a close
    inside either leaves is a real GitHub issue. That one is recorded either way (a child nothing names is the one
    state no pass can clean up) and written to never (a cancelled cycle owes its children nothing);
  - **each publication step** — the announcement, the supersession, and the retirement that hands the parent to
    `workflow:umbrella`;
  - **the activation walk** (`activation.py`), before *every* relabel rather than once for the walk: a relabel is a
    request, and a close latched after the first child was released must not release the second;
  - **the spawn** (`late_coordinator`), asked twice and the second time right against it — a worktree probe, a
    retry-budget write, a hold reconcile, and the write that records what this attempt IS all stand between a tick's
    own gates and the one step that puts an agent on somebody's repository. What the record then claims is an
    attempt nobody made, which the next tick reconciles for free; an agent that ran is what nothing takes back;
  - **the developer revision** (`late_revision`), three times: as the tick is entered, again right against the
    resume — the revising notice it posts in between is a request the poll runs beside — and once more when the run
    comes back, which stops the remeasure that would write a fresh candidate over a cycle a close already ended.
    The poisoned-session retry inside the shared resume is guarded with them, since that is a *second* agent and an
    issue somebody closed is owed neither;
  - **the `single` publication** (`late_settlement`), asked between *each* of its own steps — the reconciliations,
    the exemption write, the handoff label, and the accepted notice — because these are the barriers protecting the
    *record* rather than an effect: the last write drops the generation entirely, and both the sweep and a receipt
    adopted from the thread read that generation to decide there is anything to end. Past that write a refusal is
    too late, so the answer there is a **reinstatement**: the generation is still in the call's own memory, and it
    is written back and cancelled from there. What was published stays published — the exemption, the notice, and
    the handoff label are none of them this owner's to take back;
  - **the reclamation itself** (`late_cleanup.py`), between every obligation it settles, between every two of the
    receipts a reclaimed ref owes its children — each is a comment on somebody *else's* issue, so a close observed
    after the first is one the second may not be written over — between the fresh consumer
    proof and the ref delete it authorizes — a ref that is gone while the record still reads live is a reclamation
    nothing afterwards can attribute to the cancellation that earned it — and again between that delete and the
    receipts behind it — and once more inside each of THOSE, since proving a child untold is a thread walk of its own
    and the comment it authorizes stands behind it — each is a request, and the receipts are the one cleanup effect
    that writes to somebody *else's* issue. The mark does not buy a shortcut through the reclamation rules; what it
    changes is what the settling owes anybody, since a cancelled cycle tells its consumers nothing;
  - **the umbrella walk** (`umbrella.py`), past the child scan, behind the settlement its terminal waits on, and
    once more immediately before the write that records the resolution — the scan is a request per child, and so is
    the settlement. `done` is the write that cannot be recovered from, because it takes the issue off every label
    the closed-owner sweep queries, so what makes it safe is the write *ahead* of it: one pinned write that stamps
    the resolution and **retires the cycle** together, carrying the two ledgers across the way the `single`
    publication's own retirement does. A close observed before that write stops the terminal outright and leaves the
    owner on `umbrella` with the mark down, where the ending retires it to `rejected` from a label the sweep still
    queries. One arriving after it is a human closing an issue this orchestrator had already finished — every child
    resolved, every obligation reclaimed, the cycle over — which is not a cancellation, and leaves no live cycle
    under the terminal for anything to have to find. That write is itself a request, so the latch is asked once
    more *behind* it, off the same `observations.retiring` window the `single` retirement holds: there the
    answer is a **reinstatement** rather than a refusal — the generation is still in the call's own memory, so it
    goes back cancelled, no terminal is written, and the owner keeps `umbrella` where the ending reaches it. That
    barrier is this process's, so the write records `late_retired_cycle_id` exactly as the `single` retirement does:
    a process that dies before reaching it leaves a record naming the cycle it dropped and a receipt on the thread
    naming the same one, and the sweep adopts the two together rather than finishing a terminal over a close.
    Every window a crash can land in is one the next pass repairs:
    before that write the owner is on `umbrella` with a live cycle, which the sweep and the umbrella poll both
    already own, and after it the owner is on `umbrella` with the resolution recorded and no cycle at all — which
    the sweep finishes by writing the label the record already earned, retrying for as long as GitHub refuses it,
    because the owner keeps the label the sweep asks for until one lands. The closing notice is gated on the same
    stamp, so a terminal resumed after a crash says it once;
  - **the activation's own answer, carried out**. The walk holds the children it has not reached, which is the whole
    of what a shared dep-graph walk may decide; the split transaction asks again behind it and ends the cycle on the
    answer, because reporting settled would send it on to reclaim the superseded branch with no mark saying why.

  The barriers past a claim-bearing read take the latch alone: a claim names `owner_check`, and writing it over
  whatever boundary the tick actually reached is the rewind the record refuses.
- **It is latched where the close is READ**, which is the enumeration that classified the issue — not where the
  reading is later carried. Between the two stands the rest of that enumeration (a label read per issue in the
  repository) and the submit decision itself, and a worker already holding the issue asks the latch before every
  irreversible step it takes for the whole of that window: a reading installed only once the scheduler had refused
  would leave that worker free to spawn, create a child, or activate one against an issue the poll had already seen
  ended. It is taken for every closed issue the fan-out set records, which is exactly the set whose route carries a
  closed reading; a closed issue drained in the family bucket is a hard human stop with nothing to finalize.
- **A close the enumeration never saw is taken at the REFETCH.** An issue open when it was listed carries no
  reading at all — nothing was latched, because there was nothing to latch — and the refetch every route takes on
  its way to a handler can be where that stops being true. From there the reading exists in one place only, and
  everything behind it can fail: the pinned read the guard is built on answers a refusal of its own, and the write
  that marks the cancellation is a request like any other. So both refetching paths take the observation against the
  object they just got back — the sequential loop, which has no hand-off to hold one for it, and the worker, whose
  hand-off carries the poll's *older* reading instead — and hold it across the pass, so a pass that could not mark
  anything leaves the reading for the next tick rather than losing it to a reopen.
- **The durable half is written there too.** A latch is memory, so an accepted submit whose task never starts — a
  scheduler shutdown, a process that dies before the worker takes it — would otherwise leave the observation with
  nothing on the remote saying it happened, and a human who reopens the issue before the next process polls it takes
  the reading away for good. So the receipt goes on the thread while the record can still name the cycle it belongs
  to, from the object the enumeration already listed: one pinned read per closed fan-out issue, and the same read
  answers whether the reading is owed at all — an issue whose record says there is nothing to end has its latch
  dropped again right there, so the machinery is carried only by the owners that need it (and the admitted pass
  skips its own end-of-pass probe, since the poll already asked that record).
- **It is process-wide rather than per-scheduler** because the readers are stage handlers deep inside a worker, and
  the alternative is threading a scheduler through thirteen handler signatures that have nothing to do with it. It
  is dropped by the pass that RAN (`settle_close` from the worker, once its pass returned), never by the submit that
  was accepted: an accepted submit is not a cancellation persisted — the worker refetches the issue first, and that
  read can be the thing that fails — so a pass that raises anywhere latches the reading again. A task that never
  runs at all — a scheduler shutdown, or a process that dies between the submit and the worker taking it — leaves the
  latch standing, which is the point: the next tick routes the issue to the sweep on the strength of it.
- **The cycle a retirement drops is recorded outside the group that write clears.** The window above is memory and
  the barrier behind the write is this process's, so a process that dies between them leaves a receipt naming a
  cycle and a record that no longer names one — and the guard below returns on a record with no cycle, so nothing
  would ever look at that receipt. `late_retired_cycle_id` is the one fact about the dropped generation that
  outlives the drop (like `late_exempt_sha`, deliberately outside `LATE_STATE_KEYS`): a record carrying it is asked
  once per owner per process whether the thread has that cycle's close receipt, and one that does gets the cycle put
  back — cancelled, with the ledgers the retirement carried across — so the ending has something to run from. The
  correlation ends where its window does, and only there: any generation written with an identity supersedes it (the
  adoption's own mark included, which is what consumes it, and an operator's authorized restart with it). Both
  retirements that drop a cycle record one — the `single` publication's and the umbrella terminal's — because what
  the correlation is for is the process that dies before its own barrier, and that barrier belongs to whichever
  process made the write. A terminal retiring cycle N names N and nothing else, so a receipt for any earlier cycle
  on the same thread matches nothing an adoption would read.
- **A retirement in flight is a record that answers for a cycle it no longer names.** A published `single` drops its
  generation and then asks the latch, and between those two the record carries no cycle identity at all — which is
  the one thing every reader of a close consults. A poll reading it there would answer "nothing to end", drop the
  observation, and leave the barrier behind the write asking a latch nobody is holding any more. So the worker holds
  `observations.retiring_cycle` across its own write and that barrier: inside the window the record's silence proves
  nothing, the reading is kept, and the receipt the poll leaves on the thread is scoped to the cycle the window names
  — which is the only place that cycle can still be read, and what makes the durable half survive the retirement at
  all. Outside the window the same reading IS dropped, and correctly: the publication completed, and the ordinary
  terminal arc the issue's label names owns the closed issue from there.
- **The probe and the receipt are one read.** Whether the reading is still owed and what the receipt should say are
  the same question about the same record, and two reads of a record a worker is writing can disagree — one seeing a
  cycle and keeping the observation while the other sees the retirement behind it and leaves the thread saying
  nothing, which leaves the reading in memory alone for a restart to take. So the owner writes the receipt from the
  read that decides it and answers the dispatcher with what that read established; a read that failed keeps the
  reading, which is the only answer a request that established nothing is entitled to.
- **The durable half is a marked comment on the issue thread.** A latch dies with the process holding it, so the
  first pass to latch a close also posts one cycle-scoped receipt
  (`<!--orchestrator-late-close-observed:issue=N:cycle=C-->`). A *comment* rather than a pinned write for the reason
  the latch exists at all: the pinned comment is written whole, so a second writer racing the worker that owns the
  issue would drop whatever that worker recorded in between, while a comment is added and races nothing. Posting is
  best effort — a receipt GitHub refuses costs durability, not the reading, which is still latched and still ends
  the cycle on the next barrier the run reaches.
- **A refused receipt is retried, not lost.** The post is attempted by every pass that latches a close and settled
  by the first that lands one: the memo suppressing further attempts (`observations.receipt_written`) is written by
  the attempt that succeeded, so a comment GitHub declines is tried again on the next poll. Without that, an
  observation with no durable half would be one a restart takes away entirely — the latch alone does not survive the
  process.
- **The attempt is claimed, and the memo is counted against the reading it was claimed for.** Asking whether the
  thread already carries a receipt and getting one onto it are two operations, and the other two parties are inside
  that gap: a second poll owing the same observation (a worker's failed pass and the following tick's enumeration
  meet there), and the worker running the pass that settles the reading. So `observations.claim_receipt_post` hands
  out the sole right to attempt the post — one poll walks the receipt-less thread, not two — and it carries the
  per-owner **generation** that reading was taken at. Every `settle_close` moves that generation, so a receipt
  landing either side of a settlement records no memo at all: without it the memo would stand for a reading nobody
  holds, and the *next* close — a fresh cycle an operator authorized by removing `rejected` — would be suppressed
  into having no durable half, which a restart before its worker reaches a barrier takes away entirely. The claim is
  handed back either way, by the write that recorded the memo or by the failure that recorded nothing; a claim left
  standing would suppress every later poll's receipt for good.
- **The receipt is read back once per owner per process.** After a restart the fresh process finds an issue a human
  reopened, a record still saying the cycle is live, and nothing in memory; the dispatcher's own cancelled-cycle
  guard therefore scans the thread for a receipt scoped to the cycle the record names, adopts it, marks the
  cancellation, and runs the ending from the mark. The scan is claimed through `observations.claim_receipt_scan`, so
  a thread carrying no receipt is walked on the first tick that sees the owner and never again — what it recovers is
  an observation a *dead* process was holding, and every observation this one makes is in the latch, which costs no
  request. The claim is held for the length of the walk and handed back where the walk established nothing — a
  listing that raises leaves `observations.scanning_receipt` by exception and the claim goes with it — because a
  claim standing over a read that established nothing would send every later tick straight past the receipt and on
  to the live stage handler. It is handed back again whenever a receipt actually LANDS: a claim taken when the thread
  carried nothing proved nothing about one posted since, and every later pass would read straight past it. Cycle
  scoping is what keeps an old close from ending the fresh cycle an operator authorized by removing `rejected`.
- **Every path that runs a cleanup holds its observation the same way.** The scheduler's fan-out submit, the in-tick
  parallel one, and the sequential stream all wrap the pass in `dispatch._cleanup_observation`, with the refetch
  *inside* the wrapper — that read is the first thing a cleanup spends and the likeliest to fail, and a pass that
  raised marked nothing. Without the wrapper the exception is merely logged and a reopen before the next tick resumes
  the uncancelled cycle.
- **A closed owner whose label names an ordinary terminal is still cancelled.** The cleanup route takes a closed
  owner on either label an adjudication runs under; what reaches the dispatcher's own guard closed is the one window
  no label covers — a `single` verdict hands its issue to `workflow:implementing` a moment before it retires the
  cycle. Nothing else would end that cycle: the terminal arc that label names drains a merged pull request or a
  human close and writes the late record off nowhere, and the relabel guard beside it merely puts `decomposing`
  back, which a reopen before the next tick takes away again. So the guard marks it from the reading it already has
  — the closed issue it was handed and the record it already read — and the ending runs from the mark.
  The dispatcher covers the same window on both sides of the submit. An **admitted** task carries the poll's closed
  reading with it (`_PollReading`) and applies it on the worker thread before the guard reads the refetched object —
  a human who reopens between the poll and the refetch would otherwise leave the fresh reading saying open with a
  live cycle under it — and it holds that reading across the pass, latching it again on the way out unless the pass
  actually spent it. Spending it is not the same as finishing: the pinned read the guard is built on answers a
  refusal of its own, so a tick that could not read the record refuses the issue and marks nothing. A **refused**
  submit latches the reading **first**, then drops it again only where the record positively says there is nothing
  to end. All three tick paths do this. The order is
  the whole of it — the probe is a request, and a request can fail or can land after the very retirement it was
  asking about, so a reading conditioned on it would be lost to either. A latch held over an issue with no cycle
  costs the next tick one cleanup pass that settles it; a reading dropped costs the close itself. It is taken on the
  refusal rather than ahead of admission, because an admitted submit runs the label's own handler and settles
  nothing.
- **A cancelled cycle is refused under every label, and the terminal lands where the graph allows.** Every workflow
  label names a handler that ACTS on the issue rather than settling it, so a cancelled cycle wearing any of them is
  refused whatever it says — a human who relabels such an owner is asking for work on a cycle a close already ended.
  Where `rejected` is *written* is the transition graph's answer for every label a workflow wrote: each state a late
  cycle can be interrupted on declares that edge, and `question` — applied by an operator who wants the issue discussed
  rather than ended — does not, so an owner there is refused and said out loud rather than relabelled out from under
  whoever put it there. `ready` and `blocked` are the exception, and they are not a human's placement: a decomposer
  spawned before the close writes one of them as its ordinary outcome and lands *after* the close, so an ending refused
  there is one refused on every visit the sweep makes, forever — neither label declares the edge, and the sweep is what
  brings a tick back. The terminal is therefore written from both, unguarded, as the repair of a move this workflow
  never made. The **unlabeled** state is the one exception in the other direction — an operator who removed `rejected`
  to authorize a restart leaves the issue wearing nothing, and re-applying a terminal there would undo that
  authorization, so an unlabeled owner is stopped only while its cycle still owes something.
- **A control label defers everything past the mark, and nothing before it.** `backlog` / `paused` park an issue
  outside the state machine, and the ending is external work — a plan pull request closed, a branch deleted, a ref
  reclaimed — so none of it runs while the label is on. The cancellation itself is still persisted, because the pass
  the park would drop is the only one that would ever record the close: an owner parked while closed would otherwise
  come back from a reopen and an unpause with a live generation. That reading also survives the partition filter, so
  a parked *closed* issue is bucketed rather than discarded.

  The waiver is exactly that wide, and it is re-applied behind the mark. A record with no late cycle marks nothing
  at all, and the cancelled-cycle guard answers "not mine" for one — so without a second ask a parked issue would
  reach the stage handler its label names, which is the one reaction an operator applied `paused` to prevent. The
  same is true after a reopen between the poll and the worker: the reading is still the poll's, the record still
  owes nothing, and the park is still the answer.
- **A held observation outranks every filter above the partition.** It is not a reading of the current tick's, so
  what that tick can see about the issue has already been overtaken. A `backlog` / `paused` park no longer drops it
  — the sweep it routes to defers every external step anyway, which is exactly what the park asks for, and never the
  mark. And an issue the enumeration does not yield at all, because a human moved its label off the four the closed
  sweep queries, is added by NUMBER on the strength of the observation alone; the worker's own refetch decides the
  rest. All three tick paths do this: the partition for the scheduler and parallel modes, and the sequential stream
  sweeps whatever its enumeration never reached.
- **Why it fans out rather than joining the family bucket**: that bucket's cap exemption is all-or-nothing, so one
  open `workflow:decomposing` issue sharing the tick would make a closed owner cap-counted — and under a saturated
  cap the whole bucket is skipped, which stops the repository reclaiming refs for as long as its decomposer is busy.
  Partitioned as fan-out, the owner carries its own `cap_exempt=True` submit, for the same reason every other closed
  issue does: nothing on this path spawns an agent or touches a worktree it did not already own.
- **What it does**: it ends the cycle, and nothing about the workflow the close ended. It never spawns, never
  adjudicates, never creates or activates a child, and never touches one that already exists. The ending is
  [`late_cancellation.py`](../../orchestrator/workflow/stages/decomposition/late_cancellation.py), and it runs in
  a fixed order.
  1. **The cancellation is persisted first**, ahead of every external call, and the `late_cancellation` record
     rides that write — so there is one per cycle rather than one per cadence, and every gate below reads a record
     that already says the cycle is over. It carries the moment the obligation was taken on and the boundary it
     interrupted (`late_cancelled_phase`), because `late_phase` is about to name the cancellation itself and the
     boundary is what the whole-ledger rule reads. Both are kept from the *first* observation: a reopen and a
     second close re-mark the same cancellation and move neither.
  2. **A held plan pull request is released, told once, and closed.** This is the one obligation a cancellation
     owns that no other pass ever sees — every path that reaches an umbrella superseded its plan PR on the way, so
     a cancelled cycle is the only shape where one is still open under a "do not merge" notice. The hold comes off
     first, so a pull request that ends up closed is not also left wearing one forever; a release that failed on a
     still-open pull request stops the close, since the preserved description is the only copy of what the hold
     replaced. The notice carries a cycle-scoped marker and is proved from the pull request's own thread, and the
     entry is recorded either way — `reconciled`, or `failed` with `pr_reconcile_failed` behind it. It is re-asked
     on **every** visit, including one whose entry already reads `reconciled`, for the reason the ordinary
     supersession is: that entry records what an earlier visit did, and a human can reopen the pull request behind
     it — an owner the sweep is still visiting for a branch it cannot delete would otherwise reach `rejected`, and
     leave the sweep for good, beside a change that is open again under a cancelled cycle. Re-asking costs one
     fetch and one comment listing and repeats nothing; the write and both sinks stay behind a state that actually
     moved, so a settled pull request adds no record per cadence.
  3. **The branch and the ref are `late_cleanup`'s, unchanged** — the same rules, the same `reclaiming` / release /
     `reconciled` order, the same records, and the same bound on them: what reaches the sinks and the pinned
     comment is a state that *moved*, so a remote that goes on refusing one delete costs a request per visit
     rather than a record and a write per visit, while the log goes on naming what is held. A cancellation buys no
     shortcut through any of it: a consumer that is live again keeps the ref whether or not its owner is closed.
     What it does change is which ledger the rule reads. The count written before the first create can only be
     reached by a loop that ran to the end of its manifest, and a cancelled one never will — so the loop that stops
     writes down that its register is **final**, which it may because every barrier that ends it is asked after the
     write recording the child in hand. The ref then goes once every child the split actually cut has ended. A
     **resumed** walk stopped before it reached the first unrecorded index seals nothing: a create is a request and
     the write recording it is another, so a child an earlier attempt made and never recorded would not be on the
     register, and there the ref stays held on the count.
  3b. **A branch a supersession left unrecorded is taken on here.** The transaction settles the held plan PR and
     records the branch that PR carried in two writes — the second is the retirement, and retiring ahead of a
     supersession that might not land would let the children loose beside a change still carrying their work. A
     close landing in that window leaves a cycle whose candidate is preserved on the ref, whose plan PR is closed,
     and whose branch nothing on the record names; settling around it would retire the owner over a branch the
     remote keeps for good. So a cancellation whose kept boundary is `superseding` resolves that branch and records
     it as owed — but off the **announcement's own receipt**, not off the phase. A park at the supersession is
     resumed from the top of the transaction, which rewrites `snapshotting` and `splitting` over the boundary while
     stepping over the announcement it already made, so a second failed attempt stands at `splitting` with the
     receipt still set and the phase no longer says what was reached. Not before that receipt, since the snapshot
     is created *and proved* ahead of the first child and the branch stops being the only copy there. Only where
     the record names no branch already, in any state. And only once the plan PR of step 2 is actually
     **settled** — the boundary is written before the supersession is attempted, so it says the attempt was reached
     and nothing about whether it landed, and inferring the branch while that pull request is still open would
     delete, out from under a change a human can still see, the branch that change is built on. Nothing is lost by
     waiting: the pull request is re-asked on every visit, and the visit that closes it takes the branch on.
  3c. **The held plan pull request is asked once more, immediately before the terminal.** Step 2 settled it at the
     top of the pass; what stands between that ask and the write below is a branch delete, a ref delete, and a
     fresh read of every recorded consumer — long enough for a human to reopen the change inside them, which leaves
     the record saying `reconciled` and the remote saying open. `rejected` takes the owner off both swept labels,
     so a terminal taken on the record would leave that pull request standing under a cancelled cycle with nothing
     coming back for it. The re-ask is the same idempotent one: a pull request still where the earlier ask left it
     costs a fetch and a comment listing and moves nothing, while one that is open again is closed again and one
     that will not close goes back to `failed` and holds the terminal for the next visit. It is taken only where
     nothing else is owed, since that is the only visit whose terminal is actually due — an owner still holding a
     branch the remote refuses is one the sweep is bringing back anyway, and the ask at the top of that pass is the
     same ask.
  4. **`rejected` last, and only once nothing is owed** — branch, ref, and *every* unreconciled plan-PR entry on
     the ledger, which is a wider reading than what the pass acts on: acting takes the hold's own record, since
     releasing one means knowing which pull request this cycle marked, while being owed takes the ledger, because
     an entry left under a number a later write cleared is still an obligation and a `rejected` owner is one
     nothing revisits. It is what a restart counts too, so retiring over one would refuse the fresh cycle that
     terminal is meant to authorize. A recorded plan-PR number with no preserved description beside it is owed as
     well, and is the one entry no pass can settle: the description that hold displaced is the only copy there
     was, so nothing may put it back or close over it, and the terminal is held until a human repairs the record.
     An opaque resource ledger blocks outright beside all of them.
  4b. **The child receipts are discharged in the same breath.** Each child is recorded `pending` when it is
     created, and nothing has ever moved one: the reclamation does not look at child entries, rightly, because a
     child is a live issue rather than an object to reclaim. But `rejected` authorizes a restart, and a restart
     projects its fresh cycle only over a ledger with nothing unreconciled on it — child entries included,
     correctly, since the projection drops the ledger and may not discharge an obligation by forgetting it. So the
     ending records what is already true: the children exist, this cycle is over, nothing further about them is
     owed. Not one of them is touched on GitHub.

     That label is the one write this path ever makes, and it is what takes the
     issue out of the sweep for good: every label the sweep queries is one it keeps until this write lands, so a
     terminal taken over an unreclaimed remote would leave that object with nothing coming back for it. A refusal
     keeps the label, keeps the issue swept,
     and says on every visit what is still holding it.
- **Consumer state is re-read, never latched**: this pass fetches every recorded consumer fresh, and a consumer
  reopened before the delete lands has a live claim again, so the ref stays. A consumer whose read *fails* also
  keeps its ref, while the branch half — which owes no consumer anything — is still settled on that same visit.
  The scan is taken only where a ref is actually held, so an owner with nothing but a branch left costs no
  per-consumer request.
- **An issue with no recorded generation is left entirely alone**, which is every umbrella the initial decomposer
  ever made: they wear one of the same two swept labels and own no cycle, so there is nothing to cancel and no
  terminal to rewrite.
- **A reopen does not resume the cycle, and does not skip its ending either.** Cancellation is irreversible within
  its cycle, so a human who reopens the issue does not get that cycle back — and every label the issue could be
  wearing names a handler that would act on it rather than settle it. The reopened owner is caught by the
  dispatcher's own pinned-state guard ([above](#the-reuse-guard-every-dispatch-ahead-of-every-handler) shares that
  read), which runs exactly the reconciliation above, reaches no handler, and writes the same `rejected` a closed
  owner earns. It runs the cleanup rather than merely refusing because this sweep visits *closed* issues only: a
  refusal with nothing behind it would freeze the issue until somebody closed it again. `rejected` is what the
  **cycle** earns rather than what a closed issue earns, and it is what an operator removes to authorize a restart,
  so reaching it is the only way back into ordinary work that does not silently resume a cycle a close already
  ended. The issue is left open; closing one a human just reopened is not this pass's to do.
- **The label decides where the ending is written, not whether it is refused.** A cancelled cycle is refused under
  every label, and the terminal is written from the ones the transition graph declares the edge from, plus `ready`
  and `blocked` — the two the cycle's own decomposer writes as its ordinary outcome, which no query would ever come
  back to. Under a label that is neither (`question`), the refusal stands on its own and the cycle stays cancelled
  where it is. The unlabeled state is the single exception, because an issue an operator has taken `rejected` off
  wears no label at all and re-applying it there would undo the one authorization a restart has — so unlabeled, the
  guard stops an issue only while its cancelled cycle still *owes* something (that obligation is real wherever the
  label went) and otherwise steps aside.
- **Output**: the cycle cancelled once, obligations settled or retried (with the same `late_cleanup` /
  `late_failure` records the terminal emits, bounded the same way), no consumer written to or commented on, the
  owner moved to `rejected` once nothing is owed, OR a no-op.

## `_handle_implementing` (label `workflow:implementing`)
- **Trigger**: each tick while the label is `workflow:implementing`.
- **Input**: issue + comments + pinned state.
- **Internal flow**:
  0. **External-merge / closed-issue short-circuit.** `_finalize_if_pr_merged` flips a merged PR to `done`
     (`merge_method="external"`); `_finalize_if_issue_closed` flips a closed issue to `rejected` and emits
     `pr_closed_without_merge` + cleans up the branch only when the linked PR is also closed (an open PR with a
     manually-closed issue is left alone for operator salvage). Both helpers defer without writing state when the PR
     fetch fails so a transient failure cannot mis-label a merged-PR issue. The merge terminal is reached only past
     the plan question, which two records answer. A live `discussion_plan_path` says the recorded PR is the
     `discussion` stage's plan whatever its head is now — the handoff below retires that record durably before anything
     spawns, so nothing here has pushed yet and a head that moved is the humans editing the design they are agreeing to
     (a corrected plan, a base merged into the branch), not work having landed. Past the handoff `discussion_plan_sha`
     answers, and it is the head that PR was on when the handoff took it — snapshotted there in the path record's
     place, so an amendment the humans made is not read as an implementation by the tick after. A recorded PR still on
     that commit is the plan, and one whose head has moved is this stage's
     own push. Neither may finalize as work having landed while it is still the plan. That read has three
     answers, not two — a PR that could not be fetched ends the tick where it happened, unfinalized and unspawned,
     because falling through would ask GitHub the same question a second time and a request that failed once and
     succeeded next would finalize the plan the first answer existed to protect.
  1. Awaiting-human resume: on a new human comment past `last_action_comment_id`, resume the dev session via
     `run_agent(dev_agent, ...)`. The full spec persisted in `dev_agent` is re-parsed via `_read_dev_session` and
     reused; flipping `DEV_AGENT` in env does not migrate in-flight issues. When parked on `agent_timeout` with **no**
     new comment, first attempt `_try_recover_implementing_timeout_park` (the implementing counterpart to validating's
     transient-park recovery): on a clean worktree whose HEAD advanced past the persisted `pre_implement_sha`, publish
     the recovered commit via `_on_commits` and clear the park; otherwise stay parked silently. This recovers a clean
     commit a descendant the timeout cleanup raced finishes *after* the park is recorded (the observed `#77` shape:
     commit timestamp landed after the timeout event) without needing a human "push it" comment. A real human comment
     takes precedence and drives the normal resume.
     - **`/orchestrator continue` operator command** (`_handle_parked_continue_command`, run BEFORE the drift check so
       the bare command is never mis-read as requirement drift). On a retryable session-failure park (`park_reason` in
       `_CONTINUE_PARK_REASONS` = `agent_silent` / `agent_timeout`) a content-free continue retries the dev
       intentionally (`_retry_parked_dev_session`): the command watermark is consumed, the session is resumed on a
       neutral retry prompt — NOT the bare command text, so the dev is grounded on its transcript (or, once
       `_resume_dev_with_text` rotates it, a fresh respawn preamble) rather than the nudge — and the result disposes
       through the normal commit / timeout / question paths, with no "issue body changed" notice. A park needing a real
       answer (any other `park_reason`) consumes the command and posts a refusal (`_refuse_parked_continue`) once, then
       stays parked (no per-tick loop). A comment carrying the command *alongside* genuine guidance falls through to the
       normal drift/resume path so the guidance drives the dev (`_continue_command_action` returns `passthrough`). The
       classifier + parser + refusal live in `workflow/engine/messages.py` and are shared with `_handle_fixing` and
       `_handle_documenting`; a bare continue is also dropped from `_compute_user_content_hash` (see above).
  2. Otherwise ensure a per-issue worktree at `<WORKTREES_DIR>/<owner>__<name>/issue-<n>` on branch
     `orchestrator/<owner>__<name>/issue-<n>` (the slug-namespaced branch keeps two RepoSpecs sharing a `target_root`
     from colliding on the same `orchestrator/issue-<n>` ref). Worktrees with unpushed commits are reused (crash
     recovery); otherwise force-removed and recreated from `<spec.remote_name>/<spec.base_branch>`.
  3. If the worktree already has commits (recovered), skip the agent and go straight to push — unless those commits
     are the ones a read-only relabel just certified (`read_only_baseline_sha` still equal to HEAD), which is a branch
     the issue arrived carrying rather than a run to finish, so the implementer spawns normally.
  4. Else gate the run on the per-issue retry budget (`MAX_RETRIES_PER_DAY`, default 3); a 24h window opens at the first
     counted spawn. Only fresh spawns count.
  5. Else build the implementer prompt (issue body + recent comments + "commit, do not push"), persist `dev_agent`
     BEFORE invoking `run_agent`, then spawn.
  6. Branch on result:
     - `interrupted` (shutdown sweep killed the run mid-flight) → ignore the partial result and return WITHOUT writing
       pinned state, so durable GitHub state stays exactly as the prior tick left it and the next process retries.
       Precedes every branch below and applies to both the awaiting-human and user-content-change resumes. Never posts a
       HITL question, consumes `awaiting_human`, or advances a watermark.
     - `paused` / `backlog` applied mid-run → same short-circuit as `interrupted`: return WITHOUT writing pinned
       state, so no PR opens, no relabel, no park, no watermark bump. `_paused_during_agent_run` re-reads a FRESHLY
       fetched issue (`gh.get_issue`) because the dispatch-time skip only saw the pre-run labels. Applies to the fresh
       spawn, the awaiting-human resume (including the pre-disposition `_resume_dev_with_text` poisoned-session retry),
       and the user-content-change resume. The committed work stays on the branch and republishes through step 3's
       recovered-worktree path once the label is removed.
     - `timed_out` → dispose on whether HEAD advanced past the pre-agent SHA snapshot: a clean advance publishes via
       `_on_commits` exactly as a normal completion (a clean commit produced just before/around the kill is **not**
       stranded behind `awaiting_human`); a dirty advance parks via `_on_dirty_worktree`; no advance parks
       (`agent_timeout`) with the durable `park_reason="agent_timeout"` re-set and `pre_implement_sha` persisted for
       step 1's next-tick recovery. The `pre_implement_sha` watermark (not `_has_new_commits`, which only compares to
       `<remote>/<base>`) is what tells a commit produced by THIS run apart from commits already carried on the branch.
       (`_on_commits` clears the spent watermark + stale reason on publish.) Pairs with the hardened
       `processes.terminate_process_group` (SIGKILLs surviving descendants after the leader exits) so a build grandchild
       cannot keep committing into the worktree after the timeout is recorded.
     - new commits + clean tree → `_on_commits`: push branch, open PR (or reuse an existing open one), comment
       `:sparkles: PR opened: #N`, then set label `workflow:validating` (the docs pass runs only as the final-docs
       handoff after approval). A reused PR is only known to be open on the branch — most sharply, an issue relabeled
       out of `discussion` arrives with its plan PR open on the very branch these commits went to — so one whose body
       does not already name this dev session has that body rewritten to the implementation's (`Resolves #N`, the dev
       session, the agent's closing message); one that does name it is left as it stands, human annotations included.
       Without the rewrite the PR would keep claiming the branch is one Markdown file that changes nothing else, under
       the decomposer's session, and would close no issue when it merged. Persists `pr_number` / `branch` and
       resets `review_round=0` and `retry_count=0` via `_reset_implementing_counters`.
     - new commits + dirty files → `_on_dirty_worktree`: park; refuse to publish a partial branch.
     - no new commits → `_on_question`: post the agent's last message as a HITL question, park.
- **Output**: pushed branch + open PR + label moved to `workflow:validating`, OR a HITL park.

## `_handle_documenting` (label `workflow:documenting`)
- **Trigger**: each tick while the label is `workflow:documenting`. Set only by the **final-docs handoff** in
  `_handle_validating`'s approval branch (after verify + squash); the docs pass runs exactly once per
  reviewer-approval handoff, between approval and `in_review`. A PR may visit `workflow:documenting` more than once:
  if PR feedback bounces the issue to `workflow:fixing` and the dev pushes a fix, the next approval triggers another
  final-docs pass. Also runs on closed-`workflow:documenting` issues so an externally-merged PR finalizes to `done`.
- **Input**: pinned `pr_number`, `branch`, `dev_agent` / `dev_session_id` (the docs pass reuses the locked dev spec —
  there is no separate `documenting_agent`), plus `docs_checked_sha` / `docs_verdict` / `silent_park_count`.
- **Internal flow**:
  0. **External-merge / closed-issue short-circuit** (identical to `_handle_implementing`).
  1. **`pr_number` missing → park** with `missing_pr_number`. Documenting only runs against an existing PR worktree.
  2. **`/orchestrator continue` refusal** (`_refuse_parked_continue_command`, run BEFORE the drift block). A bare
     continue on a park needing a real answer consumes the command and posts a refusal (`_refuse_parked_continue`) once,
     then stays parked. A retryable session-failure park (`agent_silent` / `agent_timeout`) and a command carrying
     genuine guidance both fall through: because a bare continue no longer shifts `user_content_hash`, the drift block
     below stays silent (no spurious `routing back to validating`) and the retry reruns the FULL docs pass through the
     awaiting-human resume (step 7). The parser + classifier are shared with `_handle_implementing` / `_handle_fixing`;
     documenting has no preserved feedback batch, so only the refusal needs interception here.
  3. **User-content drift → relabel back to `workflow:validating`** without spawning the docs agent. A title/body edit
     (or fresh human comment) during the final-docs hop invalidates the prior approval, so the reviewer must
     re-evaluate before any docs work can land. Housekeeping: post a `:pencil2: routing back to validating` notice,
     advance `last_action_comment_id`, refresh `user_content_hash`, clear park flags, reset `review_round=0`.
     Reconcile the PR worktree (fetch, then probe ahead/behind; on `ahead > 0`, `behind > 0`, or dirty files run `git
     reset --hard <remote>/<branch>` + `git clean -fd`) so no docs work authored against the pre-drift requirements
     survives. `docs_drift_unwind_pending` is set while the cleanup is in progress and cleared only on the relabel
     back to `workflow:validating`, so an operator unpark on a parked cleanup re-enters the drift block instead of
     falling through to a docs spawn.
  4. Awaiting-human + no new comment → early return BEFORE the fetch so a transient `fetch_failed` / `diverged_branch`
     doesn't re-post its park every tick.
  5. Ensure the PR worktree (`_ensure_pr_worktree`, restored from `<remote>/<branch>` so the dev's commits are intact)
     and refresh via `_authed_fetch`. Failure parks with `fetch_failed`.
  6. Ahead/behind check vs. the just-fetched `<remote>/<branch>`:
     - `behind > 0` → park with `diverged_branch` (force-pushing would clobber the real PR head).
     - `ahead > 0` recovered commits → synthesize an `AgentResult` and skip the agent; the unified branch below pushes
       the recovered docs commit.
     - `(0, 0)` → fall through.
  7. Awaiting-human resume: rebuild the FULL docs prompt via `_build_documentation_prompt` (this may be the first time
     the session sees the docs-stage instructions), persist `docs_checked_sha=before_sha` BEFORE the spawn, then
     `_resume_dev_with_text`.
  8. Fresh spawn: snapshot `before_sha`, persist `docs_checked_sha=before_sha` and `dev_agent` BEFORE invoking the
     agent, build the prompt (issue body + recent comments + `DOCS: NO_CHANGE` marker contract), then run.
  9. Branch on result. Every success exit routes to `in_review` via `_advance_after_docs_push` /
     `_advance_after_docs_no_change`, which ratchets `pr_last_comment_id` past any issue-thread reply the resume
     consumed so in_review does not bounce over already-addressed feedback. Branches:
     - `interrupted` (shutdown sweep killed the run mid-flight) → ignore the partial result and return WITHOUT writing
       pinned state (the pre-spawn `docs_checked_sha` / watermark writes are discarded), so the next process re-runs the
       docs pass. Precedes every branch below. The recovered `ahead > 0` path synthesizes a non-interrupted result, so
       it is unaffected.
     - `paused` / `backlog` applied mid-run → same short-circuit as `interrupted`: `_paused_during_agent_run` re-reads a
       FRESHLY fetched issue after the initial-docs and awaiting-human resumes, and on a hit the handler returns WITHOUT
       pushing, posting the docs notice, advancing to `in_review`, ratcheting watermarks, or writing pinned state. The
       committed docs work stays on the branch and republishes through the `ahead > 0` recovered path once the label is
       removed (the recovered path itself runs no agent, so it observes no live-pause window).
     - `timed_out` → park (`agent_timeout`).
     - dirty worktree → `_on_dirty_worktree`: park.
     - new commit on a clean tree → `_push_branch`. On success record `docs_checked_sha=after_sha`,
       `docs_verdict="updated"`, reset `silent_park_count=0`, post `:books: documenting pass: pushed docs commit.`,
       advance. A push failure parks (`push_failed`).
     - no commit + `DOCS: NO_CHANGE` verdict: when `ahead > 0` push the recovered commit and advance; otherwise persist
       `docs_verdict="no_change"`, post `:books: no docs changes required.`, advance without pushing.
     - no commit + unknown verdict → `_on_question`: park.
- **Output**: label moved to `in_review` (success), OR `workflow:validating` (drift unwind), OR terminal `done` /
  `rejected` (short-circuit), OR a HITL park.

The docs pass is deliberately a thin dev-session rerun on the existing PR worktree rather than a separate role: there is
no `documenting_agent` pin and no separate retry budget. The dev session resumes on its locked `(backend, args)` spec,
so `DEV_AGENT` flips made mid-flight do not retarget the docs pass either.

## `_handle_validating` (label `workflow:validating`)
- **Trigger**: each tick while label is `workflow:validating`. Set by `_handle_implementing` after `_on_commits` opens
  the PR, by `_handle_documenting`'s drift unwind, and by `_handle_fixing` / `_handle_in_review` /
  `_handle_resolving_conflict` on their pushed exits.
- **Input**: PR #, branch, `dev_agent` / `dev_session_id`, `review_round`.
- **Internal flow**:
  0. **External-merge / closed-issue short-circuit** (same chain as implementing / documenting). The reviewer is not
     spawned on either short-circuit.
  1. Awaiting-human path: resume on the dev's locked spec; on a successful pushed fix, bump `review_round` and stay on
     `workflow:validating`. A transient park (`_VALIDATING_TRANSIENT_PARK_REASONS`) with NO new comment goes to
     `_try_recover_validating_transient_park` instead, which retries silently and, on `cleared` / `pushed`, posts the
     **Recovery follow-up** described below before clearing the park. Exception: on a `review_cap` park the human
     reply does NOT wake the dev — the operator
     must post `/orchestrator add-review-rounds N` on its own line (honored only from an allowlisted author when
     `ALLOWED_ISSUE_AUTHORS` is set — an outsider's command is filtered out before the parse), which resets
     `review_round` to `max(0, MAX_REVIEW_ROUNDS - N)`, clears the park, and falls through to spawn the reviewer this
     same tick. Values at or above the configured maximum grant one full review budget rather than extending the
     budget past it. A second exception: a bare `/orchestrator continue` on a session-failure dev park (`agent_silent` /
     `agent_timeout`) is intercepted (`_continue_command_action`) and retries the dev on the neutral
     `_CONTINUE_RETRY_PROMPT` — NOT the literal command, which the dev has no context for — while
     `_handle_dev_fix_result` still publishes any stranded commit; a bare continue on a park needing a real answer
     refuses (`_refuse_parked_continue`) and stays parked. A command carrying real guidance, or a normal reply,
     resumes the dev on that text as before. (Shared with `implementing` / `documenting` / `resolving_conflict`; see
     the drift-detection section for the bare-continue hash exclusion.)
  2. If `review_round >= MAX_REVIEW_ROUNDS` (default 3), park (`review_cap`). The park comment surfaces the
     `/orchestrator add-review-rounds N` escape hatch.
  3. Otherwise persist `config.REVIEW_AGENT_SPEC` to `review_agent` (traceability only — the reviewer is spawned fresh
     each round with no resume), then run the reviewer with the read-only prompt (must end with `VERDICT: APPROVED` or
     `VERDICT: CHANGES_REQUESTED`). A mid-run `paused` / `backlog` re-check (`_paused_during_agent_run`) right after the
     reviewer returns short-circuits BEFORE the usage fold, session record, verdict parse, verify gate, squash, or
     relabel, so the next tick re-spawns a fresh reviewer from durable state.
  4. Parse the last `VERDICT:` marker (`_parse_review_verdict`):
     - **approved** → in order: (1) run the local verify gate (`_run_verify_commands(wt, config.VERIFY_COMMANDS,
       config.VERIFY_TIMEOUT)`); a non-ok result parks via `_park_verify_failure` with a typed `park_reason`
       (`verify_failed` / `verify_timeout` / `verify_dirty` / `verify_head_changed`) and the approval / squash /
       handoff do NOT fire (see
       [`configuration.md#local-verification-gate`](../configuration.md#local-verification-gate)); (2) post
       `:white_check_mark: codex review approved.`; (3) when `SQUASH_ON_APPROVAL` is on (default), call
       `_squash_and_force_push` (subject reuses the first commit when it carries a reusable `<prefix>:` form —
       Conventional **or** repo-local such as `event:`/`career:` — otherwise `<inferred-prefix>: <issue title>`, where
       the prefix is inferred from recent base-branch history via `_infer_subject_prefix` and falls back to
       `fix:`/`feat:` only when no repo-local prefix dominates; pushed with `--force-with-lease`). On squash /
       force-push failure, park awaiting human and stay on `workflow:validating` so the original commits remain for
       manual triage. (4) On success, if `squashed_count > 1` post `:package: squashed N commits to 1`, seed the
       in_review watermarks (inside the `gh.get_pr()` try so a snapshot failure leaves them untouched), then relabel
       to `workflow:documenting`.
     - **unknown** (no marker) → park.
     - **changes_requested** → post the feedback to the PR, then flip the label to `workflow:fixing` BEFORE spawning
       the dev so the active job is observably "fixing reviewer-requested changes". Resume the dev with the fix
       prompt; on a new commit + clean tree push, bump `review_round`, and flip back to `workflow:validating`. A
       no-commit run that finds a stranded unpushed fix on a clean HEAD (see `_handle_fixing` step 8) publishes it the
       same way. The dev spawn records `stage="fixing"` for analytics. On any park (timeout, no-commit, dirty,
       push-fail) the label STAYS `workflow:fixing` with `awaiting_human=True` and `_handle_fixing` owns the
       awaiting-human cycle thereafter. An `interrupted` dev resume is ignored: the handler returns WITHOUT writing
       the post-spawn state (no resume-budget charge, no watermark, no park), so the pre-spawn `workflow:fixing` flip
       stands and the next tick re-runs the cycle; any commit the killed run left is republished later via the
       stranded-fix tail, not this run.
  5. `paused` / `backlog` applied mid-run → each of the three dev resumes (the drift resume, the awaiting-human
     resume, and the CHANGES_REQUESTED fix resume) re-checks a FRESHLY fetched issue via `_paused_during_agent_run`.
     On a hit the handler returns WITHOUT running its result handler (`_post_user_content_change_result` /
     `_handle_dev_fix_result`), so no comment posts, no push, no `review_round` bump, no relabel, and no pinned-state
     write. The committed work stays on the branch; the CHANGES_REQUESTED path leaves the pre-spawn `workflow:fixing`
     flip standing and `_handle_fixing` owns the issue once the label is removed — its no-feedback exit (step 6 there)
     is what publishes the discarded run's commit, since the reviewer comment that started the round is filtered out
     of every later rescan.
- **Output**: label moved to `workflow:documenting` (approval after verify + squash) OR `workflow:fixing`
  (CHANGES_REQUESTED) OR no label change with `review_round` bumped (awaiting-human resume, drift, transient-park
  recovery push) OR a HITL park.

## `_handle_in_review` (label `in_review`)
- **Trigger**: each tick while label is `in_review`. Set by `_handle_documenting` on the final-docs hop. Also runs on
  closed-`in_review` issues for external-merge finalization.
- **Input**: pinned `pr_number`, `branch`, `dev_agent` / `dev_session_id`, and three watermarks (`pr_last_comment_id`,
  `pr_last_review_comment_id`, `pr_last_review_summary_id`) — one per id namespace GitHub uses for PR feedback. Mixing
  any two namespaces under one watermark would silently drop or replay one side.
- **Internal flow**:
  1. If `pr_number` is missing → park awaiting human.
  2. Read the PR via `gh.get_pr` and delegate the terminal arcs to the shared `_drain_review_pr_terminals` helper (also
     called by `_handle_fixing` and `_handle_resolving_conflict`). The orchestrator never merges from here, so any
     `merged` state observed was produced externally. Branch on `gh.pr_state(pr)`:
     - `merged` → stamp `merged_at`, set label `done`, write pinned state, emit `pr_merged`
       (`merge_method="external"`), close the issue, `_cleanup_terminal_branch`.
     - `closed` → stamp `closed_without_merge_at`, set label `rejected`, emit `pr_closed_without_merge`, close,
       cleanup.
     - `open` BUT the issue was closed manually → set label `rejected` WITHOUT branch cleanup so the operator can
       salvage the still-open PR.
     - `open` with an open issue → fall through.
  3. **Fresh PR feedback (including any human CI-fix request) → route to `workflow:fixing`.** Read four sources
     independently, one per id namespace: issue thread, PR conversation (shares IssueComment id space), inline review
     comments, PR review summaries (filtered to non-empty `CHANGES_REQUESTED` / `COMMENTED`). If any source is newer
     than its watermark, record `pending_fix_at` + per-namespace `pending_fix_*_max_id` bookmarks (and the full
     `pending_fix_*_ids` batch lists) and flip to `workflow:fixing`. The handler does NOT honor
     `IN_REVIEW_DEBOUNCE_SECONDS` here or spawn the dev — `fixing` owns debouncing, the dev resume, and the DIRECT
     bounce back to `workflow:validating`. Watermarks are NOT advanced on this route so `fixing` can re-discover the
     triggering comments.
  4. **User-content drift → relabel back to `workflow:validating`.** Reached when no fresh PR-side ID surfaced a
     comment but `_detect_user_content_change` still reports a hash change (a title/body edit, or an edit to an
     existing issue-thread comment whose id is already below the watermark). Capture unread PR-conversation comments
     past `pr_last_comment_id` BEFORE posting the notice (the shared id space could otherwise leap past one). Resume
     the locked dev session with `_build_user_content_change_prompt` (quoting issue body + recent comments + the
     captured PR-conversation comments). Both successful outcomes — pushed fix AND `ACK: <reason>` no-commit reply —
     reset `review_round=0` and bounce directly back to `workflow:validating`. A no-commit response without the `ACK:`
     marker parks via `_on_question`. An `interrupted` resume short-circuits via `_ignore_if_interrupted` BEFORE
     `_post_user_content_change_result` and the watermark bump, returning WITHOUT writing pinned state so the drift
     stays unconsumed for the next process to retry. A mid-run `paused` / `backlog` (`pause_guard=True`)
     short-circuits the same way, right after the interrupted check.
  5. **Manual-merge HITL path** (only reached with no fresh PR feedback AND no drift):
     - `pr_is_mergeable` is `None` → try next tick.
     - `False` → park with `unmergeable`; HITL ping mentioning every `HITL_HANDLE`, bump watermarks past the park
       comment.
     - `True` → check `gh.pr_has_changes_requested(pr, head_sha=head_sha)` (a standing human CHANGES_REQUESTED on the
       current head vetoes the ping). The ping requires either `docs_checked_sha == pr.head.sha` with `docs_verdict` set
       OR `gh.pr_is_approved(pr, head_sha=pr.head.sha)` (a human/bot APPROVED review on the current head). When the
       gate passes, post a one-shot `:bell:` ping de-duplicated by `ready_ping_sha`. The ping is NOT a
       park: `awaiting_human` stays false so subsequent ticks still react to new comments / an external merge.
       Unlike park branches, the ready ping does NOT call `_bump_in_review_watermarks` (the bump reads
       `gh.latest_comment_id(issue)`, which could
       include a concurrent human comment).
  6. Every park inside this handler bumps the watermarks past the orchestrator's own park comment, so the next tick does
     not see it as fresh PR feedback.
- **Output**: label moved to `done` / `rejected` (terminal), OR `workflow:fixing` (fresh PR feedback), OR
  `workflow:validating` (drift; pushed fix OR ACK no-commit; both reset `review_round=0`), OR a HITL park
  (unmergeable, missing pr_number, drift-resume failure), OR a HITL ping (no relabel), OR a no-op tick.

**Recovery follow-up.** Both callers of `_try_recover_validating_transient_park` — the `workflow:validating`
awaiting-human branch and the `workflow:fixing` parked branch — post one short issue comment on a `cleared` /
`pushed` outcome, before the pinned write that clears the park, so the HITL mention that filed the park is not the
thread's last word after the system has healed itself. The wording is chosen by
`_recovery_followup_comment(gh, issue, state, park_reason, outcome)` from the (reason, outcome) pair: the failed push
retried, the timed-out run's commit pushed, the timed-out run having left nothing to publish, or the reviewer being
re-spawned. It carries no @mention (closing the loop must not notify a second time), and it is skipped entirely when
pinned state carries no `last_action_comment_id` — no mention was ever posted, so there is nothing to retire — or
when the pair has no wording. A `stuck` outcome posts nothing at all, so a still-failing retry stays silent poll
after poll.

Exactly one lands per park episode, and the receipt for that is the thread rather than pinned state. The post and
the write that clears the park are two operations, so a process that dies between them leaves GitHub holding a
comment no local record names — any receipt written beside the clear would die with it. So every follow-up carries
`_RECOVERY_FOLLOWUP_MARKER` (`<!--orchestrator-recovery-followup-->`), and `_episode_already_announced` looks for it
among the comments past `last_action_comment_id` before wording a new one. That watermark is the park's own mention
id, which scopes the search to this episode: a later park stamps a higher one, so an older follow-up sitting below it
cannot silence the next recovery. A forged marker costs its author the notification they would have been spared
anyway.

The late size gate's `late_owner_unreadable` park heals the same way and by the same rules, from its own owner
(`late_owner.py`) and under its own marker (`<!--orchestrator-late-owner-recovery-->`), so a follow-up from one
mode's episode cannot silence the other's. Two things differ. Its retry hangs off a durable
`late_owner_check_pending` on the generation rather than off the park, since the routes it has to survive skip the
park entirely; and its follow-up is posted *before* the write that clears the park rather than after, so the crash
window loses the write instead of the sentence — which the thread-marker check then makes free to repeat. A park
whose own notice GitHub refused (`late_park_notice` still owed) heals silently: it told nobody anything, so there is
no alarming last word to retire and a follow-up would be the first thing the episode said. What that park is and why
its retry re-reads rather than re-running anything is in
[`../workflow/roles.md`](../workflow/roles.md#the-owner-read-a-finished-run-has-to-pass).

The same failure window is why `_AwaitingValidation.build` drops the orchestrator's own comments — by recorded id
AND by `_ORCH_COMMENT_MARKER`, the pair `_rescan_fixing_feedback` already uses. Every awaiting-human decision helper
reads a non-empty batch as "a human replied", and a follow-up whose id-recording write never landed is still ours;
the marker is what says so when the id ledger cannot.

`_park_awaiting_human` posts on the issue (not the PR) so the HITL ping appears alongside the rest of orchestrator
state. The PR comment that triggers a route to `workflow:fixing` is the human signal; awaiting-human is reserved for
*unrecoverable* states (unmergeable / missing pr_number).

## `_handle_fixing` (label `workflow:fixing`)
- **Trigger**: each tick while label is `workflow:fixing`. Two routes set this label:
  - `_handle_in_review` when fresh PR feedback (any of the four surfaces, including a human CI-fix request) arrives —
    records `pending_fix_at` + per-namespace `pending_fix_*_max_id` bookmarks and the full `pending_fix_*_ids` batch
    lists.
  - `_handle_validating` on a `CHANGES_REQUESTED` verdict, flipped BEFORE the dev spawn. This route does NOT set
    `pending_fix_at`; it records `pending_fix_reviewer_comment_id` (the id of the reviewer-feedback PR comment) as its
    lone replay anchor. The dev runs inline and on a pushed fix validating flips the label back itself (clearing the
    anchor). Only the parked outcomes leave the fixing handler to own the awaiting-human cycle.

  Also runs on closed-`workflow:fixing` issues so an externally-merged PR finalizes to `done`.
- **Input**: pinned `pr_number`, `branch`, `dev_agent` / `dev_session_id`, `pending_fix_at` + per-namespace bookmarks
  (in_review route only), the three in_review watermarks (left behind so the rescan can re-discover the triggering
  feedback), `IN_REVIEW_DEBOUNCE_SECONDS`.
- **Internal flow**:
  1. PR-state terminals mirror `_handle_in_review` (shared `_drain_review_pr_terminals`). `_handle_fixing` catches its
     own `gh.get_pr` exceptions and hands `pr=None` to the helper, which is a no-op.
  2. Closed issue with no resolvable PR → no-op.
  3. Open issue with no `pr_number` (manual relabel) → park (`missing_pr_number`).
  4. Rescan unread feedback from the three watermarks across all four surfaces. Orchestrator comments are filtered by
     recorded id AND the hidden `<!--orchestrator-comment-->` body marker.
  5. If `awaiting_human`, first handle the **`/orchestrator continue` operator command** (`_handle_continue_command`).
     It is matched as an EXACT LINE (`^\s*/orchestrator continue\s*$`), so a comment carrying the command line AND real
     guidance still counts as the command; the command is handled on BOTH routes so a session-limit / session-failure
     park (`agent_silent` / `agent_timeout`) is never resumed on the bare command text. A recognized Claude
     session/usage-limit notice returned as the dev's final message (`_is_session_limit_message`) is itself parked
     `agent_silent` by `_on_question`, a retryable session failure rather than a real `park_reason=None` question, so a
     quota reset is retried here rather than refused as needing human guidance. The helper returns one of three
     actions: **replay** — an eligible session-failure park **with a reconstructable batch** (the in_review route's
     `pending_fix_*` bookmarks, or the validating route's `pending_fix_reviewer_comment_id` anchor): drop the poisoned
     dev session (`_drop_poisoned_dev_session` — so the retry re-grounds a fresh session on the committed branch), clear
     the park, and **replay the preserved feedback batch** (`_reconstruct_pending_fix_batch`) carrying ALL fresh
     feedback (the command comment and any guidance posted with or beside it) verbatim so nothing is dropped — resuming
     the fresh dev on it, skipping the debounce; **refuse** — a content-free continue (every fresh comment is a bare
     command) on a park it cannot retry (an unsafe park needing real human guidance, both `park_reason=None`; or an
     eligible reason with **no reconstructable batch**, e.g. a validating-route park whose reviewer anchor was never
     recorded or has since been deleted): the command comment is consumed (watermark advanced past it so the refusal
     does not re-fire) and a note is posted, and the issue stays parked; **passthrough** — the command arrived alongside
     genuine guidance on a park with no replayable batch, so it falls through to the normal resume below and that
     guidance drives the dev.

     Otherwise, when the rescan finds nothing new, branch on `park_reason` AND the route discriminator `pending_fix_at`:
     - **Transient reason** (`push_failed` / `agent_timeout` / `reviewer_timeout` / `reviewer_failed` — the
       `_VALIDATING_TRANSIENT_PARK_REASONS` set) **and `pending_fix_at` unset (validating route)** → call
       `_try_recover_validating_transient_park`. On `cleared` or `pushed`, post the recovery follow-up (see the
       **Recovery follow-up** note above), clear park, clear `pending_fix_*`, flip back to `workflow:validating`
       (the helper bumps `review_round` on `pushed`). This closes the loop for `_handle_validating`'s
       CHANGES_REQUESTED route. On `stuck`, fall through to the worktree-drift check below.
     - **Any other awaiting-human shape** (transient reason on the in_review route, non-transient reason like a real
       agent question, dirty-worktree park, or silent-crash park) → return silently and keep waiting for a human
       reply. We cannot distinguish "agent has a real question" from "agent reported nothing to change" by inspection
       (both surface through `_on_question` with `park_reason=None`), so auto-routing either would silently bypass the
       HITL contract.

     **Worktree-drift dead-lock breaker** (`_reconcile_parked_fixing`). Reached only from the
     stuck-validating-route-transient branch above: the self-recovery could not clear the condition, and the
     underlying cause may be a base advance that landed mid-park (the per-tick base sync deliberately stands down on
     every `awaiting_human` park — `_sync_pr_worktree_to_base` returns at its `awaiting_human` gate — so nobody else
     will sync this worktree). On a clean worktree the breaker routes to `workflow:resolving_conflict` — seeding
     `conflict_round` when absent, clearing the park, posting a PR notice, emitting `conflict_round`
     `action="entered"` (`stage="fixing"`) — in either of two shapes, both reconciled by the conflict handler, which
     owns rebasing AND publishing a PR branch:
       - **behind `<remote>/<base>`** (a local `rev-list HEAD..<remote>/<base>`) → needs a rebase;
       - **already on base but local HEAD ≠ the live `pr.head.sha`** (a rebase a prior run ran but never pushed) →
         needs a force-publish (see `_handle_resolving_conflict` below).

     The routing decision is cheap — no extra fetch, since `pr` was already fetched this tick. With no drift (the
     worktree is in sync with the PR head), or a dirty worktree, the park is left intact and the issue keeps
     awaiting a human. An operator who wants to freeze this reconciliation applies `paused`, which hard-skips the
     issue at dispatch so the breaker never runs. The `pending_fix_*` bookmarks and in_review watermarks are left
     untouched so the eventual in_review re-entry still re-discovers the feedback.
  6. If no unread feedback at all (watermarks already cover the bookmarks), publish any **stranded fix** first —
     `_stranded_fix_unpushed` against the worktree the issue already has on disk, i.e. a commit an earlier run left
     unpushed (a dev run whose outcome the live-pause guard discarded, a run killed before its push) — and on a
     successful push adjust `review_round` per the same route discriminator the pushed-fix exit uses (`pending_fix_at`
     read BEFORE the clear: in_review route resets to 0, validating route bumps by 1). Then clear `pending_fix_*` and
     bounce back to `workflow:validating`. A worktree that is not on disk, a probe refusal (dirty tree, failed fetch,
     a remote that moved), or a failed push bounces without pushing and without touching the round — the commit stays
     on the branch for a later push to carry. This exit is the validating route's LAST chance at that commit: the
     reviewer feedback that started the round is orchestrator-authored, so the step-3 rescan filters it out and no
     later tick re-runs the dev on it.
  7. **Quiet window**: compute the newest `created_at` (or `submitted_at` for review summaries); if younger than
     `IN_REVIEW_DEBOUNCE_SECONDS`, return.
  8. **Resume**: build a `_build_pr_comment_followup` prompt over ALL unread surfaces, resume the locked dev via
     `_resume_dev_with_text` (`pause_guard=True`), refresh `user_content_hash` (so any issue-thread comment we just fed
     to the dev doesn't re-fire validating's drift check). An `interrupted` resume is ignored entirely BEFORE the ACK
     fast path, the stranded-fix check, and the watermark advance below: the handler returns WITHOUT writing pinned
     state, so no watermark advances, `awaiting_human` is untouched, and the next tick re-discovers the same feedback. A
     mid-run `paused` / `backlog` short-circuits the same way, right after the interrupted check. Otherwise, a
     no-commit reply first checks for a **stranded fix** (`_stranded_fix_unpushed`): when the worktree is clean and HEAD
     is strictly ahead of the fetched remote PR branch (a fix committed by an earlier parked run whose publish was
     blocked — e.g. a dirty-park whose stray files were cleaned up afterwards), the handler publishes it through the
     normal push tail and treats the run as a pushed fix — this outranks the ACK fast path on both routes, so an acked
     stranded fix is published rather than relabeled. **ACK fast path** (in_review route only, no stranded fix): if the
     dev makes no commit but ends its message with the `ACK: <reason>` marker (the prompt instructs it to emit this when
     the comments name no actionable change — a vague "continue" / "ok"), clear `pending_fix_*`, post the ack as an
     FYI, and relabel straight to **`in_review`** without parking. Otherwise apply the same `_handle_dev_fix_result`
     disposition as the validating fix-loop. Any other unmarked no-commit reply falls through to `_on_question` and
     parks awaiting human — a no-ACK reply may be a real dev question, and we cannot tell by inspection (a dirty tree,
     failed fetch, or a remote that moved past the local view also falls back to this park rather than pushing blind).
  9. **Watermark advance**: regardless of dev outcome, `_advance_consumed_watermarks` advances each of the three
     watermarks ONLY to the max id consumed on that surface — tighter than a broad bump so a concurrent human comment
     that landed mid-handler survives to the next tick.
  10. **On a pushed fix**: clear `pending_fix_*`, adjust `review_round` per the route discriminator (in_review route
      resets to 0 — the previous approval was for the prior head; validating route bumps by 1 — same review cycle),
      flip DIRECTLY back to `workflow:validating`. Docs do not run on this exit.
- **Output**: terminal `done` / `rejected`, OR label flipped to `workflow:validating` (pushed fix OR no-new-feedback
  bounce), OR label flipped to `workflow:resolving_conflict` (stuck validating-route transient park while the worktree
  is out of sync with the PR — behind base or an unpushed local rebase), OR label flipped to `in_review` (in_review
  route, ACK fast path on this tick only), OR a HITL park, OR a no-op (quiet-window wait, missing-PR park already
  set).

## `_handle_resolving_conflict` (label `workflow:resolving_conflict`)
- **Trigger**: each tick while label is `workflow:resolving_conflict` (set by an operator relabel, by
  `_refresh_base_and_worktrees` when the auto rebase actually left conflicted files — a merely-behind-base PR rebase +
  push lands directly on `workflow:validating` — or by `_handle_fixing`'s worktree-drift dead-lock breaker when a
  validating-route transient `workflow:fixing` park whose self-recovery returned `"stuck"` is found out of sync with
  the PR head). Also runs on closed-`workflow:resolving_conflict` issues for terminal handling.
- **Input**: pinned `pr_number`, `branch`, `dev_agent` / `dev_session_id`, `conflict_round`. `MAX_CONFLICT_ROUNDS` from
  config.
- **Internal flow**:
  1. If `pr_number` is missing → park.
  2. Read the PR and hand it to the shared `_drain_review_pr_terminals` helper. `resolving_conflict` rebases the PR
     branch onto `<remote>/<base>` — it never merges, so any `merged` state was produced externally. Branch on
     `pr_state`: `merged` → `done` + close + cleanup; `closed` → `rejected` + close + cleanup; `open` → fall
     through.
  3. If the issue itself was closed manually while the PR is still open, flip to `rejected` without branch cleanup
     (operator may salvage). The closed-issue sweep does not surface `rejected`, so the operator must clean up the
     worktree / branch by hand if the PR later closes.
  4. **Awaiting-human resume**: when parked from a previous round and a new human comment arrived, resume the dev
     session on the in-progress rebase worktree with the human's text. The post-agent step uses the same
     `_post_conflict_resolution_result` helper as the fresh path. A bare `/orchestrator continue` here is intercepted
     like `validating`'s: a session-failure park (`agent_silent` / `agent_timeout`) retries the dev on the neutral
     `_CONTINUE_RETRY_PROMPT` instead of the literal command, a park needing a real answer refuses, and an auto-rebase
     park is left to the refresh retry-unpark (`_continue_command_action` / `_refuse_parked_continue`).
  5. **Cap check**: if `conflict_round >= MAX_CONFLICT_ROUNDS`, park. Escape: (a) operator relabels off
     `workflow:resolving_conflict`, or (b) a new issue comment unparks via the resume branch.
  6. Ensure the PR worktree via `_ensure_pr_worktree` (restores from `<remote>/<branch>` when THIS tick's fetch of it
     landed, NOT base — `_ensure_worktree` would discard the PR's commits — and never from a remote-tracking ref a
     failed fetch left behind, which resolves perfectly well while naming whatever was last seen; and from
     `<remote>/<base>` only when the remote itself says the branch is gone, which is a merged PR whose branch GitHub
     deleted seen from a host without the local ref: naming a ref nobody has would fail the `worktree add` on this
     tick and every one after it, and what
     that branch carried is in the base by then).
  7. Refresh `<remote>/<branch>` over `_authed_fetch` so a stale local ref doesn't mis-classify a "remote moved"
     situation as in-sync.
  8. Compare HEAD to the freshly-fetched `<remote>/<branch>`:
     - `behind > 0` (worktree diverged) → normally park (`diverged_branch`) since force-pushing could clobber the real
       PR head. **Exception — already-rebased-but-unpushed:** when the worktree is also `ahead > 0` AND already sits
       on top of base (`_already_rebased_onto_base` re-fetches base and checks `HEAD..<remote>/<base>` is empty) AND the
       stale remote head is one the orchestrator itself produced (`_pr_head_orchestrator_produced`:
       `pr.head.sha == docs_checked_sha` — the only key production code persists for an orchestrator-pushed head,
       written by `_handle_documenting`'s success exits), the "behind" commits are the orchestrator's own superseded
       pre-rebase commits — there is nothing external to lose, so fall through to the `ahead > 0` push and
       force-publish instead of parking. PR heads from earlier in the lifecycle (the initial implementing push, an
       intermediate fixing push) are not currently recorded anywhere in pinned state, so the exception declines those by
       design. If either guard fails (not on base, or an unrecognized head that might carry a direct push), keep the
       `diverged_branch` park.
     - `ahead > 0` (recovered unpushed commits, or the already-rebased fall-through above) → dirty-tree check, then
       push the recovered work (force-with-lease against the live remote head) and flip to `workflow:validating` with
       `review_round=0`, `conflict_round += 1`.
     - `(0, 0)` → fall through.
  9. Refresh `<remote>/<base>` and run `git rebase <remote>/<base>` under `_git_hardened` (drops global / system config,
     disables hooks / fsmonitor / credential helpers / commit signing / autostash — the agent owns the worktree and
     could otherwise plant a hook to execute attacker code mid-rebase).
  10. **Clean rebase succeeded**: dirty-tree check first. If HEAD did not move (already up-to-date), skip the push and
      flip to `workflow:validating` (`review_round=0`, `conflict_round += 1`). Counting no-ops against the cap
      surfaces a perpetually-unmergeable-due-to-branch-protection PR within `MAX_CONFLICT_ROUNDS` ticks. If HEAD
      moved, force-with-lease push and flip to `workflow:validating`.
  11. **Conflicted rebase**: build a conflict-resolution prompt via `_build_conflict_resolution_prompt`, resume the dev
      with it (`pause_guard=True`), then run `_post_conflict_resolution_result`.
  12. `_post_conflict_resolution_result`: `interrupted` (shutdown sweep killed the run mid-flight) → ignore the
      partial result and return WITHOUT writing pinned state, leaving durable state retryable (this is the one branch
      that does not write; it precedes all others); timeout / unfinished rebase / no commit / dirty / push fail →
      park; success → force-with-lease push, increment `conflict_round`, reset `review_round=0`, flip to
      `workflow:validating`. Fresh-rebase pushes pin the lease to the pre-rebase PR head; awaiting-human resume pushes
      use `_push_branch`'s live `ls-remote` lease fallback because `before_sha` may be an intermediate SHA. On BOTH
      resume paths (fresh conflict and awaiting-human), a mid-run `paused` / `backlog` returns in the handler BEFORE
      `_post_conflict_resolution_result` runs, so the resolved commit stays on the branch and no push / relabel /
      write happens until the label is removed.
- **Output**: label moved to `workflow:validating` (any pushed resolution OR no-op rebase), OR no label change (drift
  ACK / `_on_question` park: rebase still unfinished), OR `done` / `rejected` (terminal), OR a HITL park.

The rebase path deliberately rewrites the PR branch to keep history linear after other issue PRs land. Every pushed
rebase resets `review_round`, so the reviewer must re-approve the rewritten head before the in_review ready-ping gate
can fire.
