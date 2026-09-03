# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The one commit an accepted candidate publishes under, and only it."""
from __future__ import annotations

import unittest

from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.late_split import (
    exemption as _exemption,
    keys as _late_keys,
    state as _late_state,
)
from orchestrator.workflow.late_split.formats import InvalidLateValue
from tests.workflow.late_split.generation_test_support import (
    BASE_SHA,
    CANDIDATE_SHA,
    measured_generation,
)

# Values a hand edit or an older binary could leave in the field, none of
# which names one commit: an abbreviation, prose, a number, and a flag.
_NOT_A_COMMIT = (CANDIDATE_SHA[:7], "one coherent change", 7, True)


class RecordedExemptionTest(unittest.TestCase):
    """What the field holds, and what it refuses to hold."""

    def test_the_measured_commit_round_trips(self) -> None:
        state = PinnedState(data={})

        _exemption.record_exemption(state, CANDIDATE_SHA)

        self.assertEqual(_exemption.read_exemption(state), CANDIDATE_SHA)
        self.assertTrue(_exemption.is_exempt(state, CANDIDATE_SHA))

    def test_an_absent_field_exempts_nothing(self) -> None:
        state = PinnedState(data={})

        self.assertIsNone(_exemption.read_exemption(state))
        self.assertFalse(_exemption.is_exempt(state, CANDIDATE_SHA))

    def test_a_value_that_is_not_a_commit_is_refused(self) -> None:
        for written in _NOT_A_COMMIT:
            with self.subTest(written=written):
                state = PinnedState(data={})

                with self.assertRaises(InvalidLateValue):
                    _exemption.record_exemption(state, written)

                self.assertEqual(state.data, {})

    def test_a_damaged_field_exempts_nothing(self) -> None:
        # The gate reads this to decide whether a candidate may publish
        # unmeasured, so a value nobody here wrote has to answer "measure it"
        # rather than "let it through".
        for written in _NOT_A_COMMIT:
            with self.subTest(written=written):
                state = PinnedState(
                    data={_exemption.LATE_EXEMPT_SHA: written},
                )

                self.assertIsNone(_exemption.read_exemption(state))
                self.assertFalse(
                    _exemption.is_exempt(state, CANDIDATE_SHA),
                )

    def test_clearing_leaves_the_rest_alone(self) -> None:
        state = PinnedState(data={"pr_number": 12})
        _exemption.record_exemption(state, CANDIDATE_SHA)

        _exemption.clear_exemption(state)

        self.assertEqual(state.data, {"pr_number": 12})


class ExemptionScopeTest(unittest.TestCase):
    """One commit is exempt; the next one is a fresh candidate."""

    def test_a_new_commit_is_not_exempt(self) -> None:
        # The whole invalidation rule: work committed on top of an accepted
        # candidate is work nobody adjudicated, and it is measured as such.
        state = PinnedState(data={})
        _exemption.record_exemption(state, CANDIDATE_SHA)

        self.assertFalse(_exemption.is_exempt(state, BASE_SHA))

    def test_an_unnamable_candidate_is_not_exempt(self) -> None:
        state = PinnedState(data={})
        _exemption.record_exemption(state, CANDIDATE_SHA)

        for asked in _NOT_A_COMMIT:
            with self.subTest(asked=asked):
                self.assertFalse(_exemption.is_exempt(state, asked))

    def test_it_outlives_its_own_generation(self) -> None:
        # It is written precisely so the generation CAN be cleared: dropping
        # it with the rest would send the same candidate back through the
        # gate and into a second adjudication.
        state = PinnedState(data={})
        _late_state.write_late_generation(state, measured_generation())
        _exemption.record_exemption(state, CANDIDATE_SHA)

        _late_state.clear_late_generation(state)

        self.assertEqual(_exemption.read_exemption(state), CANDIDATE_SHA)
        self.assertNotIn(
            _exemption.LATE_EXEMPT_SHA, _late_keys.LATE_STATE_KEYS,
        )


if __name__ == "__main__":
    unittest.main()
