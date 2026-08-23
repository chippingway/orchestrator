# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a snapshot owner a human closed still owes, and who comes back for it.

An issue closed on `decomposing` or `umbrella` is outside every other pass, so
the cleanup sweep is the only thing that ever asks about its ledger again. The
real handler is driven in every case, because half of what is under test is
what the pass does NOT do: it never relabels, never activates, and never
spawns.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from orchestrator.git.snapshots import refs as _snapshot_refs
from orchestrator.workflow.late_split import lineage as _lineage, state as _late_state
from orchestrator.workflow.late_split.models import (
    LatePhase,
    LateResource,
    LateResourceKind,
    LateResourceState,
)
from orchestrator.workflow.stages.decomposition import late_sweep

from tests.workflow.fixtures import _PatchedWorkflowMixin
from tests.workflow.stages.decomposition.late_cleanup_support import (
    CHILD_NUMBER,
    DECOMPOSING,
    OwnerSeed,
    PARENT_NUMBER,
    RecordedDelete,
    SNAPSHOT_REF,
)
from tests.workflow.stages.decomposition.late_cleanup_support import (
    LABEL_BLOCKED,
    LABEL_DONE,
    LABEL_IN_REVIEW,
    LABEL_READY,
    STATE_FAILED,
    STATE_RECLAIMING,
    STATE_RECONCILED,
    STATE_RETAINED,
)
from tests.workflow.stages.decomposition.late_cleanup_support import (
    SUPERSEDED_BRANCH,
    UNRECORDED_CHILD,
    WORKFLOW_LOG,
    resource_states,
    seed_unrecorded_child,
    split_umbrella,
    walk_owner,
)
from tests.workflow.stages.decomposition.late_test_support import (
    CANDIDATE_SHA,
    CYCLE_ID,
    GENERATION_NUMBER,
    late_generation,
)

_WARNING = "WARNING"

_OPAQUE_RESOURCES = '[{"kind": "unknown-to-this-binary"}]'

_OPAQUE_CONSUMERS = '["?"]'

_DELETED = _snapshot_refs.SnapshotOutcome.DELETED

_ABSENT = _snapshot_refs.SnapshotOutcome.ABSENT

# The generation the consumer minted when it split in turn, and the child it
# is still holding that snapshot for.
_NESTED_REF = "refs/orchestrator/late-split/issue-411/cycle-3/gen-2"

_GRANDCHILD_NUMBER = 4111

_ANCESTRY_REF = "late_ancestry_snapshot_ref"


def sweep_with(case, seeded, outcome=_DELETED, **answers) -> RecordedDelete:
    """Run one cleanup sweep with the remote answering `outcome`."""
    deleted = RecordedDelete(outcome, **answers)
    with deleted.answering():
        walk_owner(case, seeded, late_sweep._handle_closed_owner_cleanup)
    return deleted


def _closed(
    owed: LateResourceState,
    snapshot: LateResourceState,
    *,
    child_label: str = LABEL_DONE,
    child_closed: bool = True,
    phase: LatePhase = LatePhase.CLEANING_UP,
):
    """A closed snapshot owner, and the consumer disposition under test."""
    return split_umbrella(
        owed,
        snapshot=snapshot,
        child_label=child_label,
        owner=OwnerSeed(
            label=DECOMPOSING,
            closed=True,
            child_closed=child_closed,
            phase=phase,
        ),
    )


def _seed_nested_generation(seeded) -> None:
    """Give the consumer a split of its own, still holding its own ref."""
    child = seeded.github.get_issue(CHILD_NUMBER)
    child_state = seeded.github.read_pinned_state(child)
    _late_state.write_late_generation(child_state, late_generation(
        threshold=None,
        additions=None,
        resources=(),
        current_issue=CHILD_NUMBER,
        generation=GENERATION_NUMBER + 1,
    ).with_consumers((_GRANDCHILD_NUMBER,)).with_resource(LateResource(
        kind=LateResourceKind.SNAPSHOT_REF,
        target=_NESTED_REF,
        resource_state=LateResourceState.RETAINED,
    )))
    seeded.github.seed_state(CHILD_NUMBER, **child_state.data)


