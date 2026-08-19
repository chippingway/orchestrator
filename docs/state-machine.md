# Workflow state machine

This area documents the label-based state machine that drives every GitHub issue from pickup to terminal. It is split
out of [`architecture.md`](architecture.md), which keeps the high-level overview, module map, and process / agent /
push / event-log details. Workflow labels and pinned-state JSON keys are a compatibility contract — live issues
already carry them — so this area is where label spelling, the transitions between them, and each handler's behavior
are authoritative.

## The pages in this area

- [`state-machine/labels-and-state.md`](state-machine/labels-and-state.md) — the label set and the control labels, the
  typed states and the transition guard, the migration off the pre-namespace spellings, what one tick reads and writes
  per issue, and every pinned-state key a handler depends on.
- [`state-machine/delivery-stages.md`](state-machine/delivery-stages.md) — pickup, the user-content drift hook,
  decomposition and the family walks, and the dev / reviewer / docs loop through `in_review`, `workflow:fixing`, and
  `workflow:resolving_conflict`.
- [`state-machine/conversation-stages.md`](state-machine/conversation-stages.md) — the two operator-applied
  conversation stages, `question` and `discussion`, including the plan PR a confirmed design earns.
- [`state-machine/lifecycle.md`](state-machine/lifecycle.md) — the compact label-lifecycle reference diagram.

Every section below keeps its heading here as a summary of what moved, so a link written against this page still lands
on the answer.

For the multi-repo dispatch, module map, and push model, see [`architecture.md`](architecture.md). For agent roles,
prompt contracts, and command specs, see [`workflow.md`](workflow.md). For env vars and the operator runbooks beside
them, see [`configuration.md`](configuration.md). For the audit event log, analytics sink, and usage parser, see
[`observability.md`](observability.md). For the security checklist, see [`security.md`](security.md).

## Workflow labels

An issue carries at most one workflow label at a time, and the orchestrator only ever swaps labels from its own set —
`bug`, `enhancement`, and a repository's own triage labels are preserved. `workflow:<tag>` is the **wire label**: the
literal string on the GitHub issue that a label write puts there, the transition guard checks, and the per-tick
dispatcher partitions on. A bare `<tag>` is the **stage**: the handler, the subpackage under
`orchestrator/workflow/stages/` holding it, and the identifier analytics rows, audit event payloads, and agent-session
attribution carry. `in_review`, `question`, `discussion`, `done`, and `rejected` were never namespaced, so those read
the same either way.

