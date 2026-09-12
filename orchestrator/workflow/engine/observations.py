# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The closes a poll saw that the run holding the issue could not.

A poll that finds a late-split owner closed cannot always hand that reading to
anybody: the scheduler admits no second worker for an issue one is already
running, so the pass that would end the cycle is refused. Every other refusal
costs a turn -- the work is still there next tick -- and this one costs an
OBSERVATION, because a human who reopens the issue before the next pass takes
the reading away for good.

So the reading is kept here rather than dropped, and it is kept for THREE
readers that could not otherwise have it.

**The run already holding the issue.** It re-reads the owner before every step
the remote keeps, and that read answers from GitHub -- which cannot show it a
close and a reopen that both happened inside one of its own steps. This record
can, so the owner read consults it first: a latched close is a closed owner, no
request required, and the run ends its own cycle on the strength of it rather
than creating another child or starting one.

**The process that comes after this one.** The latch is memory, so a restart
loses it, and the durable half is a marked comment the observing poll leaves on
the issue thread -- append-only, which is the whole reason it is a comment: the
pinned state is written whole, so a second writer racing the worker that owns
it would drop whatever that worker recorded in between. A post GitHub refuses
leaves the receipt OWED, and every later poll retries it, because an
observation with no durable half is one a restart takes away entirely.

**The worker that is mid-publication.** Every barrier standing immediately
before a push asks this record, because the issue object the tick opened with
is a snapshot and a close landing since is one only a latch knows. But the
publications those barriers guard -- a first push, one an adjudication
approved, one a recovery owes -- carry no live late cycle, and the poll drops
a reading the record says there is nothing to end. So a hold is taken for as
long as a worker has the issue, and under it the drop is DEFERRED rather than
taken: the decision is the same one made a moment later, and made then it
cannot be made out from under the barrier it was for.

The hold starts where the CLAIM does, which is the scheduler admitting the
submit -- not where the worker gets around to reading anything. Between those
two lie the queue, the worker's own refetch and its label checks, and a poll
meeting the issue in that gap is refused for the very reason the hold exists:
a worker already has it. Holds nest, because the worker takes one of its own
over the whole dispatch and the sequential path has no claim to inherit.

**Which reading a receipt belongs to is counted, not assumed.** The memo saying
one landed is a fact about ONE observation, and observations come one after
another on the same issue: a cycle is ended and retired, an operator takes
`rejected` off, and the fresh cycle a human closes again is owed a receipt of
its own. So every settlement bumps a per-owner generation, the claim to post
carries the generation it was taken at, and a memo is recorded only where that
generation is still current. The pass that posts and the worker that settles
run on different threads, so a receipt that lands either side of a settlement
would otherwise leave a memo standing for a reading nobody holds -- and the
next observation, silently suppressed, would have no durable half at all.

The claim is also what makes the post ONE post. Asking whether a receipt is
owed and getting one onto the thread cannot be made a single operation, and
two polls are in that gap together whenever a worker's failed pass and the
next tick's enumeration meet, so the right to attempt it is taken here, under
the lock, and handed back by whichever half of the attempt finished it: the
write that recorded the memo, or the failure that recorded nothing.

That receipt is scanned for once per owner per process, claimed through
`claim_receipt_scan`, because what it recovers is an observation a DEAD process
was holding; every observation this process makes is in the latch already. A
scan that could not be taken releases its claim rather than standing on a read
that established nothing.