class ClosedOwnerSweepTest(_PatchedWorkflowMixin, unittest.TestCase):
    """The ledger is settled; nothing else about the issue is touched."""

    def test_it_reclaims_what_a_closed_owner_left(self) -> None:
        # Both halves in one pass, and nothing else: the close is a human
        # decision, so no label is written, no comment is posted on the owner,
        # and the consumer is read but never activated.
        seeded = _closed(
            LateResourceState.PENDING, LateResourceState.RETAINED,
        )
        github = seeded.github

        deleted = sweep_with(self, seeded, _DELETED)

        self.assertEqual(deleted.refs, [SNAPSHOT_REF])
        self.assertEqual(deleted.shas, [CANDIDATE_SHA])
        self.assertEqual(github.deleted_remote_branches, [SUPERSEDED_BRANCH])
        self.assertEqual(
            resource_states(github),
            {
                SUPERSEDED_BRANCH: STATE_RECONCILED,
                SNAPSHOT_REF: STATE_RECONCILED,
            },
        )
        self.assertEqual(github.label_history, [])
        self.assertEqual(
            [number for number, _ in github.posted_comments], [CHILD_NUMBER],
        )

    def test_a_close_is_read_anew_every_pass(self) -> None:
        # The label a running child wears is not terminal, so a manual close
        # is the whole answer -- and it is not latched. The same ledger with
        # the same consumer reopened keeps the ref, because what decides is
        # the reading taken on the visit that would delete it.
        for child_closed, asked in ((True, [SNAPSHOT_REF]), (False, [])):
            with self.subTest(child_closed=child_closed):
                seeded = _closed(
                    LateResourceState.RECONCILED,
                    LateResourceState.RETAINED,
                    child_label=LABEL_IN_REVIEW,
                    child_closed=child_closed,
                )

                deleted = sweep_with(self, seeded, _DELETED)

                self.assertEqual(deleted.refs, asked)

    def test_a_nested_child_that_published_counts(self) -> None:
        # The consumer split again and is still holding a snapshot of its own
        # for a grandchild nothing here can see. It reached `done` only by
        # publishing, which is what proves its whole subtree is past needing
        # the ANCESTOR ref -- so this owner reclaims its own and leaves the
        # nested ledger exactly where it found it.
        seeded = _closed(
            LateResourceState.RECONCILED, LateResourceState.RETAINED,
        )
        _seed_nested_generation(seeded)

        deleted = sweep_with(self, seeded, _DELETED)

        self.assertEqual(deleted.refs, [SNAPSHOT_REF])
        self.assertEqual(
            {
                entry["target"]: entry["state"]
                for entry in
                seeded.github.pinned_data(CHILD_NUMBER)["late_resources"]
            },
            {_NESTED_REF: STATE_RETAINED},
        )

    def test_an_unreadable_consumer_owes_the_ref(self) -> None:
        # Fail per consumer, not per pass: the ref stays because nothing
        # proved the consumer done, while the branch -- which owes no consumer
        # anything -- is reclaimed on this very visit.
        seeded = _closed(
            LateResourceState.PENDING, LateResourceState.RETAINED,
        )
        seeded.github.get_issue = MagicMock(side_effect=RuntimeError("boom"))

        with self.assertLogs(WORKFLOW_LOG, level="ERROR"):
            deleted = sweep_with(self, seeded, _DELETED)

        self.assertEqual(deleted.refs, [])
        self.assertEqual(
            resource_states(seeded.github),
            {
                SUPERSEDED_BRANCH: STATE_RECONCILED,
                SNAPSHOT_REF: STATE_RETAINED,
            },
        )

    def test_a_reclaimed_ref_tells_its_consumer(self) -> None:
        # The sweep is the only pass that revisits a closed owner, so it is
        # also the only thing that can tell the children the ref they were cut
        # from is gone. They are told as part of the reclamation, not on some
        # later visit that may never come -- and told by a comment, since this
        # owner may not write a consumer's pinned state at all.
        seeded = _closed(
            LateResourceState.RECONCILED, LateResourceState.RETAINED,
        )

        sweep_with(self, seeded, _DELETED)

        self.assertEqual(
            [number for number, _ in seeded.github.posted_comments],
            [CHILD_NUMBER],
        )
        self.assertEqual(
            seeded.github.pinned_data(CHILD_NUMBER)[_ANCESTRY_REF],
            SNAPSHOT_REF,
        )

    def test_a_refused_delete_is_asked_again(self) -> None:
        # A permission or ruleset problem an operator has to see: the entry
        # reads `failed`, the typed failure reaches the sinks, and the next
        # sweep retries the same ref rather than writing it off.
        seeded = _closed(
            LateResourceState.RECONCILED, LateResourceState.RETAINED,
        )

        with self.assertLogs(WORKFLOW_LOG, level=_WARNING):
            sweep_with(self, seeded, _snapshot_refs.SnapshotOutcome.REFUSED)

        self.assertEqual(
            resource_states(seeded.github)[SNAPSHOT_REF], STATE_FAILED,
        )
        reported = [
            event for event in seeded.github.recorded_events
            if event.get("failure") == "snapshot_delete_failed"
        ]
        self.assertEqual(len(reported), 1)
        # Read off the issue rather than named by the caller, so a record says
        # where the reclamation happened -- here the state this owner was
        # closed on, not the umbrella terminal the other entry runs from.
        self.assertEqual(reported[0]["stage"], "decomposing")

        retried = sweep_with(self, seeded, _DELETED)

        self.assertEqual(retried.refs, [SNAPSHOT_REF])
        self.assertEqual(
            resource_states(seeded.github)[SNAPSHOT_REF], STATE_RECONCILED,
        )