The states, in lifecycle order: no label, `workflow:decomposing`, `workflow:ready`, `workflow:blocked`,
`workflow:umbrella`, `workflow:implementing`, `workflow:documenting`, `workflow:validating`, `in_review`,
`workflow:fixing`, `workflow:resolving_conflict`, the operator-applied `question` and `discussion`, and the `done` /
`rejected` terminals. Three non-workflow **control labels** modify behavior without occupying the workflow slot:
`backlog` (a "not yet" hard skip on a fresh issue), `paused` (the same hard skip on an in-flight one, honored again
right after every agent run returns), and `workflow:community_contribution` (applied by the per-tick open-PR sweep,
never by an operator). What each state means, what a `paused` mid-run withholds, and why the prefix is a collision
guard rather than the membership test are in
[`state-machine/labels-and-state.md#workflow-labels`](state-machine/labels-and-state.md#workflow-labels).

### Typed states and the transition guard

`WorkflowLabel` and `ControlLabel` in [`orchestrator/workflow/state.py`](../orchestrator/workflow/state.py) define
both vocabularies once; because `StrEnum` members *are* their wire strings, a member is the GitHub label verbatim.
Two guards run at `GitHubClient.set_workflow_label`, the single label-write chokepoint: an always-strict **typo
guard** that raises on a name outside `WorkflowLabel`, and the **transition guard**
(`WORKFLOW_TRANSITION_GUARD` = `off` / `warn` / `enforce`, default `warn`) checking `current → new` against
`ALLOWED_TRANSITIONS`. Operator relabels through the GitHub UI bypass both, so the guard never fights a human. The
edge set, the `orchestrator.state_machine` logger a rejection is filtered by, and how `create_child_issue` shares the
typo guard for its direct write are in [`state-machine/labels-and-state.md`][typed-states].

### Legacy labels and the migration off them

A repository whose labels predate the namespace is migrated by the startup label bootstrap: a pre-namespace spelling
that exists alone is **renamed in place**, so every issue holding it moves across in one edit; a namespaced label that
already exists is left alone, as is any bare label beside it; neither present means the namespaced one is created
fresh. Wherever that rename could not run, three reads still take either spelling — issue routing, the community
sweep's dedup marker, and the closed-issue sweep's query — and a namespaced label always outranks a bare one on the
same issue. What a PAT without `Issues: Read and write` leaves behind, and which bare tags a relabel deliberately does
not delete, are in [`state-machine/labels-and-state.md`][legacy-labels].

## Per-tick flow (`workflow.tick`)

One repo's pass runs the base refresh, the community-contribution PR sweep, and the repo skill-catalog emission, then
dispatches each pollable issue by workflow label. **Family-aware labels** (`workflow:decomposing`,
`workflow:blocked`, `workflow:umbrella`, unlabeled pickup) read and write cross-issue parent ↔ child state, so they
fold into one bucket per repo that drains sequentially; every other label fans out concurrently up to
`MAX_PARALLEL_ISSUES_GLOBAL` / `MAX_PARALLEL_ISSUES_PER_REPO`. Only issue numbers cross the thread boundary — each
worker mints its own `GitHubClient` and re-fetches the issue. The cap exemptions, the `duplicate_active` gate, and
what each step reads and writes are in [`state-machine/labels-and-state.md`][per-tick]; the multi-repo dispatch and
scheduler lifecycle around them are in
[`architecture.md#per-tick-flow-workflowtick`](architecture.md#per-tick-flow-workflowtick).

### Base refresh

Before any issue is dispatched the tick fetches `<remote>/<base>` once and rebases each existing per-issue worktree
onto it, so a long-lived worktree does not stay anchored to whatever base looked like when it was added. A pre-PR
worktree rebases locally; a PR-having one in `workflow:validating` / `workflow:documenting` / `in_review` /
`workflow:fixing` pushes the clean rebase with a pinned `--force-with-lease`, resets `review_round`, and relabels to
`workflow:validating`, reaching `workflow:resolving_conflict` only when the rebase actually leaves conflicted files.
The `question` and `discussion` labels — and the parks and in-flight discussion records that outlive them — skip both
paths. The failure modes, their durable `park_reason` tokens, and the refresh-owned retry are in
[`state-machine/labels-and-state.md#base-refresh`](state-machine/labels-and-state.md#base-refresh).

### Pollable issues and finalization

`gh.list_pollable_issues()` yields every open non-PR issue plus the closed ones still carrying one of the eight sweep
labels, each queried under its pre-namespace spelling too, so an external merge or an operator close finalizes
cleanly instead of stranding the issue. `CLOSED_ISSUE_SWEEP_EVERY_N_TICKS` batches that sweep to once every N ticks,
which is the knob for the GitHub primary-rate-limit cost it carries on a multi-repo host. Which labels are swept, why
the pre-PR labels are not, and how a closed `discussion` is held for its plan PR are in
[`state-machine/labels-and-state.md`][pollable].

### Pinned state

Per-issue durable state is a single **pinned comment** on the issue (`<!--orchestrator-state {...json...}-->`),
trusted as state only when the orchestrator's own account authored it and its whole body is the marker. Its keys group
into agent identity, decomposition, PR / branch, the drift baseline, the HITL park, the in-review watermarks, the
final-docs handoff, fix routing, the crash-recovery anchors, counters and timestamps, and the per-issue usage meter.
Every key, what writes it, what spends it, and the legacy `codex_session_id` still honored on read are in
[`state-machine/labels-and-state.md#pinned-state`](state-machine/labels-and-state.md#pinned-state).

## Stage handlers

Each workflow label dispatches to one `_handle_<label>` function under `orchestrator/workflow/stages/`. The delivery
stages — pickup through the PR loop — are in
[`state-machine/delivery-stages.md`](state-machine/delivery-stages.md); the two operator-applied conversation stages
are in [`state-machine/conversation-stages.md`](state-machine/conversation-stages.md). Which module owns each handler
is in [`architecture.md#stage-handlers`](architecture.md#stage-handlers); what the agent each one spawns is allowed to
do is in [`workflow.md`](workflow.md).

### `_handle_pickup` (no label → `workflow:decomposing` or `workflow:implementing`)

An open issue with no workflow label: when `ALLOWED_ISSUE_AUTHORS` is set an issue from outside the list is silently
skipped; otherwise the handler posts the pickup comment, anchors `pickup_comment_id`, snapshots `user_content_hash`,
and routes to `workflow:decomposing` (`DECOMPOSE=on`) or `workflow:implementing` (off), running that stage's handler
in the same tick. Full flow: [`state-machine/delivery-stages.md`][pickup].

### User-content drift detection

The drift-sensitive handlers hash the issue title, body, and every human-authored issue-thread comment, and react
once to a change: `workflow:decomposing` re-spawns inline, `workflow:ready` / `workflow:blocked` /
`workflow:umbrella` route back to `workflow:decomposing`, the dev stages resume the locked dev session, and
`workflow:documenting` unwinds to `workflow:validating`. `_handle_fixing`, `_handle_question`, and
`_handle_discussion` deliberately skip the check. The six non-human filters (including the untrusted-author filter and
the bare `/orchestrator continue` exclusion), the legacy-hash normalization, and the per-stage result routing are in
[`state-machine/delivery-stages.md#user-content-drift-detection`][drift].

### `_handle_decomposing` (label `workflow:decomposing`)

Runs the decomposer read-only in a scratch worktree and parses its fenced `orchestrator-manifest` block: `single`
posts the collected-context comment and flips to `workflow:ready`, `split` creates children labeled
`workflow:blocked` and leaves the parent on `workflow:blocked` or `workflow:umbrella`. Half-finished splits recover
rather than re-spawn, a `DECOMPOSE` kill switch falls through to `workflow:implementing`, and commits or a dirty tree
park with the worktree kept. Full flow: [`state-machine/delivery-stages.md`][decomposing].

### `_handle_ready` (label `workflow:ready` → `workflow:implementing`)

A pass-through: post the pickup comment if needed, ratchet `last_action_comment_id` past everything posted while the
issue sat in `workflow:decomposing` / `workflow:blocked`, flip to `workflow:implementing`, and fall into that handler
on the same tick. Full flow: [`state-machine/delivery-stages.md`][ready].

### `_handle_blocked` (label `workflow:blocked`)

The parent reads each child's current label: every child `done` flips the parent to `workflow:ready`, a `rejected` or
manually-closed child parks it, and the dep-graph walk relabels any `workflow:blocked` child whose recorded
dependencies are all `done` to `workflow:ready`. A child with no children of its own and a recorded `parent_number`
is a no-op. Full flow: [`state-machine/delivery-stages.md`][blocked].

### `_handle_umbrella` (label `workflow:umbrella`)

Mirrors `_handle_blocked` for the rejected / manually-closed checks and the dep-graph walk; the difference is the
terminal — every child `done` posts a checkmark comment, stamps `umbrella_resolved_at`, sets `done`, and closes the
issue, since an umbrella has no implementation of its own. Full flow:
[`state-machine/delivery-stages.md`][umbrella].

### `_handle_implementing` (label `workflow:implementing`)

Spawns (or resumes) the locked dev session in the per-issue worktree at
`<WORKTREES_DIR>/<owner>__<name>/issue-<n>` on branch `orchestrator/<owner>__<name>/issue-<n>`. Only a fresh spawn is
gated by the 24h retry budget (`MAX_RETRIES_PER_DAY`, shared with decomposing) — an awaiting-human resume and a
recovered worktree, which skips the agent entirely, are carry-over work rather than retries. New commits on a clean
tree push the branch, open or reuse a PR, and set `workflow:validating`; a dirty tree or a no-commit reply parks. A
`timed_out` run disposes on whether HEAD moved past `pre_implement_sha`, and `interrupted` or a mid-run `paused`
returns without writing pinned state. The external-merge short-circuit, the `/orchestrator continue` retry, and the
plan-PR question the merge terminal is reached past are in [`state-machine/delivery-stages.md`][implementing].

### `_handle_documenting` (label `workflow:documenting`)

The single docs pass on the existing PR worktree, reached only via the final-docs handoff in `_handle_validating`'s
approval branch. It reuses the locked dev session — there is no `documenting_agent` and no separate retry budget —
and advances to `in_review` on either a pushed docs commit or an explicit `DOCS: NO_CHANGE` verdict. Drift during the
hop unwinds the worktree and relabels back to `workflow:validating` without spawning. Full flow:
[`state-machine/delivery-stages.md`][documenting].

### `_handle_validating` (label `workflow:validating`)

Spawns a **fresh** reviewer every round (so a `REVIEW_AGENT` flip takes effect on the next tick) with a read-only
prompt that must end in `VERDICT: APPROVED` or `VERDICT: CHANGES_REQUESTED`. An approval runs the local verify gate,
then `SQUASH_ON_APPROVAL`, then hands off to `workflow:documenting`; `CHANGES_REQUESTED` flips to `workflow:fixing`
**before** the dev spawn. `MAX_REVIEW_ROUNDS` parks with the `/orchestrator add-review-rounds N` escape hatch. Full
flow: [`state-machine/delivery-stages.md`][validating].

### `_handle_in_review` (label `in_review`)

A PR is open and humans drive the merge — the orchestrator never merges from here, so any `merged` state it observes
was produced externally. The handler scans four id namespaces for fresh feedback and routes to `workflow:fixing`
without advancing the watermarks, falls back to the drift check, and otherwise posts the one-shot `:bell:` HITL ping
when the head is mergeable, docs-complete or GitHub-approved, and carries no standing human CHANGES_REQUESTED. Full
flow: [`state-machine/delivery-stages.md`][in-review].

### `_handle_fixing` (label `workflow:fixing`)

The dev fix loop, entered from `in_review` on unread feedback or from `workflow:validating` on a
`CHANGES_REQUESTED` verdict — `pending_fix_at` is the route discriminator that decides whether a pushed fix resets
`review_round` or bumps it. It owns the `IN_REVIEW_DEBOUNCE_SECONDS` quiet window, the `/orchestrator continue` batch
replay, the stranded-fix publish, the in_review-route ACK fast path, and the worktree-drift dead-lock breaker that
hands a stuck validating-route park to `workflow:resolving_conflict`. Full flow:
[`state-machine/delivery-stages.md`][fixing].

### `_handle_resolving_conflict` (label `workflow:resolving_conflict`)

Rebases the PR branch onto `<remote>/<base>` under a hardened git envelope and force-with-lease pushes the result,
flipping back to `workflow:validating` with `review_round=0` and `conflict_round` bumped — reached from an operator
relabel, from the base refresh when a rebase actually conflicts, or from `_handle_fixing`'s dead-lock breaker. A
conflicted rebase resumes the dev; a diverged branch parks unless the worktree is a recognizably orchestrator-produced
unpushed rebase. `MAX_CONFLICT_ROUNDS` caps it. Full flow:
[`state-machine/delivery-stages.md`][resolving-conflict].

### `_handle_question` (label `question`)

The operator-applied read-only Q&A label: the decomposer's backend answers in the per-issue worktree under its own
`question_agent` / `question_session_id` pin, posts the answer pinging `HITL_HANDLE`, and parks. No PR is opened and
no branch is pushed. Commits, a dirty tree, or a timeout park with the worktree **kept** for inspection; closing the
issue flips it to `done`. Per-`park_reason` semantics and the relabel guard are in
[`state-machine/conversation-stages.md`][question].

### `_handle_discussion` (label `discussion`)

The operator-applied architecture discussion: the decomposer explores the design as a tree and closes each round with
a numbered frontier, parking until a trusted human reply resumes the same session. Once a human confirms the shared
understanding the agent may commit `plans/issue-<number>.md` alone, and the stage publishes that one file as a plan
PR whose verdict ends the issue — merged is `done`, closed unmerged is `rejected`. The `issue-N` checkout is
preserved on every round exit. The publication checks, the crash-recovery records, every `discussion_*` park, and the
read-only guard screening a relabel to `workflow:implementing` are in
[`state-machine/conversation-stages.md`][discussion].

## State transition (label lifecycle)

The compact reference diagram for every arc above — the forward spine, the decompose branch, the validating fix loop,
the `in_review` and `workflow:fixing` terminals, the conflict rounds, the family walks, both conversation stages, and
the shared awaiting-human park — is in [`state-machine/lifecycle.md`](state-machine/lifecycle.md).

[typed-states]: state-machine/labels-and-state.md#typed-states-and-the-transition-guard
[legacy-labels]: state-machine/labels-and-state.md#legacy-labels-and-the-migration-off-them
[per-tick]: state-machine/labels-and-state.md#per-tick-flow-workflowtick
[pollable]: state-machine/labels-and-state.md#pollable-issues-and-finalization
[pickup]: state-machine/delivery-stages.md#_handle_pickup-no-label--workflowdecomposing-or-workflowimplementing
[drift]: state-machine/delivery-stages.md#user-content-drift-detection
[decomposing]: state-machine/delivery-stages.md#_handle_decomposing-label-workflowdecomposing
[ready]: state-machine/delivery-stages.md#_handle_ready-label-workflowready--workflowimplementing
[blocked]: state-machine/delivery-stages.md#_handle_blocked-label-workflowblocked
[umbrella]: state-machine/delivery-stages.md#_handle_umbrella-label-workflowumbrella
[implementing]: state-machine/delivery-stages.md#_handle_implementing-label-workflowimplementing
[documenting]: state-machine/delivery-stages.md#_handle_documenting-label-workflowdocumenting
[validating]: state-machine/delivery-stages.md#_handle_validating-label-workflowvalidating
[in-review]: state-machine/delivery-stages.md#_handle_in_review-label-in_review
[fixing]: state-machine/delivery-stages.md#_handle_fixing-label-workflowfixing
[resolving-conflict]: state-machine/delivery-stages.md#_handle_resolving_conflict-label-workflowresolving_conflict
[question]: state-machine/conversation-stages.md#_handle_question-label-question
[discussion]: state-machine/conversation-stages.md#_handle_discussion-label-discussion
