# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Tests for implementing retry behavior."""

from __future__ import annotations

import unittest

from tests.workflow.stages.implementing import retry_test_support as support

IssueScenario = support.IssueScenario

ACTION_COMMENT_ID = support.ACTION_COMMENT_ID
DEFAULT_SESSION = support.DEFAULT_SESSION
DONE_MESSAGE = support.DONE_MESSAGE
EXPIRED_WINDOW_HOURS = support.EXPIRED_WINDOW_HOURS
FakeComment = support.FakeComment
FakeGitHubClient = support.FakeGitHubClient
FakeUser = support.FakeUser
HUMAN_REPLY_ID = support.HUMAN_REPLY_ID
KEY_AWAITING_HUMAN = support.KEY_AWAITING_HUMAN
KEY_PARK_REASON = support.KEY_PARK_REASON
KEY_RETRY_CAP_NOTICE = support.KEY_RETRY_CAP_NOTICE
KEY_RETRY_COUNT = support.KEY_RETRY_COUNT
LABEL_IMPLEMENTING = support.LABEL_IMPLEMENTING
OK_MESSAGE = support.OK_MESSAGE
PHASE_DELIVERED = support.PHASE_DELIVERED
PHASE_RECONCILED = support.PHASE_RECONCILED
PHASE_STANDING = support.PHASE_STANDING
RETRY_CAP_PARK_ISSUE = support.RETRY_CAP_PARK_ISSUE
RETRY_CAP_TICKS = support.RETRY_CAP_TICKS
RUN_AGENT = support.RUN_AGENT
_RetryCapFixtureMixin = support._RetryCapFixtureMixin
_RetryCapParkMixin = support._RetryCapParkMixin
_agent = support._agent
_iso_hours_ago = support._iso_hours_ago
config = support.config
make_issue = support.make_issue
patch = support.patch
session = support.session


