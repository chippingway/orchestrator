# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What GitHub says about a candidate: whether it ended, and who still claims it.

The reads here never touch the host, so the clone these specs name does not
exist: what is under test is which answer each question turns into, and a
repository on disk would only slow that down. The failures are driven through
the double's own refusals where it has them and through a raising client where
it does not, because a lookup that raises and a lookup that answers "no" are
the pair every boundary in this module exists to keep apart.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from orchestrator.git.worktrees import claims
from orchestrator.git.worktrees.models import Retention, RetentionReason
from orchestrator.github.pinned_state import (
    PINNED_STATE_TEMPLATE,
    PinnedState,
    pinned_state_from_comment,
)
from tests.git.worktrees.artifact_test_support import WIDGET_SLUG, _spec
from tests.git.worktrees.eligibility_test_support import (
    BACKLOG_LABEL,
    DONE_LABEL,
    IMPLEMENTING_LABEL,
    ISSUE_NUMBER,
    OPEN_PR_STATE,
    OTHER_BASE_BRANCH,
    REJECTED_LABEL,
    _github,
    _pull_request,
    _RaisingIssue,
    _reasons,
    _terminal_issue,
)
from tests.support.fakes import FakeComment, FakeUser

BRANCH = "orchestrator/acme__widget/issue-314"
OTHER_BRANCH = "orchestrator/issue-314"
RECORDED_PR_NUMBER = 77
UNRECORDED_PR_NUMBER = 78
TIP_SHA = "1234abcd" * 5
LEGACY_IMPLEMENTING_LABEL = "implementing"
NO_CLONE = Path("/nonexistent-clone")
PINNED_BRANCH_KEY = "branch"
BOT_LOGIN = "orchestrator"
CORRUPT_COMMENT_ID = 900

# One case per way an issue can fail to be terminal, plus the two ways it can
# be one. The pair of spellings of a single state is here too: it reads as one
# state rather than as two, so an issue carrying a label the migration has not
# reached is not called ambiguous. The control label beside a terminal one is
# the other direction -- it coexists with a state and is not one.
_ENDINGS = (
    ((DONE_LABEL,), False, (RetentionReason.ISSUE_OPEN,)),
    ((), True, (RetentionReason.NO_WORKFLOW_LABEL,)),
    (
        (DONE_LABEL, IMPLEMENTING_LABEL),
        True,
        (RetentionReason.AMBIGUOUS_WORKFLOW_LABEL,),
    ),
    ((IMPLEMENTING_LABEL,), True, (RetentionReason.NON_TERMINAL_LABEL,)),
    (
        (IMPLEMENTING_LABEL, LEGACY_IMPLEMENTING_LABEL),
        True,
        (RetentionReason.NON_TERMINAL_LABEL,),
    ),
    ((DONE_LABEL,), True, ()),
    ((REJECTED_LABEL,), True, ()),
    ((DONE_LABEL, BACKLOG_LABEL), True, ()),
)

# What a bot-authored pinned comment can carry that no state can be read out
# of: JSON that does not parse, and JSON that parses into something with no
# `get` on it. All of them reach the classifier as an EMPTY state, which is
# what an issue that recorded nothing reaches it as.
_CORRUPT_PAYLOADS = ("{bad json}", "[]", '"x"', "7", "null")

# The same shapes as a payload already parsed, for the guard against a state
# that reached the classifier without passing the parser at all.
_FOREIGN_PAYLOADS = ([], "orchestrator/issue-314", 7, None)


def _claims(gh, spec, branches=(BRANCH,), **pinned) -> tuple:
    """Every open pull request claiming this issue's artifacts."""
    return claims._open_pull_request_retentions(
        gh, spec, ISSUE_NUMBER, branches, PinnedState(data=dict(pinned)),
    )


def _accounting(gh) -> tuple:
    """What accounts for the tip this issue's branch is standing on."""
    return claims._commit_accounting(gh, BRANCH, TIP_SHA)


