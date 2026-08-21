# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a late record may carry, and what each family has to say in it."""
from __future__ import annotations

import unittest

from orchestrator.workflow.late_split import records as _records
from orchestrator.workflow.late_split import formats as _formats
from orchestrator.workflow.late_split.models import LateGeneration, LateVerdict

from tests.workflow.late_split import generation_test_support as _support

_PREDECESSOR = 1
_REFUSED = _formats.InvalidLateValue
_MEASUREMENT, _VERDICT = _support.family_cases()[:2]
_CLEANUP = _support.family_cases()[4]
_CATEGORY = _support.CATEGORY
# What a generation must never carry into a record: prose, a path, a quoted
# secret -- offered through the fields that are typed only by annotation.
_PROSE = "rationale: inspect /srv/private/key before splitting"
# What a measurement and the verdict answering it are read for, one field at a
# time, and a generation that has let all of it go.
_MEASURED_CASES = tuple(
    (event, name)
    for event in _support.family_cases()[:2]
    for name in ("candidate_sha", "base_sha", "threshold", "additions", "phase")
)
_STRIPPED = _support.measured_generation(
    candidate_sha="", base_sha="", threshold=None, additions=None, phase=None,
)


def _payload(event, **generation_fields) -> dict:
    return _records.build_late_payload(
        event, _support.measured_generation(**generation_fields),
    )


def _refusal(**generation_fields) -> str:
    """What the boundary said when it refused a generation."""
    try:
        _payload(_MEASUREMENT, **generation_fields)
    except _REFUSED as refused:
        return str(refused)
    raise AssertionError("the record was not refused")


class BoundedRecordTest(unittest.TestCase):
    """A record carries correlation and nothing a reader could not publish."""

    def test_no_family_writes_an_unlisted_field(self) -> None:
        for event in _support.family_cases():
            with self.subTest(family=str(event.family)):
                self.assertLessEqual(
                    set(_payload(event)),
                    set(_records.LATE_PAYLOAD_FIELDS),
                )

    def test_every_correlation_field_is_carried(self) -> None:
        # Every field a join needs is on the record itself, so an analysis
        # never has to read the pinned comment back to interpret one.
        self.assertEqual(
            _payload(_MEASUREMENT),
            {
                "cycle_id": _support.CYCLE_ID,
                "generation": _support.GENERATION_NUMBER,
                "root_issue": _support.ROOT_ISSUE,
                "lineage_depth": _support.LINEAGE_DEPTH,
                "source_sha": _support.CANDIDATE_SHA,
                "base_sha": _support.BASE_SHA,
                "threshold": _support.THRESHOLD,
                "additions": _support.ADDITIONS,
                "phase": "adjudicating",
            },
        )

    def test_an_unknown_depth_is_absent_not_a_root(self) -> None:
        # A record may not report a lineage depth the pinned state could not
        # say, least of all the root's 0.
        self.assertNotIn(
            "lineage_depth", _payload(_MEASUREMENT, lineage_depth=None),
        )

    def test_a_family_carries_only_its_extras(self) -> None:
        recorded = _payload(_VERDICT)
        self.assertEqual(recorded["verdict"], str(LateVerdict.SPLIT))
        self.assertEqual(recorded["child_count"], _support.CHILD_COUNT)
        self.assertNotIn("failure", recorded)
        self.assertNotIn("verdict", _payload(_CLEANUP))

    def test_a_resource_is_kind_and_print_only(self) -> None:
        # The ledger's own target -- a ref, a branch, an issue number -- is
        # not something a record may carry, so what identifies it is a
        # bounded digest and the kind beside it.
        recorded = _payload(_CLEANUP)
        self.assertEqual(recorded["resource"], "child")
        self.assertEqual(recorded["outcome"], "reconciled")
        self.assertNotIn(
            _support.FIRST_CHILD.target, str(tuple(recorded.values())),
        )
        self.assertEqual(
            len(recorded["resource_id"]),
            _support.RESOURCE_PRINT_LENGTH,
        )

    def test_a_restart_names_its_step_and_predecessor(self) -> None:
        restarting = {
            "restart_pending": True,
            "restart_target": _support.DECOMPOSING,
            "restart_predecessor": _PREDECESSOR,
        }
        payload = _payload(_support.family_cases()[-1], **restarting)
        self.assertEqual(payload["restart_step"], "pending")
        self.assertEqual(payload["restart_target"], _support.DECOMPOSING)
        self.assertEqual(payload["predecessor_cycle_id"], _PREDECESSOR)


class RefusedRecordTest(unittest.TestCase):
    """A generation that cannot satisfy the contract produces no record."""

    def test_a_generation_with_no_identity_is_refused(self) -> None:
        # Nothing could join it to a pinned generation, a lineage, or its own
        # retry, which is the only reason the record exists.
        with self.assertRaises(_REFUSED):
            _records.build_late_payload(_MEASUREMENT, LateGeneration())

    def test_prose_in_a_commit_field_is_refused(self) -> None:
        # Both directions of the same adversary: the fields are typed `str`,
        # so only the format check keeps a sentence -- and the path inside it
        # -- out of a field an analysis reads as a commit.
        for sha_field in ("candidate_sha", "base_sha"):
            with self.subTest(field=sha_field):
                with self.assertRaises(_REFUSED):
                    _payload(_MEASUREMENT, **{sha_field: _PROSE})

    def test_a_phase_that_is_not_a_member_is_refused(self) -> None:
        with self.assertRaises(_REFUSED):
            _payload(_MEASUREMENT, phase=_PROSE)

    def test_a_restart_target_outside_the_pair(self) -> None:
        with self.assertRaises(_REFUSED):
            _payload(_MEASUREMENT, restart_target="workflow:done")

    def test_a_count_that_is_not_a_count_is_refused(self) -> None:
        for counted in (True, 2.5, "4000", -1):
            with self.subTest(counted=counted):
                with self.assertRaises(_REFUSED):
                    _payload(_MEASUREMENT, threshold=counted)

    def test_a_depth_past_the_bound_is_refused(self) -> None:
        with self.assertRaises(_REFUSED):
            _payload(_MEASUREMENT, lineage_depth=9)

    def test_the_refusal_never_quotes_the_value(self) -> None:
        # A field refused for carrying prose must not put that prose in the
        # log line reporting it -- that is the same leak one level over.
        self.assertNotIn(_PROSE, _refusal(candidate_sha=_PROSE))


class FamilyContextTest(unittest.TestCase):
    """A record is readable without the pinned comment its family answers for."""

    def test_a_sized_family_must_say_what_it_measured(self) -> None:
        # A measurement or the verdict answering it, reporting only an
        # identity, is a row no threshold study can use: which commits were
        # frozen, what they were measured against, and what the measurement
        # was are the record.
        for event, name in _MEASURED_CASES:
            with self.subTest(family=str(event.family), field=name):
                self._assert_refused(event, **{name: None})

    def test_a_reconciling_family_is_not_held_to_it(self) -> None:
        # The other five describe reconciliation rather than size, and a
        # restart's fresh cycle has deliberately let its commits go.
        for event in _support.family_cases()[2:]:
            with self.subTest(family=str(event.family)):
                self.assertNotIn(
                    "source_sha",
                    _records.build_late_payload(event, _STRIPPED),
                )

    def _assert_refused(self, event, **generation_fields) -> None:
        with self.assertRaises(_REFUSED):
            _records.build_late_payload(
                event, _support.measured_generation(**generation_fields),
            )


if __name__ == "__main__":
    unittest.main()
