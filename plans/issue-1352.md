# Issue #1352 — Automatic sub-splitting of issues

## Status

Agreed design. The issue thread explicitly confirmed that the humans and the
architecture discussion understand the design the same way. This document is
the implementation handoff; no implementation existed when it was written.

The design adds a late size gate to a clean, committed implementation before
publication. An oversized candidate is either accepted as one justified change
or converted into a bounded decomposition generation whose children can reuse
the exact committed snapshot. It preserves the existing label state machine,
uses additive pinned state, and adds no new workflow stage.

## Goals

- Detect unexpectedly large implementations before their branch or pull
  request is published.
- Preserve useful committed work while turning an oversized issue into child
  issues.
- Keep GitHub labels and the authenticated pinned comment authoritative.
- Make every remote mutation and crash boundary reconcilable without
  respawning an agent that already finished.
- Bound recursive splitting and expose enough telemetry to tune the initial
  threshold empirically.
- Reclaim snapshot refs in v1 so oversized Git objects are not retained on the
  remote indefinitely.

## Non-goals

- There is no new workflow label, stage, external service, or database-backed
  source of truth.
- The orchestrator does not split hunks or synthesize commits for children.
- There are no path exclusions for generated, vendored, data, or fixture
  files.
- There is no per-repository threshold override in v1.
- The initial 4,000-line value is not gated on a benchmark study.
- The lineage limit is not configurable.
- A late cancellation does not close, relabel, or comment on already-created
  children.
- This is not a general restart mechanism for every rejected issue.

## Repository evidence

The design lands on these current contracts:

- `orchestrator/workflow/stages/implementing/disposition.py` funnels every
  clean committed developer outcome through `_publish_committed_work`, which
  checks dirtiness and immediately calls publication. This is the only safe
  late-gate seam shared by normal completion, timeout completion, and recovered
  work.
- `orchestrator/workflow/stages/implementing/publication.py` owns the push,
  pull-request publication, and transition to validation. The new gate must run
  before that boundary, not inside a developer prompt or after a PR exists.
- `orchestrator/workflow/stages/implementing/spawn.py`, `resume.py`,
  `execution.py`, `session.py`, and `models.py` already preserve developer
  sessions and share retry accounting. Late developer revision should reuse
  that machinery while the issue carries `workflow:decomposing`.
- `orchestrator/workflow/stages/decomposition/manifest.py`, `outcomes.py`, and
  `split.py` own initial `single`/`split` adjudication and crash-safe child
  creation. The late contract is an additive mode; it must not change what a
  missing initial manifest means.
- `orchestrator/workflow/stages/decomposition/activation.py`, `blocked.py`,
  `umbrella.py`, and `parents.py` own child activation and parent completion.
  Their ordinary parent scan is unsuitable for cancelled cleanup because it
  activates work and treats rejected or manually closed children as an
  exception rather than a cleanup-terminal disposition.
- `orchestrator/workflow/engine/drift.py` intentionally hashes title, body,
  and trusted comments into one global `user_content_hash`. Late adjudication
  needs additional local fingerprints without changing that existing drift
  contract.
- `orchestrator/workflow/engine/guards.py` contains the existing post-agent
  pause probe. Its fail-open shape cannot guard an irreversible late split;
  the late path needs a distinct open/closed/read-failed result.
- `orchestrator/workflow/engine/pickup.py` owns author allowlisting and the
  `DECOMPOSE` route for new issues. A completed-cancellation restart is an
  authenticated operator transition, not another untrusted pickup.
- `orchestrator/workflow/state.py` and
  `orchestrator/workflow/engine/dispatch.py` define legal label transitions,
  decomposition-family scheduling, terminal no-ops, and cap exemptions. They
  need additive transition and cleanup dispatch support rather than a parallel
  state machine.
- `orchestrator/github/pinned_state.py` reads the first authenticated,
  state-only comment and edits it in place. Restart must reuse that comment;
  creating another authoritative state comment would make recovery ambiguous.
- `orchestrator/github/issues.py` performs cached closed-issue queries only on
  `CLOSED_ISSUE_SWEEP_EVERY_N_TICKS`. Its current sweep deliberately excludes
  the decomposition family, so snapshot-owner cleanup requires a narrow extra
  query on that same cadence, not blanket closed-decomposition dispatch.
