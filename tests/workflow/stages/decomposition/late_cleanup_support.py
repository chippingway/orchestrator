# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""One umbrella made by a split, and what it still owes a remote.

Shared by the three modules that ask about it, because they ask about the same
issue from three ends: what a branch obligation costs the terminal, when the
snapshot it is holding may finally go, and what is left to settle once a human
has closed the owner mid-cycle. Every one of them drives the real handler,
since what is under test is exactly the routing -- an issue that has become an
umbrella never reaches the transaction again, and a closed one is never
dispatched to the stage its label names.
"""
from __future__ import annotations

from dataclasses import dataclass

from orchestrator.workflow.late_split import lineage as _lineage
from orchestrator.workflow.late_split import state as _late_state
from orchestrator.workflow.late_split.models import (
    LatePhase,
    LateResource,
    LateResourceKind,
    LateResourceState,
)
from orchestrator.workflow.stages.decomposition import umbrella as _umbrella
from orchestrator.workflow.stages.decomposition.models import _ChildScan

from tests.support.fakes import FakeGitHubClient, make_issue
from tests.workflow.fixtures import _TEST_SPEC, _agent
from tests.workflow.stages.decomposition.late_seam_support import (
    LocalTeardown,
    RecordedDelete as RecordedDelete,
    local_teardown,
)
from tests.workflow.stages.decomposition.late_test_support import (
    CANDIDATE_SHA,
    CYCLE_ID,
    GENERATION_NUMBER,
    LINEAGE_DEPTH,
    ROOT_ISSUE,
    late_generation,
)

UMBRELLA = "workflow:umbrella"

DECOMPOSING = "workflow:decomposing"

LABEL_DONE = "done"

LABEL_REJECTED = "rejected"

LABEL_IN_REVIEW = "workflow:in_review"

LABEL_READY = "workflow:ready"

LABEL_BLOCKED = "workflow:blocked"

PARENT_NUMBER = 41

CHILD_NUMBER = 411

# The second slice's child: created on GitHub and never recorded, which is
# what the crash between the two writes leaves behind.
UNRECORDED_CHILD = 412

SUPERSEDED_BRANCH = "orchestrator/geserdugarov__agent-orchestrator/issue-41"

SNAPSHOT_REF = "refs/orchestrator/late-split/issue-41/cycle-3/gen-1"

STATE_RECONCILED = "reconciled"

STATE_FAILED = "failed"

STATE_RETAINED = "retained"

STATE_RECLAIMING = "reclaiming"

EVENT_LATE_CLEANUP = "late_cleanup"

RESOLVED_STAMP = "umbrella_resolved_at"

WORKFLOW_LOG = "orchestrator.workflow"


@dataclass(frozen=True)
class OwnerSeed:
    """Which owner a case is about, and how its one consumer stands.

    The defaults are the umbrella the terminal reaches: open, on `umbrella`,
    with a child that ended -- which means closed, because every disposition
    that ends a child closes it as it fires. A case says otherwise when it is
    about a closed owner (swept under either cleanup label) or about a
    consumer a human reopened, which is the state no label records and the one
    the reclamation rule reads.

    `child_ref` is the snapshot the consumer's own ancestry names, which is
    what decides whether this owner may speak for it: a child pointed at a
    sibling generation's ref belongs to that generation. `child_ancestry` is
    False for the crash window the split leaves when it records a child and
    then cannot seed it: the body still carries the marker the create stamped
    into it, and the pinned comment carries nothing.

    `child` is False for the interval BEFORE that: the ref is preserved and
    proved ahead of the first child issue, so an owner closed in there records
    a snapshot and no consumers at all.

    `child_mirror_first` is the ordering claim the split stamps onto every
    pointer it writes -- that the reclamation which can take this ref drops
    this host's copy of it first. False is a pointer written by an
    orchestrator that took the remote first and the mirror afterwards, which
    is what a repository upgraded mid-lineage still carries.

    `phase` defaults to what a finished split leaves, which is what every
    umbrella and every closed owner past its transaction really carries: the
    children are all created and all recorded, so the consumer ledger is the
    whole account of who was cut from the ref. A case about a split still IN
    its loop says `splitting` -- there the list may be short by a child that
    already exists, and nothing on the ref may be reclaimed.
    """

    label: str = UMBRELLA
    closed: bool = False
    child: bool = True
    child_closed: bool = True
    child_ref: str = SNAPSHOT_REF
    child_ancestry: bool = True
    child_mirror_first: bool = True
    phase: LatePhase = LatePhase.CLEANING_UP

    def seed_child(self, github: FakeGitHubClient, child_label: str) -> None:
        """Add the one consumer, with the ancestry a split writes on it.

        Always an ancestry, because a split always writes one: it is the
        record that says which generation this child was cut from and which
        ref it may reuse, and a reclamation reads it to decide whom it may
        speak for.
        """
        if not self.child:
            return
        child = make_issue(
            CHILD_NUMBER,
            label=child_label,
            closed=self.child_closed,
            body="\n\n".join((
                "the slice this child owns",
                _lineage.child_marker(
                    issue=PARENT_NUMBER,
                    cycle=CYCLE_ID,
                    generation=GENERATION_NUMBER,
                    index=0,
                ),
            )),
        )
        github.add_issue(child)
        if not self.child_ancestry:
            return
        recorded = github.read_pinned_state(child)
        _lineage.write_late_ancestry(recorded, _lineage.LateAncestry(
            root_issue=ROOT_ISSUE,
            lineage_depth=LINEAGE_DEPTH + 1,
            parent_issue=PARENT_NUMBER,
            cycle_id=CYCLE_ID,
            generation=GENERATION_NUMBER,
            snapshot_ref=self.child_ref,
            snapshot_sha=CANDIDATE_SHA,
            mirror_first=self.child_mirror_first,
            scope="the slice this child owns",
        ))
        github.seed_state(CHILD_NUMBER, **recorded.data)


@dataclass(frozen=True)
class SeededUmbrella:
    """The parent one case walks, and the client it lives on."""

    github: FakeGitHubClient
    parent: object


def split_umbrella(
    owed: LateResourceState,
    *,
    snapshot: LateResourceState | None = None,
    child_label: str = LABEL_DONE,
    branch: str = SUPERSEDED_BRANCH,
    owner: OwnerSeed | None = None,
) -> SeededUmbrella:
    """An umbrella whose children are done and whose remote is still owed."""
    seed = owner or OwnerSeed()
    github = FakeGitHubClient()
    parent = make_issue(PARENT_NUMBER, label=seed.label, closed=seed.closed)
    github.add_issue(parent)
    seed.seed_child(github, child_label)
    settled = late_generation(
        threshold=None, additions=None, resources=(), phase=seed.phase,
    ).with_consumers(
        (CHILD_NUMBER,) if seed.child else (),
    ).with_resource(LateResource(
        kind=LateResourceKind.BRANCH,
        target=branch,
        resource_state=owed,
    ))
    if snapshot is not None:
        settled = settled.with_resource(LateResource(
            kind=LateResourceKind.SNAPSHOT_REF,
            target=SNAPSHOT_REF,
            resource_state=snapshot,
        ))
    recorded = github.read_pinned_state(parent)
    _late_state.write_late_generation(recorded, settled)
    github.seed_state(
        PARENT_NUMBER,
        children=[CHILD_NUMBER] if seed.child else [],
        umbrella=True,
        **recorded.data,
    )
    return SeededUmbrella(github=github, parent=parent)


def walk_owner(
    case,
    seeded: SeededUmbrella,
    tick=_umbrella._handle_umbrella,
    *,
    local_gone: bool = True,
) -> LocalTeardown:
    """Run one tick over this owner through the real handler that answers it.

    The umbrella's own poll by default, and the cleanup sweep where a case is
    about a closed owner -- the two entries into the same reclamation.

    The local teardown it held is handed back, because what a reclamation
    asked of the checkout is not something the ledger records: an entry reads
    `failed` whether the local half ran and did not finish or was never
    attempted at all.
    """
    with local_teardown(local_gone=local_gone) as teardown:
        case._run(
            lambda: tick(seeded.github, _TEST_SPEC, seeded.parent),
            run_agent=_agent(),
        )
        return teardown


def resource_states(github: FakeGitHubClient) -> dict:
    """The obligations the parent records, by target."""
    return {
        entry["target"]: entry["state"]
        for entry in github.pinned_data(PARENT_NUMBER).get("late_resources")
        or []
    }


def seed_unrecorded_child(github: FakeGitHubClient) -> None:
    """Add a child of this split that its parent's ledger never took.

    The split opens a child issue and records it in two writes -- it must,
    since a child on GitHub the parent does not record is a child nothing
    would come back to -- so a tick that died between them leaves exactly
    this: an issue carrying the marker the create stamped into its body, and
    a parent whose consumer list stops one short of it.
    """
    github.add_issue(make_issue(
        UNRECORDED_CHILD,
        label=LABEL_BLOCKED,
        body="\n\n".join((
            "the slice nobody recorded",
            _lineage.child_marker(
                issue=PARENT_NUMBER,
                cycle=CYCLE_ID,
                generation=GENERATION_NUMBER,
                index=1,
            ),
        )),
    ))


def scan_of(label, *, closed: bool = False) -> _ChildScan:
    """The umbrella's own child scan, reporting one child this way."""
    child = make_issue(CHILD_NUMBER, label=label)
    child.closed = closed
    return _ChildScan(
        children=[CHILD_NUMBER],
        issues={CHILD_NUMBER: child},
        labels={CHILD_NUMBER: label},
    )
