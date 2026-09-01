# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a finished discussion round left behind, in the order that matters.

The live pause comes first and suppresses every disposition below it, because
that is the whole promise a hard control label makes: the timestamp, the usage
fold, the session id the run already retained, and every park here have to wait
for the operator. What keeps that safe for a run that COMMITTED -- the one
outcome the next tick could otherwise mistake for work the branch arrived with
-- is the anchor `run` wrote before the spawn: it outlives the withheld round,
so the next active tick classifies the commit instead of adopting it.

Then whether the commit question is answerable at all, then the commit, then
the timeout: a run that wrote outranks how it ended, since the timeout's
message would otherwise be the only record of a round that also edited the
tree. The first of those is there because the question is a comparison and one
of its ends is a `HEAD` read that can fail: unresolvable, it comes back empty,
compares unequal to the SHA the round opened on, and would publish the commit
already on the branch as this round's own.

What a commit MEANS is not decided here, though -- it is
handed to `publication`, which reads the branch and either publishes the agreed
plan or refuses everything else. That is the one outcome that can end in
something other than a park, and it is still ordered above the timeout for the
same reason: what the round wrote is the fact of record.

Everything after that is the rest of the write contract. A dirty tree is
inspected before interruption and before the response itself, so a run that
wrote despite the prompt parks on what it wrote rather than on what it said: a
discussion that starts editing outside the one path it may commit has skipped
the human confirmation the whole stage exists to wait for, and the operator
needs the tree to see how far it got. Both violations are read against what the
round started from -- a HEAD that moved under it, not a branch merely ahead of
base -- because an issue an operator relabels here from a PR stage arrives with
commits its dev already made, and parking the discussion agent for those would
accuse it of work it never did. Only a clean tree gets to be a design analysis,
and an empty message on a clean tree is a backend failure wearing an analysis's
clothes, which is why that park is the one carrying stderr diagnostics.

Assessment and routing are the whole of this owner because the park has to be
selected before any of it is published: what each selection then says to the
human belongs to `parks` beside it, so a message can be reworded without
touching the order the decisions are made in.
"""
from __future__ import annotations


from orchestrator.git.verification import probes as _verification_probes
from orchestrator.git.worktrees import paths as _worktree_paths
from orchestrator.workflow.engine import guards as _guards
from orchestrator.workflow.engine import usage as _usage
from orchestrator.workflow.stages.discussion import models as _models
from orchestrator.workflow.stages.discussion import parks as _parks
from orchestrator.workflow.stages.discussion import publication as _publication
from orchestrator.workflow.stages.discussion import state as _state


def _round_committed(
    run: _models._DiscussionRun, round_result: _models._DiscussionRound,
) -> bool | None:
    """True when HEAD moved under this round, or None when nothing can say.

    Measured against the SHA the round opened on rather than against the base,
    so a branch an operator relabeled here from a PR stage keeps the commits
    its dev already made without the discussion agent being blamed for them.

    BOTH ends have to have been read, because an unresolvable `HEAD` comes back
    as the empty string and empty compares unequal to whatever the other end
    is. Answered as a move, that reading publishes: the branch of an issue that
    arrived carrying a plan-shaped commit would go onto a pull request in this
    stage's name, attributed to a round that wrote nothing at all -- and a
    single transient failure between two good reads is enough to produce it. So
    a read that did not land answers for itself, and the caller holds rather
    than classifying a round it cannot see the effect of.
    """
    worktree = _worktree_paths._worktree_path(run.spec, run.issue.number)
    head_after = _verification_probes._head_sha(worktree)
    if not head_after or not round_result.head_before:
        return None
    return head_after != round_result.head_before


def _assess_discussion_outcome(
    run: _models._DiscussionRun, round_result: _models._DiscussionRound,
) -> _models._DiscussionOutcome:
    """Inspect a completed agent round in the stage's required order."""
    discussion_result = round_result.agent_result
    # A live pause suppresses every disposition below, leaving each in-memory
    # mutation unpersisted so the next active tick replays the same durable
    # state. A commit made by the withheld round is not lost with them: the
    # anchor written before the spawn outlives this return, and the next tick
    # reads it back rather than adopting the commit as its own baseline.
    if _guards._paused_during_agent_run(run.gh, run.issue):
        return _models._DiscussionOutcome(None)

    run.state.set(_state._LAST_DISCUSSION_AT, _usage._now_iso())
    if not discussion_result.interrupted:
        _usage._accumulate_issue_usage(run.state, discussion_result.usage)

    committed = _round_committed(run, round_result)
    if committed is None:
        return _models._DiscussionOutcome(_state._DISCUSSION_UNREADABLE)
    if committed:
        return _models._DiscussionOutcome(_state._DISCUSSION_COMMITS)

    if discussion_result.timed_out:
        return _models._DiscussionOutcome(_state._DISCUSSION_TIMEOUT)

    return _assess_discussion_worktree(run, round_result)


def _assess_discussion_worktree(
    run: _models._DiscussionRun, round_result: _models._DiscussionRound,
) -> _models._DiscussionOutcome:
    """Classify a clean-HEAD, non-timeout round from its tree and response.

    The dirty check takes precedence over interruption so a killed run that
    changed the tree still leaves an inspection target for the operator, and it
    needs no baseline of its own: the handler's preflight already established
    that the checkout this round opened on was clean.
    """
    discussion_result = round_result.agent_result
    worktree = _worktree_paths._worktree_path(run.spec, run.issue.number)
    dirty_files = tuple(
        _verification_probes._worktree_dirty_files(worktree),
    )
    if dirty_files:
        return _models._DiscussionOutcome(
            _state._DISCUSSION_DIRTY, dirty_files=dirty_files,
        )

    if _guards._ignore_if_interrupted(run.issue, discussion_result):
        return _models._DiscussionOutcome(None)

    response = (discussion_result.last_message or "").strip()
    if response:
        return _models._DiscussionOutcome(
            _state._DISCUSSION_RESPONSE, response=response,
        )
    return _models._DiscussionOutcome(_state._DISCUSSION_SILENT)


def _dispose_round_commit(run: _models._DiscussionRun) -> None:
    """Publish what the round committed, or refuse it in the round's name.

    The reading of the branch is taken by `publication` and handed back only
    when nothing was published, so the refusal quotes the same paths the
    decision was made on rather than probing the tree a second time and
    describing a checkout that may have moved between the two.
    """
    unpublishable = _publication._publish_plan_if_committed(run)
    if unpublishable is not None:
        _parks._park_unpublishable_plan(run, unpublishable)


def _route_discussion_outcome(
    run: _models._DiscussionRun,
    round_result: _models._DiscussionRound,
    outcome: _models._DiscussionOutcome,
) -> None:
    """Publish the outcome selected by `_assess_discussion_outcome`."""
    if outcome.park_reason == _state._DISCUSSION_UNREADABLE:
        _parks._park_unreadable_round(run)
        return
    if outcome.park_reason == _state._DISCUSSION_COMMITS:
        _dispose_round_commit(run)
        return
    if outcome.park_reason == _state._DISCUSSION_TIMEOUT:
        _parks._park_timed_out_discussion(run)
        return
    if outcome.park_reason == _state._DISCUSSION_DIRTY:
        _parks._park_dirty_discussion(run, outcome.dirty_files)
        return
    if outcome.park_reason == _state._DISCUSSION_SILENT:
        _parks._park_silent_discussion(run, round_result.agent_result)
        return
    _parks._park_discussion_response(run, outcome.response)
