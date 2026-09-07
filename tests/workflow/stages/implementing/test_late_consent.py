# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The park an adjudicated candidate with nobody behind it waits on.

A hold rather than a route back to the adjudication: the change has been ruled
one change already, so what is missing is the person. These pin down what the
hold leaves on the record, what the command that ends one writes, and what
every reply it may not act on is answered with -- once, and consumed no
further than the reading that found it.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from orchestrator import config
from orchestrator.git.measurement import fingerprint as _fingerprint
from orchestrator.git.measurement.models import (
    ContributionFingerprint,
    FingerprintFailure,
)
from orchestrator.workflow.engine import comments as _comments
from orchestrator.workflow.stages.implementing import (
    late_command as _command,
    late_consent as _consent,
    state as _state,
)
from tests.workflow.fixtures import MEASURED_BASE_SHA, MEASURED_CANDIDATE_SHA
from tests.workflow.interleaving import _RacesTheStep
from tests.workflow.repo_values import CONTRIBUTION_DIGEST
from tests.workflow.stages.implementing import (
    late_consent_test_support as support,
)

_FINGERPRINT_CONTRIBUTION = "_fingerprint_contribution"
_POST_ISSUE_COMMENT = "_post_issue_comment"
_ORCH_MARKER = _comments._ORCH_COMMENT_MARKER

# What the hermetic world's reading of the frozen pair answers with, and the
# refusal a host that never held the content between them gives instead.
_CONTRIBUTED = ContributionFingerprint(
    base_sha=MEASURED_BASE_SHA,
    candidate_sha=MEASURED_CANDIDATE_SHA,
    digest=CONTRIBUTION_DIGEST,
)
_UNREADABLE = ContributionFingerprint(failure=FingerprintFailure.CONTENT_ABSENT)

# The sentence only the side of publication with a resume behind it may offer.
_RESUMED_AGAINST_IT = "the developer is resumed against it"


class _ConsentCase(support._ParkedCase):
    """One gate call asking whether this candidate may publish as it stands."""

    def _authorizes(self, contribution=_CONTRIBUTED, **entered) -> bool:
        with patch.object(
            _fingerprint, _FINGERPRINT_CONTRIBUTION, return_value=contribution,
        ):
            return _consent._authorizes_the_park(
                self._gate(**entered), support.measured(),
            )


class AuthorizationParkTest(_ConsentCase, unittest.TestCase):
    """What an oversized reading of an adjudicated candidate is held under."""

    def test_it_holds_and_says_so_once(self) -> None:
        self._seed(parked=False)

        self.assertFalse(self._authorizes())

        pinned = self._pinned()
        self.assertTrue(pinned[_state._AWAITING_HUMAN])
        self.assertEqual(
            pinned[_state._PARK_REASON], _command.PARK_UNAUTHORIZED_EXEMPTION,
        )

    def test_a_standing_park_is_not_announced_twice(self) -> None:
        # The seams that publish onto a pull request the remote already
        # carries re-enter the gate on every poll behind the park, so a second
        # notice would mention the same people once a poll about a decision
        # they have already been asked for.
        self._seed(**support.measured_pair())

        self.assertFalse(self._authorizes())

        self.assertEqual(self.github.posted_comments, [])

    def test_a_park_over_another_commit_speaks_again(self) -> None:
        # A record naming another commit is a park a resumed developer's fresh
        # commit has moved past, and the human holding the issue has never
        # been told about the candidate now in hand.
        self._seed(**support.measured_pair(candidate_sha=support.STRANGER_SHA))

        self.assertFalse(self._authorizes())

        self.assertEqual(len(self.github.posted_comments), 1)

    def test_the_notice_names_the_command(self) -> None:
        # An operator authorizes a change of THIS size against THAT ceiling,
        # so the notice carries the reading the tick took rather than a record
        # read back off the comment.
        self._seed(parked=False)

        self._authorizes()

        said = self.github.posted_comments[0][1]
        self.assertIn(config.HITL_MENTIONS, said)
        self.assertIn(support.AUTHORIZE, said)
        self.assertIn(str(support.OVERSIZED_ADDITIONS), said)
        self.assertIn(str(support.THRESHOLD), said)

    def test_the_notice_offers_a_resume(self) -> None:
        # Before there is one the ordinary resume is still in front of the
        # issue, so a reply that is not the command reaches the developer.
        self._seed(parked=False)

        self._authorizes()

        self.assertIn(_RESUMED_AGAINST_IT, self.github.posted_comments[0][1])

    def test_the_notice_offers_no_resume_past_one(self) -> None:
        # Past a pull request the debt reconciliation that brings a parked
        # issue back to the gate stops the tick ahead of the stage handler on
        # every poll, so nothing there would carry a human's words to an agent
        # -- and a notice offering it would have somebody writing into a
        # thread nothing reads.
        self._seed(parked=False)

        self._authorizes(entry=support.PUBLISHED_ENTRY)

        said = self.github.posted_comments[0][1]
        self.assertIn(support.AUTHORIZE, said)
        self.assertNotIn(_RESUMED_AGAINST_IT, said)

    def test_it_deletes_nothing_and_counts_nothing(self) -> None:
        # The record is what an authorization would be checked against, so a
        # park that tidied the comment would destroy the evidence it exists to
        # ask about -- and a generation carrying a reading past its ceiling is
        # what the dispatcher restores `workflow:decomposing` over, so the
        # park would be relabelled out from under itself on the next poll.
        self._seed(parked=False)

        self._authorizes()

        pinned = self._pinned()
        self.assertEqual(pinned[support.KEY_EXEMPT_SHA], MEASURED_CANDIDATE_SHA)
        self.assertNotIn(support.KEY_OVERRIDE_CANDIDATE_SHA, pinned)
        self.assertIsNone(pinned.get("late_additions"))


