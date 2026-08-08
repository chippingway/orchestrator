# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The git owners the documenting stage reads, and the boundary each pins.

A docs pass owns none of the git it runs on: the checkout it disposes of, the
HEAD and dirty reads that decide whether the agent produced anything, and the
push that publishes it all belong to `git/`, and so do the park reasons that
tell an auto-rebase park apart. Each is imported from that owner rather than
read off the `orchestrator.workflow` facade, so a patch that has to intercept
one lands on the owner. Both cases patch BOTH -- the owner mock has to answer
and the facade guard has to stay untouched -- which is what fails if a call
site drifts back to `_wf`.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from orchestrator.git.base_sync import state as _base_sync_state
from orchestrator.workflow.stages.documenting import (
    models as _models,
    outcomes as _outcomes,
    preconditions as _preconditions,
)

from tests.fakes import FakeComment, FakeGitHubClient, FakePR, FakeUser, make_issue
from tests.workflow_helpers import _FAKE_WT, _TEST_SPEC, _agent
from tests.workflow_owner_boundaries import OwnerBoundaryMixin

BOUNDARY_ISSUE = 870
BOUNDARY_PR = 871
BOUNDARY_BRANCH = "orchestrator/geserdugarov__agent-orchestrator/issue-870"
BEFORE_SHA = "beforeAA"
AFTER_SHA = "afterBB"
REPLY_ID = 8700
AUTHOR = "alice"
CUSTOM_REBASE_PARK = "auto_base_rebase_custom"

AUTO_REBASE_PARK_REASONS = "_AUTO_REBASE_PARK_REASONS"


def _context(*comments, **state_fields) -> _models._DocumentingContext:
    """A `documenting` issue with an open PR, bundled as one tick."""
    gh = FakeGitHubClient()
    issue = make_issue(
        BOUNDARY_ISSUE, label="documenting", comments=list(comments),
    )
    gh.add_issue(issue)
    gh.add_pr(FakePR(number=BOUNDARY_PR, head_branch=BOUNDARY_BRANCH))
    gh.seed_state(BOUNDARY_ISSUE, pr_number=BOUNDARY_PR, **state_fields)
    return _models._DocumentingContext(
        gh, _TEST_SPEC, issue, gh.read_pinned_state(issue),
        BOUNDARY_BRANCH, BOUNDARY_PR,
    )


def _run() -> _models._DocumentingRun:
    """One finished docs run that committed on top of `BEFORE_SHA`."""
    return _models._DocumentingRun(
        _FAKE_WT, _agent(last_message="docs written"), BEFORE_SHA,
        False, False, 0,
    )


class GitProbeBoundaryTest(unittest.TestCase, OwnerBoundaryMixin):
    """The probes and the push a published docs commit runs land on git."""

    def test_pushed_docs_publish_on_owners(self) -> None:
        # The disposition runs the whole tail -- worktree lookup, HEAD and
        # dirty reads, push -- so one pass covers every git seam the docs
        # outcome names.
        ctx = _context()
        with self.git_seams_on_owners(
            _worktree_path=MagicMock(return_value=_FAKE_WT),
            _head_sha=MagicMock(return_value=AFTER_SHA),
            _worktree_dirty_files=MagicMock(return_value=[]),
            _push_branch=MagicMock(return_value=True),
        ):
            _outcomes._dispose_documenting_outcome(ctx, _run())
        self.assertIn((BOUNDARY_ISSUE, "in_review"), ctx.gh.label_history)
        self.assertEqual(ctx.state.get("docs_verdict"), "updated")


class BaseSyncParkReasonBoundaryTest(unittest.TestCase, OwnerBoundaryMixin):
    """The auto-rebase park reasons are read off the base-sync owner."""

    def test_auto_rebase_reason_lands_on_owner(self) -> None:
        # A park the base-sync retry loop owns keeps the tick silent even
        # though a trusted reply is waiting: the reply is the "retry the
        # rebase" signal, not a documenting-stage trigger.
        ctx = _context(
            FakeComment(id=REPLY_ID, body="ping", user=FakeUser(AUTHOR)),
            awaiting_human=True,
            park_reason=CUSTOM_REBASE_PARK,
        )
        # The facade answer is held empty: reading it there would let the
        # trusted reply fall through and wake the docs pass.
        with (
            self.facade_park_reasons_empty(),
            patch.object(
                _base_sync_state,
                AUTO_REBASE_PARK_REASONS,
                frozenset((CUSTOM_REBASE_PARK,)),
            ),
        ):
            handled = _preconditions._documenting_parked_no_input(
                ctx.gh, ctx.issue, ctx.state,
            )
        self.assertTrue(handled)


if __name__ == "__main__":
    unittest.main()
