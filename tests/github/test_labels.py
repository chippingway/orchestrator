# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Label vocabulary, predicates, bootstrap, and owner-targeted bindings."""
from __future__ import annotations

import unittest
from types import MappingProxyType
from unittest.mock import MagicMock

from github import GithubException

from orchestrator.github import labels as _labels
from orchestrator.github.client import GitHubClient
from orchestrator.workflow.state import (
    ControlLabel,
    WorkflowLabel,
    legacy_label_name as _legacy_label_name,
)
from tests.support.fakes import FakeIssue, FakeLabel

_HTTP_FORBIDDEN = 403
_LEGACY_IMPLEMENTING = "implementing"
_NAME_KWARG = "name"
_LABEL_SPECS = _labels.WORKFLOW_LABEL_SPECS + _labels.CONTROL_LABEL_SPECS
_SPEC_BY_LABEL = MappingProxyType({spec[0]: spec for spec in _LABEL_SPECS})
# The labels the bootstrap has a pre-namespace spelling to rename: what the
# orchestrator writes itself, the automatic control label as much as a state.
# `backlog` / `paused` are the operator's to type and stay bare.
_RENAMED_LABELS = (
    WorkflowLabel.IMPLEMENTING,
    ControlLabel.COMMUNITY_CONTRIBUTION,
)


def _issue_with(*label_names: str) -> FakeIssue:
    return FakeIssue(
        number=1,
        labels=[FakeLabel(name) for name in label_names],
    )


def _repo_label(name: str) -> MagicMock:
    """A repository label the bootstrap can rename in place.

    `name` is assigned after construction because `MagicMock(name=...)`
    configures the mock's own repr instead of the attribute under test.
    """
    repo_label = MagicMock()
    repo_label.name = name
    return repo_label


# Issue label sets -> the workflow member `workflow_label` reads past any
# control modifiers (a control label coexists with the workflow state), and
# past a pre-namespace label sitting beside a namespaced one in either order.
_WORKFLOW_LABEL_CASES = (
    ((WorkflowLabel.IMPLEMENTING,), WorkflowLabel.IMPLEMENTING),
    (
        (ControlLabel.PAUSED, WorkflowLabel.IMPLEMENTING),
        WorkflowLabel.IMPLEMENTING,
    ),
    (
        (_LEGACY_IMPLEMENTING, WorkflowLabel.VALIDATING),
        WorkflowLabel.VALIDATING,
    ),
    (
        (WorkflowLabel.VALIDATING, _LEGACY_IMPLEMENTING),
        WorkflowLabel.VALIDATING,
    ),
    ((_LEGACY_IMPLEMENTING,), WorkflowLabel.IMPLEMENTING),
    ((ControlLabel.BACKLOG,), None),
    ((), None),
)

# Issue label sets -> the first hard-skip control label (backlog before
# paused); the community-contribution label coexists with the workflow state
# and never skips.
_HARD_SKIP_CASES = (
    ((ControlLabel.PAUSED, ControlLabel.BACKLOG), ControlLabel.BACKLOG),
    ((WorkflowLabel.IMPLEMENTING, ControlLabel.PAUSED), ControlLabel.PAUSED),
    ((ControlLabel.COMMUNITY_CONTRIBUTION,), None),
    ((WorkflowLabel.IN_REVIEW,), None),
)


class WorkflowLabelPredicateTest(unittest.TestCase):
    """`workflow_label` reports the FSM state, ignoring control modifiers.

    A control label coexists with the workflow state rather than masking it, so
    a paused, implementing issue still reports the implementing state. A bare
    pre-namespace label answers only when nothing namespaced does: the
    orchestrator writes only namespaced labels, so one beside a bare tag is
    the current state whichever order GitHub lists them in.
    """

    def test_reads_member_past_control_labels(self) -> None:
        for label_names, expected in _WORKFLOW_LABEL_CASES:
            with self.subTest(label_names=label_names):
                self.assertIs(
                    _labels.workflow_label(_issue_with(*label_names)),
                    expected,
                )


