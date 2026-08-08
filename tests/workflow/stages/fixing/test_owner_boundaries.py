# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The owners fixing borrows from, and the patch boundary each one pins.

The fix loop runs a developer and disposes of what it left behind, but owns
neither half: the resume and the poisoned-session drop belong to
`workflow/stages/implementing/`, and the dev-fix disposition, the stranded-fix
probe, and the transient-park recovery to `workflow/stages/validating/`. The
debounce reads a comment timestamp off `workflow/stages/in_review/`, which is
where the surfaces it spans are already reconciled, and the worktree the resume
runs in is named, restored, and measured on `git/`. Each is imported from that
owner rather than read off the `orchestrator.workflow` facade, so a patch that
has to intercept one lands on the owner. Every case patches BOTH -- the owner
mock has to answer and the facade guard has to stay untouched -- which is what
fails if a call site drifts back to `_wf`.
"""
from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from orchestrator.workflow.stages.fixing import (
    continue_command as _continue,
    models as _models,
    parked as _parked,
    resume as _resume,
)
from orchestrator.workflow.stages.implementing import (
    resume as _dev_resume,
    session as _dev_session,
)
from orchestrator.workflow.stages.in_review import watermarks as _watermarks
from orchestrator.workflow.stages.validating import (
    dev_fix as _dev_fix,
    recovery as _validating_recovery,
)

from tests.fakes import FakeComment, FakeGitHubClient, FakePR, FakeUser, make_issue
from tests.workflow_helpers import _FAKE_WT, _TEST_SPEC, _agent
from tests.workflow_owner_boundaries import OwnerBoundaryMixin

BOUNDARY_ISSUE = 890
BOUNDARY_PR = 891
BOUNDARY_BRANCH = "orchestrator/geserdugarov__agent-orchestrator/issue-890"
BEFORE_SHA = "beforeAA"
AFTER_SHA = "afterBB"
BATCH_COMMENT_ID = 9100
AUTHOR = "alice"

RESUME_WITH_TEXT = "_resume_dev_with_text"
DROP_POISONED_SESSION = "_drop_poisoned_dev_session"
HANDLE_DEV_FIX = "_handle_dev_fix_result"
STRANDED_UNPUSHED = "_stranded_fix_unpushed"
RECOVER_TRANSIENT = "_try_recover_validating_transient_park"
COMMENT_CREATED_AT = "_comment_created_at"

SILENT_PARK = "agent_silent"
TIMEOUT_PARK = "agent_timeout"


def _context(*comments, **state_fields) -> _models._FixingContext:
    """A `fixing` issue with an open PR, bundled as one tick's handles."""
    gh = FakeGitHubClient()
    issue = make_issue(BOUNDARY_ISSUE, label="fixing", comments=list(comments))
    gh.add_issue(issue)
    pr = FakePR(number=BOUNDARY_PR, head_branch=BOUNDARY_BRANCH)
    gh.add_pr(pr)
    gh.seed_state(BOUNDARY_ISSUE, pr_number=BOUNDARY_PR, **state_fields)
    return _models._FixingContext(
        gh, _TEST_SPEC, issue, gh.read_pinned_state(issue), pr,
    )


def _feedback(*feedback_items) -> _models._FixingFeedback:
    """One rescan result carrying `feedback_items` on the issue-comment surface."""
    return _models._FixingFeedback(
        issue_space=list(feedback_items),
        review_comments=[],
        review_summaries=[],
        all_items=list(feedback_items),
    )


class _FixingBoundaryMixin(OwnerBoundaryMixin):
    """Hold the git seams one dev resume reads to fixed answers."""

    def _worktree_on_the_owners(self):
        return self.git_seams_on_owners(
            _worktree_path=MagicMock(return_value=_FAKE_WT),
            _ensure_worktree=MagicMock(return_value=_FAKE_WT),
            _resolve_branch_name=MagicMock(return_value=BOUNDARY_BRANCH),
            _head_sha=MagicMock(return_value=BEFORE_SHA),
        )


