# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""A pair frozen for a published pull request, answered before its stage runs.

The freeze is durable and the count that follows it is not, so a tick that
dies in between leaves a record naming both commits with no number on it. What
these pin down is that the next tick takes that reading first: the handler
below would otherwise spawn a reviewer, resume a developer, or read a pull
request still standing where the gate froze it, while the record goes on
freezing the branch out of the base refresh.
"""

from __future__ import annotations

import importlib
import unittest
from unittest.mock import Mock, patch

from orchestrator.git.measurement.models import FrozenCommit
from orchestrator.git.worktrees import paths as _worktree_paths
from orchestrator.workflow import state as _workflow_state
from orchestrator.workflow.engine import dispatch as _dispatch

from tests.support.fakes import FakeGitHubClient, FakePRRef, make_issue
from tests.workflow.fixtures import (
    LABEL_DECOMPOSING,
    MEASURED_CANDIDATE_SHA,
    SHA_LENGTH,
    _PatchedWorkflowMixin,
    _TEST_SPEC,
    _agent,
    _issue_branch,
    _open_pr_for,
)
from tests.workflow.stages.fixing import fixing_test_support as fixing
from tests.workflow.stages.fixing import (
    published_gate_support as support,
)

ISSUE = fixing.ISSUE
PR_NUMBER = fixing.PR_NUMBER
CEILING = support.CEILING
PAST_THE_CEILING = support.PAST_THE_CEILING
COUNT_ADDED_LINES = support.COUNT_ADDED_LINES
KEY_APPROVED_SHA = support.KEY_APPROVED_SHA
KEY_CANDIDATE_SHA = support.KEY_CANDIDATE_SHA
KEY_SOURCE_STAGE = support.KEY_SOURCE_STAGE
PARK_MEASUREMENT_FAILED = support.PARK_MEASUREMENT_FAILED
PARK_REASON = fixing.PARK_REASON
PUSH_BRANCH = fixing.PUSH_BRANCH
KEY_RECEIPT_SHA = support.KEY_RECEIPT_SHA
# The two keywords a gated push names its commit and pins its ref by.
REVISION = "revision"
LEASE = "force_with_lease"

WORKTREE_PATH = "_worktree_path"
# A commit the record does not name, for a checkout something moved while no
# run of this tick was out.
MOVED_CANDIDATE = "ef" * (SHA_LENGTH // 2)
AWAITING_HUMAN = fixing.AWAITING_HUMAN

# What a reading nobody could take left behind, for the tick that takes it.
_MEASUREMENT_PARK = ((AWAITING_HUMAN, True), (PARK_REASON, PARK_MEASUREMENT_FAILED))


class _FrozenPairMixin(_PatchedWorkflowMixin):
    """One issue whose record names a pair, and one tick routed over it."""

    def _frozen(self, *, label: str = fixing.FIXING, parked: bool = False):
        """An issue whose record names a pair and carries no count."""
        github = FakeGitHubClient()
        issue = make_issue(ISSUE, label=label)
        github.add_issue(issue)
        github.seed_state(
            ISSUE,
            branch=_issue_branch(ISSUE),
            pr_number=PR_NUMBER,
            **(dict(_MEASUREMENT_PARK) if parked else {}),
            **support.recorded_generation(),
        )
        # Standing exactly where the record says it froze it: a head that
        # moved is its own refusal, tested beside this one.
        _open_pr_for(
            github,
            issue_number=ISSUE,
            pr_number=PR_NUMBER,
            head=FakePRRef(sha=fixing.PR_HEAD_SHA),
        )
        return github, issue

    def _route(self, github, issue, *, handled=None, **run_options):
        """Route one issue the way a tick does, reporting the handler call."""
        dispatched = Mock()
        owner_name, named = _dispatch._STAGE_HANDLER_TARGETS[
            handled or _workflow_state.WorkflowLabel.FIXING
        ]
        run_options.setdefault("run_agent", _agent())
        with patch.object(
            importlib.import_module(owner_name), named, dispatched,
        ), patch.object(
            _worktree_paths, WORKTREE_PATH, return_value=fixing.TEMP_ROOT,
        ):
            mocks = self._run(
                lambda: _dispatch._route_issue_to_handler(
                    github, _TEST_SPEC, issue,
                    github.workflow_label(issue),
                ),
                **run_options,
            )
        return dispatched, mocks

    def _route_to_the_stage(self, github, issue, **run_options):
        """Route one issue with the real stage handler behind the tick.

        What the mocked form cannot say: the recovery hands the handler a
        world, and whether that world is the one the crashed tick would have
        left is only answerable by letting the handler read it.
        """
        run_options.setdefault("run_agent", _agent())
        with patch.object(
            _worktree_paths, WORKTREE_PATH, return_value=fixing.TEMP_ROOT,
        ):
            return self._run(
                lambda: _dispatch._route_issue_to_handler(
                    github, _TEST_SPEC, issue,
                    github.workflow_label(issue),
                ),
                **run_options,
            )


class FrozenPairReconciliationTest(unittest.TestCase, _FrozenPairMixin):
    """What a crash between the freeze and the count leaves, and what pays it."""

    def test_a_small_pair_publishes_and_dispatches(self) -> None:
        # The count comes back under the ceiling, so the candidate earns the
        # push the crashed tick owed -- named against the commit that was
        # measured and pinned to the head the pair froze. Only then does the
        # handler run, over the same world that tick would have handed it.
        github, issue = self._frozen()

        dispatched, mocks = self._route(github, issue)

        mocks[COUNT_ADDED_LINES].assert_called_once()
        pushed = mocks[PUSH_BRANCH].call_args
        self.assertEqual(pushed.kwargs[REVISION], MEASURED_CANDIDATE_SHA)
        self.assertEqual(pushed.kwargs[LEASE], fixing.PR_HEAD_SHA)
        dispatched.assert_called_once()

    def test_a_published_pair_leaves_no_debt(self) -> None:
        # The record is retired and the debt the approval named is paid by the
        # push that landed, with a receipt in its place: left standing, it
        # would freeze this branch out of the base refresh for the rest of the
        # issue's life over work the pull request already has.
        github = self._frozen()[0]

        self._route(github, github.get_issue(ISSUE))

        pinned = github.pinned_data(ISSUE)
        self.assertNotIn(KEY_CANDIDATE_SHA, pinned)
        self.assertIsNone(pinned[KEY_APPROVED_SHA])
        self.assertEqual(pinned[KEY_RECEIPT_SHA], MEASURED_CANDIDATE_SHA)

    def test_a_retried_pair_retires_its_park(self) -> None:
        # The park the failed reading left is durable, and no run of this tick
        # clears it: the reading IS the tick. Left standing, the source stage
        # below reads `awaiting_human` and takes its parked road -- waiting for
        # a reply to the very question this tick answered -- while the commit
        # it just approved sits unpushed.
        github, issue = self._frozen(parked=True)

        dispatched, mocks = self._route(github, issue)

        mocks[COUNT_ADDED_LINES].assert_called_once()
        dispatched.assert_called_once()
        pinned = github.pinned_data(ISSUE)
        self.assertFalse(pinned.get(AWAITING_HUMAN))
        self.assertIsNone(pinned.get(PARK_REASON))
        self.assertEqual(pinned[KEY_RECEIPT_SHA], MEASURED_CANDIDATE_SHA)

    def test_an_oversized_pair_stops_the_stage(self) -> None:
        # The reading the crash interrupted is the one that says this pull
        # request may not grow, so it is answered before the handler that
        # would have grown it.
        github, issue = self._frozen()

        with patch.object(fixing.config, support.MAX_ADDED_LINES, CEILING):
            dispatched, _mocks = self._route(
                github, issue, added_lines=PAST_THE_CEILING,
            )

        dispatched.assert_not_called()
        self.assertEqual(github.label_history, [(ISSUE, LABEL_DECOMPOSING)])

    def test_a_moved_candidate_is_refused(self) -> None:
        # No developer ran on this tick, so there is no run whose output a
        # head that is not the recorded candidate could be -- it is a checkout
        # something moved, and measuring it would settle this generation on a
        # commit it was never about. The park is made durable here, because
        # nothing runs behind this to write it.
        github, issue = self._frozen()

        dispatched, mocks = self._route(
            github, issue,
            candidate_commit=FrozenCommit(sha=MOVED_CANDIDATE),
        )

        dispatched.assert_not_called()
        mocks[COUNT_ADDED_LINES].assert_not_called()
        self.assertEqual(github.label_history, [])
        pinned = github.pinned_data(ISSUE)
        self.assertEqual(pinned[KEY_CANDIDATE_SHA], MEASURED_CANDIDATE_SHA)
        self.assertEqual(pinned[PARK_REASON], PARK_MEASUREMENT_FAILED)


class StrandedRecordTest(unittest.TestCase, _FrozenPairMixin):
    """A pair frozen on one stage and read while the issue sits on another."""

    def test_a_record_of_another_stage_stops_the_tick(self) -> None:
        # A record entered on `fixing` and read while the issue sits somewhere
        # else belongs to a stage that has moved. It may not be re-entered
        # from here -- it would be measured under a publication it was never
        # taken on -- and the stage the label now names may not run either:
        # the candidate is unmeasured and unpushed, so `validating` would hand
        # a reviewer a head the pull request never received. Neither road is
        # this process's to pick, so the tick stops and says so once.
        github, issue = self._frozen(label=fixing.VALIDATING)

        dispatched, mocks = self._route(
            github, issue, handled=_workflow_state.WorkflowLabel.VALIDATING,
        )

        mocks[COUNT_ADDED_LINES].assert_not_called()
        dispatched.assert_not_called()
        mocks[PUSH_BRANCH].assert_not_called()
        self.assertEqual(github.label_history, [])
        pinned = github.pinned_data(ISSUE)
        self.assertTrue(pinned[AWAITING_HUMAN])
        self.assertEqual(pinned[PARK_REASON], PARK_MEASUREMENT_FAILED)
        # The pair is kept whole: the stage it was entered on is what a human
        # puts the label back to, and the commit is still the one to measure.
        self.assertEqual(pinned[KEY_CANDIDATE_SHA], MEASURED_CANDIDATE_SHA)
        self.assertEqual(pinned[KEY_SOURCE_STAGE], fixing.FIXING)

    def test_a_stranded_record_asks_a_human_once(self) -> None:
        # The refusal is unrepairable from here, so every later poll reads the
        # same record and would file the same report. The park it already left
        # is what tells the second tick to hold quietly.
        github, issue = self._frozen(label=fixing.VALIDATING, parked=True)

        dispatched, _mocks = self._route(
            github, issue, handled=_workflow_state.WorkflowLabel.VALIDATING,
        )

        dispatched.assert_not_called()
        self.assertEqual(github.posted_comments, [])
