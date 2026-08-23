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

from tests.support.fakes import FakeGitHubClient, make_issue
from tests.workflow.fixtures import (
    LABEL_BLOCKED,
    LABEL_DECOMPOSING,
    LABEL_IMPLEMENTING,
    LABEL_UMBRELLA,
)

_SPEC = SimpleNamespace(slug="acme/widget")

_CLEANUP_LABELS = (LABEL_DECOMPOSING, LABEL_UMBRELLA)

_OWNER_NUMBER = 41

_LATE_RELABEL = "orchestrator.workflow.stages.decomposition.late_relabel"


class _RecordingScheduler:
    """A scheduler that keeps the callable each submit was handed."""

    def __init__(self) -> None:
        self.routes: dict[int, object] = {}

    def submit(self, _slug, issue_number, callable_, **_options) -> bool:
        self.routes[issue_number] = callable_
        return True


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
                github, _SPEC, issue, label, cleanup_only=cleanup_only,
            )
    return reached


class CleanupRouteTest(unittest.TestCase):
    """A closed cleanup-swept issue reaches the sweep and nothing else."""

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


class CleanupRouteSurvivesRefetchTest(unittest.TestCase):
    """The classification binds; the refetch does not get to re-decide.

    A closed owner is submitted on its own cap-exempt terms, and the worker
    refetches the issue afterwards. A human who reopens one in that window
    would otherwise have the freshly-read label send it to the handler whose
    exemption was granted on the understanding it would never run.
    """

    def test_a_reopen_before_running_still_cleans_up(self) -> None:
        cleanup, stage = _routed(
            LABEL_DECOMPOSING, closed=False, cleanup_only=True,
        )

        cleanup.assert_called_once()
        stage.assert_not_called()

    def test_the_submit_carries_the_route(self) -> None:
        # The flag reaches the worker as a bound argument rather than being
        # re-derived there, so it is the classification that decides.
        partition = _partition_of((_OWNER_NUMBER, LABEL_UMBRELLA, True))
        scheduler = _RecordingScheduler()

        dispatch._submit_scheduler_fanout_issues(
            FakeGitHubClient(), _SPEC, scheduler, partition, 1,
        )

        self.assertEqual(
            scheduler.routes[_OWNER_NUMBER].keywords["cleanup_only"], True,
        )
        self.assertEqual(scheduler.routes[1].keywords["cleanup_only"], False)

    def test_a_reopened_owner_does_nothing_at_all(self) -> None:
        # What the sweep does with the issue it was handed: the close it was
        # classified on is re-read, and an issue that is open again is left
        # for the next tick to classify correctly.
        github = FakeGitHubClient()
        issue = make_issue(_OWNER_NUMBER, label=LABEL_UMBRELLA)
        github.add_issue(issue)
        github.seed_state(_OWNER_NUMBER, late_cycle_id=3)

        _late_sweep._handle_closed_owner_cleanup(github, _SPEC, issue)

        self.assertEqual(github.write_state_calls, 0)
        self.assertEqual(github.label_history, [])


class CleanupExemptionTest(unittest.TestCase):
    """Cleanup is admitted cap-exempt without exempting what spawns.

    The family bucket's exemption is all-or-nothing, so a closed owner folded
    into it would be cap-counted the moment one open `decomposing` issue
    shared the tick -- and under a saturated cap the whole bucket is skipped,
    which stops a repository reclaiming refs for as long as its decomposer is
    busy. It is partitioned as fan-out instead, where its own submit carries
    its own exemption.
    """

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
