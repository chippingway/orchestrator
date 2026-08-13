# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What keeps a replayed discussion round on the agent that opened it.

A round can end with no disposition -- a mid-run pause withholds every one by
contract, a crash takes them with it -- and the next tick opens it again. The
configured `DECOMPOSE_AGENT` can change between those two ticks, so the spec
pinned at the first spawn is read back rather than re-resolved: a replay that
followed the new config would move the conversation onto a backend and argument
set that never ran on this issue, and then overwrite the pin with them.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from tests.workflow.fixtures import _agent

from tests.workflow.stages.discussion.discussion_test_support import (
    DISCUSSION_RESPONSE,
    DISCUSSION_SESSION,
    FLIPPED_ARGS,
    FLIPPED_BACKEND,
    FLIPPED_SPEC,
    KEY_DISCUSSION_AGENT,
    RUN_AGENT,
)
from tests.workflow.stages.discussion.discussion_test_support import (
    SPEC_ARGS,
    SPEC_BACKEND,
    SPEC_WITH_ARGS,
    _DiscussionWorkflowMixin,
    _configured_spec,
    _paused_view,
    _seed_discussion,
)

_REPLAY_ISSUE_NUMBER = 1000
_FIRST_SPAWN_ISSUE_NUMBER = 1001


class DiscussionSessionLockTest(unittest.TestCase, _DiscussionWorkflowMixin):

    def test_a_first_spawn_takes_the_configured_spec(self) -> None:
        gh, issue = _seed_discussion(_FIRST_SPAWN_ISSUE_NUMBER)

        with _configured_spec(SPEC_WITH_ARGS, SPEC_BACKEND, SPEC_ARGS):
            mocks = self._run_discussion(
                gh,
                issue,
                run_agent=_agent(
                    session_id=DISCUSSION_SESSION,
                    last_message=DISCUSSION_RESPONSE,
                ),
            )

        self._assert_ran_under(mocks, SPEC_BACKEND, SPEC_ARGS)
        self.assertEqual(
            gh.pinned_data(issue.number)[KEY_DISCUSSION_AGENT], SPEC_WITH_ARGS,
        )

    def test_a_replay_keeps_the_locked_spec(self) -> None:
        # Round one is withheld by a mid-run pause, so the issue keeps its
        # anchor and its pin. The operator then flips `DECOMPOSE_AGENT` before
        # the replay: the round that reopens is still the one this issue's
        # discussion belongs to, so it runs under the pinned spec.
        gh, issue = _seed_discussion(_REPLAY_ISSUE_NUMBER)

        with _configured_spec(SPEC_WITH_ARGS, SPEC_BACKEND, SPEC_ARGS):
            with patch.object(
                gh,
                "get_issue",
                return_value=_paused_view(_REPLAY_ISSUE_NUMBER, "paused"),
            ):
                self._run_discussion(
                    gh,
                    issue,
                    run_agent=_agent(last_message=DISCUSSION_RESPONSE),
                )

        with _configured_spec(FLIPPED_SPEC, FLIPPED_BACKEND, FLIPPED_ARGS):
            replay_mocks = self._run_discussion(
                gh,
                issue,
                run_agent=_agent(
                    session_id=DISCUSSION_SESSION,
                    last_message=DISCUSSION_RESPONSE,
                ),
            )

        self._assert_ran_under(replay_mocks, SPEC_BACKEND, SPEC_ARGS)
        # And the flip did not overwrite the pin on the way through.
        self.assertEqual(
            gh.pinned_data(issue.number)[KEY_DISCUSSION_AGENT], SPEC_WITH_ARGS,
        )

    def _assert_ran_under(self, mocks, backend: str, extra_args: tuple) -> None:
        mocks[RUN_AGENT].assert_called_once()
        spawn_call = mocks[RUN_AGENT].call_args
        self.assertEqual(spawn_call.args[0], backend)
        self.assertEqual(spawn_call.kwargs.get("extra_args"), extra_args)


if __name__ == "__main__":
    unittest.main()
