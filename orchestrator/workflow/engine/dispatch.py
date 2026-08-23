# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""How a tick's pollable issues become handler calls.

Everything between "the repo has open issues" and "one `_handle_<stage>` is
running" lives here, because the decisions are one chain and each link is only
safe given the one before it.

The chain starts with the hard-skip filter. `backlog` / `paused` park an issue
outside the state machine entirely, and the filter runs twice on purpose: once
in `_classify_pollable_issue` so a parked issue never reaches the partition,
and once in `_process_issue` so a directly dispatched one is still refused.
Dropping it early is not an optimization -- a parked issue carries no workflow
label, so leaving it in would fold it into the family bucket and flip that
bucket cap-counted, reserving the only per-repo slot under the default
`parallel_limit=1` and starving every fan-out issue behind a hold nobody is
working on.

The partition is the concurrency contract. Family-aware labels (`decomposing`
/ `blocked` / `umbrella`) and the unlabeled-pickup `None` are cross-issue
writers -- a parent's recovery seeds `parent_number` on a child whose own
handler would clobber the same pinned-state comment -- so they collect into one
bucket that drains sequentially, and everything else fans out. A label read
that raises is answered `(False, None)`, which routes that issue into the
family bucket rather than dropping it: the conservative side of an unreadable
label is the serialized one, where `_process_issue`'s per-issue exception
isolation picks up a sustained failure.

Cap exemption is what keeps the serialization from deadlocking. A bucket whose
every label is a no-agent, no-worktree handler (`_CAP_EXEMPT_FAMILY_LABELS`)
skips the per-repo and global caps, because a `blocked` parent polling its own
children would otherwise wait on the only slot those children need to finish.
Closed fan-out issues are exempt for the same reason at the other end: their
handler is a terminal finalize with no spawn, so it must not queue behind
active agent work.

A closed issue on the two cleanup-swept decomposition labels is the one case
where the label does NOT name the handler. `decomposing` and `umbrella` reach
the sweep yielding them only so their generation ledger can be settled, and
handing one to the stage handler its label names would spawn the decomposer on
an issue a human closed, or walk a dependency graph and activate children under
it. So the cleanup route is taken FIRST, ahead of the table and ahead of the
pinned-state guards, and the issue never reaches either.

Past that route, one read of the issue's own pinned comment answers two
questions that can stop the tick outright: a live late adjudication the label
was moved out from under, and a child of a split whose snapshot the remote no
longer has. The second is asked here rather than in a stage precisely because
the issue it is about is one nothing below would touch -- a consumer that ended
wears `done` or `rejected`, reopening leaves the label where it was, and both
are terminal no-ops.

That is also why such an issue is partitioned as FAN-OUT rather than into the
family bucket, despite wearing a family-aware label. The bucket's exemption is
all-or-nothing, so a closed owner sharing it with an open `decomposing` issue
would be cap-counted and skipped under saturated caps -- cleanup starved by
work it has nothing to do with. As fan-out it is submitted cap-exempt on its
own, and it does not need the family mutex: what serializes a parent against
its children is a mutex over handlers that ACTIVATE, and this one reads its
consumers and writes only issues it has proved terminal. The fan-out lane
already runs those consumers' own closed-sweep finalizers concurrently, so the
bucket would not have protected against them either.

Only issue NUMBERS cross the thread boundary. PyGithub's `Issue` and the
`GitHubClient` / `Repository` / `Requester` chain behind it hold mutable
per-request state that is not documented thread-safe, so `_refetch_and_process`
mints a per-worker client and refetches against it -- every in-flight call is
then the sole consumer of its own requester.

That refetch is also what makes the cleanup classification safe to act on,
which is why the sequential path takes one of its own. A closed owner is
routed to the sweep on a reading taken during enumeration, and the sweep's
re-read of the close is only a question if the issue was read again since -- so
`_process_polled_issue` classifies and refetches on the caller's thread rather
than dispatching the object the poll yielded.

