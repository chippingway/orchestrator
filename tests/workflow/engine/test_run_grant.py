# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The one command that buys an issue past its spent agent-run ledger.

What is pinned here is everything that command has to be before it moves a
number: a line of its own, a trusted author's, and an exact whole count inside
the bound. Everything else leaves the ledger where it found it -- the
allowance and the runs spent against it both -- and says so once, or says
nothing at all where saying something would be answering an outsider.

A grant is pinned as an absolute ceiling rather than an increment, because
that is what makes it safe to hand out before the write that records it: read
twice, the same command buys the same runs.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from orchestrator import config
from orchestrator.workflow.engine import run_grant as _run_grant
from tests.workflow.engine import (
    run_grant_test_support as grant,
    run_limit_test_support as support,
)

_ADDED = 3

_GRANTED_ALLOWANCE = support.ALLOWANCE + _ADDED

_VALID = f"/orchestrator add-agent-runs {_ADDED}"

_ALLOWLIST = "ALLOWED_ISSUE_AUTHORS"

_FIRST_ASK = support.WATERMARK + 1

_SECOND_ASK = support.WATERMARK + 2

# Comfortably past `sys.int_info.default_max_str_digits`, the length at which
# the interpreter refuses to build an integer out of a decimal string.
_OVERLONG_DIGITS = 5000

# What somebody writes while the tick is answering the command above it. Not a
# command itself: what it stands for is any word a stage below is still owed.
_RACING_WORDS = "hold off on this until Friday please"

# A count is the whole of what this command says, so everything that is not
# one whole number inside the bound reads the same way: nothing bought.
_UNBUYABLE = (
    "",
    "0",
    "000",
    "-3",
    "+3",
    "3.5",
    "three",
    "0x3",
    "\N{ARABIC-INDIC DIGIT THREE}",
    str(_run_grant.MAX_RUNS_PER_COMMAND + 1),
    # A count no bound could hold, and one `int()` refuses to convert at all
    # past the interpreter's own limit -- so it has to be turned away before
    # it is converted rather than raised over.
    "9" * _OVERLONG_DIGITS,
)

# Text that mentions the command without asking for anything: a line has to be
# the command and nothing else, which is what keeps the receipts below -- both
# of which spell it -- from being read back as fresh requests.
_NOT_A_REQUEST = (
    f"do we just run `{_VALID}` here?",
    "/orchestrator add-agent-runs3",
    "/orchestrator continue",
    "/orchestrator add-review-rounds 3",
    # Both receipts this owner writes. The thread they land on is the one the
    # next tick reads for a request, and a deployment that trusts every author
    # trusts the orchestrator's own account too.
    _run_grant._GRANT_NOTICE.format(
        added=_ADDED,
        allowance=_GRANTED_ALLOWANCE,
        used=support.ALLOWANCE,
        marker=_run_grant._GRANTED_MARKER.format(
            issue=support.ISSUE_NUMBER, comment=_FIRST_ASK,
        ),
    ),
    _run_grant._REFUSAL_NOTICE.format(
        mentions=config.HITL_MENTIONS,
        maximum=_run_grant.MAX_RUNS_PER_COMMAND,
        marker=_run_grant._REFUSED_MARKER.format(
            issue=support.ISSUE_NUMBER, comment=_FIRST_ASK,
        ),
    ),
)