class ImplementingOwnerBoundaryTest(unittest.TestCase, _FixingBoundaryMixin):
    """The dev resume and the poisoned-session drop land on implementing."""

    def test_fix_resume_lands_on_owner(self) -> None:
        ctx = _context()
        resume_result = (_FAKE_WT, _agent(), False)
        with (
            self.facade_out_of_the_path(RESUME_WITH_TEXT, returns=resume_result),
            self._worktree_on_the_owners(),
            patch.object(
                _dev_resume, RESUME_WITH_TEXT, return_value=resume_result,
            ) as resume,
        ):
            run = _resume._run_fixing_resume(ctx, "address the review")
            resume.assert_called_once()
        self.assertEqual(run.before_sha, BEFORE_SHA)

    def test_poisoned_session_drop_lands_on_owner(self) -> None:
        ctx = _context(
            FakeComment(
                id=BATCH_COMMENT_ID,
                body="rename the helper",
                user=FakeUser(AUTHOR),
            ),
            park_reason=SILENT_PARK,
            awaiting_human=True,
            pending_fix_issue_ids=[BATCH_COMMENT_ID],
        )
        with (
            self.facade_out_of_the_path(DROP_POISONED_SESSION),
            patch.object(_dev_session, DROP_POISONED_SESSION) as drop,
        ):
            action, batch = _continue._handle_continue_command(ctx, _feedback())
            drop.assert_called_once_with(ctx.state)
        self.assertEqual(action, "replay")
        self.assertEqual(
            [replayed.id for replayed in batch], [BATCH_COMMENT_ID],
        )


class ValidatingDispositionBoundaryTest(unittest.TestCase, _FixingBoundaryMixin):
    """The dev-fix disposition and its stranded probe land on the validating owner."""

    def test_dev_fix_result_lands_on_owner(self) -> None:
        ctx = _context()
        resume_result = (_FAKE_WT, _agent(last_message="pushed"), False)
        with (
            self.facade_out_of_the_path(HANDLE_DEV_FIX, returns=False),
            self._worktree_on_the_owners(),
            patch.object(_dev_resume, RESUME_WITH_TEXT, return_value=resume_result),
            patch.object(_dev_fix, HANDLE_DEV_FIX, return_value=False) as dispose,
        ):
            _resume._resume_fixing_and_dispatch_result(ctx, _feedback(), None)
            dispose.assert_called_once()

    def test_stranded_probe_lands_on_owner(self) -> None:
        # A stranded commit stands the ack fast path down, so a True probe is
        # observable in the return value rather than only in the call record.
        ctx = _context()
        with (
            self.facade_out_of_the_path(STRANDED_UNPUSHED, returns=True),
            patch.object(_dev_fix, STRANDED_UNPUSHED, return_value=True) as probe,
        ):
            acked = _resume._fixing_ack_fast_path(
                ctx, _FAKE_WT, _feedback(),
                _agent(last_message="ACK: nothing to change"), AFTER_SHA,
            )
            probe.assert_called_once()
        self.assertFalse(acked)


class ValidatingRecoveryBoundaryTest(unittest.TestCase, _FixingBoundaryMixin):
    """The transient-park recovery lands on the validating recovery owner."""

    def test_transient_recovery_lands_on_owner(self) -> None:
        ctx = _context(park_reason=TIMEOUT_PARK, awaiting_human=True)
        with (
            self.facade_out_of_the_path(RECOVER_TRANSIENT, returns="cleared"),
            patch.object(
                _validating_recovery, RECOVER_TRANSIENT, return_value="cleared",
            ) as recover,
        ):
            decision = _parked._dispatch_validating_recovery(
                ctx, _feedback(), TIMEOUT_PARK,
            )
            recover.assert_called_once()
        # A cleared transient owns the tick and hands the issue back.
        self.assertTrue(decision.stop)
        self.assertIn((BOUNDARY_ISSUE, "validating"), ctx.gh.label_history)


class InReviewTimestampBoundaryTest(unittest.TestCase, _FixingBoundaryMixin):
    """The debounce reads its comment timestamp off the in_review owner."""

    def test_debounce_timestamp_lands_on_owner(self) -> None:
        just_now = datetime.now(timezone.utc) - timedelta(seconds=1)
        comment = FakeComment(id=BATCH_COMMENT_ID, body="wait", user=FakeUser(AUTHOR))
        with (
            self.facade_out_of_the_path(COMMENT_CREATED_AT, returns=just_now),
            patch.object(
                _watermarks, COMMENT_CREATED_AT, return_value=just_now,
            ) as created_at,
        ):
            still_open = _resume._fixing_debounce_open(_feedback(comment), None)
            created_at.assert_called_once_with(comment)
        self.assertTrue(still_open)


if __name__ == "__main__":
    unittest.main()