The handler for a label is reached by importing the module
`_STAGE_HANDLER_TARGETS` pairs it with, at call time: twelve of them are
conflicts, decomposition, discussion, documenting, fixing, implementing,
question, validating, and in_review owners under `workflow/stages/`, and the
thirteenth is the `pickup` sibling an unlabeled issue starts on -- and the stage
tree imports this subpackage, so binding any of them
at module scope would point that edge back at itself. Every entry names the
owner its handler lives on, so the patch that intercepts a dispatch is the one
against whichever module the table names.
"""
from __future__ import annotations

import contextlib
import functools
import importlib
import logging
import time
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping, Optional

from github.Issue import Issue

from orchestrator import config
from orchestrator.github.client import GitHubClient
from orchestrator.github.issues import CLEANUP_SWEEP_LABELS, issue_is_closed
from orchestrator.observability.analytics import recording
from orchestrator.github.labels import hard_skip_control_label
from orchestrator.scheduler import IssueScheduler
from orchestrator.workflow.state import WorkflowLabel, stage_name

log = logging.getLogger("orchestrator.workflow")

# Every isolated per-issue failure reports through one line so an operator
# grepping a tick's log sees the same shape whether the issue was dispatched
# sequentially, refetched on a worker, or drained from the family bucket.
_PROCESSING_FAILED_LOG = "repo=%s issue=#%s processing failed"

_FAMILY_AWARE_LABELS = frozenset((
    WorkflowLabel.DECOMPOSING, WorkflowLabel.BLOCKED, WorkflowLabel.UMBRELLA,
))

_CAP_EXEMPT_FAMILY_LABELS = frozenset((
    WorkflowLabel.BLOCKED, WorkflowLabel.UMBRELLA,
))

# The labels whose CLOSED issues the sweep yields for cleanup only. Kept as a
# set of the members the sweep publishes so the two cannot drift: a label
# queried there and missing here is a closed issue dispatched to the stage
# handler its label names, which is the one thing the cleanup route exists to
# prevent.
_CLEANUP_SWEEP_LABELS = frozenset(CLEANUP_SWEEP_LABELS)

_FAMILY_BUCKET_ISSUE: int = 0

_CONFLICTS_PACKAGE = "orchestrator.workflow.stages.conflicts"
_DECOMPOSITION_PACKAGE = "orchestrator.workflow.stages.decomposition"
_LATE_RELABEL_OWNER = f"{_DECOMPOSITION_PACKAGE}.late_relabel"
_LATE_REUSE_OWNER = f"{_DECOMPOSITION_PACKAGE}.late_reuse"
_DISCUSSION_PACKAGE = "orchestrator.workflow.stages.discussion"
_DOCUMENTING_PACKAGE = "orchestrator.workflow.stages.documenting"
_FIXING_PACKAGE = "orchestrator.workflow.stages.fixing"
_IMPLEMENTING_PACKAGE = "orchestrator.workflow.stages.implementing"
_IN_REVIEW_PACKAGE = "orchestrator.workflow.stages.in_review"
_QUESTION_PACKAGE = "orchestrator.workflow.stages.question"
_VALIDATING_PACKAGE = "orchestrator.workflow.stages.validating"

_TERMINAL_LABELS = (WorkflowLabel.DONE, WorkflowLabel.REJECTED)

# The one handler a label does not choose. It is reached by being closed on a
# cleanup-swept label instead, and it is deliberately not in the table below:
# an entry there would make it the handler for those labels open or closed.
_CLEANUP_SWEEP_TARGET = (
    f"{_DECOMPOSITION_PACKAGE}.late_sweep", "_handle_closed_owner_cleanup",
)

# Keyed by the member rather than the label string so the table cannot drift
# from the vocabulary it routes: a relabeled state is a lookup miss here, and a
# lookup miss is an issue nobody handles.
_STAGE_HANDLER_TARGETS: Mapping[Optional[str], tuple[str, str]] = MappingProxyType({
    None: ("orchestrator.workflow.engine.pickup", "_handle_pickup"),
    WorkflowLabel.DECOMPOSING: (f"{_DECOMPOSITION_PACKAGE}.run", "_handle_decomposing"),
    WorkflowLabel.READY: (f"{_DECOMPOSITION_PACKAGE}.blocked", "_handle_ready"),
    WorkflowLabel.BLOCKED: (f"{_DECOMPOSITION_PACKAGE}.blocked", "_handle_blocked"),
    WorkflowLabel.UMBRELLA: (f"{_DECOMPOSITION_PACKAGE}.umbrella", "_handle_umbrella"),
    WorkflowLabel.IMPLEMENTING: (f"{_IMPLEMENTING_PACKAGE}.handler", "_handle_implementing"),
    WorkflowLabel.DOCUMENTING: (f"{_DOCUMENTING_PACKAGE}.handler", "_handle_documenting"),
    WorkflowLabel.VALIDATING: (f"{_VALIDATING_PACKAGE}.handler", "_handle_validating"),
    WorkflowLabel.IN_REVIEW: (f"{_IN_REVIEW_PACKAGE}.handler", "_handle_in_review"),
    WorkflowLabel.FIXING: (f"{_FIXING_PACKAGE}.handler", "_handle_fixing"),
    WorkflowLabel.RESOLVING_CONFLICT: (
        f"{_CONFLICTS_PACKAGE}.handler", "_handle_resolving_conflict",
    ),
    WorkflowLabel.QUESTION: (f"{_QUESTION_PACKAGE}.handler", "_handle_question"),
    WorkflowLabel.DISCUSSION: (f"{_DISCUSSION_PACKAGE}.handler", "_handle_discussion"),
})


def _pinned_state_refuses(
    gh: GitHubClient, spec: config.RepoSpec, issue: Issue, label: Optional[str],
) -> bool:
    """True when what this issue's own pinned comment records stops the tick.

    ONE read, two questions, because the read is what costs -- a comment walk
    per labelled issue per tick, on top of the one that issue's own handler
    makes.

    The first is a live late adjudication. An oversized committed candidate is
    adjudicated under ``workflow:decomposing``, and while that question is open
    the label is not a state anything else may set. A hand relabel cannot be
    refused where it is written -- the orchestrator never sees that write -- so
    it is caught here, the one place a label becomes a handler call: the issue
    is put back and left for the next tick rather than dispatched to whichever
    stage the new label named, which for ``ready`` or ``implementing`` would
    publish a candidate nobody adjudicated.

    The second is a child of a split whose snapshot has since been reclaimed.
    That one has to be asked HERE rather than inside a stage, because the issue
    it is about is one the dispatcher would otherwise have nothing to do with:
    a consumer that ended wears ``done`` or ``rejected``, reopening leaves the
    label where it was, and both are terminal no-ops below. Asking before the
    table also means a relabel straight to another stage cannot route around
    it. It costs nothing extra on the wire in the steady state -- the guard
    asks this host before it asks the remote.

    Both step aside for the label the adjudication actually sits on, which is
    where every one of its own ticks is spent, and where an ancestor's snapshot
    is not what the issue is working from -- but only once the record PROVES
    the adjudication is this issue's own. The label alone proves nothing: a
    child of a split closed while it was being decomposed comes back with
    ``decomposing`` exactly where it was and no generation at all, and its
    ancestor's ref may well have been reclaimed while it was closed. Waving
    that through on the label would spawn the decomposer against the reuse
    instructions in its body, naming a ref that is gone. So the read is taken
    first and the label is answered out of it. Imported at call time like the
    handlers below, since the stage tree imports this module.
    """
    late_relabel = importlib.import_module(_LATE_RELABEL_OWNER)
    state = late_relabel._dispatch_state(gh, issue)
    if state is None:
        return True
    if label == WorkflowLabel.DECOMPOSING and late_relabel._adjudicating(state):
        return False
    if late_relabel._holds_the_label(gh, issue, state):
        log.warning(
            "repo=%s issue=#%s was relabelled %r while its committed candidate "
            "was under adjudication; not dispatching it",
            spec.slug, issue.number, label,
        )
        return True
    late_reuse = importlib.import_module(_LATE_REUSE_OWNER)
    return late_reuse._refuses_reuse(gh, spec, issue, state)


def _cleanup_sweep_only(issue: Issue, label: Optional[str]) -> bool:
    """True when this issue is here for its ledger and nothing else.

    A closed issue on ``decomposing`` or ``umbrella`` reaches a tick only
    because the cleanup sweep asked for it, and what it is owed is a pass over
    its generation ledger. Its label still names a stage handler -- one that
    spawns the decomposer, or one that walks a dependency graph and activates
    children -- so the closed reading has to be taken before the label is, or
    the sweep would be resuming the workflow a human closed.
    """
    return label in _CLEANUP_SWEEP_LABELS and issue_is_closed(issue)


def _call_handler(
    gh: GitHubClient,
    spec: config.RepoSpec,
    issue: Issue,
    target: tuple[str, str],
) -> None:
    """Import the module a target names and run the handler off it."""
    module_name, handler_name = target
    issue_handler = getattr(importlib.import_module(module_name), handler_name)
    issue_handler(gh, spec, issue)


def _route_issue_to_handler(
    gh: GitHubClient,
    spec: config.RepoSpec,
    issue: Issue,
    label: Optional[str],
    *,
    cleanup_only: bool = False,
) -> None:
    """Dispatch one issue to its stage handler by workflow label.

    The module the table names is imported at call time and the handler read
    off it as an attribute, so the patch that intercepts a dispatch is the one
    against that module -- the stage's own handler owner.
    ``done`` / ``rejected`` are terminal no-ops; an unrecognized label is
    logged and left alone for a human. Timing and the ``stage_evaluation``
    analytics record stay in ``_process_issue``, which wraps this call in its
    try / except / finally.

    Two routes are taken ahead of the table. A closed issue on a cleanup-swept
    label goes to the sweep owner, because its label names a handler that would
    resume the workflow its close ended. And what the issue's own pinned
    comment records can stop the tick outright -- a live adjudication the label
    was moved out from under, or a snapshot this child was cut from and the
    remote no longer has. The cleanup route comes first: that guard spends a
    pinned read to decide, and a closed owner is not dispatched on either
    answer.

    ``cleanup_only`` is that first route arriving as a decision rather than as
    a reading. It is set by the submit that a closed cleanup owner was
    classified into, and it BINDS: the worker refetches the issue after the
    classification, so a human who reopens one in that window would otherwise
    have the freshly-read label send it to the handler its cap-exempt submit
    was granted on the understanding it would never reach. The sweep refuses
    an issue that is open again, so the answer to that race is a no-op and a
    correctly classified next tick.
    """
    if cleanup_only or _cleanup_sweep_only(issue, label):
        _call_handler(gh, spec, issue, _CLEANUP_SWEEP_TARGET)
        return
    if _pinned_state_refuses(gh, spec, issue, label):
        return
    target = _STAGE_HANDLER_TARGETS.get(label)
    if target is not None:
        _call_handler(gh, spec, issue, target)
    elif label not in _TERMINAL_LABELS:
        log.warning(
            "repo=%s issue=#%s label=%r not implemented yet; leaving alone",
            spec.slug, issue.number, label,
        )


def _process_polled_issue(
    gh: GitHubClient, spec: config.RepoSpec, issue: Issue,
) -> None:
    """Dispatch one issue this thread polled and still holds.

    The sequential path's own entry, and what it adds over `_process_issue` is
    the classification the other two paths get on their way to a worker: an
    issue on a cleanup-swept label is refetched before anything routes it, and
    a CLOSED reading at poll time additionally BINDS it to the sweep.

    The refetch is the load-bearing half, and it is taken on both readings of
    the close rather than on one. The object in hand is the enumeration's,
    and the two labels this applies to are the two where the close decides
    which handler runs: an owner closed after the poll would otherwise reach
    the stage its label names on a stale open reading -- spawning the
    decomposer, or walking a dependency graph and activating children, on an
    issue a human just ended -- and an owner reopened after the poll would
    have a cleanup pass settle a ledger the live cycle is writing again, since
    the sweep's own close re-read would be re-reading the same stale object.

    The binding is the other half, and it is one-way for the reason the
    workers' is: a closed classification may not become an agent-spawning
    stage handler on the strength of a reopen this tick raced, while an issue
    that was open when it was polled has been classified as ordinary work all
    along and the freshly-read close is what sends it to the sweep.

    Refetched on the caller's own client rather than through
    `_refetch_and_process`: nothing here crosses a thread, so what that mints
    a per-worker client for does not apply, while the read it takes does.

    Hard-skipped issues are dropped here as the partition drops them, rather
    than inside `_process_issue`, so the classification this path takes is the
    same one the other two take.
    """
    skip, label = _classify_pollable_issue(gh, spec, issue)
    if skip:
        return
    if label not in _CLEANUP_SWEEP_LABELS:
        _process_issue(gh, spec, issue)
        return
    _process_issue(
        gh, spec, gh.get_issue(int(issue.number)),
        cleanup_only=issue_is_closed(issue),
    )


def _process_issue(
    gh: GitHubClient,
    spec: config.RepoSpec,
    issue: Issue,
    *,
    cleanup_only: bool = False,
) -> None:
    # Postponed-task hold: applying `backlog` (or `paused`) parks the issue
    # outside the state machine entirely until the label is removed. Checked
    # before reading the workflow label so the orchestrator never decomposes,
    # spawns an agent, or otherwise reacts while the operator is using the
    # label as a "not yet" signal. Hard-skips are NOT counted as a stage
    # evaluation: no handler runs and there is nothing to time.
    skip_label = hard_skip_control_label(issue)
    if skip_label is not None:
        log.info(
            "repo=%s issue=#%s has %r; skipping",
            spec.slug, issue.number, skip_label,
        )
        return
    label = gh.workflow_label(issue)
    log.info("repo=%s issue=#%s label=%r", spec.slug, issue.number, label)
    # Time the handler dispatch and append a single `stage_evaluation`
    # analytics record on exit. `evaluation_result` flips to "error" inside the
    # except clause so an unhandled exception still produces a timing
    # record before propagating -- the tick loop's per-issue try/except
    # already logs and isolates the failure, so re-raising here keeps
    # the existing dispatch / exception contract intact. The append
    # itself is internally hardened against OSError; an analytics
    # misconfiguration cannot stop the per-issue tick from advancing.
    start = time.monotonic()
    evaluation_result = "ok"
    try:
        _route_issue_to_handler(
            gh, spec, issue, label, cleanup_only=cleanup_only,
        )
    except Exception:
        evaluation_result = "error"
        raise
    finally:
        duration_s = round(time.monotonic() - start, 3)
        recording.record_stage_evaluation(
            repo=getattr(gh, "_repo_slug", None) or "",
            issue=issue.number,
            stage=stage_name(label),
            duration_s=duration_s,
            result=evaluation_result,
        )


@dataclass(frozen=True)
class _PollablePartition:
    """Family / fanout split of one repo's pollable issues for a single tick.

    ``family_numbers`` and ``family_labels`` are index-aligned so the
    cap-exempt decision (`_family_bucket_cap_exempt`) can read each
    family-aware issue's workflow label. ``fanout_closed`` is the subset of
    ``fanout_numbers`` whose issue is already closed -- a cheap terminal
    finalize, or a cleanup pass over a closed owner's ledger, and neither
    spawns, so both are submitted cap-exempt.
    """
    family_numbers: list[int]
    family_labels: list[Optional[str]]
    fanout_numbers: list[int]
    fanout_closed: set[int]
    cleanup_numbers: set[int] = field(default_factory=set)


@dataclass
class _PollablePartitionBuilder:
    family_numbers: list[int] = field(default_factory=list)
    family_labels: list[Optional[str]] = field(default_factory=list)
    fanout_numbers: list[int] = field(default_factory=list)
    fanout_closed: set[int] = field(default_factory=set)
    cleanup_numbers: set[int] = field(default_factory=set)

    def add(self, issue_number: int, label: Optional[str], closed: bool) -> None:
        if _drains_in_family_bucket(label, closed):
            self.family_numbers.append(issue_number)
            self.family_labels.append(label)
            return
        self.fanout_numbers.append(issue_number)
        if closed:
            self.fanout_closed.add(issue_number)
        if closed and label in _CLEANUP_SWEEP_LABELS:
            self.cleanup_numbers.add(issue_number)

    def build(self) -> _PollablePartition:
        return _PollablePartition(
            self.family_numbers,
            self.family_labels,
            self.fanout_numbers,
            self.fanout_closed,
            self.cleanup_numbers,
        )


def _drains_in_family_bucket(label: Optional[str], closed: bool) -> bool:
    """Whether this issue belongs in the serialized, all-or-nothing bucket.

    Every family-aware label does, with one exception: a CLOSED issue on a
    cleanup-swept label runs the sweep rather than the stage its label names,
    and the sweep neither spawns nor activates. Leaving it in the bucket would
    tie its exemption to whatever else landed there -- one open `decomposing`
    issue and the whole bucket is cap-counted, so a repository at its cap
    stops reclaiming refs until the decomposer is idle.
    """
    if closed and label in _CLEANUP_SWEEP_LABELS:
        return False
    return label is None or label in _FAMILY_AWARE_LABELS


def _read_issue_routing(
    gh: GitHubClient, spec: config.RepoSpec, issue: Issue,
) -> tuple[bool, Optional[str]]:
    """Return ``(skip, label)`` from the issue's control / workflow labels."""
    skip_label = hard_skip_control_label(issue)
    if skip_label is not None:
        log.info(
            "repo=%s issue=#%s has %r; skipping",
            spec.slug, issue.number, skip_label,
        )
        return True, None
    return False, gh.workflow_label(issue)


