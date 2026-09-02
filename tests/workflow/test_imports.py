# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Clean-process import checks and package surface for the workflow package."""

from __future__ import annotations

import importlib
import pkgutil
import subprocess
import sys
import unittest
from importlib.util import find_spec
from unittest.mock import patch

from orchestrator import workflow as _workflow
from orchestrator.workflow import engine as _engine, state as _state

_TICK = "tick"

_TICK_OWNER = f"orchestrator.workflow.engine.{_TICK}"

_ENGINE_OWNERS = (
    "comments",
    "dispatch",
    "drift",
    "guards",
    "messages",
    "pickup",
    "prompts",
    "retry_budget",
    "run_ledger",
    "run_limit",
    "terminals",
    _TICK,
    "usage",
)

# The late-split domain's owners. They sit beside the engine rather than under
# it: the state round trip reaches the GitHub pinned-state model and the
# telemetry reaches the analytics recorders, both of which import the `state`
# owner's vocabulary back, so each has to load on its own.
_LATE_SPLIT_OWNERS = (
    "events",
    "exemption",
    "formats",
    "identity",
    "ledgers",
    "models",
    "payloads",
    "records",
    "restart",
    "state",
    "telemetry",
    "validation",
)

_MODULES = (
    "orchestrator.workflow",
    "orchestrator.workflow.engine",
    *(f"orchestrator.workflow.engine.{owner}" for owner in _ENGINE_OWNERS),
    "orchestrator.workflow.late_split",
    *(
        f"orchestrator.workflow.late_split.{owner}"
        for owner in _LATE_SPLIT_OWNERS
    ),
    "orchestrator.workflow.state",
)

# What importing the package must leave out of `sys.modules`: the dispatcher,
# the tick loop, the stage-handler tree, the git and GitHub subsystems those
# reach, the analytics recorders under them, and the config package behind those.
_DEFERRED_MODULES = (
    "orchestrator.config",
    "orchestrator.git",
    "orchestrator.github",
    "orchestrator.observability.analytics.recording",
    "orchestrator.workflow.engine",
    "orchestrator.workflow.engine.dispatch",
    _TICK_OWNER,
    "orchestrator.workflow.stages",
)

# The `state` owner is what the GitHub and git layers below the engine are typed
# by, so an import of it has to cost no more than the initializer it runs.
_LAZY_IMPORTS = (
    "orchestrator.workflow",
    "orchestrator.workflow.state",
)

_LAZINESS_PROBE = (
    "import sys;"
    "import {module};"
    "print(' '.join(name for name in {names!r} if name in sys.modules))"
)

# The paths a second import site for anything under this package would take: a
# flat spelling of the drift owner or of the comment, message, prompt, and
# decomposition manifest owners, the shared-value and dependency leaves the
# owners hold their own copies of, the inventory plus resolver a lazy surface
# over them would be rebuilt from, and the flat spelling of the `state` owner
# itself -- which would be a second identity for the transition graph and the
# write guard live issues already run on.
_FLAT_MODULES = (
    "orchestrator._workflow_dependencies",
    "orchestrator._workflow_export_manifest",
    "orchestrator._workflow_exports",
    "orchestrator._workflow_state",
    "orchestrator.state_machine",
    "orchestrator.workflow_drift",
    "orchestrator.workflow_messages",
)

_PUBLIC_SURFACE = (
    "ControlLabel",
    "IllegalTransition",
    "WorkflowLabel",
    "guard_transition",
    "is_allowed_transition",
    _TICK,
)

# Every published name but `tick` is the `state` owner's own object; `tick` is
# the one the package defines itself.
_STATE_NAMES = tuple(name for name in _PUBLIC_SURFACE if name != _TICK)

# The two operator-facing log channels this package reports on. Every engine and
# stage owner spells the first literally, and the `state` owner the second.
_WORKFLOW_CHANNEL = "orchestrator.workflow"

_STATE_CHANNEL = "orchestrator.state_machine"


