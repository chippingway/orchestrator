# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The typed vocabularies a late generation is described by, and its record.

Every value a late field can hold is spelled once here, because each of them
is durable: a phase, a verdict, a typed failure, and a ledger entry's kind and
state are written into the pinned comment and read back by a later tick, so a
renamed member is a migration rather than a refactor. They are `StrEnum`
members for the same reason the workflow labels are -- a member IS its wire
string, so the pinned JSON, the audit payload, and a comparison against a
plain string all read the same value.

`LateGeneration` is the whole record one generation is reconciled from, held
frozen because every field on it is evidence: the SHAs a reconciliation is
allowed to act on, the measurement a verdict answers, and the resources the
remote still owes are what a crashed tick reads back instead of re-deriving
from a moving branch. The transforms that need to change one -- recording an
obligation, recording a consumer, moving the boundary it stands at, and
cancelling -- return a new record rather than mutating this one, so a caller
cannot half-apply a change it then fails to persist.

The boundary move is also where one invariant of the phase vocabulary lives
rather than in the owners that write it. A record may move forwards freely
and may never move BACKWARDS out of a transaction that has begun: every retry
above a split names a boundary of its own, and in the window where a child
exists and nothing records it the phase is the only account of what happened.
Leaving that to each writer would mean every future one had to know.

The lineage cap is here rather than beside a caller because it is the record's
own invariant: `MAX_LINEAGE_DEPTH` bounds how deep automatic splitting may go,
and a depth at or past it (a hand-edited pinned comment included) reads as
"may not split" rather than as an error to recover from. A depth that is not
known at all is the same answer: it is `None` rather than 0, because a
generation whose depth could not be read is not a root, and a damaged field on
a lineage already at the bound must not read back as one free to split again.

The publication provenance is additive inside an additive record, and the
absence of it is the answer rather than a gap: a generation that says nothing
about how it was entered was entered BEFORE the work was published, which is
what every record written without the group describes, so no pinned comment
has to be migrated to say it. What the group carries when it is there is what
a pre-publication entry has no need of and a post-publication one could never
re-derive -- the stage the gate took the issue out of, the pull request the
work already has, and the head that pull request was left standing on. All
three are frozen for the reason every other late field is: the branch moves,
the label the gate replaced is gone, and a reconciliation that re-read either
would act on whatever the issue has become since.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from orchestrator.git.measurement.models import MeasurementFailure
from orchestrator.workflow.late_split import formats as _formats
from orchestrator.workflow.state import (
    WorkflowLabel,
    publishes_onto_a_pull_request,
)

# How deep automatic splitting may go. The root issue of a lineage is depth 0,
# so a generation may only split while its own depth is strictly below this:
# the deepest child a split can create sits exactly at the bound and must
# resolve as one change or ask a human. It is a safety invariant, not a knob,
# which is why no configuration reads it.
MAX_LINEAGE_DEPTH = 3

# How long a resource target may be. It is never recorded -- only digested
# into an identifier -- but a ref, a branch, or an issue number that does not
# fit here is not one.
MAX_RESOURCE_TARGET = 512

# What a caller is told when it tries to update a ledger the write would not
# carry its update into. Spelled once because both transforms refuse alike.
_OPAQUE_LEDGER = "{0} cannot be updated while the ledger is opaque"


class LatePhase(StrEnum):
    """The reconciliation boundary a generation last reached.

    Each member names a step that persists before it acts, so a tick that
    crashed mid-step reads the phase back and reconciles the same step rather
    than starting a new one.
    """

    MEASURING = "measuring"
    HOLDING_PLAN_PR = "holding_plan_pr"
    ADJUDICATING = "adjudicating"
    OWNER_CHECK = "owner_check"
    SNAPSHOTTING = "snapshotting"
    SPLITTING = "splitting"
    SUPERSEDING = "superseding"
    CLEANING_UP = "cleaning_up"
    CANCELLING = "cancelling"
    RESTARTING = "restarting"


# The boundaries a split TRANSACTION owns. A record standing at one of them
# has begun creating children and may be mid-loop, and that is the only thing
# saying so in the window where nothing is recorded yet -- a child is created
# before the write that records it, so the ledger is empty and the phase is
# the whole evidence.
IN_FLIGHT_PHASES = frozenset((
    LatePhase.SNAPSHOTTING,
    LatePhase.SPLITTING,
    LatePhase.SUPERSEDING,
))