- `orchestrator/github/pull_requests.py` can open, find, edit, comment on, and
  merge a PR, and treats an absent branch as successful deletion. It has no PR
  close helper today; late supersession and cancellation require one.
- `orchestrator/git/authentication.py` is the security boundary for
  token-bearing fetches and pushes. Snapshot ref create, verify, fetch, and
  delete operations must use the same hardened transport and repository lock.
- `orchestrator/github/events.py` appends a bounded in-memory audit event and
  an optional JSONL copy without blocking workflow on an I/O failure.
  `orchestrator/observability/analytics/recording/events.py` and its sink own
  the separate non-blocking analytics stream. Late-split telemetry belongs on
  both surfaces.
- `orchestrator/workflow/engine/comments.py` already bounds tracked comment
  identifiers. `orchestrator/workflow/engine/terminals.py` shows why generic
  rejected state is not restart-safe: ordinary rejection can deliberately
  retain salvageable PR and branch state.

Relevant history explains the boundaries and recovery style:

- `5b16a8f` introduced manifest decomposition and the
  decomposing-to-ready/blocked flow.
- `f4da67e` introduced umbrella parents with no implementation of their own.
- `6c3caae` established user-content drift and developer-session resumption.
- `9e5eac6` made worktree creation restart-safe; `18968e1` added recovery for
  stranded unpushed developer work.
- `9c01a60` namespaced PR branches by repository; `2970372` surfaced the
  decomposer's single-task context.
- `9385231` introduced confirmed-design plan PR publication, and `9a1b7af`
  established the discussion flow it follows.
- `eb002c6` fixed the worktree-probe outage that motivates exact-SHA
  reconciliation instead of developer respawn.
- `eccb4a8` and `5122a5e` established the one-time follow-up when a transient
  park heals itself.
- `c71cdb4` moved authenticated pinned-state ownership into the GitHub package;
  `fc5fca8` added author allowlisting at initial pickup.
- `9dfe9b4`, `63e5830`, and `49cde99` established per-issue usage, terminal
  verdict, and namespaced stage-event conventions.
- `f5f6368` split the workflow package while retaining shared agent retry
  accounting.

## Design tree and decisions

### 1. Where the gate runs

The root choice was before implementation, after implementation but before
publication, or after publication. The settled branch is the middle one:

1. A developer leaves a clean worktree with committed work.
2. The orchestrator freezes and measures the candidate before any branch push
   or implementation PR publication.
3. A candidate at or below the threshold follows today's publication path.
4. A candidate above the threshold enters late adjudication.

This rules out predicting size during initial decomposition, retracting an
already-public oversized PR as the normal path, and measuring dirty or
uncommitted work. It also makes `_publish_committed_work` the integration seam
and leaves publication itself responsible only for accepted candidates.

### 2. Configuration and measurement

There is one new global positive-integer added-line threshold. Its default is
4,000 and the trigger is strictly greater than the configured value. The final
setting name follows repository configuration conventions and is documented in
the ordinary configuration surfaces.

When `DECOMPOSE=on`, every clean committed candidate is measured, including
candidates below the threshold. Measurement is the prospective pull-request
diff between:

- the exact remote base commit frozen for this attempt; and
- the exact clean candidate commit.

Count textual added lines across every path. Binary content contributes zero.
There are no exclusions for lockfiles, generated code, migrations, snapshots,
golden fixtures, i18n catalogs, notebooks, vendored code, mass moves, or mass
formatting. This keeps the metric auditable and prevents a blessed bypass.

When `DECOMPOSE=off`, new candidates bypass both measurement and late
adjudication and retain today's publication behavior. Turning the switch off
does not erase or coerce an already-recorded late generation, categorized
question, recovery, cancellation, or cleanup obligation.

A measurement failure is not “small” and is never silently skipped. The
orchestrator logs it loudly, records a typed failure, parks with an explicit
reason, and preserves the exact candidate SHA. A trusted bare continue retries
measurement and reconciliation only; it does not respawn the finished
developer.

This rules out an inclusive threshold, changed-line totals, issue-wide size
exemptions, binary-byte approximations, path allow/deny lists, and fail-open
publication.

### 3. Frozen late-generation state

Before invoking the late decomposer, persist a generation record containing at
least:

