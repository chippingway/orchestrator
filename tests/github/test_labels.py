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
_LABEL_SPECS = _labels.WORKFLOW_LABEL_SPECS + _labels.CONTROL_LABEL_SPECS
_SPEC_BY_LABEL = MappingProxyType(
    {spec[0]: spec for spec in _labels.WORKFLOW_LABEL_SPECS},
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
# paused); `community_contribution` coexists with the workflow and never skips.
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


class LegacyLabelRenameTest(unittest.TestCase):
    """The bootstrap renames the pre-namespace label instead of doubling it.

    A rename carries every issue already holding the old label across in one
    edit -- including the closed and `backlog`-parked ones no polling pass
    revisits, which a second label beside the first would strand.
    """

    def setUp(self) -> None:
        self.gh = GitHubClient.__new__(GitHubClient)
        self.gh.repo = MagicMock()

    def test_renames_the_bare_label_in_place(self) -> None:
        legacy_label = _repo_label(
            _legacy_label_name(WorkflowLabel.IMPLEMENTING),
        )
        self.gh.repo.get_labels.return_value = [legacy_label]

        self.gh.ensure_workflow_labels()

        legacy_label.edit.assert_called_once_with(
            name=WorkflowLabel.IMPLEMENTING,
            color=_SPEC_BY_LABEL[WorkflowLabel.IMPLEMENTING][1],
            description=_SPEC_BY_LABEL[WorkflowLabel.IMPLEMENTING][2],
        )
        created = {
            call.kwargs["name"]
            for call in self.gh.repo.create_label.call_args_list
        }
        self.assertNotIn(WorkflowLabel.IMPLEMENTING, created)

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
