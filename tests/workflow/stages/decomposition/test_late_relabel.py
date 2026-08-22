# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What may not decide an in-flight generation: a kill switch or a relabel."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from orchestrator import config
from orchestrator.workflow.stages.decomposition import (
    late_relabel as _late_relabel,
)
from orchestrator.workflow.stages.decomposition import run as _run
from orchestrator.workflow.state import WorkflowLabel

from tests.workflow.fixtures import _TEST_SPEC
from tests.workflow.stages.decomposition.late_content_support import late_issue
from tests.workflow.stages.decomposition.late_relabel_support import (
    SETTLED_GENERATIONS,
    relabelled,
)
from tests.workflow.stages.decomposition.late_test_support import (
    LATE_ISSUE_NUMBER,
)

DECOMPOSE = "DECOMPOSE"

HANDLE_IMPLEMENTING = "_handle_implementing"

RESTORED_MARKER = "still being adjudicated"

TRANSITION_GUARD = "WORKFLOW_TRANSITION_GUARD"

ENFORCE = "enforce"

SET_WORKFLOW_LABEL = "set_workflow_label"


class _LateLabelCase(unittest.TestCase):
    """One late issue something other than the adjudication tried to move."""

    def _route(self, github, issue) -> bool:
        """Take the kill switch's bailout with `DECOMPOSE=off`."""
        with patch.object(config, DECOMPOSE, False):
            with patch.object(_run._implementing, HANDLE_IMPLEMENTING):
                return _run._route_disabled_to_implementing(
                    github, _TEST_SPEC, issue, github.read_pinned_state(issue),
                )

    def _restore(self, github, issue) -> bool:
        return _late_relabel._restore_decomposing_label(
            github, issue, github.read_pinned_state(issue),
        )

    def _labels(self, github) -> list:
        return list(github.label_history)


class DisabledRouteTest(_LateLabelCase):
    """`DECOMPOSE=off` may not publish a candidate nobody adjudicated."""

    def test_a_live_generation_stays_where_it_is(self) -> None:
        github, issue = late_issue()

        self.assertTrue(self._route(github, issue))
        self.assertEqual(self._labels(github), [])
        self.assertEqual(github.posted_comments, [])

    def test_an_issue_with_nothing_live_still_routes(self) -> None:
        # The kill switch keeps meaning what it meant for every issue that is
        # only waiting to be decomposed.
        for label, generation in SETTLED_GENERATIONS:
            with self.subTest(generation=label):
                github, issue = late_issue(generation=generation)

                self.assertTrue(self._route(github, issue))
                self.assertEqual(
                    self._labels(github),
                    [(LATE_ISSUE_NUMBER, WorkflowLabel.IMPLEMENTING)],
                )


class LabelRestorationTest(_LateLabelCase):
    """A hand relabel is answered rather than obeyed."""

    def test_a_relabelled_issue_is_put_back(self) -> None:
        for label in (WorkflowLabel.READY, WorkflowLabel.IMPLEMENTING):
            with self.subTest(relabelled_to=label):
                github, issue = late_issue()
                relabelled(issue, label)

                self.assertTrue(self._restore(github, issue))
                self.assertEqual(
                    github.workflow_label(issue), WorkflowLabel.DECOMPOSING,
                )
                self.assertTrue(any(
                    RESTORED_MARKER in body
                    for _, body in github.posted_comments
                ))

    def test_an_enforced_guard_does_not_strand_it(self) -> None:
        # The transition graph describes the moves this orchestrator makes,
        # and `validating -> decomposing` is not one -- so a guarded write
        # would raise every tick under `enforce`, leaving the generation
        # stranded under the wrong label with a fresh notice each time.
        github, issue = late_issue()
        relabelled(issue, WorkflowLabel.VALIDATING)

        with patch.object(config, TRANSITION_GUARD, ENFORCE):
            restored = self._restore(github, issue)

        self.assertTrue(restored)
        self.assertEqual(
            github.workflow_label(issue), WorkflowLabel.DECOMPOSING,
        )
        self.assertEqual(len(github.posted_comments), 1)

    def test_a_restored_label_says_so_once(self) -> None:
        # The notice follows the write it announces, so a tick that could not
        # land the label says nothing and the retry is the one that speaks.
        github, issue = late_issue()
        relabelled(issue, WorkflowLabel.VALIDATING)
        with patch.object(github, SET_WORKFLOW_LABEL, side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                self._restore(github, issue)
        self.assertEqual(github.posted_comments, [])

        with patch.object(config, TRANSITION_GUARD, ENFORCE):
            self._restore(github, issue)
            self._restore(github, issue)

        self.assertEqual(len(github.posted_comments), 1)

    def test_the_label_it_pins_costs_a_tick_nothing(self) -> None:
        # A live generation sitting where it belongs is every tick of an
        # adjudication, so it must write neither a comment nor a label.
        github, issue = late_issue()

        self.assertFalse(self._restore(github, issue))
        self.assertEqual(github.posted_comments, [])
        self.assertEqual(self._labels(github), [])

    def test_a_settled_generation_pins_no_label(self) -> None:
        for label, generation in SETTLED_GENERATIONS:
            with self.subTest(generation=label):
                github, issue = late_issue(generation=generation)
                relabelled(issue, WorkflowLabel.READY)

                self.assertFalse(self._restore(github, issue))
                self.assertEqual(
                    github.workflow_label(issue), WorkflowLabel.READY,
                )