- a monotonic cycle identity and generation identity;
- root issue and current issue;
- lineage depth;
- the candidate SHA and exact remote base SHA;
- the issue's declared scope;
- measurement threshold and additions;
- reconciliation phase and external-resource ledger entries;
- local title/body and trusted-comment fingerprints;
- any held plan-PR identity and its original body.

The candidate commit is immutable for adjudication. The state marker also
freezes ordinary base refresh for that generation. Local Git objects and the
existing worktree are a deliberate same-host recovery dependency until a
remote snapshot exists. A restart on that host resumes. A new host that cannot
prove the recorded objects parks loudly and never substitutes a newer HEAD or
base.

Pinned fields are additive. Issues that never enter the late gate require no
migration. A binary that does not understand live late-generation fields is
unsafe, so deployment and downgrade require pausing or draining those issues.

### 4. Plan-PR hold

If an open plan PR already represents the implementation candidate, the
orchestrator first replaces its body with a temporary, generation-marked hold
while preserving the original body in pinned state. The hold prevents humans
from mistaking the candidate for a ready implementation while adjudication is
running.

The hold write happens before an agent spawn. Failure parks without spawning;
a trusted continue retries reconciliation rather than causing a noisy mutation
on every poll. Human merge or close while the agent runs does not cancel or
re-anchor adjudication: the frozen candidate SHA remains authoritative and the
later outcome reconciles against the PR's current state.

This rules out leaving an apparently ready plan PR open during a long late
review and rules out using PR state as the source of truth for the candidate.

### 5. Late decomposer contract

The late decomposer receives the original issue, declared scope, exact diff
context, measured size, lineage, and the fact that committed work already
exists. Its structured result is one of:

- `single`: the implementation is one coherent change despite its size;
- `split`: a complete child manifest that partitions the declared scope; or
- a categorized human question when neither outcome is safe.

The late prompt makes common false positives explicit. A diff dominated by
legitimate generated or data artifacts should receive a fast `single` verdict.
If those artifacts instead look inappropriate to commit, the agent asks a
categorized question and the workflow parks for a human.

The late result parser is an additive mode. It does not alter the initial
decomposer's existing handling of no manifest or malformed output.

A `single` verdict grants an exemption only to the exact measured SHA. Any new
candidate SHA is measured and adjudicated again. There is no issue-wide escape
hatch, and no snapshot is created. If the held plan PR remains open,
restore/replace its body for normal implementation publication; if it no longer
exists in a reusable state, reconcile through the normal exact-commit PR
publication path.

A `split` verdict is allowed only below a hard-coded maximum lineage depth of
3. The bound is a safety invariant, not a tuning knob. At the bound, an
indivisible oversized child must resolve as `single` or ask a human rather than
create another generation. Lineage telemetry shows whether real work approaches
the bound.

### 6. Human guidance and content drift

Late adjudication keeps the global `user_content_hash` behavior unchanged and
adds local fingerprints that distinguish:

- title/body changes; and
- trusted conversation added after the late baseline, using a separate
  trusted-comment watermark and hash.

A substantive trusted comment answering a categorized question resumes the
late decomposer. Bare continue, `DECOMPOSE=off`, and manual relabel cannot turn
that question into `single`; a manual relabel is restored to
`workflow:decomposing`.

After the candidate SHA is frozen, a title/body edit parks without discarding
the SHA, session, generation, or PR hold. A trusted bare continue certifies that
the frozen candidate still applies and resumes adjudication. Substantive
trusted guidance instead resumes the original developer session, still under
`workflow:decomposing`, with `agent_role=developer` and `stage=decomposing`.
The late coordinator owns the result and uses the existing issue retry/resume
budget; it then requires a clean tree, freezes the resulting SHA, and measures
again. If the developer only acknowledges the guidance and leaves the commit
unchanged, the same SHA may be rechecked.

If title/body and a trusted answer arrive concurrently, title/body drift wins
and the issue parks. This avoids applying an answer to a scope that changed at
the same time.

### 7. Mandatory post-agent owner check

Every late agent completion is followed by a fresh issue-state read before any
snapshot creation, PR publication, supersession, or child activation:

- open: continue reconciliation;
- closed: enter irreversible cancellation cleanup;
- read failed: fail closed with a typed transient park and no external side
  effect.

