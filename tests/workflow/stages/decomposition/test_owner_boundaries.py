# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The owners decomposition borrows from, and the boundary each one pins.

The stage owns neither end of what it hands off: the scratch checkout the
read-only decomposer runs in belongs to `git/worktrees/`, and the retry budget
a fresh spawn consumes and the implementation a `single` verdict routes to
belong to `workflow/stages/implementing/`. Each is imported from that owner
rather than read off the `orchestrator.workflow` facade, so a patch that has to
intercept one lands on the owner. Every case patches BOTH -- the owner mock has
to answer and the facade guard has to stay untouched -- which is what fails if
a call site drifts back to `_wf`.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from orchestrator.workflow.stages.decomposition import (
    blocked as _blocked,
    models as _models,
    run as _run,
    session as _session,
)
from orchestrator.workflow.stages.implementing import (
    handler as _implementing,
    session as _dev_session,
)

from tests.fakes import FakeGitHubClient, make_issue
from tests.workflow_helpers import _FAKE_WT, _TEST_SPEC, _agent
from tests.workflow_owner_boundaries import OwnerBoundaryMixin

BOUNDARY_ISSUE = 880

HANDLE_IMPLEMENTING = "_handle_implementing"
RETRY_BUDGET = "_check_and_increment_retry_budget"


def _seed(label: str, **state_fields):
    """A decomposition issue on `label`, with its pinned state loaded."""
    gh = FakeGitHubClient()
    issue = make_issue(BOUNDARY_ISSUE, label=label)
    gh.add_issue(issue)
    gh.seed_state(BOUNDARY_ISSUE, **state_fields)
    return gh, issue, gh.read_pinned_state(issue)


class GitProbeBoundaryTest(unittest.TestCase, OwnerBoundaryMixin):
    """The read-only worktree check lands on the git worktree owners."""

    def test_dirty_check_probes_on_owners(self) -> None:
        # The two probes are `or`-ed, so each case makes one of them the sole
        # reason the park fires: a probe read off the facade would leave the
        # run unparked rather than hiding behind its sibling's owner answer.
        for new_commits, dirty in ((True, ()), (False, ("left.py",))):
            with self.subTest(new_commits=new_commits):
                self._assert_parks_on_owner_probes(
                    new_commits=new_commits, dirty=dirty,
                )

    def _assert_parks_on_owner_probes(self, *, new_commits, dirty) -> None:
        gh, issue, state = _seed("decomposing")
        run_plan = _models._DecomposerRunPlan(agent_result=_agent())
        with self.git_seams_on_owners(
            _decompose_worktree_path=MagicMock(return_value=_FAKE_WT),
            _has_new_commits=MagicMock(return_value=new_commits),
            _worktree_dirty_files=MagicMock(return_value=list(dirty)),
        ):
            _run._process_decomposer_run(gh, _TEST_SPEC, issue, state, run_plan)
        self.assertTrue(run_plan.keep_worktree)
        self.assertTrue(gh.pinned_data(BOUNDARY_ISSUE).get("awaiting_human"))


class ImplementingOwnerBoundaryTest(unittest.TestCase, OwnerBoundaryMixin):
    """The retry budget and the implementation handoff land on implementing."""

    def test_ready_handoff_lands_on_owner(self) -> None:
        gh, issue, _ = _seed("ready", pickup_comment_id=1)
        with (
            self.facade_out_of_the_path(HANDLE_IMPLEMENTING),
            patch.object(_implementing, HANDLE_IMPLEMENTING) as implement,
        ):
            _blocked._handle_ready(gh, _TEST_SPEC, issue)
            implement.assert_called_once_with(gh, _TEST_SPEC, issue)
        self.assertIn((BOUNDARY_ISSUE, "implementing"), gh.label_history)

    def test_retry_budget_lands_on_owner(self) -> None:
        # An exhausted budget owns the tick: the owner mock's refusal is what
        # keeps the spawn from happening at all.
        gh, issue, state = _seed("decomposing")
        with (
            self.facade_out_of_the_path(RETRY_BUDGET, returns=False),
            patch.object(_dev_session, RETRY_BUDGET, return_value=False) as budget,
        ):
            spawned = _session._spawn_fresh_decomposer(
                gh, _TEST_SPEC, issue, state,
            )
            budget.assert_called_once()
        self.assertIsNone(spawned)


if __name__ == "__main__":
    unittest.main()
