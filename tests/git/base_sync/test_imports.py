# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Clean-process import, layering, and facade checks for base sync."""

from __future__ import annotations

import subprocess
import sys
import unittest

from orchestrator import base_sync, git
from orchestrator.git.base_sync import models, state

_MODELS_OWNER = "orchestrator.git.base_sync.models"

_STATE_OWNER = "orchestrator.git.base_sync.state"

_OWNERS = (_MODELS_OWNER, _STATE_OWNER)

_MODULES = ("orchestrator.git.base_sync", *_OWNERS, "orchestrator.base_sync")

# The state owner exists to spell out the pinned-state keys and the label
# vocabulary one rebase attempt is routed by, so the label enum and the
# transition graph behind it are the only orchestrator modules it may reach.
_STATE_ALLOWED_MODULES = (
    "orchestrator",
    "orchestrator._package_exports",
    "orchestrator._state_transitions",
    "orchestrator._workflow_labels",
    "orchestrator.state_machine",
)

_STATE_ALLOWED_ROOT = "orchestrator.git"

# The model owner annotates its fields with the composed GitHub client, which
# drags the analytics and usage graph in behind it, so an allowlist would not
# describe it. What both owners owe is the direction of the dependency: neither
# may reach the base-sync leaves, the facade over them, the workflow engine and
# its stage handlers, or an application entrypoint. The facade is the sharpest
# of those, because it resolves the very names these owners define -- an owner
# that imported it would be reading its own definitions back out.
_FORBIDDEN_PREFIXES = (
    "orchestrator._base_sync",
    "orchestrator.base_sync",
    "orchestrator.cli",
    "orchestrator.main",
    "orchestrator.stages",
    "orchestrator.verify",
    "orchestrator.workflow",
    "orchestrator.worktree",
)

_LAYERING_SCRIPT = """
import sys
import {module}
print(*sorted(name for name in sys.modules if name.startswith('orchestrator')))
"""

# The initializer binds nothing, so each name stays reachable only through its
# owner or the historical `base_sync` facade.
_OWNER_ONLY_NAMES = (
    "_AUTO_REBASE_PARK_REASONS",
    "_AutoRebaseContext",
    "_AutoRebaseRequest",
    "_PENDING_PUSH_SHA",
    "log",
)

_FACADE_FORWARDS = (
    ("_AUTO_REBASE_PARK_REASONS", state),
    ("_AWAITING_HUMAN", state),
    ("_AutoRebaseContext", models),
    ("_AutoRebaseDecision", models),
    ("_AutoRebaseRecoveryContext", models),
    ("_AutoRebaseRecoverySnapshot", models),
    ("_AutoRebaseRequest", models),
    ("_CONFLICT_ROUND", state),
    ("_ConflictRouteContext", models),
    ("_ERROR_SNIPPET_LEN", state),
    ("_PARK_REASON", state),
    ("_PENDING_PUSH_SHA", state),
    ("_PR_REFRESH_DETOUR_LABELS", state),
    ("_REASON_AUTO_BASE_REBASE_FAILED", state),
    ("_REASON_AUTO_BASE_REBASE_PUSH_FAILED", state),
    ("_REVIEW_ROUND", state),
    ("log", state),
)


def _imported_orchestrator_modules(module: str) -> list[str]:
    """Names of the orchestrator modules a fresh `import module` pulls in."""
    completed = subprocess.run(
        [sys.executable, "-c", _LAYERING_SCRIPT.format(module=module)],
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.split()


class CleanProcessImportTest(unittest.TestCase):
    """Each base-sync module imports standalone in a fresh interpreter.

    The owners bind their collaborators at import time while the `base_sync`
    facade resolves them lazily, so importing any one of them first must not
    need a name a half-run module has not defined yet. A subprocess per module
    gives each a clean `sys.modules` no other test has already populated,
    exposing an import-order cycle a facade-first suite run would mask.
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


class LayeringTest(unittest.TestCase):
    """The owners import nothing from the base-sync leaves or above them."""

    def test_state_owner_stays_in_label_layer(self) -> None:
        for imported in _imported_orchestrator_modules(_STATE_OWNER):
            self.assertTrue(
                self._within_state_layers(imported),
                f"the state owner reaches past the label vocabulary via {imported}",
            )

    def test_owners_stay_below_base_sync_leaves(self) -> None:
        for module in _OWNERS:
            with self.subTest(module=module):
                for imported in _imported_orchestrator_modules(module):
                    self.assertFalse(
                        imported.startswith(_FORBIDDEN_PREFIXES),
                        f"{module} inverts the dependency via {imported}",
                    )

    def _within_state_layers(self, imported: str) -> bool:
        if imported in _STATE_ALLOWED_MODULES:
            return True
        return imported == _STATE_ALLOWED_ROOT or imported.startswith(
            f"{_STATE_ALLOWED_ROOT}.",
        )


class PackageSurfaceTest(unittest.TestCase):
    """The initializer carries no bindings; `base_sync` forwards to owners."""

    def test_initializer_exposes_no_owner_names(self) -> None:
        for owner_only_name in _OWNER_ONLY_NAMES:
            with self.subTest(name=owner_only_name):
                with self.assertRaises(AttributeError):
                    getattr(git.base_sync, owner_only_name)

    def test_facade_resolves_owner_objects(self) -> None:
        # The facade forwards rather than rebuilding, so a leaf reading a
        # context class or a pinned-state key off `base_sync` -- and the
        # patches aimed at that facade -- see the owner's definition.
        for export_name, owner in _FACADE_FORWARDS:
            with self.subTest(name=export_name):
                self.assertIs(
                    getattr(base_sync, export_name),
                    getattr(owner, export_name),
                )


if __name__ == "__main__":
    unittest.main()
