# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a child born of a late split inherits, and where it reads it back.

A generation is a record about an issue's OWN candidate; this is the record
about the one it came out of. They are separate fields because they answer
separate questions and have separate lifetimes: a generation is minted,
adjudicated, and retired inside one issue, while an ancestry is written once
when the child is created and is still true after that child has been
implemented, split again, and closed.

Four things travel, and each has a reader that cannot do without it:

- **The lineage.** The root issue and the depth this child is born at are what
  the child's own size gate mints its generation from, so automatic splitting
  stops at the same bound whether an issue is the root or three generations
  down. A child that could not say how deep it is would read as a root and buy
  the lineage another generation.
- **The ancestor's identity.** The cycle, the generation, and the issue that
  split are what a telemetry record about this child correlates to the
  adjudication that created it, and what a human reading a stuck child follows
  back.
- **The snapshot.** The ref and the exact commit under it are the only durable
  pointer to the work this child is meant to reuse -- the branch it was
  committed on is superseded, and the pull request that carried it is closed.
  A third field travels with the pair and is a claim about the WORLD rather
  than about this child: that any reclamation which can take that ref takes
  this host's copy of it down first. The child's own guard reads a surviving
  copy as proof no reclamation has happened, and that reading is sound only
  against an orchestrator ordering the two -- so a pointer written before this
  one did carries no such claim, and is answered on the wire instead.
- **The declared scope.** The slice of the parent's scope this child owns, in
  the words the adjudication used. It is what the child's own late prompt
  states, so an indivisible slice that is still large gets a fast `single`
  rather than being re-split against a scope nobody wrote down.

Everything is additive and read fail-closed, exactly as the generation's own
fields are: an issue that was never born of a split carries none of these
keys and reads back as the record's defaults, and a hand-edited field reads
back absent rather than becoming a lineage nobody wrote. The snapshot ref is
checked against the namespace that owns it rather than merely for being a
string, because a child pointed at a ref outside it would be pointed at a
branch, a tag, or nothing at all.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any


from orchestrator.git.snapshots import namespace as _namespace
from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.late_split import formats as _formats
from orchestrator.workflow.late_split import payloads as _payloads
from orchestrator.workflow.late_split.models import LateGeneration

_ROOT_ISSUE = "late_ancestry_root_issue"
_DEPTH = "late_ancestry_depth"
_PARENT_ISSUE = "late_ancestry_parent"
_CYCLE_ID = "late_ancestry_cycle_id"
_GENERATION = "late_ancestry_generation"
_SNAPSHOT_REF = "late_ancestry_snapshot_ref"
_SNAPSHOT_SHA = "late_ancestry_snapshot_sha"
_MIRROR_FIRST = "late_ancestry_mirror_first"
_BASE_BRANCH = "late_ancestry_base_branch"
_SCOPE = "late_declared_scope"

LATE_ANCESTRY_KEYS = (
    _ROOT_ISSUE,
    _DEPTH,
    _PARENT_ISSUE,
    _CYCLE_ID,
    _GENERATION,
    _SNAPSHOT_REF,
    _SNAPSHOT_SHA,
    _MIRROR_FIRST,
    _BASE_BRANCH,
    _SCOPE,
)