class TerminalValidationTest(unittest.TestCase):
    """Which closed, labelled issues are the ones a reclaim may proceed on."""

    def test_each_ending_earns_its_own_answer(self) -> None:
        for label_names, closed, expected in _ENDINGS:
            with self.subTest(labels=label_names, closed=closed):
                issue = _terminal_issue(
                    closed=closed, label_names=label_names,
                )

                self.assertEqual(
                    _reasons(claims._terminal_retentions(issue, ISSUE_NUMBER)),
                    expected,
                )

    def test_an_ambiguity_names_both_states(self) -> None:
        # What an operator has to settle is which of the two labels the issue
        # is meant to be on, so the reason carries them rather than the issue.
        issue = _terminal_issue(label_names=(DONE_LABEL, IMPLEMENTING_LABEL))

        kept = claims._terminal_retentions(issue, ISSUE_NUMBER)

        self.assertEqual(kept[0].subject, f"{DONE_LABEL}, {IMPLEMENTING_LABEL}")

    def test_a_field_that_raises_is_unreadable(self) -> None:
        # Every field the ending is read from is a request of its own, so a
        # failure in one is a question that could not be put -- and it must
        # not escape and take the whole classification down with it. The
        # subject comes from the candidate, since the number raises too.
        kept = claims._terminal_retentions(_RaisingIssue(), ISSUE_NUMBER)

        self.assertEqual(
            _reasons(kept), (RetentionReason.ISSUE_UNREADABLE,),
        )
        self.assertEqual(kept[0].subject, f"#{ISSUE_NUMBER}")


class PinnedStateTest(unittest.TestCase):
    """What comes back from the pinned comment, and what is not a state."""

    def setUp(self) -> None:
        self.issue = _terminal_issue()
        self.gh = _github(self.issue, branch=BRANCH)

    def test_a_recorded_state_comes_back(self) -> None:
        state = claims._read_state(self.gh, self.issue, ISSUE_NUMBER)

        self.assertEqual(state.get(PINNED_BRANCH_KEY), BRANCH)

    def test_a_read_that_raised_is_unreadable(self) -> None:
        with patch.object(
            self.gh, "read_pinned_state", side_effect=RuntimeError("no"),
        ):
            unread = claims._read_state(self.gh, self.issue, ISSUE_NUMBER)

        self.assertEqual(
            unread, Retention(
                RetentionReason.STATE_UNREADABLE, f"#{ISSUE_NUMBER}",
            ),
        )

    def test_a_payload_that_is_no_object_is_malformed(self) -> None:
        # A state that did not come from the parser -- one a caller built --
        # can still carry a payload with no `get` on it, and every reader
        # below would raise on it. The classifier answers rather than raises,
        # whichever door the state came through.
        for payload in _FOREIGN_PAYLOADS:
            with self.subTest(payload=payload):
                with patch.object(
                    self.gh,
                    "read_pinned_state",
                    return_value=PinnedState(data=payload),
                ):
                    malformed = claims._read_state(
                        self.gh, self.issue, ISSUE_NUMBER,
                    )

                self.assertEqual(
                    malformed.reason, RetentionReason.STATE_MALFORMED,
                )

    def test_a_parser_refusal_is_malformed(self) -> None:
        # Through the production parser, which is where the shape comes from:
        # each of these resolves to an EMPTY state, exactly what an issue with
        # nothing recorded resolves to. Read as that, the recorded branch and
        # pull request of a corrupted record would count as evidence that
        # there are none -- and the claims living there would go unasked.
        for payload in _CORRUPT_PAYLOADS:
            with self.subTest(payload=payload):
                corrupted = pinned_state_from_comment(
                    FakeComment(
                        id=CORRUPT_COMMENT_ID,
                        body=PINNED_STATE_TEMPLATE.format(payload=payload),
                        user=FakeUser(BOT_LOGIN),
                    ),
                    trusted_login=BOT_LOGIN,
                    issue_number=ISSUE_NUMBER,
                )
                self.assertEqual(corrupted.data, {})

                with patch.object(
                    self.gh, "read_pinned_state", return_value=corrupted,
                ):
                    malformed = claims._read_state(
                        self.gh, self.issue, ISSUE_NUMBER,
                    )

                self.assertEqual(
                    malformed, Retention(
                        RetentionReason.STATE_MALFORMED, f"#{ISSUE_NUMBER}",
                    ),
                )