class AuthorizedCandidateTest(_ConsentCase, unittest.TestCase):
    """What the command that ends the park writes, and what it costs."""

    def test_the_terms_come_from_the_reading(self) -> None:
        identified = self._reply(support.AUTHORIZE)

        self.assertTrue(self._authorizes())

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
            pinned[support.KEY_OVERRIDE_THRESHOLD], support.THRESHOLD,
        )
        self.assertEqual(pinned[support.KEY_OVERRIDE_COMMENT_ID], identified)

    def test_the_park_comes_down_with_the_record(self) -> None:
        # One write: the record without the park cleared says a human is owed
        # a question they have answered, and the park without the record sends
        # the candidate straight back to it.
        identified = self._reply(support.AUTHORIZE)

        self._authorizes()

        pinned = self._pinned()
        self.assertFalse(pinned[_state._AWAITING_HUMAN])
        self.assertIsNone(pinned[_state._PARK_REASON])
        self.assertEqual(pinned[_state._LAST_ACTION_COMMENT_ID], identified)

    def test_a_lost_reading_leaves_everything_alone(self) -> None:
        # Nothing about a store that cannot hand back the content between two
        # commits it holds is the operator's doing, so the next tick takes the
        # same reading rather than asking them to authorize twice.
        self._reply(support.AUTHORIZE)

        self.assertFalse(self._authorizes(contribution=_UNREADABLE))

        pinned = self._pinned()
        self.assertTrue(pinned[_state._AWAITING_HUMAN])
        self.assertNotIn(support.KEY_OVERRIDE_CANDIDATE_SHA, pinned)
        self.assertEqual(
            pinned[_state._LAST_ACTION_COMMENT_ID],
            support.PRIOR_ACTION_COMMENT_ID,
        )

    def test_consent_withdrawn_publishes_nothing(self) -> None:
        # An operator who authorizes and then changes their mind has decided
        # about the second thing. The marker their retraction happens to carry
        # -- pasted, or quoted off a comment of ours -- is a body anybody can
        # write, and the account it is written from may be the very token this
        # orchestrator posts under. Treating either as proof of authorship
        # deletes the retraction from the reading and publishes on consent
        # withdrawn.
        for described, author in (
            ("their own account", support.TRUSTED_AUTHOR),
            ("the shared bot login", self.github._bot_login),
        ):
            with self.subTest(written_from=described):
                self.setUp()
                self._reply(support.AUTHORIZE, author=author)
                self._reply(
                    f"actually, hold off\n\n{_ORCH_MARKER}", author=author,
                )

                self.assertFalse(self._authorizes())

                self.assertNotIn(
                    support.KEY_OVERRIDE_CANDIDATE_SHA, self._pinned(),
                )

    def test_a_reply_landing_mid_write_survives(self) -> None:
        # The reading picked the last word the thread had when it looked, and
        # a retraction posted while this tick was still writing is not one of
        # the comments it examined. Consumed to the tip as it stands NOW, that
        # retraction would be swallowed unread while the authorization it
        # retracts published.
        self._reply(support.AUTHORIZE)
        landed = []
        racing = _RacesTheStep(
            _consent._recorded_authorization,
            lambda: landed.append(self._reply("actually, hold off")),
        )

        with patch.object(_consent, "_recorded_authorization", racing):
            self.assertTrue(self._authorizes())

        self.assertLess(
            self._pinned()[_state._LAST_ACTION_COMMENT_ID], landed[0],
        )