@dataclass(frozen=True)
class LateAncestry:
    """Where one issue came from, when it came from a late split.

    Frozen for the reason the generation is: every field is evidence a later
    tick acts on rather than re-derives. The snapshot the child reuses, the
    depth its own splitting is bounded by, and the adjudication its records
    correlate to are all facts about an event that has already happened.
    """

    root_issue: int = 0
    lineage_depth: int | None = None
    parent_issue: int = 0
    cycle_id: int = 0
    generation: int = 0
    snapshot_ref: str = ""
    snapshot_sha: str = ""
    mirror_first: bool = False
    base_branch: str = ""
    scope: str = ""

    @property
    def is_present(self) -> bool:
        """Whether this issue was born of a late split at all."""
        return self.parent_issue > 0 and self.cycle_id > 0

    @property
    def trusts_the_mirror(self) -> bool:
        """Whether a surviving local copy of the ref proves anything here.

        False for every pointer written before the reclamation put this
        host's copy ahead of the remote ref, and that is not a detail of an
        upgrade: an orchestrator that deleted the remote first and dropped the
        mirror afterwards could leave a copy standing beside a ref that is
        gone, which is exactly the world the shortcut would misread. The
        stamp is what separates the two, and an unstamped ancestry pays one
        read-only ask instead.
        """
        return self.mirror_first and self.has_snapshot

    @property
    def has_snapshot(self) -> bool:
        """Whether a usable pointer to the preserved candidate survived.

        Both halves or neither: a ref with no commit beside it cannot be
        verified against anything, and a commit with no ref names work nothing
        can fetch. A child that reads False here has lost the artifact it was
        meant to reuse, which is a thing to say out loud rather than to
        reconstruct.
        """
        return bool(self.snapshot_ref) and bool(self.snapshot_sha)

    def named_snapshot(self) -> "LateAncestry":
        """This lineage with the snapshot ref its own identity names.

        The one fact a child whose ancestry write never landed can still
        recover about the ref it was cut from. The name is minted from the
        owner, the cycle, and the generation -- all three of which its BODY
        marker carries -- so re-deriving it here re-reads a fact rather than
        inventing one, and it is the same derivation the reclamation holds its
        own ledger to before it deletes anything.

        The COMMIT is not recoverable that way and stays empty: what the
        failed write was carrying is exactly what nobody wrote down. So what
        comes back still answers `has_snapshot` False, which is what keeps it
        out of every reading that needs the pair -- `vouched_lineage` is where
        the missing half comes from, and it comes from the owner's own record
        rather than from anything this issue says about itself.

        An identity that cannot produce a ref comes back unchanged -- a body
        edited into nonsense names no snapshot for anyone to ask about.
        """
        try:
            derived = _namespace.snapshot_ref(
                issue_number=self.parent_issue,
                cycle_id=self.cycle_id,
                generation=self.generation,
            )
        except _namespace.InvalidSnapshotRef:
            return self
        return replace(self, snapshot_ref=derived)

    def without_snapshot(self) -> "LateAncestry":
        """The same lineage with the pointer to the candidate dropped.

        What a child is left with once the ref it named is one it may not use.
        The lineage itself survives -- which split made this issue, how deep it
        is, and what slice it owns are still true -- and only the pair that
        says "fetch this" goes, because an ancestry that goes on naming an
        unusable ref is one every later reader would follow.
        """
        return replace(self, snapshot_ref="", snapshot_sha="")


# Stamped into every child's body so the create that returned into a crash can
# be recognized again. It names the ISSUE as well as the adjudication and the
# slice, because a cycle identity is minted per issue and repeats across them:
# two parents adjudicating their first candidate are both cycle 1, generation
# 1, and their first slices would otherwise carry the same marker -- while the
# lookup that reads it is scoped to no parent at all, walking the repository's
# issues in every state and under no label, so one parent would adopt, reseed,
# and activate the other's child. An HTML comment, so it is invisible in the
# rendered issue.
#
# It lives beside the ancestry rather than with the transaction that writes it
# because it is the only durable record of a child's lineage the split writes
# OUTSIDE the pinned comment -- which is what makes it readable when the pinned
# write that would have recorded the same thing never landed. The prefix is its
# own name because two readings need it: the marker is built from it, and a
# candidate the orphan lookup returns is checked for carrying exactly one.
CHILD_RECEIPT = "<!--orchestrator-late-child:"

_CHILD_MARKER = CHILD_RECEIPT + (
    "issue={issue}:cycle={cycle}:generation={generation}:index={index}-->"
)

_CHILD_LINEAGE = re.compile(
    r"<!--orchestrator-late-child:"
    r"issue=(?P<issue>\d+):cycle=(?P<cycle>\d+):"
    r"generation=(?P<generation>\d+):index=\d+-->",
)


def child_marker(
    *, issue: int, cycle: int, generation: int, index: int,
) -> str:
    """The hidden marker naming one child's issue, adjudication, and slice."""
    return _CHILD_MARKER.format(
        issue=issue, cycle=cycle, generation=generation, index=index,
    )