def _classify_pollable_issue(
    gh: GitHubClient, spec: config.RepoSpec, issue: Issue,
) -> tuple[bool, Optional[str]]:
    """Read one pollable issue's workflow label for the family / fanout split.

    Returns ``(skip, label)``. ``skip=True`` marks a hard-skip control label
    (``backlog`` / ``paused``): the operator parked the issue outside the
    state machine, so the caller drops it BEFORE the partition -- a parked,
    workflow-label-less issue folded into the family bucket would flip the
    whole bucket cap-counted and starve fanout under ``parallel_limit=1``
    (``_process_issue`` skips it anyway).

    A label-read failure (including one raised by ``hard_skip_control_label``
    itself) is reported as ``(False, None)`` so the issue is conservatively
    routed into the family bucket, where ``_process_issue``'s own per-issue
    exception isolation picks up any sustained failure. The label read runs
    on the caller thread so bucketing needs no extra worker-side round-trip.
    """
    try:
        return _read_issue_routing(gh, spec, issue)
    except Exception:
        log.exception(
            "repo=%s issue=#%s label read failed; routing to family bucket "
            "so per-issue exception isolation can pick up any sustained "
            "failure", spec.slug, issue.number,
        )
        return False, None


def _partition_pollable_issues(
    gh: GitHubClient, spec: config.RepoSpec,
) -> _PollablePartition:
    """Split this tick's pollable issues into the family and fanout buckets.

    Family-aware labels (``decomposing`` / ``blocked`` / ``umbrella``) and
    the unlabeled-pickup ``None`` are cross-issue writers -- a parent's
    ``_handle_decomposing`` recovery seeds ``parent_number`` on a child
    while the child's ``_handle_blocked`` would otherwise clobber the same
    pinned-state comment -- so they must never run two at a time and are
    collected into ``family_numbers`` (with index-aligned ``family_labels``).
    Every other label touches only its own per-issue state and fans out, as
    does a CLOSED issue on a cleanup-swept label, whose handler is the sweep
    rather than the stage its label names. A closed fan-out issue is
    additionally recorded in ``fanout_closed``, because what it runs is a
    cheap terminal finalize or a cleanup pass over a closed owner's ledger --
    neither spawns, so both are submitted cap-exempt. Hard-skip (``backlog``
    / ``paused``) issues are dropped entirely.
    """
    builder = _PollablePartitionBuilder()
    for issue in gh.list_pollable_issues():
        skip, label = _classify_pollable_issue(gh, spec, issue)
        if skip:
            continue
        builder.add(int(issue.number), label, issue_is_closed(issue))
    return builder.build()