class CleanProcessImportTest(unittest.TestCase):
    """The package, its subpackage, and each owner beneath them import alone.

    The engine owners import the GitHub and git layers, which import the `state`
    owner beside them and so run this initializer back. A subprocess per module
    gives each a clean `sys.modules` no other test has already populated,
    exposing an import-order cycle a package-first suite run would mask.
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

    def test_import_reaches_no_engine_or_subsystem(self) -> None:
        # The package boundary is where an accidental eager binding is cheapest
        # to add and hardest to notice: an engine import in the initializer
        # would drag the stage tree or the analytics graph into every
        # `orchestrator.workflow` import -- and into the GitHub and git layers
        # that import the state owner beside it, which is the cycle those layers
        # would then fail to import through.
        for module in _LAZY_IMPORTS:
            with self.subTest(module=module):
                self._assert_nothing_resolved(module)

    def _assert_nothing_resolved(self, module: str) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                _LAZINESS_PROBE.format(
                    module=module, names=_DEFERRED_MODULES,
                ),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertEqual(completed.stdout.strip(), "")


class PublicSurfaceTest(unittest.TestCase):
    """The initializer publishes one narrow API; the engine owns no names."""

    def test_all_names_the_narrow_public_surface(self) -> None:
        self.assertEqual(_workflow.__all__, _PUBLIC_SURFACE)
        for name in _STATE_NAMES:
            with self.subTest(name=name):
                self.assertIs(
                    getattr(_workflow, name), getattr(_state, name),
                )

    def test_tick_drives_the_engine_owner(self) -> None:
        # The entry point is defined here rather than re-exported, so what a
        # patch on the engine owner has to intercept is the call it makes.
        engine_tick = importlib.import_module(_TICK_OWNER)
        self.assertIsNot(_workflow.tick, engine_tick.tick)
        with patch.object(engine_tick, _TICK) as driven:
            _workflow.tick("gh", "spec", scheduler="scheduler")
            driven.assert_called_once_with(
                "gh", "spec", global_semaphore=None, scheduler="scheduler",
            )

    def test_engine_initializer_binds_nothing(self) -> None:
        # Importing an owner plants it in the package namespace, so a submodule
        # is the only thing allowed to appear here. A re-export beside it would
        # make the initializer a second identity for that owner and charge every
        # importer of one owner for the imports of all the others.
        for owner in _ENGINE_OWNERS:
            with self.subTest(owner=owner):
                imported = importlib.import_module(f"{_engine.__name__}.{owner}")
                self.assertIs(getattr(_engine, owner), imported)
        for name, bound in _engine.__dict__.items():
            if name.startswith("__"):
                continue
            with self.subTest(name=name):
                self.assertEqual(
                    getattr(bound, "__name__", None), f"{_engine.__name__}.{name}",
                )


class LoggerChannelTest(unittest.TestCase):
    """Every owner reports on the channel operators filter on.

    The name is spelled literally on each owner rather than derived from
    `__name__`, because it is what an operator's log filter and handler select
    on -- a module moved between packages must not move its own channel with it.
    """

    def test_every_owner_reports_on_its_channel(self) -> None:
        for module in self._modules_declaring_a_logger():
            with self.subTest(module=module.__name__):
                expected = (
                    _STATE_CHANNEL if module is _state else _WORKFLOW_CHANNEL
                )
                self.assertEqual(module.log.name, expected)

    def _modules_declaring_a_logger(self) -> list:
        found = [
            importlib.import_module(module.name)
            for module in pkgutil.walk_packages(
                _workflow.__path__, prefix=f"{_workflow.__name__}.",
            )
        ]
        return [module for module in found if hasattr(module, "log")]


class OwnerImportSiteTest(unittest.TestCase):
    """The engine owners are the only modules their surfaces answer on."""

    def test_no_flat_module_exists(self) -> None:
        # Anything importable at these paths would be a second identity for the
        # hash live issues are already parked on, the marker their comments are
        # stamped with, or the prompt text an agent is spawned with -- free to
        # drift from the owner silently and invisible to a patch aimed at it.
        # Resolving the spec rather than stat-ing one path catches a copy
        # planted anywhere the interpreter would find it.
        for module in _FLAT_MODULES:
            with self.subTest(module=module):
                self.assertIsNone(find_spec(module))


if __name__ == "__main__":
    unittest.main()
