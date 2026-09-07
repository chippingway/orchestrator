# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What the publication receipt vouches for, and what it may not.

`implementing_published_sha` is the note this stage leaves naming the commit it
pushed, and the window it exists for is the one between that push and a relabel
that never landed: the branch is on the remote, a pull request carries it, and
the record still says implementing. A tick reading that as fresh work would
measure a published commit and, finding it oversized, route it into an
adjudication with nothing left to hold back.

That is the receipt answering ALONE, and it is right for a commit this gate
measured on the way out. It is not right for one an exemption names and nothing
authorizes. The note is never cleared, so a branch that has been on the remote
before arrives carrying one -- and where the remote has since moved off that
commit, or the pull request is gone entirely, answering on the note alone
republishes unmeasured bulk with no frozen head to lease the push against.
There is nothing at this seam that could prove the pull request still carries
it: proving that is what a frozen publication IS, and the implementing side has
none.

So the receipt is refused there and the candidate goes to the ordinary
cumulative reading, which parks an oversized one for the authorization it is
missing.
"""

from __future__ import annotations

import unittest

from tests.support.fakes import FakePR, FakePRRef
from tests.workflow.fixtures import (
    LABEL_VALIDATING,
    MEASURED_CANDIDATE_SHA,
    SHA_LENGTH,
    _authorized_exemption,
    _issue_branch,
)
from tests.workflow.stages.implementing import (
    late_authority_test_support as legacy,
    late_gate_test_support as support,
)

_KEY_PUBLISHED_SHA = "implementing_published_sha"

# The pull request that note was written about, and the branch it is on.
_PR_NUMBER = 812
_BRANCH = _issue_branch(support.GATE_ISSUE_NUMBER)

# Where the remote is standing instead: a commit of the right shape that no
# record on these seeds names, which is what "the head has moved" looks like
# from the issue's side.
_MOVED_HEAD = "e" * SHA_LENGTH

_VALIDATING = (support.GATE_ISSUE_NUMBER, LABEL_VALIDATING)


class UnauthorizedReceiptTest(legacy._LegacyExemptionCase, unittest.TestCase):
    """A receipt standing beside an exemption nobody authorized."""

    def test_a_stale_receipt_is_measured(self) -> None:
        # Both endings of the same publication: a pull request a human pushed
        # over, and one somebody deleted. Neither still carries the commit the
        # note names, and neither is asked -- what the seeds are here for is
        # to say which real states this refusal covers, since the seam has
        # nothing it could ask and refuses on that ground alone.
        for described, standing in (
            ("moved off it", _MOVED_HEAD),
            ("gone from under it", ""),
        ):
            with self.subTest(pull_request=described):
                self.setUp()
                self._stand_the_pull_request_on(standing)
                self._receipt_for_a_legacy_exemption()

                mocks = self._run_gate(added_lines=support.OVERSIZED_ADDITIONS)

                self._assert_measured(mocks)
                self._assert_held(mocks)

    def test_a_refused_receipt_parks(self) -> None:
        # Where the reading then puts it: parked on the one refusal a named
        # command answers, rather than routed back into an adjudication that
        # has already ruled this change one change. The record it was refused
        # on is still there, so the authorization has something to name.
        self._stand_the_pull_request_on(_MOVED_HEAD)
        self._receipt_for_a_legacy_exemption()

        self._run_gate(added_lines=support.OVERSIZED_ADDITIONS)

        self._assert_waiting_for_authorization()
        self._assert_kept_the_record()

    def test_an_authorized_receipt_publishes(self) -> None:
        # The other side of the rule, so the refusals above are about the
        # missing half rather than about the receipt having stopped working:
        # the pair a human authorized publishes without a reading whatever the
        # remote is standing on.
        self._stand_the_pull_request_on(_MOVED_HEAD)
        self._seed(**{
            **_authorized_exemption(),
            _KEY_PUBLISHED_SHA: MEASURED_CANDIDATE_SHA,
        })

        mocks = self._run_gate(added_lines=support.OVERSIZED_ADDITIONS)

        self._assert_unmeasured(mocks)
        self._assert_published(mocks)

    def test_a_measured_receipt_answers_alone(self) -> None:
        # The window this note exists for, which the refusal above may not
        # close: nothing says this commit was ever exempt, so it went out
        # through a reading and the only thing missing is the relabel. Read as
        # fresh work it would be measured, and an oversized answer there routes
        # published work into an adjudication with nothing left to hold back.
        self._seed(**{_KEY_PUBLISHED_SHA: MEASURED_CANDIDATE_SHA})

        mocks = self._run_gate(added_lines=support.OVERSIZED_ADDITIONS)

        self._assert_unmeasured(mocks)
        self.assertIn(_VALIDATING, self.github.label_history)

    def _receipt_for_a_legacy_exemption(self) -> None:
        """The note an older binary's automatic exemption left on its push."""
        self._seed_legacy(**{_KEY_PUBLISHED_SHA: MEASURED_CANDIDATE_SHA})

    def _stand_the_pull_request_on(self, head: str) -> None:
        """Put this issue's open pull request on `head`, or take it away."""
        if not head:
            return
        opened = FakePR(
            number=_PR_NUMBER,
            head_branch=_BRANCH,
            head=FakePRRef(sha=head),
        )
        self.github.add_pr(opened)
        self.github.existing_open_pr[_BRANCH] = opened


if __name__ == "__main__":
    unittest.main()
