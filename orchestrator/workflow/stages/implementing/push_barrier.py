# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What may have ended between this tick's readings and the push it is about.

The initial publication's own barrier, asked immediately before the transport
and nowhere else in that owner. Everything above the push spends a run, a
reading, or a proof, and each of those is time a poll on another worker can
find the world changing under -- so this is the last point at which either
answer is still true.

Two endings. A close a poll LATCHED, which is the process-wide reading the
issue object cannot give: the object is the snapshot the tick opened with, and
a close landing since is one only the latch knows. And the PULL REQUEST this
push would join -- the one the gate proved where it proved one, and otherwise
the one the record names. Reuse is a lookup by BRANCH, so a pull request that
ended in the window answers nothing to it, a second one is opened over the
work, and `pr_number` is overwritten with it: the pointer to whatever a human
just decided is gone.

One ending is not an ending for this push, and it is the reason this is an
owner rather than an open-state check. A merged `discussion` plan is an
AGREEMENT: the humans read a design and said build it, and the stage ahead of
here lets such a tick carry on for exactly that reason -- finalizing on it
would close the issue `done` with no developer having run. What it licenses is
an implementation with a pull request of its own, so the plan is not something
this push joins and never something it may be held back by.

Refusing writes nothing. The commit stays in the worktree, the record stays as
it stands, and the next poll asks the same question of the same durable state.
"""
from __future__ import annotations

import logging

from github.Issue import Issue

from orchestrator import config
from orchestrator.github import client as _client, pinned_state as _pinned_state
from orchestrator.workflow.engine import observations as _observations
from orchestrator.workflow.late_split import payloads as _payloads
from orchestrator.workflow.stages.discussion.state import (
    _PLAN_PATH as _DISCUSSION_PLAN_PATH,
    _PLAN_SHA as _DISCUSSION_PLAN_SHA,
)
from orchestrator.workflow.stages.implementing import (
    late_overflow as _overflow,
    models as _models,
    state as _state,
)

log = logging.getLogger("orchestrator.workflow")


def _ended_before_the_push(
    gh: _client.GitHubClient,
    spec: config.RepoSpec,
    issue: Issue,
    state: _pinned_state.PinnedState,
    approved: _models._ApprovedWork,
) -> bool:
    """Whether the work this push is about ended while the tick was working.

    Two endings, asked immediately before the transport because that is the
    only point at which either answer is still true: everything above spends a
    run, a reading, or a proof that a poll on another worker can find the world
    changing under.

    The PULL REQUEST is the one this push would JOIN, which is whichever of two
    the tick has: the one the gate proved, where it admitted the candidate
    because that pull request is already standing on it, and otherwise the one
    the record names -- the `discussion` stage's plan pull request sitting on
    the very ref the dev commits went to, or this stage's own from a round that
    crashed before its relabel. Both are reused rather than opened, and the
    reuse is a lookup by BRANCH: one that ended between the tick's first
    reading and here answers nothing to that lookup, so a second pull request
    is opened over the work and `pr_number` is overwritten with it -- which is
    how the pointer to what a human just closed is lost. An issue that records
    none is the first publication, which has nothing to have ended and spends
    no request. A plan the humans have SETTLED is the one ending that is not
    an ending for this push, and `_publication_is_over` beside this owns why.

    Read fail-CLOSED, like every reading standing immediately before an effect
    nothing can undo: what refusing costs is the poll that asks again, and what
    falling through costs is a branch and a pull request nobody asked for.

    The CLOSE is asked last and of the process-wide latch rather than of the
    issue object, which is the snapshot the tick opened with. Last because the
    reading above it is a request: a close landing while that request is in
    flight would be answered one push too late by a latch read before it, and
    this one costs nothing, so the cheap answer gets the final word.
    """
    recorded = _payloads.as_identity(state.get(_state._PR_NUMBER))
    number = approved.delivered_pr or recorded
    if number and _publication_is_over(
        gh, issue, state, number, proved=bool(approved.delivered_pr),
    ):
        return True
    if not _observations.close_observed(spec.slug, issue.number):
        return False
    log.warning(
        "repo=%s issue=#%d was observed closed before its branch was pushed; "
        "refusing the push rather than putting work on an issue nobody wants",
        spec.slug, issue.number,
    )
    return True


def _publication_is_over(
    gh: _client.GitHubClient,
    issue: Issue,
    state: _pinned_state.PinnedState,
    number: int,
    proved: bool,
) -> bool:
    """Whether the pull request this push would join has ended.

    One reading rather than a question per fact, because the two answers are
    read off the same object: whether it is still open, and -- where it is not
    -- whether it is the `discussion` stage's PLAN rather than a publication
    of this stage's.

    That carve-out is the whole reason this is not a bare open-state check. A
    merged plan is an agreement, not a delivery: the humans read a design and
    said build it, and the stage ahead of this one lets such a tick carry on
    for exactly that reason -- finalizing on it would close the issue `done`
    with no developer ever having run. The implementation it licenses gets a
    pull request of its OWN, so an ended plan is not something this push joins
    and never something it may be held back by. A plan somebody closed
    unmerged reads the same way here and is answered the same way it is above:
    the tick carries on, and what to do about a design nobody accepted is the
    stage question, not the transport's.

    A pull request this host could not READ is refused whatever the record
    says, unless the plan record alone settles it: nothing was established, so
    there is no reading to tell a plan from a delivery, and what a refusal
    costs is the poll that asks again.

    `proved` is the delivery road, where the number came from a receipt this
    stage's own push wrote rather than from the record. Nothing there can be a
    plan -- the proof is that the branch stands on the candidate -- so the
    carve-out is not offered to it at all.
    """
    reading = _overflow._PublicationReading.taken(gh, number)
    if reading.refusal is None and reading.state == _overflow._OPEN:
        return False
    if not proved and _is_the_discussion_plan(state, reading):
        log.info(
            "issue=#%d records plan PR #%d, which the humans have settled; "
            "publishing the implementation onto a pull request of its own",
            issue.number, number,
        )
        return False
    log.warning(
        "repo=%s issue=#%d cannot read pull request #%d as open before the "
        "push that would join it; refusing rather than publishing onto a "
        "publication that has ended",
        gh.repo_slug, issue.number, number,
    )
    return True


def _is_the_discussion_plan(
    state: _pinned_state.PinnedState,
    reading: _overflow._PublicationReading,
) -> bool:
    """Whether the pull request just read is the design, not an implementation.

    The same two records the stage's own terminals tell them apart by, asked
    of the reading already in hand rather than of a second fetch. A live
    `discussion_plan_path` says so outright; past the handoff that retires it,
    `discussion_plan_sha` is what the plan publication put on that pull
    request, and a head still standing there is one nothing of this stage's
    has pushed over.

    A reading that established no head answers on the path record alone, which
    is the honest answer: with nothing read there is nothing to compare, and
    the caller refuses rather than guessing.
    """
    if state.get(_DISCUSSION_PLAN_PATH):
        return True
    plan_sha = state.get(_DISCUSSION_PLAN_SHA)
    return bool(plan_sha) and reading.head == plan_sha