A failed owner check automatically retries on the next eligible tick. It is
reconciliation-only, preserves the candidate/session anchors, and does not
need a human command or respawn an agent. If the park mentioned humans, a
successful retry posts one idempotent recovery follow-up, following the
`eccb4a8`/`5122a5e` precedent.

This rules out the existing generic fail-open pause probe for this boundary and
closes the race in which a human closes an issue while the late agent runs.

### 8. Snapshot creation and split transaction

Before creating or activating any child for a `split` verdict, create an
immutable remote snapshot ref and verify that it resolves to the exact frozen
candidate SHA. Snapshot operations run through the hardened authenticated Git
transport and target-root lock.

The exact ref namespace is selected by a disposable-repository capability
check before rollout. The acceptable choices are a custom ref namespace or a
repository-owned no-PR head namespace; the selected form must be creatable,
fetchable, verifiable, and deletable by the production token without weakening
repository rulesets. This operational selection does not change the workflow
contract.

After the ref is durable, convert the current issue into a forced umbrella
parent with no residual parent implementation. Record every direct child as a
snapshot consumer before activation, using the existing crash-safe
decomposition ordering. Children target the current base branch and receive:

- their declared scope;
- the ancestor snapshot ref and exact SHA;
- instructions to reuse only snapshot content relevant to their scope; and
- the lineage/cycle identity needed for telemetry and cleanup.

Reuse may cherry-pick coherent commits or copy selected paths, but never split
hunks automatically. Every implementing child runs the same late gate. The
child's late prompt always carries the child's declared scope so an indivisible
slice above 4,000 additions gets a fast `single` instead of reflexive
re-splitting.

Only after the snapshot and durable child ledger exist may the held plan PR be
superseded and children become runnable. Its supersession comment links forward
to the umbrella parent, every child, the snapshot ref, and exact SHA. If the PR
is open, close it. Failure to delete the ordinary superseded implementation
branch does not delay child activation, but is recorded and retried and blocks
the umbrella's final terminal transition. Local worktree cleanup is best
effort.

### 9. Snapshot ownership and reclamation

The generation ledger, not incidental labels or the current parent scan, owns
the snapshot. It survives drift resets, manual issue closure, and intermediate
label changes.

A snapshot becomes deletable only when every recorded direct consumer is
currently one of:

- `done`;
- `rejected`; or
- manually closed.

Unknown state, a failed read, or any open nonterminal consumer retains the
snapshot. Manual closure is observed anew on each sweep; it is not latched. If
a child is reopened before deletion, the ref remains. For a nested split, a
direct child reaching `done` is sufficient because that disposition proves its
own descendants no longer need the ancestor snapshot.

Snapshot deletion is part of v1 and gates the umbrella owner's terminal
completion. An absent ref means success, making deletion idempotent across
crashes. Permission, ruleset, or transport failures are loud, recorded, and
retried. A child reopened after deletion cannot reconstruct the snapshot; it
parks loudly and requires an explicit new cycle rather than fabricating a ref
whose contents cannot be proven.

Closed snapshot owners are revisited only by a narrow cleanup sweep on the
existing `CLOSED_ISSUE_SWEEP_EVERY_N_TICKS` cadence, sharing the existing label
cache and absent-label throttling. It introduces no new per-tick API traffic,
runs cap-exempt, and is cleanup-only: it never spawns an agent, resumes workflow,
or activates children.

This rules out reference TTLs, garbage collection based only on parent state,
blanket inclusion of all closed decomposition labels in normal dispatch, and a
follow-up release that leaves v1 snapshot objects alive indefinitely.

### 10. Manual close and cancellation

When the late-generation owner is observed closed, first persist an irreversible
cancellation marker, then perform external cleanup. Once observed, reopening
does not undo cancellation. A close-and-reopen interval that occurs entirely
between reads is necessarily unobserved.

Cancellation is reconciliation-only:

- do not spawn agents or create/activate more children;
- post one idempotent cancellation comment to a held plan PR and close it;
- clean up ordinary superseded branches when safe;
- leave every already-created child completely untouched—no close, relabel,
  or comment;
- retain the snapshot until the same current direct-consumer terminal rule is
  satisfied; and
- after every remote obligation is reconciled, transition the owner to
  `rejected` as a terminal no-op.

If a direct child remains active forever, cancellation may retain the snapshot
forever. That is preferable to invalidating live child recovery. The narrow
closed-owner sweep continues this cleanup but never resumes ordinary workflow.