def _family_bucket_cap_exempt(family_labels: list[Optional[str]]) -> bool:
    """True when a family bucket may skip the per-repo / global caps.

    A bucket is cap-exempt only when EVERY issue in it this tick runs a
    no-agent / no-worktree handler -- all labels in ``_CAP_EXEMPT_FAMILY_LABELS``
    (``blocked`` / ``umbrella``, pure dep-graph walks). Such a bucket must
    always get its turn even when the parallel caps are saturated by real
    implementation work: a ``blocked`` parent polling its children, or an
    ``umbrella`` aggregating them, would otherwise be starved of the only
    per-repo slot under the default ``parallel_limit=1`` -- and a ``blocked``
    parent waiting on its own children would deadlock them. A bucket
    containing ``decomposing`` (spawns the decomposer agent) or an
    unlabeled-pickup ``None`` (routes through ``_handle_pickup``, may spawn an
    agent) stays cap-counted.

    A closed issue on a cleanup-swept label is not here to be exempted: it is
    partitioned as fan-out instead (see ``_drains_in_family_bucket``), so it
    is submitted cap-exempt on its own rather than tying its turn to whatever
    else this bucket happens to hold.
    """
    return all(lbl in _CAP_EXEMPT_FAMILY_LABELS for lbl in family_labels)


