# Workflow state machine

This file documents the label-based state machine that drives every GitHub issue from pickup to terminal. It is split
out of [`architecture.md`](architecture.md), which keeps the high-level overview, module map, and process / agent /
push / event-log details.

The sections below cover:

- [Workflow labels](#workflow-labels) — the label set, what each one means, how a wire label is spelled apart from
  the stage under it, and the migration off the pre-namespace spellings.
- [Per-tick flow (`workflow.tick`)](#per-tick-flow-workflowtick) — how a single tick fans out across repos, partitions
  issues by label, dispatches handlers, and what state each handler reads / writes.
- [Stage handlers](#stage-handlers) — the per-stage flow, the user-content drift hook, and the transitions each
  handler may produce.
- [State transition (label lifecycle)](#state-transition-label-lifecycle) — the compact label-lifecycle reference
  diagram.

## Workflow labels

An issue should have at most one workflow label at a time. Non-workflow labels such as `bug` or `enhancement` are
preserved; the orchestrator only swaps labels from its own workflow set. Label names are part of the public contract
because live GitHub issues carry them.

A state's label and the stage under it are spelled apart throughout this file. `workflow:<tag>` is the **wire label**:
the literal string on the GitHub issue, which is what a label write puts there, the transition guard checks, the
pollable-issue queries ask for, and the per-tick dispatcher partitions on. A bare `<tag>` is the **stage**: the handler
that runs while an issue carries that label, the subpackage under `orchestrator/workflow/stages/` holding it, and the
identifier analytics rows, audit event payloads, and agent-session attribution carry. The labels that were never
namespaced — `in_review`, `question`, `discussion`, and the `done` / `rejected` terminals — read the same either way.

The prefix is a collision guard, not the membership test — being a `WorkflowLabel` member is. A `workflow:`-prefixed
name that is not one resolves to no state at all: the `workflow:dependencies` / `workflow:github_actions` /
`workflow:python:uv` service labels Dependabot stamps on its update PRs
([configuration.md](configuration.md#continuous-integration)) share the prefix and nothing in the tree reads them, so
they route nowhere and a label write leaves them in place exactly as it leaves `bug` or `enhancement`. Applying one as
a workflow label is what the typo guard below rejects.

Three non-workflow **control labels** modify behavior without occupying the workflow slot:

- `backlog` makes the orchestrator skip the issue: the per-tick dispatcher filters it out before the family/fanout split
  (so a parked, workflow-label-less issue cannot fold into the cap-counted family bucket and starve other work under
  `parallel_limit=1`), and each stage handler also skips it before the workflow label is read. Removing it hands control
  back to the state machine on the next tick.
- `paused` is the same hard skip as `backlog` at every point (dispatch, scheduler routing, `_process_issue`, and base
  sync), differing only in intent: `backlog` is a "not yet" hold on a fresh issue, `paused` freezes an already
  in-flight one without discarding its state. Removing it resumes processing on the next tick. Because those skip
  points read the issue's labels at tick start, every stage that runs an agent additionally re-checks a freshly
  fetched issue right after the run returns (`_paused_during_agent_run`, alongside each stage's `interrupted`
  short-circuit — both live on the `workflow/engine/guards.py` owner the stage leaves import directly): the dev-agent
  stages that resume committed work (`implementing`, `in_review`, `fixing`, `resolving_conflict`, the `validating`
  drift / awaiting-human / reviewer-change dev resumes, and the `documenting` initial and follow-up docs passes) and
  the stages whose agent is not a developer (the decomposer run in `decomposing`, fresh spawn and awaiting-human
  resume; the reviewer run in `validating`; and the question and discussion runs, opening round and awaiting-human
  resume alike) all consult it. A `paused` applied
  mid-run stops before a PR opens, the label flips, a HITL park or ACK comment posts, a docs push lands, usage
  counters fold, child issues are created, watermarks advance, or pinned state advances, so a dev stage's committed
  work stays on the branch and republishes through the normal recovered-worktree / stranded-fix path once the label is
  removed, while the read-only decomposer / reviewer / question runs simply re-run from durable state on the next
  tick. The `discussion` run is read-only only until the humans confirm the design: a confirmed round commits
  `plans/issue-<number>.md`, so a pause can leave that commit on the branch with no disposition, exactly as a crash
  can. It is not re-run — the pre-spawn write (the round anchor, `discussion_round_open`, and `discussion_base_sha`)
  is durable whatever the pause withholds, and the next tick reads the commit back through it: a valid plan is judged
  and published as the withheld round would have, and anything else parks on what the branch actually carries. Only a
  round that committed nothing re-runs against the same replies, since the watermark it staged is one of the
  mutations the pause leaves unpersisted. Because `paused` is a plain control label, removing it is the entire resume
  protocol — the next poll picks the
  issue back up from durable state; there is no un-pause command. This is distinct from `/orchestrator continue` (§
  `_handle_fixing` `_handle_continue_command`, plus the shared implementing / documenting handling), which retries
  only specific `awaiting_human` session-failure parked *retry* flows: pausing is never a `park_reason`, so a continue
  command is not an un-pause and does not clear `paused`. It is unrelated to un-pausing, but not exempt from it — the
  hard skip fires in `_process_issue` before any handler, so a continue comment posted on a paused issue is deferred
  with everything else until the label is removed.
- `workflow:community_contribution` is applied by the per-tick open-PR sweep (on the `workflow/engine/tick.py` owner,
  which drives it before per-issue dispatch) when `ALLOWED_ISSUE_AUTHORS` is configured: any open PR whose author is
  not in the allowlist is labeled and `HITL_HANDLE` is @-mentioned once per PR. Bot-authored PRs
  (Dependabot, Renovate, CI bots) are skipped via GitHub's `user.type == "Bot"` flag — they open PRs structurally and
  are not community contributions. The orchestrator does not otherwise drive these PRs. With `ALLOWED_ISSUE_AUTHORS`
  empty (the default), the sweep is a no-op. The label is the sweep's own dedup marker rather than an operator
  control, which is why it is namespaced where `backlog` / `paused` are not, and why the sweep asks for both its
  spellings: a PR the bootstrap rename could not reach is already labeled, and re-labeling it would repeat the ping.

### Typed states and the transition guard

The label vocabulary is defined once in [`orchestrator/workflow/state.py`](../orchestrator/workflow/state.py), which
every caller inside the tree imports directly — `orchestrator.workflow` re-exports the same objects for callers
outside it: `WorkflowLabel` (a `StrEnum`) is the single source of truth for workflow states, and `ControlLabel` holds
the modifiers above. Because `StrEnum` members *are* their wire strings, a member is the GitHub label verbatim — the
enum just gives the names one authoritative definition. The labels the orchestrator writes itself are namespaced
`workflow:<tag>` so a repository's own labels cannot collide with them; `in_review`, `question`, `discussion`, `done`,
`rejected`, and the `backlog` / `paused` controls keep their bare spelling because a human applies or reads those
directly. The automatic `workflow:community_contribution` control is namespaced with the rest of what the
orchestrator applies. The
namespace stops at the GitHub boundary, and `stage_name` on the same owner is what strips a wire label back to the
stage tag every sink below that boundary records. A repository whose labels predate the namespace still carries the
bare spellings; how it moves off them is [below](#legacy-labels-and-the-migration-off-them).

Two guards run at `GitHubClient.set_workflow_label` (the single label-write chokepoint; `create_child_issue` bypasses
`set_workflow_label` and shares only the typo guard for its direct write, coercing each child label through
`coerce_workflow_label` — the same strictness):

- **Typo guard (always strict).** A label name not in `WorkflowLabel` raises immediately, so a typo cannot be applied as
  a literal label that the next tick would treat as unlabeled-pickup. `create_child_issue` coerces each birth label the
  same way, so split children are born with only a valid workflow label and any control label is rejected.
- **Transition guard (`WORKFLOW_TRANSITION_GUARD` = `off` / `warn` / `enforce`, default `warn`).** An illegal
  `current → new` relabel is checked against `ALLOWED_TRANSITIONS`. `warn` logs the rejected edge through the
  `orchestrator.state_machine` logger and proceeds; `enforce` raises `IllegalTransition`; `off` disables the check. A
  same-label re-set is always allowed. That logger name is spelled out literally in the owner, so an operator log
  filter selects on it regardless of which module the guard lives in.

`ALLOWED_TRANSITIONS` is a forward spine (e.g. `workflow:implementing → workflow:validating → workflow:documenting`)
plus interrupt / detour edges declared per-target. It is keyed by `WorkflowLabel` members, so a pre-namespace label
resolves to its member before the guard sees it and is checked against the same edges. Operator relabels via the
GitHub UI bypass both guards, so the guard never fights a human.

- _(none)_ — Open issue not yet picked up by the orchestrator.
- `workflow:decomposing` — The decomposer is deciding whether the issue is single-context or should become child
  issues.
- `workflow:ready` — The issue is decomposed and has no unresolved blockers.
- `workflow:blocked` — The issue is waiting on child issues or dependency edges.
- `workflow:umbrella` — Parent issue with no implementation of its own; closes to `done` when all children resolve.
- `workflow:implementing` — The dev agent is producing commits in a per-issue worktree. A clean result advances to
  `workflow:validating`.
- `workflow:documenting` — The single docs pass on the existing PR worktree, reached only via the final-docs handoff
  in `_handle_validating`'s approval branch (after verify + squash). Advances to `in_review` after a pushed docs
  commit OR an explicit `DOCS: NO_CHANGE` verdict.
- `workflow:validating` — The reviewer agent is checking the diff; on `VERDICT: APPROVED` the local verify gate runs
  `VERIFY_COMMANDS` before the squash + `workflow:documenting` handoff. `CHANGES_REQUESTED` relabels to
  `workflow:fixing` before the dev spawn.
- `in_review` — A PR is open and ready for human review. The orchestrator never merges from here — humans drive the
  merge. A mergeable PR whose current head completed the reviewer-approved final-docs handoff (or carries a real GitHub
  APPROVED review), with no standing human CHANGES_REQUESTED on that head, earns a one-shot HITL ping per head SHA.
- `workflow:fixing` — The dev fix-loop is active. Entered on unread in-review feedback OR a `CHANGES_REQUESTED`
  verdict. A successful fix bounces directly back to `workflow:validating` so the reviewer re-approves.
- `workflow:resolving_conflict` — The orchestrator is resolving a rebase conflict on a PR branch against
  `<remote>/<base>`. Reached only when the per-tick base-sync rebase actually leaves conflicted files, or via an
  operator relabel.
- `question` — Operator-applied read-only Q&A label: the decomposer agent answers in the per-issue worktree and waits
  on a human reply or close. No PR is opened.
- `discussion` — Operator-applied architecture discussion: the decomposer agent researches the repository, explores the
  design as a tree, and comes back with a numbered frontier of currently-answerable questions plus its own recommended
  answers, then parks awaiting human. Answering by number resumes the same session, which recomputes the frontier
  around what those answers settled and parks again, for as many rounds as the humans reply. Once a human confirms the
  shared understanding, the same session commits `plans/issue-<number>.md` and the stage publishes that one file as a
  plan PR, keeping the label and opening no further round while the humans read it. Nothing is implemented here and
  nothing routes an issue in. What takes it out is the humans deciding, in one of three places. Their verdict on that
  plan PR is drained by the stage itself: merged is `done`, closed unmerged is `rejected`, and either finalizes the
  issue and reaps the worktree and the branches. Closing the ISSUE before a plan PR exists is `rejected` the same way,
  with no teardown. Otherwise a human relabel takes it out — to `done` or `rejected` by hand, the two edges
  `ALLOWED_TRANSITIONS` grants the state, or through the GitHub UI to `workflow:implementing` to have the plan built,
  which arrives as an operator relabel and is screened by the read-only guard rather than travelling a graph edge.
- `done` — Terminal success; PR merged, umbrella resolved, or a `question` issue closed.
- `rejected` — Terminal rejection; PR or issue closed without merge.

### Legacy labels and the migration off them

A repository whose labels predate the namespace carries the bare spellings on live issues, so moving it over is one
write plus the reads that cover what that write could not reach.

The write is the label bootstrap, which `runtime.startup.connect_clients` runs once per configured repo at process
start — so such a repository is migrated at the next start, not mid-tick. `ensure_workflow_labels` walks both
vocabularies and provisions each label the repository is missing. Only a namespaced label has a pre-namespace
spelling to migrate off, so only those reach all three answers:

- **The namespaced label already exists** → nothing happens, and a bare label still defined on the repository beside
  it stays defined. The bootstrap neither renames nor deletes it: at the repository level a leftover of its own and a
  name the repository picked for itself are the same thing. Issues still carrying that bare label come off it one
  relabel at a time under the rules below, not on a second bootstrap pass.
- **Only the pre-namespace spelling exists** → it is renamed in place rather than duplicated, which carries every
  issue holding it across in a single edit — including the closed ones and the `backlog` / `paused` parked ones no
  label write of the orchestrator's would otherwise reach.
- **Neither exists** → the namespaced label is created fresh.

The seven labels that were never namespaced — `in_review`, `question`, `discussion`, `done`, `rejected`, and the
`backlog` / `paused` controls — have no second spelling to migrate off, so the bootstrap only ever skips one that
already exists or creates it bare. Which vocabulary a spec came from decides nothing here: the rename is driven by the
label's own spelling, which is why it covers `workflow:community_contribution` alongside the states.

A PAT without `Issues: Read and write` can neither rename nor create: the refusal is logged and the rest of the
bootstrap is abandoned, leaving that repository on its old vocabulary until the permission is granted and the process
restarts. That, the skip case above, and a human re-adding a retired label by hand are what the reads below exist
for.

Three reads take either spelling, so none of them depends on the rename having run:

- **Routing.** `github.labels.workflow_label` reads an issue's labels through `issue_workflow_label`, which resolves a
  bare tag back to its `WorkflowLabel`, so an issue still carrying the old label reaches its handler and the next
  label write rewrites it to the namespaced spelling. (`label_for_name` is the same lookup on the write side, where
  `coerce_workflow_label` accepts either spelling for a label about to be applied.)
- **The community sweep.** It asks for both spellings of `workflow:community_contribution` and rewrites neither: the
  label it finds is proof the PR's one HITL ping already went out, and re-labeling would repeat it.
- **The closed-issue sweep.** Each sweep label is queried under its pre-namespace spelling too, because a closed issue
  is the one case no other pass revisits — see [Pollable issues and finalization](#pollable-issues-and-finalization)
  for the request cost that carries.

An issue can therefore carry both spellings at once, and the namespaced one always wins — `issue_workflow_label`
scans for it across every label before it will settle for a bare tag, so the order GitHub happens to return them in
cannot change the answer. The write side mirrors that read. `replaced_label_names` takes off the namespaced labels
always; a bare tag joins them only when it names a state coming off anyway — because the namespaced spelling of that
same state sits beside it, or because the issue has no namespaced label at all and the bare one *is* its
pre-migration state. So a bare `blocked` or `ready` the repository uses for its own triage, on an issue whose state
is already namespaced, is read past and left in place: that protection is the point of the namespace, and it would be
worth nothing if a relabel deleted the label anyway. The one case the two spellings cannot be told apart is a bare tag
on an issue with no namespaced label — there it is taken as the pre-migration state, which is what lets the issue
keep routing.

## Per-tick flow (`workflow.tick`)

Each tick fans out across every configured repo (`config.default_repo_specs()` returns one `RepoSpec` per `REPOS` line)
and dispatches per-issue handlers through a long-lived `IssueScheduler` capped by `MAX_PARALLEL_ISSUES_GLOBAL` /
`MAX_PARALLEL_ISSUES_PER_REPO`. See
[`architecture.md#per-tick-flow-workflowtick`](architecture.md#per-tick-flow-workflowtick) for the multi-repo dispatch
and scheduler lifecycle.

One repo's pass is owned by `workflow/engine/tick.py` (`workflow.tick` is the entry point into it) and runs four
things in a fixed
order: the base refresh below, then the community-contribution PR sweep and the repo skill-catalog emission, then
either the scheduler handoff or the in-tick sequential / bounded-parallel loop. The refresh goes first because the two
passes after it read what its fetch left behind, and it is the only one whose failure the tick catches — the sweep and
the emission are internally fail-open. Both of those sit before the scheduler / in-tick split so they fire exactly once
per tick on either path.

The dispatch loop classifies each pollable issue by workflow label before submitting it:

- **Family-aware labels** (`workflow:decomposing`, `workflow:blocked`, `workflow:umbrella`, unlabeled pickup) read and
  write cross-issue state (parent ↔ child). They are folded into one bucket per repo that drains sequentially on a
  single worker thread, so parent / child handlers cannot race. A bucket whose every label is in
  `_CAP_EXEMPT_FAMILY_LABELS` (`workflow:blocked` or `workflow:umbrella` — pure label / dep-graph walks) runs on a
  dedicated executor and does not consume a `MAX_PARALLEL_ISSUES_*` slot, so a blocked parent waiting on children
  cannot deadlock those children.
- **Fan-out labels** (`workflow:ready`, `workflow:implementing`, `workflow:documenting`, `workflow:validating`,
  `in_review`, `workflow:fixing`, `workflow:resolving_conflict`, and the operator-applied `question` and
  `discussion`) only touch their own state and worktree. They run concurrently up to the per-repo and global caps. A
  **closed** fan-out issue (a merged-PR, closed-`question`, or closed-`discussion` issue still carrying its sweep
  label, surfaced by the closed-issue sweep) is submitted `cap_exempt=True`: its handler only runs a terminal
  finalization (flip to `done` / `rejected` + branch cleanup) — or, on a closed `discussion` whose plan PR is still
  open, one PR poll and nothing at all, since that issue is held for the humans' verdict rather than finalized — with
  no agent spawn, so it must not be starved behind active agent work — otherwise under `parallel_limit=1` a merged-PR
  issue sits closed-but-labeled for many ticks while a sibling reviewer or docs agent holds the only slot.

The duplicate-active gate keys on `(repo_slug, issue_number)`: an in-flight handler that straddles polling passes is
reported active to the next poll's submit, which is rejected as `duplicate_active`. The pre-tick base-refresh skips any
active issue's worktree.

Only issue numbers cross the thread boundary — each scheduler worker mints a fresh `GitHubClient` via
`gh._for_worker_thread()` and re-fetches its Issue against that client.

### Base refresh

Before any issue is dispatched the tick runs `_refresh_base_and_worktrees(gh, spec)`: a single
`git fetch <spec.remote_name> <spec.base_branch>` in `spec.target_root`, then per-issue dispatch on each existing
worktree under `<WORKTREES_DIR>/<owner>__<name>/issue-*`. The remote name defaults to `origin` and is overridable per
`REPOS` row. Per-stage `_ensure_*_worktree` helpers only fetch on (re)creation, so without this refresh long-lived
worktrees would stay anchored to whatever `<remote>/<base>` looked like when first added.

Two paths depending on whether a PR exists:

- **Pre-PR worktrees** get a clean-tree `git rebase <remote>/<base>` directly — no remote to push, so the local branch
  stays linear without publishing a rewrite.
- **PR-having worktrees** in `workflow:validating` / `workflow:documenting` / `in_review` / `workflow:fixing` go
  through `_sync_pr_worktree_to_base`. A clean rebase pushes (force-with-lease pinned to the pre-rebase SHA so a
  foreign update rejects rather than being clobbered), resets `review_round`, posts a PR notice, and relabels to
  `workflow:validating` so the reviewer re-runs against the rewritten head. Only when the rebase actually leaves
  conflicted files does the helper relabel to `workflow:resolving_conflict`.

The `question` label skips both paths unconditionally — its handler tears down its own
worktree, and merging base into a question worktree would either accrete commits on a read-only branch or mask an
inspection state.

Refresh-only failure modes — push rejected (`auto_base_rebase_push_failed`), rebase failed without conflicted files
(`auto_base_rebase_failed`), dirty-after-clean-rebase (`auto_base_rebase_dirty`) — reset HEAD back to the pre-rebase
SHA and park awaiting human with a durable `park_reason`. Recovery is refresh-only and gated on a fresh human
issue-thread comment past `last_action_comment_id`; the actual `awaiting_human` / `park_reason` clear is deferred to the
same pinned-state write that publishes real progress, so an early-return path cannot silently drop the retry intent.
Every PR-stage handler short-circuits at its `awaiting_human` gate when `park_reason in _AUTO_REBASE_PARK_REASONS` so
the refresh owns the operator's retry comment.

Before rebasing, the flow fetches `gh.get_pr(pr_number)` and skips when `pr_state != "open"`: a just-merged PR advances
`<remote>/<base>`, so the stale worktree is naturally behind base; without this gate the refresh would push and relabel
a PR the next handler would finalize. A `gh.get_pr` failure is treated as "leave alone".

### Pollable issues and finalization

`gh.list_pollable_issues()` yields all open non-PR issues plus closed non-PR issues still labeled with one of the
eight sweep labels: `workflow:implementing`, `workflow:documenting`, `workflow:validating`, `in_review`,
`workflow:fixing`, `workflow:resolving_conflict`, `question`, `discussion`. Each is queried under its pre-namespace
spelling too, because a closed issue is the one case no other pass revisits: on a repository whose labels the
bootstrap could not rename (see
[Legacy labels and the migration off them](#legacy-labels-and-the-migration-off-them)), the bare label is
all that is left to find it by. Both queries feed one seen-number set, so an issue carrying both spellings is yielded
once. The closed-issue sweep makes external manual merges and operator closes finalize cleanly:
- Closed `in_review` / `workflow:fixing` / `workflow:resolving_conflict` — a human-merged PR with a `Resolves #N`
  footer auto-closes the issue before the orchestrator can flip the label.
- Closed `workflow:implementing` / `workflow:documenting` / `workflow:validating` — the same external-merge race when
  the human merges before reaching `in_review`. Each handler's entry-time `_finalize_if_pr_merged` flips to `done`
  instead of stranding the issue.
- Closed `question` — a human closing the issue is the terminal signal `_handle_question` consumes to finalize to
  `done`.
- Closed `discussion` — two different endings, and the label is swept for a longer window than the rest. With no plan
  PR published, the close is the whole signal and `_handle_discussion` finalizes to `rejected`, which is what takes
  the issue back out of the sweep. WITH one, the close says nothing about the design: the stage holds its terminal
  and keeps the `discussion` label precisely so this sweep goes on yielding the issue until the plan PR itself
  merges (`done`) or closes unmerged (`rejected`). Nothing else revisits a closed issue, so a terminal flip while
  that PR is open would strand the worktree and the branches the plan lives on.

Pre-PR labels (`workflow:decomposing` / `workflow:blocked` / `workflow:umbrella` / `workflow:ready`) are not swept
closed — a closed issue at those stages is a hard human stop until an operator relabels.

The closed-issue sweep issues one closed-issue query per sweep label the repository actually carries, per repo, every
tick — a fixed request cost that drives GitHub primary-rate-limit exhaustion on multi-repo hosts. A pre-namespace
spelling the rename already retired costs only its `GET …/labels/<name>` miss, and even that is thrown away for
twenty sweeps before being asked again rather than re-requested every pass.
`CLOSED_ISSUE_SWEEP_EVERY_N_TICKS` (default `1`) batches the whole sweep to once every N ticks; the open-issue poll is
unaffected, so the only effect of `N>1` is that an externally-merged/closed issue can take up to `N-1` extra ticks to
finalize. See [configuration.md#github-rate-limits](configuration.md#github-rate-limits).

`done` and `rejected` are terminal no-ops. Every handler receives the active `RepoSpec`, so `git worktree add`,
`git fetch <spec.remote_name> <spec.base_branch>`, push-token resolution, and PR-base selection all flow from the spec.

### Pinned state

Per-issue durable state lives in a single **pinned comment** on the issue (`<!--orchestrator-state {...json...}-->`).
The schema is defined by `read_pinned_state` / `write_pinned_state` (see `github.pinned_state.PINNED_STATE_MARKER` /
`PINNED_STATE_RE`). `read_pinned_state` trusts a comment as state only when it is authored by the account backing the
orchestrator's token AND its whole body is the marker, so neither a third party's forged marker nor an ordinary
bot-authored comment that embeds the marker in prose can preempt state (see
[pinned-state authentication](security.md#pinned-state-authentication)). The keys that matter for the state machine fall
into a few groups:

- **Agent identity.** `dev_agent` + `dev_session_id` (locked dev session — see
  [in-flight session lock](workflow.md#in-flight-session-lock--pinned-full-spec-until-the-session-ends)),
  `review_agent` (traceability only; reviewer is fresh per round), `decomposer_agent` + `decomposer_session_id`
  (parents), `question_agent` + `question_session_id` (`question` stage), `discussion_agent` +
  `discussion_session_id` (`discussion` stage). The last three pairs are separate pins on purpose: each conversation
  seeds from `DECOMPOSE_AGENT` on its own first spawn and is then locked independently of the others on the same issue,
  and each resumes its own session id on a human reply, so a flip of `DECOMPOSE_AGENT` between two rounds can neither
  move a conversation onto a backend that never ran it nor hand that backend a session id it never issued.
- **Decomposition.** `children`, `dep_graph` (`{child_idx_str: [child_idx, ...]}` — GitHub has no first-class blocks
  relation), `decomposed_at`, `pickup_comment_id`.
- **PR / branch.** `branch`, `pr_number`, `review_round`, `conflict_round`. The first two are also what a published
  discussion plan records, beside `discussion_plan_path` — the path of the Markdown file that PR carries. The stage
  reads the plan path and `pr_number` together as its "already published" gate, since an issue relabeled into
  `discussion` from a PR stage arrives carrying somebody else's `pr_number`. `discussion_publishing_sha` is the
  in-flight half of that record: the tip a publication was pushing, written before the push and retired by the write
  that records the PR, and the only thing that makes a plan-shaped commit on a parked issue's branch one this stage
  may finish rather than one it merely found there.
- **Drift baseline.** `user_content_hash` — SHA-256 over title + body + non-orchestrator comments; updated whenever
  the orchestrator reacts to a human edit.
- **HITL park.** `awaiting_human`, `last_action_comment_id`, `park_reason`. `_park_awaiting_human` (on the same
  `workflow/engine/guards.py` owner as the two run refusals) sets
  `awaiting_human=True` and clears `park_reason` to `None`; a handler that needs the reason to survive into the next
  tick explicitly re-sets it after the park call. Park reasons that route via `_park_auto_rebase_failure`
  (`auto_base_rebase_failed` / `auto_base_rebase_dirty` / `auto_base_rebase_push_failed`) are owned by the per-tick
  base-sync flow — every PR-stage handler short-circuits when `park_reason in _AUTO_REBASE_PARK_REASONS`.
- **In-review watermarks.** `pr_last_comment_id` (issue thread + PR conversation, shared IssueComment id space),
  `pr_last_review_comment_id` (inline PR review comments), `pr_last_review_summary_id` (PR review summary bodies). Only
  non-empty `CHANGES_REQUESTED` or `COMMENTED` review IDs ever advance the summary watermark; `APPROVED`, `DISMISSED`,
  `PENDING`, and empty-body reviews are filtered before the bump.
- **Final-docs handoff.** `docs_checked_sha` + `docs_verdict` (`updated` / `no_change`) set by `_handle_documenting`'s
  success exits. `ready_ping_sha` records the head the in_review handler already posted a `:bell:` HITL ping for.
  `docs_drift_unwind_pending` is set while `_handle_documenting`'s drift block is reconciling and cleared only on the
  relabel back to `workflow:validating`.
- **Fix routing.** `pending_fix_at` + per-namespace `pending_fix_issue_max_id` / `pending_fix_review_max_id` /
  `pending_fix_review_summary_max_id` recorded by the `in_review → fixing` route, plus the full
  `pending_fix_issue_ids` / `pending_fix_review_ids` / `pending_fix_review_summary_ids` batch lists. They are hints, not
  watermarks — the in_review watermarks are deliberately left behind so the `fixing` rescan can re-discover the
  triggering comments, and the id lists let `_reconstruct_pending_fix_batch` rebuild the exact triggering batch after
  the watermarks advance past it (falling back conservatively to the max ids for issues parked before the lists were
  recorded). The `validating → fixing` route instead records a single `pending_fix_reviewer_comment_id` — the id of the
  PR conversation comment carrying the reviewer's CHANGES_REQUESTED feedback — and does NOT set `pending_fix_at` (that
  key is the route discriminator that drives the review-round reset). `_reconstruct_pending_fix_batch` re-fetches that
  exact comment by id (outside `filter_trusted`, since it is the orchestrator's own reviewer output the author allowlist
  would otherwise drop) as the validating-route replay anchor. The rebuilt batch is what the `/orchestrator continue`
  operator command replays when retrying a session-failure park (see `_handle_fixing`); the anchor is cleared on a
  pushed fix and inside `_clear_pending_fix_bookmarks`.
- **Crash-recovery anchors.** `discussion_round_branch` + `discussion_round_sha` — the branch a discussion round
  opened on and the SHA it was at, written BEFORE the spawn and surviving every exit the stage takes; a published plan
  moves the pair onto the tip it pushed (that commit is what the stage now vouches for) and only a
  successful relabel out (`_clear_stale_read_only_park`) drops it. It answers two questions, and which one is
  being asked is settled by whether the discussion stage has the issue parked:
  on an unparked issue it means a round ended with no disposition (withheld by a mid-run `paused`, or cut short) and
  comparing it to the branch says whether that round committed; on a parked one it says everything the branch carries
  AT that SHA predates this stage — which is what `read_only_relabel.py` reads to let a discussion held on an
  inherited PR branch relabel to implementing. A park that *did* find a commit keeps the pair for that second reading:
  it is the tip the park tells the operator to reset back to, and the one the guard then certifies, so dropping it
  would strand a PR-backed issue whose only other remedies (reset to base, delete the branch) destroy the PR. The
  branch is recorded beside the SHA because an issue pinned to a legacy `orchestrator/issue-N` ref opens its round
  there, and answering for the slug-namespaced ref instead would report an unchanged tip while the commit sat
  elsewhere.
  `read_only_baseline_sha` — what that anchor becomes when the relabel clears. `_clear_stale_read_only_park` hands the
  certified tip to the implementing stage rather than dropping it, because the fresh-spawn path reads any branch ahead
  of base as a previous dev run whose publication was interrupted (`_has_new_commits`) — and the branch a discussion
  was held on may legitimately be ahead of base already. Without the handover the first implementing tick would skip
  the implementer and republish the inherited commits as the work the discussion just agreed to. It is the anchor
  except where the same handoff moved the branch onto a plan PR's live head, in which case it is that head: what this
  key has to name is where the branch REALLY sits, not which commit the record started from.
  `spawn._recovered_work_present` spends it: while HEAD still sits on that SHA the commits are inherited and the dev
  runs, and once the dev commits, HEAD moves off it and the key is dropped. `publication._advance_to_validating`
  spends it too, since an issue leaving for `validating` has published and would otherwise carry the key — and
  everything the key holds — out of this stage with it.
  Standing beside `discussion_plan_sha`, it is also the record that says a handoff was ACCEPTED and nothing here has
  published since, which is a state a crash can leave an issue in for polls at a time: the write lands before the
  developer runs and an interruption drops everything staged after it. While it stands,
  `read_only_relabel._reconcile_open_plan_handoff` takes the guard's own reading again on every tick — the same plan
  PR read, the same re-anchor onto what it carries, the same two records written — because the humans still have the
  design on an open pull request and can move its head. Left unwatched, an amendment made in that window reads as this
  stage having pushed: merged, the issue closes as `done` with no developer having run, and unmerged the developer is
  spawned on the checkout the handoff left and its ordinary push takes the amendment back out. A merge alone matters
  with nothing amended, since the freeze below would otherwise start the developer behind a base the plan has just
  landed in. What ENDS the reconcile is the branch and not a record, because a push reaches git before it reaches the
  issue: a tip past the baseline is a developer's work, and a tip that could not be read is no answer at all and holds
  the tick.
  `read_only_anchor_sha` — the head that reconcile is moving the branch onto, written before the move and retired by
  the write that records where it landed. The move has the same window the handoff itself does, one level down: the
  ref is put on the reviewers' head before anything says it was, and the branch a crash in between leaves is a tip
  past the baseline — which the reading above would call a developer's commit, handing their amendment to the
  recovered-work shortcut to push with no agent having run. A marker still standing says the branch is where this
  stage was putting it, so the move is simply made again; nothing is spawned between the two writes, so no developer
  can have committed under one. `publication._advance_to_validating` clears it beside the baseline.
  `disposition._run_left_commits` reads the
  same floor at the other end of the tick, so a dev that answers with a question instead of committing parks on it
  rather than having the inherited commits published as its work. Both the cleared park and this key are written
  BEFORE the spawn, because a mid-run pause or a shutdown interruption returns without writing pinned state at all:
  staged, the acceptance would be lost and the next tick would read the park and anchor back and convict the
  developer's own commit. An unspent baseline also holds the branch out of the base refresh (`_issue_skips_base_sync`
  again), since a rebase would move HEAD off the certified SHA while the inherited commits it names are still there
  and the next spawn would read them as an interrupted dev run. `_publish_committed_work` retires it — there is
  committed work to publish either way at that point — so the freeze ends with the stage that needed it rather than
  following the issue through review.
  `pending_auto_base_rebase_push_sha` — set to the pre-rebase local HEAD immediately BEFORE
  `_rebase_base_into_worktree`; cleared on every exit. A non-empty value on entry means a previous tick rebased and died
  before the post-push write, and `_recover_pending_auto_base_rebase` keys off it to either no-op, push the recovered
  head, or park as `auto_base_rebase_push_failed`.
- **Counters / timestamps.** `retry_window_start` + `retry_count` (24h fresh-spawn budget shared between implementing
  and decomposing), `silent_park_count` (dev-session silent-park counter), `dev_resume_count` (per-dev-session resume
  budget; once it reaches `DEV_SESSION_MAX_RESUMES` the session is retired and respawned fresh from durable state, reset
  to 0 on every fresh spawn), `merged_at` / `closed_without_merge_at` terminal stamps, and the per-round stamps
  `last_question_at` / `last_discussion_at` the two operator-applied conversation stages set on every run they settle.
- **Usage meter.** `issue_agent_runs` + `issue_total_tokens` + `issue_total_cost_usd` + `issue_cost_sources` are
  per-issue cumulative counters folded in by `_accumulate_issue_usage` at each developer (implementing), reviewer
  (validating), decomposer (decomposing), question, and discussion run site from the `UsageMetrics` that
  `_run_agent_tracked` parses. `issue_total_tokens` sums input +
  output + cache-read + cache-write (codex `cached_tokens` is excluded — it is already part of `input_tokens`, so
  summing it would double-count); `issue_total_cost_usd` sums each run's `cost_usd` (`None` costs from `no-usage` /
  `unknown-price` runs add nothing); `issue_cost_sources` is the sorted distinct `cost_source` set a terminal verdict
  reads to mark `(est.)` (any `estimated`) or unpriced `unknown` (any `unknown-price`). The increment rides the
  handler's existing single `write_pinned_state`, so an `interrupted` run that returns without writing never accrues.
  The decomposer / question / discussion stages additionally skip the fold for `interrupted` runs, so even
  their dirty/commits inspection park (which does write pinned state) records no counter.
- **Terminal usage verdict.** `_format_issue_usage_verdict` renders those counters into one visible receipt line
  (`:receipt: this issue: N agent runs · T tokens · $X.XX`, `(est.)` appended when any `estimated` contributed,
  `unknown` in place of the figure when an `unknown-price` run leaves the total incomplete). It returns nothing when
  no run was counted, so a terminal with an empty meter posts no receipt. Every terminal surface renders it before its
  single `write_pinned_state`: the PR merged / rejected finalizers (`_finalize_if_pr_merged`,
  `_drain_review_pr_terminals` — all three arcs, including the open-PR/manually-closed-issue rejection — and
  `_finalize_if_issue_closed`, all on the `workflow/engine/terminals.py` owner the stage leaves import
  directly) post it as a standalone `_post_issue_usage_verdict` comment, the `umbrella`
  all-children-done branch appends it to its close comment, the closed-`question` terminal posts it when
  question-stage counters accrued, and the `discussion` stage's plan-PR terminal posts it on each of its three
  endings — the merged plan, the plan closed unmerged, and a close with no plan PR at all — since that owner
  composes those same three arcs directly rather than through either entry point. Reusing `_post_issue_comment`
  keeps the receipt's comment id tracked in
  `orchestrator_comment_ids`. This is a read-only verdict — no budget breaker or control behavior gates on it.

The legacy `codex_session_id` key (written before `dev_agent` existed) is still honored on read by `_read_dev_session`:
it round-trips to `spec="codex"` with no args so an older orchestrator's pin keeps running on codex.

## Stage handlers

### `_handle_pickup` (no label → `workflow:decomposing` or `workflow:implementing`)
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

### User-content drift detection

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
  [the trust boundary](security.md#comment-trust-boundary-allowed_issue_authors)); the awaiting-human resume paths
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

### `_handle_decomposing` (label `workflow:decomposing`)
- **Trigger**: each tick while the label is `workflow:decomposing`.
- **Input**: issue + comments + pinned state (`decomposer_agent` / `decomposer_session_id`, retry-budget keys,
  `children`, `dep_graph`, `expected_children_count`, `umbrella`).
- **Internal flow**:
  1. **User-content drift check** (inline) — see drift section above.
  2. **Half-finished decomposition recovery.** If `expected_children_count` is set OR `children` is non-empty (a prior
     tick crashed mid-split), the handler cannot safely respawn the decomposer. When `expected_children_count` is set
     and `len(children) < expected_children_count`, park with `decomposition_crash`. Otherwise repair any child whose
     pinned `parent_number` was never seeded, then finalize to `workflow:umbrella` (when the flag is true) or
     `workflow:blocked`.
  3. **DECOMPOSE kill switch.** If `config.DECOMPOSE` is off when this handler runs, clear decomposer-side park flags,
     ratchet `last_action_comment_id` past every visible comment, flip the label to `workflow:implementing`, and fall
     into `_handle_implementing`. Step 2 runs first so orphan children are not abandoned.
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
### `_handle_ready` (label `workflow:ready` → `workflow:implementing`)
- **Trigger**: each tick while the label is `workflow:ready`. Reached by a `single`-decision parent or a
  freshly-created child.
- **Action**: post the pickup comment if needed, bump `last_action_comment_id` to the latest visible comment id (so
  comments posted while the issue sat in `workflow:decomposing` / `workflow:blocked` are marked consumed before the
  implementer reads them at spawn), flip to `workflow:implementing`, fall through into `_handle_implementing` on the
  same tick.

### `_handle_blocked` (label `workflow:blocked`)
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

### `_handle_umbrella` (label `workflow:umbrella`)
- **Trigger**: each tick while the label is `workflow:umbrella` (only ever a parent — set by the decomposer when the
  manifest's `umbrella` boolean is true).
- **Input**: pinned `children` and optional `dep_graph` on the parent.
- **Internal flow**: mirrors `_handle_blocked` for the rejected / manually-closed checks and dep-graph walk. The only
  difference is the all-done terminal: when every child reaches `done`, post a checkmark comment, stamp
  `umbrella_resolved_at`, set label `done`, close the issue. A `children`-less umbrella is treated as corrupt state and
  parks.
- **Output**: terminal `done`, OR a sibling unblocked, OR a HITL park, OR a no-op.

### `_handle_implementing` (label `workflow:implementing`)
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
### `_handle_documenting` (label `workflow:documenting`)
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

### `_handle_validating` (label `workflow:validating`)
- **Trigger**: each tick while label is `workflow:validating`. Set by `_handle_implementing` after `_on_commits` opens
  the PR, by `_handle_documenting`'s drift unwind, and by `_handle_fixing` / `_handle_in_review` /
  `_handle_resolving_conflict` on their pushed exits.
- **Input**: PR #, branch, `dev_agent` / `dev_session_id`, `review_round`.
- **Internal flow**:
  0. **External-merge / closed-issue short-circuit** (same chain as implementing / documenting). The reviewer is not
     spawned on either short-circuit.
  1. Awaiting-human path: resume on the dev's locked spec; on a successful pushed fix, bump `review_round` and stay on
     `workflow:validating`. Exception: on a `review_cap` park the human reply does NOT wake the dev — the operator
     must post `/orchestrator add-review-rounds N` on its own line (honored only from an allowlisted author when
     `ALLOWED_ISSUE_AUTHORS` is set — an outsider's command is filtered out before the parse), which resets
     `review_round` to `MAX_REVIEW_ROUNDS - N`, clears the park, and falls through to spawn the reviewer this same
     tick. A second exception: a bare `/orchestrator continue` on a session-failure dev park (`agent_silent` /
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
       [`configuration.md#local-verification-gate`](configuration.md#local-verification-gate)); (2) post
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
     flip standing and `_handle_fixing` owns the resume once the label is removed.
- **Output**: label moved to `workflow:documenting` (approval after verify + squash) OR `workflow:fixing`
  (CHANGES_REQUESTED) OR no label change with `review_round` bumped (awaiting-human resume, drift, transient-park
  recovery push) OR a HITL park.

### `_handle_in_review` (label `in_review`)
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

`_park_awaiting_human` posts on the issue (not the PR) so the HITL ping appears alongside the rest of orchestrator
state. The PR comment that triggers a route to `workflow:fixing` is the human signal; awaiting-human is reserved for
*unrecoverable* states (unmergeable / missing pr_number).

### `_handle_fixing` (label `workflow:fixing`)
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
       `_try_recover_validating_transient_park`. On `cleared` or `pushed`, clear park, clear `pending_fix_*`, flip
       back to `workflow:validating` (the helper bumps `review_round` on `pushed`). This closes the loop for
       `_handle_validating`'s CHANGES_REQUESTED route. On `stuck`, fall through to the worktree-drift check below.
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
  6. If no unread feedback at all (watermarks already cover the bookmarks), clear `pending_fix_*` and bounce back to
     `workflow:validating`.
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

### `_handle_resolving_conflict` (label `workflow:resolving_conflict`)
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

### `_handle_question` (label `question`)
- **Trigger**: each tick while the label is `question`. Also runs on closed-`question` issues — that's the terminal
  signal the handler consumes.
- **Input**: issue + comments + pinned state (`question_agent` / `question_session_id`, awaiting-human keys). The label
  is operator-applied — no other handler routes into `question` automatically, and `question` is deliberately NOT in
  `_FAMILY_AWARE_LABELS` so fan-out concurrency is preserved.
- **Internal flow**:
  1. **Terminal close.** If the issue is closed, stamp `question_closed_at`, set label `done`, write pinned state, tear
     down the per-issue worktree + local branch via `_cleanup_question_worktree`. Do NOT spawn the agent.
  2. **Awaiting-human resume.** If `awaiting_human`, scan for new comments past `last_action_comment_id`. No new
     comments → return (the `_question_run_cleanup` context manager still tears down any worktree from a prior safe
     tick). New comments → advance the watermark BEFORE spawning, then resume the locked session via
     `_build_question_followup_prompt`.
  3. **Fresh spawn.** Ensure the per-issue worktree, resolve the question spec via `_read_question_session` (falls back
     to the decomposer's spec on the first-ever spawn), persist `question_agent` BEFORE invoking `run_agent`, build the
     read-only `_build_question_prompt`, spawn, and persist `question_session_id`. A mid-run `paused` / `backlog`
     re-check (`_paused_during_agent_run`) right after the run returns short-circuits the resume and fresh spawn alike
     BEFORE the usage fold, park, or pinned-state write, so the next tick re-runs from durable state (the
     `_question_run_cleanup` context manager still disposes the worktree per `keep_worktree`).
  4. Branch on result:
     - `timed_out` → `_park_question` with `question_timeout`. **Keep** the worktree for operator inspection.
     - new commits → `_park_question` with `question_commits`. **Keep** the worktree: this stage is read-only.
     - dirty tree → `_park_question` with `question_dirty`. **Keep** the worktree.
     - empty `last_message` → `_park_question` with `question_silent` (worktree torn down).
     - clean answer → post the agent's quoted message to the issue (pinging `HITL_MENTIONS`), park with
       `question_answer`, tear the worktree down.

  The `_question_run_cleanup` context manager runs `_cleanup_question_worktree` unless one of the three unsafe-park
  branches set `keep_worktree=True`.
- **Cross-stage interaction (relabel to `workflow:implementing`).** `_handle_implementing` carries an explicit guard:
  when it inherits `awaiting_human=True` + a `park_reason` starting with `question_`, it inspects the worktree AND the
  local branch. A clean worktree + clean branch drops the question-stage park flags, ratchets `last_action_comment_id`
  past the question agent's answer, and falls through to fresh dev-spawn. A dirty worktree OR a branch with commits
  beyond `<remote>/<base>` re-parks with `question_unsafe_relabel`.
- **Output**: an issue comment with the answer / follow-up question + a HITL park, OR a terminal flip to `done` on a
  manual close, OR a no-op tick.

The Q&A flow keeps state minimal: no PR is ever opened, no branch is ever pushed, and the per-issue worktree only
survives across ticks when an unsafe park requires operator inspection. The locked session resumes across cleanup
because session state lives in pinned state, not in the worktree.

### `_handle_discussion` (label `discussion`)
- **Trigger**: each tick while the label is `discussion`. Like `question` the label is operator-applied — no handler
  routes into it, there is no pickup route to it, and it is deliberately NOT in `_FAMILY_AWARE_LABELS`, so fan-out
  concurrency is preserved.
- **Input**: pinned `awaiting_human` + `park_reason`, the consumed `last_action_comment_id` watermark, the
  `orchestrator_comment_ids` list the stage's own comments are recognized by, and the trust-filtered issue thread —
  quoted whole by the full prompt, and from the watermark forward by a resume.
- **Plan-PR terminal**: a recorded `discussion_plan_path` **and** `pr_number` end the tick before anything else — no
  round, no agent — and what that pull request has become is polled first, ahead of every local reading. Both halves
  are read because either alone means something else: an issue relabeled here from a PR stage arrives carrying its
  dev's `pr_number`, and a plan path without a PR is a record no publication ever wrote (they land in one durable
  write). A MERGED plan PR is the humans taking the design and finalizes to `done`; one CLOSED without merging is
  them turning it down and finalizes to `rejected`. Both take the terminal tail every other stage takes, in that
  order: the `merged_at` / `closed_without_merge_at` stamp, the label, the cumulative usage receipt posted BEFORE the
  single pinned write so its comment id rides the same state, the `pr_merged` (`merge_method="external"`) /
  `pr_closed_without_merge` event with `stage="discussion"`, the issue close, and only then
  `_cleanup_terminal_branch` — the worktree plus the local and remote branches. Teardown last is the contract: an
  operator who finds a leftover checkout still has an issue that says what happened to it.
  An OPEN plan PR is neither, and is a strict no-op — no comment, no write, no label — that KEEPS the worktree and
  both branches, since they are what that pull request is open against. That holds whether or not the ISSUE is still
  open: a human closing the issue out from under an open plan PR has said nothing about the design, so the stage
  keeps the `discussion` label (which is what leaves the issue inside the closed-issue sweep) and its checkout until
  the PR itself resolves. A `gh.get_pr` failure is that same hold, since every ending below it is a claim about a
  pull request nobody could read; the tick after this one asks again.
- **Pre-PR close**: a closed issue with no recorded plan PR is finalized to `rejected` — the
  `closed_without_merge_at` stamp, the label, the receipt, one write — ahead of the publication recovery and every
  turn-taking gate below it, since a human stop signal outranks whatever the stage was about to do. No event, because
  there is no pull request for one to name, and no teardown: the branch may be carrying an unpublished plan commit,
  or belong to a PR the issue merely arrived here holding, and neither is something a closed issue alone justifies
  deleting. The `rejected` flip is what takes the issue back out of the closed-issue sweep.
  **A standing `discussion_publishing_sha` is read first, though, and it is what makes "no recorded plan PR"
  different from "no plan PR".** The publication opens its pull request before it writes the number down, so a tick
  that died in that window leaves a real one with nothing pinned pointing at it — and the humans can decide the issue,
  or that pull request, inside the same window. So the marker's commit is looked up across every state
  (`find_pr_for_commit`, the same lookup the publication's own recovery uses) and what comes back decides: a MERGED or
  CLOSED one is finalized here exactly as a recorded one is, with `pr_number` and `branch` written first because the
  event names one and the cleanup resolves the branch from the other. That branch is resolved ONCE, before either is
  set, and the same value serves the lookup and the reap: `_resolve_branch_name` falls back to the pre-namespace
  `orchestrator/issue-N` whenever it finds a `pr_number` with no `branch` beside it, so a branch worked out after the
  recovered number was written would name a ref this stage never pushed and leave the real local and remote branches
  standing. An OPEN one holds the tick exactly as a recorded
  open one does, label and checkout intact; and a lookup GitHub declined decides nothing and is asked again next tick.
  Only "no pull request carries that commit" — a push that never landed, or a tick that died before it — reaches the
  pre-PR ending above. Taken for a discussion that never published, an open one would be flipped out of the sweep with
  its branch and worktree left for nothing to reap, while its plan sat on a pull request nobody would come back to.
- **Interrupted-publication resume**: a `discussion_publishing_sha` naming the tip the checkout is on now, on any park
  other than `discussion_push_failed`, finishes that publication before the turn-taking below runs — no agent, no
  round. It has to run there rather than behind a reply, because the marker's own write persists whatever the round
  staged, the consumed watermark included: an issue whose publication died after that point has nothing unread, so
  waiting for a reply would mean waiting for a human to answer the same round twice. The failed push is the one
  exception, since retrying it every tick would push at a remote already refusing us and comment each time; its
  retry is the reply to its park. A retry already under way is not that state: the write that begins one replaces the
  reason with `discussion_publishing`, in the same write that spends the reply, so a crash inside the retry resumes
  here like any other unfinished publication instead of waiting for a human to say the same thing twice. Every ending
  of the attempt writes its own reason over that one, so it is durable only inside that window.
  While the marker stands it answers for the branch outright: a tip that is neither
  the commit it names nor the round's own anchor parks `discussion_stale_publication` — written once, since its own
  reason is what the repeat reads — rather than falling through to a reading that would publish a second plan-shaped
  commit nobody checked. A tip back AT the anchor is the operator taking the remedy — but only once the REMOTE agrees
  nothing went out: the push sends the SHA it validated rather than `HEAD`, so a plan committed on a detached head
  reaches the remote while the local ref never moves, and a checkout restored later comes back on that ref instead of
  the head just fetched. So the branch is asked for, and the marker is spent only when the remote has no such branch
  or the branch it has does not carry the commit the marker names (asked by containment, since a human amending their
  own plan on its PR moves that tip past it — and asked of an object, so the branch is fetched unless that tip is
  already here, because git refuses an id this clone has never seen and the refusal reads exactly like a branch that
  dropped the commit). A remote that could not be read, or a tip nothing could bring here, establishes nothing and
  keeps the record. Otherwise the pull request carrying the commit is asked for once more — a merge or an amended-open
  head is already settled above, so what is left to find is one the humans CLOSED, which the reset above could also
  have explained and which this reading has now ruled out. Finding it records the number and lets `terminal` finish
  the issue `rejected` on the next tick; finding none writes the same `discussion_stale_publication` park, saying
  that the plan is out
  there and that dropping it means closing its pull request rather than resetting a branch here. A new round retires
  the marker for the same reason the reset does, since a round only opens on a tree the publication's commit has
  already been reset off.
- **Gate**: `awaiting_human` short-circuits the tick's *opening* round **only when `park_reason` carries the
  `discussion_` prefix**. That park is the round already on the thread, which the humans are answering, so nothing new
  is opened over the top of it; what the tick looks for instead is their answer. Issue comments past
  `last_action_comment_id` that survive both `filter_trusted` and the orchestrator's-own-comment drop are what makes
  it this stage's turn again — an empty batch, or one entirely from authors `ALLOWED_ISSUE_AUTHORS` excludes, spawns
  nothing, comments nothing, and writes nothing, leaving the reply (if any) unconsumed for the tick after the
  allowlist changes. A park any *other*
  stage wrote does not gate at all: pinned state outlives a relabel, so an issue an operator moves here while it is
  parked elsewhere is awaiting a reply nobody will send it here, and reading `awaiting_human` alone would leave it
  inert for good.
- **Resume hold**: a parked issue WITH a reply asks the two preflight questions below before opening its round, and a
  yes to either stops the round — opening one anyway would rewrite `discussion_round_sha` with the moved tip
  (spending the reset target the earlier park quoted and the implementing relabel guard re-measures against) or have
  `_ensure_worktree` force-remove the dirty tree the operator was parked to inspect. Ahead of both, and ahead of every
  local reading, `discussion_publishing_sha` is settled. This is the only path that resumes a failed push — the
  interrupted-publication resume above steps around that park deliberately — and "the push failed" is a claim about
  the request, not about the remote: the branch may well be published. On a host that has since lost the checkout AND
  the local ref, every local probe then reads as though nothing ever happened: no tree, no branch, and an anchor
  nothing has moved off. Gated on the moved tip, such an issue opens another round instead, and the round's own
  pre-spawn write retires the marker with it — leaving the plan pushed with no PR, no record, and nothing left that
  knows to look for it. What the marker answers is the branch itself: finished when it names the tip the checkout is
  on now (restored from `<remote>/<branch>` when the directory is gone), spent when the branch is back at the round's
  anchor AND the remote no longer carries the commit it names, and parked `discussion_stale_publication` for any other
  tip rather than that tip being read as the round's own work. Before that refusal, the same pair of questions the
  live publication asks is asked of the COMMIT THE MARKER NAMES rather than of the tip on disk — merged anywhere, or
  open on a head that descends from it — because a checkout rebuilt from the remote after the host lost it comes back
  on the reviewer's own head, which is neither the marker's commit nor the anchor. Asked of that tip instead, the
  ancestry question becomes whether their head descends from itself, and a plan the humans are reading on an open pull
  request is refused for good with no `pr_number` and no plan path ever written.
  A moved tip with no marker standing is the question after it, and
  `discussion_round_open` is what says a round of this stage was still in flight when that commit appeared —
  the resumed-round case. It is read on EVERY moved tip, not only under this stage's own parks: "no discussion park"
  is not "no park at all", and an issue relabeled out to `question` and back arrives awaiting a human under that
  stage's park, still carrying this stage's anchor and session id from a conversation that finished. Read as a round
  of this stage that never reported, a commit the question agent made on the plan path would go onto a plan PR under
  a session that never saw it, so a tip that moved with no round in flight parks `discussion_commits` naming the
  anchor to reset to. The reply that drove a retry is
  consumed by the push it asks for, or a failed one would be asked
  for again by the same comment on every poll. The marker is also how a
  tick that died between `open_pr` and the pinned write stops telling the operator to reset away the commit its PR is
  already open against. A tip neither record accounts for is not published however plan-shaped it looks — the park
  means this stage's round is over, so what appeared on the branch afterwards was put there by something else, and a
  human's next reply (a rejection, even) must not turn it into a published design. Otherwise, whether the hold is
  *reported*
  depends on what the standing park already said: a `discussion_commits` / `discussion_dirty` / `discussion_stranded`
  / `discussion_unreadable_worktree` / `discussion_plan_invalid` / `discussion_push_failed`
  park (`_repair_already_requested`) has already named the paths and quoted the reset command, so the reply is held
  silently rather than earning a second copy of those instructions. Any other park — a round that ended cleanly and
  had its tree dirtied or committed to afterwards — earns one `_park_blocked_resume` comment carrying the paths and
  the reset target, recorded under `discussion_dirty` or `discussion_commits` by which probe fired. A `git status`
  that could not run at all is the third of those and records `discussion_unreadable_worktree` with no reset target
  quoted: the read that would have named one is the thing that failed, so what the comment asks for is an inspection.
  That reason is
  itself a repair request, so the report is written once and every reply after it is held silently. No path here
  consumes the reply, so once the operator resets, the answer they already wrote is picked up on the next tick with
  no further action from them.
- **Preflight** (two halves, both WITHOUT spawning). First, a `discussion_round_sha` on an unparked issue means a
  round opened and never reached a disposition; if the checkout's HEAD has moved off it — or, when the directory is
  gone, the tip of the recorded `discussion_round_branch` has, which is asked instead of whether the branch is ahead
  of base so an issue relabeled here from a PR stage is not convicted of its dev's commits — that round committed, and
  the tick settles that commit now rather than letting the next round adopt it as its own baseline. Settling it means
  the same publication check the disposition runs: a valid plan is published exactly as the ended round would have
  published it (restoring the checkout first when only the directory is gone), and anything else parks
  `discussion_plan_invalid` naming what the branch carries. A
  matching HEAD just means the withheld round left nothing, and the tick replays it as the pause promised. Second,
  uncommitted changes already in the `issue-N` checkout park `discussion_stranded`: every park this stage writes
  suppresses the next tick, so a dirty tree at the top of a tick
  came either from a round that died before it could park on what it wrote or from the stage the issue was relabeled
  out of — and `_ensure_worktree` force-removes a dirty checkout that carries no commits, which would destroy it. The
  park names the paths and leaves the tree untouched for the operator to inspect and reset. That read is the STATUS
  form (`_worktree_status`), not the path list: the list form maps its own failure to "no paths", which is exactly
  what a clean tree reports, so a `git status` that could not run — a corrupt index, a half-removed directory — would
  be recreated over before anyone saw why it failed. An unreadable tree therefore parks
  `discussion_unreadable_worktree` on the same terms, and the post-round write checks are entitled to their
  assumption that this preflight proved the tree empty. It is asked FIRST of the two halves, and a `HEAD` that will
  not resolve is the same answer: `rev-parse` reports failure as the empty string, empty compares unequal to every
  anchor, so the commit question asked on it answers "a round of ours committed here" — and what follows that answer
  is a publication of whatever the branch arrived carrying, under a session that wrote nothing. The anchor is
  therefore compared only on a checkout that could be read, and a read that failed parks rather than being read
  either way.
- **Action**: spawn one agent per tick (`agent_role="decomposer"`, `stage="discussion"`) — the configured
  `DECOMPOSE_AGENT` on the conversation's first round, and on every round after it whatever `discussion_agent` pinned
  then, resuming `discussion_session_id` when there is one — in the
  per-issue `issue-N` worktree on the issue's own branch. A resumed round reuses that checkout as it stands — the tree
  the operator was reading while they composed the reply, already established clean and on the anchor by the hold
  above — and only a directory that has gone is restored at all. Restoring it (for an opening round, or a resumed one
  whose directory vanished) goes through `_ensure_pr_worktree` from the PR head if the issue carries a `pr_number` and
  `_ensure_worktree` from the base branch if it does not, since an issue relabeled here from a PR stage is discussed
  on the branch its PR is open against and a base-branch rebuild would hide the PR's commits from the round and from
  the anchor it writes next. A standing `discussion_publishing_sha` counts as the same thing before there is a
  `pr_number` to read: the marker is written before the push and the number only after the PR is open, so a crash in
  that window leaves a pushed branch and an open PR that nothing pinned names. Lose the worktree and the local ref
  too — a restart, an operator's cleanup, a fresh clone — and a base rebuild would refuse the publication for a tip
  it cannot find and open another round over the top of the PR. So that window asks the remote: a branch that is
  there is restored from, and "no such branch" (the push never landed) falls back to base, spends the marker, and
  lets the conversation carry on.
- **Prompt**: the opening round — and any later one with no `discussion_session_id` to resume — is given
  `_build_discussion_prompt`, which carries the issue body, title, and trust-filtered thread: research the repository
  with read-only commands rather than asking a human for readable facts, explore the design as a tree including one
  unconventional option and the research worth doing, stay at the architecture level rather than implementation
  trivia, treat what the thread has already settled as decided, and close with a NUMBERED list of the questions
  answerable right now — those whose answers do not depend on another open question — each with the agent's own
  recommended answer, and the one write a human's confirmation unlocks: `plans/issue-<number>.md`, holding the
  resolved decisions, the evidence and research behind them, the alternatives and why they lost, the risks, and the
  implementation plan, committed alone with no push and no PR of the agent's own. The path is handed in by the stage
  rather than spelled in the prompt owner, so the promise the agent is given and the diff the publication check
  demands are one string. That thread is read ONCE, and the same snapshot supplies both the text and the ceiling the
  round records as read — a second read is a thread minutes older or newer than the one the agent saw, and the
  disagreement between them is a comment either shown and re-sent next tick or consumed and never shown. The
  orchestrator's own analyses are retained in that text past `ALLOWED_ISSUE_AUTHORS` by their recorded
  `orchestrator_comment_ids` (not by the body marker, which anyone can paste), because a deployment that allowlists
  its humans and not its bot account would otherwise rebuild the conversation with the human's answers by number and
  the numbered questions they answer missing. A round WITH a session id to resume is given
  `_build_discussion_followup_prompt` instead and
  passed `resume_session_id`: it quotes only the trusted replies, since the live session already holds the issue and
  its own prior analysis, and asks for the frontier recomputed — the answers folded in as decided, the branches they
  opened expanded, and a fresh numbered frontier with the settled questions gone from it — under the same
  no-implement contract and the same plan clause, since a resume is usually the round the confirmation lands on. The
  degrade to the full prompt matters because `_run_agent_tracked` starts a *fresh* agent
  when no session id is passed, and a followup handed to that would arrive with no issue body, no design, and no
  frontier to fold an answer into; it carries the plan clause too, because a round with nothing cached can still be
  the round a human confirms on.
- **Records**: `discussion_agent` (the full spec) and `discussion_round_branch` + `discussion_round_sha` (the branch
  the round opened on and the SHA it was at) are WRITTEN before the spawn: a round can end with no disposition at all
  — a mid-run `paused` withholds every one by contract, a crash takes them with it — and the next tick reuses the same
  checkout, so without that anchor a commit the ended round made becomes the new round's own baseline and reads as
  work the branch arrived carrying. `discussion_agent` and `discussion_session_id` are re-read from pinned state on
  every round after the first rather than re-resolved, so a `DECOMPOSE_AGENT` flip between two rounds can retarget
  neither a replayed one nor a resumed one. `discussion_session_id` is staged after the spawn and rides the park's
  write, so it never outlives the analysis it points at — and a round that was NOT resumed writes it either way,
  absence included, since whatever it opened is a new conversation and an issue relabeled out of this stage and back
  arrives unparked still carrying the previous one's id. The consumed watermark is staged after the pre-spawn write
  for the same reason as the session id and lands with that same park: a round that never reaches a disposition is
  replayed, and it has to be replayed against the same replies rather than against an answer already recorded as
  read. Both round shapes stage one, over what their own prompt read — a resume consumes the batch it quotes, an
  opening round the whole trusted thread the full prompt rebuilt, which it has to or the comments it just answered
  would read as unanswered replies on the next tick. No developer or reviewer is ever spawned.
  `discussion_round_open` rides the pre-spawn write beside the anchor and says the round it describes has not
  reported yet; every park clears it, as does the one ending that writes records without parking -- the adoption of a
  pull request the humans have already decided.
  `discussion_base_sha` rides it too: the commit the REMOTE said the base branch
  was at, read through the token before the agent could touch the checkout, and the commit this round's work is
  finally measured against. `refs/remotes/<remote>/<base>` names the same thing but lives in the object store the
  per-issue worktree shares, so an agent could commit code, repoint that ref onto it, and commit the plan — leaving a
  ref-relative diff that shows one file while the branch carries two commits. It is persisted rather than re-read
  because the tick that publishes need not be the tick that ran: a recovery has to measure against the base its round
  was given. What is pinned is an id this clone holds, not merely one the remote named — the base advances between the
  tick's own fetch and the round that opens in it, and a diff naming an absent commit fails, which the path read
  reports as no paths at all: the same answer a branch that changes nothing gives, and enough to refuse a plan written
  exactly as asked. So the object store is asked, one authenticated fetch of the base supplies what it lacks (the tip
  read moments ago is an ancestor of whatever the remote has now), and an id still unreadable after that is recorded as
  no base rather than as a reading nobody could take. The same write settles the session the round runs under, in the
  one direction
  knowable before it does: a resumed round keeps the id it is resuming, and a round resuming nothing drops whatever
  was pinned, since the conversation it opens has no id yet and the previous one's would otherwise be what a recovered
  publication named. An opening round needs no such flag — it leaves the issue unparked, and an
  anchor on an unparked issue already means a round opened and never reported — but a RESUMED round runs with the
  previous park still durable, where that reading is unavailable. Without it, a resumed round that committed the
  confirmed plan and was then paused or cut short would come back to the humans as a violation to reset away.
  A publication writes twice. `discussion_publishing_sha` goes first, on its own, naming the tip it is about to push:
  everything after that write can leave the world changed, so it is what makes a half-finished publication both
  recoverable and attributable, and it carries whatever the round staged beside it since those records describe the
  publication it precedes. The rest go down in one further write, which also retires the marker — the park's, when the
  pull request is still open and the humans are being told where to read the plan, and a write of its own when the
  recovery adopts one they have already decided, since a "review the plan there" message would then be answering a
  verdict with instructions (`terminal` reads those records on the next tick and finishes the issue instead).
  The records are `discussion_plan_path`
  and `pr_number` (the pair the
  hold at the top reads, and the pair that also tells the implementing stage its recorded PR is still a design however
  that PR's head has moved since), `discussion_plan_sha` (the commit that PR carries — read against the PR's head once
  the implementing handoff has retired the path record, so its merged-PR terminal does not take a plan being agreed to
  for work having landed, and asking GitHub is what makes that answer right even for a tick that pushed onto the same PR
  and died before recording it),
  `branch` (so a later checkout is restored from the ref the PR is open against rather than
  the legacy name), and the round anchor moved onto the published tip — the branch's new position is exactly what
  this stage now vouches for, and an anchor left behind would have the implementing relabel guard convict the branch
  of the commit this stage just published.
- **Disposition** (in order): a `paused` / `backlog` label applied mid-run suppresses every disposition below and
  returns without writing anything — the anchor above is what keeps that safe for a round that committed. Otherwise
  `last_discussion_at` is stamped and a non-interrupted run's usage is folded, then whether the commit question can
  be answered at all — both ends of it are `HEAD` reads, and either failing parks `discussion_unreadable_worktree`
  with nothing published, since the empty string a failed `rev-parse` returns compares unequal to the SHA the round
  opened on and would publish the branch's existing commit as this round's — then the commit (a run that
  wrote outranks how it ended, so it is judged before the timeout and before the response), then
  `discussion_timeout`, then `discussion_dirty` — checked before the
  interruption guard and before the response, so a round that wrote outside the one path it may commit parks on what
  it wrote rather than
  being published as a design — then an interrupted run returns silently, then a non-empty response parks
  `discussion_response` and an empty one parks `discussion_silent` with stderr diagnostics. Both write checks are
  measured against the checkout THIS round opened on: a HEAD read before the spawn and compared after (not
  `_has_new_commits`, which is base-relative and would blame the agent for dev commits an issue relabeled here from a
  PR stage already carried), and a tree the preflight above already established was clean.
- **Publication** (what a commit is judged by, from the disposition and from the preflight alike): the branch is read
  once, by four probes, and every one of them has to answer for it to be publishable. The tip is read first and then
  NAMED to the two commit-level probes rather than each re-reading `HEAD`, because it is also the revision the push
  publishes: `HEAD` between two `git` invocations is whatever the branch is on by then, and a verdict carried from one
  commit to another is what would let an unchecked commit go out under a checked one's name. The worktree status
  has to have
  been READ and to be clean — an unreadable one (a corrupt index fails `git status` while a commit-to-commit diff
  still succeeds) is not a clean one, and a push may not rest on a probe that never ran.
  `HEAD` also has to BE the branch: a commit made on a detached head, or on any other ref, is the plan by every
  other reading here, but the push sends a SHA to
  `refs/heads/<branch>` and that branch stays where it was — so the records would name a commit its own ref does not
  carry, the implementing relabel guard would convict the stale tip of being unreviewed work, and a checkout rebuilt
  from that ref would come back without the plan. Nothing here advances a ref an agent left behind, so such a commit
  parks `discussion_plan_invalid` naming which ref HEAD is on. The paths its commits change
  against `discussion_base_sha` — three-dot and `--no-renames`, so a base that moved on is not counted and a file
  renamed onto the plan path does not pass as one, and `--ignore-submodules=none` so a gitlink the commit moved is
  not hidden by a `diff.ignoreSubmodules=all` the agent can write into the worktree's own config (the status read
  spells `--untracked-files=all` for the same reason) — have to be exactly `plans/issue-<number>.md`. Every one of
  those reads asks for `-z`, since git's default output quotes an unusual path and joins a rename onto one line: an
  untracked file named ` -> ` comes back as `?? " -> "`, which is that same line format's rename spelling, and read
  as one it strips to nothing — a dirty tree reporting clean with the plan beside it published. A round with
  no base recorded at all has no reading, and parks rather than publishing paths measured from nothing. And that path
  has to be in HEAD **as a regular file**, because deleting a plan the base branch already carries changes exactly the
  path writing it would, and a deletion published as the agreed design is the "missing plan" case wearing the right
  diff — as is a symlink (whose blob is a target string, so what a reviewer opens is whatever it points at) or a
  gitlink (a commit id for a submodule nobody fetches) left at that path, both of which resolve as objects there while
  carrying no document. Anything
  else parks `discussion_plan_invalid` quoting both readings and the anchor to reset to, and pushes nothing. A
  publishable one is published only under a session that can be named: `discussion_session_id` is pinned before a
  resumed round spawns and recorded from what a fresh one opened, and a round that dropped the previous id and was cut
  short before recording its own leaves none — so does a backend that hands none back. Without it the publication
  parks `discussion_plan_unattributed` with the commit untouched, since a PR body that cannot say which conversation
  produced the plan fails the one thing that body is for. Otherwise it first records `discussion_publishing_sha` — the
  tip about to be published, written durably before
  anything can change the world, so a later tick can tell a commit this stage began publishing from one it merely
  found — then goes through the hardened `_push_branch`, with the lease pinned to a tip the remote was just read at.
  What makes that tip publishable is not which record names it but whether the commit being published CONTAINS it: a
  branch the remote does not have yet is the ordinary first publication, and anything else has to be an ancestor of the
  plan commit — true of a publication being replayed after a crash (the tip is that commit) and of an inherited PR
  branch the plan sits on top of. A lease cannot stand in for that check, since it proves only that the ref has not
  moved since it was read, so a round that reset an inherited branch to base before committing its plan would pass
  every other reading and delete the PR's history. Every other tip parks `discussion_push_failed` naming what is
  there. Pinning is the other half: left to the push's own `ls-remote`
  fallback, the lease would be whatever the remote had become, so a retry would send its older validated commit
  straight over a reviewer's push to that branch. The refusal comes AFTER the marker write for the same reason the
  failed push does — the reply that retries it is carried there by the in-flight record, and a park with no marker has
  no publication to finish, no round open, and a reason that suppresses the repair request as well.
  `_push_branch` is handed that same SHA as the revision to publish
  rather than pushing `HEAD`: the reading and the push are separate git invocations, and a branch that moves between
  them would otherwise put a commit no check ever saw on the PR while the records named the one that passed. A
  failed push parks `discussion_push_failed` with the
  commit left intact, since resetting it would discard the agreed design -- and it is that same write, the one carrying
  the marker, that first replaces a standing `discussion_push_failed` with `discussion_publishing`, because it also
  consumes the reply a retry was asked for by. Before any of that, the publication asks GitHub whether the commit
  it is about to push has already MERGED on a pull request: a tick that opened the plan PR and died
  before recording its number leaves nothing pinned pointing at it, and a human merging that PR closes it and (with
  auto-delete on) takes the head branch with it — so an open-state lookup finds nothing, the push recreates a branch
  GitHub deleted, and the open that follows asks for a second PR with no commits between its two refs. Searched by
  the publication's own commit across every state — and by the commits a pull request CARRIES rather than the head it
  is on, since a human pushing to that branch, or merging the base into it, moves the head inside the same window
  while the published commit stays in the PR — that PR is found and its number simply recorded, with no push and
  no open. That commit list is a request to GitHub, and one it can decline -- as is the enumeration the candidates
  come from, page by page. Either failure answers `PR_LOOKUP_UNREADABLE` rather than "no pull request carries this",
  because the amended-and-squash-merged PR this lookup exists to find has a moved head and a deleted branch, so the
  commit list is the only place it is still visible, and a walk that never reached it says only that nobody asked.
  On that answer the publication stops where it stands — nothing pushed, nothing opened, nothing said on
  the thread — after writing the marker, which is both what the next tick retries from and what persists the round's
  own staged records (a session id a fresh round holds only in memory would otherwise be lost, and the retry would
  refuse the plan as unattributable). The retry is the next poll; a marker already standing on this tip under
  `discussion_publishing` is not rewritten, so a GitHub outage costs one read a tick and no pinned-comment edits.
  An OPEN pull request whose head a human moved past this commit while still carrying it gets the same
  ending, and for the sharper reason: the branch already has what would have been pushed, so the lease is right to
  refuse the older SHA — but refusing alone parks `discussion_push_failed` with no `pr_number`, leaving a plan that is
  published and reviewable and unreachable from the issue that produced it. Both readings are required to say so: the
  remote head has to contain the commit (a tip that merely differs is somebody else's branch, and the divergence park
  is right about it), and a pull request has to carry it. Containment is a local question about an id that came off
  the remote, so the branch is fetched first unless that head is already in the store: their commit was made after
  this checkout was, and a retained worktree asked about an id it cannot resolve answers the same "no" a real
  divergence gives — which would park `discussion_push_failed` on every retry with `pr_number` never written. The
  lease below reads the same way for the same reason, and a tip nothing can fetch is refused there rather than adopted
  here on a reading that was never taken.
  A PR closed WITHOUT merging is the same answer to the PUSH, and for a sharper reason than the merge: pushing at one
  opens a REPLACEMENT proposing the very design a human just turned down, and the issue is then held on that
  replacement with their rejection left with nothing pointing at it. So the close is recorded like the merge, and
  `terminal` reads that record on the next tick to finish the issue `rejected`. The reading taken where the branch has
  MOVED off the marker's commit takes the same three answers but holds the close back, because there the caller's
  other answer is an operator's reset — the remedy the stale-publication park asks for — and answering that park can
  mean closing the stray pull request as well as resetting the branch, so a close read as a verdict on the spot would
  finish the issue on debris somebody was tidying. It is taken up once the reset has been ruled out (the branch is not
  back at the anchor, or the remote still carries the commit), and then it IS the verdict: without that, a reviewer
  who amends the plan and then closes it leaves an issue parked `discussion_stale_publication` for good — no
  `pr_number`, no terminal label, no event, and no branch anything will reap. Neither DECIDED ending is parked with
  the "review the plan there" message an open one earns: the humans have already decided, and the records go down on
  their own for the terminal to speak from. An adopted PR is made to name the publishing session before it is
  recorded, through the same check the
  reuse below runs: the lookup proves branch, base and commit and nothing about who opened it, so a hand-opened pull
  request on the plan's branch that a human merged or wrote on top of would otherwise be recorded as the artifact and
  described by a body about something else. And nothing is adopted at all without a session to name — the same
  `discussion_plan_unattributed` refusal the push earns, asked here too because this path reaches a pull request
  BEFORE the push does: a round cut short before recording the conversation it opened would otherwise have its plan
  recorded as published and the PR body rewritten to say `session None`. That refusal is written once, since the
  adoption is reached ahead of the turn-taking gate by a marker no reply has spent.
  Otherwise the PR is found-or-opened on the
  branch — a tick that died between `open_pr` and the pinned write re-derives the same artifact and reuses its own PR
  rather than 422-ing. What that lookup returns is only known to be open on the branch, though — an issue can arrive
  here carrying a PR, an operator can open one by hand — so a reused PR whose body does not already name the
  publishing session has that body rewritten to the plan's; one that names it is left as it stands, annotations and
  all. Its body names the `discussion_agent` backend and `discussion_session_id` that wrote the plan
  and carries no closing keyword — what a merge meant is this stage's own terminal to record, and the keyword outlives
  the label, so on a PR handed to a developer by a relabel it would let a merge of the plan alone close the issue as
  finished work. The body says what deciding it does instead: merging finishes the issue `done`, closing it unmerged
  finishes it `rejected`, and having the plan built is a relabel made before either. Its title comes from the plan
  commit's own subject, and `pr_opened` is emitted with `stage="discussion"` only on the branch that really opened
  one. The label is untouched throughout: no `validating`, no `documenting`, no `in_review`.
- **Output**: the agent's response quoted in an issue comment pinging `HITL_MENTIONS`, or the matching park comment;
  `awaiting_human=True` with the durable `park_reason` re-set after `_park_awaiting_human` clears it. Or, on the
  terminal arcs above, the usage receipt plus the flip to `done` / `rejected` — and on the holds, nothing at all. That
  helper also stamps `last_action_comment_id` at the newest comment on the thread, and this stage's park funnel puts
  back the value it was entered with: the ceiling this round's prompt was BUILT from, not the thread as it stands
  minutes of agent run later. A comment posted in that window — a human's second thought, or an outsider's the
  allowlist may later admit — is never in front of the prompt, and this stage reads no comment twice, so recording it
  as consumed would mean it is answered never. Leaving the mark below the stage's own posted analysis is safe because
  `_new_trusted_replies` drops the orchestrator's own comments by recorded id and by the `_ORCH_COMMENT_MARKER` in
  their body (never by author login, which a PAT shared with a human's account would turn against that human's real
  replies), so a conversation cannot resume on itself. Every round after the opening one ends the same way until the
  humans confirm the design; what that confirmation buys is a plan PR, not a transition, so the stage decides no
  transition of its own until that PR is decided — and then it decides only the terminal the humans wrote on it.
  Everywhere else, leaving this stage is a human relabel. The `issue-N` worktree is PRESERVED on every ROUND exit —
  the tree the discussion read is the tree its next round and the operator both look at — so the only thing that ever
  tears one down is the plan-PR terminal above, and only once that pull request is gone; the per-tick base sync stands
  down on the `discussion` label (alongside `question`, in `_issue_skips_base_sync`) so `<remote>/<base>` is never
  rebased over that state. That same gate also stands down on an unconsumed `discussion_*` / `question_*` park
  whatever the current label is, because the refresh runs before the handlers: an operator's relabel to
  `workflow:implementing` removes the label a full tick before the guard below rules on the branch, and a rebase in
  that gap would move the tip off the recorded anchor and convict a branch nobody touched. It stands down on the two
  in-flight records as well — `discussion_round_open` and `discussion_publishing_sha`, whatever `awaiting_human` says
  — because both are written BEFORE the thing they describe: a tick that died after the agent committed leaves one
  standing with no park at all, and the commit it died holding on the branch. Clearing the park does not lift the
  freeze either: it becomes `read_only_baseline_sha`, and the branch stays put until that is spent on published work.
- **Exit**: either terminal above — the plan-PR verdict, or the pre-PR close — to `done` or `rejected`, the two edges
  `ALLOWED_TRANSITIONS` grants the state; or a human relabel: to either of those same two by hand, or, through the
  GitHub UI, to `workflow:implementing` once the thread settles on building it. That last one is not a
  graph edge, so it arrives as an operator relabel and is screened by the read-only guard in
  `workflow/stages/implementing/read_only_relabel.py`: a `discussion_*` park whose worktree is dirty, whose recorded
  branch no longer sits at the SHA the round anchored on, or whose CHECKOUT is on a commit no record vouches for,
  re-parks as `discussion_unsafe_relabel` rather than
  letting the recovered-worktree shortcut push that work as a dev implementation; a clean one clears the park and the
  dev spawns fresh. The checkout is read for its own `HEAD` because a commit does not have to be on a ref anybody here
  names: an agent that committed while detached leaves every branch exactly where the round opened it and the plan in
  the tree, which is what the creators keep and what the shortcut pushes. An unreadable `HEAD` counts against it for
  the same reason a dirty tree does, and so does a `git status` that failed: the list form of that read maps its own
  failure to "no paths", which is what a clean tree reports, and accepting on it would let worktree creation
  force-remove the very tree an operator was parked to inspect. Proving a checkout carries nothing cannot rest on a
  probe that did not answer. A park with no recorded tip to match (the question stage's) is certified the older way
  instead, by the checkout not being ahead of base. The screen answers for the two in-flight records on the same
  terms, and with no park to find them by: an opening round leaves the issue unparked, so a tick that died after the
  agent
  committed — or after its plan PR was opened — would otherwise arrive here looking like an ordinary relabel, and one
  push later the plan would be a dev PR closing the issue. A standing publication marker is refused on the record
  alone, without waiting for a local reading to convict: that marker is written before the push, so the branch may be
  on the remote with a PR open against it, and on a fresh clone every local probe reads clean at once — no checkout,
  nothing ahead of base, no tip to compare. Handed over there, the developer builds from base and the push takes a
  lease read live off the remote: the published plan is overwritten, its PR adopted, and its body rewritten to close
  the issue. So the refusal names which half died and leads with the way out that finishes it — relabel back to
  `discussion`, whose own recovery restores the checkout from the PR head, adopts that PR, and records it — rather
  than a reset that would destroy the plan. Those two records are read AHEAD of the terminals rather than behind
  them, which is the one place the guard's position in the preflight is not enough: the `pr_number` such an issue
  carries is whatever it arrived with — a previous cycle's implementation, or an earlier discussion's plan PR — and
  merged, it would close the issue as `done`, delete the branch the plan is sitting on, and leave the marker standing
  on an issue nothing comes back for. A round that died before committing anything is handed over like any clean
  park, and its records are retired with it, after which the terminals run against a state that no longer claims an
  unfinished conversation. A published plan passes that screen because publication moved the anchor
  onto the tip it pushed, so the branch carrying the plan commit is exactly what the record certifies — and when that
  plan PR has MERGED the handoff anchors the checkout on the base instead of leaving it there, since the design landed
  along with everything else that has since, and the baseline the handoff records would otherwise freeze the branch
  behind the one it is being built for. The anchor is
  checked whatever the branch's relation to base now is — a reset all the way to base
  is not ahead of base, but on a PR-backed issue it discarded the very commits the round was certified against — while
  a recorded ref that no longer exists is not a violation, since nothing local is left to attribute and the checkout is
  rebuilt from the PR head. A plan PR that has MERGED takes the older ahead-of-base question back, and has to: its own
  handoff moves the branch to the base and records where it landed in the write AFTER the move, so a tick that dies in
  between leaves a branch on a tip no record names — matched exactly, the base itself reads as unreviewed work and the
  refusal tells the operator to reset backwards off the commit the merge produced. A branch carrying nothing beyond
  base carries nothing of anybody's, and the move is idempotent, so the next tick simply makes it again.
  The refusal names the anchor as the reset target, so an issue whose branch legitimately
  carries a PR's commits has a way back that does not discard them, and the clear hands that same tip on as
  `read_only_baseline_sha` so the shortcut does not then mistake those inherited commits for a dev run to finish. The
  clear also drops `discussion_plan_path`: that record exists to stop this stage acting while the plan is with the
  humans, and the relabel IS them deciding — left behind, it would hold the stage inert for good if the issue ever
  came back. Dropping it is what hands the plan question over to `discussion_plan_sha`, and the order is the point:
  the guard runs behind the merged-PR question above — except on an issue whose in-flight records hoisted it, where
  the write happens first and the same PR is then read against the commit it just recorded — so every tick that has
  not reached this write still reads the recorded PR as a design however its head has moved, and only the ticks after
  it can read a moved head as this stage's own push. Which is why the head that PR is on NOW is read before the guard
  rules and recorded in the path record's place. Between the publication and the relabel the humans have the design
  on a PR and can move its head —
  a correction to the Markdown, the base merged in to make it mergeable — and the commit publication recorded would
  then be a stale answer: the tick after the handoff would read their own edit as an implementation and close the issue
  as `done` with no developer having run. The same read anchors the checkout, through
  `worktrees/creation._anchor_pr_worktree`: one authenticated fetch of the branch, a re-read of what the remote says
  that branch is on, and a `reset --hard` onto that head
  (an `update-ref` when the worktree is gone), both under the hardened envelope like every other reset here — the
  checkout is agent-writable and a linked worktree can write the common repo, so an `fsmonitor` on the reset's index
  refresh or a `reference-transaction` hook on the ref update would otherwise run with this process's environment. The
  reset also NAMES its tree with `--work-tree`, which the envelope cannot do for it: `core.worktree` in the
  per-worktree config redirects every path operation and no `-c` override beats it, so a reset left to discovery
  reports success and moves the ref while writing the reviewed commit's files into whatever directory it was pointed
  at — the issue's checkout stays on the plan it had, the recorded baseline names a tip the tree is not on, and
  somebody else's files are overwritten on the way past. The
  developer then builds on the design its reviewers approved rather
  than on a tip whose push would take their amendment back out. The re-read is what keeps that true across the gap
  between the two: the head was read off GitHub a moment earlier, and a human pushing to that branch in between
  leaves the fetch bringing THEIR commit while the one just read still resolves underneath it as an ancestor — so
  "the object is here" would anchor on a head the PR has moved past, and the push that followed would read their
  commit off the remote as its own lease and overwrite it. Only a remote still on that head anchors; anything else
  holds the handoff for a tick that reads the pull request again. `read_only_baseline_sha` then records where the branch
  really ended up — the reviewed head when the move landed, and `<remote>/<base>` when the remote confirms that branch
  is gone and what it carried has landed there, which is a base this tick FETCHED or no answer at all: a cached
  remote-tracking ref resolves perfectly well after a failed fetch and names the base from before the merge, the one
  base a plan that has just landed is not in — since a
  baseline naming any other commit would have the spawn path read the difference as an interrupted dev run and push it
  with no agent. The base is reached only when the handoff names NO head at all, which is how it says the design
  landed: a named head whose branch the remote no longer has is a pull request somebody closed and cleaned up after,
  so what it carried went with the branch and anchoring at base would retire the plan records and start the developer
  from a tree the plan was never in. A move that established NEITHER holds the handoff: the tick ends having written
  nothing, plan record intact, because accepting it would put the developer behind the reviewers and the ordinary
  push that follows reads
  their head off the remote as its own lease. A plan PR that could not be READ ends the tick the same way, because
  every one of those decisions is durable and none of them may rest on a stale reading. Reading it before the guard
  is also what makes the move crash-safe: the branch is anchored ahead of the write that records it, and a tick that
  dies in between leaves a tip the next one recognizes as the reviewed head rather than convicting the branch of it.
  The plan's own `pr_number` and `branch` stay, so the dev continues on the branch the plan PR is open
  against and its implementation lands on that same PR.
  **Removing the label is not an exit.** The stage records `discussion_agent` / `discussion_round_sha` in the
  issue's pinned comment, and `_handle_pickup` starts an unlabeled issue on a fresh `PinnedState`, so the pickup would
  write a *second* pinned comment while `read_pinned_state` keeps returning the first — the discussion's. Closing the
  issue IS a terminal signal, and `discussion` is in `CLOSED_SWEEP_LABELS` so the closed issue keeps being polled
  until that signal is drained: with no plan PR the close finalizes to `rejected`, and with one it waits for the
  pull request (see the terminal bullet at the top of the handler above).

## State transition (label lifecycle)

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
