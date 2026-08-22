# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Where a hand relabel is caught: the label becoming a handler call."""
from __future__ import annotations

import importlib
import unittest
from unittest.mock import Mock, patch

from orchestrator.workflow.engine import dispatch as _dispatch
from orchestrator.workflow.state import WorkflowLabel

from tests.workflow.fixtures import _TEST_SPEC
from tests.workflow.stages.decomposition.late_content_support import late_issue
from tests.workflow.stages.decomposition.late_relabel_support import (
    SETTLED_GENERATIONS,
    relabelled,
)

# What the dispatcher would hand a relabelled issue to. `ready` is the label a
# human reaches for to wave a candidate through, and its handler lives on the
# `blocked` owner -- so this is the module a coerced dispatch lands on.
READY_OWNER, READY_HANDLER = _dispatch._STAGE_HANDLER_TARGETS[
    WorkflowLabel.READY
]

READ_PINNED_STATE = "read_pinned_state"

SET_WORKFLOW_LABEL = "set_workflow_label"


class DispatchRefusalTest(unittest.TestCase):
    """A live adjudication may not reach the handler its label names."""

    def test_a_relabelled_generation_is_refused(self) -> None:
        # Nothing refuses the human's own label write, so the coercion is only
        # stoppable here: dispatching `ready` would hand the candidate to the
        # implementing handoff with no verdict on it.
        github, issue = late_issue()
        relabelled(issue, WorkflowLabel.READY)

        dispatched = self._route(github, issue)

        dispatched.assert_not_called()
        self.assertEqual(
            github.workflow_label(issue), WorkflowLabel.DECOMPOSING,
        )

    def test_a_settled_generation_routes_as_before(self) -> None:
        for label, generation in SETTLED_GENERATIONS:
            with self.subTest(generation=label):
                github, issue = late_issue(generation=generation)
                relabelled(issue, WorkflowLabel.READY)

                dispatched = self._route(github, issue)

                dispatched.assert_called_once_with(github, _TEST_SPEC, issue)

    def test_a_failed_repair_still_refuses(self) -> None:
        # The refusal is the safety property and the relabel is the repair, so
        # a label write that cannot land must not hand the issue to the very
        # handler this exists to keep it away from.
        github, issue = late_issue()
        relabelled(issue, WorkflowLabel.READY)

        with patch.object(
            github, SET_WORKFLOW_LABEL, side_effect=RuntimeError("nope"),
        ):
            dispatched = self._route(github, issue)

        dispatched.assert_not_called()
        self.assertEqual(github.workflow_label(issue), WorkflowLabel.READY)

    def test_an_unreadable_state_refuses(self) -> None:
        # The costs are not symmetric. Failing open publishes an unadjudicated
        # candidate -- the handler behind this reads the same pinned comment,
        # and a first read that failed transiently is followed by a second
        # that may well succeed. Failing closed costs one tick of one issue.
        github, issue = late_issue()
        relabelled(issue, WorkflowLabel.READY)

        with patch.object(
            github, READ_PINNED_STATE, side_effect=RuntimeError("blip"),
        ):
            dispatched = self._route(github, issue)

        dispatched.assert_not_called()

    def test_the_label_it_pins_is_never_read_for(self) -> None:
        # An adjudication spends every one of its own ticks on `decomposing`,
        # so the guard must cost that label nothing at all -- asked of the
        # guard itself, since the handler behind it reads state of its own.
        github, issue = late_issue()
        pinned_read = Mock()

        with patch.object(github, READ_PINNED_STATE, pinned_read):
            held = _dispatch._late_adjudication_holds_the_label(
                github, _TEST_SPEC, issue, WorkflowLabel.DECOMPOSING,
            )

        self.assertFalse(held)
        pinned_read.assert_not_called()

    def _route(self, github, issue):
        """Route one issue the way a tick does, reporting the handler call."""
        dispatched = Mock()
        label = github.workflow_label(issue)
        owner = importlib.import_module(READY_OWNER)
        with patch.object(owner, READY_HANDLER, dispatched):
            _dispatch._route_issue_to_handler(github, _TEST_SPEC, issue, label)
        return dispatched