class OpenPullRequestClaimTest(unittest.TestCase):
    """Every open pull request still standing on this issue's branches."""

    def setUp(self) -> None:
        self.spec = _spec(WIDGET_SLUG, NO_CLONE)
        self.gh = _github()

    def test_a_request_open_on_a_branch_keeps_it(self) -> None:
        self.gh.existing_open_pr[BRANCH] = _pull_request(
            UNRECORDED_PR_NUMBER, BRANCH, TIP_SHA, state=OPEN_PR_STATE,
        )

        kept = _claims(self.gh, self.spec)

        self.assertEqual(
            _reasons(kept), (RetentionReason.OPEN_PULL_REQUEST,),
        )
        self.assertEqual(kept[0].subject, BRANCH)

    def test_a_request_onto_another_base_keeps_it(self) -> None:
        # A human retargeting the pull request onto a release line is still
        # standing on this branch, and a lookup pinned to the configured base
        # would report the branch as free for deletion.
        self.gh.existing_open_pr[BRANCH] = _pull_request(
            UNRECORDED_PR_NUMBER,
            BRANCH,
            TIP_SHA,
            state=OPEN_PR_STATE,
            base=OTHER_BASE_BRANCH,
        )

        self.assertEqual(
            _reasons(_claims(self.gh, self.spec)),
            (RetentionReason.OPEN_PULL_REQUEST,),
        )

    def test_the_pinned_branch_is_asked_about_too(self) -> None:
        # A branch deleted locally after its pull request was opened is not in
        # the scan's report, and the pull request on it is still open -- so
        # the checkout beside it is exactly what somebody would come back to.
        self.gh.existing_open_pr[OTHER_BRANCH] = _pull_request(
            UNRECORDED_PR_NUMBER, OTHER_BRANCH, TIP_SHA, state=OPEN_PR_STATE,
        )

        kept = _claims(self.gh, self.spec, branches=(), branch=OTHER_BRANCH)

        self.assertEqual(
            _reasons(kept), (RetentionReason.OPEN_PULL_REQUEST,),
        )

    def test_a_failed_lookup_names_each_branch(self) -> None:
        # One branch nobody could answer for says nothing about the others,
        # so the failure is reported against every branch it happened on --
        # both layouts this issue can be published under among them.
        with patch.object(
            self.gh, "find_open_pr", side_effect=RuntimeError("no answer"),
        ):
            kept = _claims(self.gh, self.spec)

        self.assertEqual(
            _reasons(kept),
            (RetentionReason.PULL_REQUEST_UNREADABLE,) * 2,
        )
        self.assertEqual(
            sorted(retention.subject for retention in kept),
            sorted((BRANCH, OTHER_BRANCH)),
        )

    def test_a_legacy_layout_request_keeps_it(self) -> None:
        # The host holds only the namespaced branch and the pinned state
        # records nothing, so neither the scan nor the record names the flat
        # `orchestrator/issue-<n>` this issue was published under before
        # namespacing -- and the pull request open on it is what a reclaim
        # would delete the checkout out from under.
        self.gh.existing_open_pr[OTHER_BRANCH] = _pull_request(
            UNRECORDED_PR_NUMBER, OTHER_BRANCH, TIP_SHA, state=OPEN_PR_STATE,
        )

        kept = _claims(self.gh, self.spec)

        self.assertEqual(
            _reasons(kept), (RetentionReason.OPEN_PULL_REQUEST,),
        )
        self.assertEqual(kept[0].subject, OTHER_BRANCH)