Keyed by repository and issue, and process-wide rather than per-scheduler: the
readers are stage handlers deep inside a worker, and the alternative is
threading a scheduler through thirteen handler signatures that have nothing to
do with it.
"""
from __future__ import annotations

import contextlib
import threading
from dataclasses import dataclass

# Closes observed and not yet settled; the ones whose durable receipt is on the
# thread, against the generation it was posted for; the owners a receipt is
# being posted for right now; how many readings of each owner a pass has
# actually settled; and the owners whose thread has been asked about an
# inherited receipt; and the cycle a worker is retiring off each record right
# now. Module-level and lock-guarded, like the running-process registry the
# agent runner keeps: the writer is the polling thread and the readers are
# workers, so the record has to outlive both.
_observed: set[tuple[str, int]] = set()
_receipted: dict[tuple[str, int], int] = {}
_posting: set[tuple[str, int]] = set()
_settlements: dict[tuple[str, int], int] = {}
_scanned: set[tuple[str, int]] = set()
_retiring: dict[tuple[str, int], int] = {}
_publishing: dict[tuple[str, int], int] = {}
_deferred: set[tuple[str, int]] = set()
_lock = threading.Lock()


def _owner_key(repo_slug: str, issue_number: int) -> tuple[str, int]:
    """The one shape every registry here is keyed by."""
    return (repo_slug, int(issue_number))


@dataclass(frozen=True)
class ReceiptClaim:
    """One poll's right to post one observation's receipt.

    Handed out by `claim_receipt_post` and handed back by whichever half of
    the attempt finished it, so the owner it names and the reading it was
    taken for travel together: a claim settled against a different generation
    is one a cleanup ended while the post was still in flight, and the memo
    behind it belongs to nobody.
    """

    key: tuple[str, int]
    generation: int


def observe_close(repo_slug: str, issue_number: int) -> None:
    """Latch a close this poll saw, so what reads it cannot miss it."""
    with _lock:
        _observed.add(_owner_key(repo_slug, issue_number))


def close_observed(repo_slug: str, issue_number: int) -> bool:
    """Whether a close is latched on this issue and nothing has settled it.

    The barrier every irreversible step of a late cycle is asked past. It
    costs no request, which is why it can be asked as often as there are
    steps.
    """
    with _lock:
        return _owner_key(repo_slug, issue_number) in _observed


def observed_closes(repo_slug: str) -> frozenset[int]:
    """Which of this repo's issues are owed a cleanup pass regardless."""
    with _lock:
        return frozenset(
            issue_number
            for held_slug, issue_number in _observed
            if held_slug == repo_slug
        )


def settle_close(repo_slug: str, issue_number: int) -> None:
    """Drop a latched close, now that a pass has actually run it.

    Called from the worker that ran the cleanup, once it has returned --
    never from the submit that admitted it. An admitted submit is not a
    cancellation persisted: the worker refetches the issue over GitHub first,
    and a read that fails leaves the cycle unmarked with nothing saying a
    close was ever seen.

    The receipt memo goes with it, so an observation made later against the
    same issue is written down again rather than assumed durable from a
    reading this pass has already discharged. The generation moves in the
    same breath, which is what makes that true of a receipt still being
    posted as this runs: the claim it was taken under is stale from here on,
    and the memo behind it is refused rather than written over the reading
    this settlement just ended.

    DEFERRED while a worker is acting on the issue, because the barriers
    standing immediately before that worker's push read the same latch and the
    publications they guard carry no late cycle for a poll to recognise. The
    drop itself is not refused -- it is taken again on the way out of that
    window, where it is the same decision one moment later -- so nothing is
    kept for good and nothing is dropped out from under the reader it was for.
    """
    key = _owner_key(repo_slug, issue_number)
    with _lock:
        if key in _publishing:
            _deferred.add(key)
            return
        _settled(key)


def _settled(key: tuple[str, int]) -> None:
    """Drop one latched reading, its memo and the generation it was counted at.

    The three go together or the record contradicts itself, so this is the one
    spelling of a settlement and every caller holds the lock across it. The
    caller that postpones one holds it across the release that discharges it
    too: released and settled apart, a poll latching in between would have its
    fresh reading erased by a drop taken for the one before it, and the
    generation would move twice for a single settlement -- which is exactly
    how a receipt already on the thread stops suppressing the next post.
    """
    _observed.discard(key)
    _receipted.pop(key, None)
    _settlements[key] = _settlements.get(key, 0) + 1