# The boundaries that come before a transaction. Every retry above one -- the
# hold reconciled on each tick, the spawn, the owner read a completion
# claims -- writes one of these, and writing it over an in-flight boundary is
# the rewind `at_phase` refuses.
_BEFORE_TRANSACTION = frozenset((
    LatePhase.MEASURING,
    LatePhase.HOLDING_PLAN_PR,
    LatePhase.ADJUDICATING,
    LatePhase.OWNER_CHECK,
))


class LateVerdict(StrEnum):
    """What one late adjudication decided about an oversized candidate."""

    SINGLE = "single"
    SPLIT = "split"
    QUESTION = "question"


class LateFailure(StrEnum):
    """The typed failures a late reconciliation records instead of guessing.

    None of them is "small": each names the step that could not be completed,
    so the retry that follows reconciles that step rather than re-running the
    agent whose work it was about to publish.
    """

    MEASUREMENT_FAILED = "measurement_failed"
    PLAN_PR_HOLD_FAILED = "plan_pr_hold_failed"
    OWNER_READ_FAILED = "owner_read_failed"
    PR_RECONCILE_FAILED = "pr_reconcile_failed"
    SNAPSHOT_FAILED = "snapshot_failed"
    CHILD_CREATE_FAILED = "child_create_failed"
    SUPERSESSION_FAILED = "supersession_failed"
    BRANCH_CLEANUP_FAILED = "branch_cleanup_failed"
    SNAPSHOT_DELETE_FAILED = "snapshot_delete_failed"
    RESTART_FAILED = "restart_failed"


class LateResourceKind(StrEnum):
    """What kind of external thing a ledger entry holds the generation to."""

    SNAPSHOT_REF = "snapshot_ref"
    BRANCH = "branch"
    PLAN_PR = "plan_pr"
    CHILD = "child"


class LateResourceState(StrEnum):
    """How far one recorded external obligation has been reconciled.

    `RETAINED` is not a failure: a snapshot whose direct consumers are still
    live is deliberately kept, and saying so is what keeps a retained ref
    apart from one whose deletion was refused.

    `RECLAIMING` is the decision, written before the delete that carries it
    out, so a tick that died between the delete landing and the record of it
    has something durable to come back to. It is not a pass on the proof: the
    consumers are read again on every visit that would delete, and one that
    came back keeps the ref with the entry left here. What the state buys is
    the retry of a delete that may already have happened -- a ref the remote
    no longer has is finished without re-proving anything, since what is left
    is the record and the receipts rather than the deletion. Every state but
    `RECONCILED` is still owed, so a record left here holds a terminal exactly
    as `RETAINED` does.
    """

    PENDING = "pending"
    RETAINED = "retained"
    RECLAIMING = "reclaiming"
    RECONCILED = "reconciled"
    FAILED = "failed"


@dataclass(frozen=True)
class LateResource:
    """One external resource this generation owes the remote.

    `target` is the resource's own identifier -- a ref, a branch, a pull
    request number, an issue number -- and is recorded so a reconciliation
    acts on the exact thing the generation created rather than on whatever
    currently looks like it.
    """

    kind: LateResourceKind
    target: str
    resource_state: LateResourceState = LateResourceState.PENDING