def _refetch_and_process(
    gh: GitHubClient,
    spec: config.RepoSpec,
    issue_number: int,
    *,
    semaphore_cm: Optional[contextlib.AbstractContextManager] = None,
    cleanup_only: bool = False,
) -> None:
    """Mint a per-worker client, refetch the Issue, and run its handler.

    Only issue NUMBERS cross the thread boundary. PyGithub's ``Issue`` and
    the parent ``GitHubClient`` / ``Repository`` / ``Requester`` chain hold
    mutable per-request state that is not documented thread-safe, so each
    worker calls ``gh._for_worker_thread()`` to mint a fresh client and
    refetches its Issue against THAT client -- every in-flight HTTP call is
    then the sole consumer of its requester's state.

    ``semaphore_cm`` wraps the ``_process_issue`` call so the in-tick parallel
    path can thread the cross-repo ``global_semaphore`` through here; the
    scheduler path leaves it ``None`` (a no-op) because the scheduler owns
    the cross-repo cap itself.

    ``cleanup_only`` rides along because the refetch is exactly where a
    classification can go stale. A closed cleanup owner is submitted on its
    own cap-exempt terms, and a reopen between the poll and this call must not
    turn that submit into an agent-spawning stage handler running outside the
    caps -- so the route is carried rather than re-derived.
    """
    worker_gh = gh._for_worker_thread()
    worker_issue = worker_gh.get_issue(issue_number)
    cm = contextlib.nullcontext() if semaphore_cm is None else semaphore_cm
    with cm:
        _process_issue(
            worker_gh, spec, worker_issue, cleanup_only=cleanup_only,
        )


