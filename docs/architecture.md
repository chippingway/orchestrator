# Architecture

Single-process **polling orchestrator** that drives GitHub issues through a label-based state machine, delegating coding
work to a configurable coding-agent CLI (`codex` or `claude`) running as a subprocess in isolated git worktrees.

State lives in GitHub: a workflow label exposes the current stage and a pinned JSON comment holds per-issue durable
state. The orchestrator process is stateless and can restart at any time.

This file covers the high-level system: design constraints, the module map, the process model, the agent subprocess
shape, the push path, and the observability surfaces. The per-package inventory under that map lives in the focused
pages below it, [`architecture/platform-modules.md`](architecture/platform-modules.md),
[`architecture/workflow-modules.md`](architecture/workflow-modules.md), and
[`architecture/observability-modules.md`](architecture/observability-modules.md). The label set, per-stage
internals, per-tick flow, and pinned-state schema live in [`state-machine.md`](state-machine.md) and the focused
pages under it; agent roles, conversation contracts, and command-spec semantics live in
[`workflow.md`](workflow.md) and the focused pages under it.

## Design constraints

GitHub Issues are the orchestrator's task tracker and durable state surface. The process intentionally avoids an
internal database: workflow labels expose the current stage, and the pinned JSON comment holds the per-issue state that
the next tick needs. This keeps progress visible to humans on github.com and lets the process restart without
reconstructing hidden local state.

The orchestrator is not fully autonomous. When a stage hits uncertainty, an unsafe repository state, a malformed agent
response, or an exhausted retry cap, it parks with `awaiting_human` and mentions `HITL_HANDLE`; a later human issue
comment is the resume signal for the parked agent session.

The workflow is deliberately fixed instead of planner-selected: decomposition, implementation, validation, and
acceptance are mandatory phases. Routing is explicit and label-driven.

Agents run on the host as CLI subprocesses with broad local permissions
(`codex --dangerously-bypass-approvals-and-sandbox`, `claude --dangerously-skip-permissions`). The host, container, or
VM around the orchestrator is therefore the real sandbox boundary; token handling and hardened git operations are
designed around that assumption.

## Top-level layout

A responsibility answers on the owner module that defines it and nowhere else — the workflow package, the whole
analytics tree, and both Streamlit pages included — so a patch targets that module and there is no second site a mock
could be left on. Where a leaf does resolve a name at call time it is to read a knob rather than to borrow a helper,
off the one holder every owner that reads it resolves through. Each of those boundaries is named where its owner is
described, on the pages named below.

