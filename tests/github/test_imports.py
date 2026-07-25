# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Clean-process import checks and owner identity for the github package."""

from __future__ import annotations

import subprocess
import sys
import unittest

from orchestrator import github as _github
from orchestrator.github import client as _github_client
from orchestrator.github import pinned_state as _pinned_state


# The package and every owner module. The initializer imports the `client`
# owner, which pulls the whole mixin chain, and chain leaves import the package
# back for their sibling owners, so importing any owner first must run the
# initializer without re-entering a half-built one.
_MODULES = (
    "orchestrator.github",
    "orchestrator.github.checks",
    "orchestrator.github.client",
    "orchestrator.github.events",
    "orchestrator.github.issues",
    "orchestrator.github.labels",
    "orchestrator.github.pinned_state",
    "orchestrator.github.pull_requests",
    "orchestrator.github.reviews",
)

# Owner-only names the facade must not resolve: the domain surfaces each have an
# owner module callers import directly.
_OWNER_ONLY_NAMES = (
    "PINNED_STATE_MARKER",
    "WORKFLOW_LABELS",
    "hard_skip_control_label",
    "build_event_record",
    "_iter_new_non_pr_issues",
    "_review_state_for_head",
    "_normalize_check_runs",
)


class CleanProcessImportTest(unittest.TestCase):
    """Each affected module imports standalone in a fresh interpreter.

    The owners are submodules of the same package, and both the `issues` owner
    and the mixin chain the initializer imports reach back into the package for
    their sibling owners, so importing the package or any of its submodules
    directly must run the initializer without a partially-initialized-module
    error. A subprocess per module gives each a clean `sys.modules` no other test
    has already populated, exposing an import-order cycle a package-first suite
    run would mask.
    """

    def test_each_module_imports_standalone(self) -> None:
        for module in _MODULES:
            with self.subTest(module=module):
                completed = subprocess.run(
                    [sys.executable, "-c", f"import {module}"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, msg=completed.stderr)


class PublicSurfaceTest(unittest.TestCase):
    """The facade publishes a narrow `__all__` backed by owner identities."""

    def test_all_names_the_narrow_public_surface(self) -> None:
        self.assertEqual(
            _github.__all__,
            (
                "GitHubClient",
                "PinnedState",
            ),
        )

    def test_public_names_are_owner_re_exports(self) -> None:
        # Each public name resolves to the owning module's object rather than a
        # rebuilt copy, so a caller reaching through the facade sees the owner's
        # definition.
        self.assertIs(_github.GitHubClient, _github_client.GitHubClient)
        self.assertIs(_github.PinnedState, _pinned_state.PinnedState)

    def test_facade_hides_owner_only_names(self) -> None:
        for owner_only_name in _OWNER_ONLY_NAMES:
            with self.subTest(name=owner_only_name):
                with self.assertRaises(AttributeError):
                    getattr(_github, owner_only_name)

    def test_client_inherits_the_state_mixin_owner(self) -> None:
        # The pinned-state read/write and comment-watermark methods reach the
        # client through the owner's mixin, so the owner class stays in the MRO.
        self.assertIn(
            _pinned_state.GitHubStateMixin,
            _github.GitHubClient.__mro__,
        )


if __name__ == "__main__":
    unittest.main()
