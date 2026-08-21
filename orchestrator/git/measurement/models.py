# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a size measurement is, and the typed reasons there is not one.

The failure vocabulary lives beside the records because every member of it
says the same thing about them: this measurement did not happen. That
distinction is the whole point of the domain. A candidate whose size is
unknown is not a small one -- "small" is what publishes an implementation
without adjudicating it -- so a failed reading carries no count at all rather
than the zero a failed `git` invocation would otherwise be read as.

The members are separate because the operator's next move differs by which
step could not be completed, and because a retry has to know how far the
previous attempt got: a base the remote would not name is a token or transport
problem, a base this clone does not hold is a fetch that brought nothing back,
a candidate that will not resolve is a checkout to look at, a candidate whose
object is missing is work made on a host this one is not, and a diff nothing
here can pin is a checkout carrying something that decides what counts as text
-- which an operator has to clear before any reading of it is worth taking.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Optional


class MeasurementFailure(StrEnum):
    """The step a measurement stopped at, named rather than swallowed.

    They are `StrEnum` members so a member IS its wire string: what a park
    reason, a log line, and a recorded typed failure carry is the same value a
    comparison against a plain string reads.
    """

    BASE_UNREADABLE = "base_unreadable"
    BASE_ABSENT = "base_absent"
    CANDIDATE_UNREADABLE = "candidate_unreadable"
    CANDIDATE_ABSENT = "candidate_absent"
    DIFF_UNPINNABLE = "diff_unpinnable"
    DIFF_FAILED = "diff_failed"
    DIFF_UNREADABLE = "diff_unreadable"


@dataclass(frozen=True)
class FrozenCommit:
    """One end of a prospective diff, or the typed reason there is not one.

    Frozen in both senses: the object id is what the measurement and every
    retry after it are taken against, and the record is immutable so a caller
    cannot carry a `sha` it half-replaced. The two fields are mutually
    exclusive by construction -- the owners return either an id they proved is
    readable here or a failure with no id beside it -- and `is_frozen` is what
    a caller asks rather than truth-testing the SHA, since a repository that
    answered with nothing at all is a failure to establish an end of the diff,
    not an end that happens to be empty.
    """

    sha: str = ""
    failure: Optional[MeasurementFailure] = None

    @property
    def is_frozen(self) -> bool:
        """Whether this end of the diff was established."""
        return self.failure is None and bool(self.sha)


@dataclass(frozen=True)
class AdditionMeasurement:
    """How many lines a candidate adds over its base, or why nobody knows.

    `additions` is `None` rather than 0 on every failure, and the two commits
    are carried as far as they were established, so a park comment and a
    recorded failure can say which end of the diff was already frozen when the
    reading stopped. `is_measured` is the only thing that licenses reading the
    count: a caller that branched on the failure being absent would still have
    to decide what an absent number meant, which is the decision this record
    exists to take away from it.

    What the number is worth comparing to is not this record's business. The
    configured ceiling is pinned into the generation an oversized candidate is
    adjudicated under, and the strictly-past-it comparison belongs there, so a
    verdict is re-answerable from durable state after a crash rather than from
    a reading only the tick that took it still holds.
    """

    base_sha: str = ""
    candidate_sha: str = ""
    additions: Optional[int] = None
    failure: Optional[MeasurementFailure] = None

    @property
    def is_measured(self) -> bool:
        """Whether a count was actually taken, and may therefore be read."""
        return self.failure is None and self.additions is not None
