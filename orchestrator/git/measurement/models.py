# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a reading of a prospective diff is, and the typed reasons there is not one.

The records a reading hands around all live here -- the two ends of the diff,
the count over them, the fingerprint of what lies between them, and the
readback saying whether an end this host was supposed to hold is really here
-- because every one of them is spent by a caller in another module and none
is owned by the step that happens to build it.

Each failure vocabulary lives beside the record it stands in for, because
every member of one says the same thing about that record: this reading did
not happen. That distinction is the whole point of the domain. A candidate
whose size is unknown is not a small one -- "small" is what publishes an
implementation without adjudicating it -- so a failed reading carries no count
at all rather than the zero a failed `git` invocation would otherwise be read
as, and no digest rather than the hash of the nothing such an invocation
writes.

The members are separate because the operator's next move differs by which
step could not be completed, and because a retry has to know how far the
previous attempt got: a base the remote would not name is a token or transport
problem, a base this clone does not hold is a fetch that brought nothing back,
a candidate that will not resolve is a checkout to look at, a candidate whose
object is missing is work made on a host this one is not, and a diff nothing
here can pin is a checkout carrying something that decides what counts as text
-- which an operator has to clear before any reading of it is worth taking.

The two vocabularies stay apart for a reason of the same kind. A count and a
fingerprint fail over overlapping ground and are reported through the same
sinks, so members spelled alike would leave a park reason saying which step
stopped without saying which reading it stopped.

The version the digest scheme is at sits here for the reason the records do:
it is spent where a digest is, and a digest is only ever spent somewhere else.
A caller that persists one persists this beside it, because two ids taken
under different rules are not comparable and nothing about the ids themselves
would say so.
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


# Which scheme a contribution digest was taken under. It is recorded rather
# than assumed because a digest is only ever useful compared, and comparing
# two taken under different rules is the one thing an id like this may never
# license: what a reader holds is an answer from another tick, another host,
# or an older binary, and the version beside it is the whole of what says that
# answer was reached the way this build reaches one. The `fingerprint` owner
# spells the label it hashes behind from this number, so a representation that
# changes is a version that changes with it.
FINGERPRINT_FORMAT = 1


class FingerprintFailure(StrEnum):
    """The step a fingerprint stopped at, named rather than swallowed.

    A separate vocabulary from `MeasurementFailure` rather than a reuse of the
    overlapping half of it, and the wire strings say which reading they came
    from for the same reason: the two are recorded, reported, and turned into
    park reasons by the same machinery, and a bare `base_absent` on either
    sink would not say whether the count or the identity of a contribution is
    the thing nobody has.

    The members differ by what an operator does next. An end whose object this
    host does not hold is a fetch, and which end it is decides where from. A
    listing that failed is the checkout itself. Content the listing names and
    this store cannot hand back is an object lost rather than a commit missing
    -- the commits are provably here, so a fetch of the branch may well bring
    nothing back and the store is what has to be repaired. And a listing this
    build cannot parse is neither: it is a reading that arrived in a shape
    nothing here can account for, and nothing inside it was ever read.
    """

    BASE_ABSENT = "fingerprint_base_absent"
    CANDIDATE_ABSENT = "fingerprint_candidate_absent"
    DIFF_FAILED = "fingerprint_diff_failed"
    DIFF_UNREADABLE = "fingerprint_diff_unreadable"
    CONTENT_ABSENT = "fingerprint_content_absent"


@dataclass(frozen=True)
class ContributionFingerprint:
    """What a candidate contributes over its base, as one comparable id.

    `digest` is empty on every failure rather than carrying a hash of
    whatever came back, and `is_fingerprinted` is the only thing that licenses
    reading it: a `git diff` that failed writes nothing to stdout, which is
    also what a candidate that changes nothing writes, so a digest taken
    without asking would be a real-looking id shared by every failed reading
    on every host -- and two of them comparing equal is exactly the claim a
    fingerprint exists to make. A reading that SUCCEEDED over content this
    host cannot hand back is the same danger wearing a better disguise, since
    nothing about that id would say the bytes behind it never arrived.

    The two ends are carried because a digest that does not say what it was
    taken over cannot be re-taken. They are NOT in the digest itself: what is
    fingerprinted is the contribution, so the same work over the same base
    fingerprints identically no matter which commits carry it, which is the
    whole of what the id is good for.

    `detail` is the failing listing's own first line, kept for the reason it
    is kept on a measurement: the reading is taken deep in the git layer and
    reported far from it, and by the time anybody is told there is no
    fingerprint, the stderr that would have said why is gone. Free text for a
    human, never anything to branch on, and never a credential -- nothing here
    runs a transport.
    """

    base_sha: str = ""
    candidate_sha: str = ""
    digest: str = ""
    failure: FingerprintFailure | None = None
    detail: str = ""

    @property
    def is_fingerprinted(self) -> bool:
        """Whether a digest was really taken, and may therefore be read."""
        return self.failure is None and bool(self.digest)


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