class RefusedCommandTest(_ConsentCase, unittest.TestCase):
    """Every command this park owes an answer to and may not act on."""

    def test_a_command_it_cannot_act_on_is_answered(self) -> None:
        # A bypass may license exactly what a human looked at. An id copied
        # out of a notice about work the developer has since been resumed
        # over, and an abbreviation -- which names nothing, since nothing here
        # ever writes one -- both get the sentence and the command that would
        # have worked.
        for described, written in (
            ("another commit", support.AUTHORIZE_ANOTHER),
            ("an abbreviation", support.AUTHORIZE_ABBREVIATED),
        ):
            with self.subTest(command=described):
                self.setUp()
                self._reply(written)

                self.assertFalse(self._authorizes())

                pinned = self._pinned()
                self.assertTrue(pinned[_state._AWAITING_HUMAN])
                self.assertNotIn(support.KEY_OVERRIDE_CANDIDATE_SHA, pinned)
                self.assertIn(
                    MEASURED_CANDIDATE_SHA, self.github.posted_comments[-1][1],
                )

    def test_the_refusal_is_consumed_past_itself(self) -> None:
        # Ids ascend, so the sentence lands above the reply it answers. Left
        # between the two, the orchestrator's own words are what the next poll
        # finds past the watermark -- and every other reader of this thread
        # takes that for a human's fresh guidance.
        answered = self._reply(support.AUTHORIZE_ANOTHER)

        self._authorizes()

        watermark = self._pinned()[_state._LAST_ACTION_COMMENT_ID]
        self.assertGreater(watermark, answered)
        self.assertEqual(
            watermark, self.github.latest_comment_id(self.issue),
        )

    def test_the_same_reply_is_answered_once(self) -> None:
        # The sentence and the write that consumes it are two operations, and
        # a tick that says the first and dies before the second loses both the
        # watermark and the ledger entry naming what it posted -- they are
        # staged into one write. The poll after that finds our own sentence
        # standing as the last word it can attribute to nobody, which is no
        # command, so it holds the park it is already standing on and says
        # nothing rather than mentioning the same people twice.
        self._reply(support.AUTHORIZE_ANOTHER)
        self._authorizes()
        self._seed(**{
            _state._LAST_ACTION_COMMENT_ID: support.PRIOR_ACTION_COMMENT_ID,
            **support.measured_pair(),
        })

        self._authorizes()

        self.assertEqual(len(self.github.posted_comments), 1)

    def test_a_command_landing_mid_refusal_survives(self) -> None:
        # The window between reading a command this park may not act on and
        # posting the sentence answering it. An operator who reads the notice
        # and gets it right in there lands BELOW our sentence, since ids
        # ascend -- so a watermark jumped straight to the sentence's own id
        # would consume their answer unread and leave the park standing over a
        # command nobody will ever see again.
        self._reply(support.AUTHORIZE_ANOTHER)
        corrected = []
        racing = _RacesTheStep(
            _comments._post_issue_comment,
            lambda: corrected.append(self._reply(support.AUTHORIZE)),
        )

        with patch.object(_comments, _POST_ISSUE_COMMENT, racing):
            self.assertFalse(self._authorizes())

        self.assertLess(
            self._pinned()[_state._LAST_ACTION_COMMENT_ID], corrected[0],
        )

    def test_the_corrected_command_publishes(self) -> None:
        # And the other half of it: the reply the refusal did not swallow is
        # the last fresh word on the next reading, so the poll after the race
        # records the authorization rather than asking for it again.
        self._reply(support.AUTHORIZE_ANOTHER)
        corrected = []
        racing = _RacesTheStep(
            _comments._post_issue_comment,
            lambda: corrected.append(self._reply(support.AUTHORIZE)),
        )
        with patch.object(_comments, _POST_ISSUE_COMMENT, racing):
            self._authorizes()

        self.assertTrue(self._authorizes())

        self.assertEqual(
            self._pinned()[support.KEY_OVERRIDE_COMMENT_ID], corrected[0],
        )

    def test_a_correct_command_behind_it_still_works(self) -> None:
        # The command a human gets right after getting one wrong has to work.
        # Read as a set instead of as a last word, the first reply would
        # refuse every one behind it for as long as the park stood.
        self._reply(support.AUTHORIZE_ANOTHER)
        self._authorizes()
        corrected = self._reply(support.AUTHORIZE)

        self.assertTrue(self._authorizes())

        self.assertEqual(
            self._pinned()[support.KEY_OVERRIDE_COMMENT_ID], corrected,
        )


if __name__ == "__main__":
    unittest.main()