class CommandGrammarTest(unittest.TestCase):
    """What a comment has to say before anything reads it as a request."""

    def test_only_an_exact_bounded_count_buys_runs(self) -> None:
        for asked in _UNBUYABLE:
            with self.subTest(asked=asked):
                self.assertIsNone(_run_grant._added_runs(asked))
        for asked in ("1", "007", str(_run_grant.MAX_RUNS_PER_COMMAND)):
            with self.subTest(asked=asked):
                self.assertEqual(_run_grant._added_runs(asked), int(asked))

    def test_a_request_is_a_line_and_nothing_else(self) -> None:
        for body in _NOT_A_REQUEST:
            with self.subTest(body=body):
                self.assertIsNone(
                    _run_grant._requested([grant.command(body)]),
                )

    def test_the_last_command_is_the_request(self) -> None:
        # A batch is read in thread order, so a human who wrote the command
        # twice meant the second one -- and a count corrected below a typo is
        # the request rather than the line it corrects.
        request = _run_grant._requested([
            grant.command(
                "/orchestrator add-agent-runs 9", comment_id=_FIRST_ASK,
            ),
            grant.command(
                f"scratch that\n{_VALID}\n/orchestrator add-agent-runs 7",
                comment_id=_SECOND_ASK,
            ),
        ])

        self.assertEqual(request.asked, "7")
        self.assertEqual(request.added, 7)
        self.assertEqual(request.comment_id, _SECOND_ASK)


class _RacingPost:
    """The orchestrator's own post, with somebody else's comment landing first.

    Stands in for the one window where this owner can be overtaken: the batch
    has been read, the receipt is not written yet, and the comment that
    arrives in between is one no read here has seen.
    """

    def __init__(self, gh) -> None:
        self._posting = gh.comment

    def __call__(self, issue, body):
        issue.comments.append(grant.command(
            _RACING_WORDS, comment_id=grant.RACING_COMMENT_ID,
        ))
        return self._posting(issue, body)


class _ParkCase(unittest.TestCase):
    """One issue standing on a spent ledger, and what a thread says to it."""

    def _lift(self, *comments, state=None):
        self._thread(*comments)
        self.state = grant.spent_state() if state is None else state
        return _run_grant._lifts_the_park(self.gh, self.issue, self.state)

    def _thread(self, *comments) -> None:
        client, issue = support.issue_and_client(*comments)
        self.gh = client
        self.issue = issue

    def _lost_the_write(self, *comments) -> None:
        """One tick that wrote its receipt to the thread and nothing else.

        The window every receipt here is idempotent across: the post landed,
        the write that would have consumed the command did not, and the next
        tick reads the same request off the same thread.
        """
        self._thread(*comments)
        with (
            patch.object(
                self.gh, "write_pinned_state", side_effect=RuntimeError("502"),
            ),
            self.assertRaises(RuntimeError),
        ):
            _run_grant._lifts_the_park(
                self.gh, self.issue, grant.spent_state(),
            )

    def _replayed(self):
        """The next tick, reading pinned state the lost write never moved."""
        self.state = grant.spent_state()
        return _run_grant._lifts_the_park(self.gh, self.issue, self.state)

    def _lift_racing(self, *comments):
        """One tick answering a command while the thread grows under it.

        The only window in which it can: the batch is read once, and the
        receipt is written after that read.
        """
        self._thread(*comments)
        self.state = grant.spent_state()
        with patch.object(
            self.gh, "comment", side_effect=_RacingPost(self.gh),
        ):
            return _run_grant._lifts_the_park(
                self.gh, self.issue, self.state,
            )

    def _recorded(self) -> dict:
        return self.gh.pinned_data(support.ISSUE_NUMBER)

    def _assert_ledger_untouched(self) -> None:
        self.assertNotIn(support.ALLOWANCE_FIELD, self.state.data)
        self.assertEqual(self.state.get(support.USED_FIELD), support.ALLOWANCE)


