# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The one route a closed issue's label does not choose for it.

`decomposing` and `umbrella` are swept closed for cleanup only, and both name
stage handlers that would resume the workflow a human ended -- one spawns the
decomposer, the other walks a dependency graph and activates children. What
these cases pin down is that the closed reading is taken first and the label's
own handler is never reached.
"""
from __future__ import annotations

import importlib
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from orchestrator.workflow.engine import dispatch
from orchestrator.workflow.stages.decomposition import late_sweep as _late_sweep

from orchestrator.github.labels import BACKLOG_LABEL, PAUSED_LABEL

from tests.support.fakes import FakeGitHubClient, FakeLabel, make_issue
from tests.workflow.fixtures import (
    LABEL_BLOCKED,
    LABEL_DECOMPOSING,
    LABEL_IMPLEMENTING,
    LABEL_UMBRELLA,
)
from tests.workflow.observation_support import ObservedCloseCase

_SPEC = SimpleNamespace(slug="acme/widget")

_CLEANUP_LABELS = (LABEL_DECOMPOSING, LABEL_UMBRELLA)

_OWNER_NUMBER = 41

_LATE_RELABEL = "orchestrator.workflow.stages.decomposition.late_relabel"

_WORKFLOW_LOG = "orchestrator.workflow"


class _RecordingScheduler:
    """A scheduler that keeps the callable each submit was handed."""

    def __init__(self) -> None:
        self.routes: dict[int, object] = {}
        self.settled: list[int] = []

    def submit(self, _slug, issue_number, callable_, **_options) -> bool:
        self.routes[issue_number] = callable_
        return True

    def deferred_cleanups(self, _slug) -> frozenset:
        """Nothing held: every submit this double takes is accepted."""
        return frozenset()

    def settle_cleanup(self, _slug, issue_number: int) -> None:
        self.settled.append(issue_number)


def _intercepted(target: tuple[str, str], reached: Mock):
    """Hold the handler one target names, on the module that owns it."""
    return patch.object(
        importlib.import_module(target[0]), target[1], reached,
    )


def _partition_of(*issues) -> dispatch._PollablePartition:
    """Partition a repo holding exactly these issues, in this tick."""
    github = FakeGitHubClient()
    for number, label, closed in issues:
        github.add_issue(make_issue(number, label=label, closed=closed))
    # One fan-out issue so the partition is the ordinary mixed shape a
    # saturated cap is decided against.
    github.add_issue(make_issue(1, label=LABEL_IMPLEMENTING))
    return dispatch._partition_pollable_issues(github, _SPEC)


def _routed(
    label: str, *, closed: bool, cleanup_only: bool = False,
) -> tuple[Mock, Mock]:
    """Route one issue and return the (cleanup, stage) handlers it could hit."""
    github = FakeGitHubClient()
    issue = make_issue(_OWNER_NUMBER, label=label, closed=closed)
    github.add_issue(issue)
    reached = (Mock(), Mock())
    with _intercepted(dispatch._CLEANUP_SWEEP_TARGET, reached[0]):
        with _intercepted(dispatch._STAGE_HANDLER_TARGETS[label], reached[1]):
            dispatch._route_issue_to_handler(
                github, _SPEC, issue, label,
                reading=dispatch._PollReading(
                    cleanup_only=cleanup_only, closed=closed,
                ),
            )
    return reached


class CleanupRouteTest(ObservedCloseCase, unittest.TestCase):
    """A closed cleanup-swept issue reaches the sweep and nothing else.

    Including past the filter that parks an issue outside the state machine.
    `backlog` / `paused` run ahead of every route, and letting one drop a
    CLOSED cleanup owner loses the close itself -- an observed close ends the
    late cycle irreversibly, and the pass being dropped is the only one that
    would ever record that, so the owner would come back from a reopen and an
    unpause with a live generation and spawn against it. The route is taken;
    the label defers everything it would otherwise DO.
    """

    def setUp(self) -> None:
        self._fresh_process()

    def test_a_closed_owner_reaches_only_the_sweep(self) -> None:
        for label in _CLEANUP_LABELS:
            with self.subTest(label=label):
                cleanup, stage = _routed(label, closed=True)

                cleanup.assert_called_once()
                stage.assert_not_called()

    def test_an_open_issue_still_reaches_its_stage(self) -> None:
        # The sweep is reached by being closed, not by wearing the label: an
        # issue still open on either state is ordinary decomposition work.
        for label in _CLEANUP_LABELS:
            with self.subTest(label=label):
                cleanup, stage = _routed(label, closed=False)

                stage.assert_called_once()
                cleanup.assert_not_called()

    def test_the_pinned_state_guards_are_never_asked(self) -> None:
        # They cost one comment walk to decide whether a hand relabel happened
        # under a live adjudication, or whether this child's snapshot is gone,
        # and a closed owner is not dispatched on any of those answers -- so
        # the cleanup route is taken ahead of the read they share. Patched on
        # the helper the dispatcher actually calls: the composed
        # `_refuses_dispatch` is not on this path at all, so intercepting it
        # would prove nothing.
        read = Mock(return_value=None)
        with patch.object(
            importlib.import_module(_LATE_RELABEL), "_dispatch_state", read,
        ):
            cleanup, stage = _routed(LABEL_UMBRELLA, closed=True)

        read.assert_not_called()
        cleanup.assert_called_once()
        stage.assert_not_called()

    def test_a_parked_closed_owner_is_still_marked(self) -> None:
        for skip_label in (PAUSED_LABEL, BACKLOG_LABEL):
            with self.subTest(skip_label=skip_label):
                github, issue = self._parked_owner(skip_label)

                with self.assertLogs(_WORKFLOW_LOG):
                    dispatch._process_issue(github, _SPEC, issue)

                pinned = github.pinned_data(_OWNER_NUMBER)
                self.assertTrue(pinned["late_cancelled"])
                self.assertEqual(github.label_history, [])
                self.assertEqual(github.deleted_remote_branches, [])

    def test_a_parked_open_issue_is_skipped_as_before(self) -> None:
        # The exception is exactly one shape wide: an issue an operator
        # parked while it was OPEN is dropped where it always was.
        github, issue = self._parked_owner(PAUSED_LABEL)
        issue.closed = False

        with self.assertLogs(_WORKFLOW_LOG):
            dispatch._process_issue(github, _SPEC, issue)

        self.assertEqual(github.write_state_calls, 0)

    def _parked_owner(self, skip_label: str):
        """A closed snapshot owner an operator parked with a control label."""
        github = FakeGitHubClient()
        issue = make_issue(
            _OWNER_NUMBER, label=LABEL_DECOMPOSING, closed=True,
        )
        issue.labels.append(FakeLabel(skip_label))
        github.add_issue(issue)
        github.seed_state(_OWNER_NUMBER, late_cycle_id=3)
        return github, issue


class CleanupRouteSurvivesRefetchTest(ObservedCloseCase, unittest.TestCase):
    """The classification binds; the refetch does not get to re-decide.

    A closed owner is submitted on its own cap-exempt terms, and the worker
    refetches the issue afterwards. A human who reopens one in that window
    would otherwise have the freshly-read label send it to the handler whose
    exemption was granted on the understanding it would never run.
    """

    def setUp(self) -> None:
        self._fresh_process()

    def test_a_reopen_before_running_still_cleans_up(self) -> None:
        cleanup, stage = _routed(
            LABEL_DECOMPOSING, closed=False, cleanup_only=True,
        )

        cleanup.assert_called_once()
        stage.assert_not_called()

    def test_the_submit_carries_the_route(self) -> None:
        # The route reaches the worker as the callable the submit was built
        # from rather than being re-derived there, so it is the
        # classification that decides.
        partition = _partition_of((_OWNER_NUMBER, LABEL_UMBRELLA, True))
        scheduler = _RecordingScheduler()

        dispatch._submit_scheduler_fanout_issues(
            FakeGitHubClient(), _SPEC, scheduler, partition, 1,
        )

        self.assertIs(
            scheduler.routes[_OWNER_NUMBER].func, dispatch._swept_for_cleanup,
        )
        self.assertIs(scheduler.routes[1].func, dispatch._refetch_and_process)

    def test_a_reopened_owner_is_marked_and_left(self) -> None:
        # What the sweep does with the issue it was handed. Being routed here
        # says a close was observed, so the cycle ends whatever the refetch
        # says -- but an issue somebody has just reopened gets nothing
        # external done to it, and no terminal: the mark is what hands it to
        # the dispatcher's own guard from the next tick.
        github = FakeGitHubClient()
        issue = make_issue(_OWNER_NUMBER, label=LABEL_UMBRELLA)
        github.add_issue(issue)
        github.seed_state(_OWNER_NUMBER, late_cycle_id=3)

        with self.assertLogs(_WORKFLOW_LOG):
            _late_sweep._handle_closed_owner_cleanup(github, _SPEC, issue)

        self.assertTrue(github.pinned_data(_OWNER_NUMBER)["late_cancelled"])
        self.assertEqual(github.label_history, [])
        self.assertEqual(github.posted_comments, [])

    def test_an_owner_with_no_cycle_is_untouched(self) -> None:
        # The gate ahead of that: every umbrella the initial decomposer ever
        # made is a closed issue on one of these labels and owns no cycle, so
        # there is nothing about one to end.
        github = FakeGitHubClient()
        issue = make_issue(_OWNER_NUMBER, label=LABEL_UMBRELLA)
        github.add_issue(issue)

        _late_sweep._handle_closed_owner_cleanup(github, _SPEC, issue)

        self.assertEqual(github.write_state_calls, 0)
        self.assertEqual(github.label_history, [])


class CleanupExemptionTest(ObservedCloseCase, unittest.TestCase):
    """Cleanup is admitted cap-exempt without exempting what spawns.

    The family bucket's exemption is all-or-nothing, so a closed owner folded
    into it would be cap-counted the moment one open `decomposing` issue
    shared the tick -- and under a saturated cap the whole bucket is skipped,
    which stops a repository reclaiming refs for as long as its decomposer is
    busy. It is partitioned as fan-out instead, where its own submit carries
    its own exemption.
    """

    def setUp(self) -> None:
        self._fresh_process()

    def test_a_closed_owner_fans_out_cap_exempt(self) -> None:
        for label in _CLEANUP_LABELS:
            with self.subTest(label=label):
                partition = _partition_of((_OWNER_NUMBER, label, True))

                self.assertIn(_OWNER_NUMBER, partition.fanout_numbers)
                self.assertIn(_OWNER_NUMBER, partition.fanout_closed)
                self.assertNotIn(_OWNER_NUMBER, partition.family_numbers)

    def test_it_is_exempt_beside_an_open_decomposer(self) -> None:
        # The mixed bucket. The decomposer stays cap-counted, and the cleanup
        # owner is nowhere near the decision that makes it so.
        partition = _partition_of(
            (_OWNER_NUMBER, LABEL_UMBRELLA, True),
            (7, LABEL_DECOMPOSING, False),
        )

        self.assertIn(_OWNER_NUMBER, partition.fanout_closed)
        self.assertEqual(partition.family_numbers, [7])
        self.assertFalse(
            dispatch._family_bucket_cap_exempt(partition.family_labels),
        )

    def test_an_open_family_issue_stays_in_the_bucket(self) -> None:
        # Only the CLOSED reading moves an issue out of the bucket: an open
        # one on either label is an ordinary cross-issue writer.
        partition = _partition_of(
            (_OWNER_NUMBER, LABEL_UMBRELLA, False),
            (7, LABEL_BLOCKED, False),
        )

        self.assertEqual(partition.family_numbers, [_OWNER_NUMBER, 7])
        self.assertTrue(
            dispatch._family_bucket_cap_exempt(partition.family_labels),
        )


if __name__ == "__main__":
    unittest.main()
