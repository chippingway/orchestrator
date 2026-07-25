# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Compatibility contracts introduced by the runtime-core split."""
from __future__ import annotations

import importlib
import subprocess
import sys
import unittest

from orchestrator import __version__ as imported_version
from orchestrator.github import (
    GitHubClient,
    PinnedState,
    labels,
    pull_requests,
)
from orchestrator.state_machine import WorkflowLabel, coerce_workflow_label

_VALIDATING_LABEL = "validating"
_STATIC_HELPERS = (
    ("workflow_label", labels.workflow_label),
    ("pr_has_label", pull_requests.pr_has_label),
    ("pr_state", pull_requests.pr_state),
    ("pr_is_mergeable", pull_requests.pr_is_mergeable),
)
_ORCHESTRATOR_PACKAGE = importlib.import_module("orchestrator")


class PackageExportTest(unittest.TestCase):
    def test_version_import_surface(self) -> None:
        self.assertEqual(_ORCHESTRATOR_PACKAGE.__version__, imported_version)
        self.assertIn("__version__", _ORCHESTRATOR_PACKAGE.__dir__())

    def test_wildcard_import_exposes_only_the_version(self) -> None:
        command = "from orchestrator import *; print(__version__)"
        completed = subprocess.run(
            [sys.executable, "-c", command],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.stdout.strip(), imported_version)
        self.assertEqual(_ORCHESTRATOR_PACKAGE.__all__, ("__version__",))


class MainModuleEntrypointTest(unittest.TestCase):
    def test_module_launch_resolves_runtime_facade(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-m", "orchestrator.main", "--help"],
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Agent orchestrator polling loop.", completed.stdout)


class PinnedStateCompatibilityTest(unittest.TestCase):
    def test_keywords_share_data_attribute(self) -> None:
        state_data = {"branch": "orchestrator/issue-7"}
        descriptive_state = PinnedState(state_data=state_data)
        legacy_state = PinnedState(data=state_data)

        self.assertIs(descriptive_state.data, state_data)
        self.assertIs(legacy_state.state_data, state_data)

    def test_data_assignment_updates_internal_state(self) -> None:
        pinned_state = PinnedState()
        replacement = {"review_round": 2}

        pinned_state.data = replacement

        self.assertIs(pinned_state.state_data, replacement)

    def test_invalid_keywords(self) -> None:
        with self.assertRaises(TypeError):
            PinnedState(state_data={}, data={})
        with self.assertRaises(TypeError):
            PinnedState(payload={})


class GitHubStaticHelperCompatibilityTest(unittest.TestCase):
    def test_static_helper_identity(self) -> None:
        github_client = GitHubClient.__new__(GitHubClient)
        for attribute_name, module_function in _STATIC_HELPERS:
            with self.subTest(attribute_name=attribute_name):
                self.assertIs(
                    getattr(GitHubClient, attribute_name),
                    module_function,
                )
                self.assertIs(
                    getattr(github_client, attribute_name),
                    module_function,
                )


class WorkflowLabelInputCompatibilityTest(unittest.TestCase):
    def test_descriptive_and_legacy_keywords_coerce(self) -> None:
        expected_label = WorkflowLabel.VALIDATING
        self.assertIs(
            coerce_workflow_label(label_name=_VALIDATING_LABEL),
            expected_label,
        )
        self.assertIs(
            coerce_workflow_label(value=_VALIDATING_LABEL),
            expected_label,
        )

    def test_invalid_keywords(self) -> None:
        with self.assertRaises(TypeError):
            coerce_workflow_label(_VALIDATING_LABEL, value="done")
        with self.assertRaises(TypeError):
            coerce_workflow_label(label=_VALIDATING_LABEL)


if __name__ == "__main__":
    unittest.main()
