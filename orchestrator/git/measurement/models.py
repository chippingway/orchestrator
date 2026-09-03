# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a size measurement is, and the typed reasons there is not one.

The records a reading hands around all live here -- the two ends of the diff,
the count over them, and the readback saying whether an end this host was
supposed to hold is really here -- because every one of them is spent by a
caller in another module and none is owned by the step that happens to build
it.

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
    cannot carry a `sha` it half-replaced. `is_frozen` is what a caller asks
    rather than truth-testing the SHA, since a repository that answered with
    nothing at all is a failure to establish an end of the diff, not an end
    that happens to be empty -- and since an id can arrive BESIDE a failure.

    That pairing is deliberate and is the whole reason the two fields are not
    mutually exclusive: an end this owner LEARNED and could not prove is still
    the only record of which commit the attempt was about. Nothing measures
    against it, and the caller that records it does so precisely so the retry
    asks for that exact object rather than for whatever the branch has moved
    to since. What `is_frozen` licenses is unchanged either way: only an id
    with no failure beside it is an end of a diff.

    `detail` is the one line the transport that failed said for itself, and it
    is beside the typed failure rather than folded into it because the two
    answer different readers. The member is what code branches on and what a
    park reason and an event payload carry, so its meanings are a contract
    nothing may widen; the line is free text a human reads, and it is what
    tells an operator whether a base the remote would not name is an expired
    token, a repository this installation cannot see, or a host that was
    simply down. Empty where the step said nothing worth carrying, and never
    the credential: the transport scrubs its own stderr before handing it up.
    """

    sha: str = ""
    failure: MeasurementFailure | None = None
    detail: str = ""

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

    `detail` carries the failing end's own line up with the failure, for the
    same reason the two commits travel: the reading is taken deep in the git
    layer and reported far from it, and by the time a human is told a candidate
    has no size, the stderr that would have said why is long gone. It is free
    text for a reader rather than anything to branch on, and it never carries
    the token -- the transports scrub their stderr before it reaches here.
    """

    base_sha: str = ""
    candidate_sha: str = ""
    additions: int | None = None
    failure: MeasurementFailure | None = None
    detail: str = ""

    @property
    def is_measured(self) -> bool:
        """Whether a count was actually taken, and may therefore be read."""
        return self.failure is None and self.additions is not None


@dataclass(frozen=True)
class _BaseObject:
    """Whether the frozen base is readable here, and what a fetch for it said.

    The presence is the answer the freeze and every retry branch on. The line
    beside it is what the fetch that failed to supply the object wrote, kept so
    the failure a human is eventually shown names the transport fault rather
    than only the step: "not in the local object store even after a fetch" is
    the same sentence for a network that was down, a token that expired
    between two calls, and a base the remote rewrote out from under this host.

    Set exactly when the object is absent, and scrubbed of the token by the
    transport before it ever reaches here.
    """

    present: bool = False
    detail: str = ""