def _drain_scheduler_family_bucket(
    gh: GitHubClient,
    spec: config.RepoSpec,
    scheduler: IssueScheduler,
    family_numbers: list[int],
) -> None:
    """Drain this tick's family-aware issues sequentially under one bucket.

    Runs as the single ``family=True`` scheduler submit per repo, so the
    family slot is held for the whole drain: a concurrent tick mid-drain
    cannot squeeze a second family worker past the gate and no two
    family-aware handlers ever run at once. ``scheduler.track_active`` wraps
    each iteration so ``is_active(repo, n)`` reports True for the issue
    currently being processed inside the bucket -- the pre-tick base refresh
    relies on that signal to avoid rebasing a worktree under a running agent;
    without the per-iteration claim only the bucket's sentinel key would
    appear in the in-flight set and a concurrent refresh would race the agent.

    ``track_active`` yields a ``claimed`` bool: when False the issue is
    already in flight on another worker (e.g. a fanout submit accepted on a
    previous tick before this issue was relabeled into the family bucket), so
    the drain skips ``_process_issue`` for that iteration and the next polling
    pass picks it up once the other worker exits -- two workers running the
    same handler concurrently would race the worktree and pinned state.
    Per-issue exception isolation lives inside the loop so one raising family
    handler does not abort the rest of the bucket.

    Each per-issue call mirrors the fanout path: ``_refetch_and_process``
    mints a fresh ``GitHubClient`` via ``gh._for_worker_thread()`` and
    refetches the Issue against it (PyGithub is not documented thread-safe).
    """
    for issue_number in family_numbers:
        try:
            with scheduler.track_active(spec.slug, issue_number) as claimed:
                if not claimed:
                    log.info(
                        "repo=%s issue=#%s already in flight; "
                        "family bucket skipping this iteration",
                        spec.slug, issue_number,
                    )
                    continue
                _refetch_and_process(gh, spec, issue_number)
        except Exception:
            log.exception(
                _PROCESSING_FAILED_LOG,
                spec.slug, issue_number,
            )