### 11. Explicit restart after completed cancellation

Reopening a rejected issue alone remains a no-op. Restart requires both:

1. reopening the same issue; and
2. removing `rejected`.

The special path applies only when the authenticated pinned state proves a
completed late-cancellation cycle. It does not apply to generic rejected
issues, which can retain salvageable PR or branch state. Repository-permissioned
workflow-label removal is the operator authorization, so this narrow restart
bypasses `ALLOWED_ISSUE_AUTHORS` just as an existing manual workflow-label
override does.

Restart is a two-phase transaction on the existing authoritative pinned
comment:

1. Persist a new monotonic cycle ID, predecessor, intended target, and pending
   restart marker.
2. Idempotently post the restart notice and apply the target label.
3. Retire the pending marker only after both external effects reconcile.

The dispatcher recognizes pending restart state, so a crash cannot create two
cycles or duplicate notices. The fresh active cycle keeps only:

- the pinned comment identity;
- bounded `orchestrator_comment_ids`;
- cumulative issue usage fields; and
- monotonic cycle identity plus predecessor/audit linkage.

It clears all agent and session pins, PR and branch identities, children and
dependencies, snapshot/generation/cancellation fields, park state, drift
watermarks, retry/resume/review counters, and cycle timestamps. It recomputes
the current content baseline, writes a fresh cycle start/creation time, keeps
the same root issue, and resets lineage depth/generation to zero. The current
`DECOMPOSE` setting chooses whether the new cycle starts at decomposing or
implementing.

This rules out `/restart`, successor issues, a second pinned comment, implicit
restart on reopen, and stale state leaking from the cancelled cycle.

### 12. Observability

Emit two correlated primary event families:

- a measurement event for every clean committed candidate measured while the
  feature is enabled; and
- a verdict event for every late adjudication.

Typed measurement failures, owner-check recovery, snapshot lifecycle,
cancellation, cleanup failure, and restart events may extend those families.
Both the audit JSONL stream and analytics JSONL stream receive bounded,
self-contained records. Analytics remains non-blocking; neither analytics nor
audit write failure may alter workflow disposition. The audit copy must support
offline analysis even when the analytics database is unavailable.

Each measurement/verdict record carries the fields needed to join and analyze
it without reading pinned state:

- repository and issue number;
- cycle ID, root issue, lineage depth, and generation;
- source SHA and frozen base SHA;
- configured threshold and counted additions; and
- verdict, category, or typed failure where applicable.

Do not record raw rationale, file paths, diffs, prompts, or agent output.
Crashes can produce duplicate records; consumers deduplicate on correlation
keys rather than making workflow state depend on sink delivery.

The data answers three follow-up questions: whether depth 3 is approached,
which repositories repeatedly produce generated/data-dominated `single`
verdicts, and whether 4,000 additions creates excessive adjudication. A
per-repository threshold override is the first intended follow-up only if
telemetry demonstrates repository skew.

## Failure and recovery contract

| Boundary | Durable fact before side effect | Retry behavior |
| --- | --- | --- |
| Diff measurement | source/base SHA and measurement phase | Park loudly; bare continue remeasures, no developer |
| Plan-PR hold | generation and original PR body | Park before agent; trusted continue reconciles |
| Late agent | role/session/source/generation | Resume existing role; never duplicate a completed run |
| Post-agent owner read | completed agent result and exact SHA | Automatic next-tick read-only retry; fail closed |
| Snapshot create | intended ref and exact source SHA | Create-or-verify; mismatch parks, absence may create |
| Child create | ordered manifest and direct-consumer ledger slot | Reuse recorded child or create once, then activate |
| PR supersession | snapshot and child identities | Comment/close idempotently; links remain navigable |
| Branch cleanup | branch cleanup obligation | Failure does not block activation; does block final terminal |
| Snapshot delete | all current direct-consumer dispositions | Absence succeeds; failure records and retries |
| Cancellation | irreversible cancellation marker | Cleanup only, even if owner is reopened |
| Restart | new cycle ID and pending restart target | Reconcile notice/label once, then clear pending |

At every recovery point, a recorded SHA is evidence; current HEAD, current base,
or an inferred PR is not a substitute. This is the recovery path the worktree
probe outage lacked: repair the underlying cause, then trusted continue retries
reconciliation of the recorded commit without paying for or risking another
developer run.