A bare tag — `implementing`, `fixing`, `validating` — names the *stage*: the handler and the subpackage holding it,
mapped in [`architecture/workflow-modules.md`](architecture/workflow-modules.md). For a stage the orchestrator labels
itself, the GitHub label an issue carries is a different string, spelled `workflow:<tag>` here and everywhere else in
these docs. `in_review`, `question`, `discussion`, and
the `done` / `rejected` terminals were never namespaced, so for those the two coincide; see
[Workflow labels](#workflow-labels).

The map is split by area, and each page below is where the owners of the packages it names are described:

- [`architecture/platform-modules.md`](architecture/platform-modules.md) — the package root and both launch forms,
  `runtime/`, `config/`, `github/`, `agents/`, `scheduler/`, `git/`, and `skills/`.
- [`architecture/workflow-modules.md`](architecture/workflow-modules.md) — `workflow/`: the package API and the state
  owner beside it, the `engine/` owners one tick is composed of, and the nine stage subpackages the label dispatch
  routes into.
- [`architecture/observability-modules.md`](architecture/observability-modules.md) — `observability/`: the analytics
  sink and everything downstream of it, the usage parser, the Streamlit analytics page, and the file-backed
  trajectory viewer, together with the two `streamlit run` targets under `apps/` that compose the pages.

The rules under the map hold for the whole tree, the packages on those pages included.

```
orchestrator/
  __init__.py           the package version and the `__all__` naming it, bound
                        here so `import orchestrator` costs no owner behind it
  cli.py                `agent-orchestrator` console-script entry point and
                        the polling process's composition point
  __main__.py           `python -m orchestrator` launch form over `cli.main`;
                        the target `run.sh` launches
  runtime/              the polling process's own owners: the state one run
                        carries, the log destinations, startup, one pass over
                        the configured repos, the polling loop, the
                        self-restart probes, and shutdown
  config/               the bottom layer: the non-secret `.env` loader, the
                        env parsers and resolver behind the settings surface,
                        credential resolution and secret redaction, and the
                        repository-config types
  github/               the composed `GitHubClient` and the pinned durable-
                        state model over one owner per GitHub surface: issues,
                        labels, comments, pull requests, reviews, checks, and
                        audit events
  agents/               the agent-CLI subprocess layer: shared dispatch and its
                        result models, credential filtering, session parsing,
                        the process registry, and one module per backend
  scheduler/            the `IssueScheduler` every tick shares and the typed
                        submissions it takes
  workflow/             the state machine: the label vocabularies and the
                        transition guard, the `engine/` owners one tick is
                        composed of, and nine stage subpackages holding the
                        twelve labelled handlers the dispatch routes into
  git/                  local git: execution, locks, and authenticated
                        transport, under the worktree lifecycle, the per-tick
                        base sync, branch publication, and verify runs
  observability/        the four surfaces that watch a run without steering
                        it: the analytics sink and everything downstream of
                        it, the parser that meters one finished agent run, the
                        Streamlit page over the operator's Postgres target,
                        and the file-backed trajectory viewer beside it
  apps/                 the two Streamlit pages a `streamlit run` names; the
                        polling loop is launched at cli.py instead
  skills/               the two skill-enumeration owners: the per-tick repo
                        catalog and the per-run local discovery it reads its
                        marker back off
```

Five rules hold for the tree as a whole, each with a check under `tests/repository/` that finds its subjects on disk so
a module added anywhere is covered the day it lands. The root is the three files above plus the ten packages under
them, held to that exact inventory: a module parked beside them would be importable next to the package that owns the
responsibility, and both would answer. No module wears one of the retired domain families as a prefix. Every family is
forbidden in the private spelling its compatibility leaves carried (`_dashboard_read_core.py`), and the families whose
word names a domain package and nothing else — `dashboard_`, `workflow_`, `git_`, `state_machine` — in the public
spelling as well, so `workflow_state.py` fails one level down exactly as it would at the root. A word that also names a
responsibility *inside* a package keeps its public spelling: `charts/usage_axis.py` and `usage/trajectory_models.py`
are owners under the family's own package rather than that family flattened out of it. Nothing is named for an
inventory of names either — `exports.py`, `manifest.py`, `compatibility.py`, whole or as the tail of a prefixed one,
the decomposer's output manifest excepted — and nothing carries a `.pyi` stub or a module-level `__getattr__` /
`__dir__`: a re-export is the owner's own object bound at import, so a lookup lands on the module that defines the name
rather than on something answering for it.

Imports run one way through four layers — `config/` at the bottom, the domains that do the work above it, `workflow/`
deciding with them, and `cli.py` / `__main__.py` / `runtime/` / `apps/` composing the lot. The direction is read
twice, because deferring an import weakens where it lands but not whether it belongs. At module scope, where an import
decides what a package costs to load and whether it can be loaded at all, nothing points up but `workflow/state.py` —
named exactly, and only by the two layers its labels type, `github/` and `git/`. Over every scope, the only reaches
left are declared one by one in `tests/repository/test_layering.py`: three base-sync owners posting a notice or a park
through the workflow's comment and guard owners, deferred to a call because at module scope they would be a cycle. An
undeclared hop fails wherever it is written, and a declared one fails if it is bound at module scope after all. The
launch forms compose each other and are reached from nothing below them at any scope, and no import anywhere is
relative, because a relative target names its module by position and no layer can be read off it. And a package either
publishes an explicit `__all__` of its owners' own objects, with nothing else of the package's own left in its
namespace beside it, or fronts nothing and imports nothing at all — the submodules on a marker package are what other
modules' imports planted there, not what its initializer loaded, so naming the package costs no owner behind it. That
second half is read from the initializer's source, because the namespace cannot tell an eager sibling import from
somebody else's; what an initializer imports from outside the package for its own use is a helper rather than a
surface, and is held to neither. The eight that publish are listed under
[`configuration/operations.md#continuous-integration`](configuration/operations.md#continuous-integration), where each
is also a scoped lint waiver.

The test tree mirrors this one, and two more checks hold it there: every package above has a mirrored tests package,
and every directory the suite collects from carries an initializer of its own, with nothing at the tests root but the
suite-wide fixtures. The mirror is why the same short module name recurs once per domain — one `test_imports.py` per
package — and those initializers are what keep the recurrences distinct at collection.

## Workflow labels

An issue should have at most one workflow label at a time. The set is `workflow:decomposing`, `workflow:ready`,
`workflow:blocked`, `workflow:umbrella`, `workflow:implementing`, `workflow:documenting`, `workflow:validating`,
`in_review`, `workflow:fixing`, `workflow:resolving_conflict`, `question`, `discussion`, and the two terminals
`done` / `rejected`.
The `workflow:` prefix marks what the orchestrator writes itself, so a repository's own vocabulary cannot collide with
it; the five states a human also applies or reads on their own keep the bare spelling. The orchestrator also creates
three non-workflow control labels: `backlog` and `paused` each make per-tick handlers skip the issue entirely
(`backlog` is a "not yet" hold on a fresh issue, `paused` freezes an in-flight one), and
`workflow:community_contribution` is applied by the per-tick open-PR sweep to PRs from non-bot authors outside
`ALLOWED_ISSUE_AUTHORS` so a human reviews them. The two an operator types stay bare; the one the sweep applies is
namespaced on the same rule as the states. Both sets above are closed, and `WorkflowLabel` / `ControlLabel` membership
is what closes them rather than the prefix: a `workflow:`-prefixed name outside them — Dependabot's service labels on
its own update PRs — is not a state, routes nowhere, and survives a label write untouched.

The namespace is a GitHub label spelling and stops at that boundary, which is the distinction the stage map in
[`architecture/workflow-modules.md`](architecture/workflow-modules.md) reads by: a bare tag there names the *stage* —
the handler, the subpackage under `orchestrator/workflow/stages/` holding it, and the identifier analytics rows, audit
event payloads, and agent-session attribution have always carried — while the wire label an issue carries is spelled
`workflow:<tag>`. `workflow/state.py` owns both directions:
`stage_name` strips the prefix for those sinks, and `label_for_name` resolves either spelling back to its member.

A repository whose labels predate the namespace is migrated by the startup label bootstrap. Of a namespaced label it
asks a three-way question: where only the pre-namespace spelling exists it is renamed in place rather than
duplicated, so every issue holding it moves across in one edit; where the namespaced label already exists the
bootstrap does nothing and leaves any bare label beside it defined; where neither exists the namespaced one is
created. The seven never-namespaced labels have no second spelling to migrate off and are simply created bare when
missing. Wherever that rename does not run, three reads still take the bare spelling: issue routing, the community
sweep's dedup marker, and the closed-issue sweep's query. A namespaced label outranks a pre-namespace one on the same
issue, and a label write takes off only what it owns, so a bare `blocked` or `ready` the repository uses for its own
triage survives a relabel; see
[`state-machine/labels-and-state.md`](state-machine/labels-and-state.md#legacy-labels-and-the-migration-off-them).

Label names are part of the public contract because live GitHub issues already carry them. For the meaning of each
label, the control-label semantics, and the per-stage transitions they trigger, see
[`state-machine/labels-and-state.md#workflow-labels`](state-machine/labels-and-state.md#workflow-labels).

## Process model

There is **only one long-lived process**: `python -m orchestrator`. It is wrapped by `run.sh` so the loop can
self-exit and be restarted with new code.

- **Trigger**: started manually (or by a wrapper). Optional `--once` for a single tick.
- **Tick cadence**: every `POLL_INTERVAL` seconds (default 60).
- **Self-restart guard** (`runtime.self_update.self_modifying_merge_happened`): each tick fetches
  `origin/<ORCHESTRATOR_BASE_BRANCH>` (default `main`); if it advanced past the process's startup SHA *and* the new
  commits touch `orchestrator/`, the loop
  exits 0 so the wrapper can re-exec the new code. The branch is decoupled from `BASE_BRANCH` so a target repo with a
  different default branch does not interfere with self-update detection.
- **Self-update resilience** (`run.sh self_update`): before each launch — at startup and after every
  self-modifying-merge restart — the wrapper fast-forwards the orchestrator checkout to
  `origin/<ORCHESTRATOR_BASE_BRANCH>`. It skips the pull and warns to stderr if a non-base branch is checked out, and
  warns and continues (rather than exiting) if the fast-forward fails (diverged base branch, rebase in progress, network
  error); either way it launches the existing working tree. A clean fast-forward still updates the tree before launch,
  so the self-modifying-merge flow keeps picking up new code. This is deliberate: under the production systemd unit
  (`Restart=always`) exiting on a self-update failure silently crash-loops the service with the orchestrator never
  running, so a stale-but-running process plus a journal warning is preferred — the warning is the operator's signal
  to restore the checkout.
- **Signals**: SIGINT/SIGTERM set a flag and call `scheduler.shutdown(wait=False)` synchronously so the submit path is
  closed mid-tick; the loop then stops at the next tick boundary and drains. The drain terminates in-flight agent and
  verify subprocess groups up front (`agents.terminate_all_running`) so a worker parked in a long agent / verify run
  unwinds in seconds instead of holding the process for up to `AGENT_TIMEOUT`. A daemon watchdog backstops the drain: if
  it overruns, the watchdog terminates those same groups and hard-exits (`os._exit(128+signum)`) so total signal→exit
  stays within `SHUTDOWN_GRACE_SECONDS` no matter what a thread is blocked on. A second Ctrl+C hits the re-armed kernel
  default handler and kills immediately.

The coding agent runs as a **transient child subprocess**, not a daemon — spawned per tick when work is needed.

## Per-tick flow (`workflow.tick`)

Each tick the polling loop fans `workflow.tick(gh, spec, scheduler=...)` out across **every configured repo** via
`runtime.ticks.run_tick`: single-repo deployments stay in-thread, multi-repo deployments use a `ThreadPoolExecutor`
sized to the repo count. A single long-lived `IssueScheduler` (global cap `MAX_PARALLEL_ISSUES_GLOBAL`, per-repo cap
`MAX_PARALLEL_ISSUES_PER_REPO`) is shared across all `tick` calls.

One repo's pass is owned by `workflow/engine/tick.py` — the base refresh, the community-contribution PR sweep, the
skill-catalog emission, and then either the scheduler handoff or the in-tick sequential / bounded-parallel loop, in
that order (see [the owner's paragraph](#top-level-layout) above for why each step depends on the one before it).

The dispatch loop classifies each issue as family-aware (`workflow:decomposing` / `workflow:blocked` /
`workflow:umbrella` / unlabeled — parent ↔ child writes) or fan-out (everything else). Fan-out submits go one callable
per issue. Every family-aware issue this tick is folded into ONE bucket submit per repo that drains them sequentially
on a single executor worker so a stale child cannot starve the parent umbrella issue. When every family-aware issue in
the bucket runs a no-agent handler (`workflow:blocked` or `workflow:umbrella`), the bucket is cap-exempt and runs on a
dedicated executor pool so a pure label / dep-graph walk cannot be blocked by ordinary implementation work. A bucket
containing `workflow:decomposing` or unlabeled pickup stays cap-counted.

Per-issue durable state lives in a single **pinned comment** on the issue (`<!--orchestrator-state {...json...}-->`).
The orchestrator process is stateless; the label and the pinned JSON are the entire dispatch input.

For the full per-tick sequence (eligible-issue enumeration, family vs. fan-out partitioning, the pre-PR rebase /
PR-having clean-rebase + push (with `workflow:resolving_conflict` reached on actual rebase conflicts, plus the
`fixing` worktree-drift dead-lock breaker that hands a stuck validating-route transient fix-loop to
`workflow:resolving_conflict` when the worktree is behind base or carries an unpushed rebase), the read-only skip
the `question` and `discussion` labels take (and the parks and in-flight discussion records that keep taking it after
the label is gone), the per-tick external-merge sweeps, and the complete pinned-state JSON schema), see
[`state-machine/labels-and-state.md#per-tick-flow-workflowtick`](state-machine/labels-and-state.md#per-tick-flow-workflowtick).

## Stage handlers

Each workflow label dispatches to a `_handle_<label>` function. Every handler lives under
`orchestrator/workflow/stages/` (mapped in
[`architecture/workflow-modules.md`](architecture/workflow-modules.md)), and the dispatcher reaches one by importing
the module its label is paired with in `_STAGE_HANDLER_TARGETS` and reading the handler off it, so a patch that has to
intercept the dispatch targets that module. A stage-to-stage call names the owner the same way: the decomposition
disabled-rollout and `ready` paths name `stages/implementing/handler.py` for `_handle_implementing`, so a patch that
has to intercept the implementation a `single` verdict routes to targets that owner.

`orchestrator/workflow/stages/` holds every stage -- `decomposition`, `implementing`, `documenting`, `validating`,
`in_review`, `fixing`, `conflicts`, `question`, and `discussion` -- each as a subpackage of responsibility-named
owners. Nothing
answers for a stage beside them, so a name a stage owns has one module to resolve on and a `patch.object` there is the
only interception a caller can need. Two checks in `tests/workflow/stages/test_imports.py` hold that line for every
stage at once: `orchestrator.stages` resolves to nothing the interpreter would find, and every label in
`_STAGE_HANDLER_TARGETS` names an owner inside a stage subpackage here — so a stage arriving later is covered without
anyone adding it there. Dispatch names the owners too: `_STAGE_HANDLER_TARGETS` names the module a handler lives on,
and so does the same-tick start in `workflow/engine/pickup.py`, so a patch meant to intercept a dispatched handler has
to land on the owner. Like `workflow/engine/`, this package and each stage subpackage inside it bind nothing in their
initializers -- the dispatcher resolves one handler per issue, so an eager binding there would charge that import for
every other stage's leaves and for the worktree and GitHub subsystems they reach.

The decomposition owners bind their collaborators directly. `manifest` calls `validation` for the split rules, `run`
calls `session`, `recovery`, and `outcomes` for the order a tick asks them in, `outcomes` calls `manifest` and
`split`, `blocked` and `umbrella` both call `parents` for the child scan and `activation` for the dep-graph walk, and
every owner that writes to GitHub reaches `workflow/engine/` for the comment poster, the run guards, the prompts, and
the usage counters. `state`, `models`, `manifest`, and `validation` deliberately reach nothing — the keys, the
carriers, and the whole parse are decidable without a client, which is why the manifest rules can be exercised without
one. So a patch that has to intercept the manifest parse, a child scan, or the split writer targets the owner module.
What the stage does not own it names on the owner that does: `models`, `run`, and `session` reach
`git.worktrees.decomposition` for the scratch checkout's path, creation, and removal, `run` reaches
`git.worktrees.creation` and `git.verification.probes` for the read-only commit and dirty probes, and `run`,
`blocked`, and `session` reach `stages/implementing/` for the handler a `single` verdict routes to and the retry
budget a fresh spawn consumes — so a mock for any of those lands on the owner. No flat module sits beside these
owners: the `orchestrator.stages` check in `tests/workflow/stages/test_imports.py` covers this stage too, so the
manifest parse, the child scan, the split writer, and all four dispatched handlers are each answered on an owner
alone. `_MAX_CHILDREN` runs the other way: the cap lives with the validator that rejects past it and
`workflow/engine/prompts.py` reads it back, so the bound the decomposer is told and the bound it is judged against
cannot drift apart.

The implementing owners bind their collaborators the same way, and they divide along the decisions one tick makes
rather than the code it runs. `handler` holds the order those decisions are asked in and calls `read_only_relabel` and
`continue_command` for the two preflight signals, `drift` for a body edit, `spawn` for the run itself, and
`disposition` for what the run left behind. `spawn` asks `session` for the retry budget and `drift_preflight` for the
awaiting-human route; `resume` and `execution` split one resume between the call shape callers wrote against and the
attempt-and-retry behind it, over `session` for retirement and `worktree` for the checkout; `disposition` routes a
committed tree to `publication` and everything else to `parks`. `state`, `models`, and `session_read` reach no engine
owner, no GitHub client, and no worktree helper — `session_read` reads the configured agent spec and nothing else —
which is why the pinned-state keys, the carriers, and the CLI-marker classifiers can be exercised without a client. So
a patch that has to intercept a park, a push, a resume, or a session read targets the owner module. The helpers the
stage does not own are named the same way: the branch and worktree names from `git/worktrees/paths.py`, the checkout
and its commit probe from `git/worktrees/creation.py`, the unpushed-branch and branch-tip probes from
`git/worktrees/recovery.py` (the second is how the read-only relabel guard measures a branch against the SHA a
discussion round recorded, which ahead-of-base cannot answer), the
HEAD and dirty reads from `git/verification/probes.py`, the push from `git/authentication.py`, the commit subject and
the PR title builders from `git/publication/`, and the auto-rebase park reasons from `git/base_sync/state.py` — so a
patch on any of those lands on the owner that defines it. No flat module
sits beside these owners: the `orchestrator.stages` check in
`tests/workflow/stages/test_imports.py` covers this stage too, so the dev session, the retry budget, and the park
reasons are each answered on an owner alone — including for the sibling stages that borrow the resume, the session read,
and the question / dirty-tree parks from here.

The documenting owners divide by what one final-docs tick has to settle before it may spawn. `handler` asks
`preconditions` first for the checks that end the tick outright — the PR-merged and issue-closed terminals, the
missing-`pr_number` guard, and the bare `/orchestrator continue` refusal — then `drift` for the one that unwinds
instead, then `preconditions` again for the parked-no-input fast path, and only then `run` for the pass and `outcomes`
for what it left behind. `drift` hands the git half to `drift_reset`, which fails closed on every fetch, probe, reset,
and clean because a docs commit left on disk against the old body is what the next tick's recovered-commit shortcut
would push unreviewed. `outcomes` routes a commit or a confirmed `DOCS: NO_CHANGE` to `publication` and everything else
to `parks`, and `publication` calls `handoff` for the `pr_last_comment_id` ratchet that has to precede the `in_review`
relabel. `state` and `models` reach nothing, so the wire keys and the carriers are decidable without a client. This
stage owns no dev session of its own: the resume, the session read, and the question / dirty-tree parks are imported
from `workflow/stages/implementing/` directly, and the `pr_last_comment_id` seed walk from
`workflow/stages/validating/watermarks.py`, so a patch that has to intercept one lands on that owner. The git it
runs on is named the same way — the PR-aware creator and the worktree path off `git/worktrees/`, the HEAD and dirty
reads off `git/verification/probes.py`, the fetch and the push off `git/authentication.py`, the hardened runner off
`git/commands.py`, the ahead/behind read off `git/publication/probes.py`, and `_AUTO_REBASE_PARK_REASONS` off
`git/base_sync/state.py`. That
last one is why both precondition reads consult it before they act: a park the pre-tick refresh owns is one whose
retry nudge belongs to `_sync_pr_worktree_to_base`, so the docs stage stays silent rather than answering a comment
addressed to the rebase loop. No flat module sits beside these owners: the `orchestrator.stages` check in
`tests/workflow/stages/test_imports.py` covers this stage too, so the awaiting-human flag, the last-action comment id,
and the park reasons are each answered on an owner alone, `_handle_documenting` included.

The validating owners divide by what one review tick is answering, since the reviewer is only part of what the stage
runs. `handler` opens with the terminals and then holds the order — drift, the awaiting-human park, the reviewer round
— and hands the spawn itself to `reviewer`, which asks `requested_changes` for the round-cap park, meters the run
through the engine's tracked spawn, and fans the verdict out to `approval`, `requested_changes`, or the no-VERDICT
park. `approval` calls `git.verification.runner._run_verify_commands` directly for the gate, `verify` for the park a
non-ok result earns, and `watermarks` for the seed walk that keeps the docs hop and in_review from replaying the
orchestrator's own comments. Between rounds the stage is a dev-fix driver: `awaiting` / `awaiting_resume` (a park a
human replied to), `drift` / `drift_outcomes` (a body edit mid-review), and `recovery` (the parks that clear without
a human) all dispose through `dev_fix`, so the stranded-commit gate, the push, and the `review_round` bump cannot
drift apart between routes. `state`, `models`, and `watermarks` reach no worktree helper, so the wire keys, the
carriers, and the whole seed walk are decidable without one. So a patch that has to intercept a park, a push, the
verdict fan-out, or the watermark seed targets the owner module. This stage owns no dev machinery either: like
documenting it imports the resume, the session read, and the question / dirty-tree parks from
`workflow/stages/implementing/` directly, and the squash from `git/publication/squash.py`, so a patch on one of those
lands on the owner that defines it. The helpers it does not own are
named the same way — the branch and worktree names and the checkout from `git/worktrees/`, the HEAD and dirty reads
from `git/verification/probes.py`, the fetch and push from `git/authentication.py`, the ahead/behind measurement from
`git/publication/probes.py`, and `_AUTO_REBASE_PARK_REASONS` from `git/base_sync/state.py`, so a patch on any of them
lands on the owner too. No flat module sits beside these owners: the
`orchestrator.stages` check in `tests/workflow/stages/test_imports.py` covers this stage too, so the reviewer round, the
parks, and the watermark seed are each answered on an owner alone. The six names sibling stages borrow —
`_post_user_content_change_result`, `_handle_dev_fix_result`, `_stranded_fix_unpushed`,
`_try_recover_validating_transient_park`, `_VALIDATING_TRANSIENT_PARK_REASONS`, and `_latest_pr_comment_ids` — are
each named on the owner by the caller that borrows it: in_review's and resolving_conflict's
drift routes for the first, fixing's resume and parked owners for the next four, documenting's final-docs handoff for
the last.

The in_review owners divide by the four answers one tick can reach, and `handler` holds the order because the order is
the contract rather than a style choice. `feedback` runs before `drift`: `user_content_hash` covers every human
issue-thread comment as well as the body, so asking drift first would resume the dev over a review comment that should
have been bookmarked and handed to `fixing`. `feedback` routes through `fixing_route` for the flip, and the bookmarks
it writes are deliberately not watermarks — the fixing handler re-reads the same comments to build its prompt. `drift`
reads the PR conversation before the ratchet can leap past it, resumes the dev, and hands both outcomes back to
`workflow:validating` with `review_round` reset. `merge_gate` is last and never merges: an unmergeable PR parks for a
human (no `workflow:resolving_conflict` route from this stage) and a mergeable, approved, unvetoed head earns one HITL
ping per head SHA. `models` and `state` reach nothing at all and `watermarks` reaches no further than the client it is
handed, so the carriers, the wire key, and both the ratchet and the legacy seed are decidable without a worktree or an
agent. So a patch that has to intercept the scan, the route, the resume, or the ping targets the owner module. This
stage owns no dev machinery either: the resume comes from `workflow/stages/implementing/` and the body-edit
disposition from `workflow/stages/validating/drift_outcomes.py`, so a patch on one of those lands on the owner. The
helpers it does not own are named the same way — the worktree names from `git/worktrees/paths.py`, the checkout from
`git/worktrees/creation.py`, the HEAD read from `git/verification/probes.py`, and base-sync's
`_AUTO_REBASE_PARK_REASONS` from `git/base_sync/state.py`, which is what tells a park the rebase loop owns from one
this stage may answer. No flat module sits beside these owners: the `orchestrator.stages` check in
`tests/workflow/stages/test_imports.py` covers this stage too, so the feedback scan, the fixing route, the drift
resume, and the merge ping are each answered on an owner alone. `_comment_created_at` is the one name a sibling
borrows, and its one cross-package caller — fixing's quiet window — names `watermarks` itself.

The fixing owners divide by what one tick has to settle, and two of them exist as a pair because the batch that starts
the loop is not the batch that ends it. `feedback` scans forward from the three in_review watermarks; `bookmarks`
rebuilds backward from the `pending_fix_*` ids the in_review route recorded. Both are needed because the first dev
resume advances those watermarks past the triggering feedback, so once a fix has been attempted the batch a
`/orchestrator continue` must replay can only come from the ids. `feedback` also owns the ratchet, deliberately
narrower than `_bump_in_review_watermarks`: it advances each surface only to the max id actually quoted in the prompt,
on the pushed path and the park path alike, so a comment that landed mid-tick survives to the next one.
`continue_command` is the only caller that rebuilds a batch, and the only one that answers with a refusal instead of a
run. `parked` is the dispatcher for an `awaiting_human` tick and the order is the contract: the base-sync retry loop's
own parks are refused first and silently, then the explicit operator command, then the silent recovery — which fires
only on the validating route, because `review_round` accounting and watermark advancement differ between the two and
`pending_fix_at` is what tells them apart. `drift` is the exit from a stuck validating-route transient park whose
worktree has fallen behind base, and it exists because the per-tick base sync stands down on every park, so nobody
else will rebase it. `resume` owns the quiet window, the run, the interruption and live-pause refusals that write
nothing, the ACK fast path, and the `workflow:validating` relabel a pushed fix earns. `models`, `state`, and
`bookmarks` reach no further than the client they are handed, so the carriers, the wire keys, and the whole
reconstruction are decidable without a worktree or an agent. So a patch that has to intercept the rescan, the replay,
the parked dispatch, the reroute, or the run targets the owner module. This stage owns no dev machinery either: the
resume and the poisoned-session drop come from `workflow/stages/implementing/`, the dev-fix disposition, the
stranded-fix probe, and the transient-park recovery from `workflow/stages/validating/`, and the comment timestamp the
quiet window measures from `workflow/stages/in_review/watermarks.py` — so a patch on any of those lands on the owner.
The git it runs on is named the same way — the worktree path and the branch resolver off `git/worktrees/paths.py`, the
creator off `creation`, the HEAD and dirty reads off `git/verification/probes.py`, the plain runner behind the
behind-base probe off `git/commands.py`, and `_AUTO_REBASE_PARK_REASONS` off `git/base_sync/state.py`. No flat module
sits beside these owners: the `orchestrator.stages` check in `tests/workflow/stages/test_imports.py` covers this stage
too, so the pending-fix bookmarks, the review-round counter, and the park reasons are each answered on an owner alone,
`_handle_fixing` included.

The conflicts owners divide by what one tick has to establish before the rebase may run and by what it does with the
result, and `handler` holds the order: the pinned `pr_number` (without one the label can only have come from a manual
relabel), then the terminal arcs, then the body edit, then `routing` for the awaiting-human resume and the
`MAX_CONFLICT_ROUNDS` cap. `guards` and `divergence` are a pair around one decision — whether a worktree behind its
remote PR head may be published at all — and both halves fail closed: the refuse-and-park default holds unless
`guards` can prove the worktree is already on the current base AND the head it is behind is one the orchestrator
recorded, in which case `divergence` returns a lease pinned to that exact SHA so a foreign push landing mid-tick is
refused rather than overwritten. `rebase` owns the two fetches, the rebase, and the `merge_attempt` event; publishes a
clean one through `publication`; and hands real conflicted files to the dev. `resume` is the single entry point all
three dev resumes go through, and `outcomes` reads what one left behind in the order that matters — interruption,
timeout, and mid-rebase all precede any HEAD comparison. `transitions` exists because every state-changing exit shares
one of two shapes, a park plus its pinned-state write or the full pushed-round tail, and this stage has eleven of the
first and five of the second. `state` and `models` reach nothing, so the counter keys and the carriers are decidable
without a client. So a patch that has to intercept the divergence verdict, the rebase, a park, or a resume targets the
owner module. This stage owns no dev machinery either: the resume and the question / dirty-tree parks come from
`workflow/stages/implementing/`, the body-edit disposition from
`workflow/stages/validating/drift_outcomes.py`, and the auto-rebase park reasons from `git/base_sync/state.py` — so a
patch on any of those lands on the owner. The git it runs on is named the same way — the worktree path and the branch
resolver off `git/worktrees/paths.py`, the PR-aware creator off `creation`, the HEAD and dirty reads off
`git/verification/probes.py`, the fetches and the leased push off `git/authentication.py`, the plain and hardened
runners off `git/commands.py`, the ahead/behind read off `git/publication/probes.py`, and the base rebase and its
in-progress probe off `git/base_sync/pre_pr.py`. No flat module sits beside
these owners: the `orchestrator.stages` check in `tests/workflow/stages/test_imports.py` covers this stage too, so the
round counters, the divergence lease, and the park reasons are each answered on an owner alone,
`_handle_resolving_conflict` included.

The question owners divide by what one tick has to decide, and the read-only contract is what shapes the split.
`handler` holds the order — the closed-issue finalize outranks everything, then the run, then its disposition — and
owns both worktree teardowns, because the scratch checkout this stage never pushes has to disappear on the terminal arc
and on every safe exit alike, including the ones that raise. `run` picks between the two shapes a tick can take (an
`awaiting_human` resume on a human reply, or the conversation's first spawn), owns the tracked spawn they share, and
owns the park funnel every exit lands on — a funnel that exists because the shared park helper clears `park_reason` and
the stage-specific one has to be restored after it, or the implementing relabel guard loses the `question_` prefix it
refuses on. `session` is the locked identity that keeps a multi-turn Q&A on one backend, and both prompt builders sit
there because the resume degrades to the first-round prompt when no session id survived. `outcomes` is where the
read-only contract is enforced: new commits and a dirty tree are inspected before interruption and before the answer,
and both park with the worktree kept, so a misbehaving run leaves an inspection target. `state` and `models` reach
nothing, so the park reasons, the wire keys, and the carriers are decidable without a client. So a patch that has to
intercept the spawn, a park, the assessment, or a teardown targets the owner module. The stage owns no agent or
worktree machinery: the tracked spawn, the awaiting-human park, the prompt builders, the trusted conversation text, and
the stderr diagnostics come from `workflow/engine/`, and `_cleanup_question_worktree` from
`git/worktrees/terminal.py` — the last one matters because a mock aimed anywhere else would let a real teardown
run. The rest of the worktree surface is named the same way:
`_worktree_path` and `_resolve_branch_name` on `git/worktrees/paths.py`, `_ensure_worktree` and `_has_new_commits` on
`git/worktrees/creation.py`, and `_worktree_dirty_files` on `git/verification/probes.py` — the last two are what the
read-only contract is decided by, so a mock for either has to land there. No flat module sits beside these owners: the
`orchestrator.stages` check in
`tests/workflow/stages/test_imports.py` covers this stage too, so the session lock, the parks, and the wire keys are
each answered on an owner alone, `_handle_question` included.

The discussion stage divides the same way the question stage does, because it is the same shape of conversation held
to a stricter contract: until a human says the two sides understand the design the same way, the agent may not write
anything AND may not decide anything. `handler` holds the order -- `terminal`'s poll of an issue whose plan is
already published (the record its own publication left, read as a pair with `pr_number` so a dev's inherited PR is not
mistaken for one), the
gate that makes a discussion-owned park the humans' turn (a park any other stage wrote does not gate, or an issue
relabeled here while parked elsewhere would stay inert for good), the trusted reply that ends that turn, the two
preflights on what the last round left, then the round and its disposition -- and it is where the stage stops, since
no route from here reaches another stage. `session` is what keeps a multi-round conversation on one
agent: the pinned spec and session id every round after the first is read back from rather than re-resolved, the one
filter both the prompt and the consumed watermark are drawn through (so neither an untrusted reply nor the stage's own
posted analysis can steer the agent or be recorded as read), and the degrade from the followup prompt to the full one
for a round with no session to resume -- since `_run_agent_tracked` starts a fresh agent then, and a bare quote of the
reply would reach it with no design attached. That rebuild is also where the stage's own analyses are retained past
the allowlist by their recorded ids, since a deployment listing its humans and not its bot account would otherwise
hand a fresh agent the answers without the questions -- and it reads the thread ONCE, handing back the replies its
text quoted alongside the text, because a ceiling derived from a second read disagrees with the prompt by whatever
landed between the two. Reading the replies and consuming them are separate calls with the round's provenance write
between them, which is what leaves a reply unconsumed when the tick declines to spawn on it
-- or dies before its disposition, so the next process replays the round against the same answer. What is consumed is
measured over what the round's own prompt was built from and never over the thread as the park finds it, because
minutes of agent run separate the two and a comment that lands in them is one this stage would otherwise read never;
recognizing its own comments without a watermark above them is what `engine/comments`' id list and body marker are
for, and why neither reader here matches on author login. `run` opens the round in the issue's own
`issue-N` worktree -- reusing the tree its predecessor read whenever it is still there -- and owns every probe of it:
the pre-`_ensure_worktree` dirty read, because preparing the checkout force-removes a dirty tree that carries no
commits; the pre-spawn `_head_sha`, because the branch may already carry another stage's commits; and the same
question asked a tick late for a round that never got to answer it -- or asked of a parked issue a reply has just
arrived on, where a tree off the anchor or holding edits stops the round: reported once when the standing park said
nothing about repairing it, and held in silence when that park already carried the paths and the reset command. That
last one is why the SHA is written down before the spawn
rather than only held: a mid-run `paused` suppresses every disposition by contract and a crash takes them with it, and
the next tick reuses the same checkout, so an anchor is the only thing that can tell a commit the ended round made
from one the branch arrived carrying. `discussion_session_id` and the consumed watermark are staged after that write
instead and ride the park's, so a round nobody sees leaves no conversation pointer and consumes no answer. `outcomes`
enforces the write contract on the round
that does come back, checking commits and the dirty tree before interruption and before the response, so a round that
wrote is judged on what it wrote rather than published as a design. What a commit means is `publication`'s to answer:
one reading of the branch -- whether its tree could be read and is clean, what its commits change against the base
commit the round pinned before it spawned, and whether the plan is in HEAD as a regular file at all, since a
deletion changes exactly
the path an addition would -- decides between the agreed plan, which is pushed and opened as a PR, and everything
else, which parks with that reading quoted. Who may reach it is the other half of the answer. The disposition of the
round that committed and the preflight that finds a commit a round never got to report both hold a commit the anchor
attributes to a round of this stage. A parked issue holds nothing of the kind on its face -- its round is over, and a
plan-shaped commit appearing afterwards is somebody else's -- so two records say when it does.
What the push is allowed to overwrite is read before it runs. The lease is pinned to the tip the remote was just
observed at, and what makes that tip publishable is whether the commit being published CONTAINS it (`_commit_contains`):
a branch the remote does not have yet is the ordinary first publication, and every other tip has to be an ancestor of
the plan commit, which a replay after a crash and an inherited PR branch the plan sits on top of both are. A lease
cannot answer that -- it proves the ref has not moved, not that what is on it survives -- so a round that reset an
inherited branch to base before committing its plan would pass every other reading and delete the PR's history.
Anything else is somebody's own write to that branch -- a reviewer amending the plan on
its PR while a publication of it is unfinished -- and parks `discussion_push_failed` naming it. Pinning is what makes
the reading hold: `_push_branch`'s own `ls-remote` fallback would adopt whatever the remote had become as the value it
may clobber, so a publication being retried after a crash would send its older validated commit straight over that
write. The refusal is taken after the in-flight marker is durable, because the reply that retries it reaches the
publication through that marker and a park without one leaves the thread with nothing to answer.
`discussion_base_sha` rides that same pre-spawn write and is the commit the whole reading is measured from: what the
REMOTE said the base branch was at, read through the token rather than off `refs/remotes/<remote>/<base>`, which names
the base but lives in the object store the issue's worktree shares -- an agent can commit code, repoint that ref onto
it, and commit the plan, leaving a diff that shows one file while the branch carries two commits. It is persisted, not
re-read, because the tick that publishes need not be the tick that ran. What is recorded is an id this clone can read
and not merely one the remote named: the base advances between a tick's own fetch and the round that opens in it, and
an absent object fails the local diff that spends the record -- which reports no paths, exactly what a branch changing
nothing reports. So `_commit_present` is asked, one `_authed_target_fetch` of the base supplies what is missing, and a
commit still unreadable after it is recorded as no base rather than as a reading nobody could take.
`discussion_round_open`, written beside the anchor before every spawn and cleared by every park (and by the one
ending that records without parking, the adoption of an already-decided pull request), covers the resumed
round: it runs with the park it is answering still
durable, so one that committed the confirmed plan and was then paused or cut short is judged exactly as the same
crash on an unparked issue is. `discussion_publishing_sha`, written before the push, covers the publication itself --
turning a failed push into a retry (which spends the reply that asked for it, so a failure is not re-asked every poll,
and which replaces `discussion_push_failed` with `discussion_publishing` in that same write, since a reason the
recovery refuses to resume plus a spent reply is a publication nothing would pick up again)
and keeping a crash between `open_pr` and the pinned write from asking an operator
to reset away the commit its PR is open against. Neither becomes a way to publish a design nobody argued out: the
marker is asked first and answers for the branch either way, so a second plan-shaped commit appearing over an
unfinished publication is refused rather than read as the round's own work, and it is spent only by the next round
opening or by the branch going back to the anchor over a remote that no longer carries the commit it names -- the
push sends the SHA it validated rather than `HEAD`, so a local ref that never moved says nothing about whether the
plan went out, and dropping the record on that reading would leave a published plan on a pull request nobody
recorded while another round opened over it. The PR that publication lands on gets the same treatment as the
branch: `find_open_pr` only promises something open on this ref, so a body that does not name the publishing session
is rewritten to the plan's and one that does is left as it stands. What that lookup cannot see is the other half of
the same crash window -- a plan PR merged before anything recorded its number, which closes it and, with auto-delete
on, takes the head branch too -- so `find_pr_for_commit` asks by the publication's own SHA across every state before
the push -- matching on the commits a pull request CARRIES rather than the head it is on, since a human pushing to
that branch or merging the base into it moves the head inside the same window while the published commit stays in
the PR. MERGED, its number is recorded and nothing is pushed or opened: the branch the merge deleted would otherwise
be recreated and a second pull request asked for on a commit already in the base. Closed without merging is the
opposite reading and gets the ordinary publication: nothing landed, the branch is still there, and a recorded
pull request nobody can open would hold the stage on an unreviewable artifact instead of leaving one to read. A
commit list GitHub declines to serve is a third answer (`PR_LOOKUP_UNREADABLE`) rather than a miss, since that list
is the only place an amended, squash-merged publication is still visible; so is an enumeration that never reached
the candidate. Either way the stage writes its marker and stops, and the next tick asks again. The recovery asks
the same pair about the commit the MARKER names, since a checkout rebuilt from the remote comes back on whatever
head the humans left there. The
recovery asks the same question before it judges the branch at all, since a host that lost the checkout and the local
ref rebuilds from the base -- the merge took the branch -- and that tip matches neither the marker nor the anchor.
The same reasoning is why
`git/base_sync/refresh.py` lists this label beside `question` in its read-only gate — and the park beside the label,
since the refresh runs a full tick before the guard that consumes it, and `discussion_round_open` /
`discussion_publishing_sha` beside both, since those are written before the thing they describe and a tick that died
mid-round leaves one standing with no park at all — and why
`stages/implementing/handler.py` asks whether a merged recorded PR is this issue's work having landed before it
finalizes -- a plan PR is a design being agreed to, and two records say which it still is. `discussion_plan_path`
answers first and answers whatever that PR's head is now, because it is retired by this stage's own handoff before
anything spawns: while it stands nothing here has pushed, so a head that has moved is the humans editing the plan they
are agreeing to (a correction, a base merged in to make it mergeable) rather than an implementation to finalize.
`discussion_plan_sha` against the PR's head answers for the ticks after that handoff, which is what stays right when a
tick pushes onto the PR and dies before recording it -- and it is the head the handoff itself read, not the commit
publication pushed, so an amendment the humans made is not what the tick after reads as an implementation. That read
has a third answer: a PR GitHub could not be asked about ends the tick unfinalized and unspawned rather than falling
through to the terminal, which would fetch it again, and a request that failed once and succeeded next would finalize
the very plan the first answer protects. This is also why
`stages/implementing/read_only_relabel.py` refuses a relabel out of a `discussion_*` park -- or out of an unfinished
round, which carries no park at all -- whose branch, or whose checkout's own `HEAD`, has moved off
the SHA the round recorded (a commit made while detached leaves every ref where it was and the plan in the tree,
which is exactly what the shortcut would push), or whose tree `git status` could not report on at all (the list form
of that read answers a failure with no paths, which is what a clean tree answers, and the creators force-remove a
checkout nothing is holding). An unfinished PUBLICATION is refused on its record alone, because the
marker precedes the push and a fresh clone reads clean on every local probe at once, so the way out it names is the
`discussion` label whose recovery finishes it rather than a reset: the tree survives every exit short of the terminal
that finishes the issue, so nothing may rebase over it and nothing may ship as dev
work what this stage did not vouch for — while the commits an issue arrived carrying, which that same record
certifies, still let the relabel through — as does a published plan, whose anchor was moved onto the tip its
publication pushed, and as does the live head of the plan PR itself, which is the design as its reviewers left it.
Once that PR has MERGED the older ahead-of-base reading comes back, because the handoff for a merged plan resets the
branch to the base and records that in the write after the reset: a crash in between leaves a tip no record names,
and an exact match would report the base branch itself as unreviewed work.
Clearing that park hands the certified tip on as `read_only_baseline_sha`,
because `stages/implementing/spawn.py` otherwise reads any branch ahead of base as an interrupted dev run and would
skip the implementer to republish the very commits the discussion was held on top of. The same clear retires
`discussion_plan_path`: the relabel is the humans deciding, and a record left behind would hold this stage inert if the
issue ever came back. What replaces it is that live head, read once and used twice: recorded as the plan commit, and
anchored onto the branch through `worktrees/creation._anchor_pr_worktree` -- one authenticated fetch, a re-read of
what the remote says that branch is on, and a hardened
`reset --hard` (an `update-ref` where the checkout is gone) -- so the developer builds on what was approved instead of
on a tip whose push would take the amendment back out. The re-read is the one that covers the gap between reading the
PR and moving the ref: a human pushing in between leaves the fetch bringing their commit with the one just read still
resolving underneath it, so a local-object check alone would anchor on a head the PR has moved past and the push after
it would take their commit off the remote as its own lease. That call answers with the tip the branch ended up on, and
the baseline records it: the reviewed head, or `<remote>/<base>` when the remote confirms the branch is gone and what it
carried has landed there -- and that base is one the tick fetched, since a cached ref a failed fetch left behind names
the base from before the merge, which for a plan that has just landed is the one base the plan is not in. An answer of
nothing at all HOLDS the handoff -- the tick ends having written nothing, with
the plan record still standing -- because taking it would spawn the developer on a commit the reviewers moved past and
let the ordinary push that follows read their head off the remote as its own lease and overwrite it. Reading GitHub
before the guard rules is what makes the move
crash-safe: a tick that anchors and dies before its write leaves a tip the next one recognizes as the reviewed head
rather than convicting the branch of it. What that write leaves is a state of its own, not a moment: the baseline
beside `discussion_plan_sha` says the handoff was accepted and this stage has published nothing since, and an
interruption anywhere after it -- a live pause, a shutdown sweep, a dead process -- leaves an issue sitting there for
polls while the design is still on an open pull request its reviewers can move.
`_reconcile_open_plan_handoff` is the guard's own reading taken again on each of those ticks, so an amendment made in
that window is inherited rather than read as this stage having pushed (which closes the issue as `done` on a merged
design, or spawns the developer on a checkout whose push takes the correction back out), and a merge is re-anchored at
a base that has moved since. The branch is what ends it, because a push reaches git before it reaches the issue: a tip
past the baseline is a developer's own work, and a tip nothing could read is no answer and holds the tick. The move
itself is marked durably first (`read_only_anchor_sha`), since it too puts the ref on the reviewers' head before
anything records that it did -- and a marker still standing is what tells the branch that crash left from a
developer's commit, which the recovered-work shortcut would otherwise push with no agent having run.
`parks` holds what each of those decisions then says to the
human, and every one of them lands on its one funnel — the funnel puts back two things the shared helper overwrote:
the `park_reason`, which the handler's gate reads back next tick, so a park assembled anywhere else would earn a
second round over the top of the first; and the consumed ceiling, which the helper stamps at the newest comment on
the thread and which has to stay where the round's own prompt read to, or a reply that landed during the run is
recorded as answered by a round that never saw it. `state` and `models` reach no engine or git owner, so the park
reasons, the three predicates the handler gates on — whose park this is, whether it has already asked for the
checkout to be repaired, and whether the plan is already published — the plan path itself, and the carriers are all
decidable without one. Spelling that path on `state` is what keeps the prompt that promises the agent a file and the
check that refuses every other one from drifting apart: the prompt builders are handed it, and the publication check
compares against it. `terminal` is what asks the pull request those records name what it has become, and it is asked
ahead of every local reading because both endings this stage has were made somewhere else: a merged plan PR finalizes
to `done`, one closed unmerged to `rejected`, and either takes the shared tail from `engine/terminals` under
`stage="discussion"` -- the stamp, the label, the receipt before the single write, the event, the close, and
`_cleanup_terminal_branch` last of all. An open one decides nothing and, more to the point, reaps nothing, which is
also what a closed ISSUE with an open plan PR gets: the label it keeps is what leaves it inside the closed-issue sweep
until the pull request itself resolves. A closed issue with no plan PR is the one arc that needs no pull request, and
it rejects without a teardown -- the branch under it may be an unpublished plan commit or a PR the issue merely
arrived here holding. That last reading is taken only once a standing `discussion_publishing_sha` has been looked up
by commit, since the publication opens its pull request before it records the number and a human can decide the issue
inside that window: a decided pull request found there is finalized on the spot (its number and branch written first,
because the event names one and the cleanup resolves the other), and an open one holds like a recorded one.
So the only worktree this stage ever tears down is one whose plan PR is gone: everywhere else
the tree the discussion read is the tree its next round and the operator both look at. The
stage borrows the same engine surfaces question does -- the tracked spawn, the awaiting-human park, the prompt
builder, the trusted conversation text, and the stderr diagnostics from `workflow/engine/`, `_worktree_path` and
`_resolve_branch_name` from `git/worktrees/paths.py`, `_ensure_worktree` from `git/worktrees/creation.py`,
`_branch_tip_sha` from `git/worktrees/recovery.py` -- the anchor comparison falls back to it when the checkout
directory is gone but the branch survives -- and
`_head_sha`, `_worktree_status` beside the `_worktree_dirty_files` list its other callers read,
`_committed_paths_since`, and `_revision_contains_path` from `git/verification/probes.py` -- those are what the
write contract is decided by, so a mock for any of them has to land there. The status form is the one a publication
asks, because an unreadable tree and a clean one are the same empty list and only one of them may be pushed over.
Opening a round adds two more: `_remote_branch_tip` from `git/authentication.py`, read before the spawn so the base
the round's work is finally measured against is the remote's answer rather than a local ref the round could repoint,
and `_commit_present` beside it, because the diff that spends that answer is local -- an id the store lacks is fetched
in through `_authed_target_fetch` from the same owner, or recorded as no base at all.
Publishing adds the
push from that same owner and the commit subject and PR title builders from `git/publication/`, the same
owners every dev PR is opened through. It takes one restorer question of its own: an issue
carrying a `pr_number` is discussed on the branch that PR is open against, so a pruned local ref is rebuilt by
`_ensure_pr_worktree` from the PR head rather than by `_ensure_worktree` from the base branch, which would drop the
PR's commits out of the tree the round reads. A publication in flight answers that question the same way and earlier,
which is why `_remote_branch_tip` is read a second time there: the marker precedes the push and `pr_number` follows
the PR, so a crash between them leaves a pushed branch and an open PR with nothing pinned naming either -- and if the
worktree and the local ref are gone as well, only the remote can say the branch exists to restore from.

Most stage handlers run the user-content drift hook (`_compute_user_content_hash` → `_detect_user_content_change`) so
an out-of-band human edit re-routes the issue back to `workflow:decomposing` (when no dev session exists yet), resumes
the locked dev session with the updated body (implementing, validating, in_review, resolving_conflict), or unwinds
back to `workflow:validating` without resuming dev (documenting). Both halves of that hook sit on the
`workflow/engine/drift.py` owner the stage leaves import directly, so a patch aimed at the hook targets that owner.
`_handle_fixing`, `_handle_question`, and `_handle_discussion` skip the drift hook — see
[`state-machine/delivery-stages.md#user-content-drift-detection`](state-machine/delivery-stages.md#user-content-drift-detection)
for the per-handler
routing.

For per-stage internal flow — pickup, drift handling, decomposing, ready, blocked, umbrella, implementing,
documenting, validating, in_review, fixing, resolving_conflict, question, discussion — see
[`state-machine.md#stage-handlers`](state-machine.md#stage-handlers).

## Agent subprocess (`agents.run_agent`)

`run_agent(backend, prompt, cwd, ...)` dispatches to the per-backend runner (`codex.run_codex` /
`claude.run_claude`); `backend` is one of `"codex"` / `"claude"` and is re-validated at call time so a
misuse fails loudly. Both runners return a unified
`AgentResult(session_id, last_message, exit_code, timed_out, stdout, stderr, interrupted, usage)`. `interrupted`
(default `False`) flags a run the runner observed exiting on SIGTERM/SIGKILL — the shape the orchestrator's
shutdown sweep (`terminate_all_running`) produces when it kills an in-flight agent group — and is distinct
from `timed_out` (the orchestrator's own `AGENT_TIMEOUT` firing). `usage` (default `None`) is the parsed
`UsageMetrics` -- the one on `observability/usage/metrics.py` -- that `recording.record_agent_exit` attaches during a
tracked run so callers can read token / cost metrics off the result without re-parsing stdout; it stays `None` for a
result that never flowed through
`_run_agent_tracked` or whose usage parse failed (fail-open). The developer (implementing), reviewer
(validating), decomposer (decomposing), question, and discussion handlers consume it: `_accumulate_issue_usage` — in
`workflow/engine/usage.py`, which each of those handlers binds directly — folds
each run's `usage` into the per-issue `issue_agent_runs` / `issue_total_tokens` / `issue_total_cost_usd` /
`issue_cost_sources` counters on the pinned state
([`state-machine/labels-and-state.md#pinned-state`][pinned-state]); at each terminal (PR merge / reject, umbrella
close, closed question, and both discussion endings — the verdict the humans leave on the plan PR, and a close of the
issue before one exists) `_format_issue_usage_verdict` beside it reads those counters back into one visible receipt
comment — the sole read-side consumer, and nothing gates on the figure. `CodexResult` is kept as a
transitional alias.

The role command specs (`DEV_AGENT` / `REVIEW_AGENT` / `DECOMPOSE_AGENT`), their parsing, the durable per-session
lock, and the resume mechanic are documented in
[`workflow/command-specs.md`](workflow/command-specs.md). Which stage spawns which role is in
[`workflow/roles.md`](workflow/roles.md). What follows is the subprocess shape only.

- **Codex command**:
  `codex exec [-C cwd | resume <sid>] --dangerously-bypass-approvals-and-sandbox --json -o <tempfile> <prompt>`. The
  `-o` path is a per-spawn `tempfile.mkstemp` outside the worktree (so target repos without `.codex-*` in `.gitignore`
  don't see it as untracked); `last_message` is read from it and the tempfile is cleaned up on any exit path by a
  per-spawn context manager (`codex.codex_last_message_file`).
- **Claude command**:
  `claude -p --dangerously-skip-permissions --output-format stream-json --include-partial-messages --verbose <prompt>`
  (with `--resume <sid>` when resuming). `last_message` is parsed from the stream-json: prefers the terminal
  `{"type":"result","result":...}` event (honored regardless of how the run ended), falls back to the last
  `assistant`/`message` text content for schema-drift forward-compat. The fallback is gated to clean, completed runs
  (`exit_code == 0`, not timed out, not interrupted); an interrupted or non-zero run with no terminal `result` event
  exposes an empty `last_message` rather than a partial transcript chunk.
- **Input**: prompt string; optional resume session id; timeout (`AGENT_TIMEOUT` / `REVIEW_TIMEOUT`).
- **Output**: `AgentResult(...)`. `session_id` is harvested by walking the JSONL events for any UUID-shaped value at
  `session_id` / `conversation_id` / etc. (shared between both backends).
- **Timeout cleanup** (`processes.terminate_process_group`): on timeout expiry the runner SIGTERMs the agent's whole
  process group (every spawn uses `start_new_session=True`), waits for the leader, then — mirroring the shutdown sweep
  (`terminate_all_running`) — probes the group with `killpg(_, 0)` and SIGKILLs any surviving descendant. Without the
  probe a build grandchild the agent forked (Maven, gradle, a JVM test runner) could keep mutating the worktree after
  the timeout was recorded — the failure mode that stranded a late clean commit behind the implementing-stage
  `agent_timeout` park.

### Environment filtering (`agents.environment.filter_agent_env`)

The agent subprocess env is filtered to keep host secrets and the orchestrator's own GitHub credentials out of agent
reach. The same filter runs for the verify-command runner (with `allow_provider_auth=False`, which also strips provider
keys).

- **GitHub-token-bearing env vars** are stripped (`GITHUB_TOKEN`, `GH_TOKEN`, etc. — the `_FORBIDDEN_AGENT_ENV`
  exact-match set) so a prompt-injected agent cannot push or call the GitHub API.
- **Production-secret-shaped env vars** are stripped by name shape: anything matching `_AGENT_SECRET_SUFFIXES`
  (`_TOKEN`, `_KEY`, `_SECRET`, `_PASSWORD`, `_PAT`, `_CREDENTIAL`) or the bare-name set (`TOKEN`, `KEY`, `SECRET`,
  `PASSWORD`, `PAT`, `CREDENTIAL`). Without this a `STRIPE_API_KEY` / `DATABASE_PASSWORD` set on the host would ride
  into a sandbox-bypassed agent or into the operator-configured verify shell.
- **Credential-file locators** are stripped too (`*_TOKEN_FILE`, `*_KEY_FILE`, `*_SECRET_FILE`, `*_PASSWORD_FILE`,
  `*_CREDENTIAL_FILE`, `*_CREDENTIALS`, `*_CREDENTIALS_FILE`, plus bare `TOKEN_FILE` / `CREDENTIALS` /
  `CREDENTIALS_FILE`). The most important case is `ORCHESTRATOR_TOKEN_FILE`, the orchestrator's own write-credential
  locator.
- **Write-credential locators** (`_AGENT_WRITE_CREDENTIAL_LOCATORS`: `SSH_AUTH_SOCK`, `SSH_ASKPASS`, `GIT_ASKPASS`,
  `GIT_SSH_COMMAND`) are stripped by exact name. The orchestrator's own push path constructs its own `GIT_ASKPASS`
  tempfile.
- **Provider auth** required to reach the agent's own model is allowlisted by exact name in
  `_AGENT_PROVIDER_AUTH_ALLOWLIST` (`ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, `CLAUDE_CODE_OAUTH_TOKEN`,
  `OPENAI_API_KEY`) for agent subprocesses only. The verify runner passes `allow_provider_auth=False` and strips them
  too — a verify shell executes untrusted agent-produced code, and the verify-failure park comment publishes the
  offending command verbatim. Advanced deployments (Bedrock, Vertex, custom proxies) extend the allowlist explicitly.
- **`GIT_AUTHOR_*` / `GIT_COMMITTER_*`** are injected from `AGENT_GIT_NAME` / `AGENT_GIT_EMAIL` (default
  `agent-orchestrator <agent-orchestrator@users.noreply.github.com>`) so agent commits are stamped with the
  orchestrator's identity regardless of the host's `~/.gitconfig`.

### Hardened local git (`git.commands._git_hardened`)

Every local git operation inside a worktree the agent can write to runs through this envelope: the `-c` overrides
that neutralize `core.hooksPath` / `core.fsmonitor` / `credential.helper` / commit signing, `GIT_CONFIG_GLOBAL` and
`GIT_CONFIG_SYSTEM` detached from `~/.gitconfig` and `/etc/gitconfig`, and the orchestrator's committer identity.

Git's own output is decoded with `surrogateescape` rather than strictly, for the same class of reason. A repository
path is bytes, and a committed file whose name is not valid UTF-8 makes a strict decode raise inside `subprocess`
before any caller sees a return code -- taking the tick out where the probe should have reported the extra path and
parked the artifact it invalidates.

It also turns object replacement off — `GIT_NO_REPLACE_OBJECTS=1` for `refs/replace/<oid>` and
`GIT_GRAFT_FILE=/dev/null` for the graft file. Neither of those is config, so nothing above reaches them, and each is
writable by an agent whose linked worktree shares the clone's refs and git dir. Left on, they change what git says a
commit's tree and parents ARE without changing the commit anyone named: a decomposer could stand a synthetic commit
carrying its code in for the base and have the plan check measure against that, while the push — which names the real
SHA — carries the code as well. Both are disabled for every hardened read, so a probe and the push it gates are
talking about the same objects.

Two more sit on the working-tree operations themselves rather than in the envelope, because neither is config either.
`core.worktree` in a linked worktree's own `config.worktree` — which an agent
enables by writing `extensions.worktreeConfig` into the clone it shares — points every path operation at any directory
it likes, and a `-c core.worktree=` override does NOT win against it, so the tree is named with `--work-tree` instead:
by `verification/probes._worktree_status`, which would otherwise report on a clean shadow checkout, and by the
`reset --hard` in `worktrees/creation._move_branch_onto`, which would otherwise report success and move the ref while
writing the reviewed commit's files into that other directory -- leaving the issue's checkout on the plan it had, the
handoff baseline naming a tip the tree is not on, and whatever was in the redirected directory overwritten.
And `assume-unchanged` / `skip-worktree` are bits on an index entry: git honours them by not comparing the file, so a
tracked path the agent rewrote reports clean. Those entries are read separately (`git ls-files -v`) and answered as
paths AND as a withheld `readable`, so a caller refusing on what git listed and one that has to prove the tree empty
both fail closed on them.

## Push path (`git.authentication._push_branch`)

The orchestrator (not the agent) pushes. The push is hardened against the agent-controlled worktree:

- Token delivered via `GIT_ASKPASS` tempfile, never argv.
- Detaches from `~/.gitconfig` and `/etc/gitconfig` (`GIT_CONFIG_GLOBAL=/dev/null`, `GIT_CONFIG_SYSTEM=/dev/null`).
- Disables `core.hooksPath`, `credential.helper`, `core.fsmonitor`.
- Refuses to push if the config the push resolves — the worktree's local config plus any `include.path` file or
  per-worktree `config.worktree` it pulls in, with global/system detached — carries any `url.*.insteadOf` /
  `pushInsteadOf` rewrite or any `http.*` proxy/TLS setting (e.g. `http.proxy`, `http.sslVerify=false`) that could
  tunnel the token-bearing push through an attacker proxy or disable certificate verification. Env-var proxies
  (`https_proxy`) are operator-set and stay honored — only agent-writable config-file transport is rejected.
- Pushes via an explicit refspec (no upstream stored): `HEAD:refs/heads/<branch>` by default, or
  `<revision>:refs/heads/<branch>` when the caller names the commit it means. A caller that decided to push by
  inspecting a commit — the discussion stage's plan publication — names it, because `HEAD` between the reading and
  the push is not necessarily the commit that was checked.

## Observability

Four independent observability surfaces — an opt-in audit event log, a project-local analytics JSONL sink, an opt-in
(default-off) trajectory JSONL sink that `record_agent_exit` fills with redacted, head/tail-truncated per-run reasoning
trajectories — each carrying a denormalized run-level token-usage / cost summary (plus a claude-only per-turn
breakdown) alongside the step timeline — and an operator-deployed Postgres aggregation target (with a Streamlit
dashboard and the `orchestrator/observability/usage/` parser that feeds it). The trajectory sink has its own separate
Streamlit page — the file-backed trajectory viewer (`orchestrator/apps/trajectory_dashboard.py` over the pure
read model under `orchestrator/observability/trajectory_viewer/`),
which reads the JSONL directly (usage and cost included) and needs no Postgres.
None of them feed back into dispatch: workflow correctness keys off the pinned state JSON and the workflow label, so
every surface is observation-only and safe to truncate, rotate, or delete. That is also why all four migrate into
`orchestrator/observability/` — the owners there and the rules they inherit are mapped in
[`architecture/observability-modules.md`](architecture/observability-modules.md).

For each sink's schema, event-kind tables, and append / retention / rotation semantics, see
[`observability/event-streams.md`](observability/event-streams.md) and
[`observability/trajectories.md`](observability/trajectories.md). For the analytics-DB compose layout and the sync,
see [`observability/analytics-database.md`](observability/analytics-database.md); for the read-model and dashboard
wiring, [`observability/analytics-dashboard.md`](observability/analytics-dashboard.md); and for the usage parser's
cost-precedence rules, [`observability/usage.md`](observability/usage.md).
[`observability.md`](observability.md) maps all five.

## Summary of "what runs when"

- **`cli.main` polling loop** — long-lived Python process. Trigger: manual start (or wrapper). Cadence: every
  `POLL_INTERVAL`s.
- **`workflow.tick(gh, spec)`** — function call. Trigger: each loop iteration. Cadence: once per tick per configured
  `RepoSpec`; multi-repo fans out across a `ThreadPoolExecutor`, single-repo stays in-thread.
- **`_refresh_base_and_worktrees(gh, spec)`** — function call. Trigger: start of each `workflow.tick`. Cadence: once
  per tick per repo: one `git fetch <spec.remote_name> <spec.base_branch>`, then per-worktree dispatch (pre-PR
  worktrees rebase directly; PR-having worktrees behind base are rebased + pushed in the refresh itself via
  `_sync_pr_worktree_to_base` and routed to `workflow:validating` on success, with `workflow:resolving_conflict`
  reached when the auto rebase actually leaves conflicted files).
- **`_handle_*` per issue** — function call. Trigger: issue's workflow label. Cadence: once per tick per open issue;
  concurrent up to `spec.parallel_limit` per repo and `MAX_PARALLEL_ISSUES_GLOBAL` across all repos. No-agent family
  buckets (`workflow:blocked` / `workflow:umbrella`) are cap-exempt.
- **decomposer agent (`DECOMPOSE_AGENT`)** — subprocess (fresh or resumed). Trigger: `_handle_decomposing` (retry
  budget OK) or HITL resume. Cadence: one shot per tick when needed. The same role spec also backs the two
  operator-applied conversation stages, which pin their own keys and resume their own sessions rather than a
  decomposing one: `_handle_question` (`question_agent` + `question_session_id`, read-only for the whole
  conversation) and `_handle_discussion` (`discussion_agent` + `discussion_session_id`,
  `agent_role="decomposer"` / `stage="discussion"`, spawned fresh on the opening round and resumed on each trusted
  human reply after it — read-only until a human confirms the design on the thread, and from there allowed exactly
  one commit of `plans/issue-<number>.md` for the stage to publish).
- **implementer agent (`DEV_AGENT`)** — subprocess. Trigger: `_handle_implementing` (no commits yet, retry budget OK)
  or HITL resume. Cadence: one shot per tick when needed.
- **reviewer agent (`REVIEW_AGENT`)** — subprocess (fresh session). Trigger: `_handle_validating`, round < max.
  Cadence: one shot per tick.
- **dev-fix agent** — subprocess (resumed dev session). Trigger: reviewer says CHANGES_REQUESTED (dispatched from
  `_handle_validating` after the relabel to `workflow:fixing`), or fresh in_review PR feedback (dispatched from
  `_handle_fixing` after the quiet window) — both run with `stage="fixing"` and bounce back to `workflow:validating`
  for re-review. Cadence: one shot per tick.
- **`_handle_resolving_conflict`** — function call. Trigger: issue label `workflow:resolving_conflict` (operator
  relabel, refresh-time conflicted rebase, or the `fixing` worktree-drift dead-lock breaker when a stuck
  validating-route transient fix-loop is out of sync with the PR head — behind base or an unpushed local rebase); also
  fires on closed-`workflow:resolving_conflict` issues from the polling sweep. Cadence: once per tick per such issue.
- **dev-conflict agent** — subprocess (resumed dev session). Trigger: `_handle_resolving_conflict` and `git rebase`
  left conflicts. Cadence: one shot per tick.
- **`_handle_question`** — function call. Trigger: issue label `question` OR closed-`question` issue from the polling
  sweep. Cadence: once per tick per such issue.
- **question agent (`DECOMPOSE_AGENT` backend)** — subprocess (read-only). Trigger: `_handle_question` (no prior
  session OR new human comment on a parked Q&A). Cadence: one shot per tick when needed.
- **`_handle_discussion`** — function call. Trigger: issue label `discussion` OR closed-`discussion` issue from the
  polling sweep, which keeps yielding that issue every pass while its plan PR is still open. Cadence: once per tick
  per such issue, and the tick spawns nothing at all when the plan PR is already published, when the park on the
  thread is still unanswered, or when the checkout is one no round may open on.
- **discussion agent (`DECOMPOSE_AGENT` backend)** — subprocess. Trigger: `_handle_discussion` (the conversation's
  opening round, or a trusted human reply past the consumed watermark on a parked one). Cadence: one shot per tick
  when needed. No developer or reviewer ever runs on this label: the one thing the stage produces is the plan PR, and
  having that plan built is an operator relabel to `workflow:implementing`.
- **`git push`** — subprocess. Trigger: after dev produces clean commits, or after a discussion round commits the
  confirmed plan and the branch reads as exactly that one file. Cadence: per fix; per discussion, once the humans
  have confirmed the design — with a publication a tick died inside re-attempted on the next tick from the in-flight
  marker, and one whose push itself failed re-attempted on the human's reply to that park.
- **self-restart check** — git fetch + diff. Trigger: start of each tick. Cadence: every tick.

## Architecture schema

```
                     ┌──────────────────────────────────────┐
                     │   GitHub repo(s) (REPO or REPOS)     │
                     │   ─ issues (with workflow labels)    │
                     │   ─ pinned state comment per issue   │
                     │   ─ branches / PRs                   │
                     └──────────────┬───────────────────────┘
                                    │ PyGithub (one token per slug)
                                    │
   ┌────────────────────────────────┴─────────────────────────────────────┐
   │  orchestrator process  (python -m orchestrator)                      │
   │  ───────────────────────────────────────────────────                 │
   │   cli.main over orchestrator/runtime/                                │
   │     startup: build per-spec [(spec, GitHubClient), ...] from         │
   │              config.default_repo_specs(); ensure_workflow_labels;    │
   │              build one shared IssueScheduler(global_cap, per_repo)   │
   │     loop every POLL_INTERVAL s:                                      │
   │       1. self-restart check (origin/<ORCHESTRATOR_BASE_BRANCH>       │
   │          moved & touches orchestrator/?)                             │
   │       2. run_tick(state, clients, scheduler):                        │
   │            N == 1 → in-thread workflow.tick(gh, spec, scheduler)     │
   │            N  > 1 → ThreadPoolExecutor fans workflow.tick across     │
   │                     one worker thread per repo                       │
   │       3. scheduler.reap()  (drain completions; surface failures)     │
   │       4. retention.prune_with_retention_logging()                    │
   │     shutdown: scheduler.shutdown(wait=True) drains workers on        │
   │               --once / self-restart; a signal stop first kills       │
   │               in-flight agent+verify groups, and a watchdog          │
   │               hard-exits within SHUTDOWN_GRACE_SECONDS on overrun    │
   │                    │                                                 │
   │                    ▼                                                 │
   │   workflow.tick(gh, spec, scheduler) →                               │
   │     _refresh_base_and_worktrees(gh, spec, scheduler): skip           │
   │       worktrees whose handler is still in flight in scheduler        │
   │     classify each pollable issue and submit to scheduler:            │
   │       family-aware (`workflow:decomposing` / `workflow:blocked` /    │
   │         `workflow:umbrella` / unlabeled) →                           │
   │         ONE bucket submit per repo that drains sequentially          │
   │         (cap-exempt when every family issue is                       │
   │         `workflow:blocked` or `workflow:umbrella`)                   │
   │       fan-out (everything else) →                                    │
   │         one submit per issue, concurrent up to per-repo / global     │
   │         caps                                                         │
   │     scheduler rejects duplicate active / cap hit / family-slot       │
   │       conflict → skipped this tick AND logged with reason            │
   │     accepted workers call gh._for_worker_thread() + refetch the      │
   │       Issue, then run _process_issue → dispatch by label             │
   │                                                                      │
   └─────────┬───────────────────────────────────────┬────────────────────┘
             │ subprocess                            │ subprocess (hardened)
             ▼                                       ▼
   ┌─────────────────────────────┐         ┌─────────────────────────────┐
   │  coding-agent CLI           │         │  git push                   │
   │  (codex or claude,          │         │  ─ GIT_ASKPASS tempfile     │
   │   per-issue worktree)       │         │  ─ no global/system config  │
   │  ─ env: GH tokens stripped  │         │  ─ hooks/helper disabled    │
   │  ─ env: GIT_AUTHOR/COMMITTER│         │  ─ refuses url/http cfg     │
   │     stamped (orchestrator)  │         └──────────────┬──────────────┘
   │  ─ provider auth left alone │                        │
   │  ─ --bypass / --skip perms  │                        │
   │  ─ JSONL → session_id       │                        │
   │  ─ last_message: -o (codex) │                        │
   │     or stream-json (claude) │                        │
   └──────────────┬──────────────┘                        │
                  │ commits to                            │ pushes branch to
                  ▼                                       ▼
   ┌─────────────────────────────────────────────────────────────────────┐
   │  git worktree:  <WORKTREES_DIR>/<owner>__<name>/issue-<n>           │
   │  branch:        orchestrator/<owner>__<name>/issue-<n>              │
   │  ─ slug subdir + slug-namespaced branch keep two repos sharing a    │
   │    target_root from colliding on the same `orchestrator/issue-<n>`  │
   │  ─ created from <spec.remote_name>/<spec.base_branch>               │
   │    in spec.target_root                                              │
   │    (or reused if has unpushed commits)                              │
   └─────────────────────────────────────────────────────────────────────┘
```

## State transition (label lifecycle)

The compact label-lifecycle diagram for every forward, fix-loop, terminal, and HITL-park transition lives in
[`state-machine/lifecycle.md`](state-machine/lifecycle.md).

[pinned-state]: state-machine/labels-and-state.md#pinned-state
