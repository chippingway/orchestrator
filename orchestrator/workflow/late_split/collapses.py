# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a squash says it is about to do, before it destroys the evidence of it.

A squash is the one rewrite in this workflow that leaves the branch unable to
describe itself. It collapses the commits a reviewer approved into a single
object with the same tree, so the head it replaced, the base it was read over,
and how many commits went into it are all gone the moment the reset lands --
and a one-commit branch is exactly what a branch nobody ever squashed looks
like. Read afterwards, the two are indistinguishable: the retry takes the
nothing-to-squash road and reports success without measuring or pushing
anything, so reviewer-approved work reaches the merge button neither counted
nor on the remote.

So the rewrite says what it is about to do first, and this is the record it
says it in. It goes down BEFORE the reset and it is the whole of what a later
tick has to tell an interrupted rotation from a finished one:

* the HEAD the squash is collapsing, which is the rollback target and the head
  the force-push behind it is leased against;
* the BASE it is collapsed over, which is the end the contribution a transfer
  is granted on is read from;
* the COUNT of commits going into it, which is the one fact no reading past
  the reset could recover -- the collapsed commits are off the branch, and
  only the reflog still has them.

Three fields and no more, because what a recovery may act on is what it can
check. Every other term the resumed publication needs is asked again from the
world it is about: the pull request is re-read, the checkout is re-proved, the
contribution is re-fingerprinted, and the ceiling is this build's own. A field
here that could not be checked would be a claim a crash could turn into a
push nobody measured.

Read fail-closed and whole or not at all, like every other late record. A
member that is missing, a value that is not a whole object id, and a count
that is not a number of commits a squash collapses each read back as no
pending collapse -- and a comment CARRYING one of those is not the same as one
carrying none, which is the question `carries_pending_collapse` answers for
the caller that would otherwise wave a collapsed branch past as having nothing
to squash.

One boundary is left over once the rewrite is finished, and it is why this
record outlives the push. The write that ends the claim and the relabel behind
it are two calls, and an issue left on `validating` between them is one the
next tick runs a second reviewer on, over a branch already approved, squashed,
and published. So the record is not dropped there but SETTLED -- replaced by
the commit the handoff was made over, which is what the route ahead of that
reviewer reads to move the label instead. It is deliberately not a member of
the group above: nothing about the rewrite is outstanding by then, so nothing
may freeze the branch or refuse to resume over it.

The keys live outside `LATE_STATE_KEYS` for the reason the exemption's do:
they describe a rewrite that outlives the generation it was made under -- the
gate retires one the moment it approves the squashed commit -- so the write
that clears a generation may take none of them.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.late_split import formats as _formats, payloads as _payloads

# The head the squash is collapsing and the base it is collapsed over, spelled
# here because this is the record's owner and deliberately outside the keys
# `clear_late_generation` drops.
LATE_COLLAPSE_HEAD = "late_collapse_head"

LATE_COLLAPSE_BASE_SHA = "late_collapse_base_sha"

# How many commits go into it. The one field that is not a commit, and the one
# nothing past the reset could re-derive: what it is spent on is the notice a
# finished handoff owes the pull request, which says how much history the
# force-push replaced.
LATE_COLLAPSE_COUNT = "late_collapse_count"

# What is left of the record once the rewrite itself is over: the commit the
# push put on the pull request, kept until the label behind it has moved. It
# is the successor of the group above rather than a member of it -- nothing is
# outstanding about the rewrite any more, so nothing may freeze the branch or
# refuse to resume over it -- and it is what closes the one boundary the group
# could not, between the write that ends a collapse and the relabel behind it.
LATE_COLLAPSE_HANDOFF = "late_collapse_handoff_sha"

# What the two recorded ends have to be, at their exact length. An
# abbreviation is not a commit this domain froze, so neither end is a value a
# reset or a lease could be taken on.
_HEX_SHAPES = MappingProxyType({
    LATE_COLLAPSE_HEAD: _formats.COMMIT_LENGTHS,
    LATE_COLLAPSE_BASE_SHA: _formats.COMMIT_LENGTHS,
})

# Everything one pending collapse leaves on the pinned comment, taken as one
# group: it describes one rewrite of one branch, so a record short of any
# member describes a rewrite this issue cannot show the terms of.
_COLLAPSE_KEYS = (*_HEX_SHAPES, LATE_COLLAPSE_COUNT)

# The fewest commits a squash collapses. One is the branch a squash leaves
# behind, so a record claiming it describes no rewrite anybody made.
_COLLAPSED_AT_LEAST = 2


@dataclass(frozen=True)
class LateCollapse:
    """One squash this issue began and may not have finished.

    Handed out whole or not at all, so nothing downstream has to decide what
    half of one means. `head` is the commit the branch stood on before the
    reset -- the rollback target, and the head the push is leased against.
    `base_sha` is the fork point it was collapsed onto, which is the end both
    contributions are read from when a transfer is decided. `count` is how
    many commits went in, which is what the handoff behind a resumed
    publication announces.
    """

    head: str
    base_sha: str
    count: int


