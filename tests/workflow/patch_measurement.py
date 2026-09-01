# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What the size gate reads about a candidate, under the hermetic patch set.

The default world is the ordinary one -- a commit this host holds, a base the
remote named, and a diff well under any ceiling -- so a test about publishing
says nothing about size and a test about the gate seeds exactly the reading it
is about.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from orchestrator.git.measurement.models import (
    AdditionMeasurement,
    FrozenCommit,
    MeasurementFailure,
)
from tests.workflow.patch_models import _WorkflowRunContext
from tests.workflow.repo_values import (
    MEASURED_BASE_SHA,
    MEASURED_CANDIDATE_SHA,
)

# The revision the gate names the checkout's own head by. Every other
# revision it asks about is a commit some record names by id.
_HEAD = "HEAD"


class _CountedAdditions:
    """What the size gate's count reports for one frozen pair.

    Named against the pair it was handed rather than against the seed, so a
    measurement carries the commits the caller froze -- which is what the
    record written from it is then correlated by. A `MeasurementFailure` seed
    is a reading that did not happen and carries no count at all, because
    "unknown" and "small" are the two answers this domain exists to keep
    apart.
    """

    def __init__(self, context: _WorkflowRunContext) -> None:
        self._context = context

    def __call__(self, worktree, base_sha: str, candidate_sha: str):
        counted = self._context.added_lines
        if isinstance(counted, MeasurementFailure):
            return AdditionMeasurement(
                base_sha=base_sha, candidate_sha=candidate_sha,
                failure=counted,
            )
        return AdditionMeasurement(
            base_sha=base_sha, candidate_sha=candidate_sha, additions=counted,
        )


class _ProvedCommit:
    """What one revision the size gate names proves to.

    Two answers behind one seam, because the gate asks it two different
    questions: what the checkout's HEAD is, and whether the commit a record
    NAMES is an object this host still holds. A test that seeds neither gets
    the ordinary world -- a head, and a recorded object that is here.
    """

    def __init__(self, context: _WorkflowRunContext) -> None:
        self._context = context
        self._reads = 0

    def __call__(self, worktree, revision: str):
        if revision == _HEAD:
            return self._head()
        return self._context.recorded_commit or FrozenCommit(sha=revision)

    def _head(self):
        """What the checkout's own head proves to, this reading.

        A tuple seeds a head that MOVES between readings -- the gate takes one
        and the publication takes another -- which is the race the handoff
        refuses. Its last entry answers every reading past it, so a caller
        that asks once more than a test counted reads the head the test left
        the checkout on rather than running out of answers.
        """
        seeded = self._context.candidate_commit
        if seeded is None:
            return FrozenCommit(sha=MEASURED_CANDIDATE_SHA)
        if not isinstance(seeded, tuple):
            return seeded
        reading = min(self._reads, len(seeded) - 1)
        self._reads += 1
        return seeded[reading]


def _measurement_mocks(context: _WorkflowRunContext) -> dict[str, object]:
    """The four reads the size gate takes before anything is published."""
    return {
        "_prove_candidate_commit": MagicMock(side_effect=_ProvedCommit(context)),
        "_freeze_base_commit": MagicMock(
            return_value=context.frozen_base or FrozenCommit(
                sha=MEASURED_BASE_SHA,
            ),
        ),
        "_base_object_present": MagicMock(
            return_value=context.base_object_present,
        ),
        "_count_added_lines": MagicMock(side_effect=_CountedAdditions(context)),
    }
