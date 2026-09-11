# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Which comments past a park's watermark are a human asking for a change.

Not the orchestrator's own, and saying so is not a nicety. Every park in this
stage posts its notice before the write that records posting it, so a process
dying between the two leaves a sentence on the thread with nothing on the
record naming it -- and the default `ALLOWED_ISSUE_AUTHORS` is empty, which
trusts every author there is. Read as guidance, the orchestrator's own words
become a request for changes and a developer is paid to answer them.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from orchestrator.workflow.engine import comments as _comments
from orchestrator.workflow.stages.implementing import (
    resume as _resume,
    state as _state,
)
from tests.support.fakes import FakeComment, FakeGitHubClient, FakeUser, make_issue
from tests.workflow.fixtures import _TEST_SPEC, LABEL_IMPLEMENTING

_ISSUE_NUMBER = 614
_PARKED_AT = 900
_NOTICE = "this issue is waiting on a human"
_GUIDANCE = "make it smaller, please"
_TRUSTED_AUTHOR = "alice"
_RESUME_DEV_WITH_TEXT = "_resume_dev_with_text"


class ResumeAuthorshipTest(unittest.TestCase):
    """What the generic resume treats as somebody having replied."""

    def setUp(self) -> None:
        self.github = FakeGitHubClient()
        self.issue = make_issue(_ISSUE_NUMBER, label=LABEL_IMPLEMENTING)
        self.github.add_issue(self.issue)
        self.github.seed_state(
            _ISSUE_NUMBER, **{_state._LAST_ACTION_COMMENT_ID: _PARKED_AT},
        )
        self.state = self.github.read_pinned_state(self.issue)

    def test_our_own_notice_resumes_nobody(self) -> None:
        # The whole point: a notice this stage posted is not a human asking
        # for anything, and paying an agent to answer it is the one outcome
        # every park here exists to avoid.
        self._we_say(_NOTICE)

        with patch.object(_resume, _RESUME_DEV_WITH_TEXT) as resumed:
            answered = self._resumes()
            resumed.assert_not_called()

        self.assertIsNone(answered)

    def test_our_own_notice_consumes_nothing(self) -> None:
        # And it moves no watermark either. A human replying between this
        # tick and the next would be behind a mark that had crossed them.
        self._we_say(_NOTICE)

        with patch.object(_resume, _RESUME_DEV_WITH_TEXT):
            self._resumes()

        self.assertEqual(
            self.state.get(_state._LAST_ACTION_COMMENT_ID), _PARKED_AT,
        )

    def test_a_reply_under_our_notice_still_resumes(self) -> None:
        # The other direction, and the one over-filtering would break: the
        # human wrote first and our notice landed on top, so their words are
        # still the ones the developer is owed.
        spoke = self._they_say(_GUIDANCE)
        self._we_say(_NOTICE)

        with patch.object(_resume, _RESUME_DEV_WITH_TEXT) as resumed:
            self._resumes()
            resumed.assert_called_once()
            self.assertIn(_GUIDANCE, resumed.call_args.args[4])

        self.assertEqual(
            self.state.get(_state._LAST_ACTION_COMMENT_ID), spoke,
        )

    def _we_say(self, body: str) -> int:
        """Post one comment the way this workflow posts every one of them."""
        posted = _comments._post_issue_comment(
            self.github, self.issue, self.state, body,
        )
        self.github.write_pinned_state(self.issue, self.state)
        return posted.id

    def _they_say(self, body: str) -> int:
        """Add one trusted human reply past the park's watermark."""
        identified = self.github.next_reply_id(self.issue)
        self.issue.comments.append(
            FakeComment(identified, body, user=FakeUser(_TRUSTED_AUTHOR)),
        )
        return identified

    def _resumes(self):
        return _resume._resume_developer_on_human_reply(
            self.github, _TEST_SPEC, self.issue, self.state,
        )


if __name__ == "__main__":
    unittest.main()
