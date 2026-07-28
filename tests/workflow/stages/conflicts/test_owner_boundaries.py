# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The owners the conflict stage borrows from, and the boundary each one pins.

The rebase loop runs a developer and disposes of what it left behind, but owns
neither half: the resume and the question / dirty-tree parks belong to
`workflow/stages/implementing/`, and the disposition of a body-edit run to
`workflow/stages/validating/`. The park reasons that tell an auto-rebase park
apart -- the ones the base-sync retry loop owns and this stage must leave alone
-- belong to `git/base_sync/`. Each is imported from that owner rather than read
off the `orchestrator.workflow` facade, so a patch that has to intercept one
lands on the owner. Every case patches BOTH -- the owner mock has to answer and
the facade guard has to stay untouched -- which is what fails if a call site
drifts back to `_wf`.
"""
from __future__ import annotations

import contextlib
import unittest
from unittest.mock import patch

from orchestrator import workflow
from orchestrator.git.base_sync import state as _base_sync_state
from orchestrator.workflow.stages.conflicts import (
    models as _models,
    outcomes as _outcomes,
    resume as _resume,
)
from orchestrator.workflow.stages.implementing import (
    parks as _dev_parks,
    resume as _dev_resume,
)
from orchestrator.workflow.stages.validating import (
    drift_outcomes as _drift_outcomes,
)

from tests.fakes import FakeComment, FakeGitHubClient, FakePR, FakeUser, make_issue
from tests.workflow_helpers import _FAKE_WT, _TEST_SPEC, _agent

BOUNDARY_ISSUE = 830
BOUNDARY_PR = 831
BOUNDARY_BRANCH = "orchestrator/geserdugarov__agent-orchestrator/issue-830"
BEFORE_SHA = "beforeAA"
AFTER_SHA = "afterBB"
REPLY_ID = 8300
AUTHOR = "alice"
NEW_HASH = "hash-after-edit"
OUTCOME_ACK = "ack"
CUSTOM_REBASE_PARK = "auto_base_rebase_custom"

RESUME_WITH_TEXT = "_resume_dev_with_text"
ON_QUESTION = "_on_question"
ON_DIRTY_WORKTREE = "_on_dirty_worktree"
POST_DRIFT_RESULT = "_post_user_content_change_result"
AUTO_REBASE_PARK_REASONS = "_AUTO_REBASE_PARK_REASONS"


def _context(*comments, **state_fields) -> _models._ConflictContext:
    """A `resolving_conflict` issue with an open PR, bundled as one tick."""
    gh = FakeGitHubClient()
    issue = make_issue(
        BOUNDARY_ISSUE, label="resolving_conflict", comments=list(comments),
    )
    gh.add_issue(issue)
    gh.add_pr(FakePR(number=BOUNDARY_PR, head_branch=BOUNDARY_BRANCH))
    gh.seed_state(BOUNDARY_ISSUE, pr_number=BOUNDARY_PR, **state_fields)
    return _models._ConflictContext(
        gh, _TEST_SPEC, issue, gh.read_pinned_state(issue),
    )


def _run(agent_result=None) -> _models._ConflictResumeRun:
    """One finished dev resume in the worktree the loop runs in."""
    return _models._ConflictResumeRun(
        worktree=_FAKE_WT, dev_result=agent_result or _agent(), paused=False,
    )


class _OwnerBoundaryMixin:
    """Assert a block reached no borrowed helper through the facade."""

    @contextlib.contextmanager
    def _facade_out_of_the_path(self, export_name, returns=None):
        # The guard returns the shape its caller unpacks, so a regression
        # fails on the assertion below rather than on an unpack of a bare mock.
        with contextlib.ExitStack() as stack:
            guard = stack.enter_context(
                patch.object(workflow, export_name, return_value=returns),
            )
            yield
        self.assertFalse(
            guard.called, f"{export_name} was read off the workflow facade",
        )

    @contextlib.contextmanager
    def _worktree_on_the_facade(self, *, dirty=()):
        """Hold the worktree seams the stage does not own to fixed answers."""
        with (
            patch.object(
                workflow, "_worktree_path", lambda spec, number: _FAKE_WT,
            ),
            patch.object(
                workflow, "_ensure_pr_worktree", lambda spec, number, **_: _FAKE_WT,
            ),
            patch.object(
                workflow, "_resolve_branch_name", lambda *args: BOUNDARY_BRANCH,
            ),
            patch.object(workflow, "_head_sha", return_value=BEFORE_SHA),
            patch.object(
                workflow, "_worktree_dirty_files", return_value=list(dirty),
            ),
            patch.object(workflow, "_rebase_in_progress", return_value=False),
        ):
            yield


class ImplementingResumeBoundaryTest(unittest.TestCase, _OwnerBoundaryMixin):
    """The shared dev resume lands on the implementing resume owner."""

    def test_conflict_resume_lands_on_owner(self) -> None:
        ctx = _context()
        resume_result = (_FAKE_WT, _agent(), False)
        with (
            self._facade_out_of_the_path(RESUME_WITH_TEXT, returns=resume_result),
            patch.object(
                _dev_resume, RESUME_WITH_TEXT, return_value=resume_result,
            ) as resume,
        ):
            run = _resume._run_conflict_resume(ctx, "finish the rebase")
            resume.assert_called_once()
        self.assertEqual(run.worktree, _FAKE_WT)
        self.assertIn("last_agent_action_at", ctx.state.data)


class ImplementingParkBoundaryTest(unittest.TestCase, _OwnerBoundaryMixin):
    """The two dev parks land on the implementing park owner."""

    def test_unchanged_head_parks_on_owner(self) -> None:
        # HEAD never moved: the run is a question or silence, not a resolution.
        ctx = _context()
        with (
            self._facade_out_of_the_path(ON_QUESTION),
            self._worktree_on_the_facade(),
            patch.object(_dev_parks, ON_QUESTION) as park,
        ):
            _outcomes._post_conflict_resolution_result(ctx, _run(), BEFORE_SHA, 0)
            park.assert_called_once()

    def test_dirty_tree_parks_on_owner(self) -> None:
        ctx = _context()
        with (
            self._facade_out_of_the_path(ON_DIRTY_WORKTREE),
            self._worktree_on_the_facade(dirty=("a.py",)),
            patch.object(_dev_parks, ON_DIRTY_WORKTREE) as park,
        ):
            # `before_sha` differs from the patched HEAD, so the run committed.
            _outcomes._post_conflict_resolution_result(ctx, _run(), AFTER_SHA, 0)
            park.assert_called_once()


class ValidatingDispositionBoundaryTest(unittest.TestCase, _OwnerBoundaryMixin):
    """The body-edit disposition lands on the validating drift-outcome owner."""

    def test_drift_disposition_lands_on_owner(self) -> None:
        ctx = _context()
        resume_result = (_FAKE_WT, _agent(), False)
        with (
            self._facade_out_of_the_path(POST_DRIFT_RESULT, returns=OUTCOME_ACK),
            self._worktree_on_the_facade(),
            patch.object(_dev_resume, RESUME_WITH_TEXT, return_value=resume_result),
            patch.object(
                _drift_outcomes, POST_DRIFT_RESULT, return_value=OUTCOME_ACK,
            ) as dispose,
        ):
            _resume._resume_on_user_content_change(ctx, BOUNDARY_PR, NEW_HASH)
            dispose.assert_called_once()
        # An acknowledgement stays in `resolving_conflict` with the refreshed
        # hash persisted, so the same edit is not re-detected next tick.
        self.assertEqual(ctx.state.get("user_content_hash"), NEW_HASH)
        self.assertNotIn((BOUNDARY_ISSUE, "validating"), ctx.gh.label_history)


class BaseSyncParkReasonBoundaryTest(unittest.TestCase, _OwnerBoundaryMixin):
    """The auto-rebase park reasons are read off the base-sync owner."""

    def test_auto_rebase_reason_lands_on_owner(self) -> None:
        # A park the base-sync retry loop owns takes the passthrough branch:
        # the reply is handed to the dev instead of being refused as a
        # `/orchestrator continue` this stage cannot answer.
        ctx = _context(
            FakeComment(
                id=REPLY_ID,
                body="/orchestrator continue",
                user=FakeUser(AUTHOR),
            ),
            awaiting_human=True,
            park_reason=CUSTOM_REBASE_PARK,
        )
        # The facade answer is held empty: reading it there would classify the
        # bare command as a park this stage must refuse, and the refusal
        # returns no followup at all.
        with (
            patch.object(workflow, AUTO_REBASE_PARK_REASONS, frozenset()),
            patch.object(
                _base_sync_state,
                AUTO_REBASE_PARK_REASONS,
                frozenset((CUSTOM_REBASE_PARK,)),
            ),
        ):
            followup = _resume._awaiting_human_followup(ctx)
        self.assertIn("/orchestrator continue", followup)
        self.assertEqual(ctx.state.get("last_action_comment_id"), REPLY_ID)


if __name__ == "__main__":
    unittest.main()
