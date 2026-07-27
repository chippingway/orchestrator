# Repository guide for AI agents

This file is the entry point for AI coding agents (Codex, Claude, etc.) working on this repository. `CLAUDE.md` is a
symlink to this file, so both conventions resolve to the same content.

It is loaded into every agent session — keep it short. For anything beyond a pointer, edit the linked docs instead.

## What this project is

`agent-orchestrator` is a GitHub-Issue-driven workflow that watches issues on configured repos, drives them through a
label-based state machine, and spawns local CLI agents (`codex`, `claude`) in per-issue git worktrees to implement
them and open PRs. State lives entirely in GitHub (one workflow label + one pinned JSON comment per issue), so the
orchestrator process is stateless.

- User-facing overview: [`README.md`](README.md)
- Architecture, module map, process / agent / push model: [`docs/architecture.md`](docs/architecture.md)
- Workflow state machine (labels, per-tick flow, stage handlers): [`docs/state-machine.md`](docs/state-machine.md)
- Agent roles, command specs, session lifecycles: [`docs/workflow.md`](docs/workflow.md)
- Configuration / env vars: [`docs/configuration.md`](docs/configuration.md) is the full reference; basic knobs in
  [`.env.example`](.env.example), common advanced overrides in [`.env.example.advanced`](.env.example.advanced)
- Observability (audit event log, analytics sink / database, usage parser):
  [`docs/observability.md`](docs/observability.md)
- Security checklist and operator-owned controls: [`docs/security.md`](docs/security.md)

## Repository layout

