# Agent roles and sessions

The workflow has three agent roles, each spawned by a different set of stage handlers. Roles are independent: each can
use `codex` or `claude` and each carries its own optional CLI args, parsed from its own env var by the grammar in
[`command-specs.md`](command-specs.md).

Stage and label names are spelled apart here as they are in
[`../state-machine/labels-and-state.md#workflow-labels`][workflow-labels]: a bare tag names the **stage** — the
handler, the subpackage under `orchestrator/workflow/stages/` holding it, and the identifier a session's analytics row
is attributed to — while `workflow:<tag>` is the **wire label** the GitHub issue carries. `in_review`, `question`,
`discussion`, and the `done` / `rejected` terminals were never namespaced, so those read the same on both sides.

## The three roles

- **Decomposer** (`DECOMPOSE_AGENT`, default `claude`) — spawned by `_handle_decomposing` (and its `awaiting_human`
  resume); `_handle_question` (and its `awaiting_human` resume), `_handle_discussion`, and the late adjudication an
  oversized committed candidate earns all reuse the same backend. Session: locked per issue after first spawn
  (decomposing → `decomposer_agent`; question → `question_agent`; discussion → `discussion_agent`; late adjudication
  → `late_agent`, each a separate pin).
- **Implementer / dev** (`DEV_AGENT`, default `claude`) — spawned by `_handle_implementing`, `_handle_documenting`,
  `_handle_validating` (awaiting-human resume; the `CHANGES_REQUESTED` dev fix is dispatched here but relabels to
  `workflow:fixing` BEFORE the spawn and records `stage="fixing"` analytics, so the dev-fix subphase reads as fixing
  rather than validating on both the wire label and the analytics row), `_handle_fixing` (in_review-route PR-feedback
  resume + validating-route awaiting-human rescan), `_handle_resolving_conflict` (conflict resume + awaiting-human
  resume). Session: locked per issue after first spawn.
- **Reviewer** (`REVIEW_AGENT`, default `codex`) — spawned by `_handle_validating` (fresh every round). Session: fresh
  per round; current config always wins.

The defaults (`claude` decomposes, `claude` implements, `codex` reviews) use both backends; both CLIs need to be
authenticated on the host before the orchestrator starts.

## Where a role is spawned from

Every stage handler lives on responsibility-named owners under `orchestrator/workflow/stages/`, one subpackage per
stage — `decomposition` (the `decomposing` / `ready` / `blocked` / `umbrella` handlers), `implementing`, `documenting`,
`validating`, `in_review`, `fixing`, `conflicts`, `question`, and `discussion` — which own entry checks, session
execution, drift handling, persistence, and terminal routing. Nothing answers for a stage beside those owners, so each
handler is reached on the one module that holds it, the dispatcher and the same-tick pickup start that module
directly, and a patch meant to intercept a handler has to land on it. `orchestrator.workflow` publishes six names and
nothing else — `WorkflowLabel`, `ControlLabel`, `guard_transition`, `is_allowed_transition`, `IllegalTransition`, and
`tick`.