class IssueHasLabelTest(unittest.TestCase):
    def test_matches_case_insensitively(self) -> None:
        issue = _issue_with("Implementing")
        self.assertTrue(_labels.issue_has_label(issue, _LEGACY_IMPLEMENTING))
        self.assertTrue(_labels.issue_has_label(issue, "IMPLEMENTING"))

    def test_absent_label_is_false(self) -> None:
        self.assertFalse(_labels.issue_has_label(_issue_with("ready"), "done"))
        self.assertFalse(_labels.issue_has_label(_issue_with(), "ready"))


class HardSkipControlLabelTest(unittest.TestCase):
    """Only `backlog` and `paused` suppress processing, backlog reported first.

    The community-contribution label is registered for bootstrap but coexists
    with the workflow rather than pausing it, so it is never a hard skip.
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
            call.kwargs[_NAME_KWARG]: call.kwargs
            for call in self.gh.repo.create_label.call_args_list
        }
        self.assertNotIn(present[0], created)
        self.assertEqual(len(created), len(_LABEL_SPECS) - 1)
        self.assertEqual(
            created[absent[0]],
            {
                _NAME_KWARG: absent[0],
                "color": absent[1],
                "description": absent[2],
            },
        )

    def test_absent_control_label_is_namespaced(self) -> None:
        # A repository carrying neither spelling gets the namespaced name
        # outright, so the community sweep's dedup marker is born under the
        # same name the sweep later reads back off a PR.
        self.gh.repo.get_labels.return_value = []

        self.gh.ensure_workflow_labels()

        created = {
            call.kwargs[_NAME_KWARG]
            for call in self.gh.repo.create_label.call_args_list
        }
        self.assertIn(ControlLabel.COMMUNITY_CONTRIBUTION, created)
        self.assertNotIn(
            _legacy_label_name(ControlLabel.COMMUNITY_CONTRIBUTION), created,
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


class LegacyLabelRenameTest(unittest.TestCase):
    """The bootstrap renames the pre-namespace label instead of doubling it.

    A rename carries every issue already holding the old label across in one
    edit -- including the closed and `backlog`-parked ones no polling pass
    revisits, which a second label beside the first would strand. A PR the
    community sweep already labeled migrates the same way, which is what keeps
    its one HITL ping from repeating under a second spelling.
    """

    def setUp(self) -> None:
        self.gh = GitHubClient.__new__(GitHubClient)
        self.gh.repo = MagicMock()

    def test_renames_the_bare_label_in_place(self) -> None:
        for label in _RENAMED_LABELS:
            with self.subTest(label=label):
                # One repository per case: the creation calls of the case
                # before it would otherwise still be on the mock.
                self.gh.repo = MagicMock()
                spec = _SPEC_BY_LABEL[label]
                legacy_label = _repo_label(_legacy_label_name(label))
                self.gh.repo.get_labels.return_value = [legacy_label]

                self.gh.ensure_workflow_labels()

                legacy_label.edit.assert_called_once_with(
                    name=label, color=spec[1], description=spec[2],
                )
                created = {
                    call.kwargs[_NAME_KWARG]
                    for call in self.gh.repo.create_label.call_args_list
                }
                self.assertNotIn(label, created)

    def test_refused_rename_stops_bootstrap(self) -> None:
        # Same standing-down as a refused creation: an under-scoped PAT must
        # not make the bootstrap retry the denied edit once per spec.
        legacy_label = _repo_label(
            _legacy_label_name(WorkflowLabel.DECOMPOSING),
        )
        legacy_label.edit.side_effect = GithubException(
            _HTTP_FORBIDDEN,
            {"message": "Forbidden"},
            None,
        )
        self.gh.repo.get_labels.return_value = [legacy_label]

        self.gh.ensure_workflow_labels()

        self.gh.repo.create_label.assert_not_called()


if __name__ == "__main__":
    unittest.main()