def claim_receipt_post(
    repo_slug: str, issue_number: int,
) -> ReceiptClaim | None:
    """Take the one right to post this observation's receipt, or decline.

    The generation the claim was taken at travels back with it, and it is
    what `receipt_written` records the memo against: a settlement landing
    while the post is in flight moves that generation on, and a memo written
    from the stale one would say the NEXT observation's receipt is already
    durable when nothing on the thread says any such thing.

    None is both ways this owes nothing: a receipt already recorded for the
    reading in hand, and a post another poll is making right now. The second
    is what keeps the check and the post from being two separate decisions --
    a worker's failed pass and the following tick's enumeration are in that
    gap together, and both would otherwise walk a thread that carries no
    receipt yet and post one apiece.

    Handed back by `receipt_written` or `release_receipt_post`, never left
    standing: a claim over an attempt that ended would suppress every later
    poll's receipt for good.
    """
    key = _owner_key(repo_slug, issue_number)
    with _lock:
        if key in _posting or key in _receipted:
            return None
        _posting.add(key)
        return ReceiptClaim(key=key, generation=_settlements.get(key, 0))


def receipt_written(claim: ReceiptClaim) -> None:
    """Record that this reading's receipt is on the thread for good.

    Only where the reading is still the one the claim was taken for. A pass
    that settled the observation in the meantime has already dropped the memo
    on purpose, and re-creating it here would hand the next close a
    suppression it never earned -- an observation held in memory alone, which
    a restart before the run reaches a barrier takes away entirely.

    The one thread walk this process owes the owner is owed again with it.
    That claim is taken once because what it recovers is an observation a DEAD
    process was holding -- but a claim taken before this receipt existed is
    one that proved nothing about it, and every later pass would read past a
    receipt that is now there.
    """
    with _lock:
        _posting.discard(claim.key)
        if _settlements.get(claim.key, 0) != claim.generation:
            return
        _receipted[claim.key] = claim.generation
        # A thread this process already walked has something on it now, so
        # the one look it owed is owed again: the claim was taken when there
        # was nothing to find, and a later pass reading past it would step
        # straight over the receipt this attempt just landed.
        _scanned.discard(claim.key)


def release_receipt_post(claim: ReceiptClaim) -> None:
    """Hand back the right to post a receipt that never landed."""
    with _lock:
        _posting.discard(claim.key)


@dataclass
class RetiringCycle:
    """One worker's retirement window, and what landed inside it.

    Mutable where `ReceiptClaim` is frozen, because the answer is not known
    when the window opens: `observed` is written as the window CLOSES, under
    the lock that closes it, so what a caller reads afterwards is every close
    latched while the cycle was still advertised and nothing latched after.

    Built before the write it covers rather than by the `with` that holds it,
    so the answer outlives the block that decided it.
    """

    key: tuple[str, int]
    cycle_id: int
    observed: bool = False

    @contextlib.contextmanager
    def held(self):
        """Advertise this cycle for as long as the retirement write runs.

        A retirement is the one write that takes a cycle identity OFF a
        record, and everything that decides what a close is worth reads that
        identity: a poll asks the record whether there is a cycle a close
        would end, and the ending itself is entered from the mark a cycle
        carries. So between that write and the barrier behind it the record
        answers "nothing to end" about an issue whose worker is still holding
        the reading -- and a poll that believed it would drop the observation
        the worker is about to ask for.

        Held across the write, so both orderings answer the same: a poll that
        reads the record first sees the cycle, and one that reads it after
        sees this. What is advertised is the cycle id, which is what makes the
        observation DURABLE across the retirement -- the receipt a poll leaves
        on the thread is scoped to a cycle, and a retired record has none to
        scope it to.

        What the window OBSERVED is taken as it closes, under the same lock
        that closes it. That is the whole of the handoff: a barrier the worker
        takes before the exit leaves an interval -- however short -- in which
        a poll can still latch a close and post a receipt against the cycle
        this is advertising, and the worker would pass on having seen neither.
        Deciding it at the exit leaves no such interval: every observation
        made while the cycle was advertised is reported, and one made after it
        finds a record with no cycle and no window to correlate against, so it
        is dropped rather than written down.

        A cycle id of zero is no cycle at all -- an umbrella the initial
        decomposer made retires nothing -- and advertising one would have a
        poll keep a reading against an identity nothing could ever correlate
        it to. Nothing is advertised and nothing is observed.

        A worker holds one for one issue at a time, because the scheduler
        admits no second worker for an issue one is already running.
        """
        if not self.cycle_id:
            yield
            return
        with _lock:
            _retiring[self.key] = self.cycle_id
        try:
            yield
        finally:
            with _lock:
                _retiring.pop(self.key, None)
                self.observed = self.key in _observed


