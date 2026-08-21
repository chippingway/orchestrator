# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a consumer groups two late records on, and what it may not."""
from __future__ import annotations

import unittest
from types import MappingProxyType

from orchestrator.workflow.late_split import records as _records
from orchestrator.workflow.late_split.models import LateVerdict

from tests.workflow.late_split import generation_test_support as _support

_MEASUREMENT, _VERDICT = _support.family_cases()[:2]
_CLEANUP = _support.family_cases()[4]
_RESTART = _support.family_cases()[-1]
_CATEGORY = _support.CATEGORY
_IMPLEMENTING = "workflow:implementing"
# A pending restart, aimed at whichever state the current setting chose.
_PENDING_RESTART = MappingProxyType({
    "restart_pending": True,
    "restart_predecessor": _support.CYCLE_ID,
})
# One field's worth of difference, each the kind an analysis reads a record
# for: what it was measured against, and what the measurement said.
_MEASURED_APART = (
    {"base_sha": "f" * _support.SHA_LENGTH},
    {"threshold": _support.THRESHOLD + 1},
    {"additions": _support.ADDITIONS + 1},
)


def _keyed(event, generation_fields=None, **envelope) -> tuple:
    """The key a sink's record of this step would be grouped under."""
    payload = _records.build_late_payload(
        event, _support.measured_generation(**(generation_fields or {})),
    )
    return _records.correlation_key({
        "repo": _support.REPO,
        "issue": _support.CURRENT_ISSUE,
        "event": str(event.family),
        "stage": "decomposing",
        **payload,
        **envelope,
    })


def _record(event, **envelope) -> dict:
    """One record as a sink holds it: the envelope plus the bounded payload."""
    payload = _records.build_late_payload(
        event, _support.measured_generation(),
    )
    return {
        "repo": _support.REPO,
        "issue": _support.CURRENT_ISSUE,
        "event": str(event.family),
        **payload,
        **envelope,
    }


class CorrelationKeyTest(unittest.TestCase):
    """Duplicates collapse on the key; genuinely different steps do not."""

    def test_one_step_emitted_twice_has_one_key(self) -> None:
        # A crash between the record and the durable fact behind it repeats
        # the record; only the timestamp differs, and it is not in the key.
        first = _record(_MEASUREMENT, ts="2026-08-21T10:00:00+00:00")
        again = _record(_MEASUREMENT, ts="2026-08-21T10:30:00+00:00")
        self.assertEqual(
            _records.correlation_key(first), _records.correlation_key(again),
        )

    def test_different_families_keep_own_keys(self) -> None:
        keys = {
            _records.correlation_key(_record(event))
            for event in _support.family_cases()
        }
        self.assertEqual(len(keys), len(_support.family_cases()))

    def test_two_split_sizes_are_two_adjudications(self) -> None:
        # One candidate split into two children and into seven are different
        # outcomes of the same phase: a key blind to the count reports one.
        splits = tuple(
            _support.verdict_event(verdict=LateVerdict.SPLIT, child_count=count)
            for count in (_support.CHILD_COUNT, _support.OTHER_CHILD_COUNT)
        )
        self.assertNotEqual(
            _records.correlation_key(_record(splits[0])),
            _records.correlation_key(_record(splits[1])),
        )

    def test_two_categories_are_two_questions(self) -> None:
        asked = tuple(
            _support.verdict_event(
                verdict=LateVerdict.QUESTION, category=category,
            )
            for category in (_CATEGORY.SCOPE_AMBIGUOUS, _CATEGORY.UNSAFE_SPLIT)
        )
        self.assertNotEqual(
            _records.correlation_key(_record(asked[0])),
            _records.correlation_key(_record(asked[1])),
        )

    def test_one_verdict_retried_is_one_step(self) -> None:
        retried = _support.verdict_event(
            verdict=LateVerdict.SPLIT, child_count=_support.CHILD_COUNT,
        )
        self.assertEqual(
            _records.correlation_key(_record(_VERDICT)),
            _records.correlation_key(_record(retried)),
        )

class ResourceCorrelationTest(unittest.TestCase):
    """Which obligation a record was about is part of which step it was."""

    def test_two_resources_of_one_kind_are_two_steps(self) -> None:
        # The reason a record carries a resource print: cleaning up two
        # children reconciles two obligations, and a key that saw only the
        # kind and the outcome would report one of them.
        cleanups = tuple(
            _support.cleanup_event(resource)
            for resource in (_support.FIRST_CHILD, _support.SECOND_CHILD)
        )
        self.assertNotEqual(
            _records.correlation_key(_record(cleanups[0])),
            _records.correlation_key(_record(cleanups[1])),
        )

    def test_one_resource_retried_is_one_step(self) -> None:
        retried = _support.cleanup_event(_support.FIRST_CHILD)
        self.assertEqual(
            _records.correlation_key(_record(_CLEANUP)),
            _records.correlation_key(_record(retried)),
        )

    def test_two_outcomes_of_one_resource_differ(self) -> None:
        # A snapshot retained and the same snapshot reconciled are two facts
        # about one ref: collapsing them would hide the reclamation half.
        deleted = _support.cleanup_event(_support.RECLAIMED_SNAPSHOT)
        self.assertNotEqual(
            _records.correlation_key(_record(_support.family_cases()[3])),
            _records.correlation_key(_record(deleted)),
        )

class OutcomeFieldTest(unittest.TestCase):
    """Anything a record says differently is a different step it describes."""

    def test_two_restart_targets_are_two_restarts(self) -> None:
        # Which state an issue is being put back into is the outcome of the
        # restart, so two markers aimed at different ones are two steps.
        aimed = tuple(
            _keyed(_RESTART, {**_PENDING_RESTART, "restart_target": target})
            for target in (_support.DECOMPOSING, _IMPLEMENTING)
        )
        self.assertNotEqual(aimed[0], aimed[1])

    def test_two_measurements_apart_are_two_steps(self) -> None:
        # What a candidate was measured against, and what the measurement
        # said, are what a threshold study reads the record for.
        measured = _keyed(_MEASUREMENT)
        for apart in _MEASURED_APART:
            with self.subTest(field=sorted(apart)[0]):
                self.assertNotEqual(_keyed(_MEASUREMENT, apart), measured)

    def test_the_key_is_the_record_but_its_timestamp(self) -> None:
        # The rule the pairs above are cases of, and the one that survives the
        # payload growing a field nobody remembers to list.
        recorded = _record(_MEASUREMENT, ts="2026-08-21T10:00:00+00:00")
        keyed = set(_records.CORRELATION_FIELDS)
        self.assertEqual(set(recorded) - keyed, {"ts"})
        self.assertLessEqual(set(_records.LATE_PAYLOAD_FIELDS), keyed)


if __name__ == "__main__":
    unittest.main()
