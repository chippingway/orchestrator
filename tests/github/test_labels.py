# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Label vocabulary, predicates, and facade ownership for the github package."""
from __future__ import annotations

import importlib
import unittest
from unittest.mock import patch

from orchestrator import github as _github
from orchestrator.github import labels as _labels
from orchestrator.state_machine import ControlLabel, WorkflowLabel

from tests.fakes import FakeIssue, FakeLabel

_FACADE_LABEL_NAMES = (
    "WORKFLOW_LABEL_SPECS",
    "WORKFLOW_LABELS",
    "BACKLOG_LABEL",
    "PAUSED_LABEL",
    "COMMUNITY_CONTRIBUTION_LABEL",
    "CONTROL_LABEL_SPECS",
    "HARD_SKIP_CONTROL_LABELS",
    "issue_has_label",
    "hard_skip_control_label",
)

# Workflow-facing facade -> the label names it re-exports. Each must resolve
# through the `labels` owner, not the eager `orchestrator.github` copies, so a
# monkeypatch on the owner stays observable through the facade.
_LABEL_FACADE_BINDINGS = (
    ("orchestrator.workflow", "COMMUNITY_CONTRIBUTION_LABEL"),
    ("orchestrator.workflow", "hard_skip_control_label"),
    ("orchestrator.base_sync", "hard_skip_control_label"),
    ("orchestrator.base_sync", "issue_has_label"),
)


def _issue_with(*label_names: str) -> FakeIssue:
    return FakeIssue(
        number=1,
        labels=[FakeLabel(name) for name in label_names],
    )


# Issue label sets -> the workflow member `workflow_label` reads past any
# control modifiers (a control label coexists with the workflow state).
_WORKFLOW_LABEL_CASES = (
    ((WorkflowLabel.IMPLEMENTING,), WorkflowLabel.IMPLEMENTING),
    (
        (ControlLabel.PAUSED, WorkflowLabel.IMPLEMENTING),
        WorkflowLabel.IMPLEMENTING,
    ),
    ((ControlLabel.BACKLOG,), None),
    ((), None),
)

# Issue label sets -> the first hard-skip control label (backlog before
# paused); `community_contribution` coexists with the workflow and never skips.
_HARD_SKIP_CASES = (
    ((ControlLabel.PAUSED, ControlLabel.BACKLOG), ControlLabel.BACKLOG),
    ((WorkflowLabel.IMPLEMENTING, ControlLabel.PAUSED), ControlLabel.PAUSED),
    ((ControlLabel.COMMUNITY_CONTRIBUTION,), None),
    ((WorkflowLabel.IN_REVIEW,), None),
)


class LabelFacadeOwnershipTest(unittest.TestCase):
    """The package surface hands back the `labels` owner's own objects.

    A caller reaching a label name through `orchestrator.github` sees the
    owning module's object, so a monkeypatch on the owner stays observable
    through the facade rather than resolving a divergent copy.
    """

    def test_facade_names_are_owner_re_exports(self) -> None:
        for name in _FACADE_LABEL_NAMES:
            with self.subTest(name=name):
                self.assertIs(getattr(_github, name), getattr(_labels, name))


class LabelFacadeBindingTest(unittest.TestCase):
    """Workflow-facing facades resolve label names from the `labels` owner.

    `orchestrator.github` holds eager copies of the label surface, so a lazy
    binding resolved through it would miss a monkeypatch on the owner. Targeting
    `orchestrator.github.labels` keeps each binding observing the owner's live
    attribute.
    """

    def test_facade_binding_observes_owner_patch(self) -> None:
        sentinel = object()
        for facade_name, export_name in _LABEL_FACADE_BINDINGS:
            with self.subTest(facade=facade_name, export=export_name):
                self._assert_observes_patch(facade_name, export_name, sentinel)

    def _assert_observes_patch(
        self,
        facade_name: str,
        export_name: str,
        sentinel: object,
    ) -> None:
        facade = importlib.import_module(facade_name)
        # Drop any cached resolution (before) and the patched one (after
        # teardown) so the binding re-resolves through the facade `__getattr__`.
        facade.__dict__.pop(export_name, None)
        self.addCleanup(facade.__dict__.pop, export_name, None)
        with patch.object(_labels, export_name, sentinel):
            self.assertIs(getattr(facade, export_name), sentinel)


class WorkflowLabelPredicateTest(unittest.TestCase):
    """`workflow_label` reports the FSM state, ignoring control modifiers.

    A control label coexists with the workflow state rather than masking it, so
    a paused, implementing issue still reports `implementing`.
    """

    def test_reads_member_past_control_labels(self) -> None:
        for label_names, expected in _WORKFLOW_LABEL_CASES:
            with self.subTest(label_names=label_names):
                self.assertIs(
                    _labels.workflow_label(_issue_with(*label_names)),
                    expected,
                )

    def test_static_helper_alias_yields_the_function(self) -> None:
        # `WORKFLOW_LABEL_METHOD` binds `workflow_label` unchanged onto the
        # client class, so class or instance access returns the module function.
        self.assertIs(
            _labels.WORKFLOW_LABEL_METHOD.__get__(None, object),
            _labels.workflow_label,
        )


class IssueHasLabelTest(unittest.TestCase):
    def test_matches_case_insensitively(self) -> None:
        issue = _issue_with("Implementing")
        self.assertTrue(_labels.issue_has_label(issue, "implementing"))
        self.assertTrue(_labels.issue_has_label(issue, "IMPLEMENTING"))

    def test_absent_label_is_false(self) -> None:
        self.assertFalse(_labels.issue_has_label(_issue_with("ready"), "done"))
        self.assertFalse(_labels.issue_has_label(_issue_with(), "ready"))


class HardSkipControlLabelTest(unittest.TestCase):
    """Only `backlog` and `paused` suppress processing, backlog reported first.

    `community_contribution` is registered for bootstrap but coexists with the
    workflow rather than pausing it, so it is never a hard skip.
    """

    def test_reports_first_hard_skip_control_label(self) -> None:
        for label_names, expected in _HARD_SKIP_CASES:
            with self.subTest(label_names=label_names):
                self.assertIs(
                    _labels.hard_skip_control_label(_issue_with(*label_names)),
                    expected,
                )


if __name__ == "__main__":
    unittest.main()
