# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a late generation record answers about itself, and how it changes."""
from __future__ import annotations

import unittest

from orchestrator import config
from orchestrator.workflow.late_split.formats import InvalidLateValue
from orchestrator.workflow.late_split.models import (
    MAX_LINEAGE_DEPTH,
    LateGeneration,
    LateResource,
    LateResourceKind,
    LateResourceState,
)

from tests.workflow.late_split import generation_test_support as _support

_BRANCH = "orchestrator/issue-1"
_OTHER_BRANCH = "orchestrator/issue-2"
_LATER_STAMP = "2026-08-21T11:00:00+00:00"


def _generation(**fields) -> LateGeneration:
    return LateGeneration(
        cycle_id=1, current_issue=_support.CURRENT_ISSUE, **fields,
    )


class PresenceTest(unittest.TestCase):
    """The cycle identity is what tells a late issue from a legacy one."""

    def test_default_record_is_absent(self) -> None:
        self.assertFalse(LateGeneration().is_present)

    def test_a_recorded_cycle_is_present(self) -> None:
        self.assertTrue(_generation().is_present)


class MeasurementTest(unittest.TestCase):
    """The gate trips strictly past the threshold it was measured against."""

    def test_threshold_comparison_is_strict(self) -> None:
        threshold = _support.THRESHOLD
        cases = (
            (threshold - 1, False), (threshold, False), (threshold + 1, True),
        )
        for additions, oversized in cases:
            with self.subTest(additions=additions):
                measured = _generation(threshold=threshold, additions=additions)
                self.assertEqual(measured.is_oversized, oversized)

    def test_the_configured_ceiling_is_a_ceiling(self) -> None:
        # `MAX_ADDED_LINES` is what an operator tunes and what a generation
        # records, and a candidate landing exactly on it publishes as one
        # change: the trigger is strictly past the value, so retuning the
        # setting cannot move it by a line.
        ceiling = config.MAX_ADDED_LINES
        for additions, oversized in ((ceiling, False), (ceiling + 1, True)):
            with self.subTest(additions=additions):
                measured = _generation(threshold=ceiling, additions=additions)
                self.assertEqual(measured.is_oversized, oversized)

    def test_an_unmeasured_candidate_is_not_oversized(self) -> None:
        # A missing measurement is a typed failure to reconcile, never a
        # small candidate that may publish.
        for fields in (
            {"threshold": _support.THRESHOLD},
            {"additions": _support.ADDITIONS},
            {},
        ):
            with self.subTest(fields=sorted(fields)):
                self.assertFalse(_generation(**fields).is_oversized)


class LineageBoundTest(unittest.TestCase):
    """Splitting stops at the bound, and reads fail closed outside it."""

    def test_depth_below_the_bound_may_split(self) -> None:
        for depth in range(MAX_LINEAGE_DEPTH):
            with self.subTest(depth=depth):
                self.assertTrue(_generation(lineage_depth=depth).may_split)

    def test_the_bound_and_beyond_may_not_split(self) -> None:
        # A hand-edited pinned comment is the reason the high case exists:
        # refusing is what the cap is for, and an absurd depth is not proof
        # that a fourth generation is safe. Neither is an unknown one -- a
        # lineage that cannot say how deep it is cannot show it has room, and
        # reading that as the root's 0 is exactly how a damaged field would
        # buy a generation past the bound.
        for depth in (MAX_LINEAGE_DEPTH, MAX_LINEAGE_DEPTH + 6, -1, None, 2.5):
            with self.subTest(depth=depth):
                self.assertFalse(_generation(lineage_depth=depth).may_split)


class ResourceLedgerTest(unittest.TestCase):
    """The ledger records one entry per resource, however often it is written."""

    def test_repeating_a_resource_updates_its_entry(self) -> None:
        pending = LateResource(
            kind=LateResourceKind.SNAPSHOT_REF, target=_support.SNAPSHOT_REF,
        )
        reconciled = LateResource(
            kind=LateResourceKind.SNAPSHOT_REF,
            target=_support.SNAPSHOT_REF,
            resource_state=LateResourceState.RECONCILED,
        )
        recorded = _generation().with_resource(pending).with_resource(reconciled)
        self.assertEqual(recorded.resources, (reconciled,))

    def test_a_different_target_is_its_own_entry(self) -> None:
        first = LateResource(
            kind=LateResourceKind.BRANCH, target=_BRANCH,
        )
        second = LateResource(
            kind=LateResourceKind.BRANCH, target=_OTHER_BRANCH,
        )
        recorded = _generation().with_resource(first).with_resource(second)
        self.assertEqual(recorded.resources, (first, second))

    def test_only_an_issue_number_is_a_consumer(self) -> None:
        # The ledger decides whether a snapshot may be reclaimed, so a value
        # nobody can ask GitHub about may not be converted into one.
        for damaged in (True, 2.5, "7", 0, -3):
            with self.subTest(damaged=damaged):
                with self.assertRaises(InvalidLateValue):
                    _generation().with_consumers((damaged,))

    def test_consumers_are_deduplicated_and_ordered(self) -> None:
        # The reclamation sweep walks this ledger, so a child recorded twice
        # would be asked about twice.
        recorded = _generation().with_consumers((7, 3)).with_consumers((3, 5))
        self.assertEqual(recorded.consumers, (3, 5, 7))


class OpaqueLedgerTest(unittest.TestCase):
    """An obligation this binary cannot type is one nothing may read past."""

    def test_a_typed_record_owes_nothing_opaque(self) -> None:
        self.assertFalse(_generation().has_opaque_ledger)

    def test_either_ledger_makes_the_record_opaque(self) -> None:
        for held in ("opaque_resources", "opaque_consumers"):
            with self.subTest(ledger=held):
                self.assertTrue(
                    _generation(**{held: "[1]"}).has_opaque_ledger,
                )


class CancellationTest(unittest.TestCase):
    """Cancellation is irreversible, and keeps the moment it was observed."""

    def test_a_second_cancel_keeps_the_first_stamp(self) -> None:
        cancelled = _generation().cancel(_support.CANCELLED_AT)
        again = cancelled.cancel(_LATER_STAMP)
        self.assertTrue(again.cancelled)
        self.assertEqual(again.cancelled_at, cancelled.cancelled_at)


if __name__ == "__main__":
    unittest.main()