class WholeLedgerTest(_PatchedWorkflowMixin, unittest.TestCase):
    """Whether the ledger names every child cut from the ref, before who ended.

    The sweep is the only thing that ever looks at a closed owner again, so
    both answers are final. An empty list read as a gap left a ref nothing
    would ever reclaim; a list read as complete while the split was still
    filling it would take one out from under a child nobody had recorded yet.
    The record's own phase is what tells the two apart.
    """

    def test_a_ref_nothing_was_cut_from_is_reclaimed(self) -> None:
        seeded = self._orphan(LatePhase.SNAPSHOTTING)

        deleted = self._swept(seeded)

        self.assertEqual(deleted.refs, [SNAPSHOT_REF])
        self.assertEqual(self._ref_state(seeded.github), STATE_RECONCILED)

    def test_it_settles_the_owner_for_good(self) -> None:
        # What being stuck cost: the sweep came back on every cadence with a
        # ref it would never take. Once the entry reconciles there is nothing
        # left to ask about -- and nobody was told, because there is nobody.
        seeded = self._orphan(LatePhase.SNAPSHOTTING)
        self._swept(seeded)
        settled = seeded.github.write_state_calls

        again = self._swept(seeded)

        self.assertEqual(again.refs, [])
        self.assertEqual(seeded.github.write_state_calls, settled)
        self.assertEqual(seeded.github.posted_comments, [])
        self.assertEqual(seeded.github.label_history, [])

    def test_a_ledger_the_split_may_lead_is_kept(self) -> None:
        # Past the write that goes down before the first create, the same
        # empty list may be one write behind a child already on GitHub.
        seeded = self._orphan(LatePhase.SPLITTING)

        deleted = self._swept(seeded)

        self.assertEqual(deleted.refs, [])
        self.assertEqual(self._ref_state(seeded.github), STATE_RETAINED)

    def test_a_part_written_ledger_is_kept(self) -> None:
        # The same window with the list NOT empty, which is the shape that
        # looks provable and is not: the split recorded its first child, died
        # before recording its second, and the owner and the first child have
        # both closed since. Every consumer the ledger names has ended, so a
        # proof walking that list alone would take the ref -- out from under a
        # child it never read, never told, and could still be resumed.
        seeded = _closed(
            LateResourceState.RECONCILED,
            LateResourceState.RETAINED,
            phase=LatePhase.SPLITTING,
        )
        seed_unrecorded_child(seeded.github)

        deleted = self._swept(seeded)

        self.assertEqual(deleted.refs, [])
        self.assertEqual(self._ref_state(seeded.github), STATE_RETAINED)
        self.assertEqual(seeded.github.posted_comments, [])
        self.assertFalse(seeded.github.get_issue(UNRECORDED_CHILD).closed)

    def _orphan(self, phase: LatePhase):
        """A closed owner holding a ref, with no child recorded or made."""
        return split_umbrella(
            LateResourceState.RECONCILED,
            snapshot=LateResourceState.RETAINED,
            owner=OwnerSeed(
                label=DECOMPOSING, closed=True, child=False, phase=phase,
            ),
        )

    def _swept(self, seeded) -> RecordedDelete:
        """One sweep, with the remote taking whatever it is asked for."""
        return sweep_with(self, seeded)

    def _ref_state(self, github) -> str:
        """What the owner's ledger now says about the one ref it held."""
        return resource_states(github)[SNAPSHOT_REF]


