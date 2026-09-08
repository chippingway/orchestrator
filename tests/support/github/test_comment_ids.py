# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The id space every comment this double hands out is numbered in.

One ascending space per client, shared by every thread and by the pinned
records beside them, because that is the space GitHub numbers issue comments
in. A double that numbers a thread from its own comments instead gives two
threads the same id and puts a seeded reply below a record minted after it --
and the orchestrator reads a thread by comparing ids, so a case written
against that double asserts on an ordering production never has.
"""

from __future__ import annotations

import unittest

from tests.support.fakes import (
    FakeComment,
    FakeGitHubClient,
    FakeUser,
    make_issue,
)
from tests.workflow.fixtures import LABEL_IMPLEMENTING

_FIRST_ISSUE = 701
_SECOND_ISSUE = 702
_BODY = "a reply"


class CommentIdSpaceTest(unittest.TestCase):
    """What the double promises about every id it mints."""

    def setUp(self) -> None:
        self.github = FakeGitHubClient()
        self.issues = [
            make_issue(number, label=LABEL_IMPLEMENTING)
            for number in (_FIRST_ISSUE, _SECOND_ISSUE)
        ]
        for issue in self.issues:
            self.github.add_issue(issue)
            self.github.seed_state(issue.number)

    def test_no_two_threads_share_an_id(self) -> None:
        # Interleaved deliberately: a client-wide counter is the only thing
        # that keeps a reply seeded on one thread off an id the other has
        # been given, and a per-thread one collides on the very first pair.
        minted = []
        for _ in range(3):
            for issue in self.issues:
                minted.append(self._seed_reply(issue))
                minted.append(self.github.comment(issue, _BODY).id)

        self.assertEqual(len(set(minted)), len(minted))

    def test_every_id_ascends(self) -> None:
        # Which is what a watermark means: a comment past one is a comment
        # nobody has read, whichever thread or author it came from.
        minted = [
            self._seed_reply(issue)
            for issue in self.issues
            for _ in range(2)
        ]

        self.assertEqual(minted, sorted(minted))

    def test_a_reply_lands_above_its_own_thread(self) -> None:
        # A seeded reply is answering what is already there, so it may never
        # be numbered at or below it -- a reply sharing the watermark's id is
        # one no reader ever sees.
        issue = self.issues[0]
        self.github.comment(issue, _BODY)

        seeded = self._seed_reply(issue)

        self.assertGreater(
            seeded, max(posted.id for posted in issue.comments[:-1]),
        )

    def test_a_record_lands_above_a_seeded_reply(self) -> None:
        # The other direction, and the one a per-thread number breaks: the
        # record is minted from the client's counter, so a reply that never
        # advanced it is handed an id the next record repeats.
        seeded = self._seed_reply(self.issues[0])

        self.github.seed_state(_SECOND_ISSUE)

        self.assertGreater(
            self.github.read_pinned_state(self.issues[1]).comment_id, seeded,
        )

    def _seed_reply(self, issue) -> int:
        """Append one reply the way a case seeds a human's, and say which."""
        identified = self.github.next_reply_id(issue)
        issue.comments.append(
            FakeComment(identified, _BODY, user=FakeUser("alice")),
        )
        return identified


if __name__ == "__main__":
    unittest.main()