class GrantTest(_ParkCase):
    """What a valid command buys, and what it leaves alone."""

    def test_a_valid_command_buys_exactly_used_plus_n(self) -> None:
        lifted = self._lift(grant.command(_VALID))

        self.assertTrue(lifted)
        recorded = self._recorded()
        self.assertEqual(
            recorded[support.ALLOWANCE_FIELD], _GRANTED_ALLOWANCE,
        )
        # Nothing here returns a run: what widens is the ceiling.
        self.assertEqual(recorded[support.USED_FIELD], support.ALLOWANCE)
        self.assertFalse(recorded[support.AWAITING_HUMAN])
        self.assertIsNone(recorded[support.PARK_REASON])
        self.assertEqual(support.phases(self.gh), [support.GRANTED])

    def test_the_command_is_said_and_consumed_once(self) -> None:
        self._lift(grant.command(_VALID))

        said = self.gh.posted_comments
        self.assertEqual(len(said), 1)
        self.assertIn(str(_GRANTED_ALLOWANCE), said[0][1])
        # The receipt is consumed with the command, so the road the grant
        # opens does not read the orchestrator answering itself as guidance.
        self.assertEqual(
            self._recorded()[support.LAST_ACTION_COMMENT_ID],
            self.gh.latest_comment_id(self.issue),
        )

    def test_a_lost_write_says_it_once(self) -> None:
        # The acknowledgement lands and the write that records it does not, so
        # the next tick reads the same command off the same thread. An
        # allowance written as `used + N` says the same thing then -- an
        # increment would not -- and the receipt already on the thread is what
        # keeps the same sentence from being said a second time.
        self._lost_the_write(grant.command(_VALID))

        lifted = self._replayed()

        self.assertTrue(lifted)
        self.assertEqual(len(self.gh.posted_comments), 1)
        self.assertEqual(
            self._recorded()[support.ALLOWANCE_FIELD], _GRANTED_ALLOWANCE,
        )

    def test_an_owed_sentence_reads_no_command(self) -> None:
        # The hold above says that sentence and moves the response boundary
        # past everything under the old one, so a command read here would be
        # bought and then consumed by the notice explaining the park.
        lifted = self._lift(
            grant.command(_VALID), state=grant.spent_state(owing=True),
        )

        self.assertFalse(lifted)
        self.assertEqual(self.gh.posted_comments, [])
        self._assert_ledger_untouched()


class RefusalTest(_ParkCase):
    """What every other request earns, and how often it earns it."""

    def test_an_unbuyable_request_changes_nothing(self) -> None:
        for asked in _UNBUYABLE:
            with self.subTest(asked=asked):
                lifted = self._lift(
                    grant.command(f"/orchestrator add-agent-runs {asked}"),
                )

                self.assertFalse(lifted)
                self._assert_ledger_untouched()
                self.assertTrue(self.state.get(support.AWAITING_HUMAN))
                self.assertEqual(len(self.gh.posted_comments), 1)
                self.assertEqual(support.phases(self.gh), [support.REFUSED])

    def test_the_receipt_names_the_bound(self) -> None:
        self._lift(grant.command("/orchestrator add-agent-runs 999"))

        said = self.gh.posted_comments[0][1]
        self.assertIn(str(_run_grant.MAX_RUNS_PER_COMMAND), said)
        self.assertIn(config.HITL_MENTIONS, said)
        self.assertEqual(
            self._recorded()[support.LAST_ACTION_COMMENT_ID],
            self.gh.latest_comment_id(self.issue),
        )

    def test_a_receipt_on_the_thread_is_not_repeated(self) -> None:
        # The post and the write that consumes the request cannot be made one
        # operation, so a tick that died between them re-reads the request --
        # and the marker its own receipt carries is what stops the repeat.
        asked = grant.command("/orchestrator add-agent-runs 0")
        self._lost_the_write(asked)
        receipt = self.gh.posted_comments[0][1]

        replayed = self._replayed()

        self.assertFalse(replayed)
        self.assertEqual(len(self.gh.posted_comments), 1)
        self.assertIn(
            _run_grant._REFUSED_MARKER.format(
                issue=support.ISSUE_NUMBER, comment=asked.id,
            ),
            receipt,
        )
        self._assert_ledger_untouched()

    def test_an_outsiders_marker_silences_nothing(self) -> None:
        # A marker is plain text on a public thread. Read from anybody, one
        # pasted below the request would suppress the answer a human is owed.
        marker = _run_grant._REFUSED_MARKER.format(
            issue=support.ISSUE_NUMBER, comment=_FIRST_ASK,
        )
        self._lift(
            grant.command(
                "/orchestrator add-agent-runs x", comment_id=_FIRST_ASK,
            ),
            grant.command(
                marker, comment_id=_SECOND_ASK, author=support.OUTSIDER,
            ),
        )

        self.assertEqual(len(self.gh.posted_comments), 1)


