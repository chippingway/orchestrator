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
  resume); `_handle_question` (and its `awaiting_human` resume) and `_handle_discussion` reuse the same backend.
  Session: locked per issue after first spawn (decomposing → `decomposer_agent`; question → `question_agent`;
  discussion → `discussion_agent`, each a separate pin).
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

What a resume re-parses, and why the pin is the full spec rather than the backend alone, is in
[`command-specs.md#in-flight-session-lock`](command-specs.md#in-flight-session-lock). The two conversation stages'
prompts and round contracts are in [`conversations.md`](conversations.md).

## Local verify gate (not an agent)

After the reviewer emits `VERDICT: APPROVED`, `_handle_validating` runs the configured `VERIFY_COMMANDS` directly in
the per-issue worktree — these are plain shell commands, not an agent role, so no `*_AGENT` env var applies. The gate
runs before the approval comment, the squash, the watermark seeding, and the `workflow:documenting` (final-docs) label
flip. A clean run advances the issue; any failure parks on `workflow:validating` with a typed `park_reason`
(`verify_failed` / `verify_timeout` / `verify_dirty` / `verify_head_changed`). See
[`../configuration.md#local-verification-gate`](../configuration.md#local-verification-gate) for the env-var
reference.

[workflow-labels]: ../state-machine/labels-and-state.md#workflow-labels
