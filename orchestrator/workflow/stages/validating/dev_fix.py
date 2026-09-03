# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What one finished dev fix leaves behind, whichever route started it.

The reviewer feedback route, the awaiting-human resume, and the drift resume
all end here, because the questions after a dev run are the same three
regardless of what prompted it: did the run produce something publishable, is
the tree clean enough to push, and does the reviewer owe the branch another
look. Only the disposition order differs, and `_dispose_dev_fix_result` fixes
it -- an interrupted run first, so a shutdown-killed agent parks nothing and
the next tick simply retries it, then the timeout park, then the question.

`_stranded_fix_unpushed` is the non-obvious gate. A fix committed by an
earlier run that parked before publishing looks identical to "the agent did
nothing" on every later resume -- `after_sha == before_sha` -- so without it
the commit can never reach the PR and the issue ping-pongs between
awaiting-human parks forever. It is conservative by construction: a dirty
tree, a failed fetch, or a remote that moved all report False, because
pushing over a head nobody reconciled is worse than one more park.

`rounds.py` beside this owns the counter every landed fix pays into. It sits there
rather than beside any one caller because all three routes owe it for the
same reason -- the head the reviewer approved or rejected no longer exists,
so the round it spent does not count against the cap.
"""
from __future__ import annotations

from dataclasses import replace as _replace
from pathlib import Path

from github.Issue import Issue

from orchestrator import config
from orchestrator.git import branch_transport as _branch_transport
from orchestrator.git.publication import probes as _publication_probes
from orchestrator.git.verification import probes as _verification_probes
from orchestrator.git.worktrees import paths as _worktree_paths
from orchestrator.github.client import GitHubClient
from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.engine import guards as _guards
from orchestrator.workflow.stages.implementing import (
    late_push as _late_push,
    late_records as _late_records,
    parks as _dev_parks,
)
from orchestrator.workflow.stages.validating import models as _models, state as _state


def _stranded_fix_unpushed(
    spec: config.RepoSpec, wt: Path, state: PinnedState, issue: Issue
) -> str:
    """The remote head a stranded fix is proved ahead of, or "" where none is.

    A clean worktree HEAD strictly ahead of the remote PR branch is a fix an
    earlier parked run committed and never published.

    The shape arises when the publish was blocked at commit time (e.g. a
    dirty-worktree park whose stray files a human later had the dev clean
    up): every later resume sees `after_sha == before_sha`, so without
    this check the stranded commit can never reach the PR and the issue
    ping-pongs between `awaiting_human` parks forever.

    Conservative by construction: a dirty tree, a failed fetch, or a
    remote that moved (`behind > 0` -- pushing would race a head we have
    not reconciled) all report "", so the caller takes whichever
    no-publish path it owns -- the question park here, the bounce back to
    `validating` in the fixing handler's no-feedback exit -- instead of
    pushing blind.

    What comes back is the head the comparison was taken AGAINST rather than
    a bare yes. The caller's next step is a push, and the proof this took is
    a claim about one commit: the branch is ahead of THAT head and behind
    nothing. Handed on, the gate is pinned to it and a pull request somebody
    moved between this probe and that push refuses instead of being adopted
    as the lease and force-overwritten. A tip nothing could read is no head
    either, and refuses here rather than publishing against one.
    """
    if _verification_probes._worktree_dirty_files(wt):
        return ""
    branch = _worktree_paths._resolve_branch_name(state, spec, issue.number)
    fetch = _branch_transport._authed_fetch(
        spec,
        f"+refs/heads/{branch}:refs/remotes/{spec.remote_name}/{branch}",
        cwd=wt,
    )
    if fetch.returncode != 0:
        return ""
    divergence = _publication_probes._branch_divergence(spec, wt, branch)
    if not divergence.readable or divergence.ahead <= 0 or divergence.behind:
        return ""
    return divergence.tip


def _park_dev_fix_timeout(
    gh: GitHubClient, issue: Issue, state: PinnedState, before_sha: str,
) -> None:
    _guards._park_awaiting_human(
        gh, issue, state,
        f"{config.HITL_MENTIONS} agent timed out after {config.AGENT_TIMEOUT}s, "
        "manual intervention needed.",
        reason=_state._REASON_AGENT_TIMEOUT,
    )
    state.set(_state._PARK_REASON, _state._REASON_AGENT_TIMEOUT)
    state.set(_state._PRE_DEV_FIX_SHA, before_sha or "")


def _publishable_dev_fix(
    spec: config.RepoSpec, issue: Issue, state: PinnedState, run: _models._DevFixRun,
) -> _models._DevFixRun | None:
    """The run a fix publishes, carrying the head it was decided on, or None.

    The head is read ONCE and travels on the answer, because the decision and
    the push have to be about the same commit. Between this reading and the
    proof the size gate takes for itself the worktree is writable -- another
    tick, an operator, a stray descendant -- and a commit landing there is a
    different candidate: measured, pushed, and receipted while the route that
    reached this answer goes on as if the head it read had gone out. Handed on
    instead of dropped, the two are one decision and a checkout standing
    anywhere else refuses.

    A STRANDED fix carries a head of its own instead. This run committed
    nothing, so the head it began at is not what the push would replace: what
    it replaces is the remote tip the stranded proof was taken against, and
    that is the head the gate is pinned to. Without it the gate reads the pull
    request afterwards and adopts whatever it finds, so a head somebody landed
    in between is force-overwritten by work proved against the head it used to
    be on.

    None is every no-publish reading: a checkout that could not name its head
    at all, and one whose head is exactly what the run started on with nothing
    of that run's stranded on the branch unpushed.
    """
    after_sha = run.after_sha
    if after_sha is None:
        after_sha = _verification_probes._head_sha(run.worktree)
    if not after_sha:
        return None
    if after_sha != run.before_sha:
        return _replace(run, after_sha=after_sha)
    stranded = _stranded_fix_unpushed(spec, run.worktree, state, issue)
    if not stranded:
        return None
    return _replace(run, after_sha=after_sha, stranded_head=stranded)


def _publish_dev_fix(
    gh: GitHubClient,
    spec: config.RepoSpec,
    issue: Issue,
    state: PinnedState,
    run: _models._DevFixRun,
) -> bool:
    """Push what a finished dev fix left, once it is small enough to push.

    The one seam every fix route publishes through, which is what makes the
    size gate between the tree read and the push a contract rather than a
    check: a candidate that would take the pull request past `MAX_ADDED_LINES`
    is held here whether the run came from reviewer feedback, a human's reply,
    or an edited issue body. Held means the gate has already done everything
    this tick does with the candidate -- parked it, or handed the issue to the
    adjudication under `workflow:decomposing` -- so the caller reads it as
    every other no-publish exit: nothing is pushed and no label is advanced.

    The push is named and pinned by what the gate handed back rather than by
    the checkout it is run in: the measured commit goes out even if `HEAD`
    moved since, and the head the entry froze is the lease, so a pull request
    somebody pushed to in that same window rejects this push instead of being
    overwritten by work measured against the head it used to be on.

    The state the gate freezes is the run's own where it carries one. A route
    that relabels remotely and then publishes in the same tick reads its own
    cached labels back, so the record would name the state the issue has left
    -- and a settled adjudication continues at whatever the record names.

    The approval the gate leaves behind is spent HERE, on the push that pays
    it. It says one commit is still owed a publication, and a record left
    standing past the push that made it would freeze this branch out of the
    pre-tick base refresh with nothing coming back to drop it.
    """
    state.set("silent_park_count", 0)
    dirty = _verification_probes._worktree_dirty_files(run.worktree)
    if dirty:
        _dev_parks._on_dirty_worktree(gh, issue, state, run.agent_result, dirty)
        return False
    branch = _worktree_paths._resolve_branch_name(state, spec, issue.number)
    published = _late_push._publishes(
        _late_records._gate(gh, spec, issue, state, run.worktree), branch,
        _late_records._Entered(
            stage=run.stage,
            # The head the pull request was standing on before this run made
            # its commit. Left for the gate to read afterwards, a pull request
            # somebody pushed to while the agent was out becomes the lease and
            # the force-push overwrites them with work measured against the
            # head it used to be on.
            head=run.entered_head,
            spends=run.spends or _late_records._SPENDS_NOTHING,
            # The head this route read and decided to publish on. The gate
            # proves the checkout again, and a commit landing between the two
            # reads would otherwise be measured, pushed, and receipted here
            # while the route behind this call reports the fix it read as
            # published.
            candidate=run.after_sha or "",
        ),
    )
    if published.held:
        return False
    if published.landed:
        return True
    _guards._park_awaiting_human(
        gh, issue, state,
        f"{config.HITL_MENTIONS} git push failed; see orchestrator logs.",
        reason=_state._REASON_PUSH_FAILED,
    )
    state.set(_state._PARK_REASON, _state._REASON_PUSH_FAILED)
    return False


def _dispose_dev_fix_result(
    gh: GitHubClient,
    spec: config.RepoSpec,
    issue: Issue,
    state: PinnedState,
    run: _models._DevFixRun,
) -> bool:
    if run.agent_result.interrupted:
        return False
    if run.agent_result.timed_out:
        _park_dev_fix_timeout(gh, issue, state, run.before_sha)
        return False
    publishable = _publishable_dev_fix(spec, issue, state, run)
    if publishable is None:
        _dev_parks._on_question(gh, issue, state, run.agent_result)
        return False
    return _publish_dev_fix(gh, spec, issue, state, publishable)


def _handle_dev_fix_result(
    gh: GitHubClient,
    spec: config.RepoSpec,
    issue: Issue,
    *context_args,
    **fields,
) -> bool:
    """Post-agent handling for a dev fix during validating.

    Returns True if a fix was committed, pushed, and the caller should
    advance the label (validating routes the issue back to `validating`
    on True so the reviewer re-runs against the new head; any stale
    approval state must be reset by the caller before relabeling). A
    no-new-commit run also returns True when it published a stranded fix
    a prior parked run had committed (see `_stranded_fix_unpushed`).
    Returns False if the run produced no fix (timeout, no-new-commit,
    dirty tree, or push failure); caller should write state and return.
    A shutdown-killed (interrupted) run also returns False WITHOUT parking,
    posting, or publishing, so the next tick re-runs the dev cleanly.

    `after_sha`, when provided, is the post-agent HEAD the caller already
    read (e.g. the fixing handler's ACK fast path); passing it avoids a
    redundant `_head_sha` call. When None it is read here.
    """
    state, run = _models._dev_fix_run(context_args, fields)
    return _dispose_dev_fix_result(gh, spec, issue, state, run)
