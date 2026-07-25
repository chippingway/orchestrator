# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Label vocabulary, predicates, bootstrap, and owner-targeted bindings."""
from __future__ import annotations

import importlib
import unittest
from unittest.mock import MagicMock, patch

from github import GithubException

from orchestrator.github import labels as _labels
from orchestrator.github.client import GitHubClient
from orchestrator.state_machine import ControlLabel, WorkflowLabel

from tests.fakes import FakeIssue, FakeLabel

_HTTP_FORBIDDEN = 403
_LABEL_SPECS = _labels.WORKFLOW_LABEL_SPECS + _labels.CONTROL_LABEL_SPECS

# Workflow-facing facade -> the label names it re-exports. Each must resolve
# through the `labels` owner rather than a copy, so a monkeypatch on the owner
# stays observable through the facade.
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


class LabelFacadeBindingTest(unittest.TestCase):
    """Workflow-facing facades resolve label names from the `labels` owner.

    A lazy binding declared against a module that only holds a copy of the label
    surface would miss a monkeypatch on the owner. Targeting
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


class EnsureWorkflowLabelsTest(unittest.TestCase):
    """Bootstrap creates the missing vocabulary and never blocks the loop.

    The PAT may lack `Issues: Read and write`, and the orchestrator has to keep
    polling either way: a failed listing skips the pass entirely, and a failed
    creation stops after the first refusal instead of retrying it per spec.
    """

    def setUp(self) -> None:
        # Bypass the networked __init__; the bootstrap reads only `self.repo`.
        self.gh = GitHubClient.__new__(GitHubClient)
        self.gh.repo = MagicMock()

    def test_creates_only_the_absent_labels(self) -> None:
        present, absent = _LABEL_SPECS[0], _LABEL_SPECS[1]
        self.gh.repo.get_labels.return_value = [FakeLabel(present[0])]

        self.gh.ensure_workflow_labels()

        created = {
            call.kwargs["name"]: call.kwargs
            for call in self.gh.repo.create_label.call_args_list
        }
        self.assertNotIn(present[0], created)
        self.assertEqual(len(created), len(_LABEL_SPECS) - 1)
        self.assertEqual(
            created[absent[0]],
            {
                "name": absent[0],
                "color": absent[1],
                "description": absent[2],
            },
        )

    def test_unreadable_labels_skip_the_bootstrap(self) -> None:
        self.gh.repo.get_labels.side_effect = GithubException(
            _HTTP_FORBIDDEN,
            {"message": "Forbidden"},
            None,
        )

        self.gh.ensure_workflow_labels()

        self.gh.repo.create_label.assert_not_called()

    def test_refused_creation_stops_bootstrap(self) -> None:
        self.gh.repo.get_labels.return_value = []
        self.gh.repo.create_label.side_effect = GithubException(
            _HTTP_FORBIDDEN,
            {"message": "Forbidden"},
            None,
        )

        self.gh.ensure_workflow_labels()

        self.gh.repo.create_label.assert_called_once()


if __name__ == "__main__":
    unittest.main()
