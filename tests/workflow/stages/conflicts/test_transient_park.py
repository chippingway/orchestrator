# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from orchestrator.git.base_sync import pre_pr as _base_sync_pre_pr
from tests.support.fakes import FakeComment, FakeUser
from tests.workflow.fixtures import _agent
from tests.workflow.stages.conflicts.conflicts_test_support import (
    RESOLVED_HEAD_SHA,
    _ResolvingConflictMixin,
)

CONFLICT_ISSUE = 200
CONFLICT_FILE = "a.py"
BEFORE_HEAD = "be40e5ba" * 5

AWAITING_HUMAN = "awaiting_human"
PARK_REASON = "park_reason"
AGENT_TIMEOUT = "agent_timeout"
CONFLICT_ROUND = "conflict_round"

REBASE_SEAM = "_rebase_base_into_worktree"
RUN_AGENT = "run_agent"
PUSH_BRANCH = "_push_branch"
LABEL_VALIDATING = "workflow:validating"

# What `_authed_fetch` answers on a tick the remote is briefly unreachable.
_REFUSED = MagicMock(returncode=1, stdout="", stderr="no route to host")

FETCH_NOTICE = "failed during conflict resolution"
TIMEOUT_NOTICE = "timed out resolving rebase conflicts"

# The reply an operator leaves on the park, and who leaves it.
HUMAN_REPLY_ID = 9000
HUMAN_LOGIN = "alice"
HUMAN_REPLY = "skip the vendored file and finish the rebase"


class ResolvingConflictTransientOverHumanParkTest(
    unittest.TestCase, _ResolvingConflictMixin,
):
    """A reading that did not happen, taken over a park a person owes.

    Both kinds of refusal set the awaiting-human flag, and only the durable
    reason tells them apart: a transient one is retried by the tick that finds
    it, and a human one waits. So recording the transient reason over a
    standing question would answer the question on the human's behalf -- the
    next successful reading would skip the resume, rebase, push, count the
    round, and hand a reviewer work nobody was asked about.
    """

    def test_a_transient_refusal_keeps_the_park(self) -> None:
        github, issue = self._parked_on_the_agent()

        self._refusing_the_fetch(github, issue)

        pinned_state = github.pinned_data(CONFLICT_ISSUE)
        self.assertEqual(pinned_state.get(PARK_REASON), AGENT_TIMEOUT)
        self.assertTrue(pinned_state.get(AWAITING_HUMAN))
        # The notice an operator has to act on is the timeout's, and a
        # remote that stays unreachable is reached every poll.
        self.assertEqual(
            [body for _, body in github.posted_comments if FETCH_NOTICE in body],
            [],
        )

    def test_the_tick_after_it_still_waits(self) -> None:
        # The tick whose fetch lands reads the same standing question, so
        # nothing is rebased, pushed, counted, or handed on while it is open.
        github, issue = self._parked_on_the_agent()
        self._refusing_the_fetch(github, issue)

        mocks = self._clean_tick(github, issue)

        mocks[PUSH_BRANCH].assert_not_called()
        mocks[RUN_AGENT].assert_not_called()
        self.assertNotIn(
            (CONFLICT_ISSUE, LABEL_VALIDATING), github.label_history,
        )
        pinned_state = github.pinned_data(CONFLICT_ISSUE)
        self.assertEqual(pinned_state.get(CONFLICT_ROUND), 0)
        self.assertTrue(pinned_state.get(AWAITING_HUMAN))

    def test_the_reply_it_stood_over_is_answered(self) -> None:
        # The consumed-comment watermark is the other half of the same park:
        # re-parking ratchets it past everything on the thread. Recorded over
        # the question, the transient reason both swallows the answer and
        # sends the tick that follows to the rebase instead of the dev.
        github, issue = self._parked_on_the_agent()
        issue.comments.append(FakeComment(
            id=HUMAN_REPLY_ID, body=HUMAN_REPLY, user=FakeUser(HUMAN_LOGIN),
        ))
        # The reply is answered as a reply rather than as requirements drift,
        # which is what a baseline taken over the thread as it stands leaves.
        self._seed_with_baseline_hash(github, issue)
        self._refusing_the_fetch(github, issue)

        mocks = self._clean_tick(github, issue)

        mocks[RUN_AGENT].assert_called_once()
        self.assertIn(HUMAN_REPLY, mocks[RUN_AGENT].call_args.args[1])

    def _parked_on_the_agent(self):
        """The tick that leaves a question only a person can answer."""
        github, issue = self._seed()[:2]
        self._run_with_merge(
            github, issue,
            merge_succeeded=False,
            conflicted_files=[CONFLICT_FILE],
            head_shas=[BEFORE_HEAD, "after"],
            run_agent_result=_agent(
                session_id="dev-sess", last_message="", timed_out=True,
            ),
        )
        self.assertIn(TIMEOUT_NOTICE, github.posted_comments[-1][1])
        return github, issue

    def _refusing_the_fetch(self, github, issue) -> None:
        """One tick whose branch fetch does not land."""
        self._run_with_merge(
            github, issue,
            head_shas=[BEFORE_HEAD, RESOLVED_HEAD_SHA],
            authed_fetch_result=_REFUSED,
        )

    def _clean_tick(self, github, issue):
        """The tick after it, where every reading answers."""
        with patch.object(
            _base_sync_pre_pr, REBASE_SEAM, MagicMock(return_value=(True, [])),
        ):
            return self._run_resolving_conflict(
                github, issue,
                run_agent=_agent(session_id="dev-sess", last_message="done"),
                push_branch=True,
                head_shas=[BEFORE_HEAD, RESOLVED_HEAD_SHA],
            )


if __name__ == "__main__":
    unittest.main()
