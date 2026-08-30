# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What the world does to a publication while an agent is out.

Every seam the size gate stands in front of reads its pull request, its head,
or its label BEFORE the agent runs and again once the gate has it -- and the
window between the two is minutes long. These are the four things that can
land in it, spelled as the run itself so a whole tick reaches the race the way
production does rather than by a test rewriting state around a run that never
saw it.

They belong to no one stage: a fix round, a docs pass, and a conflict
resolution each resume an agent over the same window and each need the same
four doubles.
"""
from __future__ import annotations

from tests.support.fakes import FakeLabel, LazyPullRequest


class _ClosesThePullRequest:
    """A run that finishes into a pull request somebody closed meanwhile.

    The only way the closed-PR refusal is reachable through a whole tick: the
    preflight drains a merged or closed pull request before anything else
    runs, so the state this refuses on can only arrive while the agent is out.
    """

    def __init__(self, pr, finished) -> None:
        self._pr = pr
        self._finished = finished

    def __call__(self, *called, **options):
        self._pr.state = "closed"
        return self._finished


class _MovesThePullRequest:
    """A run that finishes into a pull request somebody pushed to.

    The race the pre-effect head closes, and the only way to reach it through
    a whole tick: the branch is in sync with its publication when a round
    opens, so the head that round names is the head the caller just read --
    and the move can only land while the agent is out.
    """

    def __init__(self, pr, moved: str, finished) -> None:
        self._pr = pr
        self._moved = moved
        self._finished = finished

    def __call__(self, *called, **options):
        self._pr.head.sha = self._moved
        return self._finished


class _RelabelsTheIssue:
    """A run that finishes into an issue a human moved off its stage.

    The label the entry freezes is the one the object carries AFTER the run,
    and this is the window it can change in: the route reads its own labels
    before the spawn and the agent is out for minutes. Moved to a state no
    publication is entered from, there is no group for the entry to freeze --
    and the states with an edge to the adjudication and no pull request behind
    them are exactly the ones a general graph check would wave through.
    """

    def __init__(self, issue, moved: str, finished) -> None:
        self._issue = issue
        self._moved = moved
        self._finished = finished

    def __call__(self, *called, **options):
        self._issue.labels = [FakeLabel(self._moved)]
        return self._finished


class _BreaksThePullRequest:
    """A run that finishes into a pull request the remote stops answering.

    The same shape as `_ClosesThePullRequest` and for the same reason: the
    preflight reads the pull request before anything else runs, so a state
    the gate is meant to refuse on can only arrive while the agent is out.
    """

    def __init__(self, github, number: int, failing: str, finished) -> None:
        self._github = github
        self._number = number
        self._failing = failing
        self._finished = finished

    def __call__(self, *called, **options):
        self._github.add_pr(LazyPullRequest(
            self._github.get_pr(self._number), failing=self._failing,
        ))
        return self._finished
