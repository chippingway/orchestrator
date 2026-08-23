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
  retained ahead of the first child. A cancelled or restarted cycle, or a phase this binary cannot type, proves
  nothing and keeps the ref.
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

## Closed-owner cleanup sweep (no label of its own)
- **Trigger**: an issue that is **closed** while still carrying `workflow:decomposing` or `workflow:umbrella`. The
  closed-issue sweep yields those two states beside its own recovery labels, on the same
  `CLOSED_ISSUE_SWEEP_EVERY_N_TICKS` cadence and through the same label cache and absent-label throttle, so it costs
  no request on a tick that sweep is skipping anyway (see
  [labels-and-state.md](labels-and-state.md#pollable-issues-and-finalization)).
- **Why it is not the label's handler**: both labels name a stage handler that would resume the workflow the close
  ended — one spawns the decomposer, the other walks the dependency graph and activates children. The dispatcher
  therefore reads *closed* before it reads the label and routes to `late_sweep._handle_closed_owner_cleanup`
  instead, ahead of even the live-adjudication relabel guard. That classification then **binds**: the submit carries
  a `cleanup_only` route the worker cannot re-derive, so a human who reopens the issue between the poll and the
  refetch cannot turn a cap-exempt submit into an agent-spawning stage handler. The handler re-reads the close
  itself and does nothing at all when the issue is open again, leaving the next tick to classify it correctly.
- **Why it fans out rather than joining the family bucket**: that bucket's cap exemption is all-or-nothing, so one
  open `workflow:decomposing` issue sharing the tick would make a closed owner cap-counted — and under a saturated
  cap the whole bucket is skipped, which stops the repository reclaiming refs for as long as its decomposer is busy.
  Partitioned as fan-out, the owner carries its own `cap_exempt=True` submit, for the same reason every other closed
  issue does: nothing on this path spawns an agent or touches a worktree it did not already own.
- **What it does**: exactly what the umbrella's terminal does to the obligation ledger — the same rules, the same
  `reclaiming` / release / `reconciled` order, the same records — and nothing else. It never writes a label, never
  activates a child, never spawns, and never decides a terminal. An owner whose every obligation is `reconciled`
  costs the pinned read and stops there, reading no consumer at all; an opaque ledger stops the pass with a warning,
  because nothing on it may be reclaimed around an entry this binary cannot type.
- **Consumer state is re-read, never latched**: this pass fetches every recorded consumer fresh, and a consumer
  reopened before the delete lands has a live claim again, so the ref stays. A consumer whose read *fails* also
  keeps its ref, while the branch half — which owes no consumer anything — is still settled on that same visit.
- **Output**: obligations settled or retried (with the same `late_cleanup` / `late_failure` records the terminal
  emits), consumers released where a ref went, OR a no-op.

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