def carries_pending_collapse(state: PinnedState) -> bool:
    """Whether this comment claims a squash at all.

    Presence rather than truth, and presence of ANY member rather than of all
    of them, because what this answers is whether the comment is CLAIMING an
    unfinished rewrite -- which a record a crash left half written, or one a
    hand edit damaged, claims just as loudly as a whole one. Asked through the
    fail-closed reader instead, a damaged claim would read as no claim, and
    the branch it is about -- one commit, collapsed, unpushed -- would be
    waved past as having nothing to squash.

    The key being THERE is the whole test, rather than the value under it
    being something. A pinned comment is JSON, so a field can be present and
    `null`, and a group carrying one member spelled that way is exactly the
    minimal damaged claim this exists to catch.
    """
    return any(key in state.data for key in _COLLAPSE_KEYS)


def read_pending_collapse(state: PinnedState) -> LateCollapse | None:
    """Return the squash this issue may not have finished, or None.

    None wherever the record cannot vouch for itself, which is every way it
    can fail to: a field that is missing, a group where only some of them are
    there, an end that is not a whole object id, and a count that is not a
    number of commits a squash collapses. Each of those is a record nothing
    may act on, and what acting on one would do is publish -- under a lease
    nobody can check -- a commit no reading here established.

    A caller that has to tell "no claim" from "a claim nobody can read" asks
    `carries_pending_collapse` beside this, because the two answers owe the
    branch different things: nothing at all, and a refusal.
    """
    recorded = {
        key: _payloads.as_hex(state.get(key), lengths)
        for key, lengths in _HEX_SHAPES.items()
    }
    collapsed = _payloads.as_identity(state.get(LATE_COLLAPSE_COUNT))
    if not all(recorded.values()) or collapsed is None:
        return None
    if collapsed < _COLLAPSED_AT_LEAST:
        return None
    return LateCollapse(
        head=recorded[LATE_COLLAPSE_HEAD],
        base_sha=recorded[LATE_COLLAPSE_BASE_SHA],
        count=collapsed,
    )


def record_pending_collapse(
    state: PinnedState, head: str, base_sha: str, count: int,
) -> None:
    """Record the squash this branch is about to become, before it becomes it.

    Written while the collapsed commits are still on the branch, because that
    is the only moment every term of it can be read: past the reset the head
    is off the branch, the count is gone with the commits it counted, and the
    base is not derivable from the object that replaced them.

    Every field is held to the shape it claims for the reason each pinned end
    in this domain is -- a value that cannot name a commit is not one, and a
    count of one collapses nothing -- and writing one would move the failure
    onto a reader whose only move is to publish under it.
    """
    for given in (head, base_sha):
        if not _formats.is_hex_of(given, _formats.COMMIT_LENGTHS):
            raise _formats.InvalidLateValue(
                f"a pending collapse is not one ({type(given).__name__})",
            )
    if not _formats.whole_number(count) or count < _COLLAPSED_AT_LEAST:
        raise _formats.InvalidLateValue(
            f"a squash does not collapse {count!r} commits",
        )
    state.set(LATE_COLLAPSE_HEAD, head)
    state.set(LATE_COLLAPSE_BASE_SHA, base_sha)
    state.set(LATE_COLLAPSE_COUNT, count)


def clear_pending_collapse(state: PinnedState) -> None:
    """Drop the whole record, leaving every other field alone."""
    for key in _COLLAPSE_KEYS:
        state.data.pop(key, None)


def settle_pending_collapse(state: PinnedState, published: str) -> None:
    """End the record of the rewrite, keeping what the label still owes.

    The last thing a finished collapse is. The push landed, the notice its
    count was worded from went out, and the watermarks behind it are seeded,
    so nothing about the REWRITE is outstanding any more -- but the relabel is
    a second call, and a process that dies between the two comes back to an
    issue still labeled `validating` with nothing on the comment saying any of
    it happened. Read as an ordinary tick, that issue gets a second reviewer
    over a branch this stage already approved, squashed, and published.

    So the record does not simply go: it becomes the commit the handoff was
    made over, which is the whole of what the move still needs and the only
    thing that says the move is owed. An approval that collapsed nothing
    leaves none -- there was no claim to end, and the label is all it ever
    owed -- and neither does a publication whose commit is not one this domain
    froze. A value that cannot name a commit is not one a later tick could
    check the publication against, and a record nothing can check is exactly
    what this one may not become: what it buys is a relabel taken without a
    reviewer.
    """
    claimed = carries_pending_collapse(state)
    clear_pending_collapse(state)
    if claimed and _formats.is_hex_of(published, _formats.COMMIT_LENGTHS):
        state.set(LATE_COLLAPSE_HANDOFF, published)


def read_settled_handoff(state: PinnedState) -> str:
    """The commit a finished squash still owes its relabel over, or "".

    Held to the same shape every other end in this domain is: a whole object
    id, at its exact length. What the value is spent on is a comparison
    against the commit the pull request is standing on, and what a value that
    cannot name a commit buys is a comparison nobody can make -- which, on the
    road where there is no pull request to compare against at all, is a label
    moved past the reviewer on the strength of a string somebody typed.

    Read for a usable value rather than for presence, which is the opposite of
    what the group above is read for and for the opposite reason. A claim
    nobody can read there describes a branch mid-rewrite, so it has to reach a
    refusal; here it describes a rewrite already measured, published, and
    announced, where the most an unreadable value can cost is the reviewer
    round this route would have saved -- so it is dropped and the round runs.
    """
    return _payloads.as_hex(
        state.get(LATE_COLLAPSE_HANDOFF), _formats.COMMIT_LENGTHS,
    ) or ""


def clear_settled_handoff(state: PinnedState) -> None:
    """Drop the handoff record, leaving every other field alone."""
    state.data.pop(LATE_COLLAPSE_HANDOFF, None)
