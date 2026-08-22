# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The label an in-flight generation pins, and the two ways it is taken away.

An oversized committed candidate is adjudicated under `workflow:decomposing`,
and while that is open the label is not a state anything else may set. Both
ways it can be moved are the same move dressed differently, and both amount to
publishing the candidate without adjudicating it -- which is the one outcome
the whole size gate exists to prevent.

The kill switch is the first. `DECOMPOSE=off` routes a `decomposing` issue
into the legacy implementing flow, which is exactly right for an issue that
was only ever waiting to be decomposed and exactly wrong for one whose
implementation is already committed and measured past the ceiling: the switch
would turn a live question into a `single` verdict nobody recorded. So the
route is refused while a generation is live, for the same reason the
half-finished recovery beside it keeps running -- a kill switch that strands
or force-publishes existing work is not what off should mean. Turning it off
still stops new candidates from ever entering the gate; it does not decide the
ones already in it.

A human relabelling by hand is the second, and it is caught a step later than
the switch is, because there is nothing to refuse at the write: the
orchestrator never sees a human move a label, and by the time anything reads
one the old value is gone. So the refusal happens where a label becomes a
handler call. The dispatcher asks this owner before it routes anything, the
issue is put back to `workflow:decomposing` and told why, and it is left for
the next tick rather than handed to the stage the new label named. Idempotent
by construction -- a label already correct is left alone and says nothing -- so
the notice appears once per relabel rather than once per tick, and the refusal
stands even when the label write itself fails.

Neither of these clears, cancels, or decides anything. A generation an
operator really wants gone is cancelled through the late domain's own
cancellation, which records what was owed; coercing it through a label or a
switch would leave the plan-PR hold, the frozen commit, and the external
ledgers behind with nothing on the issue pointing at them.