def _scheduler_per_repo_cap(spec: config.RepoSpec) -> int:
    return max(1, int(getattr(spec, "parallel_limit", 1) or 1))


def _submit_scheduler_family_bucket(
    gh: GitHubClient,
    spec: config.RepoSpec,
    scheduler: IssueScheduler,
    partition: _PollablePartition,
    per_repo_cap: int,
) -> None:
    family_numbers = partition.family_numbers
    if not family_numbers:
        return

    submitted = scheduler.submit(
        spec.slug,
        _FAMILY_BUCKET_ISSUE,
        functools.partial(
            _drain_scheduler_family_bucket, gh, spec, scheduler, family_numbers,
        ),
        family=True,
        cap_exempt=_family_bucket_cap_exempt(partition.family_labels),
        per_repo_cap=per_repo_cap,
    )
    if submitted:
        return

    # The scheduler logs the precise skip reason (closed, family_slot_held,
    # cap, ...) inside `submit`; this line gives the dispatch-layer context
    # -- which issues were waiting on this bucket -- so an operator can
    # correlate "umbrella not advancing" with a previous tick's bucket
    # still in flight.
    log.info(
        "repo=%s family bucket (%d issues) not submitted this "
        "tick; next polling pass retries",
        spec.slug, len(family_numbers),
    )


def _submit_scheduler_fanout_issues(
    gh: GitHubClient,
    spec: config.RepoSpec,
    scheduler: IssueScheduler,
    partition: _PollablePartition,
    per_repo_cap: int,
) -> None:
    for issue_number in partition.fanout_numbers:
        scheduler.submit(
            spec.slug,
            issue_number,
            functools.partial(
                _refetch_and_process,
                gh,
                spec,
                issue_number,
                cleanup_only=issue_number in partition.cleanup_numbers,
            ),
            family=False,
            # A closed issue's handler is a cheap terminal finalization with
            # no agent spawn -- exempt it from the per-repo / global caps so
            # a merged-PR or closed-question issue flips to `done` promptly
            # instead of being starved behind active agent work under
            # `parallel_limit=1` (mirrors the `_CAP_EXEMPT_FAMILY_LABELS`
            # exemption for `blocked` / `umbrella`).
            cap_exempt=(issue_number in partition.fanout_closed),
            per_repo_cap=per_repo_cap,
        )


