# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The owners in_review borrows from, and the patch boundary each one pins.

The drift route runs a developer and reads what it left behind, but owns
neither half: the resume belongs to `workflow/stages/implementing/` and the
disposition of a body-edit run -- the `ACK:` reply that must not park -- to
`workflow/stages/validating/`. Each is imported from that owner rather than
read off the `orchestrator.workflow` facade, so a patch that has to intercept
one lands on the owner. Both cases patch BOTH -- the owner mock has to answer
and the facade guard has to stay untouched -- which is what fails if a call
site drifts back to `_wf`.
"""
from __future__ import annotations

import contextlib
import unittest
from unittest.mock import patch

from orchestrator import workflow
from orchestrator.workflow.stages.implementing import resume as _dev_resume
from orchestrator.workflow.stages.in_review import drift as _drift
from orchestrator.workflow.stages.in_review import models as _models
from orchestrator.workflow.stages.validating import (
    drift_outcomes as _drift_outcomes,
)

from tests.fakes import FakeGitHubClient, FakePR, make_issue
from tests.workflow_helpers import _FAKE_WT, _TEST_SPEC, _agent

BOUNDARY_ISSUE = 780
BOUNDARY_PR = 781
BOUNDARY_BRANCH = "orchestrator/geserdugarov__agent-orchestrator/issue-780"
BEFORE_SHA = "beforeAA"
OUTCOME_ACK = "ack"

RESUME_WITH_TEXT = "_resume_dev_with_text"
POST_DRIFT_RESULT = "_post_user_content_change_result"


def _context() -> _models._InReviewContext:
    """An `in_review` issue with an open PR, bundled as one tick's handles."""
    gh = FakeGitHubClient()
    issue = make_issue(BOUNDARY_ISSUE, label="in_review", body="new acceptance")
    gh.add_issue(issue)
    pr = FakePR(number=BOUNDARY_PR, head_branch=BOUNDARY_BRANCH)
    gh.add_pr(pr)
    gh.seed_state(BOUNDARY_ISSUE, pr_number=BOUNDARY_PR)
    return _models._InReviewContext(
        gh, _TEST_SPEC, issue, gh.read_pinned_state(issue), pr, BOUNDARY_PR,
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


class ImplementingResumeBoundaryTest(unittest.TestCase, _OwnerBoundaryMixin):
    """The drift resume lands on the implementing resume owner."""

    def test_drift_resume_lands_on_owner(self) -> None:
        ctx = _context()
        resume_result = (_FAKE_WT, _agent(), False)
        with (
            self._facade_out_of_the_path(
                RESUME_WITH_TEXT, returns=resume_result,
            ),
            patch.object(
                workflow, "_ensure_worktree", lambda spec, number, **_: _FAKE_WT,
            ),
            patch.object(
                workflow, "_resolve_branch_name", lambda *args: BOUNDARY_BRANCH,
            ),
            patch.object(workflow, "_head_sha", return_value=BEFORE_SHA),
            patch.object(
                _dev_resume, RESUME_WITH_TEXT, return_value=resume_result,
            ) as resume,
        ):
            drift_resume = _drift._resume_dev_for_drift(ctx, [])
            resume.assert_called_once()
        self.assertEqual(drift_resume.before_sha, BEFORE_SHA)


class ValidatingDispositionBoundaryTest(unittest.TestCase, _OwnerBoundaryMixin):
    """The body-edit disposition lands on the validating drift-outcome owner."""

    def test_drift_disposition_lands_on_owner(self) -> None:
        ctx = _context()
        resume = _models._DriftResume(_FAKE_WT, _agent(), False, BEFORE_SHA)
        with (
            self._facade_out_of_the_path(POST_DRIFT_RESULT, returns=OUTCOME_ACK),
            patch.object(
                _drift_outcomes, POST_DRIFT_RESULT, return_value=OUTCOME_ACK,
            ) as dispose,
        ):
            _drift._dispose_drift_result(ctx, [], resume)
            dispose.assert_called_once()
        # An ack invalidates the approval that carried the issue here.
        self.assertEqual(ctx.state.get("review_round"), 0)


if __name__ == "__main__":
    unittest.main()
