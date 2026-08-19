# Workflow labels, per-tick flow, and pinned state

This page is the authoritative spelling of the state machine's public contract: the label set and how a wire label is
spelled apart from the stage under it, the migration off the pre-namespace spellings, what one tick reads and writes
per issue, and every pinned-state key a handler depends on. Live GitHub issues carry these strings, so a rename here
is a migration rather than a refactor.

The handlers that act on them are in [`delivery-stages.md`](delivery-stages.md) and
[`conversation-stages.md`](conversation-stages.md); the compact label-lifecycle reference is in
[`lifecycle.md`](lifecycle.md). For the summaries these sections are reached from, see
[`../state-machine.md`](../state-machine.md).

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
([configuration/operations.md](../configuration/operations.md#continuous-integration)) share the prefix and nothing in
the tree reads them, so they route nowhere and a label write leaves them in place exactly as it leaves `bug` or
`enhancement`. Applying one as a workflow label is what the typo guard below rejects.

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
  issue back up from durable state; there is no un-pause command. This is distinct from `/orchestrator continue`
  ([`_handle_fixing`](delivery-stages.md#_handle_fixing-label-workflowfixing)'s `_handle_continue_command`, plus
  the shared implementing / documenting handling), which retries
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

The label vocabulary is defined once in [`orchestrator/workflow/state.py`](../../orchestrator/workflow/state.py), which
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
`MAX_PARALLEL_ISSUES_PER_REPO`. One repo's pass is owned by `workflow/engine/tick.py`, which `workflow.tick` is the
entry point into; the multi-repo dispatch, the scheduler lifecycle, and the fixed order that pass runs its four steps
in are in
[`architecture.md#per-tick-flow-workflowtick`](../architecture.md#per-tick-flow-workflowtick). What follows is what
each step reads and writes per issue.

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

The `question` and `discussion` labels skip both paths unconditionally (`_issue_skips_base_sync`) — the question
handler tears down its own worktree, the discussion stage keeps its checkout across every round exit, and merging
base into either would accrete commits on a branch no developer owns or rewrite the state an unsafe park left for an
operator to read. On the discussion side it is also what protects the publication: the plan is pushed at the SHA the
stage's own check read, so a rebase between that reading and the push — or after it, onto the tip the plan PR is open
against — would move the branch off the commit anything vouches for.

The skip outlives the label. An unconsumed `question_*` / `discussion_*` park is honored whatever the issue is
labeled now, because an operator's relabel to `workflow:implementing` takes the label off a full tick before the
read-only guard rules on the branch, and a rebase in that gap would move the tip off the SHA the guard measures and
convict a branch nobody touched. So are the three records that freeze a branch on their own: the two a discussion
tick writes BEFORE the thing they describe (`discussion_round_open` and `discussion_publishing_sha`, which a tick
that died mid-round leaves standing with no park at all, and with the commit it died holding on the branch), and the
`read_only_baseline_sha` the guard writes in place of a park it clears, which stands until the dev run commits.

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
- Closed `question` — a human closing the issue is the terminal signal
  [`_handle_question`](conversation-stages.md#_handle_question-label-question) consumes to finalize to
  `done`.
- Closed `discussion` — two different endings, and the label is swept for a longer window than the rest. With no plan
  PR published, the close is the whole signal and
  [`_handle_discussion`](conversation-stages.md#_handle_discussion-label-discussion) finalizes to `rejected`,
  which is what takes
  the issue back out of the sweep. WITH one, the close says nothing about the design: the stage holds its terminal
  and keeps the `discussion` label precisely so this sweep goes on yielding the issue until the plan PR itself
  merges (`done`) or closes unmerged (`rejected`). Nothing else revisits a closed issue, so a terminal flip while
  that PR is open would strand the worktree and the branches the plan lives on.

Pre-PR labels (`workflow:decomposing` / `workflow:blocked` / `workflow:umbrella` / `workflow:ready`) are not swept
closed — a closed issue at those stages is a hard human stop until an operator relabels.

The closed-issue sweep issues one closed-issue query per sweep label the repository actually carries, per repo, every
tick — a fixed request cost that drives GitHub primary-rate-limit exhaustion on multi-repo hosts. A pre-namespace
spelling the rename already retired costs only its `GET …/labels/<name>` miss, and even that is thrown away for
twenty sweeps before being asked again rather than re-requested every pass. The spellings one sweep confirms absent
are reported together, in a single repo-qualified INFO line naming them, so a migrated multi-repo host does not open
with a burst of near-identical lines that reads like broken configuration; a sweep whose legacy lookups all came from
the throttle confirms nothing and logs nothing, so that line recurs when the window expires rather than every pass. A
missing namespaced label, or a lookup that failed any other way — a 403 is no answer about whether the label exists —
stays a per-label warning.
`CLOSED_ISSUE_SWEEP_EVERY_N_TICKS` (default `1`) batches the whole sweep to once every N ticks; the open-issue poll is
unaffected, so the only effect of `N>1` is that an externally-merged/closed issue can take up to `N-1` extra ticks to
finalize. See [configuration.md#github-rate-limits](../configuration.md#github-rate-limits).

`done` and `rejected` are terminal no-ops. Every handler receives the active `RepoSpec`, so `git worktree add`,
`git fetch <spec.remote_name> <spec.base_branch>`, push-token resolution, and PR-base selection all flow from the spec.

### Pinned state

Per-issue durable state lives in a single **pinned comment** on the issue (`<!--orchestrator-state {...json...}-->`).
The schema is defined by `read_pinned_state` / `write_pinned_state` (see `github.pinned_state.PINNED_STATE_MARKER` /
`PINNED_STATE_RE`). `read_pinned_state` trusts a comment as state only when it is authored by the account backing the
orchestrator's token AND its whole body is the marker, so neither a third party's forged marker nor an ordinary
bot-authored comment that embeds the marker in prose can preempt state (see
[pinned-state authentication](../security.md#pinned-state-authentication)). The keys that matter for the state
machine fall into a few groups:

- **Agent identity.** `dev_agent` + `dev_session_id` (locked dev session — see
  [in-flight session lock](../workflow/command-specs.md#in-flight-session-lock)),
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
  operator command replays when retrying a session-failure park (see
  [`_handle_fixing`](delivery-stages.md#_handle_fixing-label-workflowfixing)); the anchor is cleared on a
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