class HandleImplementingRetryCapTest(
    unittest.TestCase,
    _RetryCapFixtureMixin,
):
    """Bound the implementing loop with MAX_RETRIES_PER_DAY in pinned state.

    Resumes on human reply and recovered-worktree pushes are explicitly NOT
    counted; only fresh codex spawns consume the budget.
    """

    def test_fourth_fresh_attempt_parks_before_codex(self) -> None:
        # Run three fresh attempts that each park as a question, then assert
        # the fourth tick parks before run_agent is called. Pin the cap at 3
        # so the test is hermetic against a `MAX_RETRIES_PER_DAY` env
        # override that would otherwise let the fourth tick spawn through.
        scenario = IssueScenario(*self._seeded())

        with patch.object(config, "MAX_RETRIES_PER_DAY", 3):
            # First three ticks: codex returns no commits + a question, parking on
            # awaiting_human. Each tick consumes one retry from the budget.
            for tick in range(3):
                self._run_implementing(
                    scenario.github,
                    scenario.issue,
                    run_agent=_agent(last_message=f"q{tick}"),
                    has_new_commits=False,
                )
                # Clear the awaiting-human flag manually so the next tick takes
                # the fresh-spawn branch again (simulating that the human answered
                # but the agent still failed to commit). We do NOT update
                # last_action_comment_id, but we also drop awaiting_human so the
                # else branch runs.
                pinned_data = scenario.github._pinned[8].data
                pinned_data["awaiting_human"] = False

            self.assertEqual(scenario.github.pinned_data(8).get(KEY_RETRY_COUNT), 3)
            self.assertIsNotNone(scenario.github.pinned_data(8).get("retry_window_start"))

            # Fourth tick: must park before codex spawns.
            mocks = self._run_implementing(
                scenario.github,
                scenario.issue,
                run_agent=_agent(last_message="should not run"),
                has_new_commits=False,
            )

        mocks[RUN_AGENT].assert_not_called()
        self.assertTrue(scenario.github.pinned_data(8).get("awaiting_human"))
        last_comment = scenario.github.posted_comments[-1][1]
        self.assertIn("hit retry cap (3/day)", last_comment)
        self.assertIn("Window opened at", last_comment)

    def test_successful_commits_clear_counter(self) -> None:
        # Pre-seed near-cap state, then run a successful tick (commits + clean
        # tree + push succeeds). The PR-open path must clear the budget.
        gh, issue = self._seeded(
            retry_count=2,
            retry_window_start=_iso_hours_ago(1),
            retry_cap_continued=1,
        )

        self._run_implementing(
            gh,
            issue,
            run_agent=_agent(session_id=DEFAULT_SESSION, last_message=DONE_MESSAGE),
            has_new_commits=[False, True],
            dirty_files=(),
            push_branch=True,
        )

        pinned_data = gh.pinned_data(8)
        self.assertEqual(pinned_data.get(KEY_RETRY_COUNT), 0)
        # window_start cleared back to falsy, and with it the attempts a
        # continuation left on this issue's budget.
        self.assertFalse(pinned_data.get("retry_window_start"))
        self.assertFalse(pinned_data.get("retry_cap_continued"))
        self.assertEqual(len(gh.opened_prs), 1)

    def test_window_older_than_one_day_resets_counter(self) -> None:
        # Cap exhausted but the window is 25h old: next fresh attempt opens a
        # new window with count=1 and codex actually spawns.
        gh, issue = self._seeded(
            retry_count=3,
            retry_window_start=_iso_hours_ago(EXPIRED_WINDOW_HOURS),
        )

        mocks = self._run_implementing(
            gh,
            issue,
            run_agent=_agent(last_message="ask again"),
            has_new_commits=False,
        )

        mocks[RUN_AGENT].assert_called_once()
        pinned_data = gh.pinned_data(8)
        # Reset to 0 by the window-expired branch, then incremented to 1.
        self.assertEqual(pinned_data.get(KEY_RETRY_COUNT), 1)
        # Park message must NOT be the cap message.
        last_comment = gh.posted_comments[-1][1]
        self.assertNotIn("hit retry cap", last_comment)

    def test_human_resume_keeps_counter(self) -> None:
        gh = FakeGitHubClient()
        issue = make_issue(9, label=LABEL_IMPLEMENTING)
        reply = FakeComment(
            id=HUMAN_REPLY_ID,
            body="please use sqlite",
            user=FakeUser("alice"),
        )
        issue.comments.append(reply)
        gh.add_issue(issue)
        gh.seed_state(
            9,
            awaiting_human=True,
            last_action_comment_id=ACTION_COMMENT_ID,
            codex_session_id="sess-old",
            retry_count=2,
            retry_window_start=_iso_hours_ago(1),
        )

        mocks = self._run_implementing(
            gh,
            issue,
            run_agent=_agent(session_id="sess-old", last_message=OK_MESSAGE),
            has_new_commits=[True],
            dirty_files=(),
            push_branch=True,
        )

        # Resume happened (codex was called once with the followup comment).
        mocks[RUN_AGENT].assert_called_once()
        # retry_count NOT incremented by the resume itself. The successful
        # _on_commits then clears it to 0.
        pinned_data = gh.pinned_data(9)
        self.assertEqual(pinned_data.get(KEY_RETRY_COUNT), 0)