def child_lineage(body: Any) -> LateAncestry | None:
    """The lineage a child's own body claims, or None when it claims none.

    The one reading of a child that costs nothing and survives everything. A
    split records a child on the parent's ledger BEFORE it seeds that child's
    ancestry -- a child on GitHub the parent does not record is a child
    nothing would come back to -- so the window between the two is durable:
    an ancestry write that failed leaves an issue whose BODY says which split
    made it and whose pinned comment says nothing at all.

    Identity only. The snapshot the child was pointed at is not in the marker,
    and deriving it here would be inventing a fact the failed write is exactly
    what did not record. What this answers is "whose child is this", which is
    all a receipt has to be matched against.

    A body carrying two receipts answers no. That is an issue an older binary
    created or a human edited, and a lineage read off one of two claims is a
    lineage nothing vouches for.
    """
    if not isinstance(body, str) or body.count(CHILD_RECEIPT) != 1:
        return None
    claimed = _CHILD_LINEAGE.search(body)
    if claimed is None:
        return None
    return LateAncestry(
        parent_issue=int(claimed.group("issue")),
        cycle_id=int(claimed.group("cycle")),
        generation=int(claimed.group("generation")),
    )


# The receipt one reclamation leaves on each child it was preserved for. It
# lives beside the ancestry because both ends key it the same way and neither
# may guess: the reclamation writes it from the generation it is settling, and
# the child reads it back from the lineage it was born with.
_RELEASE_MARKER = (
    "<!--orchestrator-late-release owner={owner} cycle={cycle} "
    "generation={generation}-->"
)


def release_marker(*, owner: int, cycle: int, generation: int) -> str:
    """The hidden marker a reclamation's receipt on one child carries.

    Named by the owner, the cycle, and the generation together, because none
    of the three is enough on its own: an issue splits more than once, a cycle
    holds more than one generation, and a child of a later reclamation must
    not read an earlier one's receipt as its own.

    It is a claim nothing can lose. A pinned comment is rewritten whole by
    whoever writes it, so a record left there can be undone by a writer the
    author cannot see; a comment is appended, and the reclamation that reached
    a child stays reached.
    """
    return _RELEASE_MARKER.format(
        owner=owner, cycle=cycle, generation=generation,
    )


def read_late_ancestry(state: PinnedState) -> LateAncestry:
    """Return the ancestry a pinned comment records for this issue.

    An issue that was never split into reads back as the defaults, which
    `is_present` answers False on -- the one reading that keeps every issue
    that reached this workflow another way out of every lineage decision
    without a migration.
    """
    return LateAncestry(
        root_issue=_payloads.as_identity(state.get(_ROOT_ISSUE)) or 0,
        lineage_depth=_payloads.as_depth(state.get(_DEPTH)),
        parent_issue=_payloads.as_identity(state.get(_PARENT_ISSUE)) or 0,
        cycle_id=_payloads.as_identity(state.get(_CYCLE_ID)) or 0,
        generation=_payloads.as_count(state.get(_GENERATION)) or 0,
        snapshot_ref=_snapshot_ref(state.get(_SNAPSHOT_REF)),
        snapshot_sha=_payloads.as_hex(
            state.get(_SNAPSHOT_SHA), _formats.COMMIT_LENGTHS,
        ) or "",
        mirror_first=_payloads.as_flag(state.get(_MIRROR_FIRST)),
        base_branch=_payloads.as_text(state.get(_BASE_BRANCH)) or "",
        scope=_payloads.as_text(state.get(_SCOPE)) or "",
    )


def write_late_ancestry(state: PinnedState, ancestry: LateAncestry) -> None:
    """Record one ancestry, replacing whatever ancestry keys were there.

    Every key is dropped first, so a field a caller cleared leaves no stale
    value for the next tick to read: a child re-seeded against a snapshot that
    no longer exists must not keep pointing at the old one. Keys outside this
    group are untouched -- the pinned comment is shared with every stage, and
    this write is only ever about its own fields.
    """
    clear_late_ancestry(state)
    for key, written in _written_fields(ancestry).items():
        state.set(key, written)


def clear_late_ancestry(state: PinnedState) -> None:
    """Drop every ancestry field, leaving the rest of the state alone."""
    for key in LATE_ANCESTRY_KEYS:
        state.data.pop(key, None)


