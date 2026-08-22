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
  late run and locked from then on. One late run in three resumes it: a human answering the categorized question the
  adjudicator asked is answering the agent that ASKED it, so that run continues the pinned session rather than opening
  a conversation which would have to be told the question before it could be told the answer. Every other late run is
  fresh — a first adjudication has none to continue, and a candidate the developer revised is a different question, so
  a session opened against the commit it replaced would hand the agent a transcript about work nobody is adjudicating.
  Both halves are proved rather than assumed: the caller says it is carrying an answer, and the record says its
  session really ran against this cycle, generation, and commit. The id is pinned at the two exits that persist, a
  timeout and a completed reply. The run happens in the issue's OWN worktree rather than a scratch checkout of the
  base branch, because the diff
  it is asked about is between two commits nothing has pushed. The coordinator is callable and complete, and **almost
  nothing calls it**: `_adjudicate_late_generation` has no caller in the tree, so no live issue reaches it, and the
  one wired seam is the refusal below — a live generation stops `DECOMPOSE=off` from routing an unadjudicated
  candidate to implementation. Wiring the adjudication itself into the clean-committed pre-publication seam — the
  point at which a candidate is measured and found oversized — is a separate change.
- **Late developer revision.** Guidance a human writes about an oversized candidate is not a decomposition question,
  so it does not go to the late adjudicator: the work itself has to change, and the session that wrote it is resumed
  against the guidance in the worktree the candidate already lives in
  (`workflow/stages/decomposition/late_revision.py`). It runs under `agent_role=developer` and `stage=decomposing`,
  because that is what it is and where it happened — the issue never leaves `workflow:decomposing`. The prompt quotes
  the issue's CURRENT title and body beside the guidance, because a resume is exactly the case that cannot see them:
  the replayed transcript holds the issue as it read when the work started, and the commonest reason to be here is
  that a human edited it since. The budgets are
  the ones that already exist: the resume budget and the session rotation behind it belong to the shared developer
  resume this goes through rather than around, and the per-issue daily retry cap counts fresh spawns, so a resume
  driven by a human's reply is an unblock signal rather than a retry exactly as it is in every other stage.

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

None of it starts on a generation that cannot be acted on. The prompt names both frozen commits and tells the agent to
diff between them, the hold marks a pull request in the generation's name, and the verdict is reported under its
identities — so the identities and both SHAs are proved before the plan PR is touched or an agent is started. That
includes the generation naming THIS issue, which a positive `late_current_issue` on its own does not say. A candidate
whose base was never recorded would otherwise produce a `git diff` against nothing and a record two sinks refuse
afterwards, with the run already paid for; one carrying somebody else's number would show the agent a prompt naming two
issues and file the verdict against the one it names. Either parks instead, saying which field is wrong.

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

## What the humans can still change while a candidate is frozen

Adjudication takes minutes to hours, and the issue is a live thread the whole time. Two local fingerprints watch it —
`late_title_body_hash` over the title and body, and `late_comment_hash` beside the `late_comment_watermark_id` it
covers from — and they are deliberately separate from the global `user_content_hash`, which keeps its single baseline
and its meaning so nothing here fires the re-decompose or dev-resume routes that read it. What counts as a human's
words is that hash's own trust filter all the same, so an outsider, a third-party bot, and the orchestrator's own
comments shift nothing. The fields themselves are in
[`../state-machine/labels-and-state.md#late-generation-state`][late-state].

The first tick of an adjudication takes the baseline: whatever the issue says then is what the candidate was frozen
against, and nothing on the thread counts as an answer to it. Every tick after that compares.

**Drift outranks every answer.** An edit to the title, the body, or a comment already counted into the baseline
changes what the candidate is supposed to BE, and an answer that arrived in the same window was written about the scope
as it stood before — applying it would adjudicate a reply against requirements it never saw. So the tick that first
sees drift parks (`late_content_drift`) and consumes nothing: the frozen commit, the late session, the recorded
generation, and any plan-PR hold are all left exactly as they were, because none of them is wrong, only unadjudicable
until a human says what the edit meant. A comment rewritten in place is drift for the same reason a title edit is —
it moves no comment id, so there is no new comment to read the change out of.

The park is a *response boundary*, not a one-tick delay. What counts as a reply is read against the higher of the
generation's own comment watermark and the issue-wide `last_action_comment_id`, which every announced park advances
past the notice it just posted — so an answer written before the human was told anything cannot resolve the park on
the next poll either. Nothing advances that watermark without consuming what it advances past, so the conservative
reading costs no real reply.

**Then the reply resolves it, and the two kinds of reply mean opposite things.** A bare `/orchestrator continue` is a
certificate: the committed work still answers the updated issue, so the fingerprints are re-baselined onto the content
as it now reads and the SAME frozen candidate goes on to be adjudicated — against the updated requirements, which is
why a verdict recorded before the edit is dropped rather than reused. The certificate covers the commit, not an answer
taken against a scope that has since moved: acting on one would be the drift rule refused a step later, with a split
creating children that describe requirements nobody is asking for any more. What it does buy is everything else —
the candidate is not re-derived and no developer is paid for. Substantive guidance is not a certificate — it says the
work has to change, so the developer session is resumed against it (above) and the candidate is re-frozen from what
comes back.