class UnansweredRequestTest(_ParkCase):
    """The threads this owner buys nothing from and says nothing to."""

    def test_an_untrusted_command_buys_nothing(self) -> None:
        # What the command spends is agent time, so it is worth exactly the
        # trust of the account that wrote it -- and answering an outsider
        # would spend the watermark a real operator is read against.
        with patch.object(config, _ALLOWLIST, (grant.OPERATOR,)):
            lifted = self._lift(
                grant.command(_VALID, author=support.OUTSIDER),
            )

        self.assertFalse(lifted)
        self.assertEqual(self.gh.posted_comments, [])
        self.assertEqual(self.gh.write_state_calls, 0)
        self._assert_ledger_untouched()

    def test_only_the_spent_ledger_park_is_answered(self) -> None:
        # Read anywhere else, the same words would clear a park waiting for
        # something they do not say, or hand a running issue a ceiling
        # nobody decided.
        for reason in (None, "retry_cap", "agent_question"):
            with self.subTest(park_reason=reason):
                parked = grant.spent_state(**{
                    support.AWAITING_HUMAN: reason is not None,
                    support.PARK_REASON: reason,
                })

                lifted = self._lift(grant.command(_VALID), state=parked)

                self.assertFalse(lifted)
                self.assertEqual(self.gh.posted_comments, [])
                self._assert_ledger_untouched()

    def test_a_thread_with_no_command_is_left_alone(self) -> None:
        lifted = self._lift(grant.command("any update here?"))

        self.assertFalse(lifted)
        self.assertEqual(self.gh.posted_comments, [])
        self.assertEqual(self.gh.write_state_calls, 0)

    def test_an_unreadable_thread_holds_the_park(self) -> None:
        # A park held one poll too long is answered by the next read, while a
        # grant handed out on a thread nobody could read buys runs no human
        # asked for.
        self._thread(grant.command(_VALID))
        self.state = grant.spent_state()

        with patch.object(
            self.gh, "comments_after", side_effect=RuntimeError("502"),
        ):
            lifted = _run_grant._lifts_the_park(
                self.gh, self.issue, self.state,
            )

        self.assertFalse(lifted)
        self.assertEqual(self.gh.posted_comments, [])
        self._assert_ledger_untouched()


class ConcurrentCommentTest(_ParkCase):
    """What a tick may mark answered is what it read, and nothing after it."""

    def test_a_racing_comment_stays_unread(self) -> None:
        # The thread is read once and the receipt is written after that read.
        # A watermark taken from the thread as it stands afterwards would mark
        # a comment nobody here has seen as answered -- and a comment under
        # the mark is not delayed, it is lost: every stage below decides what
        # is unread by exactly that number.
        for asked in (_VALID, "/orchestrator add-agent-runs 0"):
            with self.subTest(asked=asked):
                self._lift_racing(grant.command(asked))

                consumed = self._recorded()[support.LAST_ACTION_COMMENT_ID]
                self.assertEqual(consumed, grant.COMMAND_ID)
                self.assertIn(
                    grant.RACING_COMMENT_ID,
                    [
                        unread.id
                        for unread in self.gh.comments_after(
                            self.issue, consumed,
                        )
                    ],
                )

    def test_the_answer_still_lands(self) -> None:
        # The boundary is the only thing the race moves: the command is still
        # answered, and answered once.
        lifted = self._lift_racing(grant.command(_VALID))

        self.assertTrue(lifted)
        self.assertEqual(len(self.gh.posted_comments), 1)
        self.assertEqual(
            self._recorded()[support.ALLOWANCE_FIELD], _GRANTED_ALLOWANCE,
        )


if __name__ == "__main__":
    unittest.main()