def contradicted_lineage(
    state: PinnedState, generation: LateGeneration,
) -> str | None:
    """Why this generation's lineage disagrees with the ancestry, or None.

    The one production reading of an ancestry, and it is a refusal rather than
    a substitution. What a child's own generation is minted from is this
    record; if the two ever disagree, the generation was minted without it --
    and the failure that matters is the one that reads the child as shallower
    or rooted elsewhere than it is, which is exactly how a lineage buys itself
    another generation past the cap the bound exists to enforce.

    Refusing rather than correcting is deliberate. A generation whose depth
    was minted wrong has already been adjudicated under a prompt that told the
    agent how much room it had, so quietly deepening it here would act on a
    verdict nobody asked for at that depth. An issue with no recorded ancestry
    is a root and contradicts nothing.
    """
    ancestry = read_late_ancestry(state)
    if not ancestry.is_present:
        return None
    if ancestry.root_issue != generation.root_issue:
        return (
            f"it was created by issue #{ancestry.parent_issue} under root "
            f"#{ancestry.root_issue}, and the generation names root "
            f"#{generation.root_issue}"
        )
    if ancestry.lineage_depth != generation.lineage_depth:
        return (
            f"it was created at lineage depth {ancestry.lineage_depth}, and "
            f"the generation names depth {generation.lineage_depth}"
        )
    return None


def vouched_lineage(
    claimed: LateAncestry, consumer: int, generation: LateGeneration,
) -> LateAncestry | None:
    """The lineage a body claims, as the owner's own generation vouches for it.

    The body marker is the one lineage claim in this workflow that comes out
    of a field the world can write, and every other claim it competes with is
    authenticated: a pinned comment only this orchestrator writes, a receipt
    checked against its author. So it is corroborated rather than believed,
    and the record that corroborates it is the SPLIT's -- read from the owner
    the marker names, where nothing but this orchestrator writes.

    Three things have to agree, because each is a different way for a claim to
    be about something else: the cycle, the generation inside it, and the
    consumer list carrying this issue's number. A marker from another
    adjudication of the same owner, from another generation of the same cycle,
    or on an issue that owner never cut anything for fails one of them.

    What comes back is the whole pointer the failed seed never wrote -- the
    ref the identity mints and the commit the owner recorded preserving -- so
    a caller can ask whether THIS candidate is still obtainable rather than
    whether some ref is occupied. A record that vouches for the consumer and
    not for a commit answers None with the rest: half a pointer is not one.

    None is "this record does not vouch for that claim", which is not the same
    as "this record refutes it": a ledger nobody could read, or one whose
    consumers this binary cannot type, vouches for nothing either. The caller
    holds the record and can tell those apart, which is why it is passed in
    rather than read here.
    """
    if generation.cycle_id != claimed.cycle_id:
        return None
    if generation.generation != claimed.generation:
        return None
    if consumer not in generation.consumers:
        return None
    return replace(
        claimed.named_snapshot(), snapshot_sha=generation.candidate_sha,
    )


def _snapshot_ref(raw: Any) -> str:
    """Return a recorded snapshot ref, or "" unless it is one of ours.

    Checked against the namespace rather than for being a string, because what
    this field is FOR is telling a child which ref to fetch: a value outside
    the namespace names a branch, a tag, or nothing, and handing one to a
    child is worse than handing it none.
    """
    return raw if _namespace.is_snapshot_ref(raw) else ""


def _written_fields(ancestry: LateAncestry) -> dict[str, Any]:
    """Return the pinned fields this ancestry records, unset ones out.

    A field at its own empty value names itself None here and is dropped, so
    the pinned comment carries what the split actually knew. A lineage depth
    of 0 is not one of them: it is the root of a lineage and is written as
    itself, while an unknown depth is dropped -- a child whose depth nobody
    recorded may not read back as a root free to split again.
    """
    fields = {
        _ROOT_ISSUE: ancestry.root_issue or None,
        _DEPTH: ancestry.lineage_depth,
        _PARENT_ISSUE: ancestry.parent_issue or None,
        _CYCLE_ID: ancestry.cycle_id or None,
        _GENERATION: ancestry.generation or None,
        _SNAPSHOT_REF: ancestry.snapshot_ref or None,
        _SNAPSHOT_SHA: ancestry.snapshot_sha or None,
        _MIRROR_FIRST: ancestry.mirror_first or None,
        _BASE_BRANCH: ancestry.base_branch or None,
        _SCOPE: ancestry.scope or None,
    }
    return {
        key: written
        for key, written in fields.items()
        if written is not None
    }