def retiring(
    repo_slug: str, issue_number: int, cycle_id: int,
) -> RetiringCycle:
    """The window one retirement is made inside, before it is held."""
    return RetiringCycle(
        key=_owner_key(repo_slug, issue_number), cycle_id=int(cycle_id),
    )


def cycle_being_retired(
    repo_slug: str, issue_number: int,
) -> int | None:
    """The cycle a worker is retiring off this record right now, if any."""
    with _lock:
        return _retiring.get(_owner_key(repo_slug, issue_number))


def claim_publication(repo_slug: str, issue_number: int) -> None:
    """Hold this issue's readings for a worker that has been given it.

    Taken where the CLAIM is -- the scheduler admitting a submit -- rather
    than where the worker first reads anything. Between those two lie the
    queue, the refetch and the label checks, and a poll meeting the issue in
    that gap has its own submit refused for the very reason this exists: a
    worker already has it. Dropping the reading there would take it out from
    under a barrier that has not run yet.

    Counted rather than flagged, because the holds nest: the dispatch takes
    one of its own over the whole handler, and the sequential path -- which
    has no claim to inherit -- takes that one alone.
    """
    key = _owner_key(repo_slug, issue_number)
    with _lock:
        _publishing[key] = _publishing.get(key, 0) + 1


def release_publication(repo_slug: str, issue_number: int) -> None:
    """Give one hold back, and settle what the last of them postponed.

    What a hold changes is WHEN a drop lands, not whether. Under it a settle
    is recorded rather than taken, and the recorded one is applied as the last
    hold goes -- the same drop, one moment later, where it can no longer be
    taken out from under the barrier it was for. Nothing is kept for good, so
    an issue somebody reopens inherits no latch a later poll would never
    clear.

    The release and the drop it discharges are ONE critical section, because
    between them this owner would be holding neither: a poll latching a fresh
    close there would have it erased by a settlement taken for the reading
    before it, and its receipt memo with it, while the generation moved twice
    for one settlement. So a settle arriving as the last hold goes is either
    under this lock -- deferred, and taken here -- or past it and taken for
    itself, and there is no third moment for it to arrive in.
    """
    key = _owner_key(repo_slug, issue_number)
    with _lock:
        held = _publishing.get(key, 0) - 1
        if held > 0:
            _publishing[key] = held
            return
        _publishing.pop(key, None)
        if key in _deferred:
            _deferred.discard(key)
            _settled(key)


@contextlib.contextmanager
def publishing(repo_slug: str, issue_number: int):
    """One hold, for a caller whose whole use of it is one block.

    The dispatch takes this over the handler it runs, which is the hold the
    sequential path has and the only one it has. A worker reached through the
    scheduler takes it under the claim that admitted it, and the two nest.
    """
    claim_publication(repo_slug, issue_number)
    try:
        yield
    finally:
        release_publication(repo_slug, issue_number)


@contextlib.contextmanager
def scanning_receipt(repo_slug: str, issue_number: int):
    """Whether this process still owes this owner's thread one look.

    True once per owner per process, and the claim is taken as this is
    ENTERED rather than once the walk has answered, so a thread that carries
    no receipt is not walked again every tick. What the scan recovers is an
    observation a process that died was holding: anything observed since is
    in the latch, which costs nothing to ask.

    Handed back where the walk established nothing, which is what makes the
    claim honest. A listing that raises proved neither answer, and a claim
    standing over one would send every later tick straight past the receipt
    and on to the live stage handler -- so the claim survives a body that
    RETURNS and not one that raises, which is exactly the difference between
    a walk that answered and a walk that did not.
    """
    key = _owner_key(repo_slug, issue_number)
    with _lock:
        claimed = key not in _scanned
        _scanned.add(key)
    try:
        yield claimed
    except Exception:
        if claimed:
            with _lock:
                _scanned.discard(key)
        raise