## Compatibility and rollout

- Add fields to pinned JSON rather than rename existing fields, markers, labels,
  or event payloads.
- Add the legal `implementing` to `decomposing` transition and the minimum
  decomposition-family terminal/restart transitions required by the design.
- Keep normal terminal labels inert; only authenticated completed-cancellation
  state plus the explicit label removal can enter restart.
- Keep existing initial decomposition, publication, drift, author allowlist,
  usage accounting, and global retry semantics unchanged outside late mode.
- Pause or drain live late generations before deploying an older binary.
- Before enabling v1, use a disposable repository with production-equivalent
  token and rulesets to prove snapshot create/fetch/verify/delete, including
  absent-delete success. A failure blocks rollout rather than weakening rules.
- Ship the 4,000 default without a pre-launch corpus study. Review measurement
  and verdict telemetry after rollout; add a per-repository override only if
  the data shows systematic skew.

## Alternatives considered and why they lost

- **Discard the initial implementation and decompose from scratch.** Simpler
  lifecycle, but directly violates the issue's requirement to preserve useful
  progress and wastes developer work.
- **Push the oversized branch and let children depend on it.** Makes a mutable
  PR branch the artifact source and races human updates, merges, and automatic
  branch deletion. An immutable verified snapshot has a stable contract.
- **Keep the parent implementation and assign only residual work to children.**
  Produces two publication authorities and complicated merge ordering. A forced
  umbrella gives one clear owner per implementation slice.
- **Automatically partition commits or hunks.** Attractive for reuse, but file
  and hunk boundaries do not express issue scope and can create uncompilable or
  semantically mixed children. Scoped selective reuse keeps judgment with the
  child developer.
- **Exclude generated or vendored paths from the metric.** Reduces known false
  positives but creates a permanent bypass and hides suspicious artifacts. A
  fast semantic `single`/question verdict plus telemetry is safer.
- **Use a repository-specific threshold immediately.** More flexible, but no
  evidence yet identifies the right overrides. It expands configuration before
  measurement can justify it.
- **Create a new late-decomposition label/stage.** Makes state visually explicit
  but expands a live compatibility contract. Additive pinned mode under the
  existing decomposing label is enough.
- **Store snapshots only in local Git.** Avoids remote refs but cannot survive
  host loss and leaves remote child workers without the artifact. The agreed
  design accepts local-only durability only before snapshot creation.
- **Store the patch outside Git in object storage.** An unconventional option
  could avoid Git ref policy and object retention, but introduces a service,
  credentials, integrity protocol, and new source of truth. It does not fit the
  repository's GitHub-and-Git state model.
- **Delete snapshots on a TTL.** Operationally convenient but can invalidate a
  slow or parked child. Consumer state is the only safe reclamation signal.
- **Cascade-cancel children.** Produces fast cleanup but takes ownership away
  from independent issues and can destroy human progress. Cancellation stops
  new fan-out and leaves existing children alone.
- **Let reopen implicitly restart.** Easy to trigger accidentally and ambiguous
  with cleanup. Reopen plus workflow-label removal is an explicit,
  repository-permissioned gesture.
- **Make telemetry delivery transactional.** Would improve event exactly-once
  properties at the cost of blocking core workflow on optional sinks. Durable
  pinned reconciliation plus duplicate-tolerant analysis is the better split.

## Risks and how they appear

- **Threshold false positives:** many `single` verdicts, especially clustered
  by repository or artifact type. Address through the prompt first and use
  telemetry to justify a later per-repo override.
- **Threshold false negatives:** very large conceptual changes below 4,000
  additions. The gate is a size safety net, not a replacement for initial
  decomposition or review.
- **Snapshot namespace blocked by policy:** disposable-repo validation fails,
  blocking rollout. At runtime, an unexpected denial creates a loud retried
  park rather than an untracked local dependency.
- **Remote object retention:** snapshot deletion or branch cleanup repeatedly
  fails and the owner cannot reach terminal state. The cleanup ledger and audit
  events make the leak visible.
- **Rate-limit pressure:** extra closed queries exhaust GitHub primary limits.
  Avoided by sharing the existing closed-sweep cadence/cache and adding no
  per-tick cleanup query.