What counts as in-flight is deliberately wider than "oversized". A read this
generation still owes is a question as open as the size one, and it is the
one an undersized revision leaves behind: the candidate no longer trips the
ceiling, so every gate keyed to size waves it through while nobody has
established that the issue is still there. Both doors are shut on it until
that read is reconciled or the cycle is cancelled.
"""
from __future__ import annotations

import logging

from github.Issue import Issue

from orchestrator import config
from orchestrator.github.client import GitHubClient
from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.engine import comments as _comments
from orchestrator.workflow.late_split import state as _late_state
from orchestrator.workflow.late_split.models import LateGeneration
from orchestrator.workflow.state import WorkflowLabel

log = logging.getLogger("orchestrator.workflow")

_RESTORED_NOTICE = (
    "{mentions} :lock: this issue's committed implementation is still being "
    "adjudicated for its size ({additions} added lines against a ceiling of "
    "{threshold}), so it has been put back on `{label}`. Relabelling does not "
    "decide that question -- close the issue, or answer the adjudication, to "
    "settle it."
)


def _adjudication_is_live(generation: LateGeneration) -> bool:
    """Whether a generation is one nothing outside this mode may decide.

    An issue that never entered the gate and a cancelled cycle are free to be
    routed and relabelled like any other -- there is no open question about
    either. Everything else turns on two answers, and a candidate measured at
    or below its ceiling is only the first of them.

    The second is an owner read this generation still owes. A revision that
    came back UNDER the ceiling is exactly that case: it is no longer
    oversized, so the size question is closed, and yet nobody has established
    whether the issue it belongs to is still open. Routing it out of this mode
    on the strength of the first answer alone hands another stage a candidate
    the guard has not cleared -- which is the same publication the gate exists
    to stop, reached by a different door. So the read outstanding keeps the
    generation live until it is reconciled or the cycle is cancelled.
    """
    if not generation.is_present or generation.cancelled:
        return False
    return generation.is_oversized or generation.owner_check_pending


def _refuses_disabled_route(state: PinnedState) -> bool:
    """Whether `DECOMPOSE=off` may not route this issue to implementation.

    Asked of the pinned record rather than of the switch, because the switch
    is about whether NEW candidates enter the gate and this is about one
    already in it. A live generation means the issue is carrying a committed
    candidate measured past the ceiling with no verdict on it -- or one whose
    owner nobody has been able to read since the run that produced it -- and
    the legacy route publishes exactly that.
    """
    return _adjudication_is_live(_late_state.read_late_generation(state))


def _restore_decomposing_label(
    gh: GitHubClient, issue: Issue, state: PinnedState,
) -> bool:
    """Put a hand-relabelled in-flight generation back, and say so once.

    Returns whether anything was done. The notice tracks its own comment id on
    the pinned state in memory, as every posted comment does, so a caller told
    True and staging nothing else of its own still owes a write.

    The label is read off the issue rather than assumed: a generation that is
    live and already on `workflow:decomposing` is the normal case, on every
    tick, and it must cost neither a comment nor a label write.

    The write goes out unguarded and BEFORE the notice, and both halves of
    that are about the same failure. The transition graph describes the moves
    this orchestrator makes, and a repair of a move a human made is not one of
    them -- under `WORKFLOW_TRANSITION_GUARD=enforce` a `validating ->
    decomposing` restoration would raise, leaving the generation stranded
    under the wrong label for as long as the guard stayed on. And a notice
    posted ahead of a write that then failed would be posted again on every
    tick that retried it, so the comment follows the label it is announcing:
    one notice per restoration that actually happened.
    """
    generation = _late_state.read_late_generation(state)
    if not _adjudication_is_live(generation):
        return False
    if gh.workflow_label(issue) == WorkflowLabel.DECOMPOSING:
        return False
    log.warning(
        "issue=#%d was relabelled while its oversized candidate %s was under "
        "adjudication; restoring %s",
        issue.number, generation.candidate_sha, WorkflowLabel.DECOMPOSING,
    )
    gh.set_workflow_label(issue, WorkflowLabel.DECOMPOSING, guarded=False)
    _comments._post_issue_comment(
        gh, issue, state,
        _RESTORED_NOTICE.format(
            mentions=config.HITL_MENTIONS,
            additions=generation.additions,
            threshold=generation.threshold,
            label=WorkflowLabel.DECOMPOSING,
        ),
    )
    return True


def _refuses_dispatch(gh: GitHubClient, issue: Issue) -> bool:
    """Whether this issue may not reach the handler its label names.

    The dispatcher's own question, and the one place a hand relabel is
    actually caught: by the time anything reads the label it is already gone,
    so there is nothing to refuse at the write and the repair has to happen
    where the label becomes a handler call.

    The refusal is the safety property and the relabel is only the repair, so
    a label write that fails still stops the dispatch. Otherwise a transition
    guard set to `enforce`, or a GitHub error, would hand the issue to the
    very handler this exists to keep it away from.

    Reading the pinned state is this check's whole cost -- one comment walk per
    labelled, non-decomposing issue per tick, on top of the one that issue's
    own handler makes. It is paid because there is no cheaper signal: a live
    generation is a fact about the pinned comment, and the label that would
    have told us is exactly the thing a human moved.

    A read that could not be taken refuses, which is the one place this guard
    does NOT follow the additive-safety-net convention the pause probe reads
    by. The costs are not symmetric. Failing open costs an unadjudicated
    candidate published: the handler behind this one reads the same pinned
    comment for itself, and a first read that failed transiently is followed
    by a second that may well succeed -- so the very state that would have
    stopped the dispatch is what the stage then acts on. Failing closed costs
    one tick of one issue, retried on the next poll, during an outage in which
    nothing else was going to make progress either.
    """
    try:
        state = gh.read_pinned_state(issue)
    except Exception:
        log.exception(
            "issue=#%s pinned state could not be read; refusing to dispatch "
            "it rather than risk publishing an unadjudicated candidate",
            getattr(issue, "number", "?"),
        )
        return True
    if not _adjudication_is_live(_late_state.read_late_generation(state)):
        return False
    try:
        restored = _restore_decomposing_label(gh, issue, state)
    except Exception:
        log.exception(
            "issue=#%d could not be put back on %s; refusing to dispatch it "
            "while its candidate is under adjudication",
            issue.number, WorkflowLabel.DECOMPOSING,
        )
        return True
    if restored:
        gh.write_pinned_state(issue, state)
    return restored