Everything a stage borrows is named the same way. A cross-stage call names the owner it borrows from rather than a
facade; the worktree, HEAD, fetch, push, and PR-title helpers live on owners under `orchestrator/git/`; and the
tracked spawn every role goes through dispatches on `orchestrator/agents/runner.py`. Which owner defines which helper
and which stage borrows it is the module map in
[`../architecture/platform-modules.md`](../architecture/platform-modules.md) for the git and agent owners and
[`../architecture/workflow-modules.md`](../architecture/workflow-modules.md) for the stage tree; the
per-stage behavior is in
[`../state-machine.md#stage-handlers`](../state-machine.md#stage-handlers). What follows is the role-specific glue.

## Session lifecycles

- **Dev session reuse.** The implementer session is spawned once in `_handle_implementing` and then resumed by
  `_handle_documenting`, `_handle_validating`, `_handle_fixing`, and `_handle_resolving_conflict` whenever they need
  the dev to make a change. The locked `(backend, args)` spec is re-parsed on every resume from pinned `dev_agent` so
  a config flip mid-flight cannot retarget the session. `_resume_dev_with_text` on
  `workflow/stages/implementing/resume.py` is the one module every one of those resumes goes through; it declares the
  call signature its callers were written against, then binds those arguments into a typed request/context before
  executing the resume.
- **Reviewer freshness.** `_handle_validating` spawns a fresh reviewer subprocess every round with no resume, so
  `REVIEW_AGENT` changes take effect on the next validating tick. The current value is recorded in `review_agent` for
  traceability only.
- **Decomposer reuse.** `_handle_decomposing` spawns the decomposer once and resumes it on every awaiting-human reply.
  The `question` stage reads `DECOMPOSE_AGENT` only as the *fallback* on the first-ever question spawn, then pins what
  it ran under to `question_agent` (a separate key) so a multi-turn Q&A keeps its own lock independent of any
  decomposing session on the same issue. The `discussion` stage borrows the same role on the same terms and pins to
  `discussion_agent` + `discussion_session_id`, a third independent pair, and resumes that session on every human
  reply — so the pin protects both which backend and args a later round runs under and the conversation it continues,
  since a session id is only meaningful to the CLI that issued it.
- **Late adjudication.** An oversized committed candidate is adjudicated by the same role under the same
  `workflow:decomposing` label, by `_adjudicate_late_generation` on
  `workflow/stages/decomposition/late_coordinator.py`. It is an additive mode rather than a stage: an analytics row
  reads `agent_role=decomposer` and `stage=decomposing` exactly as the initial decomposer's does, the spawn spends
  the same per-issue retry budget and folds its usage into the same counters, and the initial decomposer's prompt,
  fence, and missing-manifest handling are untouched. What it does not share is the pin or the conversation:
  `late_agent` + `late_session_id` are a fourth independent pair, seeded from `DECOMPOSE_AGENT` on an issue's first
  late run and locked from then on. Unlike the three conversation pins, this one does not resume anything yet: every
  late run is a fresh conversation against the frozen candidate, and the session id is pinned — at the two exits that
  persist, a timeout and a completed reply — so the resume the late lifecycle will land can find the CLI that issued
  it. The run happens in the issue's OWN worktree rather than a scratch checkout of the base branch, because the diff
  it is asked about is between two commits nothing has pushed. The coordinator is callable and complete, and **nothing
  calls it**: `_adjudicate_late_generation` has no caller in the tree, so no live issue reaches it. Wiring it into the
  clean-committed pre-publication seam — the point at which a candidate is measured and found oversized — is a
  separate change.

What a resume re-parses, and why the pin is the full spec rather than the backend alone, is in
[`command-specs.md#in-flight-session-lock`](command-specs.md#in-flight-session-lock). The two conversation stages'
prompts and round contracts are in [`conversations.md`](conversations.md).

## What a late adjudication is asked, and what it may answer

The late prompt (`late_prompt.py`) carries the original issue and its trust-filtered thread, the declared scope this
generation owns, the two frozen commits with the `git diff <base>...<candidate>` that reads them, the measured additions
against the configured ceiling, the lineage, and the fact that committed work already exists and is not to be rewritten.
Three dots, not two: that is the prospective pull-request range the measurement was taken over
(`git/measurement/additions.py`), and on a diverged history the two-dot range would put the agent on changes nobody
measured — deciding a split over work this candidate does not add. The child cap, the lineage bound, and the category
vocabulary are read back off the owners that enforce them, so a bound the agent is told cannot drift from the bound it
is judged against.

The reply ends in exactly one fenced `orchestrator-late-manifest` block — a different fence from the initial
`orchestrator-manifest`, read by `late_reply.py` — declaring one of three outcomes:

- `single` — the committed work is one coherent change despite its size. A diff dominated by legitimate generated or
  data artifacts is the named false positive and gets this verdict with `"category": "generated_artifacts"`.
- `split` — a child manifest that partitions the declared scope completely, held to the same rules the initial mode
  uses: the child cap, each child's shape, and the acyclicity of the graph they declare.
- `question` — a categorized question for a human, which is also where artifacts that look like they should NOT have
  been committed go. The category is mapped onto the closed vocabulary, so an agent's own spelling records as
  `unknown` rather than widening the field.

Unlike the initial mode, prose alone is not an outcome: a reply with no block, or with more than one, parks for a
human rather than being read as the agent asking a question, because a late question has its own structured decision
to travel in. Automatic splitting stops at `MAX_LINEAGE_DEPTH` (3), and a split proposed at the bound is recorded as
the categorized question the workflow actually owes a human (`lineage_bound`) rather than acted on — so the next tick
asks the human instead of paying for the same forbidden split again.

A completed run is recorded whole so a crashed tick does not pay for a second one — a second run is not free, and it
is free to decide differently. What "whole" means is per verdict: a `single` needs nothing beside itself, a `question`
carries its category and the sentence it asked, and a `split` carries the ordered child manifest that *is* its
decision. Whether it fits is measured on the whole comment the write would produce — the preserved plan-PR body and
every other stage's keys included — because a result small on its own can still be the one that pushes the comment
past what GitHub accepts, and learning that from the failed write means the agent has already been paid for. An
outcome past that budget is refused entire rather than shortened, and the issue parks for a human; an incomplete one
read back later is not an answer at all and the adjudicator runs again. The record goes
out before the question it announces does, so the narrow crash window between them costs a repeated comment rather
than a repeated agent run, and the next tick posts the recorded question instead of earning it again. Which keys carry
that, why a recorded answer names its cycle as well as its generation and commit, and why the pre-spawn write leaves
the retry counter alone are in [`../state-machine/labels-and-state.md#the-late-run`][late-run].

The read-only promise the prompt makes is proved rather than trusted. The late adjudicator runs in the developer's own
worktree — the frozen candidate is not on any remote yet — and the CLI it runs under can write there whatever the
prompt says, so before the reply is read at all the candidate is proved unmoved (HEAD still IS the frozen commit, not
merely contains it) and the tree proved clean. An agent that committed over the evidence or left changes beside it has
contaminated the one artifact every later step acts on: the issue parks for a human and the verdict is not used. That
check sits ahead of the interruption refusal for the same reason the initial decomposer's dirty check does — a run the
shutdown sweep killed can have written before it died.

None of it starts on a generation that cannot be acted on. The prompt names both frozen commits and tells the agent
to diff between them, the hold marks a pull request in the generation's name, and the verdict is reported under its
identities — so the identities and both SHAs are proved before the plan PR is touched or an agent is started. A
candidate whose base was never recorded would otherwise produce a `git diff` against nothing and a record two sinks
refuse afterwards, with the run already paid for; instead the issue parks and says which field is missing.

Before any of that runs, a reusable open plan PR is put under a generation-marked hold (`late_hold.py`). *Plan* is
checked, not assumed: `pr_number` names whichever pull request the issue currently records, and that is an
implementation as often as a plan, so the hold reads the discussion provenance through the implementing stage's own
`_recorded_pr_is_the_plan` — about the one snapshot it read, since past the handoff a plan is told from an
implementation by the commit its head is on and two reads would leave a window for a human push. That snapshot is read
whole where the fetch is guarded, because a PyGithub pull request is lazy and the request that can fail is the first
attribute access rather than the fetch itself; anything unreadable parks rather than escaping. An implementation PR is
left alone — rewriting an implementation PR's description would replace a human's account of a change under review with
a notice about a different one. A provenance that could not be established is not the same answer and fails closed. Past
that gate, the original body is written to pinned state BEFORE the pull request is edited, so a crash can lose the edit
— which the next tick re-applies, since every branch is idempotent — but never the only copy of the description. A write
that *refuses* is the same rule read the other way: with no preserved copy there is no hold to take, so nothing is
edited and the issue parks. How long a description may be preserved is decided the same way, before it is replaced: the
whole prospective comment is rendered with the run's record already in it — the spec this issue is locked to, an
operator's command line bounded by nothing here, included — because the write that starts the run has no safe failure of
its own. A body too long to hold beside that is refused while nothing has been touched. A hold that cannot be reconciled
parks WITHOUT spawning — once, since the retry that changes nothing repeats no notice — and the park it leaves is
retired the moment a later attempt reconciles it — a stale `awaiting_human` would otherwise silence a question, whether
the retry recorded it or a crashed run had already recorded one whose announcement never landed. A pull request a human
merged or closed meanwhile is simply not held, and nothing re-anchors the frozen candidate SHA off it: the recorded
commit is the evidence every later step acts on, never the pull request's current head. What the run itself records —
role, locked spec, session, cycle, source commit, generation, and the whole of what the verdict decided — is in
[`../state-machine/labels-and-state.md#the-late-run`][late-run].

## Local verify gate (not an agent)

After the reviewer emits `VERDICT: APPROVED`, `_handle_validating` runs the configured `VERIFY_COMMANDS` directly in
the per-issue worktree — these are plain shell commands, not an agent role, so no `*_AGENT` env var applies. The gate
runs before the approval comment, the squash, the watermark seeding, and the `workflow:documenting` (final-docs) label
flip. A clean run advances the issue; any failure parks on `workflow:validating` with a typed `park_reason`
(`verify_failed` / `verify_timeout` / `verify_dirty` / `verify_head_changed`). See
[`../configuration.md#local-verification-gate`](../configuration.md#local-verification-gate) for the env-var
reference.

[workflow-labels]: ../state-machine/labels-and-state.md#workflow-labels
[late-run]: ../state-machine/labels-and-state.md#the-late-run
