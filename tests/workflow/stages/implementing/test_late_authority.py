# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What an adjudication is worth at the gate without a human behind it.

An oversized candidate publishes without a reading only where two records name
it: the exemption a settlement wrote, and the terms an operator authorized
that publication on. These pin down the second half -- what the gate does with
an exemption standing alone, which is the shape an older binary left on live
issues and the shape a damaged authorization leaves on any of them.

What that costs is the measurement, and the reading then decides: a candidate
at or below the ceiling publishes exactly as it always did, and an oversized
one is parked for the authorization rather than routed back into an
adjudication that has already answered. The park's own recovery is here too,
because the command that ends it is the only thing that can.
"""

from __future__ import annotations

import unittest

from orchestrator import config
from orchestrator.git.measurement.models import FingerprintFailure
from tests.workflow.fixtures import (
    LABEL_DECOMPOSING,
    MEASURED_BASE_SHA,
    MEASURED_CANDIDATE_SHA,
    SHA_LENGTH,
    _agent,
    _authorize_command,
    _authorized_exemption,
    _damaged_authorization,
    _legacy_exemption,
)
from tests.workflow.stages.implementing import late_gate_test_support as support

_DECOMPOSING = (support.GATE_ISSUE_NUMBER, LABEL_DECOMPOSING)
_KEY_APPROVED_SHA = "late_approved_sha"
_MAX_ADDED_LINES = "MAX_ADDED_LINES"
_OTHER_SHA = "d" * SHA_LENGTH

# What an operator writes to end the park, and the two replies that are not
# it: a paragraph mentioning the command, and the command for a commit this
# issue is not holding.
_AUTHORIZE = _authorize_command()
_AUTHORIZE_IN_PROSE = f"looks fine to me, so: {_AUTHORIZE}"
_AUTHORIZE_ANOTHER = _authorize_command(_OTHER_SHA)

# The reply id the fixture posts, which is the comment an authorization
# recorded from this thread is attributable to.
_REPLY_ID = support.REPLY_COMMENT_ID


class UnauthorizedExemptionTest(
    support._LegacyExemptionCase, unittest.TestCase,
):
    """An exemption alone lets nothing past: the candidate is measured."""

    def test_an_unauthorized_exemption_is_measured(self) -> None:
        # Both shapes reach the same place. The legacy comment never had an
        # authorization on it, and the damaged one has a group this build
        # cannot read whole -- and a bypass nobody can show the terms of is
        # worth exactly what a bypass nobody granted is worth.
        for shape, seeded in (
            ("legacy", _legacy_exemption()),
            ("damaged", _damaged_authorization()),
        ):
            with self.subTest(shape=shape):
                self.setUp()
                self._seed(**seeded)

                mocks = self._run_gate(added_lines=support.OVERSIZED_ADDITIONS)

                self._assert_measured(mocks)
                self._assert_held(mocks)

    def test_an_authorized_one_still_publishes(self) -> None:
        # The other side of the same rule, so the refusals above are about the
        # missing half rather than about the exemption having stopped working.
        self._seed(**_authorized_exemption())

        mocks = self._run_gate()

        self._assert_unmeasured(mocks)
        self._assert_published(mocks)

    def test_a_small_candidate_still_publishes(self) -> None:
        # What "measured like any other candidate" means at the other end of
        # the reading: nothing about a legacy exemption holds a change the
        # ceiling would have let through.
        self._seed_legacy()

        mocks = self._run_gate(added_lines=support.SMALL_ADDITIONS)

        self._assert_measured(mocks)
        self._assert_published(mocks)

    def test_the_exact_ceiling_publishes(self) -> None:
        # The boundary is inclusive and stays inclusive here: a candidate
        # exactly at the configured value is not oversized, so it never
        # reaches the park at all.
        self._seed_legacy()

        with support.patch.object(
            config, _MAX_ADDED_LINES, support.SMALL_ADDITIONS,
        ):
            mocks = self._run_gate(added_lines=support.SMALL_ADDITIONS)

        self._assert_measured(mocks)
        self._assert_published(mocks)

    def test_the_exemptions_own_debt_does_not_bypass(self) -> None:
        # The settlement writes the exemption and the approval in one breath,
        # so an approval naming the exempt commit is that adjudication's
        # publication debt rather than a reading this gate took. Read as an
        # ordinary approval it would publish the very candidate the record
        # above it may not.
        self._seed_legacy(**{_KEY_APPROVED_SHA: MEASURED_CANDIDATE_SHA})

        mocks = self._run_gate(added_lines=support.OVERSIZED_ADDITIONS)

        self._assert_measured(mocks)
        self._assert_held(mocks)

    def test_a_gate_owned_approval_still_bypasses(self) -> None:
        # And the approval this gate owns is untouched. Nothing exempts the
        # commit, so the debt is the gate's own answer about a small candidate
        # brought back by a crash, and no human was ever owed a decision.
        self._seed(**{_KEY_APPROVED_SHA: MEASURED_CANDIDATE_SHA})

        mocks = self._run_gate()

        self._assert_unmeasured(mocks)
        self._assert_published(mocks)


class AuthorizationParkTest(support._LegacyExemptionCase, unittest.TestCase):
    """What an oversized reading of an adjudicated candidate earns."""

    def test_it_parks_rather_than_re_adjudicating(self) -> None:
        # The change has been ruled one change already. Routing it back would
        # pay for a second adjudicator over an answered question, and a
        # `split` there would cut children out of work somebody decided ships
        # whole -- so the issue stops for the one thing that is missing.
        self._seed_legacy()

        mocks = self._run_gate(added_lines=support.OVERSIZED_ADDITIONS)

        self._assert_held(mocks)
        self._assert_waiting_for_authorization()
        self.assertNotIn(_DECOMPOSING, self.github.label_history)

    def test_it_deletes_nothing_and_keeps_the_reading(self) -> None:
        # The record is what an authorization would be checked against, and
        # the reading is what its terms are written from -- so the park
        # repairs nothing and keeps the pair it counted.
        self._seed_legacy()

        self._run_gate(added_lines=support.OVERSIZED_ADDITIONS)

        self._assert_kept_the_record()
        self._assert_frozen(additions=support.OVERSIZED_ADDITIONS)

    def test_the_notice_names_the_command(self) -> None:
        self._seed_legacy()

        self._run_gate(added_lines=support.OVERSIZED_ADDITIONS)

        self.assertEqual(len(self.github.posted_comments), 1)
        said = self.github.posted_comments[0][1]
        self.assertIn(config.HITL_MENTIONS, said)
        self.assertIn(_AUTHORIZE, said)
        self.assertIn(str(support.OVERSIZED_ADDITIONS), said)
        self.assertIn(str(config.MAX_ADDED_LINES), said)


class AuthorizationRecoveryTest(
    support._LegacyExemptionCase, unittest.TestCase,
):
    """The command that ends the park, and every reply that does not."""

    def test_the_command_records_the_terms(self) -> None:
        # The authorization is written from the gate's own reading rather than
        # from anything the comment already carried: a human authorizes a
        # change of THIS size against THAT ceiling, and only the owner that
        # counted can say either.
        self._park_awaiting_authorization(_AUTHORIZE)

        self._run_gate()

        pinned = self._pinned()
        self.assertEqual(
            pinned[support.KEY_OVERRIDE_CANDIDATE_SHA], MEASURED_CANDIDATE_SHA,
        )
        self.assertEqual(
            pinned[support.KEY_OVERRIDE_BASE_SHA], MEASURED_BASE_SHA,
        )
        self.assertEqual(
            pinned[support.KEY_OVERRIDE_ADDITIONS], support.OVERSIZED_ADDITIONS,
        )
        self.assertEqual(
            pinned[support.KEY_OVERRIDE_THRESHOLD], support.GATE_THRESHOLD,
        )
        self.assertEqual(pinned[support.KEY_OVERRIDE_COMMENT_ID], _REPLY_ID)

    def test_the_command_publishes_unmeasured(self) -> None:
        # What the record buys on the same tick: the park comes down, the
        # candidate goes out under the exemption it now has a human behind,
        # and nothing pays for a developer over work that is already
        # committed.
        self._park_awaiting_authorization(_AUTHORIZE)

        mocks = self._run_gate()

        self._assert_no_agent(mocks)
        self._assert_unmeasured(mocks)
        self._assert_published(mocks)
        pinned = self._pinned()
        self.assertFalse(pinned[support.AWAITING_HUMAN])
        self.assertIsNone(pinned[support.PARK_REASON])
        self.assertEqual(pinned[support.LAST_ACTION_COMMENT_ID], _REPLY_ID)

    def test_a_lost_reading_leaves_the_park(self) -> None:
        # Nothing about a store that cannot hand back the content between two
        # commits it holds is the operator's doing, so the next tick takes the
        # same reading rather than asking them to authorize twice.
        mocks = self._unreadable_contribution()

        self._assert_held(mocks)
        self._assert_waiting_for_authorization()
        self._assert_kept_the_record()

    def test_the_standing_park_is_not_announced_twice(self) -> None:
        # The same road re-measures the pair the park was taken over and
        # re-takes the park, which is the one way the gate is entered while
        # somebody is still waiting behind it. Said again, the notice would
        # mention the same people about a decision they have already made.
        self._unreadable_contribution()

        self.assertEqual(self.github.posted_comments, [])

    def test_guidance_resumes_the_developer_instead(self) -> None:
        # The two say opposite things -- one that the change publishes as it
        # stands, the other that it has to be different -- and the safe
        # reading of a human who wrote either publishes nothing.
        self._park_awaiting_authorization(_AUTHORIZE_IN_PROSE)

        mocks = self._run_gate(
            run_agent=_agent(
                session_id=support.DEV_SESSION, last_message="revised",
            ),
            added_lines=support.OVERSIZED_ADDITIONS,
        )

        self._assert_resumed(mocks)
        self.assertNotIn(support.KEY_OVERRIDE_CANDIDATE_SHA, self._pinned())

    def test_another_commits_command_does_nothing(self) -> None:
        # A bypass may license exactly what a human looked at, and an id
        # copied out of a notice about work the developer has since been
        # resumed over is not this candidate.
        self._park_awaiting_authorization(_AUTHORIZE_ANOTHER)

        mocks = self._run_gate(
            run_agent=_agent(
                session_id=support.DEV_SESSION, last_message="revised",
            ),
            added_lines=support.OVERSIZED_ADDITIONS,
        )

        self.assertNotIn(support.KEY_OVERRIDE_CANDIDATE_SHA, self._pinned())
        self.assertEqual(
            mocks[support.PUSH_BRANCH].call_args_list, [],
        )

    def _unreadable_contribution(self):
        """The authorized park re-entered on a host that cannot fingerprint."""
        self._park_awaiting_authorization(_AUTHORIZE)
        return self._run_gate(
            contribution_digest=FingerprintFailure.CONTENT_ABSENT,
            added_lines=support.OVERSIZED_ADDITIONS,
        )


if __name__ == "__main__":
    unittest.main()