- **Close/agent race:** an agent finishes after a human cancels. The fresh
  fail-closed owner read routes to cleanup before irreversible publication.
- **State written by a newer binary is read by an older one:** live generation
  fields could be ignored. Operational pause/drain is required for downgrade.
- **Snapshot consumer reopens after deletion:** its original artifact cannot be
  proven. It parks loudly and requires a new cycle; it never reconstructs from
  a moving branch.
- **Duplicate side effects around crashes:** repeated comments, children, refs,
  or cycles. Persist-before-side-effect phases, exact identities, and
  create-or-verify reconciliation make each mutation idempotent.
- **Unbounded pinned state:** generations, comments, or telemetry metadata grow
  forever. Keep only active ledgers and bounded comment IDs; event history
  lives in the append-only sinks and cycle ancestry is compact.

## Implementation plan

1. Add and document the positive global threshold, additive late-cycle state
   schema, typed phases/reasons, and legal state transitions. Preserve current
   behavior when the feature is off or no late fields exist.
2. Add Git primitives to freeze the remote base, measure exact textual
   additions, and create/fetch/verify/delete the chosen immutable snapshot ref
   inside the existing authenticated transport and repository lock.
3. Add audit and analytics producers for measurement, verdict, lineage,
   failure, snapshot, cleanup, cancellation, and restart. Keep both sinks
   fail-open and records bounded/self-contained.
4. Insert the measurement gate at the clean committed pre-publication seam.
   Persist exact SHA state before measurement and route oversize work to
   decomposing without pushing it.
5. Extend decomposition with an explicit late coordinator: plan-PR hold,
   specialized prompt/parser, exact-SHA `single`, bounded `split`, categorized
   questions, local fingerprints, preserved developer revision, and the
   mandatory post-agent owner check.
6. Implement the snapshot-first split transaction, forced umbrella, scoped
   child reuse context, direct-consumer ledger, forward-linked plan-PR
   supersession, PR close support, and durable nonblocking branch cleanup.
7. Implement current-state snapshot reclamation and the narrow, cap-exempt
   closed-owner cleanup sweep on the existing cadence and label cache.
8. Implement irreversible manual-close cancellation and its cleanup-only
   reconciliation, leaving existing children untouched.
9. Implement the authenticated completed-cancellation restart transaction on
   the same pinned comment, including fresh-cycle state projection and pending
   crash recovery.
10. Update the authoritative architecture, state-machine, workflow,
    configuration, observability, security, and operator-runbook documentation
    with the shipped interfaces and rollout/downgrade constraints.

## Verification plan

- Unit-test configuration validation and strict `>` threshold semantics.
- Use real temporary Git repositories to test prospective-diff counting across
  text, binary, generated/data files, renames, base movement, and candidate
  SHAs; no test may depend on a working-tree approximation.
- Test every persist/side-effect crash boundary by retrying from each phase and
  asserting no duplicate agents, children, refs, comments, PRs, or cycles.
- Test exact-SHA `single` exemption and remeasurement after any new commit.
- Test depth 0 through 3, nested child scope propagation, and direct-child
  snapshot completion semantics.
- Test title/body versus trusted-comment drift, concurrent edits, categorized
  questions, manual relabel restoration, and `DECOMPOSE=off` with both new and
  in-flight candidates.
- Test post-agent open, closed, and read-failed outcomes, including automatic
  recovery and one idempotent recovery follow-up.
- Test cancellation before and after snapshot/child/PR side effects, direct
  consumer reopen before deletion, absent ref deletion, persistent deletion
  failure, and reopen after deletion.
- Test the narrow closed sweep at cadence boundaries, cached/absent labels,
  cap exemption, no agent invocation, and no ordinary child activation.
- Test restart authorization, generic rejected exclusion, two-phase crashes,
  state projection, cycle lineage, allowlist bypass, and current `DECOMPOSE`
  routing.
- Assert event schemas contain all analysis fields and no raw path, diff,
  prompt, rationale, or output; simulate unavailable audit and analytics sinks
  to prove workflow remains live.
- Run the full test suite and the disposable-repository snapshot namespace and
  permission check before rollout.

## Decision frontier

No architecture questions remain open. Snapshot namespace selection is a
pre-rollout capability check between two implementations of the same agreed
interface, and threshold tuning is explicitly post-rollout empirical work; they
do not block implementation of this design.