class UnfinishedReleaseTest(_PatchedWorkflowMixin, unittest.TestCase):
    """A ref that went and a child that was not told is not a settled owner.

    The sweep is the only pass that comes back to a closed owner, so an entry
    that reconciles is an entry nothing revisits. It may only do that once
    every child cut from the ref has been reached.
    """

    def test_an_unreachable_child_owes_the_release(self) -> None:
        # The delete landed and one child could not be reached to be told.
        # The entry stays `reclaiming` rather than reconciling, because
        # reconciling is what stops the sweep coming back -- and this owner is
        # the only thing that would ever come back.
        seeded = _closed(
            LateResourceState.RECONCILED, LateResourceState.RECLAIMING,
        )
        seeded.github.get_issue = MagicMock(side_effect=RuntimeError("boom"))

        with self.assertLogs(WORKFLOW_LOG, level=_WARNING):
            deleted = self._sweep(seeded, _ABSENT)

        self.assertEqual(deleted.refs, [SNAPSHOT_REF])
        self.assertEqual(
            resource_states(seeded.github)[SNAPSHOT_REF], STATE_RECLAIMING,
        )

    def test_a_child_of_any_label_is_told(self) -> None:
        # The two pre-PR states a human can close an issue on are swept by
        # nothing, so a consumer left on one never becomes terminal. It is
        # still ended -- so the ref goes -- and it is still told, because the
        # receipt is a comment rather than anything a label could gate.
        for child_label in (LABEL_READY, LABEL_BLOCKED, LABEL_IN_REVIEW):
            with self.subTest(child_label=child_label):
                seeded = _closed(
                    LateResourceState.RECONCILED,
                    LateResourceState.RETAINED,
                    child_label=child_label,
                )

                deleted = self._sweep(seeded)

                self.assertEqual(deleted.refs, [SNAPSHOT_REF])
                self.assertEqual(
                    resource_states(seeded.github)[SNAPSHOT_REF],
                    STATE_RECONCILED,
                )
                self.assertEqual(
                    [
                        number
                        for number, _ in seeded.github.posted_comments
                    ],
                    [CHILD_NUMBER],
                )

    def test_a_reachable_child_finishes_the_release(self) -> None:
        # The visit after it. The ref is gone, so the entry is asked about
        # again on the strength of the decision alone, and the receipt it
        # could not deliver is what the pass is now for.
        seeded = _closed(
            LateResourceState.RECONCILED, LateResourceState.RECLAIMING,
        )

        self._sweep(seeded, _ABSENT)

        self.assertEqual(
            resource_states(seeded.github)[SNAPSHOT_REF], STATE_RECONCILED,
        )
        self.assertEqual(
            [number for number, _ in seeded.github.posted_comments],
            [CHILD_NUMBER],
        )

    def test_a_receipt_it_already_left_stands(self) -> None:
        # The crash between the receipt and the record of it. The retry
        # re-enters through `reclaiming`, finds the ref gone, and reaches the
        # release again -- where the thread, not the ledger, is what says the
        # child has already been told.
        seeded = _closed(
            LateResourceState.RECONCILED, LateResourceState.RECLAIMING,
        )
        seeded.github.comment(
            seeded.github.get_issue(CHILD_NUMBER),
            _lineage.release_marker(
                owner=PARENT_NUMBER,
                cycle=CYCLE_ID,
                generation=GENERATION_NUMBER,
            ),
        )

        self._sweep(seeded, _ABSENT)

        self.assertEqual(
            resource_states(seeded.github)[SNAPSHOT_REF], STATE_RECONCILED,
        )
        self.assertEqual(len(seeded.github.posted_comments), 1)

    def _sweep(self, seeded, outcome=_DELETED) -> RecordedDelete:
        """Sweep this owner, with the read-only ask agreeing with `outcome`."""
        return sweep_with(self, seeded, outcome, presence=outcome)