@dataclass(frozen=True)
class LateGeneration:
    """One late generation's whole durable record.

    An issue that never entered the late gate reads back as this record's
    defaults, which is what `is_present` answers on: the fields are additive,
    so a legacy pinned comment needs no migration and writing an absent
    generation back adds no key to it.

    The two `opaque_*` fields are the ledgers this binary could not fully
    type, kept verbatim rather than reduced to what it understood. An
    obligation dropped on read would be an obligation dropped on the next
    write, and a snapshot whose consumer ledger was silently emptied reads as
    one nobody is waiting on -- so what cannot be typed is carried through
    untouched and `has_opaque_ledger` says so out loud.

    `split_children` and `links_announced` are the split transaction's own
    receipts, and they live on the generation rather than beside the stage's
    shared keys precisely because they have to be scoped to ONE adjudication.
    The stage's `children` list belongs to whichever decomposition last wrote
    it -- an issue that was decomposed, saw its children resolve, and then
    implemented an oversized candidate still carries the old one -- so a
    transaction reading it would adopt completed issues by manifest index.
    `split_children` is ordered and positional for the same reason: entry `i`
    is the child that owns slice `i` of this manifest.

    `owner_check_pending` is the one field that records an unfinished READ
    rather than a fact about the candidate: a completed run whose owner could
    not be re-read leaves it set, and while it is set no later tick may treat
    this generation as settled, however small, decided, or parked it looks.
    It is durable because nothing else would bring the workflow back to that
    read -- a below-threshold revision and an issue parked for a human both
    stop the tick long before the guard would run again.

    `measurement_miss_count` and `measurement_failure` are the record of a
    reading that did NOT happen, and they are durable because nothing else
    remembers one: every tick is a fresh process, so a gate holding the count
    in memory would either re-read a permanently broken pair forever or spend
    a human on the first reading a fetch happened to interrupt. The count is
    how many consecutive readings this generation has lost and the failure is
    the step the last one stopped at, kept typed because the two answers are
    different next moves -- a base this clone does not hold is a fetch that
    brought nothing back, and a diff nothing here can pin is a checkout an
    operator has to clear first. Both are scoped to the pair frozen beside
    them: a fresh generation freezes a fresh pair, so its misses start at zero
    rather than inheriting a count taken over commits nobody measures any
    more.

    `plan_pr_number`, `plan_pr_head`, and `plan_pr_body` are one hold's whole
    record: the pull request a cycle-marked notice was written onto, the tip
    it was standing on when that happened, and the description the notice
    replaced. The `plan_pr` spelling is what live pinned comments carry, so it
    stays; what the group NAMES is whichever pull request the cycle holds --
    the plan one a discussion left standing where the generation was entered
    before publication, and the implementation one the work is already on
    where it was entered past it. The head is a reading rather than a claim:
    it says which change wore the notice, and it is not `published_sha` one
    field over, which is the tip the GATE was entered on and the evidence a
    settlement pins its push to. A hold reads the head it marks and never
    writes that one.

    `post_publication`, and the `source_stage`, `published_pr_number`, and
    `published_sha` beside it, are the only context saying a generation was
    entered on work the remote already has. A record carrying none of them was
    entered before publication, so a pinned comment written without the group
    answers the question without having been touched.
    `has_publication_context` is what a caller asks rather than the flag: the
    three fields are read as fail-closed as every other, a marker standing
    alone would claim a pull request nothing could name, and the stage is
    asked what it is rather than merely whether it is there -- only the five
    states that publish onto a pull request the remote already carries name
    an entry anything may be reconciled from.
    """

    cycle_id: int = 0
    generation: int = 0
    root_issue: int = 0
    current_issue: int = 0
    lineage_depth: int | None = None
    scope: str = ""
    candidate_sha: str = ""
    base_sha: str = ""
    threshold: int | None = None
    additions: int | None = None
    measurement_miss_count: int = 0
    measurement_failure: MeasurementFailure | None = None
    phase: LatePhase | None = None
    title_body_hash: str | None = None
    comment_hash: str | None = None
    comment_watermark_id: int | None = None
    plan_pr_number: int | None = None
    plan_pr_head: str = ""
    plan_pr_body: str | None = None
    post_publication: bool = False
    source_stage: WorkflowLabel | None = None
    published_pr_number: int | None = None
    published_sha: str = ""
    resources: tuple[LateResource, ...] = ()
    consumers: tuple[int, ...] = ()
    split_children: tuple[int, ...] = ()
    links_announced: bool = False
    opaque_resources: str | None = None
    opaque_consumers: str | None = None
    owner_check_pending: bool = False
    cancelled: bool = False
    cancelled_at: str | None = None
    cancelled_phase: LatePhase | None = None
    restart_pending: bool = False
    restart_target: str | None = None
    restart_cycle_id: int | None = None
    restart_predecessor: int | None = None

    @property
    def is_present(self) -> bool:
        """Whether a late cycle was ever recorded on this issue."""
        return self.cycle_id > 0

    @property
    def is_oversized(self) -> bool:
        """Whether the measurement is strictly past the threshold it named.

        Strictly: a candidate exactly at the configured value is accepted, so
        the trigger cannot move by one line when the threshold is retuned. An
        unmeasured generation is not oversized -- a missing measurement is a
        typed failure to reconcile, never a small candidate.
        """
        if self.threshold is None or self.additions is None:
            return False
        return self.additions > self.threshold

    @property
    def may_split(self) -> bool:
        """Whether this generation is allowed to create another one.

        Read fail-closed, so every depth that is not a real one below the
        bound refuses the split rather than unlocking a generation the cap
        exists to forbid: a depth at or past the bound, a negative one, one
        that is not a whole number at all, and an unknown one -- which is what
        a damaged or missing field on a recorded cycle reads back as -- all
        answer False.
        """
        if not _formats.whole_number(self.lineage_depth):
            return False
        return 0 <= self.lineage_depth < MAX_LINEAGE_DEPTH

    @property
    def has_opaque_ledger(self) -> bool:
        """Whether an external obligation here is one this binary cannot type.

        The one answer a reclamation may not read past: an unknown consumer or
        an unknown resource is still an obligation, so nothing may treat the
        cleanup as complete or the snapshot as reclaimable while this holds.
        """
        return (
            self.opaque_resources is not None
            or self.opaque_consumers is not None
        )

    @property
    def has_publication_context(self) -> bool:
        """Whether a post-publication entry carries what it is reconciled by.

        The flag is not that answer on its own. Every field beside it is read
        fail-closed, so a hand-edited or older pinned comment can leave the
        marker standing with the stage, the pull request, or the head it named
        gone -- and none of the three can be recovered from anywhere else: the
        label the adjudication runs under has replaced the one it came from by
        the time anything asks, the hold beside it names a pull request only
        because this group named one first, and the head is a commit the
        branch has already moved off. A group
        that cannot say all three says nothing an entry is reconciled from.

        The stage is asked what it IS as well as whether it is there, and by
        the same predicate the entry was frozen under: only the five states
        that push onto a pull request the remote already carries. A record
        naming any other -- `ready`, `blocked`, `umbrella`, or the
        `implementing` seam whose own push is what OPENS the pull request --
        describes a publication this workflow never enters one on, so reading
        it back as context would let a reconciliation measure and push a
        candidate no post-publication stage ever committed. Written that way
        it is refused; read back that way it is no context at all, which is
        the same answer a pre-publication record gives.
        """
        if not self.post_publication:
            return False
        if not publishes_onto_a_pull_request(self.source_stage):
            return False
        return bool(self.published_pr_number and self.published_sha)

    def with_resource(self, resource: LateResource) -> LateGeneration:
        """Return this record with one external obligation recorded.

        Keyed on kind and target, so a reconciliation that repeats after a
        crash updates the entry it already wrote instead of appending a second
        one -- the ledger stays as bounded as the resources actually created.

        Refused while the resource ledger is opaque. What gets written back
        then is the verbatim copy, so the update would be returned here and
        lost at the next write -- and merging into a ledger this binary could
        not read is exactly the rewrite the verbatim copy exists to prevent. A
        caller that reaches this has a ledger a human has to settle first.
        """
        if self.opaque_resources is not None:
            raise _formats.InvalidLateValue(_OPAQUE_LEDGER.format("resources"))
        kept = tuple(
            entry for entry in self.resources
            if (entry.kind, entry.target) != (resource.kind, resource.target)
        )
        return replace(self, resources=(*kept, resource))

    def with_consumers(self, numbers: tuple[int, ...]) -> LateGeneration:
        """Return this record with direct snapshot consumers recorded.

        Deduplicated and ordered, because the ledger is what a reclamation
        sweep walks: a child recorded twice would be asked about twice, and
        the order it was created in is not what decides anything.

        Only a positive whole number is an issue: converting anything else
        would put a consumer nobody can ask about into the one ledger that
        decides whether a snapshot may be reclaimed -- `True` is not issue 1,
        2.5 is not issue 2, and "7" is a string somebody hand-edited.

        Refused while the consumer ledger is opaque, for the reason
        `with_resource` is: the verbatim copy is what a write puts back, so an
        update accepted here would disappear at the next one.
        """
        if self.opaque_consumers is not None:
            raise _formats.InvalidLateValue(_OPAQUE_LEDGER.format("consumers"))
        for number in numbers:
            if not _formats.whole_number(number) or number <= 0:
                raise _formats.InvalidLateValue(
                    f"consumer is not an issue ({type(number).__name__})",
                )
        merged = set(self.consumers) | set(numbers)
        return replace(self, consumers=tuple(sorted(merged)))

    def with_split_children(self, numbers: tuple[int, ...]) -> LateGeneration:
        """Return this record with the ordered child register replaced.

        Replaced rather than merged, because the register is positional and a
        caller rebuilding it walks the whole manifest: merging would leave a
        stale tail behind whenever a re-run shortened it. Only positive whole
        numbers are children, for the reason the consumer ledger says so --
        a value nobody can ask GitHub about is not one to adopt by index.
        """
        for number in numbers:
            if not _formats.whole_number(number) or number <= 0:
                raise _formats.InvalidLateValue(
                    f"child is not an issue ({type(number).__name__})",
                )
        return replace(self, split_children=tuple(numbers))

    def with_publication(
        self, *, stage: str, pr_number: int, published_sha: str,
    ) -> LateGeneration:
        """Return this record entered on work a publication already carried.

        All three are proved here rather than left to the write, for the
        reason the exemption is proved where it is recorded: the pinned write
        drops what it cannot type, so a stage that is not a workflow state, a
        pull request that is not an identity, or a head that is not a whole
        object id would each leave the marker standing over a context nothing
        could reconcile -- and the reader on the far side would report a
        post-publication entry with no publication in it. A caller that cannot
        name all three has an entry this domain must not record as one.

        The stage is taken through the label vocabulary rather than kept as
        whatever was passed, for the reason a restart target is: what it names
        is the state a settled adjudication puts the issue back into, and a
        string nobody looked up would reach a later tick wearing this domain's
        word that the workflow has such a state.

        Being a state is not enough, and the same predicate the entry is
        frozen under is what says which: the five that push onto a pull
        request the remote already carries. `ready`, `blocked`, and `umbrella`
        each have an edge to the adjudication for reasons of their own and no
        pull request behind any of them, and `implementing`'s own push is the
        one that OPENS the pull request. Recorded from one of those, the group
        would send a later reconciliation to measure and push a candidate no
        post-publication stage ever committed.
        """
        if stage not in WorkflowLabel or not publishes_onto_a_pull_request(
            WorkflowLabel(stage),
        ):
            raise _formats.InvalidLateValue(
                "source stage is not one a publication is entered from "
                f"({type(stage).__name__})",
            )
        if not _formats.whole_number(pr_number) or pr_number <= 0:
            raise _formats.InvalidLateValue(
                "published PR is not an identity "
                f"({type(pr_number).__name__})",
            )
        if not _formats.is_hex_of(published_sha, _formats.COMMIT_LENGTHS):
            raise _formats.InvalidLateValue(
                "published head is not a commit "
                f"({type(published_sha).__name__})",
            )
        return replace(
            self,
            post_publication=True,
            source_stage=WorkflowLabel(stage),
            published_pr_number=pr_number,
            published_sha=published_sha,
        )

    def at_phase(self, phase: LatePhase) -> LateGeneration:
        """Return this record standing at one reconciliation boundary.

        Ordinarily whatever the step that reached it says. The one move
        refused is BACKWARDS out of a transaction that has begun, and it is
        refused here rather than at each caller because every retry ABOVE the
        transaction makes it: the hold is reconciled on every tick, a
        spawn names its own boundary, and each completion claims the owner
        read. Any of them writing its own phase over `splitting` would erase
        the only evidence there is in the window that matters -- a child is
        created before the write that records it, so a loop that died between
        the two leaves an empty ledger and a real issue on GitHub. What a
        later reclamation reads then is a cycle that never started a split,
        and the ref that half-created child is still cutting from is one it
        would delete.

        A cancellation is not a rewind and is not refused: `cancelling` comes
        after every boundary here, and `cancel` keeps the one it interrupted
        beside the stamp. Nor is a fresh generation, which starts over at
        `measuring` by advancing the counter rather than by moving this one.
        """
        if phase in _BEFORE_TRANSACTION and self.phase in IN_FLIGHT_PHASES:
            return self
        return replace(self, phase=phase)

    def cancel(self, stamp: str) -> LateGeneration:
        """Return this record marked cancelled, keeping the first stamp.

        Cancellation is irreversible within a cycle: once the owner has been
        observed closed, a later tick that observes it reopened re-runs this
        and must not move the moment the cleanup obligation was taken on.

        The boundary it was standing at is kept beside the stamp, because the
        `phase` field is about to name the cancellation itself and the answer
        it was carrying is one the reconciliation still needs: whether the
        consumer ledger accounts for every child cut from this generation's
        snapshot is read off the phase, and a record that forgot where it was
        cancelled from could never prove it again. Kept from the first marking
        for the same reason the stamp is -- a re-mark must not move it -- and
        a record whose first marking is the one being repeated answers with
        `cancelling`, which proves nothing and keeps the ref.
        """
        return replace(
            self,
            cancelled=True,
            cancelled_at=self.cancelled_at or stamp,
            cancelled_phase=self.cancelled_phase or self.phase,
        )