An edit taken back needs no reply at all: the candidate matches the issue again, so the park is cleared and the
adjudication resumes. Leaving it standing would not be harmless — `awaiting_human` is exactly the flag that
suppresses the announcement a question verdict earns, so a reverted edit would silence a question recorded and never
said out loud. Guidance that came with the revert is still guidance, though, and it is routed before any of that:
taking the edit back decides which requirements the change is asked against, not whether it was asked for. Absorbing
it into the baseline instead would consume a human's instruction without acting on it, and then reuse a verdict
nobody re-earned.

**A revised candidate is proved, not trusted.** The tree has to be clean before anything is read off it — a candidate
measured beside uncommitted changes is not the one a publication would push — and the commit the checkout ends on is
frozen and measured again from scratch under the ceiling as it stands now. What is not allowed is
skipping the measurement, which is why the generation counter advances on every reconciliation that lands — a recorded
verdict answers a cycle, a generation, AND a commit, so an acknowledged candidate is adjudicated against the
requirements that changed rather than answered from the record taken before they did.

The resulting SHA is allowed to be the one that went in, but only when the developer *said* so. The prompt asks for
the same `ACK: <justification>` marker every other drift resume asks for, and that marker is what an unchanged commit
needs before it is re-measured. Without one, an unchanged commit is not an acknowledgment — it is a run that said
nothing, asked a question, or timed out before it could do either, and all three look identical from the checkout.
Reading any of them as "the work already covers it" would advance a generation and adjudicate a candidate nobody
vouched for, so they park (`late_revision_unanswered`) with whatever the developer *did* say quoted, so a question
reaches the human it was meant for. A commit that MOVED needs no marker: work that changed HEAD speaks for itself. The
one path where an unchanged commit passes without one is the human's own `/orchestrator continue` on a stalled
revision — they have read the park and accepted the commit as it stands, which is the same thing the marker says.

A reconciliation that could not
be completed parks (`late_revision_dirty` / `late_revision_unmeasured`) with the generation exactly as it was, and a
bare continue re-runs that reconciliation alone rather than paying for a second developer run that already finished.

**Guidance means the same thing with nothing parked.** An adjudication in flight, or one that already recorded a
verdict, is still work a human can ask to be different — so the developer is resumed there too, and the re-measured
candidate that comes back advances the generation, which is what stops a verdict taken over the old work from
applying to the new. Folding the comment into the baseline instead would consume an instruction without acting on it.
The one reply that lands here with nothing to do is a bare `/orchestrator continue`: no park is waiting on it and no
candidate needs certifying.

**A categorized question is reopened only by a real answer.** Substantive trusted guidance drops the recorded outcome
— the record is exactly what suppresses the next spawn — so the adjudicator runs again against what the human said. A
bare continue may not: a question is not a step that failed, and "proceed" is not an answer to "which half of this is
in scope". The command is consumed, the refusal is posted once, and the issue stays parked on the question it is
really waiting on.

**Nothing outside the adjudication may decide it either.** While a generation is live — recorded, oversized, and not
cancelled — `workflow:decomposing` is the label it sits on, and both ways that can be taken away amount to publishing
an unadjudicated candidate. `DECOMPOSE=off` routes a `decomposing` issue into the legacy implementing flow, which is
right for an issue only waiting to be decomposed and wrong for one whose implementation is already committed and
measured past the ceiling, so the route is refused while a generation is live — the switch still keeps NEW candidates
out of the gate, it just does not decide the ones already in it. A hand relabel is caught a step later, since the
label is
already gone by the time anything reads it: the dispatcher asks before it routes anything, and an issue whose label a
human moved is put back on `workflow:decomposing`, told why, and left for the next tick rather than handed to the
stage the new label named (`late_relabel.py`). The refusal is the safety property and the relabel only the repair, so
a label write that cannot land still stops the dispatch, and so does a pinned read that cannot be taken. The
restoration itself goes out UNGUARDED and posts its notice only after the label lands: the transition graph describes
the moves this orchestrator makes, and putting back one a human made is not among them, so under
`WORKFLOW_TRANSITION_GUARD=enforce` a guarded `validating → decomposing` repair would raise every tick and strand the
generation under the wrong label — announcing itself again each time. That last
one is the single place this guard does not follow the additive-safety-net convention the pause probe reads by,
because the costs are not symmetric: failing open publishes an unadjudicated candidate — the handler behind it reads
the same pinned comment, and a first read that failed transiently is followed by a second that may well succeed —
while failing closed costs one tick of one issue, retried on the next poll, during an outage in which nothing else
was going to make progress either. Neither
clears, cancels, or decides anything — a
generation an operator really wants gone goes through the late domain's own cancellation, which records what the
remote is still owed.

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
[late-state]: ../state-machine/labels-and-state.md#late-generation-state