- `orchestrator/` — Python package: tick loop and label-dispatch compatibility facade (the `workflow/` package
  initializer, over the `workflow/state.py` owner -- the workflow / control label vocabularies and their wire
  strings, the strict label coercion and its legacy `value=` adapter, the declared transition graph, and the
  warn-or-raise guard plus the `orchestrator.state_machine` logger it warns through -- and over the
  `workflow/engine/comments.py` owner in the subpackage reserved for its remaining owners: the hidden
  orchestrator marker and the capped tracked-comment id ledger both posting helpers write, the
  trusted-author filter and quoting every prompt reads the issue thread through, and the capped
  tracked-repository awareness block -- and over the `workflow/engine/messages.py` owner beside it: the
  last-marker-wins review and documentation verdicts, the drift `ACK:` read, the `/orchestrator continue`
  recognition, park-reason classification, and guidance-free refusal, the Markdown blockquote every notice
  quotes through, and the redact-before-truncate stderr diagnostics a park comment and a log line
  carry -- and over the `workflow/engine/prompts.py` owner beside those: the prompt builders the stages
  share (implement, fresh-respawn preamble, review, documentation, fix, conflict resolution, question and
  its followup, PR-comment followup, decompose), the shared issue-body / conversation header and its empty
  placeholders, the foreground-only note every commit-producing prompt appends and the commit-style note
  the subject-writing subset of them adds beside it (the conflict prompt replays subjects it did not
  write, so it takes only the first) -- the single-caller drift-resume prompt stays on
  `workflow/engine/drift.py` and borrows both -- the
  bounded conflicted-path listing, and the single-decision comment and its best-effort manifest
  fields -- and over the `workflow/engine/usage.py` owner beside them: the single tracked-run site
  every agent role spawns through, the frozen run request and the runner kwargs it forwards
  selectively, the `agent_spawn` / `agent_exit` pair around the spawn, the analytics record its exit
  appends (with the configured model read out of `extra_args` as the parser's fallback, and the
  prompt and worktree the trajectory hooks ride on), the fail-open `skill_triggered` emission that
  record's return value drives, the per-issue run / token / cost / cost-source counters that record's
  parsed usage is folded into and the terminal receipt line and tracked comment read back off them,
  and the UTC timestamp the stages stamp pinned state with -- and over the
  `workflow/engine/drift.py` owner beside them: the user-content hash and the six filters
  that keep an orchestrator, bot, untrusted, or bare-continue comment from shifting it, the
  first-encounter baseline write and the legacy-baseline absorption, the drift-resume prompt and its
  `ACK:` contract, the consumed-comment watermark ratchet the resume paths bump, and the
  decomposition reset, orphan-naming notice, and `decomposing` relabel a pre-implementation drift is
  rerouted with -- and over the `workflow/engine/guards.py` owner beside them: the two
  refusals every agent-running stage puts between a finished run and its disposition -- the
  shutdown-interruption read off the result, and the hard-skip label read off a freshly fetched issue
  because the handler's own snapshot predates the run -- beside the awaiting-human park that
  publishes one instead: its HITL comment, `awaiting_human` flag, cleared park reason,
  action-comment watermark ratchet, and `park_awaiting_human` event, with the pinned-state write
  left to the handler in all three cases -- and over the `workflow/engine/pickup.py` owner beside
  them: the two decisions an unlabeled issue's first tick makes -- the
  case-insensitive `ALLOWED_ISSUE_AUTHORS` filter that answers whether the orchestrator picks it up
  at all, and the `DECOMPOSE` switch that picks `decomposing` or the legacy straight-to-implementing
  route -- and the four writes both starts publish in one order: the greeting whose id anchors
  `pickup_comment_id`, the `user_content_hash` baseline computed with that id filtered out, the
  workflow label, and the pinned state, with the chosen stage handler called in the same tick
  through a call-time import of the owner it lives on -- and over the
  `workflow/engine/terminals.py` owner beside them: the three arcs an issue stops on --
  merged PR, PR closed unmerged, and a human-closed issue over an open PR -- sharing one tail of
  terminal stamp, terminal label, usage receipt, and single pinned-state write, with the `pr_merged` /
  `pr_closed_without_merge` payloads, the issue close, and the local + remote branch cleanup the two
  PR-gone arcs alone earn, reached either through the drain the PR-holding stages hand their own PR
  to or through the pair of entry-time finalizers that fetch their own and answer a failed fetch by
  leaving the issue alone and by deferring the tick respectively -- and over the
  `workflow/engine/dispatch.py` owner closing the subpackage: everything between a repo's pollable
  issues and a running stage handler -- the `backlog` / `paused` filter applied both before the
  partition and again in `_process_issue`, the family / fanout split that serializes the
  cross-issue writers (`decomposing` / `blocked` / `umbrella` and the unlabeled-pickup `None`)
  and the failed label read routed conservatively into that bucket, the cap exemption a no-agent
  family bucket and a closed fan-out issue are submitted under, the per-worker client and refetch
  only issue numbers cross a thread with, the scheduler submits and the sequential bucket drain
  with its `track_active` claim, and the `stage_evaluation` record every timed dispatch appends,
  with each handler reached through a call-time import of the module its label is paired with in
  `_STAGE_HANDLER_TARGETS` -- and over the `workflow/engine/tick.py` owner closing the
  subpackage: one repo's polling pass in one order -- the base refresh whose failure is the only
  one the tick catches, the community-contribution sweep that sits here because the outsider PRs
  it labels carry no pinned state for a stage handler to consult, and the skill-catalog emission
  beside it, both placed before the scheduler / in-tick split so they fire once per tick on either
  path -- and behind that split either the scheduler handoff or the two in-tick modes: the
  streaming sequential loop that keeps the issues a mid-sweep pagination failure yielded, and the
  bounded pool whose materialized partition folds the whole family bucket into one task so it
  holds a single slot, both wrapping each issue in its own try/except, with
  `_refresh_base_and_worktrees` and `_emit_repo_skill_catalog` deliberately read off the facade
  because those are the seams the tick tests replace -- and over the `workflow/stages/` package
  beside that subpackage, the destination the per-label stage facades migrate to one at a time: it
  binds nothing, a migrated stage arrives as its own subpackage of responsibility-named owners, the
  `stages/<stage>.py` it vacates stays behind as a temporary forwarder reading every name back off
  those owners, and dispatch is the one caller the forwarder does not cover -- both the label table
  and the same-tick pickup start name the owner a migrated handler lives on -- and over the
  `workflow/stages/decomposition/` subpackage that arrived there first: the four labels one manifest
  produces, split across the `state.py` owner (the pinned-state fields every owner keys and the
  `#a, #b` renderer each notice quotes children through), the `models.py` owner (the run plan and
  its worktree policy, the locked session, the split plan, the child scan), the `manifest.py` /
  `validation.py` pair (the one-final-fence envelope, the JSON decode and the parse entry point
  beside it; and everything a `split` payload must satisfy before the first irreversible child
  create -- the `_MAX_CHILDREN` cap the decompose prompt reads back so the two cannot disagree, each
  child's shape, and the acyclicity of the graph they declare), the `session.py` owner (the spec
  pinned before the first spawn can fail, the spawn that pins it, the human-reply resume, and the
  drift reset that drops the session id but never the lock), the `run.py` owner (one `decomposing`
  tick: drift before recovery before the `DECOMPOSE` kill switch, then pause, dirty worktree, and
  interruption before any disposition, with the worktree torn down by an `ExitStack` callback so a
  mid-sequence `keep_worktree` survives a raise), the `outcomes.py` owner (the unparsed park that
  tells a malformed manifest from a question, the `single` finalize, the `split` hand-off), the
  `recovery.py` owner (the two markers a crashed split leaves, the orphan-child repair a finalize
  runs first, and the park a short count earns), the `split.py` owner (the crash-safe order children
  are created and recorded in, and the summary / label / activation tail), the `parents.py` owner
  (the fresh child scan the family bucket makes safe, the rejected and manually-closed parks, and
  the parent's own drift reroute), the `activation.py` owner (the dep-graph walk and the
  held-dependency line it logs), and the `blocked.py` / `umbrella.py` handlers (the poll they share,
  and the `ready` handoff versus the close their all-done branches differ by) -- and over the
  `workflow/stages/implementing/` subpackage beside it, whose owners split one tick along the
  decisions it makes: the order those decisions are asked in (`handler.py`), whether anything runs at
  all -- the awaiting-human route, the recovered-worktree shortcut, and the retry-gated fresh spawn
  (`spawn.py`); the locked dev session -- what the pinned state says it is and what a run's own text
  says about its health (`session_read.py`), the three retirements and the per-issue 24h spawn cap
  (`session.py`), the two resume entry points and the historical call shape they keep (`resume.py`),
  one resume with its poisoned-session retry (`execution.py`), and the checkout it runs in
  (`worktree.py`); what a finished run leaves behind -- the `before_sha` disposition and the timeout
  park's own recovery (`disposition.py`), the four HITL parks (`parks.py`), and the push / PR /
  validating handoff (`publication.py`); and the four signals that arrive between runs -- a body edit
  and its `ACK:` (`drift.py`), a pre-session edit and a quiet timeout (`drift_preflight.py`),
  `/orchestrator continue` on a parked issue (`continue_command.py`), and the question relabel guards
  (`question_relabel.py`) -- over the frozen records they hand each other (`models.py`) and the
  pinned-state keys and CLI markers they share (`state.py`), with the worktree, git, and push helpers
  still reached through the `workflow` facade at call time) -- and over the
  `workflow/stages/documenting/` subpackage beside it, whose owners divide by what one final-docs tick
  has to settle before it may spawn: the order those questions are asked in (`handler.py`); the three
  that end the tick outright -- the merged-PR / closed-issue terminals, the missing-`pr_number` guard,
  and the bare `/orchestrator continue` refusal -- beside the parked-no-input fast path that keeps a
  transient park from reposting (`preconditions.py`); the one that unwinds instead, a body edit that
  drops the stale approval and relabels back to `validating` (`drift.py`), with the fetch, probe, and
  hard-reset + clean it hands the worktree to, each failing closed because a docs commit left against
  the OLD body is what the next tick's recovered-commit shortcut would push unreviewed
  (`drift_reset.py`); the pass itself -- the branch refresh, the diverged-worktree refusal, and the
  awaiting-human resume / recovered-commit / fresh-spawn shapes (`run.py`); and what it left behind --
  the timeout / dirty / commit / `DOCS: NO_CHANGE` order (`outcomes.py`), the push with the
  `docs_checked_sha` and `docs_verdict` it stamps and the PR notice it posts (`publication.py`), and the
  `pr_last_comment_id` ratchet that has to precede the `in_review` relabel so a consumed reply does not
  replay as fresh PR feedback (`handoff.py`) -- with the four awaiting-human parks (`parks.py`) over the
  frozen records (`models.py`) and pinned-state keys (`state.py`) they share, the dev resume, session
  read, and question / dirty-tree parks imported from the implementing owners directly and the seed
  walk from validating's `watermarks.py`, and the worktree, git, and push helpers still reached
  through the `workflow` facade at call time) -- and over the `workflow/stages/validating/` subpackage beside it,
  whose owners divide by what one review tick is answering, the reviewer being only part of what the
  stage runs: the terminals a landed or rejected PR ends the tick on and the order the rest are asked
  in (`handler.py`); the round cap that guards a loop which cannot converge, the tracked spawn, and the
  live-pause and interruption refusals that stand between it and any disposition (`reviewer.py`); the
  approved arc -- the local verify gate that is the last thing before `in_review`, the approval
  comment, the optional squash whose failure parks WITHOUT relabeling, and the `documenting` relabel
  (`approval.py`) -- with the failure side of that gate (`verify.py`) and the seed walk it hands the PR
  to, which stops at the first comment the dev has not consumed rather than the first the orchestrator
  did not write, plus the ratchet that never regresses one (`watermarks.py`); the other two verdicts --
  the PR feedback and the dev fix run under the `fixing` label, and the park a reviewer that emitted no
  VERDICT line earns (`requested_changes.py`); and what one finished dev fix leaves behind whichever
  route started it -- the stranded-commit probe that keeps a committed-but-unpublished fix from
  ping-ponging between parks, the push, and the `review_round` bump (`dev_fix.py`) -- fed by the three
  routes between rounds: a park a human replied to, its three park-reason claims and the resume none of
  them wanted (`awaiting.py` / `awaiting_resume.py`), a body edit mid-review and the `ACK:` reply that
  must not park (`drift.py` / `drift_outcomes.py`), and the push race or dev timeout that clears
  without anyone commenting (`recovery.py`) -- over the frozen records (`models.py`) and the
  pinned-state keys, park reasons, and outcome tokens (`state.py`) they share, with the dev resume,
  session read, and question / dirty-tree parks imported from the implementing owners directly and the
  squash from `git/publication/squash.py`, and the worktree, git, and push helpers still reached
  through the `workflow` facade at call time),
  per-stage
  lazy facades (`stages/`),
  worktree-subsystem compatibility hub (`worktrees.py`), and the `base_sync.py`,
  `branch_publication.py`, `git_plumbing.py`, `verify.py`, `worktree_lifecycle.py`, `workflow_drift.py`, and
  `workflow_messages.py` subsystem facades. Their immutable `_export_manifest.py` inventories and `_exports.py` hooks
  route historical imports and patch points to responsibility-named private leaves (`_workflow_*`
  and stage-specific prefixes) or straight to the package owners -- `workflow/engine/drift.py` for
  every name `workflow_drift.py` publishes, `git/` for
  `git_plumbing.py`, `git/verification/` for `verify.py`, `git/worktrees/` for `worktree_lifecycle.py`,
  `git/publication/` for `branch_publication.py`, and `git/base_sync/` for every name `base_sync.py`
  publishes: the models, shared state, worktree refresh, rebase-eligibility gates, the PR-route coordinator
  and conflict routing, the rebase startup, publication and its guards, and
  crash-recovery probing, routing, outcomes, and persistence. The package also
  contains per-tick
  repo skill-catalog analytics (`skill_catalog.py`), lazy analytics/read and dashboard facades backed by focused
  recording, query, rendering, usage-provider, and trajectory leaves, the process-local scheduler package
  (`scheduler/`, whose `__init__.py` publishes the narrow public surface (`__all__`) -- `IssueScheduler` and
  `SubmissionRequest`, re-exported from their owners -- over the `models.py` owner (typed submissions,
  legacy-call binding, normalization) and the `service.py` owner (the concrete scheduler and its view,
  reservation, and execution layers)),
  the configuration package (`config/`, whose `__init__.py` binds each setting resolved by the `environment.py`
  `_SettingsResolver`, which draws on the `_dotenv.py` / `credentials.py` / `models.py` / `repositories.py` leaves;
  `credentials.py` also owns secret redaction -- the secret-key shapes plus the environment / configured-token
  passes every stderr, verify-output, and trajectory consumer masks with),
  the agents package (`agents/`, whose `__init__.py` is the stable runner facade over the `models.py` /
  `environment.py` / `sessions.py` / `processes.py` / `runner.py` owners -- `processes.py` owning the shared process
  registry and subprocess-group lifecycle (the facade re-exports only its `terminate_all_running`) and `runner.py`
  owning shared agent dispatch, result assembly, and spawn logging (re-exported as `run_agent`) -- and the
  per-backend command modules in the `backends/` subpackage (`backends/codex.py`, `backends/claude.py`)),
  the github package (`github/`, whose `__init__.py` publishes the narrow public surface (`__all__`) -- the composed
  `GitHubClient` and the pinned durable-state model, re-exported from their owners; every other GitHub surface is
  imported from its owner directly -- over the `client.py` owner (token resolution, PyGithub initialization, the
  composed client class, its worker-thread clone, cached label reads, and the paired audit / analytics stage-enter
  hook), the `labels.py` owner (the workflow/control label vocabulary, bootstrap specifications,
  predicates, and the label-bootstrap client mixin), the `events.py` owner (audit record construction and the
  optional JSONL sink), the `issues.py` owner (non-PR issue filtering, issue-query options, and the issue-client
  mixin: polling with the closed-issue sweep, guarded workflow-label writes, event emission, comments, and
  validated child creation), the `pinned_state.py` owner (the authenticated pinned-state model, parser, and the
  state / comment-watermark client mixin), the `pull_requests.py` owner (stateless PR status helpers plus the
  pull-request client mixin: branch/base lookup, creation, comments, open-PR iteration, labeling, retrieval,
  SHA-pinned merges, and idempotent head-branch deletion), the `reviews.py` owner (current-head review aggregation
  plus the review client mixin: approval and change-request verdicts and the unread conversation / inline / summary
  feedback watermarks), the `checks.py` owner (status / check-run normalization, failure-before-pending folding, and
  the fail-closed check-read client mixin), and the `comments.py` owner (the comment-author trust policy the git
  base-sync gates and the workflow stage leaves both filter through: the `ALLOWED_ISSUE_AUTHORS` allowlist, its
  trust-all empty default, and the case-insensitive login match that gates bots like any other
  author)), the git package (`git/`, whose `__init__.py` binds nothing so callers
  import each owner directly -- the `commands.py` owner (plain / hardened git execution plus the unsafe local
  transport probe), the `authentication.py` owner (per-repository token resolution, the askpass session and its
  detached environment, the authenticated worktree / target-root fetches, and the lease-pinned hardened push), the
  `locks.py` owner (the
  per-target-root re-entrant lock registry), the `verification/` subpackage over the `models.py` owner (the
  `VerifyResult` statuses / fields and the output budget its `output` is truncated to), the `output.py` owner
  (the redact-then-truncate pass that fills that field), the `probes.py` owner (the HEAD snapshot and the
  hardened porcelain dirty-file scan, both run through `commands.py`), the `process.py` owner (one verify
  command's process-group spawn, group kill, bounded drains, and the `VerifyResult` verdict it earns) and the
  `runner.py` owner (the HEAD snapshot, the credential-stripped child environment, and the fail-fast
  `VERIFY_COMMANDS` sequencing the validating stage calls directly, with process registration and environment
  filtering borrowed from `agents/`), the `worktrees/` subpackage, whose `__init__.py` likewise binds nothing
  over the `paths.py` owner (slug sanitization, the git-ref-safe branch segment, branch / path derivation, and
  the pinned / legacy branch resolver), the `recovery.py` owner (candidate-branch discovery and the
  unpushed-commit probes), the `creation.py` owner (the issue / PR worktree creators, their stale-worktree
  reuse, and the new-commit probe the reuse turns on), the `decomposition.py` owner (the decomposer scratch
  checkout's path, detached creation, and best-effort removal), the `cleanup.py` owner (best-effort issue-worktree
  removal and local branch deletion under the target-root lock) and the `terminal.py` owner (the question-stage
  teardown and the terminal local + remote branch cleanup composed from it), and the `publication/` subpackage, whose
  `__init__.py` also binds nothing, over the
  `probes.py` owner (the conventional / repo-local subject vocabulary and predicates, ahead/behind counts,
  first-commit and recent-base subject reads), the `titles.py` owner (subject-prefix inference from base
  history and PR-title selection), the `planning.py` owner (the pre-rewrite merge-base, HEAD, dirty-tree and
  topic-subject probes, their preparation error, and the squash message they select), the `rewrite.py` owner
  (the soft reset, the orchestrator-identity squash commit, the lease-pinned force-push, and the rollback each
  post-reset failure takes) and the `squash.py` owner (the plan-then-rewrite entry point stage handlers call),
  and the `base_sync/`
  subpackage, whose `__init__.py` binds nothing either, over the `models.py` owner (the frozen auto-rebase
  context / request / recovery-context / snapshot / decision / conflict-route dataclasses), the `state.py`
  owner (the pinned-state keys, park reasons, refresh detour labels, and the `orchestrator.base_sync` logger
  every behavioral owner binds directly), the `pre_pr.py` owner (the hardened rebase / merge probes,
  rebase-in-progress detection, and the abort-on-failure local rebase of a branch nobody has pushed), the
  `refresh.py` owner (the per-tick authenticated base fetch, worktree discovery, scheduler-claim and
  hard-skip / question / dirty-tree gates, and the per-worktree route to `pre_pr` or the PR-aware
  coordinator), the `pr.py` owner (that coordinator: the order the gate, rebase, and publication owners are
  asked in, plus the legacy keyword signature the refresh enters through), the `conflicts.py` owner (the
  once-seeded round counter, PR notice, `conflict_round` event, and `resolving_conflict` relabel a genuinely
  conflicted rebase is handed to its stage with), the `eligibility.py` owner (the refresh-driven label check
  that settles a stale recovery
  anchor, the park-reason and trusted-retry-comment decision, the open-PR read that clears an anchor a
  terminal PR left behind, the crash-recovery precedence, and the clean-tree / behind-base start
  probe), the `startup.py` owner (the pre-rebase HEAD guard, the anchor and retry unpark persisted
  before git runs, and the abort / conflict-route / park a failed rebase takes), the `publication.py` owner
  (the post-rebase HEAD and dirty checks, the lease-pinned force-push they gate, and the notice, audit event,
  `validating` route, and pinned-state write an accepted push earns), the `guards.py` owner (the no-op
  completion plus the unreadable-HEAD, dirty-tree, and failed-push parks publication hands off to), the
  `persistence.py` owner (the auto-rebase park, the shared
  reset-and-park tail, and the pinned-state / notice / audit-event writes a recovered rebase finalizes and
  routes with), the `outcomes.py` owner (the two recovery notices plus the already-published,
  unknown-comparison, diverged, dirty, and failed-push answers one verified recovery resolves into), the
  `snapshot.py` owner (the authenticated branch fetch, the local and remote head reads, the divergence
  counts, the anchor-clearing no-op exits, and the reset-and-park abort every unreadable read fails closed
  to) and the `recovery.py` owner (the order those reads and answers are asked in, the dirty-guarded
  reissued push and the finalize it earns, plus its own legacy keyword signature), with
  `git_plumbing.py`, `verify.py`,
  `worktree_lifecycle.py`, `branch_publication.py`, and
  `base_sync.py` kept as the forwarding facades for historical callers), the stable runtime-core
  facade (`main.py`), and the two root modules that forward a historical compatibility surface off a package owner
  without rebuilding any of it: `state_machine.py` over `workflow/state.py`, and `comment_trust.py` over
  `github/comments.py`.
  Full module-by-module map: [`docs/architecture.md`](docs/architecture.md#top-level-layout).
- `tests/` — pytest suite. In-memory GitHub doubles live in `tests/support/github/` and reach the still-flat workflow
  tests through the `tests/fakes.py` bridge. Stage-handler tests in
  `tests/test_workflow_<stage>*.py` (the in_review stage is split across
  `tests/test_workflow_in_review_*.py`; the implementing, documenting, and validating stages have moved beside their
  owners into `tests/workflow/stages/implementing/`, `tests/workflow/stages/documenting/`, and
  `tests/workflow/stages/validating/`, and the decomposition and question
  stages across their respective focused modules, with shared fixtures in `tests/decomposition*_support.py` and
  `tests/question_*_support.py`; the resolving-conflict stage is split across
  `tests/test_workflow_conflicts_*.py` — infrastructure tests (`_event_emission`,
  `_list_pollable`, `_routing`) plus the `_handle_resolving_conflict` handler scenarios in focused modules
  (`_clean_rebase` for clean rebase routing, `_agent` for agent execution, `_resume` for awaiting-human resume
  paths, `_dirty` for dirty / rebase-in-progress parking, `_recovery` for recovery pushes, `_diverged` for stale /
  diverged worktree handling, `_publish` for already-rebased force-publish scenarios, `_publish_guard` for the
  publish-guard probe unit tests, `_drift` for hash-drift resume behavior), with resume fixtures in
  `tests/conflict_resume_test_support.py`); other facade-level helper tests
  include (`tests/test_workflow_event_emission.py`, `tests/test_workflow_agent_event_emission.py`,
  `tests/test_workflow_model_extraction.py`, `tests/test_workflow_pr_lifecycle.py`,
  `tests/test_workflow_question_routing.py`, `tests/test_workflow_fixing_routing.py`,
  `tests/test_workflow_in_review_fresh_feedback.py`); shared helpers in `tests/workflow_helpers.py`.
  Configuration-package
  tests live in `tests/config/`, agent-package owner / import-cycle tests in `tests/agents/`, and github-package
  client (construction, token resolution, worker clone, label cache), label (vocabulary, predicates, and bootstrap),
  event, issue-query, issue-client (real-client polling and child creation), pollable-listing, pinned-state,
  pull-request (status helpers, writes, merges, branch deletion), review (head verdicts, actionable summaries,
  feedback watermarks), check (surface normalization, folding, fail-closed reads), comment-trust (the empty-allowlist
  trust-all default, case-insensitive login matching, missing users, bots, and preserved input order), and
  import-cycle / layering / public-surface
  tests in `tests/github/`. Scheduler-package tests live in `tests/scheduler/`: caps and duplicate-active gating,
  tracked claims, family exclusion, cap-exempt execution, skip logging, shutdown, submission models and `submit`
  compatibility, and import-cycle / public-surface checks, with their worker, coordination, log, and shutdown
  helpers alongside. Git-package tests live in `tests/git/`: plain / hardened command envelopes and real-git
  transport probing, askpass session / environment construction and failed-fetch shaping, the authenticated
  worktree and target-root fetches, the push's lease decisions / per-repository token / transport refusals,
  target-root lock ownership, and import-cycle / package-surface checks, plus
  their shared authentication fixtures, with the verification owners covered under `tests/git/verification/` —
  result fields and statuses, HEAD and porcelain probing against a planted `core.fsmonitor`, command sequencing
  and output budgeting, child-environment stripping and redaction-before-truncation, timeout group-kill and
  bounded drains, fail-closed HEAD-baseline and fail-fast refusals, verify-time mutation detection, and
  import-cycle / layering / package-surface checks, plus the real-git verify-command fixture; the
  worktrees owners covered in `tests/git/worktrees/`: path derivation, git-ref-safe branch segments, pinned /
  legacy branch resolution, real-git unpushed-commit probes, issue / PR creation with stale-worktree reuse and
  remote-branch restoration, the new-commit probe, decomposer path / creation / removal, lock-held worktree removal
  and local branch deletion with their best-effort boundaries, question and PR-terminal teardown ordering against
  both faked plumbing and a real worktree, per-target-root
  serialization against both a blocking fake and a real bare remote, and import-cycle / package-surface checks,
  plus their path, branch-fixture, faked-plumbing, terminal, and real-git support modules (the thread scaffolding
  those serialization tests share with the authenticated-fetch one lives in
  `tests/git/concurrency_test_support.py`);
  the publication owners covered in `tests/git/publication/`: subject
  predicates, per-spec commit-subject reads, ahead/behind folding, prefix inference, PR-title selection,
  squash preparation errors and guard ordering with the message it selects, real-git subject selection and
  no-op / dirty-tree refusals, real-git commit identity, fsmonitor hardening and push-failure rollback, and
  import-cycle / package-surface checks, plus their git-double and real-repository support modules; and the
  base-sync owners
  covered in `tests/git/base_sync/`: request-to-context derivation, model defaults and frozen-ness, the
  published pinned-state keys / park reasons / detour labels / logger name, the hardened rebase and its
  conflicted-path list, rebase-state probing, the aborting pre-PR rebase, the per-tick fetch / discovery
  and the gates that end a sync early, the hard-skip controls / handler-owned label / terminal PR that end
  one worktree's sync before a rewrite, the label, park-and-trusted-retry, open-PR, recovery-precedence, and
  clean-tree eligibility decisions, a real bare remote driving the clean / no-op / conflicting / dirty
  pre-PR paths end to end, the auto-rebase park and its
  reset-and-park tail, the staged recovery state / notice / event / routing writes and the order the park and
  finalize paths publish them in, the recovery notices and the park, abort, and already-published outcomes,
  the anchor a normal rebase sets and every park clears, the abort / conflict / park routes a failed rebase
  takes, the notice / event / relabel a published clean rebase writes and the reset-and-park a rejected push
  falls to, the PR states and counters a refresh leaves untouched, a real bare remote driving the PR-route
  publish and its push-failure rollback,
  the fetch refspec / remote-head reads / divergence probing and their fail-closed exits, the order one
  comparison is routed to a single answer in and the guards the reissued push is leased behind, the recovery
  exits that cannot verify what the remote PR branch carries, real-git recovery of an unpushed rebase, a
  landed push, an out-of-band remote update, and a dirty worktree, the three ways an interrupted rebase
  reaches `validating` again, the historical keyword calls the three compatibility adapters still accept, and
  import-cycle / layering /
  package-surface checks including the guard that no flat `_base_sync_*` implementation leaf returns, plus
  their collaborator patch table, refresh fixtures and scenarios, real-git fixtures, anchor / clean / park
  assertions, and recovery-context / call-order support modules. Workflow-package tests live in
  `tests/workflow/`: the clean-process imports of the package, its `engine/` subpackage, and the `state`,
  `engine/comments.py`, `engine/dispatch.py`, `engine/drift.py`, `engine/guards.py`, `engine/messages.py`,
  `engine/pickup.py`, `engine/prompts.py`, `engine/terminals.py`, and
  `engine/usage.py` owners, the guard that
  importing either the facade or the state
  owner resolves no manifest target and no
  dependency binding — the `stages/` destination included — the package-surface checks that the facade is the
  initializer, that the engine initializer binds only the submodules planted in it, and that a submodule
  binding leaves its lazy hooks intact, and the state owner's own
  coverage — the label wire strings and their typo-guarded coercion, the transition table and its
  reachability / terminal-liveness invariants (`test_state.py`), and the per-mode guard decisions, terminal
  edges, preserved logger name, and `set_workflow_label` wiring (`test_state_guards.py`). The comment owner's
  coverage lives in `tests/workflow/engine/`: the shared id ledger both posting surfaces append to with its
  marker, idempotent wrap, and eviction cap, the allowlist filter and `@author` quoting the thread read applies,
  and the four historical facades that still forward its names (`test_comments.py`), plus the tracked-repos
  gate, listing, cap, framing, and absent secret fields (`test_comments_tracked_repos.py`). The injected-comment
  thread those filter tests share with the top-level prompt-builder and drift-hash ones lives in
  `tests/comment_trust_test_support.py`. The message owner's coverage lives beside them: the
  redact-before-truncate stderr block and log tail, the `ACK:` marker's last-wins read and its refusal of
  unmarked prose, `/orchestrator continue` recognition and bare-vs-guided classification, the retry / refuse /
  passthrough action per park reason, the refusal that consumes the command it answers, and the three
  historical facades that still forward its names (`test_messages.py`), plus the review and documentation
  marker parsers with the inline / nonfinal / punctuated variants they reject
  (`test_messages_verdicts.py`). The prompt owner's coverage sits beside those: the shared header's body /
  thread text and its empty placeholders across every builder that carries one, the repo-local commit-style
  and foreground-only notes on every commit-producing prompt (the conflict prompt authors no subject, so it
  carries only the second), the conflicted-path listing and its capped remainder, the empty reviewer-feedback
  fallback, and the three historical facades that still forward its names (`test_prompts.py`), plus the
  documentation prompt's own marker / diff-target / `plans/`-exclusion contract
  (`test_prompts_documentation.py`). The tracked-run owner's coverage sits beside those: the single
  analytics record a stage-driven run appends, its context / exit / usage fields and the prompt, stdout,
  stderr, and secrets it must not carry (`test_usage.py`), the configured-model fallback filling only a
  stream that omitted its own model (`test_usage_fallback.py`), the one-per-distinct-skill emission with
  its default-off gate, args privacy, and fail-open guard (`test_usage_skills.py`), the opt-in trajectory
  record and the pinned-off sink it must not write (`test_usage_trajectory.py`), and the `UsageMetrics`
  surfaced on the returned result (`test_usage_metrics.py`), with the wire payloads and issue numbers all
  five share in `tests/workflow/engine/usage_test_support.py`. The same owner's per-issue meter follows: the
  token formula that excludes codex's cached tokens, the cost and cost-source aggregates, the
  `(est.)` / `unknown` / zero-run verdict slots, and the developer, resume, and reviewer run sites whose
  interrupted runs persist nothing (`test_usage_accumulator.py`), with the poisoned-then-fresh resume fixture
  in `tests/workflow/engine/usage_accumulator_test_support.py`. The drift owner's coverage follows: the
  title / body / comment hash, its first-encounter baseline write, the legacy bare-continue
  baseline it absorbs and the real edit it still reports, and the two facades that forward its names
  (`test_drift.py`), the evicted-id and third-party-bot comments the hash must stay stable across
  (`test_drift_filtering.py`), the pickup hash seed, the resume prompt's quoted conversation, the durable
  baseline a no-op tick still writes, and the `ACK:` that must not park (`test_drift_routing.py`), the
  unmarked clarification that must (`test_drift_parking.py`), and the `last_action_comment_id` ratchet each
  stage's drift path leaves behind (`test_drift_watermarks.py`), with the issue numbers and the
  prior-versus-current hash fixture all five share in `tests/workflow/engine/drift_test_support.py`. The
  guard owner's coverage follows: the mid-run hard skip read off a freshly fetched issue at
  the decomposer, reviewer, and question spawn sites, and the children, relabel, comment, session id, and
  watermark none of them may leave behind (`test_guards_paused.py`); the per-stage `_paused` modules and each
  stage's own interrupted cases keep the dispositions those refusals are wrapped in. The pickup owner's
  coverage follows: the decompose-off route to implementing, the allowlist's silent skip and
  its case-insensitive and empty-list matches, the start each `DECOMPOSE` setting selects on the owner, the
  label and anchors each start has already published by the time it dispatches the stage owner in the same
  tick, and the facade that still forwards its five names (`test_pickup.py`). The terminal owner's
  coverage follows: the merged, closed-unmerged, and human-closed arcs with the stamp, label,
  event payload, issue close, and branch cleanup each earns (`test_terminals_drain.py`), the two states that
  fire no arc at all -- a `None` PR and an open PR under an open issue (`test_terminals_no_op.py`), the
  already-closed issue a merged arc must not re-close and the tracked receipt every arc posts before its
  write (`test_terminals_receipts.py`), the `conflict_round` a `resolving_conflict` event coerces and the
  other stages leave absent (`test_terminals_metadata.py`), and the entry-time merged-PR finalizer with its
  no-`pr_number` / open-PR / closed-unmerged negatives, its open- and already-closed-issue finalizes, and the
  receipt it skips on an empty meter (`test_terminals_finalize.py`), with the scenario models, issue numbers,
  and drain / cleanup / receipt assertions the first four share in
  `tests/workflow/engine/terminals_test_support.py`. The dispatch owner's coverage
  follows: the facade forward of all nineteen names (`test_dispatch.py`), the `backlog` and
  `paused` holds that must run no handler, write no label, and post no comment, and the resume a removed
  label is (`test_dispatch_backlog.py`, `test_dispatch_paused.py`), the one `stage_evaluation` record each
  dispatch appends across the happy, unlabeled, error, hard-skip, and disabled-sink paths
  (`test_dispatch_analytics.py`), and the scheduler-dispatch scenarios in
  `tests/workflow/engine/test_dispatch_scheduler_*.py` — the hard-skip issue that must not starve fanout
  (`_backlog`), the closed-issue probe and its cap-exempt fan-out submit (`_closed`), the no-agent bucket's
  cap exemption and the mixes that forfeit it (`_exemption`), the single sequential bucket and its
  in-flight claim (`_family`), the per-issue submits and the duplicate-active skip (`_fanout`), and the
  per-worker client the refetch mints (`_isolation`) — with their fixtures, fakes, and gated workers in
  `tests/workflow/engine/dispatch_scheduler_test_support.py`, `dispatch_scheduler_fakes.py`, and
  `dispatch_scheduler_workers.py`. The tick owner's coverage closes the directory: the pass order both
  dispatch routes run and the facade forward of all eleven names (`test_tick.py`), the base refresh that
  precedes every issue and the failure that must not stop them (`test_tick_refresh.py`), the family
  bucket's internal serialization, one-slot footprint, and overlap with fanout plus the label read routed
  into it (`test_tick_family_parallel.py`), the per-repo cap, its sequential `limit == 1` legacy, and the
  isolation of a raising issue (`test_tick_per_repo_parallel.py`), the global semaphore clamping under a
  higher per-repo limit, the per-worker clients the fanout mints and the sequential path must not, and
  the issues a mid-enumeration failure must not lose (`test_tick_global_parallel.py`), and the sweep's
  allowlist, bot, and already-labeled skips (`test_tick_community.py`) beside the ping-before-label
  ordering, the per-PR and enumeration failure isolation, and the tick wiring
  (`test_tick_community_failures.py`), with their spec / client fixtures, concurrency probes,
  family-scheduling probes, and PR builders in `tests/workflow/engine/tick_parallel_test_support.py`,
  `tick_probe_test_support.py`, `tick_family_test_support.py`, and `tick_community_test_support.py`. The mirrored
  `tests/workflow/stages/` directory holds what the migration destination owes: its clean-process import, the
  layering guard that the package costs the facade above it and nothing else, and the surface checks that its
  initializer binds only submodules and that `orchestrator.stages` still answers with the object the facade does
  (`test_imports.py`). `tests/workflow/stages/decomposition/` holds the stage that arrived there: the same import,
  layering, and initializer guards for its own package plus the two forwarding checks that no manifest target names
  a flat `_decomposition_*` leaf and that both historical import sites hand back the owner's exact object, and the
  dispatch check that the label table and the pickup start name the owner rather than the forwarder
  (`test_imports.py`); the handler scenarios beside it (`test_blocked.py`, `test_umbrella.py`, `test_ready.py`,
  `test_decision.py`, `test_manifest.py`, `test_recovery.py`, `test_resume.py`, `test_drift.py`, `test_disabled.py`,
  `test_park.py`, `test_persistence.py`, `test_write_ordering.py`, `test_finalize.py`, `test_cleanup.py`,
  `test_usage.py`, `test_worktree.py`, `test_full_spec.py`), with shared fixtures in
  `tests/workflow/stages/decomposition/decomposition_test_support.py` and `decomposing_test_support.py`.
  `tests/workflow/stages/implementing/` holds the stage beside it: the same import, layering, and initializer guards
  for its own package plus the forwarding checks that no manifest target names a flat `_implementing_*` leaf and that
  both historical import sites hand back the owner's exact object, and the dispatch check that the label table and the
  pickup start name the handler owner (`test_imports.py`); the stage scenarios beside it -- fresh runs and parks
  (`test_fresh.py`), timeout disposition and its recovery (`test_timeout.py`), the live-pause guard
  (`test_paused.py`), PR titles / reuse / body capping (`test_pr_*.py`), the retry cap and the locked backend
  (`test_retry.py`, `test_backend.py`), session rotation, staleness, overflow, quota, and silence
  (`test_rotation.py`, `test_stale_session.py`, `test_overflow.py`, `test_session_limit.py`,
  `test_silent_session.py`), a body edit and its continue route (`test_drift*.py`), full-spec persistence
  (`test_full_spec_*.py`), and the terminal arcs (`test_terminal*.py`) -- with shared fixtures in
  `drift_test_support.py`, `fresh_test_support.py`, `pr_test_support.py`, `retry_test_support.py`, and
  `terminal_test_support.py`; the two fixtures the flat suite still shares stay in `tests/`
  (`implementing_fixing_test_cases.py` for the fixing scenarios, `implementing_full_spec_test_support.py` for the
  decomposer full-spec mixin).
  `tests/workflow/stages/documenting/` holds the third stage to arrive: the same import, layering, and initializer
  guards for its own package plus the forwarding checks that no manifest target names a flat `_documenting_*` leaf and
  that both historical import sites hand back the owner's exact object, and the dispatch check that the label table
  names the handler owner (`test_imports.py`); the stage scenarios beside it -- the label bootstrap, detour membership,
  and dispatcher routing (`test_routing.py`), the missing-`pr_number` park (`test_missing_pr.py`), the external-merge
  and human-closed finalizes (`test_external_merge.py`, `test_closed.py`), the fresh pass and the guards that stop it
  short (`test_fresh_outcome.py`, `test_fresh_safety.py`), the recovered-commit push (`test_recovery.py`), the
  awaiting-human resume and the park it wakes from (`test_resume.py`, `test_parked.py`), the refused bare continue
  (`test_continue.py`), the interruption and live-pause returns that write nothing (`test_interrupted.py`,
  `test_paused.py`), the drift unwind and its reconcile failures (`test_drift_route.py`, `test_drift_recovery.py`), and
  the `pr_last_comment_id` ratchet on the handoff with the validating owner its seed walk has to land on
  (`test_final_docs.py`) -- with shared fixtures in `documenting_test_support.py`,
  `documenting_assertion_test_support.py`, `documenting_scenario_test_support.py`,
  `documenting_drift_test_support.py`, and `documenting_drift_recovery_test_support.py`.
  `tests/workflow/stages/validating/` holds the fourth stage to arrive: the same import, layering, and initializer
  guards for its own package plus the forwarding checks that no manifest target names a flat `_validating_*` leaf and
  that both historical import sites hand back the owner's exact object, and the dispatch check that the label table
  names the handler owner (`test_imports.py`); the stage scenarios beside it -- the review loop and its retry caps
  (`test_review.py`), the operator controls and handler-level guards (`test_controls.py`), the live-pause returns that
  write nothing (`test_paused.py`), the approval handoff and its recoveries (`test_handoff.py`), the squash on
  approval (`test_squash.py`), the terminal arcs a merged PR or closed issue earns (`test_terminal.py`), the verify
  gate and the mutations it refuses (`test_verify.py`, `test_verify_refusal.py`), a body edit mid-review
  (`test_drift.py`), the in_review watermark seed across its fresh, consumed, legacy, and review-surface cases
  (`test_watermarks*.py`), and the implementing / publication owners the stage borrows, each pinned by patching the
  owner and the facade name it must not read (`test_owner_boundaries.py`) -- with shared fixtures in
  `validating_review_test_support.py`, `validating_verify_test_support.py`, and
  `validating_boundary_test_support.py`.
- `docs/` — architecture, workflow, and configuration references.
- `run.sh` — production launcher that auto-restarts after self-modifying merges.
- `.env.example` / `.env.example.advanced` — basic and advanced configuration templates; full reference is in
  [`docs/configuration.md`](docs/configuration.md).

## Running and testing

The repo targets Python 3.12+. Local development uses [`uv`](https://github.com/astral-sh/uv) and installs from the
lockfile.

```sh
uv sync --locked                              # creates .venv/ and installs runtime + dev deps from uv.lock
uv run ruff check orchestrator tests          # run Ruff
uv run flake8 orchestrator tests --select=WPS # run wemake-python-styleguide
uv run pytest tests                           # run the test suite
uv run python -m orchestrator.main --once     # one polling tick then exit
uv run python -m orchestrator.main --log-level DEBUG
```

`analytics-db/data/` is the operator-owned Docker bind mount holding the local analytics Postgres volume. It is
runtime state, not source: **never traverse, read, modify, permission-repair, delete, or re-run any command against it
with elevated privileges.** If a tool reports it as unreadable, that is expected — target `tests` explicitly (the
default `pytest` config already ignores the directory) rather than escalating access.

Dev tools (`pytest`, `ruff`, and `wemake-python-styleguide`, which supplies the WPS Flake8 plugin) live in the `dev`
dependency group in `pyproject.toml`; exact versions are pinned in `uv.lock`. CI installs the same set via
`uv sync --locked`.

Tests are the primary correctness gate. Add or update tests for any behavioral change. Prefer extending the in-memory
fakes in `tests/support/github/` over mocking PyGithub directly.

## Code conventions

- **License headers.** Every source file (`*.py`, `*.sh`, `pyproject.toml`) starts with:
  ```
  # Copyright 2026 Geser Dugarov
  # SPDX-License-Identifier: Apache-2.0
  ```
- **Commits.** Conventional Commits: `<type>: <subject>` with types `feat`, `fix`, `chore`, `docs`, `refactor`,
  `test`. Subject line only — no body, no `Co-Authored-By` trailer. Imperative mood, short.
- **Comments.** Sparse — only when the *why* is non-obvious (hidden constraint, race window, GitHub quirk).
- **Dependencies.** `pyproject.toml` pins `PyGithub` and `psycopg[binary]` as runtime deps; `pytest`, `ruff`, and
  `wemake-python-styleguide` live in the `dev` group; the analytics dashboard's `streamlit` and `plotly` live in the
  separate `dashboard` group so the default `uv sync --locked` stays minimal. `uv.lock` is the source of truth for
  exact versions and is committed — regenerate it (`uv lock`) whenever `pyproject.toml` changes. Anything else needs
  justification.
- **Secrets.** `GITHUB_TOKEN` is deliberately *not* loaded from `.env`. Tokens live in
  `~/.config/<owner>/<repo>/token` or the process environment. Rationale:
  [`docs/configuration.md#github-pat`](docs/configuration.md#github-pat).

## Out of scope without explicit ask

- New external dependencies, frameworks, or services.
- Reformatting unrelated files or churning whitespace.
- "Future-proofing" abstractions for hypothetical features. Implement what the issue asks for and stop.

When touching the state machine, agent invocation, or stage handlers, read
[`docs/state-machine.md`](docs/state-machine.md) and [`docs/workflow.md`](docs/workflow.md) first — labels and the
pinned-state JSON schema are part of the public contract that live issues already carry.
