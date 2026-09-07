# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""An adjudicated commit nobody authorized, on the side that already published.

The exemption an older binary wrote lets nothing past the size gate on its
own, and what that costs on a pull request the remote already carries is not
what it costs before one exists. A commit the pull request is standing on has
already been delivered: the push would move nothing, so what is left is the
bookkeeping behind it, and holding that back would strand published work under
a stage no later tick advances. A commit it is NOT standing on is an
unmeasured push waiting to happen, and it is measured and held like any other.
"""

from __future__ import annotations

import unittest

from tests.workflow.fixtures import _legacy_exemption
from tests.workflow.stages.fixing import (
    fixing_test_support as fixing,
    published_gate_support as support,
)

CEILING = support.CEILING
MEASURED_CANDIDATE_SHA = support.MEASURED_CANDIDATE_SHA
PAST_THE_CEILING = support.PAST_THE_CEILING
_SizeGateFixtureMixin = support._SizeGateFixtureMixin

ISSUE = fixing.ISSUE
PUSH_BRANCH = fixing.PUSH_BRANCH
VALIDATING = fixing.VALIDATING
config = fixing.config
patch = fixing.patch

# The debt the settlement recorded beside the exemption, which is also what
# tells the remote standing on the accepted commit from somebody else's push
# landing there.
_KEY_APPROVED_SHA = support.KEY_APPROVED_SHA

PARK_UNAUTHORIZED_EXEMPTION = "late_unauthorized_exemption"


class DeliveredExemptionTest(unittest.TestCase, _SizeGateFixtureMixin):
    """A commit its own pull request already carries finishes its bookkeeping."""

    def setUp(self) -> None:
        self.scenario = self._seed_fix_round(
            pr_head=MEASURED_CANDIDATE_SHA,
            **{
                **_legacy_exemption(),
                _KEY_APPROVED_SHA: MEASURED_CANDIDATE_SHA,
            },
        )
        with patch.object(config, support.MAX_ADDED_LINES, CEILING):
            self.mocks = self._run_fix_round(
                self.scenario, added_lines=PAST_THE_CEILING,
            )

    def test_it_publishes_without_a_reading(self) -> None:
        # Nothing is being decided about whether unmeasured bulk may reach a
        # pull request -- it is there. Measuring it would only stop the
        # relabel behind a publication that has already happened.
        self._assert_unmeasured(self.mocks)
        self._assert_settled_publication(self.mocks)

    def test_it_hands_the_issue_on(self) -> None:
        self.assertIn((ISSUE, VALIDATING), self.scenario.github.label_history)


class UndeliveredExemptionTest(unittest.TestCase, _SizeGateFixtureMixin):
    """The same record where the push has not happened is measured and held."""

    def setUp(self) -> None:
        self.scenario = self._seed_fix_round(**{
            **_legacy_exemption(),
            _KEY_APPROVED_SHA: MEASURED_CANDIDATE_SHA,
        })
        with patch.object(config, support.MAX_ADDED_LINES, CEILING):
            self.mocks = self._run_fix_round(
                self.scenario, added_lines=PAST_THE_CEILING,
            )

    def test_the_debt_does_not_publish_it(self) -> None:
        # The approval is the settlement's own publication debt rather than a
        # reading this gate took, so it is worth exactly what the exemption
        # beside it is worth.
        self._assert_unpushed(self.mocks)
        self.assertEqual(
            self.mocks[support.COUNT_ADDED_LINES].call_count, 1,
        )

    def test_it_waits_for_the_authorization(self) -> None:
        # Parked rather than routed to the adjudication: the change has been
        # ruled one change, and what is missing is the human.
        pinned = self._pinned(self.scenario)

        self.assertTrue(pinned[fixing.AWAITING_HUMAN])
        self.assertEqual(
            pinned[fixing.PARK_REASON], PARK_UNAUTHORIZED_EXEMPTION,
        )
        self.assertEqual(self.scenario.github.label_history, [])


if __name__ == "__main__":
    unittest.main()
