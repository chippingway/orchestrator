# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The handoff record this stage was given, and why it ends here.

A `validating` approval settles a finished squash into
`late_collapse_handoff_sha` -- the commit the relabel behind it is owed over --
and drops that record in a write BEHIND the label it moves. So a record still
standing when a documenting tick runs is one whose move landed and whose
cleanup write did not, and this stage having the issue is the only proof of
that there is: the label history cannot tell a move that never happened from
one a drift unwind later reversed.

Left standing, that is exactly what it costs. The unwind sends the issue back
to `validating` for a re-review with the pull request still on the head the
record names, and the route that reads it there answers by relabelling
straight back here -- so the review the unwind exists to ask for never runs.
"""
from __future__ import annotations

import unittest
from types import MappingProxyType

from orchestrator.workflow.late_split import collapses as _collapses
from tests.support.fakes import DEFAULT_PR_HEAD_SHA
from tests.workflow.fixtures import _agent
from tests.workflow.stages.documenting.documenting_scenario_test_support import (
    _ParkedDocumentingFixture,
)
from tests.workflow.stages.documenting.documenting_test_support import (
    AWAITING_HUMAN,
    PARK_AGENT_QUESTION,
    RUN_AGENT,
    VALIDATING,
)

HANDOFF_KEY = _collapses.LATE_COLLAPSE_HANDOFF

LABEL_DOCUMENTING = "workflow:documenting"

# The tick a parked issue takes: no fetch, no agent, and no write of its own,
# which is what makes the one write this record earns visible.
_QUIET_TICK = MappingProxyType({
    "push_branch": True,
    "head_shas": [],
    "branch_ahead_behind": (0, 0),
})


class SettledHandoffTest(
    unittest.TestCase,
    _ParkedDocumentingFixture,
):
    """What a documenting tick does with the record that handed it the issue."""

    def test_the_record_is_ended_here(self) -> None:
        gh, issue = self._seeded(
            park_reason=PARK_AGENT_QUESTION,
            **{HANDOFF_KEY: DEFAULT_PR_HEAD_SHA},
        )

        self._quiet_tick(gh, issue)

        self.assertNotIn(HANDOFF_KEY, gh.pinned_data(self.issue_number))
        self.assertEqual(gh.write_state_calls, 1)

    def test_an_ordinary_tick_writes_nothing(self) -> None:
        # The cost is one lookup on the pinned comment: an issue whose
        # approval dropped its own record reaches this stage exactly as it
        # always did, and a parked tick still writes nothing at all.
        gh, issue = self._seeded(park_reason=PARK_AGENT_QUESTION)

        self._quiet_tick(gh, issue)

        self.assertEqual(gh.write_state_calls, 0)

    def test_the_unwound_issue_is_reviewed_again(self) -> None:
        # The drift unwind's whole point is the re-review, and the record
        # would answer it with a relabel: the pull request is still standing
        # on the commit it names, since no docs pass has pushed anything.
        gh, issue = self._seeded(
            park_reason=PARK_AGENT_QUESTION,
            review_round=0,
            **{HANDOFF_KEY: DEFAULT_PR_HEAD_SHA},
        )
        self._quiet_tick(gh, issue)
        self._unwinds_to_validating(gh, issue)

        mocks = self._run_validating(gh, issue, run_agent=_agent())

        mocks[RUN_AGENT].assert_called_once()
        self.assertNotIn(
            (self.issue_number, LABEL_DOCUMENTING), gh.label_history,
        )

    def _quiet_tick(self, gh, issue):
        """One documenting tick that does nothing but answer this record."""
        return self._run_documenting(
            gh, issue, run_agent=_agent(), **_QUIET_TICK,
        )

    def _unwinds_to_validating(self, gh, issue) -> None:
        """Send the issue back for the re-review a body edit earned."""
        gh.set_workflow_label(issue, VALIDATING)
        state = gh.read_pinned_state(issue)
        state.set(AWAITING_HUMAN, False)
        gh.write_pinned_state(issue, state)


if __name__ == "__main__":
    unittest.main()
