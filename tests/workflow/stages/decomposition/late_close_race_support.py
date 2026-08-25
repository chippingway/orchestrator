# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The human who closes an issue while its split transaction is running.

A close a run has to catch for itself lands INSIDE one of the run's own steps,
never before it started, so every fixture here hangs the close off a seam the
transaction goes through anyway: the read that answers a child create, the
comment that says what the parent became, the call that closes the held plan
pull request, the write that hands the parent to `umbrella`. What the run does
with the reading it takes next is the test module's subject; none of this
decides any of it.
"""
from __future__ import annotations

from unittest.mock import patch

from tests.workflow.stages.decomposition.late_transaction_support import (
    FORWARD_LINK_MARKER,
)


def closes_when_children_exist(case, children: int):
    """Close the owner once it has this many children on GitHub."""
    return _ClosesAt(
        case,
        "get_issue",
        lambda asked: len(case.github.created_child_issues) >= children,
    ).answering()


def closes_on_announcement(case):
    """Close the owner from inside the post that says what it became."""
    return _ClosesAt(
        case,
        "comment",
        lambda asked: FORWARD_LINK_MARKER in (asked[1] or ""),
    ).answering()


def closes_on_supersession(case):
    """Close the owner from inside the call that closes its plan PR."""
    return _ClosesAt(case, "supersede_pr", _always).answering()


def closes_on_retirement(case):
    """Close the owner from inside the write that hands it to `umbrella`.

    The last gap the transaction has, and the one past every guard the
    publication takes: after this write the children are started, which is
    the one effect of a split that puts an agent on somebody's repository.
    """
    return _ClosesAt(case, "set_workflow_label", _always).answering()


def _always(asked) -> bool:
    """A seam the run reaches exactly once, so reaching it is the whole test."""
    return True


class _ClosesAt:
    """Close the owner from inside one call the transaction makes.

    A human with the issue open in a browser, in other words: the close lands
    between two of the run's own readings rather than before it started, which
    is the only way any of these windows can be entered. The seam still does
    what it was asked, because what each case is about is the state the run
    leaves once that step HAS happened.
    """

    def __init__(self, case, seam: str, when) -> None:
        self._case = case
        self._seam = seam
        self._when = when
        self._answering = getattr(case.github, seam)

    def __call__(self, *asked, **answering):
        """Close the owner if this call is the one, then answer it."""
        if self._when(asked):
            self._case.issue.closed = True
        return self._answering(*asked, **answering)

    def answering(self):
        """Put this in front of every call the run makes to that seam."""
        return patch.object(
            self._case.github, self._seam, side_effect=self,
        )