class SpentLedgerTest(_PatchedWorkflowMixin, unittest.TestCase):
    """A sweep costs what is left to settle, and nothing when that is none.

    The pass runs on every closed owner on the two cleanup labels, for as long
    as they carry one, so what it spends on an owner with nothing left to do
    is what decides whether the sweep is affordable at all.
    """

    def test_a_settled_ledger_reads_no_consumer(self) -> None:
        seeded = split_umbrella(
            LateResourceState.RECONCILED,
            owner=OwnerSeed(label=DECOMPOSING, closed=True),
        )

        self._asks_nothing(seeded)

        self.assertEqual(seeded.github.write_state_calls, 0)

    def test_an_opaque_ledger_stops_the_pass(self) -> None:
        # An entry this binary cannot type is an obligation too, so nothing on
        # the ledger may be reclaimed around it -- which makes every reading
        # this pass could take one it may not act on.
        seeded = _closed(
            LateResourceState.PENDING, LateResourceState.RETAINED,
        )
        github = seeded.github
        github.seed_state(
            PARENT_NUMBER,
            **{
                **github.pinned_data(PARENT_NUMBER),
                "late_resources": _OPAQUE_RESOURCES,
            },
        )
        with self.assertLogs(WORKFLOW_LOG, level=_WARNING):
            self._asks_nothing(seeded)

        self.assertEqual(github.deleted_remote_branches, [])

    def test_an_opaque_consumer_list_frees_the_branch(self) -> None:
        # The two ledgers stop different things, and a sweep that folded them
        # together would stop coming back for a branch because somebody
        # hand-edited a list of issue numbers.
        seeded = _closed(
            LateResourceState.PENDING, LateResourceState.RETAINED,
        )
        github = seeded.github
        github.seed_state(
            PARENT_NUMBER,
            **{
                **github.pinned_data(PARENT_NUMBER),
                "late_consumers": _OPAQUE_CONSUMERS,
            },
        )

        deleted = sweep_with(self, seeded)

        self.assertEqual(
            github.deleted_remote_branches, [SUPERSEDED_BRANCH],
        )
        self.assertEqual(deleted.refs, [])
        self.assertEqual(
            resource_states(github),
            {
                SUPERSEDED_BRANCH: STATE_RECONCILED,
                SNAPSHOT_REF: STATE_RETAINED,
            },
        )

    def _asks_nothing(self, seeded) -> None:
        """Sweep an owner that must cost neither a read nor a delete."""
        seeded.github.get_issue = MagicMock(side_effect=AssertionError)

        deleted = sweep_with(self, seeded, _DELETED)

        self.assertEqual(deleted.refs, [])


if __name__ == "__main__":
    unittest.main()