class RetryCapParkDeliveryTest(unittest.TestCase, _RetryCapParkMixin):
    """What a refused fresh spawn says, and how often it says it.

    The gate is asked again on every eligible tick -- that is what makes the
    refusal idempotent -- so the notice is the one thing that may not be.
    """

    def test_repeated_ticks_park_once_and_say_it_once(self) -> None:
        gh, issue = self._exhausted()

        refusals = [
            self._refuse(gh, issue) for _ in range(RETRY_CAP_TICKS)
        ]

        self.assertEqual(refusals, [False, False, False])
        self.assertEqual(len(gh.posted_comments), 1)
        self.assertIn("hit retry cap", gh.posted_comments[0][1])
        self.assertEqual(
            self._phases(gh),
            [PHASE_DELIVERED, PHASE_STANDING, PHASE_STANDING],
        )
        # Durable and stable: the park survives the restart each re-read is.
        pinned = gh.pinned_data(RETRY_CAP_PARK_ISSUE)
        self.assertTrue(pinned.get(KEY_AWAITING_HUMAN))
        self.assertEqual(pinned.get(KEY_PARK_REASON), "retry_cap")
        self.assertEqual(pinned.get(KEY_RETRY_COUNT), RETRY_CAP_TICKS)

    def test_an_unbounded_cap_does_not_lift_the_park(self) -> None:
        # The gate answers the park before it answers the cap, so an operator
        # who turns the budget off does not resume a workflow whose notice
        # asked for a human -- only an explicit continuation does.
        gh, issue = self._exhausted()

        self._refuse(gh, issue)
        lifted = self._refuse(gh, issue, cap=0)

        self.assertFalse(lifted)
        self.assertEqual(len(gh.posted_comments), 1)
        self.assertEqual(
            self._phases(gh), [PHASE_DELIVERED, PHASE_STANDING],
        )

    def test_a_notice_on_the_thread_is_not_repeated(self) -> None:
        # A tick that posted and died before its write leaves the sentence
        # owed by a thread that already has it.
        gh, issue = self._exhausted()

        self._refuse(gh, issue, persist=False)
        self._refuse(gh, issue)

        self.assertEqual(len(gh.posted_comments), 1)
        self.assertEqual(
            self._phases(gh), [PHASE_DELIVERED, PHASE_RECONCILED],
        )

    def test_an_unreadable_thread_says_nothing(self) -> None:
        # The window the reconciliation exists for: a notice that landed under
        # a pinned write that then failed is on the thread, and a read that
        # fails cannot tell that from a thread with nothing on it. Posting on
        # a failed read is the duplicate this protocol is here to stop, so the
        # tick says nothing and the notice stays owed for the next one.
        gh, issue = self._exhausted()
        self._refuse(gh, issue, persist=False)

        with patch.object(gh, "comments_after", side_effect=RuntimeError):
            quiet = self._refuse(gh, issue)
        said_later = self._refuse(gh, issue)

        self.assertEqual([quiet, said_later], [False, False])
        self.assertEqual(len(gh.posted_comments), 1)
        # The tick that could read the thread found the sentence on it and
        # recorded it as said rather than saying it twice.
        self.assertEqual(
            self._phases(gh), [PHASE_DELIVERED, PHASE_RECONCILED],
        )

    def test_a_park_that_cannot_persist_says_nothing(self) -> None:
        # The park goes down before the sentence goes out. A notice nothing
        # durable backs is one no later tick would reconcile -- and the window
        # under it would roll over a day later with the issue running again
        # beneath a comment saying it had stopped.
        gh, issue = self._exhausted()
        state = gh.read_pinned_state(issue)

        with (
            patch.object(config, "MAX_RETRIES_PER_DAY", RETRY_CAP_TICKS),
            patch.object(gh, "write_pinned_state", side_effect=RuntimeError),
            self.assertRaises(RuntimeError),
        ):
            session._check_and_increment_retry_budget(gh, issue, state)

        self.assertEqual(gh.posted_comments, [])
        self.assertFalse(
            gh.pinned_data(RETRY_CAP_PARK_ISSUE).get(KEY_AWAITING_HUMAN),
        )


class RetryCapNoticeReplayTest(unittest.TestCase, _RetryCapParkMixin):
    """The sentence a stranded park is still owed, said at the next entry.

    A park routes the tick to a resume or to nothing, and neither road passes
    the gate that took it, so nothing below stage entry would ever say it.
    """

    def test_a_stranded_notice_is_said_at_stage_entry(self) -> None:
        client, parked = self._exhausted()
        with patch.object(client, "comments_after", side_effect=RuntimeError):
            self._refuse(client, parked)

        mocks = self._run_implementing(
            client, parked, run_agent=_agent(), has_new_commits=False,
        )

        mocks[RUN_AGENT].assert_not_called()
        self.assertEqual(len(client.posted_comments), 1)
        self.assertIn("hit retry cap", client.posted_comments[0][1])
        self.assertEqual(self._phases(client), [PHASE_DELIVERED])
        # Said once and settled durably, so the tick after it says nothing.
        self.assertNotIn(
            KEY_RETRY_CAP_NOTICE, client.pinned_data(RETRY_CAP_PARK_ISSUE),
        )
