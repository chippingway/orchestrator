# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""A discussion held over several rounds, and what has to hold across all of them.

One round is already covered elsewhere; what only a running conversation can
show is what accumulates. The frontier has to be recomputed rather than
repeated, so each round after the first is handed the answer instead of the
issue. The watermark has to climb past the orchestrator's own comment as well
as the human's, or a stage that talks to itself would spawn forever. The tree
has to survive being reused rather than rebuilt each time. And the receipt has
to charge the issue once per round -- neither dropping a resumed one nor
double-counting the round that was replayed into it.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.workflow.fixtures import KEY_ISSUE_AGENT_RUNS

from tests.workflow.stages.discussion.discussion_test_support import (
    DISCUSSION_SESSION,
    PARK_DISCUSSION_RESPONSE,
    _DiscussionWorkflowMixin,
)
from tests.workflow.stages.discussion.discussion_resume_test_support import (
    _DiscussionConversation,
)

_CONVERSATION_ISSUE_NUMBER = 1200
_USAGE_ISSUE_NUMBER = 1201

_OPENING_ANALYSIS = "Two branches: own the schema, or borrow the writer's."
_SECOND_ANALYSIS = "Owning it opens migration; here is what that costs."
_THIRD_ANALYSIS = "Migration by shadow column, then a cutover flag."
_FIRST_ANSWER = "1: own it. 2: overruled, keep the shim."
_SECOND_ANSWER = "3: shadow column is fine. 4: no flag, cut over at once."


class DiscussionConversationTest(unittest.TestCase, _DiscussionWorkflowMixin):
    """Three rounds of one design conversation on one issue."""

    def test_each_answer_earns_the_next_round(self) -> None:
        with tempfile.TemporaryDirectory() as tree:
            conversation = _DiscussionConversation(
                self, _CONVERSATION_ISSUE_NUMBER, Path(tree),
            )

            opening = conversation.round(_OPENING_ANALYSIS)
            # Nobody has answered the frontier it posted, so the tick after it
            # is the humans' and earns nothing at all.
            conversation.quiet_tick()
            second = conversation.round(
                _SECOND_ANALYSIS, reply=_FIRST_ANSWER,
            )
            third = conversation.round(_THIRD_ANALYSIS, reply=_SECOND_ANSWER)

        self.assertIsNone(opening.resume_session_id)
        self._assert_resumed(second, answer=_FIRST_ANSWER)
        self._assert_resumed(third, answer=_SECOND_ANSWER)
        # Each round's watermark clears its own answer AND the comment the
        # round posted back, so a conversation cannot resume on itself.
        self.assertLess(opening.watermark, second.watermark)
        self.assertLess(second.watermark, third.watermark)
        # The tree the opening round was given is the one the rest read: only
        # the first had to build one.
        self.assertEqual(
            (
                opening.rebuilt_worktree,
                second.rebuilt_worktree,
                third.rebuilt_worktree,
            ),
            (True, False, False),
        )
        self._assert_each_analysis_posted_once(conversation)

    def test_every_round_is_charged_once(self) -> None:
        with tempfile.TemporaryDirectory() as tree:
            conversation = _DiscussionConversation(
                self, _USAGE_ISSUE_NUMBER, Path(tree),
            )

            conversation.round(_OPENING_ANALYSIS)
            conversation.quiet_tick()
            conversation.round(_SECOND_ANALYSIS, reply=_FIRST_ANSWER)
            final_round = conversation.round(
                _THIRD_ANALYSIS, reply=_SECOND_ANSWER,
            )

        # Three spawns, three folds. A tick that answered nobody must not be
        # in there, and neither must a resumed round be missing from it.
        self.assertEqual(final_round.pinned[KEY_ISSUE_AGENT_RUNS], 3)

    def _assert_resumed(self, round_record, *, answer: str) -> None:
        self.assertEqual(round_record.resume_session_id, DISCUSSION_SESSION)
        # A live session already holds the issue and its own prior analysis,
        # so what it is sent is the answer and the instruction to redraw the
        # tree around it.
        self.assertIn(answer, round_record.prompt)
        self.assertIn("the new frontier", round_record.prompt)
        self.assertEqual(round_record.park_reason, PARK_DISCUSSION_RESPONSE)

    def _assert_each_analysis_posted_once(self, conversation) -> None:
        posted = conversation.posted_bodies()
        self.assertEqual(
            {
                analysis: sum(analysis in body for body in posted)
                for analysis in (
                    _OPENING_ANALYSIS, _SECOND_ANALYSIS, _THIRD_ANALYSIS,
                )
            },
            {
                _OPENING_ANALYSIS: 1,
                _SECOND_ANALYSIS: 1,
                _THIRD_ANALYSIS: 1,
            },
        )


if __name__ == "__main__":
    unittest.main()