class RecordedPullRequestTest(unittest.TestCase):
    """The claim the pinned state names by number rather than by branch."""

    def setUp(self) -> None:
        self.spec = _spec(WIDGET_SLUG, NO_CLONE)
        self.gh = _github()

    def test_the_recorded_number_is_read_too(self) -> None:
        # The claim a branch lookup can miss entirely: the issue's own pull
        # request, whatever branch it went out on.
        self.gh.add_pr(_pull_request(
            RECORDED_PR_NUMBER, OTHER_BRANCH, TIP_SHA, state=OPEN_PR_STATE,
        ))

        kept = _claims(self.gh, self.spec, pr_number=RECORDED_PR_NUMBER)

        self.assertEqual(
            _reasons(kept), (RetentionReason.OPEN_PULL_REQUEST,),
        )
        self.assertEqual(kept[0].subject, f"#{RECORDED_PR_NUMBER}")

    def test_a_recorded_ending_claims_nothing(self) -> None:
        self.gh.add_pr(_pull_request(RECORDED_PR_NUMBER, BRANCH, TIP_SHA))

        self.assertEqual(
            _claims(self.gh, self.spec, pr_number=RECORDED_PR_NUMBER), (),
        )

    def test_a_number_nobody_can_read_keeps_it(self) -> None:
        # Nothing was established about the pull request, and an unread claim
        # spent as an absent one reclaims a branch reviewers are still on.
        kept = _claims(self.gh, self.spec, pr_number=RECORDED_PR_NUMBER)

        self.assertEqual(
            _reasons(kept), (RetentionReason.PULL_REQUEST_UNREADABLE,),
        )
        self.assertEqual(kept[0].subject, f"#{RECORDED_PR_NUMBER}")


class CommitAccountingTest(unittest.TestCase):
    """Whether a terminal pull request exactly accounts for one branch tip."""

    def setUp(self) -> None:
        self.gh = _github()

    def test_a_terminal_request_carrying_it_accounts(self) -> None:
        # Rejected work is still published work: the commit exists in a pull
        # request that outlives the branch, so the local copy is a copy.
        self.gh.add_pr(_pull_request(RECORDED_PR_NUMBER, BRANCH, TIP_SHA))

        self.assertEqual(_accounting(self.gh), ())

    def test_a_request_onto_another_base_accounts(self) -> None:
        # What makes the commit safe to delete here is that GitHub holds it,
        # which a pull request retargeted onto another base does just as well.
        self.gh.add_pr(_pull_request(
            RECORDED_PR_NUMBER, BRANCH, TIP_SHA, base=OTHER_BASE_BRANCH,
        ))

        self.assertEqual(_accounting(self.gh), ())

    def test_a_tip_nothing_carries_is_unaccounted(self) -> None:
        self.assertEqual(
            _reasons(_accounting(self.gh)),
            (RetentionReason.UNACCOUNTED_COMMITS,),
        )

    def test_an_unlistable_branch_is_not_an_absence(self) -> None:
        # The reading that deletes an unpublished branch if it is taken for a
        # no, which is why the lookup has an answer of its own for it.
        self.gh.unreadable_pr_lookups.add(BRANCH)

        self.assertEqual(
            _reasons(_accounting(self.gh)),
            (RetentionReason.PULL_REQUEST_UNREADABLE,),
        )

    def test_a_lookup_that_raised_is_the_same(self) -> None:
        with patch.object(
            self.gh, "find_pr_for_commit", side_effect=RuntimeError("no"),
        ):
            self.assertEqual(
                _reasons(_accounting(self.gh)),
                (RetentionReason.PULL_REQUEST_UNREADABLE,),
            )

    def test_a_request_still_open_accounts_for_none(self) -> None:
        # A disagreement between two readings of the same remote is not one
        # to settle in favour of deleting.
        self.gh.add_pr(_pull_request(
            RECORDED_PR_NUMBER, BRANCH, TIP_SHA, state=OPEN_PR_STATE,
        ))

        self.assertEqual(
            _reasons(_accounting(self.gh)),
            (RetentionReason.OPEN_PULL_REQUEST,),
        )


if __name__ == "__main__":
    unittest.main()
