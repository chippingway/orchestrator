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


# The github-package modules plus every client-mixin leaf between `_github_api`
# and the `pinned_state` owner. The initializer binds the `labels`, `events`,
# and `issues` owners eagerly, and `_github_issues` (the pinned-state mixin's
# base) imports the package back for those surfaces, so importing any leaf
# first must run the initializer without re-entering a half-built one.
_MODULES = (
    "orchestrator.github",
    "orchestrator.github.events",
    "orchestrator.github.issues",
    "orchestrator.github.labels",
    "orchestrator.github.pinned_state",
    "orchestrator.github.client",
    "orchestrator._github_api",
    "orchestrator._github_internals",
    "orchestrator._github_feedback",
    "orchestrator._github_pull_checks",
    "orchestrator._github_pull_requests",
    "orchestrator._github_issues",
)


class CleanProcessImportTest(unittest.TestCase):
    """Each affected module imports standalone in a fresh interpreter.

    The owners are submodules of the same package whose `__init__` binds
    `labels`, `events`, and `issues` eagerly and whose mixin chain imports the
    package back for those surfaces, so importing the package, any of its
    submodules, or any mixin leaf directly must run the initializer without a
    partially-initialized-module error. A subprocess per module gives each a
    clean `sys.modules` no other test has already populated, exposing an
    import-order cycle a package-first suite run would mask.
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


class PinnedStateOwnershipTest(unittest.TestCase):
    """The package surface is backed by the owning modules' identities.

    A caller reaching a name through `orchestrator.github` sees the owning
    module's own object, so a monkeypatch on the owner stays observable through
    the facade rather than resolving a divergent copy.
    """

    def test_pinned_names_are_owner_re_exports(self) -> None:
        self.assertIs(_github.PinnedState, _pinned_state.PinnedState)
        self.assertIs(
            _github.PINNED_STATE_MARKER,
            _pinned_state.PINNED_STATE_MARKER,
        )
        self.assertIs(_github.PINNED_STATE_RE, _pinned_state.PINNED_STATE_RE)
        self.assertIs(
            _github.PINNED_STATE_BODY_RE,
            _pinned_state.PINNED_STATE_BODY_RE,
        )
        self.assertIs(
            _github.PINNED_STATE_TEMPLATE,
            _pinned_state.PINNED_STATE_TEMPLATE,
        )
        self.assertIs(
            _github._pinned_state_from_comment,
            _pinned_state.pinned_state_from_comment,
        )

    def test_client_resolves_to_the_client_owner(self) -> None:
        # `GitHubClient` is resolved lazily from `orchestrator.github.client`;
        # the facade must hand back the owner's class, not a rebuilt copy.
        self.assertIs(_github.GitHubClient, _github_client.GitHubClient)

    def test_client_inherits_the_state_mixin_owner(self) -> None:
        # The pinned-state read/write and comment-watermark methods reach the
        # client through the owner's mixin, so the owner class stays in the MRO.
        self.assertIn(
            _pinned_state.GitHubStateMixin,
            _github.GitHubClient.__mro__,
        )


if __name__ == "__main__":
    unittest.main()
