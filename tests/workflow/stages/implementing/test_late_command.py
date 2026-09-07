# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Which reply on a standing authorization park a tick should act on.

A reading and nothing else: no record is written here and nothing is decided,
so what these pin down is which comment the road behind it is handed, how far
the thread was looked at, and every author and shape that is never in the
reading at all.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from orchestrator import config
from orchestrator.workflow.engine import comments as _comments
from orchestrator.workflow.stages.implementing import (
    late_command as _command,
    state as _state,
)
from tests.workflow.fixtures import MEASURED_CANDIDATE_SHA
from tests.workflow.stages.implementing import (
    late_consent_test_support as support,
)


class ReadTheParkTest(support._ParkedCase, unittest.TestCase):
    """The command a human has written on this park, or nothing."""

    def test_the_command_carries_what_it_names(self) -> None:
        identified = self._reply(support.AUTHORIZE)

        answer = self._read()

        self.assertEqual(answer.named, MEASURED_CANDIDATE_SHA)
        self.assertEqual(answer.comment_id, identified)

    def test_a_thread_with_nothing_new_reads_nothing(self) -> None:
        # A human who has not replied yet, which is every poll of a standing
        # park until one does.
        self.assertIsNone(self._read())

    def test_an_abbreviation_carries_nothing(self) -> None:
        # A command nobody could act on is still a gesture this park owes an
        # answer to. The empty id can never equal a candidate, so it takes the
        # refusal road by itself rather than earning a silent park.
        identified = self._reply(support.AUTHORIZE_ABBREVIATED)

        answer = self._read()

        self.assertEqual(answer.named, "")
        self.assertEqual(answer.comment_id, identified)

    def test_the_last_fresh_reply_decides(self) -> None:
        # Guidance written after a command outranks it, and a command written
        # after guidance is the decision that replaced it. Read as a set, one
        # stale reply would refuse every command posted behind it for as long
        # as the park stood.
        self._reply(support.AUTHORIZE_ANOTHER)
        self._reply(support.GUIDANCE)
        decided = self._reply(support.AUTHORIZE)

        answer = self._read()

        self.assertEqual(answer.comment_id, decided)

    def test_the_watermark_is_what_was_looked_at(self) -> None:
        # Every comment the fetch returned counts, filtered-out ones included:
        # what a watermark records is what has been LOOKED at, and an
        # outsider's reply that never reaches the next poll as unread is the
        # whole point of recording one.
        acted = self._reply(support.AUTHORIZE)
        seen = self._reply(support.GUIDANCE, author=support.OUTSIDER)

        with patch.object(
            config, support.ALLOWLIST_CONFIG, (support.TRUSTED_AUTHOR,),
        ):
            answer = self._read()

        self.assertEqual(answer.comment_id, acted)
        self.assertEqual(answer.watermark, seen)

    def _read(self):
        return _command._read_the_park(self.github, self.issue, self._state())


class UnreadReplyTest(support._ParkedCase, unittest.TestCase):
    """Every reply this reading is never handed, and why each is left."""

    def test_another_park_is_not_this_ones_to_end(self) -> None:
        # Both halves of the park say who is waiting behind which question,
        # and a command written under either of the others is not an answer
        # to this one.
        for described, seeded in (
            ("another reason", {_state._PARK_REASON: "late_measurement_failed"}),
            ("nobody waiting", {_state._AWAITING_HUMAN: False}),
        ):
            with self.subTest(park=described):
                self.setUp()
                self._seed(**seeded)
                self._reply(support.AUTHORIZE)

                self.assertIsNone(self._read())

    def test_guidance_is_not_this_parks_to_read(self) -> None:
        # A last word that is not the whole command belongs to the ordinary
        # resume that feeds it to the developer rather than to a bypass taken
        # behind their back.
        for described, written in (
            ("prose", support.GUIDANCE),
            ("the command inside a paragraph", f"sure: {support.AUTHORIZE}"),
            ("a bare continue", "/orchestrator continue"),
        ):
            with self.subTest(reply=described):
                self.setUp()
                self._reply(written)

                self.assertIsNone(self._read())

    def test_an_outsider_authorizes_nothing(self) -> None:
        # The allowlist's rule applied where the thread is read: an outsider's
        # comment is not in the reading, so nothing they post can authorize
        # anything or move a watermark past somebody who may.
        self._reply(support.AUTHORIZE, author=support.OUTSIDER)

        with patch.object(
            config, support.ALLOWLIST_CONFIG, (support.TRUSTED_AUTHOR,),
        ):
            self.assertIsNone(self._read())

    def test_our_own_sentence_is_nobodys_decision(self) -> None:
        # The park notice spells the command out ready to copy, so our own
        # comments are exactly what a reader matching on that syntax would
        # otherwise mistake for one. Read off the marker rather than the
        # login, which a personal access token shares with its owner.
        self._reply(f"{support.AUTHORIZE}\n\n{_comments._ORCH_COMMENT_MARKER}")

        self.assertIsNone(self._read())

    def test_guidance_written_last_reads_nothing(self) -> None:
        # The same batch the other way round: the safe reading of somebody who
        # asked to publish and then asked for a change publishes nothing.
        self._reply(support.AUTHORIZE)
        self._reply(support.GUIDANCE)

        self.assertIsNone(self._read())

    def _read(self):
        return _command._read_the_park(self.github, self.issue, self._state())


if __name__ == "__main__":
    unittest.main()