def _dispatch_via_scheduler(
    gh: GitHubClient, spec: config.RepoSpec, scheduler: IssueScheduler,
) -> None:
    """Enumerate pollable issues this tick and hand work to the scheduler.

    Family-aware work (unlabeled pickup + decomposing / blocked /
    umbrella -- the cross-issue writers) is folded into ONE bucket
    submit per repo that drains its issues sequentially on a single
    worker thread; non-family issues are submitted individually. The
    in-tick parallel path in ``tick()`` partitions the same way (one
    drain task for the family bucket, per-issue futures for fanout).

    One bucket per repo is what keeps the family mutex from starving
    itself. The scheduler grants the family slot to the first accepted
    ``family=True`` submit and silently skips every later one this tick,
    so a per-issue family submit would let a stale ``blocked`` child
    take the slot while the parent ``umbrella`` that should relabel it
    never runs -- and the pair would trade the slot back and forth
    forever. Draining every family issue inside the one accepted submit
    means the umbrella always gets its turn within the same tick.

    The bucket task uses ``scheduler.track_active`` around each
    per-issue iteration so ``scheduler.is_active(repo, n)`` reports True
    for the issue currently being processed inside the bucket -- the
    pre-tick base refresh relies on that signal to avoid rebasing a
    worktree under a running agent. Without per-iteration tracking,
    only the bucket's sentinel key would appear in the in-flight set
    and a concurrent refresh would race the agent.

    Each per-issue callable mirrors the in-tick parallel path: mint a
    fresh ``GitHubClient`` via ``gh._for_worker_thread()`` and refetch
    the Issue against that client so the worker drives its own
    Requester chain (PyGithub is not documented thread-safe).

    Completion reaping is the polling loop's job, not this function's.
    ``runtime.ticks.run_tick`` calls ``scheduler.reap()`` exactly once
    after every configured repo's tick returns, which is the cadence surfaced
    to operators and documented in ``docs/observability.md`` ("one reap
    per polling pass"). Reaping here as well would multiply that to N+1
    reaps per pass under ``REPOS``.

    ``spec.parallel_limit`` is forwarded as the scheduler's per-call cap
    override so a per-repo configuration tighter than the scheduler
    default still binds. Label-read failures route the offending issue
    into the family bucket so ``_process_issue``'s own exception
    isolation picks up any sustained failure -- the same recovery the
    in-tick parallel path uses.

    When every family-aware issue this tick runs a no-agent handler
    (label in ``_CAP_EXEMPT_FAMILY_LABELS`` -- ``blocked`` or
    ``umbrella``, both pure label/dep-graph walks), the bucket submit is
    marked ``cap_exempt=True`` so it does not consume a
    ``MAX_PARALLEL_ISSUES_PER_REPO`` or ``MAX_PARALLEL_ISSUES_GLOBAL``
    slot. Such a bucket must always get its turn even when the caps are
    saturated by ordinary implementation work -- otherwise a ``blocked``
    parent polling its own children would be starved of the only
    per-repo slot (under the default ``parallel_limit=1``) and deadlock
    the very children it waits on. A bucket containing ``decomposing``
    (spawns the decomposer agent) or an unlabeled-pickup ``None`` stays
    cap-counted. ``backlog`` / ``paused`` issues are filtered out before
    this split -- a parked issue carries no workflow label, so leaving it in
    would fold it into the bucket and force ``cap_exempt=False``, starving
    fanout behind a hard-skip hold under ``parallel_limit=1``. The family mutex
    still applies, so a follow-up tick that finds another family issue
    still serializes against this bucket.

    Closed fan-out issues are likewise submitted ``cap_exempt=True``: a
    closed issue carrying a sweep label (``in_review`` / ``fixing`` /
    ``resolving_conflict`` / ``question`` / ...) only runs a terminal
    finalization (flip to ``done`` / ``rejected`` + branch cleanup) with no
    agent spawn, so it must not be starved behind active agent work -- a
    merged-PR issue could otherwise sit closed-but-labeled for many ticks
    while a sibling ``validating`` / ``documenting`` agent holds the only
    per-repo slot. A closed ``decomposing`` / ``umbrella`` owner is a fan-out
    submit for exactly this reason: its handler is the cleanup sweep, which
    settles a ledger and spawns nothing, and folding it into the bucket would
    make its turn depend on whatever else landed there.
    """
    per_repo_cap = _scheduler_per_repo_cap(spec)
    # `_partition_pollable_issues` owns the skip-label filtering, per-issue
    # label-read isolation, and the family/fanout split (including the closed
    # fan-out set). `backlog` / `paused` issues are dropped there so a parked,
    # workflow-label-less issue never folds into the bucket and flips it
    # cap-counted, which would reserve the only per-repo slot and starve
    # fanout under `parallel_limit=1`.
    partition = _partition_pollable_issues(gh, spec)

    # One `family=True` submit per repo drains every family-aware issue
    # sequentially (see `_drain_scheduler_family_bucket`). The bucket is
    # cap-exempt only when every family issue runs a no-agent handler
    # (`_family_bucket_cap_exempt`); the helper keeps the exempt probe and
    # the submit off the no-family path entirely.
    _submit_scheduler_family_bucket(gh, spec, scheduler, partition, per_repo_cap)
    _submit_scheduler_fanout_issues(gh, spec, scheduler, partition, per_repo_cap)
